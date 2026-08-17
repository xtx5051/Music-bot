import os
import re
import asyncio
import discord
from discord.ext import commands
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# ==========================================
# 1. قراءة التوكنات والمفاتيح
# ==========================================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")

sp = None
if SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET:
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET
    ))

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix="", intents=intents)

# خيارات محسنة لـ yt-dlp لتجاوز حظر يوتيوب في السيرفرات
import yt_dlp

# الإعدادات المحدثة والمطورة لتجاوز حظر يوتيوب
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
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    # هذا الجزء هو "السحر" الذي يحل مشكلة الحظر:
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'ios'],
        }
    }
}

# تهيئة ytdl
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)


song_queues = {}

def get_queue(guild_id):
    if guild_id not in song_queues:
        song_queues[guild_id] = []
    return song_queues[guild_id]

def get_spotify_query(url):
    if not sp:
        return None
    try:
        track_id = re.search(r'track/([a-zA-Z0-9]+)', url).group(1)
        track_info = sp.track(track_id)
        return f"{track_info['name']} {track_info['artists'][0]['name']}"
    except Exception as e:
        print(f"Spotify Parse Error: {e}")
        return None

def play_next(ctx):
    queue = get_queue(ctx.guild.id)
    if len(queue) > 0:
        next_song = queue.pop(0)
        source = discord.FFmpegPCMAudio(next_song['url'], **FFMPEG_OPTIONS)
        
        def after_playing(error):
            if error:
                print(f"Error during playback: {error}")
            play_next(ctx)

        ctx.voice_client.play(source, after=after_playing)
        asyncio.run_coroutine_threadsafe(
            ctx.send(f"🎶 جاري تشغيل: **{next_song['title']}**"),
            bot.loop
        )
    else:
        asyncio.run_coroutine_threadsafe(
            ctx.send("✅ انتهت قائمة الانتظار، البوت مستمر في الروم الصوتي."),
            bot.loop
        )

@bot.event
async def on_ready():
    print(f"✅ تم تسجيل الدخول بنجاح باسم: {bot.user.name}")

@bot.event
async def on_voice_state_update(member, before, after):
    if member == bot.user and before.channel is not None and after.channel is None:
        await asyncio.sleep(2)
        try:
            await before.channel.connect()
        except Exception as e:
            print(f"Error reconnecting: {e}")

@bot.command(aliases=['شغل', 'play'])
async def ش(ctx, *, query: str = None):
    if not query:
        await ctx.send("يرجى كتابة اسم الأغنية أو الرابط بعد الأمر.")
        return

    if not ctx.author.voice:
        await ctx.send("عفواً، يجب أن تكون في روم صوتي أولاً!")
        return

    voice_channel = ctx.author.voice.channel

    if ctx.voice_client is None:
        await voice_channel.connect()
    elif ctx.voice_client.channel != voice_channel:
        await ctx.voice_client.move_to(voice_channel)

    async with ctx.typing():
        search_target = query

        if "open.spotify.com/track" in query:
            song_title = get_spotify_query(query)
            if song_title:
                search_target = f"ytsearch:{song_title}"
                await ctx.send(f"🔍 تم التعرف على رابط سبوتيفاي: **{song_title}**")
            else:
                await ctx.send("تعذر جلب البيانات من سبوتيفاي.")
                return
        elif query.startswith("http://") or query.startswith("https://"):
            search_target = query
        else:
            search_target = f"ytsearch:{query}"

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
                
                def after_playing(error):
                    if error:
                        print(f"Playback error: {error}")
                    play_next(ctx)

                ctx.voice_client.play(source, after=after_playing)
                await ctx.send(f"🎶 جاري تشغيل: **{song_data['title']}**")

        except Exception as e:
            await ctx.send("حدث خطأ أثناء محاولة جلب تشغيل الصوت.")
            print(f"Play Error Details: {e}")

@bot.command(aliases=['سكب', 'skip'])
async def س(ctx):
    if not ctx.voice_client or not ctx.voice_client.is_playing():
        await ctx.send("لا يوجد شيء شغال حالياً لتخطيه.")
        return
    ctx.voice_client.stop()
    await ctx.send("⏭️ تم تخطي الأغنية.")

@bot.command(aliases=['وقف', 'stop'])
async def ي(ctx):
    if not ctx.voice_client:
        await ctx.send("البوت غير متصل بأي روم صوتي.")
        return

    song_queues[ctx.guild.id] = []
    if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
        ctx.voice_client.stop()
    await ctx.send("⏹️ تم إيقاف التشغيل ومسح قائمة الانتظار (البوت متبقي في الروم).")

bot.run(DISCORD_TOKEN)
