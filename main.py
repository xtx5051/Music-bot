import os
import re
import asyncio
import discord
from discord.ext import commands
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# ==========================================
# 1. قراءة التوكنات والمفاتيح من Railway Variables
# ==========================================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")

# إعداد سبوتيفاي
sp = None
if SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET:
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET
    ))

# إعدادات البوت بدون بادئة رمادية (أوامر مباشرة مثل: ش ، س ، ي)
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="", intents=intents)

# خيارات yt-dlp للتعامل مع الصوت وساوند كلاود ويوتيوب
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

# خيارات FFmpeg لإعادة الاتصال التلقائي بسلاسة
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# نظام قائمة الانتظار (Queue) لكل سيرفر
song_queues = {}

def get_queue(guild_id):
    if guild_id not in song_queues:
        song_queues[guild_id] = []
    return song_queues[guild_id]

# دالة استخراج بيانات الأغنية من رابط سبوتيفاي
def get_spotify_query(url):
    if not sp:
        return None
    try:
        track_id = re.search(r'track/([a-zA-Z0-9]+)', url).group(1)
        track_info = sp.track(track_id)
        song_name = track_info['name']
        artist_name = track_info['artists'][0]['name']
        return f"{song_name} {artist_name}"
    except Exception as e:
        print(f"Spotify Parse Error: {e}")
        return None

# دالة تشغيل الأغنية التالية تلقائياً
def play_next(ctx):
    queue = get_queue(ctx.guild.id)
    if len(queue) > 0:
        next_song = queue.pop(0)
        source = discord.FFmpegPCMAudio(next_song['url'], **FFMPEG_OPTIONS)
        ctx.voice_client.play(source, after=lambda e: play_next(ctx))
        asyncio.run_coroutine_threadsafe(
            ctx.send(f"🎶 جاري تشغيل: **{next_song['title']}**"),
            bot.loop
        )
    else:
        asyncio.run_coroutine_threadsafe(
            ctx.send("✅ انتهت قائمة الانتظار."),
            bot.loop
        )

# ==========================================
# 2. أحداث وأوامر البوت
# ==========================================

@bot.event
async def on_ready():
    print(f"✅ تم تسجيل الدخول بنجاح باسم البوت: {bot.user.name}")

# أمر التشغيل: ش أو شغل أو play
@bot.command(aliases=['شغل', 'play'])
async def ش(ctx, *, query: str = None):
    if not query:
        await ctx.send("يرجى كتابة اسم الأغنية أو الرابط بعد الأمر (مثال: `ش رابط_ساوند_كلاود` أو `ش اسم_الأغنية`).")
        return

    if not ctx.author.voice:
        await ctx.send("عفواً، يجب أن تكون في روم صوتي أولاً!")
        return

    voice_channel = ctx.author.voice.channel

    # الاتصال بالروم الصوتي
    if ctx.voice_client is None:
        await voice_channel.connect()
    elif ctx.voice_client.channel != voice_channel:
        await ctx.voice_client.move_to(voice_channel)

    async with ctx.typing():
        search_target = query

        # 1. إذا كان الرابط من سبوتيفاي
        if "open.spotify.com/track" in query:
            song_title = get_spotify_query(query)
            if song_title:
                search_target = f"ytsearch:{song_title}"
                await ctx.send(f"🔍 تم التعرف على رابط سبوتيفاي: **{song_title}**")
            else:
                await ctx.send("تعذر جلب البيانات من سبوتيفاي، تأكد من إضافة `SPOTIPY_CLIENT_ID` و `SPOTIPY_CLIENT_SECRET` في Variables.")
                return

        # 2. إذا كان الرابط من ساوند كلاود (SoundCloud) أو يوتيوب مباشر
        elif query.startswith("http://") or query.startswith("https://"):
            search_target = query  # yt-dlp يدعم روابط ساوند كلاود مباشرة

        # 3. إذا كان نص بحث عادي
        else:
            search_target = f"ytsearch:{query}"

        # جلب الصوت واستخراجه عبر yt-dlp
        loop = asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(search_target, download=False))
            if 'entries' in data:
                data = data['entries'][0]

            song_data = {
                'url': data['url'],
                'title': data.get('title', 'مقطع صوتي')
            }

            queue = get_queue(ctx.guild.id)

            if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
                queue.append(song_data)
                await ctx.send(f"📥 تم إضافة **{song_data['title']}** إلى قائمة الانتظار (ترتيبها: #{len(queue)})")
            else:
                source = discord.FFmpegPCMAudio(song_data['url'], **FFMPEG_OPTIONS)
                ctx.voice_client.play(source, after=lambda e: play_next(ctx))
                await ctx.send(f"🎶 جاري تشغيل: **{song_data['title']}**")

        except Exception as e:
            await ctx.send("حدث خطأ أثناء محاولة تشغيل مقطع الصوت.")
            print(f"Play Error: {e}")

# أمر التخطي: س أو سكب أو skip
@bot.command(aliases=['سكب', 'skip'])
async def س(ctx):
    if not ctx.voice_client or not ctx.voice_client.is_playing():
        await ctx.send("لا يوجد شيء شغال حالياً لتخطيه.")
        return

    ctx.voice_client.stop()
    await ctx.send("⏭️ تم تخطي الأغنية.")

# أمر الإيقاف والخروج: ي أو وقف أو stop
@bot.command(aliases=['وقف', 'stop'])
async def ي(ctx):
    if not ctx.voice_client:
        await ctx.send("البوت غير متصل بأي روم صوتي.")
        return

    song_queues[ctx.guild.id] = []
    ctx.voice_client.stop()
    await ctx.voice_client.disconnect()
    await ctx.send("⏹️ تم إيقاف التشغيل والخروج من الروم الصوتي.")

bot.run(DISCORD_TOKEN)
