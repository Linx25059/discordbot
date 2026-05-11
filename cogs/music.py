import discord
from discord.ext import commands
import asyncio
import yt_dlp

# 隱藏 yt-dlp 預設的報錯訊息
yt_dlp.utils.bug_reports_message = lambda: ''

# 設定 yt-dlp 解析參數
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

# 設定 FFmpeg 參數 (自動重連防止斷線)
ffmpeg_options = {
    'options': '-vn',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

# 🎵 音樂控制台 UI 面板
class MusicControlView(discord.ui.View):
    def __init__(self, cog, ctx):
        super().__init__(timeout=None)
        self.cog = cog
        self.ctx = ctx

    @discord.ui.button(label="⏯️ 暫停/播放", style=discord.ButtonStyle.primary)
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc:
            return await interaction.response.send_message("❌ 我現在不在語音頻道裡面喔！", ephemeral=True)
        
        if vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ 音樂已暫停。", ephemeral=True)
        elif vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ 繼續播放音樂。", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 現在沒有音樂在播放喔。", ephemeral=True)

    @discord.ui.button(label="⏭️ 下一首", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_playing():
            return await interaction.response.send_message("❌ 目前沒有下一首歌可以切換。", ephemeral=True)
        
        vc.stop() # 停止當前音樂會自動觸發 play_next
        await interaction.response.send_message("⏭️ 已切換到下一首歌！", ephemeral=True)

    @discord.ui.button(label="⏹️ 停止並離開", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc:
            return await interaction.response.send_message("❌ 我現在不在語音頻道裡面喔！", ephemeral=True)
        
        self.cog.queues[interaction.guild.id] = [] # 清空歌單
        vc.stop()
        await vc.disconnect()
        await interaction.response.send_message("⏹️ 音樂已停止，我先離開語音頻道囉！", ephemeral=True)

    @discord.ui.button(label="📜 待播清單", style=discord.ButtonStyle.success)
    async def show_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        queue = self.cog.queues.get(interaction.guild.id, [])
        if not queue:
            return await interaction.response.send_message("📜 目前的待播清單是空的喔！", ephemeral=True)
        
        q_list = "\n".join([f"**{i+1}.** {song['title']}" for i, song in enumerate(queue[:10])])
        if len(queue) > 10:
            q_list += f"\n...還有 {len(queue)-10} 首歌"
            
        embed = discord.Embed(title="📜 待播清單", description=q_list, color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}

    def play_next(self, ctx):
        if ctx.guild.id in self.queues and len(self.queues[ctx.guild.id]) > 0:
            song = self.queues[ctx.guild.id].pop(0)
            
            # 在背景任務中獲取音訊流，避免阻塞機器人
            async def _play_task():
                try:
                    # 獲取實際的播放串流網址
                    data = await self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(song['webpage_url'], download=False))
                    stream_url = data['url']
                    source = discord.FFmpegPCMAudio(stream_url, **ffmpeg_options)
                    
                    # 確保在主執行緒中安全地呼叫下一首歌，避免跨執行緒操作崩潰
                    def after_playing(error):
                        if error:
                            print(f"音樂播放結束時發生錯誤: {error}")
                        self.bot.loop.call_soon_threadsafe(self.play_next, ctx)
                        
                    ctx.voice_client.play(source, after=after_playing)
                    
                    # 發送簡潔的控制面板
                    embed = discord.Embed(title="🎶 現正播放", description=f"**[{song['title']}]({song['webpage_url']})**", color=discord.Color.blurple())
                    embed.set_footer(text=f"點歌者：{song['requester']}")
                    if song.get('thumbnail'):
                        embed.set_thumbnail(url=song['thumbnail'])
                    
                    view = MusicControlView(self, ctx)
                    await ctx.send(embed=embed, view=view)
                except Exception as e:
                    print(f"播放音樂時發生錯誤: {e}")
                    self.play_next(ctx) # 發生錯誤則跳下一首
            
            self.bot.loop.create_task(_play_task())

    @commands.hybrid_command(name="play", aliases=["p", "點歌"], help="播放 YouTube 音樂 (支援網址或關鍵字)")
    async def play(self, ctx, *, query: str):
        if not ctx.author.voice:
            return await ctx.send("❌ 你必須先加入一個語音頻道，我才能進去放音樂喔！", ephemeral=True)
        
        # 讓機器人加入語音頻道
        vc = ctx.voice_client
        if not vc:
            await ctx.author.voice.channel.connect()
            vc = ctx.voice_client
        elif vc.channel != ctx.author.voice.channel:
            await vc.move_to(ctx.author.voice.channel)

        await ctx.send(f"🔍 正在搜尋：`{query}`...", delete_after=2.0)

        # 解析音樂資訊
        try:
            data = await self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
            if 'entries' in data:
                data = data['entries'][0] # 如果是搜尋結果或清單，只取第一首
        except Exception as e:
            return await ctx.send(f"❌ 找不到相關的音樂，請確認一下關鍵字或網址是否正確。", ephemeral=True)

        song_info = {'webpage_url': data.get('webpage_url', data.get('url')), 'title': data.get('title'), 'thumbnail': data.get('thumbnail'), 'requester': ctx.author.display_name}

        if ctx.guild.id not in self.queues:
            self.queues[ctx.guild.id] = []
        self.queues[ctx.guild.id].append(song_info)

        if not vc.is_playing() and not vc.is_paused():
            self.play_next(ctx)
        else:
            await ctx.send(embed=discord.Embed(title="📝 已加入待播清單", description=f"**[{song_info['title']}]({song_info['webpage_url']})**", color=discord.Color.green()))

async def setup(bot):
    await bot.add_cog(Music(bot))