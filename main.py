import os
import asyncio
import discord
from discord.ext import commands
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# إعداد صلاحيات البوت
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="", intents=intents)

# إعداد سبوتيفاي من المتغيرات البيئية
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")

sp = None
if SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET:
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET
    ))

# البحث التشغيلي حصرياً من SoundCloud لتفادي الحظر
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
    'default_search': 'scsearch',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

queues = {}

def check_queue(ctx):
    guild_id = ctx.guild.id
    if guild_id in queues and len(queues[guild_id]) > 0:
        next_track = queues[guild_id].pop(0)
        source = discord.FFmpegPCMAudio(next_track['url'], **FFMPEG_OPTIONS)
        ctx.voice_client.play(source, after=lambda e: check_queue(ctx))
        asyncio.run_coroutine_threadsafe(ctx.send(f"شغال الآن: **{next_track['title']}** 🎵"), bot.loop)

@bot.event
async def on_ready():
    print(f'البوت جاهز ويعمل باسم: {bot.user.name}')

# أمر التشغيل: ش
@bot.command(name="ش", aliases=["play", "p"])
async def play(ctx, *, query: str = None):
    if not query:
        await ctx.send("يرجى كتابة اسم الأغنية أو الرابط بعد الأمر.")
        return

    if not ctx.author.voice:
        await ctx.send("يرجى الانضمام إلى روم صوتي أولاً!")
        return

    voice_channel = ctx.author.voice.channel
    voice_client = ctx.voice_client

    if not voice_client:
        voice_client = await voice_channel.connect()
    elif voice_client.channel != voice_channel:
        await voice_client.move_to(voice_channel)

    search_query = query

    if "spotify.com" in query:
        if not sp:
            await ctx.send("لم يتم ضبط حساب Spotify في Railway!")
            return
        
        try:
            if "track" in query:
                track = sp.track(query)
                track_name = track['name']
                artist_name = track['artists'][0]['name']
                search_query = f"scsearch:{artist_name} - {track_name}"
            else:
                await ctx.send("يدعم البوت الأغاني الفردية فقط من سبوتيفاي.")
                return
        except Exception as e:
            await ctx.send(f"خطأ أثناء جلب بيانات سبوتيفاي: {e}")
            return
    elif not query.startswith("http"):
        search_query = f"scsearch:{query}"

    await ctx.send(f"جاري البحث عن: `{query}` عبر SoundCloud...")

    try:
        data = await bot.loop.run_in_executor(None, lambda: ytdl.extract_info(search_query, download=False))
        if 'entries' in data and len(data['entries']) > 0:
            info = data['entries'][0]
        else:
            info = data

        track_data = {
            'url': info['url'],
            'title': info.get('title', 'صوتية')
        }

        guild_id = ctx.guild.id
        if guild_id not in queues:
            queues[guild_id] = []

        if voice_client.is_playing() or voice_client.is_paused():
            queues[guild_id].append(track_data)
            await ctx.send(f"تمت الإضافة إلى القائمة: **{track_data['title']}** 📝")
        else:
            source = discord.FFmpegPCMAudio(track_data['url'], **FFMPEG_OPTIONS)
            voice_client.play(source, after=lambda e: check_queue(ctx))
            await ctx.send(f"شغال الآن: **{track_data['title']}** 🎵")

    except Exception as e:
        await ctx.send(f"حدث خطأ أثناء استخراج الصوت: {e}")

# أمر التخطي: س
@bot.command(name="س", aliases=["skip", "s"])
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("تم تخطي المقطع الحالي ⏭️")
    else:
        await ctx.send("لا يوجد شيء شغال حالياً للتخطي.")

# أمر الإيقاف المسح والتواجد 24/7: ي
@bot.command(name="ي", aliases=["stop", "clear"])
async def stop(ctx):
    guild_id = ctx.guild.id
    if guild_id in queues:
        queues[guild_id].clear()
        
    if ctx.voice_client:
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            ctx.voice_client.stop()
        await ctx.send("تم إيقاف التشغيل وتفريغ القائمة ⏹️ (البوت متواجد بالروم 24/7)")
    else:
        await ctx.send("البوت ليس متواجداً في روم صوتي.")

token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
else:
    print("خطأ: لم يتم العثور على DISCORD_TOKEN.")
