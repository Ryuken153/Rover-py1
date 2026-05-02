from discord.ext import commands 

class ping(commands.Cog):
  def __init__(self, bot):
    self.bot = bot

    @commands.command()
    async def ping(self, ctx: commands.Context):
      """Check bot latency."""
      latency = round(self.bot.latency * 1000)
      msg = await ctx.reply("Pinging...")
      roundtrip = round((msg.created_at - ctx.message.created_at).total_seconds() * 1000)
      await msg.edit(content = f"🏓 Pong! Latency: **{roundtrip}ms** | API: **{latency}ms**")

async def setup(bot):
  await bot.add_cog(Ping(bot))
