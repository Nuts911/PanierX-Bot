import discord
from discord.ext import commands
import os
import asyncio

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
            embed=emb("🔒 Fermeture..."),
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
                embed=emb("❌ Tu as déjà un ticket"),
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
            description="Support actif\nClique sur 🔒 pour fermer",
            color=discord.Color.light_gray()
        )

        await channel.send(embed=embed, view=CloseView())

        await interaction.response.send_message(
            embed=emb(f"Ticket créé : {channel.mention}"),
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

    await ctx.send(embed=emb("💬 Mentionne le salon du bouton"))
    msg2 = await bot.wait_for("message", check=check)
    channel_id = int(msg2.content.replace("<#", "").replace(">", ""))
    await msg2.delete()

    channel = bot.get_channel(channel_id)

    embed = discord.Embed(
        title="🎫 Support",
        description="Clique sur le bouton pour ouvrir un ticket",
        color=discord.Color.light_gray()
    )

    await channel.send(embed=embed, view=TicketView(category_id))

    await ctx.send(embed=emb("✅ Setup terminé"))


# ---------------- UNSETUP ----------------

@bot.command()
async def unsetupticket(ctx):
    if not is_owner(ctx):
        return await ctx.message.delete()

    user_ticket.clear()
    await ctx.message.delete()

    await ctx.send(embed=emb("🗑️ Ticket system reset"))


# ---------------- 🔥 FIXED +SEND (ULTRA STABLE GIF / IMAGE / TEXT) ----------------

@bot.command()
async def send(ctx, *, args=None):
    if not is_owner(ctx):
        return await ctx.message.delete()

    await ctx.message.delete()

    if not args:
        return

    parts = args.split()

    text_parts = []
    media = None

    for p in parts:
        if p.startswith("http"):
            media = p
        else:
            text_parts.append(p)

    text = " ".join(text_parts)

    embed = discord.Embed(color=discord.Color.light_gray())

    if text:
        embed.description = text

    if media:
        embed.set_image(url=media)

    await ctx.channel.send(embed=embed)


# ---------------- HELP ----------------

@bot.command()
async def help(ctx):
    if not is_owner(ctx):
        return await ctx.message.delete()

    await ctx.message.delete()

    embed = discord.Embed(
        title="📌 Commands",
        color=discord.Color.light_gray(),
        description="""
+setupticket → setup system
+unsetupticket → reset system
+send → texte + GIF + image + lien
+help → commandes
"""
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


bot.run(TOKEN)