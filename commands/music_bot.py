"""
Discord Music Bot — music_bot.py
Dependencies:
    pip install discord.py yt-dlp PyNaCl
FFmpeg must be installed and in PATH.
"""

import asyncio
import re
from collections import deque

import discord
import yt_dlp
from discord.ext import commands

# ──────────────────────────────────────────
#  Config
# ──────────────────────────────────────────
TOKEN = "YOUR_BOT_TOKEN"
PREFIX = "!"

YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": False,
    "quiet": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "postprocessors": [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "opus",
        }
    ],
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

# ──────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────
def is_url(text: str) -> bool:
    return re.match(r"https?://", text) is not None


async def fetch_search_results(query: str, limit: int = 5) -> list[dict]:
    """Return up to `limit` search results for the given query."""
    loop = asyncio.get_event_loop()

    def _extract():
        opts = {**YTDL_OPTIONS, "default_search": f"ytsearch{limit}", "noplaylist": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(query, download=False)
            return info.get("entries", [])

    entries = await loop.run_in_executor(None, _extract)
    results = []
    for e in entries:
        if e:
            results.append({
                "title":       e.get("title", "Unknown"),
                "uploader":    e.get("uploader") or e.get("channel", "Unknown Artist"),
                "url":         e["url"],
                "duration":    e.get("duration", 0),
                "thumbnail":   e.get("thumbnail"),
                "webpage_url": e.get("webpage_url", ""),
                "requester":   None,
            })
    return results


async def fetch_track(query: str) -> dict | None:
    """Return a dict with {title, url, duration, thumbnail, webpage_url}."""
    search = query if is_url(query) else f"ytsearch:{query}"
    loop = asyncio.get_event_loop()

    def _extract():
        with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
            info = ydl.extract_info(search, download=False)
            # If playlist / search result, grab first entry
            if "entries" in info:
                info = info["entries"][0]
            return info

    info = await loop.run_in_executor(None, _extract)
    if info is None:
        return None

    return {
        "title": info.get("title", "Unknown"),
        "url": info["url"],
        "duration": info.get("duration", 0),
        "thumbnail": info.get("thumbnail"),
        "webpage_url": info.get("webpage_url", query),
        "requester": None,  # filled in by the command
    }


def fmt_duration(seconds: int) -> str:
    if not seconds:
        return "?"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ──────────────────────────────────────────
#  Per-guild state
# ──────────────────────────────────────────
class GuildPlayer:
    def __init__(self):
        self.queue: deque[dict] = deque()
        self.current: dict | None = None
        self.volume: float = 0.5
        self.loop: bool = False   # loop current track
        self.voice: discord.VoiceClient | None = None


# ──────────────────────────────────────────
#  Bot setup
# ──────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)
players: dict[int, GuildPlayer] = {}          # guild_id → GuildPlayer
pending_searches: dict[int, list[dict]] = {}  # user_id  → search results


def get_player(guild_id: int) -> GuildPlayer:
    if guild_id not in players:
        players[guild_id] = GuildPlayer()
    return players[guild_id]


# ──────────────────────────────────────────
#  Playback engine
# ──────────────────────────────────────────
def play_next(guild_id: int, text_channel: discord.TextChannel):
    """Called when a track ends; plays the next one or cleans up."""
    player = get_player(guild_id)

    if player.loop and player.current:
        # Re-queue the same track
        player.queue.appendleft(player.current)

    if not player.queue:
        player.current = None
        asyncio.run_coroutine_threadsafe(
            text_channel.send("⏹ Queue finished."), bot.loop
        )
        return

    track = player.queue.popleft()
    player.current = track

    source = discord.FFmpegPCMAudio(track["url"], **FFMPEG_OPTIONS)
    source = discord.PCMVolumeTransformer(source, volume=player.volume)

    def after(error):
        if error:
            print(f"[playback error] {error}")
        play_next(guild_id, text_channel)

    player.voice.play(source, after=after)

    async def _announce():
        embed = now_playing_embed(track)
        await text_channel.send(embed=embed)

    asyncio.run_coroutine_threadsafe(_announce(), bot.loop)


def now_playing_embed(track: dict) -> discord.Embed:
    embed = discord.Embed(
        title="🎵 Now Playing",
        description=f"[{track['title']}]({track['webpage_url']})",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Duration", value=fmt_duration(track["duration"]))
    if track.get("requester"):
        embed.add_field(name="Requested by", value=track["requester"].mention)
    if track.get("thumbnail"):
        embed.set_thumbnail(url=track["thumbnail"])
    return embed


# ──────────────────────────────────────────
#  Commands
# ──────────────────────────────────────────

@bot.command(name="join", aliases=["j"])
async def join(ctx: commands.Context):
    """Join the caller's voice channel."""
    if not ctx.author.voice:
        return await ctx.send("❌ You're not in a voice channel.")

    channel = ctx.author.voice.channel
    player = get_player(ctx.guild.id)

    if ctx.voice_client:
        await ctx.voice_client.move_to(channel)
    else:
        player.voice = await channel.connect()

    await ctx.send(f"✅ Joined **{channel.name}**.")


@bot.command(name="play", aliases=["p"])
async def play(ctx: commands.Context, *, query: str):
    """Play a song or add it to the queue. Accepts URL or search term."""
    # Auto-join if needed
    if not ctx.voice_client:
        if not ctx.author.voice:
            return await ctx.send("❌ Join a voice channel first.")
        player = get_player(ctx.guild.id)
        player.voice = await ctx.author.voice.channel.connect()
    else:
        player = get_player(ctx.guild.id)
        player.voice = ctx.voice_client

    async with ctx.typing():
        track = await fetch_track(query)

    if track is None:
        return await ctx.send("❌ Could not find that track.")

    track["requester"] = ctx.author

    if player.voice.is_playing() or player.voice.is_paused():
        player.queue.append(track)
        await ctx.send(
            f"📋 Added to queue: **{track['title']}** `[{fmt_duration(track['duration'])}]` "
            f"(position {len(player.queue)})"
        )
    else:
        player.queue.append(track)
        play_next(ctx.guild.id, ctx.channel)


@bot.command(name="playnext", aliases=["pn"])
async def playnext(ctx: commands.Context, *, query: str):
    """Add a song to the front of the queue."""
    player = get_player(ctx.guild.id)

    if not ctx.voice_client:
        return await ctx.send("❌ Not connected. Use `!play` first.")

    async with ctx.typing():
        track = await fetch_track(query)

    if track is None:
        return await ctx.send("❌ Could not find that track.")

    track["requester"] = ctx.author
    player.queue.appendleft(track)
    await ctx.send(f"⏭ Playing next: **{track['title']}**")


@bot.command(name="skip", aliases=["s"])
async def skip(ctx: commands.Context):
    """Skip the current track."""
    vc = ctx.voice_client
    if not vc or not vc.is_playing():
        return await ctx.send("❌ Nothing is playing.")
    vc.stop()
    await ctx.send("⏭ Skipped.")


@bot.command(name="stop")
async def stop(ctx: commands.Context):
    """Stop playback and clear the queue."""
    player = get_player(ctx.guild.id)
    player.queue.clear()
    player.current = None
    player.loop = False
    if ctx.voice_client:
        ctx.voice_client.stop()
    await ctx.send("⏹ Stopped and queue cleared.")


@bot.command(name="pause")
async def pause(ctx: commands.Context):
    """Pause playback."""
    vc = ctx.voice_client
    if vc and vc.is_playing():
        vc.pause()
        await ctx.send("⏸ Paused.")
    else:
        await ctx.send("❌ Nothing is playing.")


@bot.command(name="resume", aliases=["r"])
async def resume(ctx: commands.Context):
    """Resume paused playback."""
    vc = ctx.voice_client
    if vc and vc.is_paused():
        vc.resume()
        await ctx.send("▶️ Resumed.")
    else:
        await ctx.send("❌ Not paused.")


@bot.command(name="volume", aliases=["vol"])
async def volume(ctx: commands.Context, vol: int):
    """Set volume 0–100."""
    if not 0 <= vol <= 100:
        return await ctx.send("❌ Volume must be between 0 and 100.")
    player = get_player(ctx.guild.id)
    player.volume = vol / 100
    if ctx.voice_client and ctx.voice_client.source:
        ctx.voice_client.source.volume = player.volume
    await ctx.send(f"🔊 Volume set to **{vol}%**.")


@bot.command(name="nowplaying", aliases=["np"])
async def nowplaying(ctx: commands.Context):
    """Show the currently playing track."""
    player = get_player(ctx.guild.id)
    if not player.current:
        return await ctx.send("❌ Nothing is playing.")
    await ctx.send(embed=now_playing_embed(player.current))


@bot.command(name="queue", aliases=["q"])
async def queue(ctx: commands.Context, page: int = 1):
    """Show the current queue (10 tracks per page)."""
    player = get_player(ctx.guild.id)

    if not player.queue and not player.current:
        return await ctx.send("📋 The queue is empty.")

    per_page = 10
    items = list(player.queue)
    total_pages = max(1, (len(items) + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    start = (page - 1) * per_page
    chunk = items[start : start + per_page]

    lines = []
    if player.current and page == 1:
        lines.append(
            f"▶️ **[Now]** [{player.current['title']}]({player.current['webpage_url']}) "
            f"`{fmt_duration(player.current['duration'])}`"
        )

    for i, track in enumerate(chunk, start=start + 1):
        lines.append(
            f"`{i}.` [{track['title']}]({track['webpage_url']}) "
            f"`{fmt_duration(track['duration'])}`"
        )

    embed = discord.Embed(
        title=f"📋 Queue — Page {page}/{total_pages}",
        description="\n".join(lines) or "Empty",
        color=discord.Color.blurple(),
    )
    embed.set_footer(text=f"{len(items)} track(s) in queue")
    await ctx.send(embed=embed)


@bot.command(name="remove")
async def remove(ctx: commands.Context, index: int):
    """Remove a track from the queue by its position number."""
    player = get_player(ctx.guild.id)
    if not 1 <= index <= len(player.queue):
        return await ctx.send(f"❌ Invalid index. Queue has {len(player.queue)} track(s).")
    items = list(player.queue)
    removed = items.pop(index - 1)
    player.queue = deque(items)
    await ctx.send(f"🗑 Removed **{removed['title']}** from the queue.")


@bot.command(name="shuffle")
async def shuffle(ctx: commands.Context):
    """Shuffle the queue."""
    import random
    player = get_player(ctx.guild.id)
    if not player.queue:
        return await ctx.send("❌ Queue is empty.")
    items = list(player.queue)
    random.shuffle(items)
    player.queue = deque(items)
    await ctx.send("🔀 Queue shuffled!")


@bot.command(name="loop", aliases=["repeat"])
async def loop(ctx: commands.Context):
    """Toggle loop for the current track."""
    player = get_player(ctx.guild.id)
    player.loop = not player.loop
    status = "🔂 Loop **ON**" if player.loop else "➡️ Loop **OFF**"
    await ctx.send(status)


@bot.command(name="leave", aliases=["disconnect", "dc"])
async def leave(ctx: commands.Context):
    """Disconnect from the voice channel."""
    player = get_player(ctx.guild.id)
    player.queue.clear()
    player.current = None
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
    await ctx.send("👋 Disconnected.")


# ──────────────────────────────────────────
#  Error handler
# ──────────────────────────────────────────
@bot.command(name="search", aliases=["find", "fs"])
async def search(ctx: commands.Context, *, query: str):
    """Search YouTube and pick a track to play by number."""
    async with ctx.typing():
        results = await fetch_search_results(query, limit=5)

    if not results:
        return await ctx.send("❌ No results found.")

    # Store results keyed by the user's ID
    pending_searches[ctx.author.id] = results

    lines = []
    for i, t in enumerate(results, 1):
        lines.append(
            f"`{i}.` **{t['title']}**\n"
            f"     ↳ {t['uploader']}  •  `{fmt_duration(t['duration'])}`"
        )

    embed = discord.Embed(
        title=f"🔍 Results for: {query}",
        description="\n".join(lines),
        color=discord.Color.blurple(),
    )
    embed.set_footer(text="Reply with a number 1–5 to play  •  'cancel' to dismiss")
    if results[0].get("thumbnail"):
        embed.set_thumbnail(url=results[0]["thumbnail"])

    await ctx.send(embed=embed)


@bot.event
async def on_message(message: discord.Message):
    # Let normal commands run first
    await bot.process_commands(message)

    # Ignore bots and DMs
    if message.author.bot or not message.guild:
        return

    # Check if this user has a pending search
    if message.author.id not in pending_searches:
        return

    text = message.content.strip().lower()

    if text == "cancel":
        pending_searches.pop(message.author.id, None)
        return await message.channel.send("❌ Search cancelled.")

    if not text.isdigit():
        return  # not a number, ignore (let normal chat through)

    choice = int(text)
    results = pending_searches.pop(message.author.id)

    if not 1 <= choice <= len(results):
        return await message.channel.send(f"❌ Pick a number between 1 and {len(results)}.")

    track = results[choice - 1]
    track["requester"] = message.author

    ctx_guild_id = message.guild.id
    player = get_player(ctx_guild_id)

    # Auto-join voice if needed
    vc = message.guild.voice_client
    if not vc:
        if not message.author.voice:
            return await message.channel.send("❌ Join a voice channel first.")
        player.voice = await message.author.voice.channel.connect()
    else:
        player.voice = vc

    if player.voice.is_playing() or player.voice.is_paused():
        player.queue.append(track)
        await message.channel.send(
            f"📋 Added to queue: **{track['title']}** by **{track['uploader']}** "
            f"`[{fmt_duration(track['duration'])}]` (position {len(player.queue)})"
        )
    else:
        player.queue.append(track)
        play_next(ctx_guild_id, message.channel)



    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: `{error.param.name}`")
    elif isinstance(error, commands.CommandNotFound):
        pass  # silently ignore unknown commands
    else:
        await ctx.send(f"⚠️ Error: {error}")
        raise error


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} ({bot.user.id})")
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.listening, name=f"{PREFIX}play"
    ))


# ──────────────────────────────────────────
#  Run
# ──────────────────────────────────────────
if __name__ == "__main__":
    bot.run(TOKEN)
