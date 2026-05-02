import discord 
from discord.ext import commands
import asyncio
import time
from db import add_reminder, get_user_reminders, delete_reminder

def parse_time(time_str: str) -> int:
  units =  {"s": 1, "m": 60, "h": 3600, "d": 86400}
  try:
    unit = time_str[-1].lower()
    amount = int(time_str[:-1])
    if unit not in units:
      return None
    return amount * units[unit]
  except:
    return None

async def reminder_task(bot, reminder_id, user_id, channel_id, reminder, delay):
  await asyncio.sleep(delay)
  try:
    channel = bot.get_channel(channel_id)
    if channel:
            await channel.send(f"<@{user_id}> ⏰ Reminder: **{reminder}**")
  except:
    pass
  await delete_reminder(reminder_id)

class Remind(commands.Cog):
  def __init__(self, bot):
    self.bot = bot

  @commands.command()
  async def remind(self, ctx, time_str: str, *, reminder: str):
    seconds = parse_time(time_str)
        if not seconds:
            return await ctx.reply("❌ Invalid time. Use `10s`, `5m`, `2h`, `1d`")

        remind_at = time.time() + seconds
        reminder_id = await add_reminder(ctx.author.id, ctx.channel.id, reminder, remind_at)

        asyncio.create_task(reminder_task(
            self.bot, reminder_id, ctx.author.id, ctx.channel.id, reminder, seconds
        ))
        await ctx.reply(f"✅ I'll remind you about **{reminder}** in `{time_str}`")

    @commands.command()
    async def reminders(self, ctx):
        docs = await get_user_reminders(ctx.author.id)
        if not docs:
            return await ctx.reply("You have no active reminders.")

        embed = discord.Embed(title="⏰ Your Reminders", color=discord.Color.blurple())
        for i, doc in enumerate(docs, 1):
            remaining = round(doc["remind_at"] - time.time())
            embed.add_field(
                name=f"{i}. {doc['reminder']}",
                value=f"In `{remaining}s`",
                inline=False
            )
        await ctx.reply(embed=embed)

async def setup(bot):
    cog = Remind(bot)
    await bot.add_cog(cog)

    # Reschedule all pending reminders on startup
    docs = await get_all_reminders()
    for doc in docs:
        delay = doc["remind_at"] - time.time()
        if delay > 0:
            asyncio.create_task(reminder_task(
                bot, doc["_id"], doc["user_id"], doc["channel_id"], doc["reminder"], delay
            ))
        else:
            # Already overdue, fire immediately
            asyncio.create_task(reminder_task(
                bot, doc["_id"], doc["user_id"], doc["channel_id"], doc["reminder"], 0
            ))
    


    
  

