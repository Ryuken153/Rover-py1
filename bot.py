import sys, traceback
sys.stderr = sys.stdout
import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv
from keep_alive import keep_alive
from db import get_prefixes

load_dotenv()

print(f"MONGO_URI loaded: {'YES' if os.getenv('MONGO_URI') else 'NO - MISSING'}", flush=True)
print(f"DISCORD_TOKEN loaded: {'YES' if os.getenv('DISCORD_TOKEN') else 'NO - MISSING'}", flush=True)

async def get_prefix(bot, message):
    prefixes = await get_prefixes(message.guild.id)
    return prefixes

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix=get_prefix, intents=intents, help_command=None)

async def load_extensions():
    folders = ["commands", "events"]
    for folder in folders:
        if not os.path.isdir(folder):
            continue
        for filename in os.listdir(folder):
            if filename.endswith(".py") and not filename.startswith("_"):
                ext = f"{folder}.{filename[:-3]}"
                try:
                    await bot.load_extension(ext)
                    print(f"Loaded: {ext}")
                except Exception as e:
                    print(f"Failed to load {ext}: {e}")

async def main():
    async with bot:
        await load_extensions()
        token = os.getenv("DISCORD_TOKEN")
        print(f"Token loaded: {'YES' if token else 'NO - TOKEN IS MISSING'}", flush=True)
        await bot.start(token)

try:
    keep_alive()
    asyncio.run(main())

except Exception as e:
    print(f"FATAL: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)
