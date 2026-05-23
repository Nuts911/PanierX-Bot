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

bot = commands.Bot(command_prefix="+", intents=intents, help_command=None)

ticket_data = {}  # guild_id -> category_id


def is_owner(ctx):
    return ctx.author.id == OWNER_ID


def emb(text, color=discord.Color.white()):
    return discord.Embed(description=text, color=color)


# ---------------- TICKET BUTTON ----------------

class TicketView(discord.ui.View):
    def __init__(self, category_id: int):
        super().__init__(timeout=None)
        self.category_id = category_id

    @discord.ui.button(label="Ouvrir un ticket", style=discord.ButtonStyle.secondary)
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):

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

        await interaction.response.send_message(
            embed=emb(f"🎫 Ticket créé : {channel.mention}"),
            ephemeral=True
        )


# ---------------- SETUP TICKET ----------------

@bot.command()
async def setupticket(ctx):
    if not is_owner(ctx):
        return await ctx.message.delete()

    await ctx.message.delete()

    def check(m):
        return m.author.id == OWNER_ID and m.channel == ctx.channel

    await ctx.send(embed=emb("📁 Mentionne la catégorie des tickets :"))
    msg1 = await bot.wait_for("message", check=check)
    category_id = int(msg1.content.replace("<#", "").replace(">", ""))
    await msg1.delete()

    await ctx.send(embed=emb("💬 Mentionne le salon du bouton :"))
    msg2 = await bot.wait_for("message", check=check)
    channel_id = int(msg2.content.replace("<#", "").replace(">", ""))
    await msg2.delete()

    ticket_data[ctx.guild.id] = category_id

    channel = bot.get_channel(channel_id)

    embed = discord.Embed(
        title="Support",
        description="Pour ouvrir clique sur le bouton en dessous",
        color=discord.Color.white()
    )

    await channel.send(embed=embed, view=TicketView(category_id))

    await ctx.send(embed=emb("✅ Setup terminé"))


# ---------------- UNSETUP ----------------

@bot.command()
async def unsetupticket(ctx):
    if not is_owner(ctx):
        return await ctx.message.delete()

    await ctx.message.delete()

    ticket_data.pop(ctx.guild.id, None)

    await ctx.send(embed=emb("🗑️ Ticket system supprimé"))


# ---------------- SEND ----------------

@bot.command()
async def send(ctx, *, content=None):
    if not is_owner(ctx):
        return await ctx.message.delete()

    await ctx.message.delete()

    embed = discord.Embed(color=discord.Color.white())

    if content:
        embed.description = content

    if ctx.message.attachments:
        embed.set_image(url=ctx.message.attachments[0].url)

    await ctx.channel.send(embed=embed)


# ---------------- CLOSE TICKET ----------------

@bot.command()
async def close(ctx):
    if not is_owner(ctx):
        return await ctx.message.delete()

    if not ctx.channel.name.startswith("ticket-"):
        return await ctx.send(embed=emb("❌ Pas un ticket"), delete_after=5)

    await ctx.send(embed=emb("🔒 Fermeture du ticket dans 5 secondes...", discord.Color.orange()))

    await asyncio.sleep(5)
    await ctx.channel.delete()


# ---------------- HELP ----------------

@bot.command()
async def help(ctx):
    if not is_owner(ctx):
        return await ctx.message.delete()

    await ctx.message.delete()

    embed = discord.Embed(
        title="Commandes",
        color=discord.Color.white(),
        description="""
`+setupticket` → setup ticket system
`+unsetupticket` → supprime system
`+send` → envoie embed + image
`+close` → ferme un ticket
`+help` → commandes
"""
    )

    await ctx.send(embed=embed)


# ---------------- DELETE COMMANDS ----------------

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.startswith("+"):
        if message.author.id != OWNER_ID:
            await message.delete()
            return

    await bot.process_commands(message)


bot.run(TOKEN)