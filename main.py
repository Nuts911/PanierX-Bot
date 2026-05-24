import discord
from discord.ext import commands
import os
import asyncio
import aiohttp
import re
import io

TOKEN = os.getenv("TOKEN")
OWNER_IDS = [766337426846646273, 1318912814353481778]

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="+", intents=intents, help_command=None)

user_ticket = {}

# ================================================================
#  CONSTANTES
# ================================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
}

# Domaines ignorés (pas du media, on les garde dans le texte)
IGNORED_DOMAINS = [
    "gofile.io", "gofile.me",
    "mediafire.com",
    "mega.nz", "mega.co.nz",
    "drive.google.com",
    "dropbox.com",
    "wetransfer.com", "we.tl",
    "anonfiles.com",
    "pixeldrain.com",
    "krakenfiles.com",
    "uploadhaven.com",
    "zippyshare.com",
    "1fichier.com",
    "uptobox.com",
    "turbobit.net",
    "file.io",
    "sendspace.com",
    "workupload.com"
]

# Domaines reconnus comme media
MEDIA_DOMAINS = ["tenor.com", "giphy.com", "imgur.com"]

# Extensions reconnues comme media
MEDIA_EXTENSIONS = [".gif", ".png", ".jpg", ".jpeg", ".webp", ".bmp"]


# ================================================================
#  UTILS
# ================================================================

def emb(text: str, color=discord.Color.light_gray()) -> discord.Embed:
    return discord.Embed(description=text, color=color)

def is_owner(ctx) -> bool:
    return ctx.author.id == OWNER_ID

def is_media_url(url: str) -> bool:
    """Vérifie si l'URL est un media (image/gif) et PAS un lien de partage"""
    lower = url.lower()

    # Ignoré = pas du media
    if any(d in lower for d in IGNORED_DOMAINS):
        return False

    # Domaine media connu
    if any(d in lower for d in MEDIA_DOMAINS):
        return True

    # Extension media directe
    if any(lower.split("?")[0].endswith(ext) for ext in MEDIA_EXTENSIONS):
        return True

    return False


# ================================================================
#  RESOLVER - Trouve la vraie URL du GIF/image
# ================================================================

async def get_media_url(url: str) -> str | None:
    async with aiohttp.ClientSession(headers=HEADERS) as session:

        # ── TENOR ──
        if "tenor.com" in url:

            # 1) API Tenor v2
            try:
                match = re.search(r"-(\d+)$", url.rstrip("/"))
                if match:
                    gif_id = match.group(1)
                    api = (
                        f"https://tenor.googleapis.com/v2/posts?ids={gif_id}"
                        f"&key=AIzaSyAyimkuYQYF_FXVALexPuGQctUWRURdCY0"
                        f"&media_filter=gif,mediumgif,tinygif&limit=1"
                    )
                    async with session.get(api, timeout=aiohttp.ClientTimeout(total=8)) as r:
                        if r.status == 200:
                            data = await r.json(content_type=None)
                            results = data.get("results", [])
                            if results:
                                media = results[0].get("media_formats", {})
                                for fmt in ("gif", "mediumgif", "tinygif"):
                                    u = media.get(fmt, {}).get("url")
                                    if u:
                                        return u
            except Exception:
                pass

            # 2) Scraping HTML
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    if r.status == 200:
                        html = await r.text()
                        gifs = re.findall(r'https://media\.tenor\.com/[^"\'<>\s]+\.gif', html)
                        if gifs:
                            return gifs[0]
                        og = re.search(r'content=["\']([^"\']+\.gif[^"\']*)["\']', html)
                        if og:
                            return og.group(1)
            except Exception:
                pass

            # 3) oEmbed
            try:
                async with session.get(
                    f"https://tenor.com/oembed?url={url}&format=json",
                    timeout=aiohttp.ClientTimeout(total=8)
                ) as r:
                    if r.status == 200:
                        data = await r.json(content_type=None)
                        for key in ("url", "thumbnail_url"):
                            val = data.get(key, "")
                            if val:
                                return val
            except Exception:
                pass

            return None

        # ── GIPHY ──
        elif "giphy.com" in url and ".gif" not in url:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    if r.status == 200:
                        html = await r.text()
                        match = re.search(r'https://media\d?\.giphy\.com/media/[^"\'<>\s]+\.gif', html)
                        if match:
                            return match.group(0)
            except Exception:
                pass
            return url

        # ── URL DIRECTE ──
        else:
            return url


# ================================================================
#  DOWNLOADER
# ================================================================

async def download_file(url: str) -> tuple[io.BytesIO | None, str]:
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=25)) as r:
                if r.status != 200:
                    return None, ""

                ct = r.headers.get("Content-Type", "")
                data = await r.read()

                if len(data) < 100:
                    return None, ""

                if "gif" in ct or ".gif" in url:
                    ext = "gif"
                elif "png" in ct or ".png" in url:
                    ext = "png"
                elif "jpeg" in ct or "jpg" in ct or ".jpg" in url or ".jpeg" in url:
                    ext = "jpg"
                elif "webp" in ct or ".webp" in url:
                    ext = "webp"
                else:
                    ext = "gif"

                buf = io.BytesIO(data)
                buf.seek(0)
                return buf, f"media.{ext}"

        except Exception:
            return None, ""


# ================================================================
#  CLOSE BUTTON
# ================================================================

class CloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Fermer le ticket", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(embed=emb("❌ Pas la permission."), ephemeral=True)
        await interaction.response.send_message(embed=emb("🔒 Fermeture dans 3 secondes..."), ephemeral=True)
        await asyncio.sleep(3)
        await interaction.channel.delete()


# ================================================================
#  TICKET BUTTON
# ================================================================

class TicketView(discord.ui.View):
    def __init__(self, category_id: int):
        super().__init__(timeout=None)
        self.category_id = category_id

    @discord.ui.button(label="🎫 Ouvrir un ticket", style=discord.ButtonStyle.secondary)
    async def open(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in user_ticket:
            return await interaction.response.send_message(embed=emb("❌ Tu as déjà un ticket ouvert."), ephemeral=True)

        category = interaction.guild.get_channel(self.category_id)
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True),
        }

        channel = await interaction.guild.create_text_channel(
            name=f"ticket-{interaction.user.name}".lower(),
            category=category,
            overwrites=overwrites
        )

        user_ticket[interaction.user.id] = channel.id

        embed = discord.Embed(
            title="🎫 Ticket ouvert",
            description=(
                f"Bienvenue {interaction.user.mention} !\n"
                "Le support va vous répondre rapidement.\n\n"
                "Cliquez sur 🔒 pour fermer le ticket."
            ),
            color=discord.Color.light_gray()
        )
        embed.set_footer(text=f"Ticket de {interaction.user.name}")
        await channel.send(embed=embed, view=CloseView())
        await interaction.response.send_message(embed=emb(f"✅ Ticket créé : {channel.mention}"), ephemeral=True)


# ================================================================
#  SETUP / UNSETUP
# ================================================================

@bot.command()
async def setupticket(ctx):
    if not is_owner(ctx):
        return await ctx.message.delete()

    def check(m):
        return m.author.id == OWNER_ID and m.channel == ctx.channel

    await ctx.message.delete()

    q1 = await ctx.send(embed=emb("📁 Mentionne la **catégorie** des tickets :"))
    msg1 = await bot.wait_for("message", check=check)
    category_id = int(msg1.content.replace("<#", "").replace(">", ""))
    await msg1.delete()
    await q1.delete()

    q2 = await ctx.send(embed=emb("💬 Mentionne le **salon** pour le bouton :"))
    msg2 = await bot.wait_for("message", check=check)
    channel_id = int(msg2.content.replace("<#", "").replace(">", ""))
    await msg2.delete()
    await q2.delete()

    channel = bot.get_channel(channel_id)
    embed = discord.Embed(
        title="🎫 Support",
        description="Clique sur le bouton ci-dessous pour ouvrir un ticket.",
        color=discord.Color.light_gray()
    )
    await channel.send(embed=embed, view=TicketView(category_id))

    confirm = await ctx.send(embed=emb("✅ Setup terminé !"))
    await asyncio.sleep(3)
    await confirm.delete()


@bot.command()
async def unsetupticket(ctx):
    if not is_owner(ctx):
        return await ctx.message.delete()

    user_ticket.clear()
    await ctx.message.delete()
    msg = await ctx.send(embed=emb("🗑️ Ticket system reset."))
    await asyncio.sleep(3)
    await msg.delete()


# ================================================================
#  +SEND  —  RESPECTE LES SAUTS DE LIGNE + IGNORE GOFILE ETC
# ================================================================

@bot.command()
async def send(ctx, *, args=None):
    if not is_owner(ctx):
        return await ctx.message.delete()

    await ctx.message.delete()

    if not args:
        return

    # ── Trouver toutes les URLs dans le message ──
    all_urls = re.findall(r'https?://\S+', args)

    # ── Trouver la première URL media (pas gofile etc) ──
    media_url = None
    for url in all_urls:
        if is_media_url(url):
            media_url = url
            break

    # ── Extraire le texte en retirant UNIQUEMENT l'URL media ──
    # Les autres URLs (gofile etc) restent dans le texte
    if media_url:
        text = args.replace(media_url, "").strip()
    else:
        text = args.strip()

    # ── Remplacer \n littéral par de vrais sauts de ligne ──
    text = text.replace("\\n", "\n")

    # ── Pas de media : embed texte simple ──
    if not media_url:
        embed = discord.Embed(color=discord.Color.light_gray())
        if text:
            embed.description = text
        return await ctx.channel.send(embed=embed)

    # ── Avec media : télécharger et envoyer ──
    loading = await ctx.channel.send(embed=emb("⏳ Chargement..."))

    real_url = await get_media_url(media_url)

    if not real_url:
        await loading.delete()
        # Media pas trouvé, envoie le texte + lien brut
        embed = discord.Embed(color=discord.Color.light_gray())
        full = f"{text}\n{media_url}" if text else media_url
        embed.description = full
        return await ctx.channel.send(embed=embed)

    buf, filename = await download_file(real_url)

    await loading.delete()

    if buf and filename:
        embed = discord.Embed(color=discord.Color.light_gray())
        if text:
            embed.description = text
        embed.set_image(url=f"attachment://{filename}")

        file = discord.File(buf, filename=filename)
        await ctx.channel.send(embed=embed, file=file)

    else:
        embed = discord.Embed(color=discord.Color.light_gray())
        if text:
            embed.description = text
        embed.set_image(url=real_url)
        await ctx.channel.send(embed=embed)


# ================================================================
#  HELP
# ================================================================

@bot.command()
async def help(ctx):
    if not is_owner(ctx):
        return await ctx.message.delete()

    await ctx.message.delete()

    embed = discord.Embed(
        title="📌 Commandes",
        color=discord.Color.light_gray(),
        description=(
            "**`+send [texte] [url]`**\n"
            "> Envoie un embed avec texte + image/GIF animé\n"
            "> Supporte : Tenor · Giphy · Imgur · URLs directes\n"
            "> Ignore : Gofile · Mediafire · Mega · etc\n"
            "> Utilise `\\n` pour les sauts de ligne\n\n"
            "**`+setupticket`** — Configure les tickets\n"
            "**`+unsetupticket`** — Reset les tickets\n"
            "**`+help`** — Cette aide"
        )
    )

    await ctx.send(embed=embed)


# ================================================================
#  AUTO DELETE
# ================================================================

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.startswith("+") and message.author.id != OWNER_ID:
        await message.delete()
        return

    await bot.process_commands(message)


# ================================================================
#  RUN
# ================================================================

bot.run(TOKEN)