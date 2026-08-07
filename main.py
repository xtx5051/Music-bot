import discord
from discord.ext import commands
import yt_dlp
import asyncio
from datetime import timedelta

# إعدادات البوت
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# إعدادات yt-dlp
ydl_options = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'quiet': True,
    'no_warnings': True,
}

# Dictionary لتخزين قائمة التشغيل لكل سيرفر
playlists = {}

class MusicPlayer:
    def __init__(self, guild_id):
        self.guild_id = guild_id
        self.queue = []
        self.is_playing = False
        self.current_song = None
        self.voice_client = None
    
    def add_to_queue(self, song_url, title):
        self.queue.append({'url': song_url, 'title': title})
    
    def get_next_song(self):
        if self.queue:
            return self.queue.pop(0)
        return None

@bot.event
async def on_ready():
    print(f'✅ البوت شغال! {bot.user}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="🎵 الموسيقى"))

@bot.command(name='join')
async def join(ctx):
    """الأمر: !join - دخول الغرفة الصوتية"""
    if not ctx.author.voice:
        await ctx.send("❌ أنت لازم تكون في غرفة صوتية أولاً!")
        return
    
    channel = ctx.author.voice.channel
    voice_client = await channel.connect()
    
    # تهيئة قائمة التشغيل
    if ctx.guild.id not in playlists:
        playlists[ctx.guild.id] = MusicPlayer(ctx.guild.id)
    
    playlists[ctx.guild.id].voice_client = voice_client
    await ctx.send(f"✅ تم الدخول إلى الغرفة: **{channel.name}**")

@bot.command(name='leave')
async def leave(ctx):
    """الأمر: !leave - مغادرة الغرفة الصوتية"""
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 تم المغادرة!")
    else:
        await ctx.send("❌ البوت غير متصل بأي غرفة صوتية!")

@bot.command(name='play')
async def play(ctx, *, search):
    """الأمر: !play [اسم الأغنية أو الرابط]"""
    if not ctx.voice_client:
        await ctx.send("❌ البوت غير متصل! استخدم !join أولاً")
        return
    
    await ctx.send(f"🔍 جاري البحث عن: **{search}**...")
    
    try:
        with yt_dlp.YoutubeDL(ydl_options) as ydl:
            info = ydl.extract_info(f"ytsearch:{search}", download=False)
            video = info['entries'][0]
            url = video['url']
            title = video['title']
            duration = video.get('duration', 0)
            
            player = playlists[ctx.guild.id]
            player.add_to_queue(url, title)
            
            duration_str = str(timedelta(seconds=duration))
            await ctx.send(f"✅ تمت الإضافة إلى قائمة التشغيل:\n**{title}**\n⏱️ المدة: {duration_str}\n📋 عدد الأغاني المتبقية: {len(player.queue)}")
            
            # إذا لم يكن هناك أغنية تشغيل حالياً، ابدأ التشغيل
            if not ctx.voice_client.is_playing():
                await play_next(ctx)
    
    except Exception as e:
        await ctx.send(f"❌ حدث خطأ: {str(e)}")

async def play_next(ctx):
    """تشغيل الأغنية التالية"""
    player = playlists.get(ctx.guild.id)
    
    if not player or not player.queue:
        await ctx.send("✅ انتهت قائمة التشغيل!")
        return
    
    song = player.get_next_song()
    player.current_song = song
    
    try:
        audio_source = discord.FFmpegPCMAudio(song['url'], before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5")
        
        def after_playing(error):
            if error:
                print(f"خطأ في التشغيل: {error}")
            asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
        
        ctx.voice_client.play(audio_source, after=after_playing)
        await ctx.send(f"▶️ الآن يتم التشغيل: **{song['title']}**")
    
    except Exception as e:
        await ctx.send(f"❌ خطأ في التشغيل: {str(e)}")
        await play_next(ctx)

@bot.command(name='pause')
async def pause(ctx):
    """الأمر: !pause - إيقاف مؤقت"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ تم الإيقاف المؤقت")
    else:
        await ctx.send("❌ لا توجد أغنية قيد التشغيل!")

@bot.command(name='resume')
async def resume(ctx):
    """الأمر: !resume - استئناف التشغيل"""
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ تم استئناف التشغيل")
    else:
        await ctx.send("❌ لا توجد أغنية موقوفة!")

@bot.command(name='stop')
async def stop(ctx):
    """الأمر: !stop - إيقاف التشغيل"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        playlists[ctx.guild.id].queue = []
        playlists[ctx.guild.id].current_song = None
        await ctx.send("⏹️ تم إيقاف التشغيل وحذف قائمة الانتظار")
    else:
        await ctx.send("❌ لا توجد أغنية قيد التشغيل!")

@bot.command(name='queue')
async def queue(ctx):
    """الأمر: !queue - عرض قائمة التشغيل"""
    player = playlists.get(ctx.guild.id)
    
    if not player or not player.queue:
        await ctx.send("📭 قائمة التشغيل فارغة!")
        return
    
    embed = discord.Embed(title="📋 قائمة التشغيل", color=discord.Color.purple())
    
    if player.current_song:
        embed.add_field(name="▶️ الآن يتم التشغيل", value=player.current_song['title'], inline=False)
    
    for i, song in enumerate(player.queue[:10], 1):
        embed.add_field(name=f"{i}. الأغنية التالية", value=song['title'], inline=False)
    
    if len(player.queue) > 10:
        embed.add_field(name="...", value=f"و {len(player.queue) - 10} أغنية أخرى", inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='skip')
async def skip(ctx):
    """الأمر: !skip - تخطي الأغنية الحالية"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏭️ تم التخطي للأغنية التالية")
    else:
        await ctx.send("❌ لا توجد أغنية قيد التشغيل!")

@bot.command(name='help')
async def help_command(ctx):
    """الأمر: !help - عرض قائمة الأوامر"""
    embed = discord.Embed(title="🎵 أوامر بوت الموسيقى", color=discord.Color.gold())
    
    commands_info = [
        ("!join", "دخول الغرفة الصوتية"),
        ("!leave", "مغادرة الغرفة الصوتية"),
        ("!play [اسم/رابط]", "تشغيل أغنية"),
        ("!pause", "إيقاف مؤقت"),
        ("!resume", "استئناف التشغيل"),
        ("!stop", "إيقاف التشغيل"),
        ("!skip", "تخطي الأغنية"),
        ("!queue", "عرض قائمة التشغيل"),
        ("!help", "عرض هذه الرسالة"),
    ]
    
    for cmd, desc in commands_info:
        embed.add_field(name=cmd, value=desc, inline=False)
    
    embed.set_footer(text="استمتع بالموسيقى! 🎶")
    await ctx.send(embed=embed)

# تشغيل البوت
bot.run(MTUyODk1MTkyMDk3MzE4OTE3Mw.GfcmPp.K1EX-JXrmAtJwCTODGB6WF0ZX06nr_HkfUF4ck)
