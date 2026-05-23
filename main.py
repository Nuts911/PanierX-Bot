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

# ================================================================
#  UTILS
# ================================================================

def emb(text: str, color=discord.Color.light_gray()) -> discord.Embed:
    return discord.Embed(description=text, color=color)

def is_owner(ctx) -> bool:
    return ctx.author.id == OWNER_ID

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

# ================================================================
#  TENOR RESOLVER  (3 méthodes en cascade)
# ================================================================

async def resolve_tenor(url: str, session: aiohttp.ClientSession) -> str | None:

    # ── 1) oEmbed officiel ──
    try:
        async with session.get(
            f"https://tenor.com/oembed?url={url}&format=json",
            timeout=aiohttp.ClientTimeout(total=8)
        ) as r:
            if r.status == 200:
                data = await r.json(content_type=None)
                for key in ("url", "thumbnail_url"):
                    val = data.get(key, "")
                    if val and (".gif" in val or "media" in val):
                        return val
    except Exception:
        pass

    # ── 2) Scraping HTML de la page Tenor ──
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                html = await r.text()

                # Cherche media.tenor.com .gif
                gifs = re.findall(
                    r'https://media\.tenor\.com/[^"\'<>\s]+\.gif(?:[\?][^"\'<>\s]*)?',
                    html
                )
                if gifs:
                    return gifs[0]

                # Cherche og:image
                og = re.search(
                    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
                    html
                )
                if og:
                    return og.group(1)

                # Cherche og:video
                ov = re.search(
                    r'<meta[^>]+property=["\']og:video["\'][^>]+content=["\']([^"\']+)["\']',
                    html
                )
                if ov:
                    return ov.group(1)
    except Exception:
        pass

    # ── 3) API Tenor v2 (clé publique connue) ──
    try:
        match = re.search(r"-(\d+)(?:/)?$", url)
        if match:
            gif_id = match.group(1)
            api = (
                f"https://tenor.googleapis.com/v2/posts"
                f"?ids={gif_id}&key=AIzaSyAyimkuYQYF_FXVALexPuGQctUWRURdCY0"
                f"&media_filter=gif,mediumgif,tinygif"
                f"&limit=1"
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

    return None


# ================================================================
#  GIPHY RESOLVER
# ================================================================

async def resolve_giphy(url: str, session: aiohttp.ClientSession) -> str | None:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                html = await r.text()
                match = re.search(
                    r'https://media\d?\.giphy\.com/media/[^"\'<>\s]+\.gif',
                    html
                )
                if match:
                    return match.group(0)
    except Exception:
        pass
    return None


# ================================================================
#  DOWNLOADER UNIVERSEL
# ================================================================

async def download_media(url: str) -> tuple[io.BytesIO | None, str, str | None]:
    """
    Retourne (BytesIO, filename, original_resolved_url)
    original_resolved_url = URL directe résolue (pour fallback)
    """
    async with aiohttp.ClientSession(headers=HEADERS) as session:

        real_url = url

        if "tenor.com" in url:
            resolved = await resolve_tenor(url, session)
            if not resolved:
                return None, "", None
            real_url = resolved

        elif "giphy.com" in url and ".gif" not in url:
            resolved = await resolve_giphy(url, session)
            if resolved:
                real_url = resolved

        # Téléchargement binaire
        try:
            async with session.get(
                real_url,
                timeout=aiohttp.ClientTimeout(total=25)
            ) as r:
                if r.status != 200:
                    return None, "", real_url

                ct = r.headers.get("Content-Type", "")
                raw = await r.read()

                if "gif" in ct or ".gif" in real_url:
                    ext = "gif"
                elif "png" in ct or ".png" in real_url:
                    ext = "png"
                elif "jpeg" in ct or "jpg" in ct or ".jpg" in real_url or ".jpeg" in real_url:
                    ext = "jpg"
                elif "webp" in ct or ".webp" in real_url:
                    ext = "webp"
                else:
                    ext = "gif"

                return io.BytesIO(raw), f"media.{ext}", real_url

        except Exception:
            return None, "", real_url


# ================================================================
#  CLOSE BUTTON
# ================================================================

class CloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Fermer le ticket", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(
                embed=emb("❌ Tu n'as pas la permission."),
                ephemeral=True
            )
        await interaction.response.send_message(
            embed=emb("🔒 Fermeture dans 3 secondes..."),
            ephemeral=True
        )
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
            return await interaction.response.send_message(
                embed=emb("❌ Tu as déjà un ticket ouvert."),
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
            description=(
                f"Bienvenue {interaction.user.mention} !\n"
                "Le support va vous répondre rapidement.\n\n"
                "Cliquez sur 🔒 pour fermer le ticket."
            ),
            color=discord.Color.light_gray()
        )
        embed.set_footer(text=f"Ticket de {interaction.user.name}")

        await channel.send(embed=embed, view=CloseView())
        await interaction.response.send_message(
            embed=emb(f"✅ Ticket créé : {channel.mention}"),
            ephemeral=True
        )


# ================================================================
#  COMMANDS
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

    q2 = await ctx.send(embed=emb("💬 Mentionne le **salon** où envoyer le bouton :"))
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
#  +SEND  —  VERSION PRO FINALE
# ================================================================

@bot.command()
async def send(ctx, *, args=None):
    if not is_owner(ctx):
        return await ctx.message.delete()

    await ctx.message.delete()

    if not args:
        return

    # ── Sépare texte et URL ──
    parts = args.split()
    text_parts = []
    media_url = None

    for p in parts:
        if (p.startswith("http://") or p.startswith("https://")) and media_url is None:
            media_url = p
        else:
            text_parts.append(p)

    text = " ".join(text_parts).strip() or None

    # ── Pas de média : embed texte simple ──
    if not media_url:
        embed = discord.Embed(
            description=text,
            color=discord.Color.light_gray()
        )
        return await ctx.channel.send(embed=embed)

    # ── Avec média ──
    loading = await ctx.channel.send(embed=emb("⏳ Chargement du média..."))

    file_bytes, filename, resolved_url = await download_media(media_url)

    await loading.delete()

    if file_bytes and filename:
        # ────────────────────────────────────────────────
        #  CAS 1 : Téléchargement réussi
        #  → Upload direct sur Discord (GIF animé 100%)
        #  → Embed avec attachment:// pour le style
        # ────────────────────────────────────────────────
        file = discord.File(file_bytes, filename=filename)

        embed = discord.Embed(color=discord.Color.light_gray())

        if text:
            embed.description = text

        embed.set_image(url=f"attachment://{filename}")

        await ctx.channel.send(embed=embed, file=file)

    elif resolved_url:
        # ────────────────────────────────────────────────
        #  CAS 2 : Téléchargement échoué mais URL résolue
        #  → Embed avec URL directe (peut marcher pour images)
        # ────────────────────────────────────────────────
        embed = discord.Embed(color=discord.Color.light_gray())

        if text:
            embed.description = text

        embed.set_image(url=resolved_url)

        await ctx.channel.send(embed=embed)

    else:
        # ────────────────────────────────────────────────
        #  CAS 3 : Échec total → texte brut + lien
        # ────────────────────────────────────────────────
        content = f"{text}\n{media_url}" if text else media_url
        await ctx.channel.send(content=content)


# ================================================================
#  HELP
# ================================================================

@bot.command()
async def help(ctx):
    if not is_owner(ctx):
        return await ctx.message.delete()

    await ctx.message.delete()

    embed = discord.Embed(
        title="📌 Commandes disponibles",
        color=discord.Color.light_gray(),
        description=(
            "`+send [texte] [url]` — Envoie un message avec texte et/ou média\n"
            "> Supporte : Tenor, Giphy, images directes (.gif .png .jpg .webp)\n\n"
            "`+setupticket` — Configure le système de tickets\n"
            "`+unsetupticket` — Remet à zéro le système\n"
            "`+help` — Affiche cette aide"
        )
    )

    await ctx.send(embed=embed)


# ================================================================
#  AUTO DELETE (non-owner)
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