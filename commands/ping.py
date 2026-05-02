import discord
from discord.ext import commands
import time
from db import guilds_col

class Ping(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx: commands.Context):
        """Check bot latency."""
        api_latency = round(self.bot.latency * 1000)

        # Send initial embed
        embed = discord.Embed(title="🏓 Pinging...", color=discord.Color.yellow())
        start = time.monotonic()
        msg = await ctx.reply(embed=embed)
        roundtrip = round((time.monotonic() - start) * 1000)

        # Measure DB ping
        try:
            db_start = time.monotonic()
            await guilds_col.find_one({})
            db_ping = round((time.monotonic() - db_start) * 1000)
            db_status = "🟢 Connected"
        except Exception:
            db_ping = None
            db_status = "🔴 Disconnected"

        # Color based on roundtrip latency
        if roundtrip < 100:
            color = discord.Color.green()
            status = "🟢 Excellent"
        elif roundtrip < 200:
            color = discord.Color.orange()
            status = "🟡 Good"
        else:
            color = discord.Color.red()
            status = "🔴 Poor"

        embed = discord.Embed(title="🏓 Pong!", color=color)
        embed.add_field(name="Roundtrip", value=f"```{roundtrip}ms```", inline=True)
        embed.add_field(name="API Latency", value=f"```{api_latency}ms```", inline=True)
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="DB Latency", value=f"```{db_ping}ms```" if db_ping is not None else "```N/A```", inline=True)
        embed.add_field(name="DB Status", value=db_status, inline=True)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)

        await msg.edit(embed=embed)

async def setup(bot):
    await bot.add_cog(Ping(bot))
