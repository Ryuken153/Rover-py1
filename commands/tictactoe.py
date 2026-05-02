import discord
from discord.ext import commands

def check_winner(board):
    lines = [
        [0,1,2],[3,4,5],[6,7,8],  # rows
        [0,3,6],[1,4,7],[2,5,8],  # cols
        [0,4,8],[2,4,6]           # diagonals
    ]
    for line in lines:
        if board[line[0]] == board[line[1]] == board[line[2]] and board[line[0]] != 0:
            return board[line[0]], line
    if 0 not in board:
        return "draw", []
    return None, []

def minimax(board, is_maximizing, alpha=-float("inf"), beta=float("inf")):
    """Minimax with alpha-beta pruning. Bot=2 (maximizing), Player=1 (minimizing)."""
    winner, _ = check_winner(board)
    if winner == 2:
        return 10
    if winner == 1:
        return -10
    if winner == "draw":
        return 0

    if is_maximizing:
        best = -float("inf")
        for i in range(9):
            if board[i] == 0:
                board[i] = 2
                score = minimax(board, False, alpha, beta)
                board[i] = 0
                best = max(best, score)
                alpha = max(alpha, best)
                if beta <= alpha:
                    break
        return best
    else:
        best = float("inf")
        for i in range(9):
            if board[i] == 0:
                board[i] = 1
                score = minimax(board, True, alpha, beta)
                board[i] = 0
                best = min(best, score)
                beta = min(beta, best)
                if beta <= alpha:
                    break
        return best

def bot_move(board):
    """Returns the best possible move index using Minimax + alpha-beta pruning."""
    best_score = -float("inf")
    best_move = None
    for i in range(9):
        if board[i] == 0:
            board[i] = 2
            score = minimax(board, False)
            board[i] = 0
            if score > best_score:
                best_score = score
                best_move = i
    return best_move

class TicTacToeButton(discord.ui.Button):
    def __init__(self, index):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=index // 3)
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        view: TicTacToeView = self.view
        if interaction.user.id != view.current_player.id:
            return await interaction.response.send_message("❌ It's not your turn!", ephemeral=True)
        if view.board[self.index] != 0:
            return await interaction.response.send_message("❌ That cell is already taken!", ephemeral=True)

        # Player move
        view.board[self.index] = 1
        self.style = discord.ButtonStyle.blurple
        self.label = view.x_emoji
        self.disabled = True

        winner, winning_line = check_winner(view.board)
        if winner:
            await view.finish(interaction, winner, winning_line)
            return

        # Bot or other player move
        if view.vs_bot:
            move = bot_move(view.board)
            if move is not None:
                view.board[move] = 2
                btn = view.children[move]
                btn.style = discord.ButtonStyle.red
                btn.label = view.o_emoji
                btn.disabled = True

                winner, winning_line = check_winner(view.board)
                if winner:
                    await view.finish(interaction, winner, winning_line)
                    return

            await view.update(interaction)
        else:
            view.current_player = view.player2 if view.current_player == view.player1 else view.player1
            await view.update(interaction)

class TicTacToeView(discord.ui.View):
    def __init__(self, player1, player2, vs_bot=False):
        super().__init__(timeout=120)
        self.player1 = player1
        self.player2 = player2
        self.vs_bot = vs_bot
        self.current_player = player1
        self.board = [0] * 9
        self.x_emoji = "✖️"
        self.o_emoji = "⭕"

        for i in range(9):
            self.add_item(TicTacToeButton(i))

    async def update(self, interaction):
        symbol = "✖️" if self.current_player == self.player1 else "⭕"
        embed = discord.Embed(
            title="🎮 Tic Tac Toe",
            description=f"{self.current_player.mention}'s turn {symbol}",
            color=discord.Color.blurple()
        )
        if self.vs_bot:
            embed.set_footer(text=f"{self.player1.display_name} ✖️  vs  ⭕ Bot [Minimax AI]")
        else:
            embed.set_footer(text=f"{self.player1.display_name} ✖️  vs  ⭕ {self.player2.display_name}")
        await interaction.response.edit_message(embed=embed, view=self)

    async def finish(self, interaction, winner, winning_line):
        for i in winning_line:
            self.children[i].style = discord.ButtonStyle.green
        for btn in self.children:
            btn.disabled = True

        if winner == "draw":
            title = "🤝 It's a Draw!"
            color = discord.Color.yellow()
            desc = "The bot's Minimax AI couldn't be beaten, but neither could you!"
        elif winner == 1:
            title = f"🏆 {self.player1.display_name} Wins!"
            color = discord.Color.green()
            desc = f"{self.player1.mention} ✖️ beat the Minimax AI! Impressive!"
        else:
            if self.vs_bot:
                title = "🤖 Bot Wins!"
                color = discord.Color.red()
                desc = "The Minimax AI is unbeatable. Better luck next time!"
            else:
                title = f"🏆 {self.player2.display_name} Wins!"
                color = discord.Color.green()
                desc = f"{self.player2.mention} ⭕ wins the game!"

        embed = discord.Embed(title=title, description=desc, color=color)
        if self.vs_bot:
            embed.set_footer(text=f"{self.player1.display_name} ✖️  vs  ⭕ Bot [Minimax AI]")
        else:
            embed.set_footer(text=f"{self.player1.display_name} ✖️  vs  ⭕ {self.player2.display_name}")
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    async def on_timeout(self):
        for btn in self.children:
            btn.disabled = True

class TicTacToe(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["ttt"])
    async def tictactoe(self, ctx, opponent: discord.Member = None):
        """Play Tic Tac Toe! Use !tictactoe @user or !tictactoe to play vs bot."""

        if opponent is None:
            view = TicTacToeView(ctx.author, None, vs_bot=True)
            embed = discord.Embed(
                title="🎮 Tic Tac Toe",
                description=f"{ctx.author.mention}'s turn ✖️\n\n⚠️ You're playing against **Minimax AI** — it never loses!",
                color=discord.Color.blurple()
            )
            embed.set_footer(text=f"{ctx.author.display_name} ✖️  vs  ⭕ Bot [Minimax AI]")
            return await ctx.reply(embed=embed, view=view)

        if opponent.id == ctx.author.id:
            return await ctx.reply("❌ You can't play against yourself!")

        if opponent.bot:
            return await ctx.reply("❌ You can't challenge a bot! Use `!tictactoe` without mentioning anyone to play vs me.")

        embed = discord.Embed(
            title="🎮 Tic Tac Toe Challenge!",
            description=f"{ctx.author.mention} has challenged {opponent.mention} to a game!\n\n{opponent.mention} do you accept?",
            color=discord.Color.orange()
        )
        embed.set_footer(text="Challenge expires in 30 seconds")

        class ChallengeView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30)

            @discord.ui.button(label="Accept ✅", style=discord.ButtonStyle.green)
            async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != opponent.id:
                    return await interaction.response.send_message("❌ This challenge is not for you!", ephemeral=True)
                game_view = TicTacToeView(ctx.author, opponent, vs_bot=False)
                game_embed = discord.Embed(
                    title="🎮 Tic Tac Toe",
                    description=f"{ctx.author.mention}'s turn ✖️",
                    color=discord.Color.blurple()
                )
                game_embed.set_footer(text=f"{ctx.author.display_name} ✖️  vs  ⭕ {opponent.display_name}")
                await interaction.response.edit_message(embed=game_embed, view=game_view)
                self.stop()

            @discord.ui.button(label="Decline ❌", style=discord.ButtonStyle.red)
            async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id not in [opponent.id, ctx.author.id]:
                    return await interaction.response.send_message("❌ This challenge is not for you!", ephemeral=True)
                embed = discord.Embed(
                    title="❌ Challenge Declined",
                    description=f"{opponent.mention} declined the challenge.",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=embed, view=None)
                self.stop()

        await ctx.reply(embed=embed, view=ChallengeView())

async def setup(bot):
    await bot.add_cog(TicTacToe(bot))
