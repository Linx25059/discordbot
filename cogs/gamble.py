import discord
from discord import app_commands
from discord.ext import commands, tasks
import random
import asyncio
import aiosqlite
from typing import Optional
import datetime
import zoneinfo

# --- 21點 輔助函式 ---
def get_deck(num_decks=4):
    """取得洗好的撲克牌堆 (多副牌混洗)"""
    suits = ['♠', '♥', '♦', '♣']
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    deck = [s + r for s in suits for r in ranks] * num_decks
    random.shuffle(deck)
    return deck

def calculate_hand(hand):
    """計算 21 點手牌點數 (A 自動算 1 或 11)"""
    value = 0
    aces = 0
    for card in hand:
        rank = card[1:] # 略過前面的花色
        if rank in ['J', 'Q', 'K']:
            value += 10
        elif rank == 'A':
            value += 11
            aces += 1
        else:
            value += int(rank)
    # 如果爆牌，且手上有 A，就把 A 當成 1
    while value > 21 and aces > 0:
        value -= 10
        aces -= 1
    return value

# --- 圖片/表情符號 輔助函式 ---
def get_card_display(card):
    """將卡牌轉換為 Discord 自訂表情符號 (Emoji) 或維持文字顯示"""
    # TODO: 若要使用圖片，請將 52 張牌圖片上傳至 Discord 伺服器並取得 Emoji ID
    # 格式如： '<:spades_A:123456789012345678>'
    card_emojis = {
        # '♠A': '<:sA:111111111111>',
        # '♥K': '<:hK:222222222222>',
    }
    return card_emojis.get(card, f"`{card}`") # 若無圖片則回傳加了反白的純文字

# --- 重新下注 Modal ---
class RebetModal(discord.ui.Modal, title='💸 重新下注'):
    new_amount_input = discord.ui.TextInput(
        label='新的下注金額',
        placeholder='請輸入你想下注的金額',
        required=True,
        style=discord.TextStyle.short
    )

    def __init__(self, original_view: "PlayAgainView"):
        super().__init__(timeout=180)
        self.original_view = original_view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.new_amount_input.value)
            if amount <= 0:
                return await interaction.response.send_message("❌ 金額必須大於 0！", ephemeral=True)
        except ValueError:
            return await interaction.response.send_message("❌ 請輸入有效的數字金額！", ephemeral=True)

        # 檢查餘額
        current_balance = await self.original_view.cog.bot.db.get_balance(interaction.user.id)
        if current_balance < amount:
            return await interaction.response.send_message(f"❌ 你的餘額不足！(需要 **{amount:,}** 金幣)", ephemeral=True)

        # 停用舊訊息的按鈕
        for child in self.original_view.children:
            child.disabled = True
        await interaction.message.edit(view=self.original_view)
        
        # 回應 Modal
        await interaction.response.send_message(f"✅ 已用新賭注 **{amount:,}** 金幣重新開始一局！", ephemeral=True)
        
        # 準備新參數
        new_args = list(self.original_view.args)
        new_args[-1] = amount
        
        # 呼叫原指令
        await self.original_view.command_coro(self.original_view.cog, self.original_view.ctx, *new_args, **self.original_view.kwargs)

class BlackjackRebetModal(discord.ui.Modal, title='💸 重新下注開桌'):
    new_amount_input = discord.ui.TextInput(
        label='新的牌桌賭注',
        placeholder='請輸入每位玩家加入的賭注金額',
        required=True,
        style=discord.TextStyle.short
    )

    def __init__(self, original_view: "BlackjackPlayView"):
        super().__init__(timeout=180)
        self.original_view = original_view
        self.cog = original_view.cog
        self.ctx = original_view.ctx

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.new_amount_input.value)
            if amount <= 0:
                return await interaction.response.send_message("❌ 金額必須大於 0！", ephemeral=True)
        except ValueError:
            return await interaction.response.send_message("❌ 請輸入有效的數字金額！", ephemeral=True)

        # 檢查餘額
        current_balance = await self.cog.bot.db.get_balance(interaction.user.id)
        if current_balance < amount:
            return await interaction.response.send_message(f"❌ 你的餘額不足以用此金額開桌！(需要 **{amount:,}** 金幣)", ephemeral=True)

        # 停用舊訊息的按鈕
        for child in self.original_view.children:
            child.disabled = True
            
        # 安全地更新原訊息 (避免 interaction.message 為 None 的情況)
        if interaction.message:
            try:
                await interaction.message.edit(view=self.original_view)
            except: pass
        elif self.original_view.message:
            try:
                await self.original_view.message.edit(view=self.original_view)
            except: pass
        
        # 回應 Modal
        await interaction.response.send_message(f"✅ 已用新賭注 **{amount:,}** 金幣重新開桌！", ephemeral=True)
        
        # 呼叫 21 點指令
        await self.cog.blackjack.callback(self.cog, self.ctx, amount)

# --- 21點 UI 面板 ---
class BlackjackPlayView(discord.ui.View):
    """21點：遊玩與操作階段"""
    def __init__(self, cog, participants, dealer_hand, deck):
        super().__init__(timeout=60) # 每個玩家有 60 秒可以考慮
        self.cog = cog
        self.players = list(participants.values())
        self.dealer_hand = dealer_hand
        self.deck = deck
        self.current_idx = 0
        self.ctx = None
        self.amount = 0
        self.message = None

    def get_current_player(self):
        if self.current_idx < len(self.players):
            return self.players[self.current_idx]
        return None

    async def on_timeout(self):
        # 超時防呆：自動幫剩下還沒動作的玩家全部停牌
        for p in self.players[self.current_idx:]:
            if p['status'] == 'playing':
                p['status'] = 'stand'
        await self.dealer_turn(None)

    async def update_ui(self, interaction=None):
        p = self.get_current_player()
        # 如果所有玩家都操作完畢，換莊家(機器人)動作
        if p is None:
            return await self.dealer_turn(interaction)
        
        val = calculate_hand(p['hand'])
        # 如果自動達到 21 點或爆牌，強制跳到下一位
        if val >= 21:
            p['status'] = 'bust' if val > 21 else 'stand'
            self.current_idx += 1
            return await self.update_ui(interaction)
            
        embed = self.build_embed()
        if interaction:
            try:
                await interaction.message.edit(embed=embed, view=self)
            except:
                pass
        elif self.message:
            await self.message.edit(embed=embed, view=self)

    def build_embed(self, show_dealer=False):
        embed = discord.Embed(title="🃏 皇家 21 點", color=discord.Color.dark_green())
        
        # 莊家區塊
        if show_dealer:
            dealer_val = calculate_hand(self.dealer_hand)
            dealer_cards = " ".join([get_card_display(c) for c in self.dealer_hand])
            dealer_text = f"**({dealer_val}點)** " + dealer_cards
        else:
            dealer_text = f"(?點) {get_card_display(self.dealer_hand[0])} 🎴"
        embed.add_field(name="🤵 莊家", value=dealer_text, inline=False)
        
        # 玩家區塊
        for i, p in enumerate(self.players):
            val = calculate_hand(p['hand'])
            # 目前動作的玩家前面加上箭頭標示
            status_icon = "▶️ " if i == self.current_idx and not show_dealer else "👤 "
            hand_label = f" (手牌 {p['split_idx']})" if 'split_idx' in p else ""
            
            hand_str = " ".join([get_card_display(c) for c in p['hand']])
            if p['status'] == 'bust':
                status_str = "💥 爆牌"
            elif p['status'] == 'surrender':
                status_str = "🏳️ 投降"
            elif val == 21 and len(p['hand']) == 2:
                status_str = "🌟 黑傑克"
            else:
                status_str = f"{val}點"
                
            embed.add_field(name=f"{status_icon}{p['user'].display_name}{hand_label}", 
                            value=f"牌：{hand_str} | {status_str}\n賭注：`{p['bet']}`", inline=False)
            
        if not show_dealer:
            p = self.get_current_player()
            embed.set_footer(text=f"👉 現在輪到 {p['user'].display_name} 動作！(60秒未動作自動停牌)")
        return embed

    @discord.ui.button(label="👆 補牌", style=discord.ButtonStyle.primary)
    async def hit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self.get_current_player()
        if interaction.user.id != p['user'].id:
            return await interaction.response.send_message("❌ 還沒輪到你啦，別急！", ephemeral=True)
        
        p['hand'].append(self.deck.pop())
        await interaction.response.defer()
        await self.update_ui(interaction)

    @discord.ui.button(label="✋ 停牌", style=discord.ButtonStyle.secondary)
    async def stand_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self.get_current_player()
        if interaction.user.id != p['user'].id:
            return await interaction.response.send_message("❌ 還沒輪到你，別亂按喔！", ephemeral=True)
        
        p['status'] = 'stand'
        self.current_idx += 1
        await interaction.response.defer()
        await self.update_ui(interaction)

    @discord.ui.button(label="💰 雙倍下注", style=discord.ButtonStyle.success)
    async def double_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self.get_current_player()
        if interaction.user.id != p['user'].id:
            return await interaction.response.send_message("❌ 還沒輪到你喔！", ephemeral=True)
        
        if len(p['hand']) != 2:
            return await interaction.response.send_message("❌ 只有剛發完頭兩張牌時才能雙倍下注喔！", ephemeral=True)
        
        bal = await self.cog.bot.db.get_balance(p['user'].id)
        if bal < p['bet']:
            return await interaction.response.send_message("❌ 你的餘額不夠加倍囉！", ephemeral=True)
        
        # 扣除加倍的賭注
        await self.cog.bot.db.update_balance(p['user'].id, -p['bet'])
        p['bet'] *= 2
        
        # 發最後一張牌並強制定格
        p['hand'].append(self.deck.pop())
        val = calculate_hand(p['hand'])
        p['status'] = 'bust' if val > 21 else 'stand'
        self.current_idx += 1
        
        await interaction.response.defer()
        await self.update_ui(interaction)

    @discord.ui.button(label="✂️ 分牌", style=discord.ButtonStyle.blurple)
    async def split_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self.get_current_player()
        if interaction.user.id != p['user'].id:
            return await interaction.response.send_message("❌ 還沒輪到你喔！", ephemeral=True)
        if len(p['hand']) != 2:
            return await interaction.response.send_message("❌ 只有剛發完兩張牌時才能分牌喔！", ephemeral=True)
            
        rank1, rank2 = p['hand'][0][1:], p['hand'][1][1:]
        val1 = 10 if rank1 in ['J', 'Q', 'K'] else (11 if rank1 == 'A' else int(rank1))
        val2 = 10 if rank2 in ['J', 'Q', 'K'] else (11 if rank2 == 'A' else int(rank2))
        if val1 != val2:
            return await interaction.response.send_message("❌ 兩張牌點數相同才能分牌喔！", ephemeral=True)
            
        bal = await self.cog.bot.db.get_balance(p['user'].id)
        if bal < p['bet']:
            return await interaction.response.send_message("❌ 你的餘額不夠分牌下注囉！", ephemeral=True)
            
        await self.cog.bot.db.update_balance(p['user'].id, -p['bet'])
        
        card1, card2 = p['hand'][0], p['hand'][1]
        p['hand'] = [card1, self.deck.pop()]
        if 'split_idx' not in p: p['split_idx'] = 1
            
        new_hand = {'user': p['user'], 'hand': [card2, self.deck.pop()], 'status': 'playing', 'bet': p['bet'], 'split_idx': p['split_idx'] + 1}
        self.players.insert(self.current_idx + 1, new_hand)
        
        await interaction.response.defer()
        await self.update_ui(interaction)

    @discord.ui.button(label="🏳️ 投降", style=discord.ButtonStyle.danger)
    async def surrender_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self.get_current_player()
        if interaction.user.id != p['user'].id:
            return await interaction.response.send_message("❌ 還沒輪到你喔！", ephemeral=True)
        if len(p['hand']) != 2:
            return await interaction.response.send_message("❌ 只有剛發完頭兩張牌時才能投降喔！", ephemeral=True)
        p['status'] = 'surrender'
        self.current_idx += 1
        await interaction.response.defer()
        await self.update_ui(interaction)

    async def dealer_turn(self, interaction):
        self.stop()
        for child in self.children:
            child.disabled = True
        
        # 賭場正規規則：莊家未滿 17 點必須強迫補牌
        while calculate_hand(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())
        
        dealer_val = calculate_hand(self.dealer_hand)
        dealer_bust = dealer_val > 21
        
        embed = self.build_embed(show_dealer=True)
        result_texts = []
        
        # 結算每位玩家的輸贏
        for p in self.players:
            val = calculate_hand(p['hand'])
            hand_label = f" (手牌 {p['split_idx']})" if 'split_idx' in p else ""
            mention_name = f"{p['user'].mention}{hand_label}"
            
            # 老闆特權：只要不是選擇投降，就算爆牌也強制判定獲勝！
            is_owner = await self.cog.bot.is_owner(p['user'])
            if is_owner and p['status'] != 'surrender':
                win = p['bet'] * 2
                await self.cog.bot.db.update_balance(p['user'].id, win)
                await self.cog.update_gamble_profit(p['user'].id, p['bet'])
                result_texts.append(f"👑 {mention_name} 發動了 **【老闆特權】**，無視規則強制獲勝！賺了 `{p['bet']}` 金幣！")
                continue

            if p['status'] == 'bust':
                await self.cog.update_gamble_profit(p['user'].id, -p['bet'])
                result_texts.append(f"❌ {mention_name} 爆牌了，損失 `{p['bet']}` 金幣。")
            elif p['status'] == 'surrender':
                half_bet = int(p['bet'] / 2)
                await self.cog.bot.db.update_balance(p['user'].id, half_bet)
                await self.cog.update_gamble_profit(p['user'].id, half_bet - p['bet'])
                result_texts.append(f"🏳️ {mention_name} 選擇投降，退回一半賭注 (`{half_bet}` 金幣)。")
            else:
                is_bj = val == 21 and len(p['hand']) == 2 and not p.get('split_idx')
                dealer_is_bj = dealer_val == 21 and len(self.dealer_hand) == 2
                
                if is_bj and not dealer_is_bj:
                    win = int(p['bet'] * 2.5) # BJ 贏 1.5 倍 (拿回本金 + 1.5倍獎金)
                    await self.cog.bot.db.update_balance(p['user'].id, win)
                    await self.cog.update_gamble_profit(p['user'].id, win - p['bet'])
                    result_texts.append(f"🎉 {mention_name} **黑傑克！** 贏得 `{win - p['bet']}` 金幣！")
                elif not is_bj and dealer_is_bj:
                    await self.cog.update_gamble_profit(p['user'].id, -p['bet'])
                    result_texts.append(f"💀 {mention_name} 遭莊家通殺，損失 `{p['bet']}` 金幣。")
                elif dealer_bust or val > dealer_val:
                    win = p['bet'] * 2
                    await self.cog.bot.db.update_balance(p['user'].id, win)
                    await self.cog.update_gamble_profit(p['user'].id, p['bet'])
                    result_texts.append(f"🎊 {mention_name} 贏了莊家！賺了 `{p['bet']}` 金幣！")
                elif val == dealer_val:
                    await self.cog.bot.db.update_balance(p['user'].id, p['bet'])
                    result_texts.append(f"🤝 {mention_name} 平手，退回 `{p['bet']}` 金幣。")
                else:
                    await self.cog.update_gamble_profit(p['user'].id, -p['bet'])
                    result_texts.append(f"❌ {mention_name} 點數小於莊家，損失 `{p['bet']}` 金幣。")
        
        embed.add_field(name="──────────\n📊 結算結果", value="\n".join(result_texts), inline=False)
        embed.set_footer(text="遊戲結束！想玩的話可以自己開一桌喔。")
        
        # 加入「再來一局」按鈕 (限房主)
        if self.ctx:
            play_again_btn = discord.ui.Button(label="🔄 再開一桌", style=discord.ButtonStyle.success)
            
            async def play_again_callback(inter: discord.Interaction):
                if inter.user.id != self.ctx.author.id:
                    return await inter.response.send_message("❌ 只有原房主可以重新開桌喔！", ephemeral=True)
                
                bal = await self.cog.bot.db.get_balance(self.ctx.author.id)
                if bal < self.amount:
                    return await inter.response.send_message(f"❌ 你的餘額不足以再開一桌！(需要 **{self.amount:,}** 金幣)", ephemeral=True)
                
                for child in self.children:
                    child.disabled = True
                await inter.response.edit_message(view=self)
                await self.cog.blackjack.callback(self.cog, self.ctx, self.amount)
                
            play_again_btn.callback = play_again_callback
            self.add_item(play_again_btn)

            rebet_btn = discord.ui.Button(label="💸 重新下注", style=discord.ButtonStyle.secondary)
            async def rebet_callback(inter: discord.Interaction):
                if inter.user.id != self.ctx.author.id:
                    return await inter.response.send_message("❌ 只有原房主可以重新開桌喔！", ephemeral=True)
                
                await inter.response.send_modal(BlackjackRebetModal(self))
            rebet_btn.callback = rebet_callback
            self.add_item(rebet_btn)

        if interaction:
            try:
                await interaction.message.edit(embed=embed, view=self)
            except: pass
        elif self.message:
            await self.message.edit(embed=embed, view=self)

class BlackjackLobbyView(discord.ui.View):
    """21點：大廳招募階段"""
    def __init__(self, cog, ctx, bet_amount):
        super().__init__(timeout=45) # 給大家 45 秒可以坐下
        self.cog = cog
        self.ctx = ctx
        self.host = ctx.author
        self.bet_amount = bet_amount
        self.participants = {self.host.id: {'user': self.host, 'hand': [], 'status': 'playing', 'bet': bet_amount}}
        self.message = None

    async def on_timeout(self):
        await self.start_game()

    @discord.ui.button(label="🪑 坐下 (加入)", style=discord.ButtonStyle.success)
    async def join_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.participants:
            return await interaction.response.send_message("❌ 你已經在牌桌上了喔！", ephemeral=True)
        if len(self.participants) >= 5:
            return await interaction.response.send_message("❌ 滿桌了！下局請早。", ephemeral=True)
        
        bal = await self.cog.bot.db.get_balance(interaction.user.id)
        if bal < self.bet_amount:
            return await interaction.response.send_message(f"❌ 你的餘額不足以加入牌桌喔！(需要 **{self.bet_amount}** 金幣)", ephemeral=True)
        
        await self.cog.bot.db.update_balance(interaction.user.id, -self.bet_amount)
        self.participants[interaction.user.id] = {'user': interaction.user, 'hand': [], 'status': 'playing', 'bet': self.bet_amount}
        
        embed = self.message.embeds[0]
        embed.description = (
            f"💰 **固定賭注：** `{self.bet_amount}` 金幣\n"
            f"👥 **目前玩家：** `{len(self.participants)}/5` 人\n"
            "──────────────────\n"
            + "\n".join([f"👤 {p['user'].mention}" for p in self.participants.values()])
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🃏 莊家發牌 (開始)", style=discord.ButtonStyle.primary)
    async def start_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host.id:
            return await interaction.response.send_message("❌ 只有開桌的莊家可以宣佈開始喔！", ephemeral=True)
        await self.start_game(interaction)

    async def start_game(self, interaction=None):
        self.stop()
        deck = get_deck(4)
        dealer_hand = [deck.pop(), deck.pop()]
        for p in self.participants.values():
            p['hand'] = [deck.pop(), deck.pop()]
            
        play_view = BlackjackPlayView(self.cog, self.participants, dealer_hand, deck)
        play_view.ctx = self.ctx
        play_view.amount = self.bet_amount
        play_view.message = self.message
        
        if interaction:
            await interaction.response.defer()
            
        await play_view.update_ui(interaction)

class PlayAgainView(discord.ui.View):
    """通用的「再玩一次」互動按鈕"""
    def __init__(self, command_coro, cog, ctx, *args, **kwargs):
        super().__init__(timeout=180)  # 3 分鐘後按鈕失效
        self.command_coro = command_coro
        self.cog = cog
        self.ctx = ctx
        self.args = args
        self.kwargs = kwargs

    @discord.ui.button(label="🔄 再玩一次", style=discord.ButtonStyle.success)
    async def play_again(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 防呆：限制只能由原發起人點擊
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                embed=discord.Embed(description="❌ 這是別人的賭局，請自己發起一局喔！", color=discord.Color.red()), 
                ephemeral=True
            )
        
        # 停用所有按鈕並更新原本的訊息 (避免雙按鈕被重複連續點擊)
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        
        # 重新呼叫該遊戲的核心邏輯 (會自動在最下方發送一場新賭局)
        await self.command_coro(self.cog, self.ctx, *self.args, **self.kwargs)

    @discord.ui.button(label="💸 重新下注", style=discord.ButtonStyle.secondary)
    async def rebet(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(embed=discord.Embed(description="❌ 這是別人的賭局，請自己發起一局喔！", color=discord.Color.red()), ephemeral=True)
        
        # 呼叫彈出式視窗
        modal = RebetModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🟡 ✖️2 倍壓下注", style=discord.ButtonStyle.primary)
    async def double_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(embed=discord.Embed(description="❌ 這是別人的賭局，請自己發起一局喔！", color=discord.Color.red()), ephemeral=True)
            
        # 檢查倍壓後的餘額是否足夠
        new_amount = self.args[-1] * 2
        current_balance = await self.cog.bot.db.get_balance(interaction.user.id)
        if current_balance < new_amount:
            return await interaction.response.send_message(embed=discord.Embed(description=f"❌ 你的餘額不足以倍壓！需要 **{new_amount:,}** 金幣。", color=discord.Color.red()), ephemeral=True)
            
        # 停用所有按鈕
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        
        # 替換下注金額參數 (因為三個賭博遊戲的 amount 始終是 args 傳入的最後一個參數)
        new_args = list(self.args)
        new_args[-1] = new_amount
        
        # 以兩倍賭注重新呼叫遊戲邏輯
        await self.command_coro(self.cog, self.ctx, *new_args, **self.kwargs)

class Gamble(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        # 建立賭場歷史淨利追蹤表
        await self.bot.db.db.execute('''CREATE TABLE IF NOT EXISTS gamble_stats (user_id INTEGER PRIMARY KEY, net_profit INTEGER DEFAULT 0)''')
        await self.bot.db.db.commit()
        self.weekly_reset_task.start()

    async def cog_unload(self):
        self.weekly_reset_task.cancel()

    # 設定排程任務：每天台灣時間 00:00 執行
    tz_tw = zoneinfo.ZoneInfo("Asia/Taipei")
    @tasks.loop(time=datetime.time(hour=0, minute=0, second=0, tzinfo=tz_tw))
    async def weekly_reset_task(self):
        # 確保只有在星期一 (0) 執行
        if datetime.datetime.now(self.tz_tw).weekday() != 0:
            return

        # 抓取淨賺最多的前三名 (且必須是大於 0 的贏家)
        async with self.bot.db.db.execute('SELECT user_id, net_profit FROM gamble_stats WHERE net_profit > 0 ORDER BY net_profit DESC LIMIT 3') as cursor:
            top_players = await cursor.fetchall()

        if top_players:
            rewards = [50000, 30000, 10000]
            medals = ["🥇", "🥈", "🥉"]

            for i, (user_id, profit) in enumerate(top_players):
                reward = rewards[i]
                await self.bot.db.update_balance(user_id, reward)
                
                # 嘗試抓取使用者物件 (若快取中沒有則透過 API 抓取)
                user = self.bot.get_user(user_id)
                if not user:
                    try:
                        user = await self.bot.fetch_user(user_id)
                    except discord.NotFound:
                        pass

                if user:
                    try:
                        embed = discord.Embed(title="🏆 賭場每週排行結算", description=f"恭喜你在本週的賭場排行榜獲得 {medals[i]} 第 {i+1} 名！\n這週你總共淨賺了 **{profit:,}** 金幣。\n\n🎁 **獲得排行獎勵：** `{reward:,}` 金幣", color=discord.Color.gold())
                        await user.send(embed=embed)
                    except discord.Forbidden:
                        pass

        # 清空所有人的淨利紀錄，迎接新的一週
        await self.bot.db.db.execute('UPDATE gamble_stats SET net_profit = 0')
        await self.bot.db.db.commit()

    @weekly_reset_task.before_loop
    async def before_weekly_reset(self):
        await self.bot.wait_until_ready()

    async def update_gamble_profit(self, user_id: int, amount: int):
        async with self.bot.db.db.execute('SELECT net_profit FROM gamble_stats WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            await self.bot.db.db.execute('UPDATE gamble_stats SET net_profit = net_profit + ? WHERE user_id = ?', (amount, user_id))
        else:
            await self.bot.db.db.execute('INSERT INTO gamble_stats (user_id, net_profit) VALUES (?, ?)', (user_id, amount))
        await self.bot.db.db.commit()

    async def check_win_achievement(self, ctx: commands.Context, amount: int) -> str:
        if amount >= 50000:
            if await self.bot.db.check_and_add_achievement(ctx.author.id, '【賭神】'):
                return f"\n\n🎰 **成就解鎖！** 單次贏得超過 50,000 金幣！獲得稱號 **【賭神】**！"
        return ""

    async def check_loss_achievement(self, ctx: commands.Context, amount: int) -> str:
        ach_msg = ""
        if amount >= 10000:
            if await self.bot.db.check_and_add_achievement(ctx.author.id, '【大慈善家】'):
                ach_msg += f"\n\n💸 **成就解鎖！** 單次輸掉超過 10,000 金幣... 獲得稱號 **【大慈善家】**！"
        
        # 檢查是否破產 (餘額歸零)
        if await self.bot.db.get_balance(ctx.author.id) <= 0:
            if await self.bot.db.check_and_add_achievement(ctx.author.id, '【破產仔】'):
                ach_msg += f"\n\n📉 **成就解鎖！** 餘額歸零... 獲得稱號 **【破產仔】**！"
                
        return ach_msg

    # --- 賭博遊戲區 ---
    @commands.hybrid_command(name="coinflip", aliases=["cf", "猜硬幣"], help="猜硬幣正反面")
    @app_commands.describe(choice="選擇你要猜哪一面", amount="下注金額")
    @app_commands.choices(choice=[
        app_commands.Choice(name="🪙 正面", value="正"),
        app_commands.Choice(name="🪙 反面", value="反")
    ])
    async def coinflip(self, ctx: commands.Context, choice: str, amount: int):
        if amount <= 0:
            return await ctx.send(embed=discord.Embed(description="❌ 下注金額必須大於 0 喔！", color=discord.Color.red()), ephemeral=True)
        if await self.bot.db.get_balance(ctx.author.id) < amount:
            return await ctx.send(embed=discord.Embed(description="❌ 你的餘額不足，無法下注！", color=discord.Color.red()), ephemeral=True)
        if choice not in ["正", "反"]:
            return await ctx.send(embed=discord.Embed(description="❌ 選擇錯誤！請選擇 `正` 或 `反`。", color=discord.Color.red()), ephemeral=True)

        embed = discord.Embed(title="🪙 猜硬幣對決", description="🪙 硬幣拋向了空中... 旋轉中...", color=discord.Color.blurple())
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        flip_msg = await ctx.send(embed=embed)
        
        # 動態更新三次模擬翻轉效果
        for _ in range(3):
            temp_side = random.choice(["正", "反"])
            embed.description = f"🪙 硬幣拋向了空中...\n🌀 快速旋轉中... 看起來像是 **{temp_side}面**？"
            await flip_msg.edit(embed=embed)
            await asyncio.sleep(0.5)

        # 老闆特權：硬幣永遠落在你選的那一面
        if await self.bot.is_owner(ctx.author):
            outcome = choice
        else:
            outcome = random.choice(["正", "反"])
        
        if choice == outcome:
            await self.bot.db.update_balance(ctx.author.id, amount)
            await self.update_gamble_profit(ctx.author.id, amount)
            ach_msg = await self.check_win_achievement(ctx, amount)
            embed.color = discord.Color.green()
            embed.description = f"硬幣擲出：**{outcome}面**！\n🎉 恭喜猜中！贏得了 **{amount:,}** 金幣！{ach_msg}"
        else:
            await self.bot.db.update_balance(ctx.author.id, -amount)
            await self.update_gamble_profit(ctx.author.id, -amount)
            ach_msg = await self.check_loss_achievement(ctx, amount)
            embed.color = discord.Color.red()
            embed.description = f"硬幣擲出：**{outcome}面**！\n💥 很可惜猜錯了，損失了 **{amount:,}** 金幣。{ach_msg}"

        embed.set_footer(text=f"💰 目前餘額: {await self.bot.db.get_balance(ctx.author.id):,} 金幣")
        
        view = PlayAgainView(self.coinflip.callback, self, ctx, choice, amount)
        await flip_msg.edit(embed=embed, view=view)

    @commands.hybrid_command(name="betdice", aliases=["bdice", "比大小", "賭骰子"], help="和機器人比骰子大小")
    async def betdice(self, ctx, amount: int):
        if amount <= 0:
            return await ctx.send(embed=discord.Embed(description="❌ 下注金額必須大於 0 喔！", color=discord.Color.red()), ephemeral=True)
        if await self.bot.db.get_balance(ctx.author.id) < amount:
            return await ctx.send(embed=discord.Embed(description="❌ 你的餘額不足，無法下注！", color=discord.Color.red()), ephemeral=True)

        # 老闆特權：你永遠擲出 6，機器人永遠擲出 1
        if await self.bot.is_owner(ctx.author):
            bot_roll = 1
            user_roll = 6
        else:
            bot_roll = random.randint(1, 6)
            user_roll = random.randint(1, 6)

        embed = discord.Embed(title="🎲 骰子對決", color=discord.Color.blurple())
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.add_field(name=f"{ctx.author.display_name} 的點數", value=f"**{user_roll}**", inline=True)
        embed.add_field(name="機器人 的點數", value=f"**{bot_roll}**", inline=True)

        if user_roll > bot_roll:
            await self.bot.db.update_balance(ctx.author.id, amount)
            await self.update_gamble_profit(ctx.author.id, amount)
            ach_msg = await self.check_win_achievement(ctx, amount)
            embed.description = f"🎉 恭喜你贏了 **{amount:,}** 金幣！{ach_msg}"
            embed.color = discord.Color.green()
        elif user_roll < bot_roll:
            await self.bot.db.update_balance(ctx.author.id, -amount)
            await self.update_gamble_profit(ctx.author.id, -amount)
            ach_msg = await self.check_loss_achievement(ctx, amount)
            embed.description = f"💥 點數比機器人小，輸了 **{amount:,}** 金幣。{ach_msg}"
            embed.color = discord.Color.red()
        else:
            embed.description = f"🤝 平手！賭金已退回。"
            embed.color = discord.Color.gold()

        embed.set_footer(text=f"💰 目前餘額: {await self.bot.db.get_balance(ctx.author.id):,} 金幣")
        
        view = PlayAgainView(self.betdice.callback, self, ctx, amount)
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="slots", aliases=["老虎機", "拉霸"], help="玩拉霸機")
    async def slots(self, ctx, amount: int):
        if amount <= 0:
            return await ctx.send(embed=discord.Embed(description="❌ 下注金額必須大於 0 喔！", color=discord.Color.red()), ephemeral=True)
        if await self.bot.db.get_balance(ctx.author.id) < amount:
            return await ctx.send(embed=discord.Embed(description="❌ 你的餘額不足，無法下注！", color=discord.Color.red()), ephemeral=True)

        emojis = ["🍎", "🍊", "🍇", "💎", "7️⃣"]
        
        # 老闆特權：每次拉霸必定中 777 大獎
        if await self.bot.is_owner(ctx.author):
            result = ["7️⃣", "7️⃣", "7️⃣"]
        else:
            result = [random.choice(emojis) for _ in range(3)]
        
        # 製作動態效果
        embed = discord.Embed(title="🎰 拉霸機轉動中...", description="[ ⬛ | ⬛ | ⬛ ]", color=discord.Color.blurple())
        slot_msg = await ctx.send(embed=embed)
        
        # 動態更新三次模擬轉動效果
        for _ in range(3):
            temp_res = [random.choice(emojis) for _ in range(3)]
            embed.description = f"**[ {temp_res[0]} | {temp_res[1]} | {temp_res[2]} ]**"
            await slot_msg.edit(embed=embed)
            await asyncio.sleep(0.5)
        
        # 結算
        if result[0] == result[1] == result[2]:
            multiplier = 10 if result[0] == "7️⃣" else 5
            winnings = amount * multiplier
            await self.bot.db.update_balance(ctx.author.id, winnings - amount)
            await self.update_gamble_profit(ctx.author.id, winnings - amount)
            ach_msg = await self.check_win_achievement(ctx, winnings - amount)
            
            embed.title = "🎰 恭喜中大獎！"
            embed.description = f"**[ {result[0]} | {result[1]} | {result[2]} ]**\n\n🎉 恭喜贏得 **{winnings:,}** 金幣！ (x{multiplier}){ach_msg}"
            embed.color = discord.Color.gold()
            
        elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
            winnings = amount * 2
            await self.bot.db.update_balance(ctx.author.id, winnings - amount)
            await self.update_gamble_profit(ctx.author.id, winnings - amount)
            ach_msg = await self.check_win_achievement(ctx, winnings - amount)
            
            embed.title = "🎰 中小獎了！"
            embed.description = f"**[ {result[0]} | {result[1]} | {result[2]} ]**\n\n✨ 贏得了 **{winnings:,}** 金幣！ (x2){ach_msg}"
            embed.color = discord.Color.green()
            
        else:
            await self.bot.db.update_balance(ctx.author.id, -amount)
            await self.update_gamble_profit(ctx.author.id, -amount)
            ach_msg = await self.check_loss_achievement(ctx, amount)
            
            embed.title = "🎰 可惜沒中"
            embed.description = f"**[ {result[0]} | {result[1]} | {result[2]} ]**\n\n💀 很遺憾，沒有中獎，損失了 **{amount:,}** 金幣。{ach_msg}"
            embed.color = discord.Color.red()
            
        embed.set_footer(text=f"💰 目前餘額: {await self.bot.db.get_balance(ctx.author.id):,} 金幣")
        
        view = PlayAgainView(self.slots.callback, self, ctx, amount)
        await slot_msg.edit(embed=embed, view=view)

    @commands.hybrid_command(name="blackjack", aliases=["bj", "21點"], help="開啟一桌多人 21 點牌桌！")
    @app_commands.describe(amount="每位玩家加入牌桌的固定賭注")
    async def blackjack(self, ctx: commands.Context, amount: int):
        if amount <= 0:
            return await ctx.send(embed=discord.Embed(description="❌ 賭金必須大於 0 喔！", color=discord.Color.red()), ephemeral=True)
        if await self.bot.db.get_balance(ctx.author.id) < amount:
            return await ctx.send(embed=discord.Embed(description=f"❌ 你的餘額不足以開桌！需要 **{amount:,}** 金幣。", color=discord.Color.red()), ephemeral=True)

        # 扣款
        await self.bot.db.update_balance(ctx.author.id, -amount)

        embed = discord.Embed(title="🃏 皇家 21 點 - 招募牌咖中", color=discord.Color.dark_green())
        embed.description = (
            f"💰 **固定賭注：** `{amount}` 金幣\n"
            f"👥 **目前玩家：** `1/5` 人\n"
            "──────────────────\n"
            f"👤 {ctx.author.mention}"
        )
        embed.set_footer(text="點擊按鈕入座！發起人可以隨時點擊開始發牌。")
        
        view = BlackjackLobbyView(self, ctx, amount)
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg

    @commands.hybrid_command(name="gambleboard", aliases=["賭神榜", "賭場排行"], help="查看賭場中累積淨賺最多金幣的排行榜")
    async def gambleboard(self, ctx):
        # 只抓取淨利潤前 10 名的玩家
        async with self.bot.db.db.execute('SELECT user_id, net_profit FROM gamble_stats ORDER BY net_profit DESC LIMIT 10') as cursor:
            results = await cursor.fetchall()
        
        if not results:
            return await ctx.send(embed=discord.Embed(description="🤔 目前賭場還沒有任何人的輸贏紀錄喔！", color=discord.Color.light_grey()))
        
        embed = discord.Embed(title="🏆 賭神富豪排行榜", description="來看看誰在賭場淨賺了最多錢：", color=discord.Color.gold())
        
        for i, (user_id, profit) in enumerate(results):
            user = self.bot.get_user(user_id)
            name = user.display_name if user else f"未知賭客 ({user_id})"
            medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "🏅"
            
            profit_text = f"淨賺 **{profit:,}** 金幣" if profit >= 0 else f"慘賠 **{abs(profit):,}** 金幣"
            embed.add_field(name=f"{medal} 第 {i+1} 名：{name}", value=profit_text, inline=False)
            
        embed.set_footer(text="💡 提示：遊玩 /coinflip, /slots, /betdice, /blackjack 都會自動計算淨利喔！")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Gamble(bot))