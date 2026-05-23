import discord
from discord.ext import commands
import os

TOKEN = os.getenv("TOKEN")  # ← Railway variable

OWNER_ID = 766337426846646273

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="+", intents=intents)


def is_owner(ctx):
    return ctx.author.id == OWNER_ID


# ---------------- TICKET VIEW ----------------

class TicketView(discord.ui.View):
    def __init__(self, category_id: int):
        super().__init__(timeout=None)
        self.category_id = category_id

    @discord.ui.button(label="Ouvrir un ticket", style=discord.ButtonStyle.secondary)
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):

        guild = interaction.guild
        category = guild.get_channel(self.category_id)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True),
        }

        channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}".lower(),
            category=category,
            overwrites=overwrites
        )

        await interaction.response.send_message(
            f"Ticket créé : {channel.mention}",
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

    await ctx.send("Mentionne la **catégorie** pour les tickets :")
    msg1 = await bot.wait_for("message", check=check)
    category_id = int(msg1.content.replace("<#", "").replace(">", ""))
    await msg1.delete()

    await ctx.send("Mentionne le **salon** pour le bouton :")
    msg2 = await bot.wait_for("message", check=check)
    channel_id = int(msg2.content.replace("<#", "").replace(">", ""))
    await msg2.delete()

    channel = bot.get_channel(channel_id)

    embed = discord.Embed(
        title="Support",
        description="Pour ouvrir clique sur le bouton en dessous",
        color=discord.Color.white()
    )

    view = TicketView(category_id)

    await channel.send(embed=embed, view=view)


# ---------------- SEND COMMAND ----------------

@bot.command()
async def send(ctx, *, content=None):
    if not is_owner(ctx):
        return await ctx.message.delete()

    await ctx.message.delete()

    if not content and not ctx.message.attachments:
        return

    embed = discord.Embed(
        description=content if content else "",
        color=discord.Color.white()
    )

    if ctx.message.attachments:
        embed.set_image(url=ctx.message.attachments[0].url)

    await ctx.channel.send(embed=embed)


# ---------------- AUTO DELETE COMMANDS ----------------

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.startswith("+"):
        if message.author.id != OWNER_ID:
            return await message.delete()

    await bot.process_commands(message)


bot.run(TOKEN)