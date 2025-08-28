import os
import asyncio
from collections import defaultdict, deque
from dotenv import load_dotenv

import discord
from discord.ext import commands

# OpenAI SDK (ny stil)
from openai import OpenAI

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Enkel "minne" per kanal (ikke persistent – lagres i RAM)
# Vi beholder maks 30 utvekslinger pr kanal for kontekst.
channel_memory = defaultdict(lambda: deque(maxlen=30))

# Systemrolle: gjør KI til "siste gruppemedlem" (Oppg. 3-kravet)
SYSTEM_PROMPT = (
    "Du er gruppens KI-medlem. Vær presis, hjelpsom og kortfattet. "
    "Hjelp med: intervjuguider, dokumentanalyse, organisasjonsanalyse, "
    "SPGR-refleksjon (ikke finn på resultater), og forslag til tiltak."
)

# OpenAI-klient (kan være None hvis API-nøkkel mangler)
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

async def call_openai(messages):
    """Kaller OpenAI hvis API-nøkkel finnes, ellers faller tilbake til “gratis”-modus."""
    if client is None:
        # Gratis fallback: enkel heuristikk
        return ("(Gratismodus) Jeg mangler OpenAI-nøkkel, så jeg svarer enkelt. "
                "Be eieren legge inn OPENAI_API_KEY i .env for fulle svar 🤖.")
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"Feil mot KI: {e}"

def build_history(channel_id, user_prompt):
    """Bygger meldingshistorikk for kanalen med systemprompt på topp."""
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    for role, content in channel_memory[channel_id]:
        history.append({"role": role, "content": content})
    history.append({"role": "user", "content": user_prompt})
    return history

@bot.event
async def on_ready():
    print(f"✅ Logget inn som {bot.user} – klar for gruppesamarbeid!")

# --- Kjernekommando: fri spørsmål til KI ---
@bot.command(name="ask")
async def ask(ctx, *, prompt: str):
    """Fri spørsmål/samtale med KI-en. Bruk: !ask <spørsmål>"""
    history = build_history(ctx.channel.id, prompt)
    reply = await call_openai(history)
    # Oppdater minnet
    channel_memory[ctx.channel.id].append(("user", prompt))
    channel_memory[ctx.channel.id].append(("assistant", reply))
    await ctx.send(reply)

# --- Nyttig for Oppg. 2: intervjuguide ---
@bot.command(name="intervjuguide")
async def intervjuguide(ctx, *, bransje_eller_tema: str = ""):
    """
    Lager intervjuguide for casebedrift.
    Bruk: !intervjuguide <bransje/tema>  (valgfritt)
    """
    prompt = (
        "Lag en kort intervjuguide (10–15 spørsmål) til en casebedrift. "
        "Dekke: strategi/verdiforslag, organisering/ledelse, kultur/endringsvilje, "
        "dagens arbeidsprosesser (som kan digitaliseres), gevinst/tap for ulike aktører, "
        "grønn omstilling. Nummerer og grupper i temaer."
    )
    if bransje_eller_tema:
        prompt += f" Bransje/tema: {bransje_eller_tema}."
    history = build_history(ctx.channel.id, prompt)
    reply = await call_openai(history)
    channel_memory[ctx.channel.id].append(("user", prompt))
    channel_memory[ctx.channel.id].append(("assistant", reply))
    await ctx.send(reply)

# --- Nyttig for Oppg. 2: dokumentanalyse / intervjuoppsummering ---
@bot.command(name="analyse")
async def analyse(ctx, *, tekst: str):
    """
    Lim inn notater/utdrag. Botten gir stikkordsoppsummering + funn.
    Bruk: !analyse <tekst/utdrag>
    """
    prompt = (
        "Oppsummer og analyser teksten under i punktform for Oppgave 2. "
        "1) Nøkkelfakta (strategi, organisering, kultur, prosesser) "
        "2) Mulige digitaliseringstiltak (+ påvirkede roller) "
        "3) Mulig effekt på grønt skifte "
        "4) Åpne spørsmål til videre intervju.\n\nTEKST:\n" + tekst
    )
    history = build_history(ctx.channel.id, prompt)
    reply = await call_openai(history)
    channel_memory[ctx.channel.id].append(("user", prompt))
    channel_memory[ctx.channel.id].append(("assistant", reply))
    await ctx.send(reply[:1900] if len(reply) > 1900 else reply)

# --- Nyttig for Oppg. 2: teknologi-beskrivelse ---
@bot.command(name="teknologi")
async def teknologi(ctx, *, beskrivelse: str):
    """
    Beskriv en valgt digital teknologi for casebedriften.
    Bruk: !teknologi <kort hva/hvorfor>
    """
    prompt = (
        "Lag en konsis beskrivelse av en ny digital teknologi for casebedriften: "
        "Hva det er, hvordan den virker, hvilke behov den løser, krav til innføring, "
        "kost/nytte, risiko, KPI-er, og hvordan den kan bidra til grønn omstilling. \n"
        f"Teknologivalg/kontekst: {beskrivelse}"
    )
    history = build_history(ctx.channel.id, prompt)
    reply = await call_openai(history)
    channel_memory[ctx.channel.id].append(("user", prompt))
    channel_memory[ctx.channel.id].append(("assistant", reply))
    await ctx.send(reply)

# --- Nyttig for Oppg. 3: SPGR-refleksjon og tiltak ---
@bot.command(name="spgr")
async def spgr(ctx, *, status_eller_funn: str):
    """
    Hjelp til SPGR-analyse og tiltak.
    Bruk: !spgr <kort om testfunn/status>
    """
    prompt = (
        "Med utgangspunkt i følgende SPGR-status/funn, gi: "
        "1) Sannsynlige styrker/svakheter i gruppen "
        "2) Konkrete tiltak (atferd/struktur/verktøy) "
        "3) Hvordan måle effekt i SPGR II "
        "4) Risikoer og mottiltak.\n\n"
        f"SPGR-funn/tekst: {status_eller_funn}"
    )
    history = build_history(ctx.channel.id, prompt)
    reply = await call_openai(history)
    channel_memory[ctx.channel.id].append(("user", prompt))
    channel_memory[ctx.channel.id].append(("assistant", reply))
    await ctx.send(reply)

# --- Minne: nullstill kanal ---
@bot.command(name="reset")
async def reset(ctx):
    channel_memory[ctx.channel.id].clear()
    await ctx.send("🧠 Minne for denne kanalen er nullstilt.")

# --- Enkle gratis-kommandoer ---
@bot.command(name="hei")
async def hei(ctx):  # fungerer uten OpenAI
    await ctx.send("Hei! Jeg er gruppens KI-medlem 🤖 Skriv !ask <spørsmål> for å starte.")

@bot.command(name="hjelp")
async def hjelp(ctx):
    await ctx.send(
        "Kommandoer: !ask <spm>, !intervjuguide [tema], !analyse <tekst>, "
        "!teknologi <beskrivelse>, !spgr <status>, !reset"
    )

bot.run(DISCORD_TOKEN)
