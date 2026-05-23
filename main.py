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

ticket_data = {}        # guild_id -> category_id
user_ticket = {}        # user_id -> channel_id


# ---------------- EMBED ----------------

def emb(text, color=discord.Color.light_gray()):
    return discord.Embed(description=text, color=color)


def is_owner(ctx):
    return ctx.author.id == OWNER_ID


# ---------------- CLOSE BUTTON ----------------

class CloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Close", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(
                embed=emb("❌ Tu n'as pas la permission"),
                ephemeral=True
            )

        await interaction.response.send_message(
            embed=emb("🔒 Fermeture du ticket..."),
            ephemeral=True
        )

        await asyncio.sleep(3)
        await interaction.channel.delete()


# ---------------- TICKET BUTTON ----------------

class TicketView(discord.ui.View):
    def __init__(self, category_id: int):
        super().__init__(timeout=None)
        self.category_id = category_id

    @discord.ui.button(label="🎫 Ouvrir un ticket", style=discord.ButtonStyle.secondary)
    async def open(self, interaction: discord.Interaction, button: discord.ui.Button):

        user_id = interaction.user.id

        # ❌ déjà un ticket
        if user_id in user_ticket:
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

        user_ticket[user_id] = channel.id

        embed = discord.Embed(
            title="🎫 Ticket",
            description="Support ouvert\nClique sur 🔒 pour fermer",
            color=discord.Color.light_gray()
        )

        await channel.send(embed=embed, view=CloseView())

        await interaction.response.send_message(
            embed=emb(f"Ticket créé : {channel.mention}"),
            ephemeral=True
        )


# ---------------- SETUP TICKET CLEAN ----------------

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

    await ctx.send(embed=emb("⏳ Setup en cours..."))

    channel = bot.get_channel(channel_id)

    embed = discord.Embed(
        title="Support",
        description="Clique sur le bouton pour ouvrir un ticket",
        color=discord.Color.light_gray()
    )

    msg = await channel.send(embed=embed, view=TicketView(category_id))

    # ❌ supprime messages inutiles
    await ctx.channel.purge(limit=10)

    await ctx.send(embed=emb("✅ Setup terminé (clean)"))


# ---------------- UNSETUP ----------------

@bot.command()
async def unsetupticket(ctx):
    if not is_owner(ctx):
        return await ctx.message.delete()

    await ctx.message.delete()

    ticket_data.pop(ctx.guild.id, None)
    user_ticket.clear()

    await ctx.send(embed=emb("🗑️ Ticket system supprimé"))


# ---------------- SEND FIX (IMAGE OK) ----------------

@bot.command()
async def send(ctx, *, content=None):
    if not is_owner(ctx):
        return await ctx.message.delete()

    await ctx.message.delete()

    embed = discord.Embed(color=discord.Color.light_gray())

    if content:
        embed.description = content

    if ctx.message.attachments:
        embed.set_image(url=ctx.message.attachments[0].url)

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
+send → embed + image
+help → commands
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