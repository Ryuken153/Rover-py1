import sys, traceback
sys.stderr= sys.stdout
import discord
from discord.ext import commands
import random
import os
from dotenv import  load_dotenv
from keep_alive import keep_alive

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!",  intents=intents, help_command=None)

@bot.event
async def on_ready ():
    print(f"logged in as {bot.user}(ID: {bot.user.id})")
    await bot.change_presence(activity=discord.Game(name="!help for commands"))

@bot.event
async def  on_member_join(member: discord.Member):
    if member.guild.system_channel:
        await member.guild.system_channel.send(
            f"Welcome to **{member.guild.name}, {member.mention}! enjoy your stay" 
        )

@bot.command()
async def ping(ctx: commands.Context):
    """Check bot latency."""
    latency = round(bot.latency * 1000)
    msg = await ctx.reply("Pinging...")
    roundtrip = round((msg.created_at - ctx.message.created_at).total_seconds() * 1000)
    await msg.edit(content=f"🏓 Pong! Latency: **{roundtrip}ms** | API: **{latency}ms**")

@bot.command()
async def hello(ctx: commands.Context):
    """Say hello to the bot."""
    await ctx.reply(f"👋 Hello, **{ctx.author.display_name}**! Welcome to the server!")

try:
    keep_alive()
    token = os.getenv("DISCORD_TOKEN"))
    print(f"Token loaded: {'YES' if token else 'NO - TOKEN IS MISSING'}", flush=True)
    bot.run(token)
    
except Exception as e:
    print(f"FATAL: {e}",flush=True)
    trackback.print_exc()
    sys.exit(1)
