"""
commands/music.py
Requires: pip install wavelink==3.4.1 PyNaCl
Uses free public Lavalink v4 nodes — no self-hosting needed.
"""

import asyncio
import typing

import discord
import wavelink
from discord.ext import commands


# ──────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────
def fmt_duration(ms: int) -> str:
    """Convert milliseconds to m:ss or h:mm:ss."""
    s = ms // 1000
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def track_embed(track: wavelink.Playable, title: str = "🎵 Now Playing") -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=f"[{track.title}]({track.uri})" if track.uri else track.title,
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Artist",   value=track.author or "Unknown")
    embed.add_field(name="Duration", value=fmt_duration(track.length))
    if hasattr(track, "extras") and getattr(track.extras, "requester", None):
        embed.add_field(name="Requested by", value=track.extras.requester)
    if track.artwork:
        embed.set_thumbnail(url=track.artwork)
    return embed


# ──────────────────────────────────────────
#  Cog
# ──────────────────────────────────────────
class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        """Connect to Lavalink nodes when the cog loads."""
        nodes = [
            # Primary node
            wavelink.Node(
                uri="https://lavalinkv4.serenetia.com",
                password="https://dsc.gg/ajidevserver",
                identifier="PRIMARY",
            ),
            # Backup node
            wavelink.Node(
                uri="https://lavalink.nextgencoders.xyz",
                password="nextgencoderspvt",
                identifier="BACKUP",
            ),
        ]
        await wavelink.Pool.connect(nodes=nodes, client=self.bot, cache_capacity=100)

    # ── wavelink events ───────────────────

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        print(f"[wavelink] Node '{payload.node.identifier}' connected | session: {payload.session_id}")

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        player: wavelink.Player = payload.player
        if not player or not hasattr(player, "text_channel"):
            return
        can_embed = player.text_channel.permissions_for(player.guild.me).embed_links
        if can_embed:
            await player.text_channel.send(embed=track_embed(payload.original or payload.track))
        else:
            t = payload.original or payload.track
            await player.text_channel.send(
                f"🎵 **Now Playing:** {t.title} — {t.author} `[{fmt_duration(t.length)}]`"
            )

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player: wavelink.Player = payload.player
        if not player:
            return
        if not player.queue and not player.playing:
            if hasattr(player, "text_channel"):
                await player.text_channel.send("⏹ Queue finished.")

    @commands.Cog.listener()
    async def on_wavelink_inactive_player(self, player: wavelink.Player):
        """Auto-disconnect after 3 minutes of inactivity."""
        if hasattr(player, "text_channel"):
            await player.text_channel.send("💤 No activity for 3 minutes — disconnecting.")
        await player.disconnect()

    # ── internal ──────────────────────────

    async def _get_player(self, ctx: commands.Context) -> wavelink.Player | None:
        """Return existing player or join the user's VC."""
        player: wavelink.Player = typing.cast(wavelink.Player, ctx.voice_client)

        if player:
            if ctx.author.voice and ctx.author.voice.channel != player.channel:
                await ctx.send("❌ You must be in the same voice channel as the bot.")
                return None
            return player

        if not ctx.author.voice:
            await ctx.send("❌ Join a voice channel first.")
            return None

        try:
            player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
            player.text_channel = ctx.channel
            player.inactive_timeout = 180
            player.autoplay = wavelink.AutoPlayMode.partial
        except Exception as e:
            await ctx.send(f"❌ Could not connect: {e}")
            return None

        return player

    # ── commands ──────────────────────────

    @commands.command(name="join", aliases=["j"])
    async def join(self, ctx: commands.Context):
        """Join your voice channel."""
        if not ctx.author.voice:
            return await ctx.send("❌ You're not in a voice channel.")
        if ctx.voice_client:
            return await ctx.send("✅ Already connected.")
        player: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        player.text_channel = ctx.channel
        player.inactive_timeout = 180
        await ctx.send(f"✅ Joined **{ctx.author.voice.channel.name}**.")

    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx: commands.Context, *, query: str):
        """Play a song or add it to queue. Accepts URL or search term."""
        player = await self._get_player(ctx)
        if not player:
            return

        async with ctx.typing():
            search_query = query if query.startswith("http") else f"ytsearch:{query}"
            results = await wavelink.Playable.search(search_query)

        if not results:
            return await ctx.send("❌ No results found.")

        track: wavelink.Playable = results[0] if isinstance(results, list) else results.tracks[0]
        track.extras = {"requester": ctx.author.mention}

        await player.queue.put_wait(track)

        if not player.playing:
            await player.play(player.queue.get())
        else:
            can_embed = ctx.channel.permissions_for(ctx.me).embed_links
            if can_embed:
                await ctx.send(embed=track_embed(track, f"📋 Added to Queue (position {player.queue.count})"))
            else:
                await ctx.send(
                    f"📋 Added: **{track.title}** — {track.author} "
                    f"`[{fmt_duration(track.length)}]` (position {player.queue.count})"
                )

    @commands.command(name="search", aliases=["find", "fs"])
    async def search(self, ctx: commands.Context, *, query: str):
        """Search YouTube and pick a result to play."""
        async with ctx.typing():
            results = await wavelink.Playable.search(f"ytsearch5:{query}")

        if not results:
            return await ctx.send("❌ No results found.")

        tracks = results[:5] if isinstance(results, list) else results.tracks[:5]

        lines = []
        for i, t in enumerate(tracks, 1):
            lines.append(f"`{i}.` **{t.title}**\n     ↳ {t.author}  •  `{fmt_duration(t.length)}`")

        can_embed = ctx.channel.permissions_for(ctx.me).embed_links
        if can_embed:
            embed = discord.Embed(
                title=f"🔍 Results for: {query}",
                description="\n".join(lines),
                color=discord.Color.blurple(),
            )
            embed.set_footer(text="Reply with a number 1–5  •  'cancel' to dismiss")
            if tracks[0].artwork:
                embed.set_thumbnail(url=tracks[0].artwork)
            await ctx.send(embed=embed)
        else:
            text = f"🔍 **Results for: {query}**\n\n" + "\n".join(lines)
            text += "\n\nReply with a number 1–5  •  `cancel` to dismiss"
            await ctx.send(text)

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
        if not 1 <= choice <= len(tracks):
            return await ctx.send(f"❌ Pick a number between 1 and {len(tracks)}.")

        track = tracks[choice - 1]
        track.extras = {"requester": ctx.author.mention}

        player = await self._get_player(ctx)
        if not player:
            return

        await player.queue.put_wait(track)
        if not player.playing:
            await player.play(player.queue.get())
        else:
            await ctx.send(
                f"📋 Added: **{track.title}** — {track.author} "
                f"`[{fmt_duration(track.length)}]` (position {player.queue.count})"
            )

    @commands.command(name="playnext", aliases=["pn"])
    async def playnext(self, ctx: commands.Context, *, query: str):
        """Add a song to the front of the queue."""
        player: wavelink.Player = typing.cast(wavelink.Player, ctx.voice_client)
        if not player:
            return await ctx.send("❌ Not connected. Use `play` first.")

        async with ctx.typing():
            results = await wavelink.Playable.search(
                query if query.startswith("http") else f"ytsearch:{query}"
            )

        if not results:
            return await ctx.send("❌ No results found.")

        track = results[0] if isinstance(results, list) else results.tracks[0]
        track.extras = {"requester": ctx.author.mention}
        player.queue.put_at(0, track)
        await ctx.send(f"⏭ Playing next: **{track.title}** — {track.author}")

    @commands.command(name="skip", aliases=["s"])
    async def skip(self, ctx: commands.Context):
        """Skip the current track."""
        player: wavelink.Player = typing.cast(wavelink.Player, ctx.voice_client)
        if not player or not player.playing:
            return await ctx.send("❌ Nothing is playing.")
        await player.skip()
        await ctx.send("⏭ Skipped.")

    @commands.command(name="stop")
    async def stop(self, ctx: commands.Context):
        """Stop playback and clear the queue."""
        player: wavelink.Player = typing.cast(wavelink.Player, ctx.voice_client)
        if not player:
            return await ctx.send("❌ Not connected.")
        player.queue.clear()
        await player.stop()
        await ctx.send("⏹ Stopped and queue cleared.")

    @commands.command(name="pause")
    async def pause(self, ctx: commands.Context):
        """Pause playback."""
        player: wavelink.Player = typing.cast(wavelink.Player, ctx.voice_client)
        if not player or not player.playing:
            return await ctx.send("❌ Nothing is playing.")
        await player.pause(True)
        await ctx.send("⏸ Paused.")

    @commands.command(name="resume", aliases=["r"])
    async def resume(self, ctx: commands.Context):
        """Resume paused playback."""
        player: wavelink.Player = typing.cast(wavelink.Player, ctx.voice_client)
        if not player or not player.paused:
            return await ctx.send("❌ Not paused.")
        await player.pause(False)
        await ctx.send("▶️ Resumed.")

    @commands.command(name="volume", aliases=["vol"])
    async def volume(self, ctx: commands.Context, vol: int):
        """Set volume 0–100."""
        if not 0 <= vol <= 100:
            return await ctx.send("❌ Volume must be between 0 and 100.")
        player: wavelink.Player = typing.cast(wavelink.Player, ctx.voice_client)
        if not player:
            return await ctx.send("❌ Not connected.")
        await player.set_volume(vol)
        await ctx.send(f"🔊 Volume set to **{vol}%**.")

    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying(self, ctx: commands.Context):
        """Show the currently playing track."""
        player: wavelink.Player = typing.cast(wavelink.Player, ctx.voice_client)
        if not player or not player.current:
            return await ctx.send("❌ Nothing is playing.")
        can_embed = ctx.channel.permissions_for(ctx.me).embed_links
        if can_embed:
            await ctx.send(embed=track_embed(player.current))
        else:
            t = player.current
            await ctx.send(f"🎵 **Now Playing:** {t.title} — {t.author} `[{fmt_duration(t.length)}]`")

    @commands.command(name="queue", aliases=["q"])
    async def queue(self, ctx: commands.Context, page: int = 1):
        """Show the queue (10 tracks per page)."""
        player: wavelink.Player = typing.cast(wavelink.Player, ctx.voice_client)
        if not player or (not player.current and player.queue.is_empty):
            return await ctx.send("📋 The queue is empty.")

        per_page = 10
        items = list(player.queue)
        total_pages = max(1, (len(items) + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        chunk = items[(page - 1) * per_page : page * per_page]

        lines = []
        if player.current and page == 1:
            t = player.current
            lines.append(f"▶️ **[Now]** {t.title} — {t.author} `{fmt_duration(t.length)}`")
        for i, t in enumerate(chunk, start=(page - 1) * per_page + 1):
            lines.append(f"`{i}.` {t.title} — {t.author} `{fmt_duration(t.length)}`")

        can_embed = ctx.channel.permissions_for(ctx.me).embed_links
        if can_embed:
            embed = discord.Embed(
                title=f"📋 Queue — Page {page}/{total_pages}",
                description="\n".join(lines) or "Empty",
                color=discord.Color.blurple(),
            )
            embed.set_footer(text=f"{len(items)} track(s) in queue")
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"📋 **Queue — Page {page}/{total_pages}**\n\n" + "\n".join(lines))

    @commands.command(name="remove")
    async def remove(self, ctx: commands.Context, index: int):
        """Remove a track from the queue by position."""
        player: wavelink.Player = typing.cast(wavelink.Player, ctx.voice_client)
        if not player:
            return await ctx.send("❌ Not connected.")
        if not 1 <= index <= player.queue.count:
            return await ctx.send(f"❌ Invalid index. Queue has {player.queue.count} track(s).")
        items = list(player.queue)
        removed = items.pop(index - 1)
        player.queue.clear()
        for t in items:
            await player.queue.put_wait(t)
        await ctx.send(f"🗑 Removed **{removed.title}**.")

    @commands.command(name="shuffle")
    async def shuffle(self, ctx: commands.Context):
        """Shuffle the queue."""
        player: wavelink.Player = typing.cast(wavelink.Player, ctx.voice_client)
        if not player or player.queue.is_empty:
            return await ctx.send("❌ Queue is empty.")
        player.queue.shuffle()
        await ctx.send("🔀 Queue shuffled!")

    @commands.command(name="loop", aliases=["repeat"])
    async def loop(self, ctx: commands.Context):
        """Toggle loop for the current track."""
        player: wavelink.Player = typing.cast(wavelink.Player, ctx.voice_client)
        if not player:
            return await ctx.send("❌ Not connected.")
        if player.queue.mode == wavelink.QueueMode.loop:
            player.queue.mode = wavelink.QueueMode.normal
            await ctx.send("➡️ Loop **OFF**")
        else:
            player.queue.mode = wavelink.QueueMode.loop
            await ctx.send("🔂 Loop **ON** — looping current track")

    @commands.command(name="loopqueue", aliases=["lq"])
    async def loopqueue(self, ctx: commands.Context):
        """Toggle loop for the entire queue."""
        player: wavelink.Player = typing.cast(wavelink.Player, ctx.voice_client)
        if not player:
            return await ctx.send("❌ Not connected.")
        if player.queue.mode == wavelink.QueueMode.loop_all:
            player.queue.mode = wavelink.QueueMode.normal
            await ctx.send("➡️ Queue loop **OFF**")
        else:
            player.queue.mode = wavelink.QueueMode.loop_all
            await ctx.send("🔁 Queue loop **ON**")

    @commands.command(name="leave", aliases=["disconnect", "dc"])
    async def leave(self, ctx: commands.Context):
        """Disconnect from voice."""
        player: wavelink.Player = typing.cast(wavelink.Player, ctx.voice_client)
        if not player:
            return await ctx.send("❌ Not connected.")
        await player.disconnect()
        await ctx.send("👋 Disconnected.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
