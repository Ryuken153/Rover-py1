"""
events/error_handler.py
Catches command errors and gives clear, specific feedback.
"""

import discord
from discord.ext import commands


# Human-readable names for Discord permissions
PERM_NAMES = {
    "send_messages":              "Send Messages",
    "read_messages":              "Read Messages",
    "read_message_history":       "Read Message History",
    "embed_links":                "Embed Links",
    "attach_files":               "Attach Files",
    "add_reactions":              "Add Reactions",
    "external_emojis":            "Use External Emojis",
    "manage_messages":            "Manage Messages",
    "manage_channels":            "Manage Channels",
    "manage_guild":               "Manage Server",
    "manage_roles":               "Manage Roles",
    "kick_members":               "Kick Members",
    "ban_members":                "Ban Members",
    "mention_everyone":           "Mention Everyone",
    "connect":                    "Connect (Voice)",
    "speak":                      "Speak (Voice)",
    "mute_members":               "Mute Members",
    "deafen_members":             "Deafen Members",
    "move_members":               "Move Members",
    "administrator":              "Administrator",
}


def perm_list(missing: list[str]) -> str:
    return "\n".join(f"• **{PERM_NAMES.get(p, p.replace('_', ' ').title())}**" for p in missing)


def error_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=discord.Color.red())


class ErrorHandler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        # Unwrap CheckFailure wrappers
        error = getattr(error, "original", error)

        # ── Bot missing permissions ────────────────────────────────────────
        if isinstance(error, commands.BotMissingPermissions):
            perms = perm_list(error.missing_permissions)
            await ctx.send(embed=error_embed(
                "🔒 I'm Missing Permissions",
                f"I need the following permissions to run `{ctx.command}`:\n\n{perms}"
            ))

        # ── User missing permissions ───────────────────────────────────────
        elif isinstance(error, commands.MissingPermissions):
            perms = perm_list(error.missing_permissions)
            await ctx.send(embed=error_embed(
                "🚫 You're Missing Permissions",
                f"You need the following permissions to use `{ctx.command}`:\n\n{perms}"
            ))

        # ── Bot missing role ───────────────────────────────────────────────
        elif isinstance(error, commands.BotMissingRole):
            await ctx.send(embed=error_embed(
                "🔒 I'm Missing a Role",
                f"I need the **{error.missing_role}** role to run `{ctx.command}`."
            ))

        # ── User missing role ──────────────────────────────────────────────
        elif isinstance(error, commands.MissingRole):
            await ctx.send(embed=error_embed(
                "🚫 You're Missing a Role",
                f"You need the **{error.missing_role}** role to use `{ctx.command}`."
            ))

        # ── Not in a guild ─────────────────────────────────────────────────
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.send(embed=error_embed(
                "🚫 Server Only",
                f"`{ctx.command}` can only be used inside a server, not in DMs."
            ))

        # ── Command on cooldown ────────────────────────────────────────────
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(embed=error_embed(
                "⏱ Slow Down",
                f"`{ctx.command}` is on cooldown. Try again in **{error.retry_after:.1f}s**."
            ))

        # ── Missing required argument ──────────────────────────────────────
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(embed=error_embed(
                "❓ Missing Argument",
                f"You're missing `{error.param.name}` for `{ctx.command}`.\n\n"
                f"Usage: `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`"
            ))

        # ── Bad argument type ──────────────────────────────────────────────
        elif isinstance(error, commands.BadArgument):
            await ctx.send(embed=error_embed(
                "❓ Invalid Argument",
                f"{error}\n\n"
                f"Usage: `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`"
            ))

        # ── Command not found ──────────────────────────────────────────────
        elif isinstance(error, commands.CommandNotFound):
            pass  # silently ignore unknown commands

        # ── Not the owner ──────────────────────────────────────────────────
        elif isinstance(error, commands.NotOwner):
            await ctx.send(embed=error_embed(
                "🚫 Owner Only",
                "Only the bot owner can use this command."
            ))

        # ── Unexpected error ───────────────────────────────────────────────
        else:
            print(f"[error] command={ctx.command} | error={error}")
            await ctx.send(embed=error_embed(
                "⚠️ Something Went Wrong",
                f"An unexpected error occurred.\n```{error}```"
            ))


async def setup(bot: commands.Bot):
    await bot.add_cog(ErrorHandler(bot))
