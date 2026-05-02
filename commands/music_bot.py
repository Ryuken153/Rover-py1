"""
commands/music.py
Drop this in your commands/ folder — it loads automatically.
"""

import asyncio
import re
from collections import deque

import discord
import yt_dlp
from discord.ext import commands

# ──────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────
YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": False,
    "quiet": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
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


def fmt_duration(seconds: int) -> str:
    if not seconds:
        return "?"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


async def fetch_track(query: str) -> dict | None:
    search = query if is_url(query) else f"ytsearch:{query}"
    loop = asyncio.get_event_loop()

    def _extract():
        with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
            info = ydl.extract_info(search, download=False)
            if "entries" in info:
                info = info["entries"][0]
            return info

    info = await loop.run_in_executor(None, _extract)
    if not info:
        return None

    return {
        "title":       info.get("title", "Unknown"),
        "uploader":    info.get("uploader") or info.get("channel", "Unknown Artist"),
        "url":         info["url"],
        "duration":    info.get("duration", 0),
        "thumbnail":   info.get("thumbnail"),
        "webpage_url": info.get("webpage_url", query),
        "requester":   None,
    }


async def fetch_search_results(query: str, limit: int = 5) -> list[dict]:
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


# ──────────────────────────────────────────
#  Per-guild state
# ──────────────────────────────────────────
class GuildPlayer:
    def __init__(self):
        self.queue:   deque[dict]          = deque()
        self.current: dict | None          = None
        self.volume:  float                = 0.5
        self.loop:    bool                 = False
        self.voice:   discord.VoiceClient | None = None


# ──────────────────────────────────────────
#  Cog
# ──────────────────────────────────────────
class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._players: dict[int, GuildPlayer] = {}

    # ── internal ──────────────────────────

    def get_player(self, guild_id: int) -> GuildPlayer:
        if guild_id not in self._players:
            self._players[guild_id] = GuildPlayer()
        return self._players[guild_id]

    def _play_next(self, guild_id: int, channel: discord.TextChannel):
        player = self.get_player(guild_id)

        if player.loop and player.current:
            player.queue.appendleft(player.current)

        if not player.queue:
            player.current = None
            asyncio.run_coroutine_threadsafe(
                channel.send("⏹ Queue finished."), self.bot.loop
            )
            return

        track = player.queue.popleft()
        player.current = track

        source = discord.FFmpegPCMAudio(track["url"], **FFMPEG_OPTIONS)
        source = discord.PCMVolumeTransformer(source, volume=player.volume)

        def after(error):
            if error:
                print(f"[music error] {error}")
            self._play_next(guild_id, channel)

        player.voice.play(source, after=after)

        asyncio.run_coroutine_threadsafe(
            channel.send(embed=self._now_playing_embed(track)), self.bot.loop
        )

    def _now_playing_embed(self, track: dict) -> discord.Embed:
        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"[{track['title']}]({track['webpage_url']})",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Artist",   value=track.get("uploader", "?"))
        embed.add_field(name="Duration", value=fmt_duration(track["duration"]))
        if track.get("requester"):
            embed.add_field(name="Requested by", value=track["requester"].mention)
        if track.get("thumbnail"):
            embed.set_thumbnail(url=track["thumbnail"])
        return embed

    async def _ensure_voice(self, ctx: commands.Context) -> GuildPlayer | None:
        """Join voice if needed; return the GuildPlayer or None on failure."""
        player = self.get_player(ctx.guild.id)
        if ctx.voice_client:
            player.voice = ctx.voice_client
            return player
        if not ctx.author.voice:
            await ctx.send("❌ Join a voice channel first.")
            return None
        player.voice = await ctx.author.voice.channel.connect()
        return player

    # ── commands ──────────────────────────

    @commands.command(name="join", aliases=["j"])
    async def join(self, ctx: commands.Context):
        """Join your voice channel."""
        if not ctx.author.voice:
            return await ctx.send("❌ You're not in a voice channel.")
        channel = ctx.author.voice.channel
        player  = self.get_player(ctx.guild.id)
        if ctx.voice_client:
            await ctx.voice_client.move_to(channel)
        else:
            player.voice = await channel.connect()
        await ctx.send(f"✅ Joined **{channel.name}**.")

    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx: commands.Context, *, query: str):
        """Play a song or add it to the queue (URL or search term)."""
        player = await self._ensure_voice(ctx)
        if not player:
            return

        async with ctx.typing():
            track = await fetch_track(query)

        if not track:
            return await ctx.send("❌ Could not find that track.")

        track["requester"] = ctx.author
        player.queue.append(track)

        if player.voice.is_playing() or player.voice.is_paused():
            await ctx.send(
                f"📋 Added to queue: **{track['title']}** by **{track['uploader']}** "
                f"`[{fmt_duration(track['duration'])}]` (position {len(player.queue)})"
            )
        else:
            self._play_next(ctx.guild.id, ctx.channel)

    @commands.command(name="search", aliases=["find", "fs"])
    async def search(self, ctx: commands.Context, *, query: str):
        """Search YouTube and pick a result to play."""
        async with ctx.typing():
            results = await fetch_search_results(query, limit=5)

        if not results:
            return await ctx.send("❌ No results found.")

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
        embed.set_footer(text="Reply with a number 1–5  •  'cancel' to dismiss")
        if results[0].get("thumbnail"):
            embed.set_thumbnail(url=results[0]["thumbnail"])

        await ctx.send(embed=embed)

        # Wait for the user's pick (60s timeout)
        def check(m: discord.Message):
            return (
                m.author == ctx.author
                and m.channel == ctx.channel
                and (m.content.strip().isdigit() or m.content.strip().lower() == "cancel")
            )

        try:
            reply = await self.bot.wait_for("message", check=check, timeout=60)
        except asyncio.TimeoutError:
            return await ctx.send("⏱ Search timed out.")

        if reply.content.strip().lower() == "cancel":
            return await ctx.send("❌ Search cancelled.")

        choice = int(reply.content.strip())
        if not 1 <= choice <= len(results):
            return await ctx.send(f"❌ Pick a number between 1 and {len(results)}.")

        track = results[choice - 1]
        track["requester"] = ctx.author

        player = await self._ensure_voice(ctx)
        if not player:
            return

        player.queue.append(track)
        if player.voice.is_playing() or player.voice.is_paused():
            await ctx.send(
                f"📋 Added to queue: **{track['title']}** by **{track['uploader']}** "
                f"`[{fmt_duration(track['duration'])}]` (position {len(player.queue)})"
            )
        else:
            self._play_next(ctx.guild.id, ctx.channel)

    @commands.command(name="playnext", aliases=["pn"])
    async def playnext(self, ctx: commands.Context, *, query: str):
        """Add a song to the front of the queue."""
        player = self.get_player(ctx.guild.id)
        if not ctx.voice_client:
            return await ctx.send("❌ Not connected. Use `play` first.")

        async with ctx.typing():
            track = await fetch_track(query)

        if not track:
            return await ctx.send("❌ Could not find that track.")

        track["requester"] = ctx.author
        player.queue.appendleft(track)
        await ctx.send(f"⏭ Playing next: **{track['title']}** by **{track['uploader']}**")

    @commands.command(name="skip", aliases=["s"])
    async def skip(self, ctx: commands.Context):
        """Skip the current track."""
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send("❌ Nothing is playing.")
        ctx.voice_client.stop()
        await ctx.send("⏭ Skipped.")

    @commands.command(name="stop")
    async def stop(self, ctx: commands.Context):
        """Stop playback and clear the queue."""
        player = self.get_player(ctx.guild.id)
        player.queue.clear()
        player.current = None
        player.loop = False
        if ctx.voice_client:
            ctx.voice_client.stop()
        await ctx.send("⏹ Stopped and queue cleared.")

    @commands.command(name="pause")
    async def pause(self, ctx: commands.Context):
        """Pause playback."""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("⏸ Paused.")
        else:
            await ctx.send("❌ Nothing is playing.")

    @commands.command(name="resume", aliases=["r"])
    async def resume(self, ctx: commands.Context):
        """Resume paused playback."""
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("▶️ Resumed.")
        else:
            await ctx.send("❌ Not paused.")

    @commands.command(name="volume", aliases=["vol"])
    async def volume(self, ctx: commands.Context, vol: int):
        """Set volume 0–100."""
        if not 0 <= vol <= 100:
            return await ctx.send("❌ Volume must be between 0 and 100.")
        player = self.get_player(ctx.guild.id)
        player.volume = vol / 100
        if ctx.voice_client and ctx.voice_client.source:
            ctx.voice_client.source.volume = player.volume
        await ctx.send(f"🔊 Volume set to **{vol}%**.")

    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying(self, ctx: commands.Context):
        """Show the currently playing track."""
        player = self.get_player(ctx.guild.id)
        if not player.current:
            return await ctx.send("❌ Nothing is playing.")
        await ctx.send(embed=self._now_playing_embed(player.current))

    @commands.command(name="queue", aliases=["q"])
    async def queue(self, ctx: commands.Context, page: int = 1):
        """Show the queue (10 tracks per page)."""
        player = self.get_player(ctx.guild.id)
        if not player.queue and not player.current:
            return await ctx.send("📋 The queue is empty.")

        per_page = 10
        items = list(player.queue)
        total_pages = max(1, (len(items) + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        chunk = items[(page - 1) * per_page : page * per_page]

        lines = []
        if player.current and page == 1:
            lines.append(
                f"▶️ **[Now]** [{player.current['title']}]({player.current['webpage_url']}) "
                f"— {player.current.get('uploader','?')} `{fmt_duration(player.current['duration'])}`"
            )
        for i, t in enumerate(chunk, start=(page - 1) * per_page + 1):
            lines.append(
                f"`{i}.` [{t['title']}]({t['webpage_url']}) "
                f"— {t.get('uploader','?')} `{fmt_duration(t['duration'])}`"
            )

        embed = discord.Embed(
            title=f"📋 Queue — Page {page}/{total_pages}",
            description="\n".join(lines) or "Empty",
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"{len(items)} track(s) in queue")
        await ctx.send(embed=embed)

    @commands.command(name="remove")
    async def remove(self, ctx: commands.Context, index: int):
        """Remove a track from the queue by position."""
        player = self.get_player(ctx.guild.id)
        if not 1 <= index <= len(player.queue):
            return await ctx.send(f"❌ Invalid index. Queue has {len(player.queue)} track(s).")
        items = list(player.queue)
        removed = items.pop(index - 1)
        player.queue = deque(items)
        await ctx.send(f"🗑 Removed **{removed['title']}**.")

    @commands.command(name="shuffle")
    async def shuffle(self, ctx: commands.Context):
        """Shuffle the queue."""
        import random
        player = self.get_player(ctx.guild.id)
        if not player.queue:
            return await ctx.send("❌ Queue is empty.")
        items = list(player.queue)
        random.shuffle(items)
        player.queue = deque(items)
        await ctx.send("🔀 Queue shuffled!")

    @commands.command(name="loop", aliases=["repeat"])
    async def loop(self, ctx: commands.Context):
        """Toggle loop for the current track."""
        player = self.get_player(ctx.guild.id)
        player.loop = not player.loop
        await ctx.send("🔂 Loop **ON**" if player.loop else "➡️ Loop **OFF**")

    @commands.command(name="leave", aliases=["disconnect", "dc"])
    async def leave(self, ctx: commands.Context):
        """Disconnect from voice."""
        player = self.get_player(ctx.guild.id)
        player.queue.clear()
        player.current = None
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
        await ctx.send("👋 Disconnected.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
