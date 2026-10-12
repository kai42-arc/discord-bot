import os
import threading
from flask import Flask
import discord
from discord.ext import commands
from discord import app_commands
from typing import Dict, Optional, List

# ---------------------------------------------------------
# Render用のWebサーバー設定（ポート開放エラー回避）
# ---------------------------------------------------------
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.start()


# ---------------------------------------------------------
# Discord Bot 設定
# ---------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

COLOR_OPTIONS = [
    ("レッド", "🔴", "red"),
    ("ブルー", "🔷", "blue"),
    ("グリーン", "🟢", "green"),
    ("ピンク", "🌸", "pink"),
    ("オレンジ", "🍊", "orange"),
    ("イエロー", "🟡", "yellow"),
    ("ブラック", "⬛", "black"),
    ("ホワイト", "⚪", "white"),
    ("パープル", "🟣", "purple"),
    ("ブラウン", "🟤", "brown"),
    ("シアン", "💎", "cyan"),
    ("ライム", "🍈", "lime"),
]

# ---------------------------------------------------------
# カラー選択 View
# ---------------------------------------------------------
class ColorSelectView(discord.ui.View):
    def __init__(self, main_view: 'RecruitmentView'):
        super().__init__(timeout=None)
        self.main_view = main_view

        for label, emoji, cid in COLOR_OPTIONS:
            btn = discord.ui.Button(label=label, emoji=emoji, custom_id=f"color_{cid}", row=0 if len(self.children) < 5 else (1 if len(self.children) < 10 else 2))
            btn.callback = self.make_color_callback(cid, label)
            self.add_item(btn)

        free_btn = discord.ui.Button(label="FREE", emoji="🆓", style=discord.ButtonStyle.secondary, custom_id="color_free", row=3)
        free_btn.callback = self.make_color_callback("free", "FREE（おまかせ）")
        self.add_item(free_btn)

        clear_btn = discord.ui.Button(label="解除", emoji="❌", style=discord.ButtonStyle.danger, custom_id="color_clear", row=3)
        clear_btn.callback = self.make_color_callback("clear", "解除")
        self.add_item(clear_btn)

    def make_color_callback(self, color_id: str, color_label: str):
        async def callback(interaction: discord.Interaction):
            user = interaction.user
            if user not in self.main_view.participants:
                await interaction.response.send_message("⚠️ カラー選択は「参加者」のみ可能です。先に『参加』ボタンを押してください。", ephemeral=True)
                return

            if self.main_view.is_closed:
                await interaction.response.send_message("この募集はすでに締め切られています。", ephemeral=True)
                return

            if color_id == "clear":
                if user.id in self.main_view.user_colors:
                    del self.main_view.user_colors[user.id]
                    await interaction.response.send_message("希望カラーを解除しました。", ephemeral=True)
                else:
                    await interaction.response.send_message("カラーは設定されていません。", ephemeral=True)
            else:
                if color_id != "free":
                    for uid, cid in self.main_view.user_colors.items():
                        if cid == color_id and uid != user.id:
                            await interaction.response.send_message(f"⚠️ `{color_label}` はすでに他の参加者が選択しています。", ephemeral=True)
                            return

                self.main_view.user_colors[user.id] = color_id
                await interaction.response.send_message(f"希望カラーを `{color_label}` に設定しました。", ephemeral=True)

            await self.main_view.update_messages(interaction)

        return callback


# ---------------------------------------------------------
# メイン募集 View
# ---------------------------------------------------------
class RecruitmentView(discord.ui.View):
    def __init__(self, author: discord.Member, title: str, description: str, capacity: int):
        super().__init__(timeout=None)
        self.author = author
        self.title = title
        self.description = description
        self.capacity = capacity
        self.participants: List[discord.Member] = []
        self.user_colors: Dict[int, str] = {}
        self.is_closed = False
        self.message: Optional[discord.Message] = None
        self.color_message: Optional[discord.Message] = None

    def create_main_embed(self) -> discord.Embed:
        status = "🔴 募集終了" if self.is_closed else "🎮 募集を開始しました 🎮"
        embed = discord.Embed(
            title=status,
            description=f"**{self.title}**\n\n{self.description}",
            color=discord.Color.red() if self.is_closed else discord.Color.blue()
        )

        embed.add_field(name="募集者", value=self.author.mention, inline=False)

        members_str = "\n".join([m.display_name for m in self.participants]) if self.participants else "なし"
        embed.add_field(
            name=f"参加者 ({len(self.participants)}/{self.capacity})",
            value=members_str,
            inline=False
        )

        embed.add_field(
            name="操作案内",
            value="・**参加 / 辞退**: `✅ 参加` ボタン（再度押すと辞退）\n・**色選択**: 下のカラーパネルから選択できます。",
            inline=False
        )

        if self.message:
            embed.set_footer(text=f"message_id: {self.message.id}")

        return embed

    def create_color_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="上記募集の AmongUs希望色（先着順）",
            description="色選択は参加者のみできます。\n解除＝選択を取り消し / FREE＝色おまかせ・未定\n✅ 募集終了後も色は変更できます。",
            color=discord.Color.dark_purple()
        )

        lines = []
        for label, emoji, cid in COLOR_OPTIONS:
            assigned_users = [m.display_name for m in self.participants if self.user_colors.get(m.id) == cid]
            if assigned_users:
                lines.append(f"{emoji} **{label}**：{', '.join(assigned_users)}")

        free_users = [m.display_name for m in self.participants if self.user_colors.get(m.id) == "free" or m.id not in self.user_colors]
        if free_users:
            lines.append(f"🆓 **FREE**：{', '.join(free_users)}")

        embed.add_field(name="現在の割り当て", value="\n".join(lines) if lines else "なし", inline=False)
        return embed

    async def update_messages(self, interaction: discord.Interaction):
        main_embed = self.create_main_embed()
        color_embed = self.create_color_embed()

        if interaction.response.is_done():
            if self.message:
                await self.message.edit(embed=main_embed, view=self)
            if self.color_message:
                await self.color_message.edit(embed=color_embed)
        else:
            await interaction.response.edit_message(embed=main_embed, view=self)
            if self.color_message:
                await self.color_message.edit(embed=color_embed)

    @discord.ui.button(label="参加", style=discord.ButtonStyle.success, emoji="✅", custom_id="join_toggle_btn")
    async def join_toggle_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user

        if user in self.participants:
            self.participants.remove(user)
            if user.id in self.user_colors:
                del self.user_colors[user.id]
            
            if self.is_closed and len(self.participants) < self.capacity:
                self.is_closed = False
                button.disabled = False

            await interaction.response.send_message("参加をキャンセル（辞退）しました。", ephemeral=True)
            await self.update_messages(interaction)
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

        await interaction.response.send_message("参加登録しました！下のカラーパネルから希望色を選んでください。", ephemeral=True)
        await self.update_messages(interaction)


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
@app_commands.describe(
    title="募集タイトル",
    description="詳細説明",
    capacity="定員人数（数字のみ）"
)
async def recruit(interaction: discord.Interaction, title: str, description: str, capacity: int = 11):
    await interaction.response.defer()

    view = RecruitmentView(author=interaction.user, title=title, description=description, capacity=capacity)
    
    main_embed = view.create_main_embed()
    main_msg = await interaction.followup.send(embed=main_embed, view=view, wait=True)
    view.message = main_msg

    color_view = ColorSelectView(main_view=view)
    color_embed = view.create_color_embed()
    color_msg = await interaction.channel.send(embed=color_embed, view=color_view)
    view.color_message = color_msg

    await main_msg.edit(embed=view.create_main_embed())
    active_recruitments[main_msg.id] = view


@bot.tree.command(name="close", description="【作成者専用】指定した募集を終了します")
@app_commands.describe(message_id="終了したい募集メッセージのID")
async def close_recruitment(interaction: discord.Interaction, message_id: str):
    try:
        msg_id = int(message_id)
    except ValueError:
        await interaction.response.send_message("正しいメッセージIDを入力してください。", ephemeral=True)
        return

    view = active_recruitments.get(msg_id)
    if not view:
        await interaction.response.send_message("対象の募集が見つかりません。", ephemeral=True)
        return

    is_author = interaction.user.id == view.author.id
    is_admin = interaction.user.guild_permissions.administrator

    if not (is_author or is_admin):
        await interaction.response.send_message("⚠️ 募集を終了できるのは「作成者本人」または「管理者」のみです。", ephemeral=True)
        return

    view.is_closed = True
    for child in view.children:
        if isinstance(child, discord.ui.Button) and child.custom_id == "join_toggle_btn":
            child.disabled = True

    await view.message.edit(embed=view.create_main_embed(), view=view)
    await interaction.response.send_message("募集を終了（締め切り）しました。", ephemeral=True)


# Webサーバーをバックグラウンドで起動
asyncio.run(main())

# Discord Bot起動
bot.run(os.getenv('DISCORD_TOKEN'))
