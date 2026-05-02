import discord
from discord.ext import commands
import asyncio
import random

X_EMJ, O_EMJ = "✖️", "⭕"

# ══════════════════════════════════════════════════════════════
#  3×3  —  ALGORITHMS
# ══════════════════════════════════════════════════════════════

LINES_3 = [
    [0, 1, 2], [3, 4, 5], [6, 7, 8],   # rows
    [0, 3, 6], [1, 4, 7], [2, 5, 8],   # cols
    [0, 4, 8], [2, 4, 6]               # diagonals
]

def check_winner_3(board):
    for a, b, c in LINES_3:
        if board[a] == board[b] == board[c] != 0:
            return board[a], [a, b, c]
    return ("draw", []) if 0 not in board else (None, [])

def _mm3(board, turn, mx, a, b):
    """Minimax with alpha-beta pruning for 3×3. mx = maximizing player."""
    w, _ = check_winner_3(board)
    if w == mx:            return 10
    if w not in (None, "draw"): return -10
    if w == "draw":        return 0
    mn = 3 - mx
    if turn == mx:
        v = -11
        for i in range(9):
            if board[i] == 0:
                board[i] = turn
                v = max(v, _mm3(board, mn, mx, a, b))
                board[i] = 0
                a = max(a, v)
                if b <= a: break
    else:
        v = 11
        for i in range(9):
            if board[i] == 0:
                board[i] = turn
                v = min(v, _mm3(board, mx, mx, a, b))
                board[i] = 0
                b = min(b, v)
                if b <= a: break
    return v

def minimax_move_3(board, player):
    """Perfect minimax move for `player` on a 3×3 board."""
    best, mv = -99, None
    for i in range(9):
        if board[i] == 0:
            board[i] = player
            s = _mm3(board, 3 - player, player, -99, 99)
            board[i] = 0
            if s > best:
                best, mv = s, i
    return mv

def strategic_move_3(board, player):
    """Smart-but-not-perfect bot: Win → Block → Center → Corners → Edges."""
    opp = 3 - player
    emp = [i for i in range(9) if board[i] == 0]
    # Immediate win
    for i in emp:
        board[i] = player
        w, _ = check_winner_3(board)
        board[i] = 0
        if w == player: return i
    # Block opponent win
    for i in emp:
        board[i] = opp
        w, _ = check_winner_3(board)
        board[i] = 0
        if w == opp: return i
    # Priority positional play
    for p in [4, 0, 2, 6, 8, 1, 3, 5, 7]:
        if p in emp: return p
    return None

# ══════════════════════════════════════════════════════════════
#  4×4  —  ALGORITHMS
# ══════════════════════════════════════════════════════════════

LINES_4 = (
    [[r * 4 + c for c in range(4)] for r in range(4)] +   # rows
    [[r * 4 + c for r in range(4)] for c in range(4)] +   # cols
    [[0, 5, 10, 15], [3, 6, 9, 12]]                        # diagonals
)

def check_winner_4(board):
    for line in LINES_4:
        a, b, c, d = line
        if board[a] == board[b] == board[c] == board[d] != 0:
            return board[a], line
    return ("draw", []) if 0 not in board else (None, [])

def _eval4(board, mx):
    """Heuristic: score lines by count of maximizer / minimizer pieces."""
    mn, score = 3 - mx, 0
    weights = [0, 1, 10, 100, 10000]
    for line in LINES_4:
        vals = [board[i] for i in line]
        mc, oc = vals.count(mx), vals.count(mn)
        if oc == 0: score += weights[mc]
        if mc == 0: score -= weights[oc]
    return score

def _mm4(board, turn, mx, depth, a, b):
    """Depth-limited minimax with alpha-beta for 4×4."""
    w, _ = check_winner_4(board)
    if w == mx:                  return 10000
    if w not in (None, "draw"):  return -10000
    if w == "draw" or depth == 0: return _eval4(board, mx)
    mn = 3 - mx
    if turn == mx:
        v = -99999
        for i in range(16):
            if board[i] == 0:
                board[i] = turn
                v = max(v, _mm4(board, mn, mx, depth - 1, a, b))
                board[i] = 0
                a = max(a, v)
                if b <= a: break
    else:
        v = 99999
        for i in range(16):
            if board[i] == 0:
                board[i] = turn
                v = min(v, _mm4(board, mx, mx, depth - 1, a, b))
                board[i] = 0
                b = min(b, v)
                if b <= a: break
    return v

def minimax_move_4(board, player, depth=4):
    """Best depth-limited minimax move for `player` on a 4×4 board."""
    best, mv = -99999, None
    for i in range(16):
        if board[i] == 0:
            board[i] = player
            s = _mm4(board, 3 - player, player, depth - 1, -99999, 99999)
            board[i] = 0
            if s > best:
                best, mv = s, i
    return mv

def strategic_move_4(board, player):
    """4×4 strategic bot: Win → Block → Inner cells → Corners → Edges."""
    opp = 3 - player
    emp = [i for i in range(16) if board[i] == 0]
    for i in emp:
        board[i] = player
        w, _ = check_winner_4(board)
        board[i] = 0
        if w == player: return i
    for i in emp:
        board[i] = opp
        w, _ = check_winner_4(board)
        board[i] = 0
        if w == opp: return i
    # Inner 4 → corners → edges
    for p in [5, 6, 9, 10, 0, 3, 12, 15, 1, 2, 4, 7, 8, 11, 13, 14]:
        if p in emp: return p
    return None

# ══════════════════════════════════════════════════════════════
#  3×3  —  INTERACTIVE (Human vs Human / Human vs Bot)
# ══════════════════════════════════════════════════════════════

class TTTButton(discord.ui.Button):
    def __init__(self, idx):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=idx // 3)
        self.idx = idx

    async def callback(self, interaction: discord.Interaction):
        view: TTTView = self.view
        if interaction.user.id != view.current.id:
            return await interaction.response.send_message("❌ Not your turn!", ephemeral=True)
        if view.board[self.idx] != 0:
            return await interaction.response.send_message("❌ Cell already taken!", ephemeral=True)
        await view.apply_move(interaction, self.idx, is_p1=(view.current == view.p1))

class TTTView(discord.ui.View):
    def __init__(self, p1, p2, vs_bot=False):
        super().__init__(timeout=120)
        self.p1, self.p2 = p1, p2
        self.vs_bot = vs_bot
        self.current = p1
        self.board = [0] * 9
        for i in range(9):
            self.add_item(TTTButton(i))

    def _btn(self, i): return self.children[i]

    def _footer(self):
        p2n = "Bot [Minimax AI]" if self.vs_bot else self.p2.display_name
        return f"{self.p1.display_name} {X_EMJ}  vs  {O_EMJ} {p2n}"

    async def apply_move(self, interaction, idx, is_p1):
        pid = 1 if is_p1 else 2
        self.board[idx] = pid
        self._btn(idx).style = discord.ButtonStyle.blurple if is_p1 else discord.ButtonStyle.red
        self._btn(idx).label = X_EMJ if is_p1 else O_EMJ
        self._btn(idx).disabled = True

        w, wl = check_winner_3(self.board)
        if w:
            return await self._finish(interaction, w, wl)

        if self.vs_bot:
            move = minimax_move_3(self.board, 2)
            if move is not None:
                self.board[move] = 2
                self._btn(move).style = discord.ButtonStyle.red
                self._btn(move).label = O_EMJ
                self._btn(move).disabled = True
                w, wl = check_winner_3(self.board)
                if w:
                    return await self._finish(interaction, w, wl)
            await self._update(interaction)
        else:
            self.current = self.p2 if self.current == self.p1 else self.p1
            await self._update(interaction)

    async def _update(self, interaction):
        sym = X_EMJ if self.current == self.p1 else O_EMJ
        embed = discord.Embed(
            title="🎮 Tic Tac Toe",
            description=f"{self.current.mention}'s turn {sym}",
            color=discord.Color.blurple()
        )
        embed.set_footer(text=self._footer())
        await interaction.response.edit_message(embed=embed, view=self)

    async def _finish(self, interaction, winner, wl):
        for i in wl:
            self._btn(i).style = discord.ButtonStyle.green
        for btn in self.children:
            btn.disabled = True

        if winner == "draw":
            title, color = "🤝 It's a Draw!", discord.Color.yellow()
            desc = "A perfectly played game — no winner!"
        elif winner == 1:
            title, color = f"🏆 {self.p1.display_name} Wins!", discord.Color.green()
            desc = f"{self.p1.mention} {X_EMJ} wins!"
            if self.vs_bot: desc += " You beat the Minimax AI! 🧠 Impressive!"
        else:
            if self.vs_bot:
                title, color = "🤖 Bot Wins!", discord.Color.red()
                desc = "The Minimax AI is unbeatable. Better luck next time!"
            else:
                title, color = f"🏆 {self.p2.display_name} Wins!", discord.Color.green()
                desc = f"{self.p2.mention} {O_EMJ} wins!"

        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_footer(text=self._footer())
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    async def on_timeout(self):
        for btn in self.children:
            btn.disabled = True

# ══════════════════════════════════════════════════════════════
#  3×3  —  BOT vs BOT  (auto-play spectator view)
# ══════════════════════════════════════════════════════════════

class BotVsBotView3(discord.ui.View):
    """All buttons disabled — purely visual. auto_play() drives the game."""
    def __init__(self):
        super().__init__(timeout=60)
        self.board = [0] * 9
        for i in range(9):
            btn = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="\u200b",
                row=i // 3,
                disabled=True
            )
            self.add_item(btn)

    def _render(self):
        for i, btn in enumerate(self.children):
            if self.board[i] == 1:
                btn.style, btn.label = discord.ButtonStyle.blurple, X_EMJ
            elif self.board[i] == 2:
                btn.style, btn.label = discord.ButtonStyle.red, O_EMJ

    async def auto_play(self, message):
        BOT_NAMES  = {1: "🤖 Minimax AI", 2: "🧠 Strategic Bot"}
        BOT_EMOJI  = {1: X_EMJ, 2: O_EMJ}
        BOT_ALGO   = {
            1: lambda b: minimax_move_3(b, 1),    # perfect play
            2: lambda b: strategic_move_3(b, 2),  # smart heuristic
        }
        FOOTER = f"{X_EMJ} Minimax AI  vs  {O_EMJ} Strategic Bot"
        turn = 1

        while True:
            await asyncio.sleep(1.2)
            move = BOT_ALGO[turn](self.board)
            if move is None:
                break

            self.board[move] = turn
            self._render()
            w, wl = check_winner_3(self.board)

            if w:
                for i in wl:
                    self.children[i].style = discord.ButtonStyle.green
                for btn in self.children:
                    btn.disabled = True

                if w == "draw":
                    title, color = "🤝 Draw!", discord.Color.yellow()
                    desc = "Both bots played perfectly — it's a draw!"
                elif w == 1:
                    title, color = "🏆 Minimax AI Wins!", discord.Color.green()
                    desc = f"Minimax AI {X_EMJ} defeated the Strategic Bot!"
                else:
                    title, color = "🏆 Strategic Bot Wins!", discord.Color.orange()
                    desc = f"Strategic Bot {O_EMJ} upset the Minimax AI!"

                embed = discord.Embed(title=title, description=desc, color=color)
                embed.set_footer(text=FOOTER)
                await message.edit(embed=embed, view=self)
                self.stop()
                return

            # Update for next turn
            nxt = 3 - turn
            embed = discord.Embed(
                title="🤖 Bot vs Bot — Tic Tac Toe",
                description=f"{BOT_NAMES[nxt]}'s turn {BOT_EMOJI[nxt]}",
                color=discord.Color.blurple()
            )
            embed.set_footer(text=FOOTER)
            await message.edit(embed=embed, view=self)
            turn = nxt

        self.stop()

# ══════════════════════════════════════════════════════════════
#  4×4  —  INTERACTIVE (Human vs Human / Human vs Bot)
# ══════════════════════════════════════════════════════════════

class TTT4Button(discord.ui.Button):
    def __init__(self, idx):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=idx // 4)
        self.idx = idx

    async def callback(self, interaction: discord.Interaction):
        view: TTT4View = self.view
        if interaction.user.id != view.current.id:
            return await interaction.response.send_message("❌ Not your turn!", ephemeral=True)
        if view.board[self.idx] != 0:
            return await interaction.response.send_message("❌ Cell already taken!", ephemeral=True)
        await view.apply_move(interaction, self.idx, is_p1=(view.current == view.p1))

class TTT4View(discord.ui.View):
    def __init__(self, p1, p2, vs_bot=False):
        super().__init__(timeout=180)
        self.p1, self.p2 = p1, p2
        self.vs_bot = vs_bot
        self.current = p1
        self.board = [0] * 16
        for i in range(16):
            self.add_item(TTT4Button(i))

    def _btn(self, i): return self.children[i]

    def _footer(self):
        p2n = "Bot [Minimax d4]" if self.vs_bot else self.p2.display_name
        return f"{self.p1.display_name} {X_EMJ}  vs  {O_EMJ} {p2n}"

    async def apply_move(self, interaction, idx, is_p1):
        pid = 1 if is_p1 else 2
        self.board[idx] = pid
        self._btn(idx).style = discord.ButtonStyle.blurple if is_p1 else discord.ButtonStyle.red
        self._btn(idx).label = X_EMJ if is_p1 else O_EMJ
        self._btn(idx).disabled = True

        w, wl = check_winner_4(self.board)
        if w:
            return await self._finish(interaction, w, wl)

        if self.vs_bot:
            move = minimax_move_4(self.board, 2, depth=4)
            if move is not None:
                self.board[move] = 2
                self._btn(move).style = discord.ButtonStyle.red
                self._btn(move).label = O_EMJ
                self._btn(move).disabled = True
                w, wl = check_winner_4(self.board)
                if w:
                    return await self._finish(interaction, w, wl)
            await self._update(interaction)
        else:
            self.current = self.p2 if self.current == self.p1 else self.p1
            await self._update(interaction)

    async def _update(self, interaction):
        sym = X_EMJ if self.current == self.p1 else O_EMJ
        embed = discord.Embed(
            title="🎮 4×4 Tic Tac Toe",
            description=f"{self.current.mention}'s turn {sym}\n*Get 4 in a row to win!*",
            color=discord.Color.blurple()
        )
        embed.set_footer(text=self._footer())
        await interaction.response.edit_message(embed=embed, view=self)

    async def _finish(self, interaction, winner, wl):
        for i in wl:
            self._btn(i).style = discord.ButtonStyle.green
        for btn in self.children:
            btn.disabled = True

        if winner == "draw":
            title, color = "🤝 It's a Draw!", discord.Color.yellow()
            desc = "The whole 4×4 board is full — no winner!"
        elif winner == 1:
            title, color = f"🏆 {self.p1.display_name} Wins!", discord.Color.green()
            desc = f"{self.p1.mention} {X_EMJ} gets 4 in a row!"
            if self.vs_bot: desc += " You beat the AI on a 4×4 board! 🧠"
        else:
            if self.vs_bot:
                title, color = "🤖 Bot Wins!", discord.Color.red()
                desc = "Depth-4 Minimax AI wins the 4×4 game!"
            else:
                title, color = f"🏆 {self.p2.display_name} Wins!", discord.Color.green()
                desc = f"{self.p2.mention} {O_EMJ} gets 4 in a row!"

        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_footer(text=self._footer())
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    async def on_timeout(self):
        for btn in self.children:
            btn.disabled = True

# ══════════════════════════════════════════════════════════════
#  4×4  —  BOT vs BOT  (auto-play spectator view)
# ══════════════════════════════════════════════════════════════

class BotVsBotView4(discord.ui.View):
    """4×4 spectator view. auto_play() drives the game."""
    def __init__(self):
        super().__init__(timeout=120)
        self.board = [0] * 16
        for i in range(16):
            btn = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="\u200b",
                row=i // 4,
                disabled=True
            )
            self.add_item(btn)

    def _render(self):
        for i, btn in enumerate(self.children):
            if self.board[i] == 1:
                btn.style, btn.label = discord.ButtonStyle.blurple, X_EMJ
            elif self.board[i] == 2:
                btn.style, btn.label = discord.ButtonStyle.red, O_EMJ

    async def auto_play(self, message):
        BOT_NAMES = {1: "🤖 Minimax d4", 2: "🧠 Strategic Bot"}
        BOT_EMOJI = {1: X_EMJ, 2: O_EMJ}
        BOT_ALGO  = {
            1: lambda b: minimax_move_4(b, 1, depth=4),   # stronger
            2: lambda b: strategic_move_4(b, 2),           # heuristic
        }
        FOOTER = f"{X_EMJ} Minimax d4  vs  {O_EMJ} Strategic Bot"
        turn = 1

        while True:
            await asyncio.sleep(1.5)
            move = BOT_ALGO[turn](self.board)
            if move is None:
                break

            self.board[move] = turn
            self._render()
            w, wl = check_winner_4(self.board)

            if w:
                for i in wl:
                    self.children[i].style = discord.ButtonStyle.green
                for btn in self.children:
                    btn.disabled = True

                if w == "draw":
                    title, color = "🤝 Draw!", discord.Color.yellow()
                    desc = "Both bots matched wits across the full 4×4 board!"
                elif w == 1:
                    title, color = "🏆 Minimax d4 Wins!", discord.Color.green()
                    desc = f"Depth-4 Minimax {X_EMJ} dominates the 4×4 board!"
                else:
                    title, color = "🏆 Strategic Bot Wins!", discord.Color.orange()
                    desc = f"Strategic Bot {O_EMJ} outsmarted the Minimax AI on 4×4!"

                embed = discord.Embed(title=title, description=desc, color=color)
                embed.set_footer(text=FOOTER)
                await message.edit(embed=embed, view=self)
                self.stop()
                return

            nxt = 3 - turn
            embed = discord.Embed(
                title="🤖 Bot vs Bot — 4×4 Tic Tac Toe",
                description=f"{BOT_NAMES[nxt]}'s turn {BOT_EMOJI[nxt]}\n*First to get 4 in a row wins!*",
                color=discord.Color.blurple()
            )
            embed.set_footer(text=FOOTER)
            await message.edit(embed=embed, view=self)
            turn = nxt

        self.stop()

# ══════════════════════════════════════════════════════════════
#  SHARED CHALLENGE VIEW  (PvP accept/decline)
# ══════════════════════════════════════════════════════════════

class ChallengeView(discord.ui.View):
    def __init__(self, challenger, opponent, mode="3x3"):
        super().__init__(timeout=30)
        self.challenger = challenger
        self.opponent = opponent
        self.mode = mode   # "3x3" or "4x4"

    @discord.ui.button(label="Accept ✅", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message("❌ This challenge isn't for you!", ephemeral=True)

        if self.mode == "3x3":
            game = TTTView(self.challenger, self.opponent)
            title = "🎮 Tic Tac Toe"
        else:
            game = TTT4View(self.challenger, self.opponent)
            title = "🎮 4×4 Tic Tac Toe"

        embed = discord.Embed(
            title=title,
            description=f"{self.challenger.mention}'s turn {X_EMJ}",
            color=discord.Color.blurple()
        )
        embed.set_footer(text=f"{self.challenger.display_name} {X_EMJ}  vs  {O_EMJ} {self.opponent.display_name}")
        await interaction.response.edit_message(embed=embed, view=game)
        self.stop()

    @discord.ui.button(label="Decline ❌", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in [self.opponent.id, self.challenger.id]:
            return await interaction.response.send_message("❌ This challenge isn't for you!", ephemeral=True)
        embed = discord.Embed(
            title="❌ Challenge Declined",
            description=f"{self.opponent.mention} declined the challenge.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

# ══════════════════════════════════════════════════════════════
#  COG  —  COMMANDS
# ══════════════════════════════════════════════════════════════

class TicTacToe(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ─── helper: kick off bot vs bot ───────────────────────────
    async def _bot_vs_bot(self, ctx, ViewClass, title, footer):
        view = ViewClass()
        embed = discord.Embed(
            title=title,
            description="🤖 Minimax AI is thinking...",
            color=discord.Color.blurple()
        )
        embed.set_footer(text=footer)
        msg = await ctx.reply(embed=embed, view=view)
        await view.auto_play(msg)

    # ─── 3×3 ───────────────────────────────────────────────────
    @commands.command(aliases=["ttt"])
    async def tictactoe(self, ctx, opponent: discord.Member = None):
        """
        3×3 Tic Tac Toe.
          !ttt           → You vs Minimax AI
          !ttt @bot      → Bot vs Bot (Minimax AI vs Strategic Bot) 🤖
          !ttt @user     → PvP challenge
        """
        if opponent is None:
            # Player vs Minimax AI
            view = TTTView(ctx.author, None, vs_bot=True)
            embed = discord.Embed(
                title="🎮 Tic Tac Toe",
                description=(
                    f"{ctx.author.mention}'s turn {X_EMJ}\n"
                    f"⚠️ Playing against **Minimax AI** — it never loses!"
                ),
                color=discord.Color.blurple()
            )
            embed.set_footer(text=f"{ctx.author.display_name} {X_EMJ}  vs  {O_EMJ} Bot [Minimax AI]")
            return await ctx.reply(embed=embed, view=view)

        if opponent.id == ctx.author.id:
            return await ctx.reply("❌ You can't play against yourself!")

        if opponent.bot:
            # ✨ Bot vs Bot mode
            return await self._bot_vs_bot(
                ctx,
                BotVsBotView3,
                "🤖 Bot vs Bot — Tic Tac Toe",
                f"{X_EMJ} Minimax AI  vs  {O_EMJ} Strategic Bot"
            )

        # PvP challenge
        embed = discord.Embed(
            title="🎮 Tic Tac Toe Challenge!",
            description=f"{ctx.author.mention} challenged {opponent.mention}!\n\n{opponent.mention}, do you accept?",
            color=discord.Color.orange()
        )
        embed.set_footer(text="Challenge expires in 30 seconds")
        await ctx.reply(embed=embed, view=ChallengeView(ctx.author, opponent, "3x3"))

    # ─── 4×4 ───────────────────────────────────────────────────
    @commands.command(aliases=["ttt4"])
    async def tictactoe4(self, ctx, opponent: discord.Member = None):
        """
        4×4 Tic Tac Toe — get 4 in a row to win!
          !ttt4           → You vs Minimax AI (depth 4)
          !ttt4 @bot      → Bot vs Bot (Minimax d4 vs Strategic Bot) 🤖
          !ttt4 @user     → PvP challenge
        """
        if opponent is None:
            view = TTT4View(ctx.author, None, vs_bot=True)
            embed = discord.Embed(
                title="🎮 4×4 Tic Tac Toe",
                description=(
                    f"{ctx.author.mention}'s turn {X_EMJ}\n"
                    f"*Get **4 in a row** to win!*\n"
                    f"⚠️ Playing against **Minimax AI (depth 4)**"
                ),
                color=discord.Color.blurple()
            )
            embed.set_footer(text=f"{ctx.author.display_name} {X_EMJ}  vs  {O_EMJ} Bot [Minimax d4]")
            return await ctx.reply(embed=embed, view=view)

        if opponent.id == ctx.author.id:
            return await ctx.reply("❌ You can't play against yourself!")

        if opponent.bot:
            # ✨ Bot vs Bot mode (4×4)
            return await self._bot_vs_bot(
                ctx,
                BotVsBotView4,
                "🤖 Bot vs Bot — 4×4 Tic Tac Toe",
                f"{X_EMJ} Minimax d4  vs  {O_EMJ} Strategic Bot"
            )

        # PvP challenge
        embed = discord.Embed(
            title="🎮 4×4 Tic Tac Toe Challenge!",
            description=f"{ctx.author.mention} challenged {opponent.mention}!\n\n{opponent.mention}, do you accept?",
            color=discord.Color.orange()
        )
        embed.set_footer(text="Challenge expires in 30 seconds")
        await ctx.reply(embed=embed, view=ChallengeView(ctx.author, opponent, "4x4"))


async def setup(bot):
    await bot.add_cog(TicTacToe(bot))
