import discord
from discord.ext import commands
import sqlite3

class AutoVoice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect('bot_database.db', timeout=10.0)
        self.c = self.conn.cursor()

        # 建立兩個資料表：
        # 1. auto_voice_generators: 存放「➕ 點我開房」這類負責生成新頻道的母頻道 ID
        # 2. auto_voice_temp: 存放機器人動態產生的「專屬包廂」ID (用來判斷何時該刪除)
        self.c.execute('''CREATE TABLE IF NOT EXISTS auto_voice_generators (channel_id INTEGER PRIMARY KEY)''')
        self.c.execute('''CREATE TABLE IF NOT EXISTS auto_voice_temp (channel_id INTEGER PRIMARY KEY)''')
        self.conn.commit()

    @commands.hybrid_command(name="setupvoice", aliases=["設定語音"], help="在當前類別建立一個「自動語音生成頻道」")
    @commands.has_permissions(manage_channels=True)
    async def setup_voice(self, ctx):
        category = ctx.channel.category
        
        # 在與輸入指令相同的類別 (Category) 中建立一個語音頻道
        new_channel = await ctx.guild.create_voice_channel(name="➕ 點我開房", category=category)
        
        # 將這個頻道的 ID 存入資料庫
        self.c.execute('INSERT OR IGNORE INTO auto_voice_generators (channel_id) VALUES (?)', (new_channel.id,))
        self.conn.commit()
        
        await ctx.send(f"✅ 成功！已建立 {new_channel.mention}。\n只要有人點進去，我就會自動幫他開一個專屬包廂，等人都離開後再自動刪除乾淨！")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # 狀況 1：使用者「離開」了某個頻道，我們要檢查是不是動態包廂空了，空了就刪掉
        if before.channel is not None:
            self.c.execute('SELECT channel_id FROM auto_voice_temp WHERE channel_id = ?', (before.channel.id,))
            if self.c.fetchone():
                # 如果該包廂裡面已經沒有半個人了
                if len(before.channel.members) == 0:
                    try:
                        await before.channel.delete(reason="自動化語音頻道：已無人在內")
                        self.c.execute('DELETE FROM auto_voice_temp WHERE channel_id = ?', (before.channel.id,))
                        self.conn.commit()
                    except Exception as e:
                        print(f"刪除動態頻道時發生錯誤: {e}")

        # 狀況 2：使用者「加入」了某個頻道，我們要檢查是不是踩到了生成器 (➕ 點我開房)
        if after.channel is not None:
            self.c.execute('SELECT channel_id FROM auto_voice_generators WHERE channel_id = ?', (after.channel.id,))
            if self.c.fetchone():
                try:
                    # 在母頻道所屬的類別底下，建立專屬包廂
                    new_channel = await member.guild.create_voice_channel(name=f"🎧 {member.display_name} 的包廂", category=after.channel.category)
                    
                    # 記錄到暫時頻道資料庫中
                    self.c.execute('INSERT INTO auto_voice_temp (channel_id) VALUES (?)', (new_channel.id,))
                    self.conn.commit()

                    # 把剛加入母頻道的人，立刻拉進專屬包廂
                    await member.move_to(new_channel)
                except Exception as e:
                    print(f"建立動態頻道時發生錯誤: {e}")

async def setup(bot):
    await bot.add_cog(AutoVoice(bot))