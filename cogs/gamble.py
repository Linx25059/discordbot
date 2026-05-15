import discord
from discord import app_commands
from discord.ext import commands, tasks
import random
import asyncio
import aiosqlite
from typing import Optional
import datetime
import zoneinfo
import math

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
    
    if card in card_emojis:
        return card_emojis[card]
        
    suit = card[0]
    rank = card[1:]
    return f"` {suit} {rank:<2} `" # 使用 inline code block 讓寬度固定，看起來更像實體牌

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
        try:
            await interaction.response.edit_message(view=self.original_view)
        except Exception:
            await interaction.response.defer()
            
        await interaction.followup.send(f"✅ 已用新賭注 **{amount:,}** 金幣重新開始一局！", ephemeral=True)
        
        # 準備新參數
        new_args = list(self.original_view.args)
        new_args[-1] = amount
        
        try:
            # 解決斜線指令過期問題：將 interaction 設為 None，強制使用不受時效限制的頻道發送
            self.original_view.ctx.interaction = None
            await self.original_view.command_coro(self.original_view.cog, self.original_view.ctx, *new_args, **self.original_view.kwargs)
        except Exception as e:
            from cogs.bug_report import BugReportPanelView
            embed = discord.Embed(title="🚨 重新下注發生錯誤", description=f"```py\n{e}\n```", color=discord.Color.red())
            await interaction.followup.send(embed=embed, view=BugReportPanelView(), ephemeral=True)

class BlackjackRebetModal(discord.ui.Modal, title='💸 重新下注開桌'):
    new_amount_input = discord.ui.TextInput(
        label='新的房主賭注',
        placeholder='請輸入你要開桌的初始賭注金額',
        required=True,
        style=discord.TextStyle.short
    )

    def __init__(self, original_view: "BlackjackEndView"):
        super().__init__(timeout=180)
        self.original_view = original_view
        self.cog = original_view.cog
        self.host = original_view.host

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
            
        try:
            await interaction.response.edit_message(view=self.original_view)
        except Exception:
            await interaction.response.defer()
            
        await interaction.followup.send(f"✅ 已用新賭注 **{amount:,}** 金幣重新開桌！", ephemeral=True)
        
        try:
            # 徹底脫離原先的 ctx，直接透過 channel 發送全新的一局，避開 interaction 超時限制
            await self.cog.start_blackjack_lobby(self.original_view.channel, self.host, amount)
        except Exception as e:
            from cogs.bug_report import BugReportPanelView
            embed = discord.Embed(title="🚨 重新開桌發生錯誤", description=f"```py\n{e}\n```", color=discord.Color.red())
            await interaction.followup.send(embed=embed, view=BugReportPanelView(), ephemeral=True)

class BlackjackEndView(discord.ui.View):
    """21點：遊戲結束後的結算面板 (解決原本附加在停止 View 上的失效 Bug)"""
    def __init__(self, cog, host, amount, channel):
        super().__init__(timeout=120)
        self.cog = cog
        self.host = host
        self.amount = amount
        self.channel = channel

    @discord.ui.button(label="🔄 再開一桌", style=discord.ButtonStyle.success)
    async def play_again_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host.id:
            return await interaction.response.send_message("❌ 只有原房主可以重新開桌喔！", ephemeral=True)
        
        bal = await self.cog.bot.db.get_balance(self.host.id)
        if bal < self.amount:
            return await interaction.response.send_message(f"❌ 你的餘額不足以用原本的金額 ({self.amount:,}) 再開一桌！", ephemeral=True)
        
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        
        try:
            await self.cog.start_blackjack_lobby(self.channel, self.host, self.amount)
        except Exception as e:
            from cogs.bug_report import BugReportPanelView
            embed = discord.Embed(title="🚨 再玩一局發生錯誤", description=f"```py\n{e}\n```", color=discord.Color.red())
            await interaction.followup.send(embed=embed, view=BugReportPanelView(), ephemeral=True)

    @discord.ui.button(label="💸 重新下注", style=discord.ButtonStyle.secondary)
    async def rebet_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host.id:
            return await interaction.response.send_message("❌ 只有原房主可以重新開桌喔！", ephemeral=True)
        
        await interaction.response.send_modal(BlackjackRebetModal(self))

# --- 21點 UI 面板 ---
class BlackjackPlayView(discord.ui.View):
    """21點：遊玩與操作階段"""
    def __init__(self, cog, participants, dealer_hand, deck, host, amount):
        super().__init__(timeout=60) # 每個玩家有 60 秒可以考慮
        self.cog = cog
        self.players = list(participants.values())
        self.dealer_hand = dealer_hand
        self.deck = deck
        self.current_idx = 0
        self.host = host
        self.amount = amount
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
            dealer_cards = "  ".join([get_card_display(c) for c in self.dealer_hand])
            dealer_text = f"**點數：** `{dealer_val}`\n**手牌：** {dealer_cards}"
        else:
            dealer_text = f"**點數：** ` ? `\n**手牌：** {get_card_display(self.dealer_hand[0])}  ` 🎴 `"
            
        embed.add_field(name="🤵 莊家 (Dealer)", value=dealer_text, inline=False)
        embed.add_field(name="━" * 15, value="\u200b", inline=False) # 視覺分隔線
        
        # 玩家區塊
        for i, p in enumerate(self.players):
            val = calculate_hand(p['hand'])
            
            # 目前動作的玩家高亮顯示
            is_current = (i == self.current_idx and not show_dealer)
            status_icon = "🟢" if is_current else "👤"
            hand_label = f" (分牌 {p['split_idx']})" if 'split_idx' in p else ""
            
            hand_str = "  ".join([get_card_display(c) for c in p['hand']])
            
            if p['status'] == 'bust':
                status_str = "💥 **爆牌 (Bust)**"
            elif p['status'] == 'surrender':
                status_str = "🏳️ **投降 (Surrender)**"
            elif val == 21 and len(p['hand']) == 2:
                status_str = "🌟 **黑傑克 (Blackjack!)**"
            elif p['status'] == 'stand':
                status_str = f"🛑 **停牌 ({val}點)**"
            else:
                status_str = f"🎲 **{val}點**"
                
            player_info = f"**狀態：** {status_str}\n**手牌：** {hand_str}\n**賭注：** `{p['bet']}`"
            embed.add_field(name=f"{status_icon} {p['user'].display_name}{hand_label}", value=player_info, inline=False)
            
        if not show_dealer:
            p = self.get_current_player()
            if p:
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
        
        channel = interaction.channel if interaction else (self.message.channel if self.message else None)
        end_view = BlackjackEndView(self.cog, self.host, self.amount, channel) if self.host and channel else None

        if interaction:
            try:
                await interaction.message.edit(embed=embed, view=end_view)
            except: pass
        elif self.message:
            await self.message.edit(embed=embed, view=end_view)

class BlackjackJoinModal(discord.ui.Modal, title='💰 加入 21 點牌桌'):
    bet_amount_input = discord.ui.TextInput(
        label='請輸入你的下注金額',
        placeholder='例如：1000',
        required=True,
        style=discord.TextStyle.short
    )

    def __init__(self, lobby_view: "BlackjackLobbyView"):
        super().__init__(timeout=120)
        self.lobby_view = lobby_view
        self.cog = lobby_view.cog

    async def on_submit(self, interaction: discord.Interaction):
        try:
            bet_amount = int(self.bet_amount_input.value)
            if bet_amount <= 0:
                return await interaction.response.send_message("❌ 金額必須大於 0！", ephemeral=True)
        except ValueError:
            return await interaction.response.send_message("❌ 請輸入有效的數字金額！", ephemeral=True)

        if interaction.user.id in self.lobby_view.participants:
            return await interaction.response.send_message("❌ 你已經在牌桌上了喔！", ephemeral=True)
            
        if len(self.lobby_view.participants) >= 5:
            return await interaction.response.send_message("❌ 滿桌了！下局請早。", ephemeral=True)

        bal = await self.cog.bot.db.get_balance(interaction.user.id)
        if bal < bet_amount:
            return await interaction.response.send_message(f"❌ 你的餘額不足以加入牌桌喔！(需要 **{bet_amount:,}** 金幣)", ephemeral=True)

        await self.cog.bot.db.update_balance(interaction.user.id, -bet_amount)
        self.lobby_view.participants[interaction.user.id] = {'user': interaction.user, 'hand': [], 'status': 'playing', 'bet': bet_amount}
        
        embed = self.lobby_view.message.embeds[0]
        players_text = "\n".join([f"👤 {p['user'].mention} - 賭注: `{p['bet']:,}`" for p in self.lobby_view.participants.values()])
        embed.description = (
            "💰 **自訂賭注：** 每位玩家可自行決定下注金額\n"
            f"👥 **目前玩家：** `{len(self.lobby_view.participants)}/5` 人\n"
            "──────────────────\n"
            + players_text
        )
        await interaction.response.edit_message(embed=embed, view=self.lobby_view)

class BlackjackLobbyView(discord.ui.View):
    """21點：大廳招募階段"""
    def __init__(self, cog, channel, host, bet_amount):
        super().__init__(timeout=45) # 給大家 45 秒可以坐下
        self.cog = cog
        self.channel = channel
        self.host = host
        self.host_bet_amount = bet_amount
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
        
        await interaction.response.send_modal(BlackjackJoinModal(self))

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
            
        play_view = BlackjackPlayView(self.cog, self.participants, dealer_hand, deck, self.host, self.host_bet_amount)
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
        
        try:
            self.ctx.interaction = None
            await self.command_coro(self.cog, self.ctx, *self.args, **self.kwargs)
        except Exception as e:
            from cogs.bug_report import BugReportPanelView
            embed = discord.Embed(title="🚨 再玩一次發生錯誤", description=f"```py\n{e}\n```", color=discord.Color.red())
            await interaction.followup.send(embed=embed, view=BugReportPanelView(), ephemeral=True)

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
        
        try:
            self.ctx.interaction = None
            await self.command_coro(self.cog, self.ctx, *new_args, **self.kwargs)
        except Exception as e:
            from cogs.bug_report import BugReportPanelView
            embed = discord.Embed(title="🚨 倍壓下注發生錯誤", description=f"```py\n{e}\n```", color=discord.Color.red())
            await interaction.followup.send(embed=embed, view=BugReportPanelView(), ephemeral=True)

class TreasureBetModal(discord.ui.Modal, title='💸 跟注或加注'):
    bet_input = discord.ui.TextInput(
        label='你的下注金額 (跟注或加注)',
        required=True,
        style=discord.TextStyle.short
    )

    def __init__(self, view, tile_idx):
        super().__init__(timeout=120)
        self.game_view = view
        self.tile_idx = tile_idx
        self.bet_input.placeholder = f"最低需下注 {view.min_bet:,} 金幣"

    async def on_submit(self, interaction: discord.Interaction):
        if self.game_view.is_finished:
            return await interaction.response.send_message("❌ 遊戲已經結束囉！", ephemeral=True)
        if self.game_view.buttons[self.tile_idx].disabled:
            return await interaction.response.send_message("❌ 這個格子剛剛已經被別人搶先翻開了！", ephemeral=True)

        try:
            bet = int(self.bet_input.value)
            if bet < self.game_view.min_bet:
                return await interaction.response.send_message(f"❌ 下注金額不能低於目前的最低跟注 ({self.game_view.min_bet:,} 金幣)！", ephemeral=True)
        except ValueError:
            return await interaction.response.send_message("❌ 請輸入有效的數字金額！", ephemeral=True)

        cog = self.game_view.cog
        bal = await cog.bot.db.get_balance(interaction.user.id)
        if bal < bet:
            return await interaction.response.send_message(f"❌ 你的餘額不足！(需要 **{bet:,}** 金幣)", ephemeral=True)

        # 扣款與更新獎池
        await cog.bot.db.update_balance(interaction.user.id, -bet)
        self.game_view.pot += bet
        self.game_view.min_bet = bet

        is_owner = await cog.bot.is_owner(interaction.user)
        if is_owner and self.tile_idx != self.game_view.winning_idx:
            # 老闆特權：如果點錯了，偷偷把隱藏寶石移到你點的這格！必定中獎！
            self.game_view.winning_idx = self.tile_idx

        btn = self.game_view.buttons[self.tile_idx]
        btn.disabled = True

        if self.tile_idx == self.game_view.winning_idx:
            self.game_view.is_finished = True
            btn.emoji = "💎"
            btn.style = discord.ButtonStyle.success

            # 發獎金
            await cog.bot.db.update_balance(interaction.user.id, self.game_view.pot)
            await cog.update_gamble_profit(interaction.user.id, self.game_view.pot - bet)
            
            self.game_view.history.insert(0, f"🎉 **{interaction.user.display_name}** 投入 `{bet:,}` 金幣並挖到了寶石！獨得 `{self.game_view.pot:,}` 金幣！")
            
            # 翻開所有未點開的格子
            for idx, b in enumerate(self.game_view.buttons):
                b.disabled = True
                if not b.emoji:
                    b.emoji = "💥" if idx != self.game_view.winning_idx else "💎"
            
            self.game_view.add_play_again_button()

            embed = self.game_view.build_embed(won=True, winner=interaction.user)
            await interaction.response.edit_message(embed=embed, view=self.game_view)
        else:
            # 踩到地雷
            btn.emoji = "💥"
            btn.style = discord.ButtonStyle.danger
            await cog.update_gamble_profit(interaction.user.id, -bet)
            self.game_view.history.insert(0, f"💥 **{interaction.user.display_name}** 下注 `{bet:,}` 金幣卻踩到了地雷！")
            
            embed = self.game_view.build_embed()
            await interaction.response.edit_message(embed=embed, view=self.game_view)

class TreasureHuntView(discord.ui.View):
    def __init__(self, cog, ctx, seed_amount):
        super().__init__(timeout=600) # 給予 10 分鐘完賽
        self.cog = cog
        self.ctx = ctx
        self.seed_amount = seed_amount
        self.pot = seed_amount
        self.min_bet = seed_amount
        self.is_finished = False
        self.message = None
        
        self.winning_idx = random.randint(0, 19)
        self.history = [f"🟢 **{ctx.author.display_name}** 注入了初始獎池 `{seed_amount:,}` 金幣開局！"]
        
        self.buttons = []
        for i in range(20):
            btn = discord.ui.Button(label="\u200b", style=discord.ButtonStyle.secondary, row=i//5, custom_id=f"tile_{i}")
            btn.callback = self.make_callback(i)
            self.buttons.append(btn)
            self.add_item(btn)

    def make_callback(self, i):
        async def callback(interaction: discord.Interaction):
            if self.is_finished:
                if not interaction.response.is_done(): await interaction.response.defer()
                return
            await interaction.response.send_modal(TreasureBetModal(self, i))
        return callback

    def add_play_again_button(self):
        btn = discord.ui.Button(label="🔄 原房主再開一局", style=discord.ButtonStyle.primary, row=4)
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.ctx.author.id:
                return await interaction.response.send_message("❌ 只有原房主可以重新開局喔！", ephemeral=True)
            
            bal = await self.cog.bot.db.get_balance(self.ctx.author.id)
            if bal < self.seed_amount:
                return await interaction.response.send_message(f"❌ 你的餘額不足以用相同金額再開一局！需要 **{self.seed_amount:,}** 金幣", ephemeral=True)
            
            for child in self.children: child.disabled = True
            await interaction.response.edit_message(view=self)
            self.ctx.interaction = None
            await self.cog.minesweeper.callback(self.cog, self.ctx, self.seed_amount)
        btn.callback = callback
        self.add_item(btn)

    def build_embed(self, won=False, winner=None):
        embed = discord.Embed(title="💎 奪寶大逃殺 (多人累積獎池)", color=discord.Color.gold() if won else discord.Color.blurple())
        
        if won:
            embed.description = f"🎉 恭喜 {winner.mention} 找出了隱藏的寶石！\n獨得總獎池 **{self.pot:,}** 金幣！"
        else:
            embed.description = "🎯 **規則：** 找出 20 格中唯一隱藏的寶石 💎！\n💥 若踩到地雷，你的賭金將會注入總獎池中！\n💰 下一位玩家可選擇 **跟注** 或 **加注** 繼續挑戰！"

        embed.add_field(name="💰 目前總獎池", value=f"**{self.pot:,}** 金幣", inline=True)
        embed.add_field(name="📈 最低跟注金額", value=f"**{self.min_bet:,}** 金幣", inline=True)
        
        history_text = "\n".join(self.history[:5])
        embed.add_field(name="📜 最新動態", value=history_text, inline=False)
        
        embed.set_footer(text="閒置 10 分鐘未破關，總獎池將全數充公！")
        return embed

    async def on_timeout(self):
        if not self.is_finished:
            self.is_finished = True
            for child in self.children: child.disabled = True
            if self.message:
                embed = self.message.embeds[0]
                embed.color = discord.Color.dark_grey()
                embed.description = "⏳ **遊戲已逾時！** 10 分鐘內無人找出寶石，總獎池已全數充公！"
                try: await self.message.edit(embed=embed, view=self)
                except: pass

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

    @commands.hybrid_command(name="slots", aliases=["老虎機", "拉霸"], help="玩拉霸機 (可自訂賠率倍數)")
    @app_commands.describe(amount="下注金額", multiplier="自訂額外賠率倍數 (預設 1.0 倍，倍率越高越難中)")
    async def slots(self, ctx, amount: int, *, multiplier: float = 1.0):
        if amount <= 0:
            return await ctx.send(embed=discord.Embed(description="❌ 下注金額必須大於 0 喔！", color=discord.Color.red()), ephemeral=True)
        if multiplier < 1.0 or multiplier > 100.0:
            return await ctx.send(embed=discord.Embed(description="❌ 倍率必須設定在 1.0 到 100.0 倍之間！", color=discord.Color.red()), ephemeral=True)
        if await self.bot.db.get_balance(ctx.author.id) < amount:
            return await ctx.send(embed=discord.Embed(description="❌ 你的餘額不足，無法下注！", color=discord.Color.red()), ephemeral=True)

        emojis = ["🍎", "🍊", "🍇", "💎", "7️⃣"]
        
        # 根據倍率調整勝率 (保持數學期望值一致)
        chance_777 = 0.8 / multiplier
        chance_3 = 3.2 / multiplier
        chance_2 = 48.0 / multiplier
        
        roll = random.uniform(0, 100)
        
        if await self.bot.is_owner(ctx.author):
            roll = 0.0
            
        if roll < chance_777:
            result = ["7️⃣", "7️⃣", "7️⃣"]
        elif roll < chance_777 + chance_3:
            e = random.choice(["🍎", "🍊", "🍇", "💎"])
            result = [e, e, e]
        elif roll < chance_777 + chance_3 + chance_2:
            e = random.choice(emojis)
            other = random.choice([x for x in emojis if x != e])
            result = [e, e, other]
            random.shuffle(result)
        else:
            result = random.sample(emojis, 3) # 隨機抽出 3 個不一樣的水果
        
        # 製作動態效果
        mult_text = f" (倍率: {multiplier:.1f}x)" if multiplier != 1.0 else ""
        embed = discord.Embed(title=f"🎰 拉霸機轉動中...{mult_text}", description="[ ⬛ | ⬛ | ⬛ ]", color=discord.Color.blurple())
        slot_msg = await ctx.send(embed=embed)
        
        # 動態更新三次模擬轉動效果
        for _ in range(3):
            temp_res = [random.choice(emojis) for _ in range(3)]
            embed.description = f"**[ {temp_res[0]} | {temp_res[1]} | {temp_res[2]} ]**"
            await slot_msg.edit(embed=embed)
            await asyncio.sleep(0.5)
        
        # 結算
        if result[0] == result[1] == result[2]:
            base_mult = 10 if result[0] == "7️⃣" else 5
            final_mult = base_mult * multiplier
            winnings = int(amount * final_mult)
            await self.bot.db.update_balance(ctx.author.id, winnings - amount)
            await self.update_gamble_profit(ctx.author.id, winnings - amount)
            ach_msg = await self.check_win_achievement(ctx, winnings - amount)
            
            embed.title = "🎰 恭喜中大獎！"
            embed.description = f"**[ {result[0]} | {result[1]} | {result[2]} ]**\n\n🎉 恭喜贏得 **{winnings:,}** 金幣！ (x{final_mult:g}){ach_msg}"
            embed.color = discord.Color.gold()
            
        elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
            final_mult = 2 * multiplier
            winnings = int(amount * final_mult)
            await self.bot.db.update_balance(ctx.author.id, winnings - amount)
            await self.update_gamble_profit(ctx.author.id, winnings - amount)
            ach_msg = await self.check_win_achievement(ctx, winnings - amount)
            
            embed.title = "🎰 中小獎了！"
            embed.description = f"**[ {result[0]} | {result[1]} | {result[2]} ]**\n\n✨ 贏得了 **{winnings:,}** 金幣！ (x{final_mult:g}){ach_msg}"
            embed.color = discord.Color.green()
            
        else:
            await self.bot.db.update_balance(ctx.author.id, -amount)
            await self.update_gamble_profit(ctx.author.id, -amount)
            ach_msg = await self.check_loss_achievement(ctx, amount)
            
            embed.title = "🎰 可惜沒中"
            embed.description = f"**[ {result[0]} | {result[1]} | {result[2]} ]**\n\n💀 很遺憾，沒有中獎，損失了 **{amount:,}** 金幣。{ach_msg}"
            embed.color = discord.Color.red()
            
        embed.set_footer(text=f"💰 目前餘額: {await self.bot.db.get_balance(ctx.author.id):,} 金幣")
        
        # 完美支援面板「再玩一次、雙倍下注」等功能，並記住使用者設定的倍率
        view = PlayAgainView(self.slots.callback, self, ctx, amount, multiplier=multiplier)
        await slot_msg.edit(embed=embed, view=view)

    @commands.hybrid_command(name="minesweeper", aliases=["highroll", "踩地雷", "高賠率", "mines", "尋寶", "treasure"], help="奪寶大逃殺！大家輪流跟注或加注，直到有人找出唯一的寶石獨得總獎池！")
    @app_commands.describe(amount="初始獎池底注 (最少需 10 金幣)")
    async def minesweeper(self, ctx: commands.Context, amount: int):
        if amount < 10:
            return await ctx.send(embed=discord.Embed(description="❌ 初始底注必須大於或等於 10 金幣喔！", color=discord.Color.red()), ephemeral=True)
        if await self.bot.db.get_balance(ctx.author.id) < amount:
            return await ctx.send(embed=discord.Embed(description="❌ 你的餘額不足以開啟牌局！", color=discord.Color.red()), ephemeral=True)

        await self.bot.db.update_balance(ctx.author.id, -amount)
        await self.update_gamble_profit(ctx.author.id, -amount)
        
        view = TreasureHuntView(self, ctx, amount)
        embed = view.build_embed()
        
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg

    async def start_blackjack_lobby(self, channel, host, amount):
        """獨立的多人 21 點牌桌發起器，完美避開斜線指令逾時限制"""
        await self.bot.db.update_balance(host.id, -amount)

        embed = discord.Embed(title="🃏 皇家 21 點 - 招募牌咖中", color=discord.Color.dark_green())
        embed.description = (
            "💰 **自訂賭注：** 每位玩家可自行決定下注金額\n"
            f"👥 **目前玩家：** `1/5` 人\n"
            "──────────────────\n"
            f"👤 {host.mention} - 賭注: `{amount:,}`"
        )
        embed.set_footer(text="點擊按鈕入座！發起人可以隨時點擊開始發牌。")
        
        view = BlackjackLobbyView(self, channel, host, amount)
        msg = await channel.send(embed=embed, view=view)
        view.message = msg

    @commands.hybrid_command(name="blackjack", aliases=["bj", "21點"], help="開啟一桌多人 21 點牌桌！支援各自獨立下注。")
    @app_commands.describe(amount="身為房主你的初始下注金額")
    async def blackjack(self, ctx: commands.Context, amount: int):
        if amount <= 0:
            return await ctx.send(embed=discord.Embed(description="❌ 賭金必須大於 0 喔！", color=discord.Color.red()), ephemeral=True)
        if await self.bot.db.get_balance(ctx.author.id) < amount:
            return await ctx.send(embed=discord.Embed(description=f"❌ 你的餘額不足以開桌！需要 **{amount:,}** 金幣。", color=discord.Color.red()), ephemeral=True)

        # 若為斜線指令，先回覆並關閉互動，後續使用一般訊息發送，打破 15 分鐘限制
        if ctx.interaction:
            await ctx.defer()
            await ctx.send("🃏 **牌桌準備中...**", ephemeral=True, delete_after=3.0)
            
        await self.start_blackjack_lobby(ctx.channel, ctx.author, amount)

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