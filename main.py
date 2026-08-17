import discord
from discord.ext import commands
import yt_dlp
import asyncio
from datetime import timedelta
import os

# إعدادات البوت
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# إعدادات yt-dlp
ydl_options = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'noplaylist': True,
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'web']
        }
    },
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

@bot.event
async def on_voice_state_update(member, before, after):
    """إذا غادر الجميع الروم، يطلع البوت أيضاً"""
    if member.id == bot.user.id:
        return
    
    voice_client = discord.utils.get(bot.voice_clients, guild=member.guild)
    
    if not voice_client:
        return
    
    # التحقق من عدد الأعضاء المتبقيين في الروم (بدون عد البوت)
    members_in_channel = [m for m in voice_client.channel.members if not m.bot]
    
    # إذا لم يبقى أحد، البوت يطلع
    if len(members_in_channel) == 0:
        await voice_client.disconnect()
        if member.guild.id in playlists:
            playlists[member.guild.id].queue = []
            playlists[member.guild.id].current_song = None

@bot.command(name='join')
async def join(ctx):
    """الأمر: !join - دخول الغرفة الصوتية"""
    if not ctx.author.voice:
        await ctx.send("❌ خش الروم اول يا ثور")
        return
    
    channel = ctx.author.voice.channel
    
    # إذا كان البوت متصل بغرفة أخرى، اطلعه أولاً
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
    
    voice_client = await channel.connect()
    
    # تهيئة قائمة التشغيل
    if ctx.guild.id not in playlists:
        playlists[ctx.guild.id] = MusicPlayer(ctx.guild.id)
    
    playlists[ctx.guild.id].voice_client = voice_client
    await ctx.send(f"✅ خشيت: **{channel.name}**")

@bot.command(name='leave')
async def leave(ctx):
    """الأمر: !leave - مغادرة الغرفة الصوتية"""
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        if ctx.guild.id in playlists:
            playlists[ctx.guild.id].queue = []
            playlists[ctx.guild.id].current_song = None
        await ctx.send("👋 طلعت من الروم!")
    else:
        await ctx.send("❌ البوت غير متصل بأي غرفة صوتية!")

@bot.command(name='play')
async def play(ctx, *, search):
    """الأمر: !play [اسم الأغنية]"""
    if not ctx.voice_client:
        await ctx.send("❌ البوت غير متصل! استخدم !join أولاً")
        return
    
    await ctx.send(f"🔍 ثواني ابحث: **{search}**...")
    
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
        embed.add_field(name="▶️ بشغل حالياً", value=player.current_song['title'], inline=False)
    
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
        await ctx.send("⏭️ سكبت للأغنية التالية")
    else:
        await ctx.send("❌ لا توجد أغنية قيد التشغيل!")

# ==================== أوامر بدون علامة تعجب ====================

@bot.command(name='د')
async def join_shortcut(ctx):
    """اختصار: د - دخول الروم"""
    await join(ctx)

@bot.command(name='ش')
async def play_shortcut(ctx, *, search):
    """اختصار: ش [اسم الأغنية] - تشغيل أغنية"""
    await play(ctx, search=search)

@bot.command(name='و')
async def stop_shortcut(ctx):
    """اختصار: و - إيقاف التشغيل"""
    await stop(ctx)

@bot.command(name='س')
async def skip_shortcut(ctx):
    """اختصار: س - تخطي الأغنية"""
    await skip(ctx)

@bot.command(name='ع')
async def queue_shortcut(ctx):
    """اختصار: ع - عرض قائمة التشغيل"""
    await queue(ctx)

@bot.command(name='ب')
async def pause_shortcut(ctx):
    """اختصار: ب - إيقاف مؤقت"""
    await pause(ctx)

@bot.command(name='ت')
async def resume_shortcut(ctx):
    """اختصار: ت - استئناف التشغيل"""
    await resume(ctx)

@bot.command(name='خ')
async def leave_shortcut(ctx):
    """اختصار: خ - طلع من الروم"""
    await leave(ctx)

# ==================== أوامر المساعدة ====================

@bot.command(name='help')
@bot.command(name='h')
@bot.command(name='م')
async def help_command(ctx):
    """الأمر: !help أو !h أو !م - عرض قائمة الأوامر"""
    embed = discord.Embed(title="🎵 أوامر بوت الموسيقى", color=discord.Color.gold())
    
    commands_info = [
        ("!join أو !د", "دخول الغرفة الصوتية"),
        ("!leave أو !خ", "مغادرة الغرفة الصوتية"),
        ("!play [اسم/رابط] أو !ش", "تشغيل أغنية"),
        ("!pause أو !ب", "إيقاف مؤقت"),
        ("!resume أو !ت", "استئناف التشغيل"),
        ("!stop أو !و", "إيقاف التشغيل"),
        ("!skip أو !س", "تخطي الأغنية"),
        ("!queue أو !ع", "عرض قائمة التشغيل"),
        ("!help أو !h أو !م", "عرض هذه الرسالة"),
    ]
    
    for cmd, desc in commands_info:
        embed.add_field(name=cmd, value=desc, inline=False)
    
    embed.set_footer(text="استمتع بالموسيقى! 🎶")
    await ctx.send(embed=embed)

# تشغيل البوت
bot.run(os.getenv("DISCORD_TOKEN"))
