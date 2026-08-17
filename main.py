import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os
from datetime import timedelta

# =========================
# الإعدادات
# =========================

VOICE_CHANNEL_ID = 770786224612704306

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="",
    intents=intents,
    help_command=None
)

playlists = {}
reconnect_task = None


# =========================
# إعداد yt-dlp
# =========================

YDL_OPTIONS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "default_search": "ytsearch",
}


FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn"
}


# =========================
# مشغل الموسيقى
# =========================

class MusicPlayer:
    def __init__(self):
        self.queue = []
        self.current_song = None


def get_player(guild_id):
    if guild_id not in playlists:
        playlists[guild_id] = MusicPlayer()

    return playlists[guild_id]


# =========================
# الاتصال بالروم المحدد
# =========================

async def connect_to_fixed_channel():

    global reconnect_task

    await bot.wait_until_ready()

    channel = bot.get_channel(VOICE_CHANNEL_ID)

    if channel is None:
        print("لم يتم العثور على الروم الصوتي")
        return

    guild = channel.guild

    while not bot.is_closed():

        try:

            voice_client = guild.voice_client

            # إذا كان متصل بالروم المطلوب
            if voice_client and voice_client.is_connected():

                if voice_client.channel.id == VOICE_CHANNEL_ID:
                    await asyncio.sleep(10)
                    continue

                # إذا كان في روم ثاني، يرجع للروم المحدد
                print("البوت موجود في روم آخر، سيتم نقله للروم المحدد")

                try:
                    await voice_client.move_to(channel)
                except Exception as e:
                    print(f"تعذر نقل البوت: {e}")

                await asyncio.sleep(10)
                continue

            # لا يوجد اتصال
            print("البوت غير متصل، محاولة الاتصال...")

            try:
                await channel.connect(
                    reconnect=True,
                    timeout=30
                )

                print("تم الاتصال بالروم المحدد")

            except Exception as e:
                print(f"تعذر الاتصال بالروم الصوتي: {e}")

            await asyncio.sleep(10)

        except Exception as e:

            print(f"خطأ في نظام الاتصال: {e}")

            await asyncio.sleep(10)


# =========================
# عند تشغيل البوت
# =========================

@bot.event
async def on_ready():

    global reconnect_task

    print("--------------------------------")
    print(f"البوت شغال: {bot.user}")
    print(f"الروم الثابت: {VOICE_CHANNEL_ID}")
    print("--------------------------------")

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="الموسيقى"
        )
    )

    if reconnect_task is None or reconnect_task.done():
        reconnect_task = asyncio.create_task(
            connect_to_fixed_channel()
        )


# =========================
# البحث عن أغنية
# =========================

def search_song(query):

    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:

        info = ydl.extract_info(
            f"ytsearch:{query}",
            download=False
        )

        if not info or not info.get("entries"):
            return None

        video = info["entries"][0]

        return {
            "url": video["url"],
            "title": video.get("title", "أغنية"),
            "duration": video.get("duration", 0)
        }


# =========================
# تشغيل الأغنية التالية
# =========================

async def play_next(guild):

    player = get_player(guild.id)

    voice_client = guild.voice_client

    if not voice_client or not voice_client.is_connected():
        return

    if voice_client.channel.id != VOICE_CHANNEL_ID:
        try:
            channel = bot.get_channel(VOICE_CHANNEL_ID)
            await voice_client.move_to(channel)
        except Exception:
            return

    if not player.queue:

        player.current_song = None
        return

    song = player.queue.pop(0)

    player.current_song = song

    try:

        audio_source = discord.FFmpegPCMAudio(
            song["url"],
            **FFMPEG_OPTIONS
        )

        def after_playing(error):

            if error:
                print(f"خطأ في التشغيل: {error}")

            asyncio.run_coroutine_threadsafe(
                play_next(guild),
                bot.loop
            )

        voice_client.play(
            audio_source,
            after=after_playing
        )

        print(f"يتم تشغيل: {song['title']}")

    except Exception as e:

        print(f"خطأ في تشغيل الأغنية: {e}")

        player.current_song = None

        await play_next(guild)


# =========================
# ش - تشغيل
# =========================

@bot.command(name="ش")
async def play_command(ctx, *, search=None):

    if not search:
        await ctx.send("اكتب اسم الأغنية بعد ش")
        return

    guild = ctx.guild

    voice_client = guild.voice_client

    # التأكد من الروم الثابت
    if not voice_client or not voice_client.is_connected():

        channel = bot.get_channel(VOICE_CHANNEL_ID)

        try:
            voice_client = await channel.connect(
                reconnect=True,
                timeout=30
            )

        except Exception:
            await ctx.send("تعذر الاتصال بالروم الصوتي")
            return

    elif voice_client.channel.id != VOICE_CHANNEL_ID:

        channel = bot.get_channel(VOICE_CHANNEL_ID)

        try:
            await voice_client.move_to(channel)

        except Exception:
            await ctx.send("تعذر الانتقال للروم المحدد")
            return

    await ctx.send(f"جاري البحث عن: {search}")

    try:

        song = await asyncio.to_thread(
            search_song,
            search
        )

        if not song:
            await ctx.send("ما لقيت الأغنية")
            return

        player = get_player(guild.id)

        player.queue.append(song)

        duration = song["duration"]

        duration_text = str(
            timedelta(seconds=duration)
        )

        await ctx.send(
            f"تمت إضافة: {song['title']}\n"
            f"المدة: {duration_text}"
        )

        if not voice_client.is_playing() and not voice_client.is_paused():

            await play_next(guild)

    except Exception as e:

        print(e)

        await ctx.send(
            f"حدث خطأ: {str(e)}"
        )


# =========================
# س - تخطي
# =========================

@bot.command(name="س")
async def skip_command(ctx):

    voice_client = ctx.guild.voice_client

    if voice_client and voice_client.is_playing():

        voice_client.stop()

        await ctx.send("تم التخطي")

    else:

        await ctx.send("ما فيه أغنية شغالة")


# =========================
# و - وقف
# =========================

@bot.command(name="و")
async def stop_command(ctx):

    voice_client = ctx.guild.voice_client
    player = get_player(ctx.guild.id)

    player.queue.clear()
    player.current_song = None

    if voice_client and (
        voice_client.is_playing()
        or voice_client.is_paused()
    ):

        voice_client.stop()

    await ctx.send("تم إيقاف التشغيل")


# =========================
# ب - إيقاف مؤقت
# =========================

@bot.command(name="ب")
async def pause_command(ctx):

    voice_client = ctx.guild.voice_client

    if voice_client and voice_client.is_playing():

        voice_client.pause()

        await ctx.send("تم الإيقاف المؤقت")

    else:

        await ctx.send("ما فيه أغنية شغالة")


# =========================
# ت - استئناف
# =========================

@bot.command(name="ت")
async def resume_command(ctx):

    voice_client = ctx.guild.voice_client

    if voice_client and voice_client.is_paused():

        voice_client.resume()

        await ctx.send("تم استئناف التشغيل")

    else:

        await ctx.send("ما فيه أغنية موقوفة")


# =========================
# ع - قائمة الانتظار
# =========================

@bot.command(name="ع")
async def queue_command(ctx):

    player = get_player(ctx.guild.id)

    if not player.queue:

        if player.current_song:

            await ctx.send(
                f"تشغيل الآن: {player.current_song['title']}\n"
                "ما فيه أغاني بعدها"
            )

        else:

            await ctx.send("قائمة التشغيل فارغة")

        return

    text = "قائمة التشغيل:\n"

    for index, song in enumerate(
        player.queue[:10],
        1
    ):

        text += f"{index}. {song['title']}\n"

    if len(player.queue) > 10:

        text += (
            f"... و {len(player.queue) - 10} أغاني أخرى"
        )

    await ctx.send(text)


# =========================
# م - المساعدة
# =========================

@bot.command(name="م")
async def help_command(ctx):

    await ctx.send(
        "أوامر البوت:\n\n"
        "ش [اسم الأغنية] - تشغيل\n"
        "س - تخطي\n"
        "و - وقف\n"
        "ب - إيقاف مؤقت\n"
        "ت - استئناف\n"
        "ع - قائمة التشغيل\n"
        "م - المساعدة\n\n"
        "البوت ثابت في الروم المحدد."
    )


# =========================
# معالجة الرسائل
# =========================

@bot.event
async def on_command_error(ctx, error):

    if isinstance(
        error,
        commands.CommandNotFound
    ):
        return

    if isinstance(
        error,
        commands.MissingRequiredArgument
    ):

        await ctx.send(
            "استخدم الأمر بالشكل الصحيح"
        )

        return

    print(
        f"Command error: {error}"
    )


# =========================
# تشغيل البوت
# =========================

token = os.getenv("DISCORD_TOKEN")

if not token:

    raise RuntimeError(
        "DISCORD_TOKEN غير موجود في متغيرات Railway"
    )

bot.run(token)
