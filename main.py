import discord
from discord.ext import commands
import os
import asyncio
import aiohttp
import re

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


# ---------------- FETCH GIF URL (TENOR FIX) ----------------

async def get_real_gif_url(url: str) -> str | None:
    """
    Récupère la vraie URL du GIF depuis Tenor.
    Méthode 1 : oEmbed API
    Méthode 2 : Scraping direct de la page HTML
    Méthode 3 : Retourne l'URL directe si c'est déjà un .gif
    """

    # Déjà une URL directe vers un gif/image
    if re.search(r"\.(gif|png|jpg|jpeg|webp)(\?|$)", url, re.IGNORECASE):
        return url

    # Tenor
    if "tenor.com" in url:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        }

        async with aiohttp.ClientSession(headers=headers) as session:

            # ── Méthode 1 : oEmbed ──
            try:
                oembed_url = f"https://tenor.com/oembed?url={url}&format=json"
                async with session.get(oembed_url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                    if r.status == 200:
                        data = await r.json(content_type=None)
                        gif = data.get("url") or data.get("thumbnail_url")
                        if gif:
                            return gif
            except Exception:
                pass

            # ── Méthode 2 : Scraping HTML ──
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                    if r.status == 200:
                        html = await r.text()

                        # Cherche les URLs .gif dans le HTML
                        matches = re.findall(
                            r'https://[^"\'>\s]+\.gif[^"\'>\s]*',
                            html
                        )
                        if matches:
                            # Préfère les URLs media.tenor.com
                            for m in matches:
                                if "media.tenor.com" in m:
                                    return m
                            return matches[0]

                        # Cherche og:image ou og:video dans les meta tags
                        og = re.search(
                            r'<meta[^>]+property=["\']og:(?:image|video)["\'][^>]+content=["\']([^"\']+)["\']',
                            html
                        )
                        if og:
                            return og.group(1)

            except Exception:
                pass

        return None  # Échec total

    return url  # URL inconnue, on retourne telle quelle


# ---------------- +SEND ULTRA FIX ----------------

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
            if media_url is None:  # On garde seulement la première URL
                media_url = p
        else:
            text_parts.append(p)

    text = " ".join(text_parts).strip()

    # ── Résolution de l'URL media ──
    real_url = None
    if media_url:
        real_url = await get_real_gif_url(media_url)

    # ── Construction de l'embed ──
    embed = discord.Embed(color=discord.Color.light_gray())

    if text:
        embed.description = text

    if real_url:
        embed.set_image(url=real_url)
    elif media_url:
        # URL non résolue → on la met en texte pour ne pas perdre le contenu
        embed.description = (embed.description or "") + f"\n{media_url}"

    await ctx.channel.send(embed=embed)


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
            "`+send [texte] [url]` → Envoie texte + gif + image\n"
            "`+help` → Affiche cette aide"
        )
    )

    await ctx.send(embed=embed)


# ---------------- AUTO DELETE COMMANDS (non-owner) ----------------

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