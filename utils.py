import discord
from discord.ext import commands
from functools import wraps


# ── Intents Presets ──────────────────────────────────────────────────────────

def get_intents(preset: str = "default") -> discord.Intents:
    """
    Returns a configured Intents object based on preset.

    Presets:
        "default"    → messages + guilds + members (recommended for most bots)
        "minimal"    → guilds only (read-only, no member/message events)
        "moderation" → default + bans + dm messages
        "full"       → everything enabled (requires verification for large bots)

    Usage:
        from utils import get_intents
        bot = commands.Bot(command_prefix="!", intents=get_intents("default"))
    """
    if preset == "minimal":
        intents = discord.Intents.default()
        return intents

    if preset == "default":
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        return intents

    if preset == "moderation":
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.bans = True
        intents.dm_messages = True
        return intents

    if preset == "full":
        return discord.Intents.all()

    raise ValueError(f"Unknown preset: '{preset}'. Choose: minimal, default, moderation, full")


# ── Custom Exceptions ────────────────────────────────────────────────────────

class NotServerOwner(commands.CheckFailure):
    pass

class NotStaff(commands.CheckFailure):
    pass


# ── Reusable Check Functions (use with @commands.check()) ────────────────────

def is_owner():
    """Server owner only."""
    async def predicate(ctx: commands.Context):
        if ctx.author != ctx.guild.owner:
            raise NotServerOwner("Only the server owner can use this.")
        return True
    return commands.check(predicate)

def is_staff():
    """Has at least one of: admin, manage guild, or manage roles."""
    async def predicate(ctx: commands.Context):
        perms = ctx.author.guild_permissions
        if not any([perms.administrator, perms.manage_guild, perms.manage_roles]):
            raise NotStaff("You must be a staff member to use this.")
        return True
    return commands.check(predicate)

def has_role_named(*role_names: str):
    """Has at least one role matching the given name(s)."""
    async def predicate(ctx: commands.Context):
        member_roles = [r.name.lower() for r in ctx.author.roles]
        if not any(r.lower() in member_roles for r in role_names):
            raise commands.CheckFailure(f"You need one of these roles: {', '.join(role_names)}")
        return True
    return commands.check(predicate)


# ── Direct Boolean Helpers (use inside command logic) ────────────────────────

def is_admin(member: discord.Member) -> bool:
    return member.guild_permissions.administrator

def can_kick(member: discord.Member) -> bool:
    return member.guild_permissions.kick_members

def can_ban(member: discord.Member) -> bool:
    return member.guild_permissions.ban_members

def can_manage_messages(member: discord.Member) -> bool:
    return member.guild_permissions.manage_messages

def can_manage_roles(member: discord.Member) -> bool:
    return member.guild_permissions.manage_roles

def can_manage_channels(member: discord.Member) -> bool:
    return member.guild_permissions.manage_channels

def can_mute(member: discord.Member) -> bool:
    return member.guild_permissions.moderate_members

def is_bot_owner(member: discord.Member, bot: commands.Bot) -> bool:
    return member.id == bot.owner_id


# ── Role Hierarchy Guard (use before kick/ban/role changes) ──────────────────

def can_action_member(actor: discord.Member, target: discord.Member) -> bool:
    """Returns True if actor's top role is above target's top role."""
    return actor.top_role > target.top_role


# ── Error Handler Helper (paste in your on_command_error event) ──────────────

async def handle_perm_error(ctx: commands.Context, error):
    if isinstance(error, NotServerOwner):
        await ctx.reply("❌ Only the server owner can use this.")
    elif isinstance(error, NotStaff):
        await ctx.reply("❌ You must be a staff member to use this.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.reply(f"❌ You are missing permissions: `{'`, `'.join(error.missing_permissions)}`")
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.reply(f"❌ I am missing permissions: `{'`, `'.join(error.missing_permissions)}`")
    elif isinstance(error, commands.CheckFailure):
        await ctx.reply(f"❌ {str(error)}")
