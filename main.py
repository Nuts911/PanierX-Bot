import discord
from discord.ext import commands
import os
import asyncio
import aiohttp
import re
import io

TOKEN = os.getenv("TOKEN")
OWNER_ID = 766337426846646273

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(
    command_prefix="+",
    intents=intents,
    help_command=None
)

user_ticket = {}


# ---------------- EMBED ----------------

def emb(text, color=discord.Color.light_gray()):
    return discord.Embed(description=text, color=color)


def is_owner(ctx):
    return ctx.author.id == OWNER_ID


# ---------------- CLOSE BUTTON ----------------

class CloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Close ticket", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(
                embed=emb("❌ Pas permission"),
                ephemeral=True
            )

        await interaction.response.send_message(
            embed=emb("🔒 Fermeture dans 3 secondes..."),
            ephemeral=True
        )

        await asyncio.sleep(3)
        await interaction.channel.delete()


# ---------------- TICKET SYSTEM ----------------

class TicketView(discord.ui.View):
    def __init__(self, category_id: int):
        super().__init__(timeout=None)
        self.category_id = category_id

    @discord.ui.button(label="🎫 Ouvrir un ticket", style=discord.ButtonStyle.secondary)
    async def open(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in user_ticket:
            return await interaction.response.send_message(
                embed=emb("❌ Tu as déjà un ticket ouvert"),
                ephemeral=True
            )

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
            description="Support actif\nClique sur 🔒 pour fermer le ticket",
            color=discord.Color.light_gray()
        )

        await channel.send(embed=embed, view=CloseView())

        await interaction.response.send_message(
            embed=emb(f"✅ Ticket créé : {channel.mention}"),
            ephemeral=True
        )


# ---------------- SETUP TICKET ----------------

@bot.command()
async def setupticket(ctx):
    if not is_owner(ctx):
        return await ctx.message.delete()

    def check(m):
        return m.author.id == OWNER_ID and m.channel == ctx.channel

    await ctx.message.delete()

    await ctx.send(embed=emb("📁 Mentionne la catégorie des tickets"))
    msg1 = await bot.wait_for("message", check=check)
    category_id = int(msg1.content.replace("<#", "").replace(">", ""))
    await msg1.delete()

    await ctx.send(embed=emb("💬 Mentionne le salon pour le bouton"))
    msg2 = await bot.wait_for("message", check=check)
    channel_id = int(msg2.content.replace("<#", "").replace(">", ""))
    await msg2.delete()

    channel = bot.get_channel(channel_id)

    embed = discord.Embed(
        title="🎫 Support",
        description="Clique sur le bouton ci-dessous pour ouvrir un ticket",
        color=discord.Color.light_gray()
    )

    await channel.send(embed=embed, view=TicketView(category_id))
    await ctx.send(embed=emb("✅ Setup ticket terminé"), delete_after=3)


# ---------------- UNSETUP TICKET ----------------

@bot.command()
async def unsetupticket(ctx):
    if not is_owner(ctx):
        return await ctx.message.delete()

    user_ticket.clear()
    await ctx.message.delete()
    await ctx.send(embed=emb("🗑️ Ticket system reset"), delete_after=3)


# ---------------- CORE : DOWNLOAD + SEND FILE ----------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8",
}


async def resolve_tenor(url: str, session: aiohttp.ClientSession) -> str | None:
    """Extrait la vraie URL .gif depuis une page Tenor"""

    # ── Méthode 1 : oEmbed JSON ──
    try:
        oembed = f"https://tenor.com/oembed?url={url}&format=json"
        async with session.get(oembed, timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status == 200:
                data = await r.json(content_type=None)
                for key in ("url", "thumbnail_url"):
                    val = data.get(key, "")
                    if val.endswith(".gif"):
                        return val
    except Exception:
        pass

    # ── Méthode 2 : Scraping HTML ──
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                html = await r.text()

                # Cherche toutes les URLs .gif
                gifs = re.findall(r'https://media\.tenor\.com/[^"\'<>\s]+\.gif', html)
                if gifs:
                    return gifs[0]

                # Cherche og:image
                og = re.search(
                    r'content=["\']([^"\']+\.gif[^"\']*)["\']',
                    html
                )
                if og:
                    return og.group(1)
    except Exception:
        pass

    # ── Méthode 3 : API Tenor non officielle ──
    try:
        # Extraire l'ID du GIF depuis l'URL
        match = re.search(r"-(\d+)$", url.rstrip("/"))
        if match:
            gif_id = match.group(1)
            api_url = f"https://tenor.com/oembed?url=https://tenor.com/view/{gif_id}&format=json"
            async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status == 200:
                    data = await r.json(content_type=None)
                    val = data.get("url", "")
                    if val:
                        return val
    except Exception:
        pass

    return None


async def download_media(url: str) -> tuple[io.BytesIO | None, str]:
    """
    Télécharge n'importe quelle image/gif et retourne (BytesIO, filename)
    Supporte : Tenor, Giphy, URLs directes .gif/.png/.jpg/.webp
    """

    async with aiohttp.ClientSession(headers=HEADERS) as session:

        real_url = url

        # ── Résolution Tenor ──
        if "tenor.com" in url:
            resolved = await resolve_tenor(url, session)
            if resolved:
                real_url = resolved
            else:
                return None, ""

        # ── Résolution Giphy ──
        elif "giphy.com" in url and not url.endswith(".gif"):
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    html = await r.text()
                    match = re.search(r'https://media\d?\.giphy\.com/media/[^"\'<>\s]+\.gif', html)
                    if match:
                        real_url = match.group(0)
            except Exception:
                pass

        # ── Téléchargement du fichier ──
        try:
            async with session.get(real_url, timeout=aiohttp.ClientTimeout(total=20)) as r:
                if r.status != 200:
                    return None, ""

                content_type = r.headers.get("Content-Type", "")
                data = await r.read()

                # Déterminer l'extension
                if "gif" in content_type or real_url.endswith(".gif"):
                    ext = "gif"
                elif "png" in content_type or real_url.endswith(".png"):
                    ext = "png"
                elif "jpeg" in content_type or "jpg" in content_type:
                    ext = "jpg"
                elif "webp" in content_type:
                    ext = "webp"
                else:
                    ext = "gif"  # fallback

                return io.BytesIO(data), f"media.{ext}"

        except Exception:
            return None, ""


# ---------------- +SEND ----------------

@bot.command()
async def send(ctx, *, args=None):
    if not is_owner(ctx):
        return await ctx.message.delete()

    await ctx.message.delete()

    if not args:
        return

    parts = args.split()
    text_parts = []
    media_url = None

    for p in parts:
        if p.startswith("http://") or p.startswith("https://"):
            if media_url is None:
                media_url = p
        else:
            text_parts.append(p)

    text = " ".join(text_parts).strip() or None

    # ── Pas de media ──
    if not media_url:
        embed = discord.Embed(
            description=text,
            color=discord.Color.light_gray()
        )
        return await ctx.channel.send(embed=embed)

    # ── Téléchargement du media ──
    loading_msg = await ctx.channel.send(embed=emb("⏳ Chargement..."))

    file_bytes, filename = await download_media(media_url)

    await loading_msg.delete()

    # ── Envoi ──
    if file_bytes and filename:
        # Upload direct du fichier = GIF animé garanti
        file = discord.File(file_bytes, filename=filename)

        if text:
            # Embed avec texte + image uploadée
            embed = discord.Embed(
                description=text,
                color=discord.Color.light_gray()
            )
            embed.set_image(url=f"attachment://{filename}")
            await ctx.channel.send(embed=embed, file=file)
        else:
            # Juste le fichier (animé)
            await ctx.channel.send(file=file)

    else:
        # Fallback : on envoie juste le lien brut
        content = f"{text}\n{media_url}" if text else media_url
        await ctx.channel.send(content)


# ---------------- HELP ----------------

@bot.command()
async def help(ctx):
    if not is_owner(ctx):
        return await ctx.message.delete()

    await ctx.message.delete()

    embed = discord.Embed(
        title="📌 Commandes",
        color=discord.Color.light_gray(),
        description=(
            "`+setupticket` → Setup le système de tickets\n"
            "`+unsetupticket` → Reset le système\n"
            "`+send [texte] [url]` → Envoie texte + gif animé + image\n"
            "`+help` → Affiche cette aide"
        )
    )

    await ctx.send(embed=embed)


# ---------------- AUTO DELETE ----------------

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.startswith("+") and message.author.id != OWNER_ID:
        await message.delete()
        return

    await bot.process_commands(message)


# ---------------- RUN ----------------

bot.run(TOKEN)