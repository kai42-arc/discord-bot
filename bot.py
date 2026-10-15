import os
import threading
from flask import Flask
import discord
from discord.ext import commands
from discord import app_commands
from typing import Dict, Optional, List

# --- Flask Keep Alive ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

class RecruitmentView(discord.ui.View):
    def __init__(self, author: discord.Member, title: str, description: str, capacity: int):
        super().__init__(timeout=None)
        self.author = author
        self.title = title
        self.description = description
        self.capacity = capacity
        self.participants: List[discord.Member] = []
        self.is_closed = False
        self.message: Optional[discord.Message] = None

    def create_main_embed(self) -> discord.Embed:
        status = "🔴 募集終了" if self.is_closed else "🎮 募集を開始しました 🎮"
        embed = discord.Embed(
            title=status,
            description=f"**{self.title}**\n\n{self.description}",
            color=discord.Color.red() if self.is_closed else discord.Color.blue()
        )
        embed.add_field(name="募集者", value=self.author.mention, inline=False)
        members_str = "\n".join([m.display_name for m in self.participants]) if self.participants else "なし"
        embed.add_field(name=f"参加者 ({len(self.participants)}/{self.capacity})", value=members_str, inline=False)
        embed.add_field(name="操作案内", value="・**参加 / 辞退**: `✅ 参加` ボタン（再度押すと辞退）", inline=False)
        if self.message:
            embed.set_footer(text=f"message_id: {self.message.id}")
        return embed

    async def update_message(self, interaction: discord.Interaction):
        main_embed = self.create_main_embed()
        if interaction.response.is_done():
            if self.message:
                await self.message.edit(embed=main_embed, view=self)
        else:
            await interaction.response.edit_message(embed=main_embed, view=self)

    @discord.ui.button(label="参加", style=discord.ButtonStyle.success, emoji="✅", custom_id="join_toggle_btn")
    async def join_toggle_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if user in self.participants:
            self.participants.remove(user)
            if self.is_closed and len(self.participants) < self.capacity:
                self.is_closed = False
                button.disabled = False
            await interaction.response.send_message("参加をキャンセル（辞退）しました。", ephemeral=True)
            await self.update_message(interaction)
            return

        if self.is_closed:
            await interaction.response.send_message("⚠️ この募集はすでに締め切られています。", ephemeral=True)
            return

        if len(self.participants) >= self.capacity:
            await interaction.response.send_message("⚠️ 定員に達しているため参加できません。", ephemeral=True)
            return

        self.participants.append(user)
        if len(self.participants) >= self.capacity:
            self.is_closed = True
            button.disabled = True

        await interaction.response.send_message("参加登録しました！", ephemeral=True)
        await self.update_message(interaction)

active_recruitments: Dict[int, RecruitmentView] = {}

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)

@bot.tree.command(name="recruit", description="新規募集を開始します")
@app_commands.describe(title="募集タイトル", description="詳細説明", capacity="定員人数（数字のみ）")
async def recruit(interaction: discord.Interaction, title: str, description: str, capacity: int = 11):
    await interaction.response.defer()
    view = RecruitmentView(author=interaction.user, title=title, description=description, capacity=capacity)
    main_embed = view.create_main_embed()
    main_msg = await interaction.followup.send(embed=main_embed, view=view, wait=True)
    view.message = main_msg
    await main_msg.edit(embed=view.create_main_embed())
    active_recruitments[main_msg.id] = view

@bot.tree.command(name="close", description="【作成者専用】指定した募集を終了します")
@app_commands.describe(message_id="終了したい募集メッセージのID")
async def close_recruitment(interaction: discord.Interaction, message_id: str):
    await interaction.response.defer(ephemeral=True)

    try:
        msg_id = int(message_id)
    except ValueError:
        await interaction.followup.send("⚠️ 正しいメッセージID（数字）を入力してください。", ephemeral=True)
        return

    view = active_recruitments.get(msg_id)
    if not view:
        await interaction.followup.send("⚠️ 対象の募集が見つかりません。（Botが再起動されたか、IDが間違っている可能性があります）", ephemeral=True)
        return

    is_author = interaction.user.id == view.author.id
    is_admin = interaction.user.guild_permissions.administrator
    if not (is_author or is_admin):
        await interaction.followup.send("⚠️ 募集を終了できるのは「作成者本人」または「管理者」のみです。", ephemeral=True)
        return

    view.is_closed = True
    for child in view.children:
        if isinstance(child, discord.ui.Button) and child.custom_id == "join_toggle_btn":
            child.disabled = True

    await view.message.edit(embed=view.create_main_embed(), view=view)
    await interaction.followup.send("募集を終了（締め切り）しました。", ephemeral=True)

if __name__ == "__main__":
    keep_alive()
    token = os.getenv('DISCORD_TOKEN')
    if token:
        bot.run(token)
    else:
        print("Error: DISCORD_TOKEN environment variable is not set.")
