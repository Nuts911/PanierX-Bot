import discord
from discord.ext import commands
import os

TOKEN = os.getenv("TOKEN")
OWNER_ID = 766337426846646273

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="+", intents=intents)

ticket_data = {}  # guild_id -> category_id


def only_owner(ctx):
    return ctx.author.id == OWNER_ID


def embed_msg(text):
    return discord.Embed(description=text, color=discord.Color.white())


# ---------------- TICKET BUTTON ----------------

class TicketView(discord.ui.View):
    def __init__(self, category_id: int):
        super().__init__(timeout=None)
        self.category_id = category_id

    @discord.ui.button(label="Ouvrir un ticket", style=discord.ButtonStyle.secondary)
    async def ticket(self, interaction: discord.Interaction, button: discord.ui.Button):

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
            embed=embed_msg(f"🎫 Ticket créé : {channel.mention}"),
            ephemeral=True
        )


# ---------------- SETUP TICKET ----------------

@bot.command()
async def setupticket(ctx):
    if not only_owner(ctx):
        return await ctx.message.delete()

    await ctx.message.delete()

    def check(m):
        return m.author.id == OWNER_ID and m.channel == ctx.channel

    await ctx.send(embed=embed_msg("📁 Mentionne la catégorie des tickets :"))
    msg1 = await bot.wait_for("message", check=check)
    category_id = int(msg1.content.replace("<#", "").replace(">", ""))
    await msg1.delete()

    await ctx.send(embed=embed_msg("💬 Mentionne le salon du bouton :"))
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

    await ctx.send(embed=embed_msg("✅ Setup ticket terminé"))


# ---------------- UNSETUP ----------------

@bot.command()
async def unsetupticket(ctx):
    if not only_owner(ctx):
        return await ctx.message.delete()

    await ctx.message.delete()

    ticket_data.pop(ctx.guild.id, None)

    await ctx.send(embed=embed_msg("🗑️ Ticket désactivé pour ce serveur"))


# ---------------- SEND COMMAND FIX ----------------

@bot.command()
async def send(ctx):
    if not only_owner(ctx):
        return await ctx.message.delete()

    await ctx.message.delete()

    content = ctx.message.content[len("+send"):].strip()

    embed = discord.Embed(color=discord.Color.white())

    if content:
        embed.description = content

    if ctx.message.attachments:
        embed.set_image(url=ctx.message.attachments[0].url)

    await ctx.channel.send(embed=embed)


# ---------------- HELP ----------------

@bot.command()
async def help(ctx):
    if not only_owner(ctx):
        return await ctx.message.delete()

    await ctx.message.delete()

    embed = discord.Embed(
        title="Commandes bot",
        color=discord.Color.white(),
        description="""
`+setupticket` → setup ticket
`+unsetupticket` → supprime ticket system
`+send` → envoie message + image
`+help` → commandes
"""
    )

    await ctx.send(embed=embed)


# ---------------- AUTO DELETE COMMANDS ----------------

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