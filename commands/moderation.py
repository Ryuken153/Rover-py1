import discord
from discord.ext import commands
from datetime import timedelta
from utils import can_action_member, can_kick

def mod_embed(title: str, discription: str, color: discord.Color.orange()) -> discord.Embed:
  return discord.Embed(title=title, discription=discription, color=color)

class Moderation(commands.Cog):
  def __init__(self, bot: commands.bot):
    self.bot = bot

  @commands.command()
  @commands.bot_has_permissions(kick_members=True)
  async def kick(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
    if not can_kick(ctx.author):
      return await ctx.send(embed=mod_embed("No permission", "you need a authority called **Kick members**."))
    if member == ctx.author:
      return await ctx.send(embed=mod_embed("Error", "you cannot kick yourself baka ~~~"))
    if not can_action_member(ctx.author, member):
      return await ctx.send(embed=mod_embed("Error", "you cannot kick someone equal or higher authority"))

    await member.kick(reason=reason)
    await ctx.send(embed=mod_embed(
      "Member kicked",
      f"**{member}** has been kicked.\n **Reason:** {reason}",
      discord.Color.orange()
    ))
  
async def setup(bot):
  await bot.add_cog(Moderation(bot))
