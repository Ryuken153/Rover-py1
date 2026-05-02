import discord
from discord.ext import commands
import asyncio
import time
from datetime import datetime, timezone
from db import add_reminder, get_user_reminders, get_all_reminders, delete_reminder

def parse_time(time_str: str) -> int:
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    try:
        unit = time_str[-1].lower()
        amount = int(time_str[:-1])
        if unit not in units:
            return None
        return amount * units[unit]
    except:
        return None

def format_remaining(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    elif seconds < 86400:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    else:
        return f"{seconds // 86400}d {(seconds % 86400) // 3600}h"

async def reminder_task(bot, reminder_id, user_id, channel_id, reminder, delay):
    await asyncio.sleep(delay)
    try:
        user = await bot.fetch_user(user_id)
        if user:
            embed = discord.Embed(
                title="⏰ Reminder!",
                description=f">>> {reminder}",
                color=discord.Color.gold(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_footer(text="Rover Reminders")
            await user.send(embed=embed)
    except Exception:
        try:
            channel = bot.get_channel(channel_id)
            if channel:
                embed = discord.Embed(
                    title="⏰ Reminder!",
                    description=f">>> {reminder}",
                    color=discord.Color.gold(),
                    timestamp=datetime.now(timezone.utc)
                )
                embed.set_footer(text="Rover Reminders • Could not DM you")
                await channel.send(f"<@{user_id}>", embed=embed)
        except Exception:
            pass
    await delete_reminder(reminder_id)

class DeleteView(discord.ui.View):
    def __init__(self, docs, author_id):
        super().__init__(timeout=60)
        self.author_id = author_id
        options = [
            discord.SelectOption(
                label=f"{i}. {doc['reminder'][:50]}",
                description=f"In {format_remaining(doc['remind_at'] - time.time())}",
                value=str(doc["_id"])
            )
            for i, doc in enumerate(docs, 1)
        ]
        select = discord.ui.Select(placeholder="Choose a reminder to delete...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ This menu is not for you.", ephemeral=True)
            return False
        return True

    async def select_callback(self, interaction: discord.Interaction):
        from bson import ObjectId
        reminder_id = ObjectId(interaction.data["values"][0])
        await delete_reminder(reminder_id)
        await interaction.response.edit_message(
            content="✅ Reminder deleted successfully.",
            embed=None,
            view=None
        )

class Remind(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["rm"])
    async def remind(self, ctx, time_str: str, *, reminder: str):
        """Set a reminder. Usage: !remind 10m Buy groceries"""
        seconds = parse_time(time_str)
        if not seconds:
            return await ctx.reply("❌ Invalid time format. Use `10s`, `5m`, `2h`, `1d`")

        remind_at = time.time() + seconds
        reminder_id = await add_reminder(ctx.author.id, ctx.channel.id, reminder, remind_at)

        asyncio.create_task(reminder_task(
            self.bot, reminder_id, ctx.author.id, ctx.channel.id, reminder, seconds
        ))

        fire_time = datetime.fromtimestamp(remind_at, tz=timezone.utc)
        embed = discord.Embed(
            title="✅ Reminder Set!",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="📝 Reminder", value=f">>> {reminder}", inline=False)
        embed.add_field(name="⏱ In", value=f"`{format_remaining(seconds)}`", inline=True)
        embed.add_field(name="🕐 Fires At", value=f"<t:{int(remind_at)}:F>", inline=True)
        embed.add_field(name="📬 Delivery", value="DM (fallback to channel)", inline=True)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    @commands.command(aliases=["rms", "myreminders"])
    async def reminders(self, ctx):
        """List all your active reminders."""
        docs = await get_user_reminders(ctx.author.id)
        if not docs:
            embed = discord.Embed(
                title="⏰ Your Reminders",
                description="You have no active reminders.\nUse `!remind <time> <message>` to set one!",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)

        embed = discord.Embed(
            title=f"⏰ Your Reminders ({len(docs)})",
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc)
        )
        for i, doc in enumerate(docs, 1):
            remaining = doc["remind_at"] - time.time()
            embed.add_field(
                name=f"{i}. {doc['reminder'][:50]}",
                value=f"⏱ In `{format_remaining(remaining)}` • <t:{int(doc['remind_at'])}:R>",
                inline=False
            )
        embed.set_footer(text=f"{ctx.author.display_name} • Use !delremind to delete", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    @commands.command(aliases=["delrm", "rmdelete"])
    async def delremind(self, ctx):
        """Delete one of your active reminders."""
        docs = await get_user_reminders(ctx.author.id)
        if not docs:
            return await ctx.reply("❌ You have no active reminders to delete.")

        embed = discord.Embed(
            title="🗑️ Delete a Reminder",
            description="Select a reminder from the dropdown below to delete it.",
            color=discord.Color.orange()
        )
        for i, doc in enumerate(docs, 1):
            remaining = doc["remind_at"] - time.time()
            embed.add_field(
                name=f"{i}. {doc['reminder'][:50]}",
                value=f"⏱ In `{format_remaining(remaining)}`",
                inline=False
            )
        embed.set_footer(text="Only you can use this menu • Expires in 60s")

        view = DeleteView(docs, ctx.author.id)
        await ctx.reply(embed=embed, view=view)

async def setup(bot):
    cog = Remind(bot)
    await bot.add_cog(cog)

    docs = await get_all_reminders()
    for doc in docs:
        delay = doc["remind_at"] - time.time()
        asyncio.create_task(reminder_task(
            bot, doc["_id"], doc["user_id"], doc["channel_id"], doc["reminder"],
            max(delay, 0)
        ))
