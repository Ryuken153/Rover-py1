import discord
from discord.etx import commands

class Avatar(commands.Cog):
  def __init__(self, bot):
    self.bot = bot

  @commands.command(aliases=["av"])
  async def Avatar(self, ctx: commands.Context, member: discord.Member = None):
      member = member or ctx.author

      embed = discord.Embed(title = f"{member.display_name}'s Avatar", color = member.color)
      embed.set_image(url=member.display.avatar.url)
      embed.set_footer(text= f"Requested by {ctx.author.display_name}")
   
  await ctx.reply(embed=embed)

async def setup(bot):
  await bot.add_cog(Avatar(bot))
    
