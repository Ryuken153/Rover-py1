import discord
from discord.ext import commands
from db import set_prefix, get_prefixes, add_prefix, remove_prefix

class Prefix(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["set"])
    @commands.has_permissions(manage_guild=True)
    async def setprefix(self, ctx: commands.Context, new_prefix: str):
        """Set a single prefix, replacing all existing ones."""
        await set_prefix(ctx.guild.id, new_prefix)
        await ctx.reply(f"Prefix set to `{new_prefix}`")

    @commands.command(aliases=["addp"])
    @commands.has_permissions(manage_guild=True)
    async def addprefix(self, ctx: commands.Context, new_prefix: str):
        """Add a prefix without removing existing ones."""
        prefixes = await add_prefix(ctx.guild.id, new_prefix)
        formatted = " ".join(f"`{p}`" for p in prefixes)
        await ctx.reply(f"Added `{new_prefix}`. Active prefixes: {formatted}")

    @commands.command(aliases=["removep"])
    @commands.has_permissions(manage_guild=True)
    async def removeprefix(self, ctx: commands.Context, prefix: str):
        """Remove a specific prefix."""
        prefixes = await remove_prefix(ctx.guild.id, prefix)
        if prefixes:
            formatted = " ".join(f"`{p}`" for p in prefixes)
            await ctx.reply(f"Removed `{prefix}`. Active prefixes: {formatted}")
        else:
            await ctx.reply(f"Removed `{prefix}`. Reverted to default `!`")

    @commands.command()
    async def prefixes(self, ctx: commands.Context):
        """List all active prefixes."""
        prefixes = await get_prefixes(ctx.guild.id)
        formatted = " ".join(f"`{p}`" for p in prefixes)
        await ctx.reply(f"Active prefixes: {formatted}")

async def setup(bot):
    await bot.add_cog(Prefix(bot))
