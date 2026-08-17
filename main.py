import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os
from datetime import timedelta

# ==========================================
# إعدادات البوت
# ==========================================

VOICE_CHANNEL_ID = 770786224612704306

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="",
    intents=intents,
    help_command=None
)

players = {}

# قفل يمنع أكثر من محاولة اتصال بنفس الوقت
voice_lock = asyncio.Lock()

# ==========================================
# SoundCloud
# ==========================================

YDL_OPTIONS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "extract_flat": False,
}

FFMPEG_OPTIONS = {
    "before_options": (
        "-reconnect 1 "
        "-reconnect_streamed 1 "
        "-reconnect_delay_max 5"
    ),
    "options": "-vn"
}


# ==========================================
# Music Player
# ==========================================

class MusicPlayer:

    def __init__(self):
        self.queue = []
        self.current_song = None


def get_player(guild_id):

    if guild_id not in players:
        players[guild_id] = MusicPlayer()

    return players[guild_id]


# ==========================================
# الحصول على الروم
# ==========================================

def get_fixed_channel():

    channel = bot.get_channel(VOICE_CHANNEL_ID)

    if channel is None:
        return None

    if not isinstance(channel, discord.VoiceChannel):
        return None

    return channel


# ==========================================
# الاتصال بالروم الثابت
# ==========================================

async def connect_fixed_channel():

    async with voice_lock:

        channel = get_fixed_channel()

        if channel is None:
            print("❌ لم يتم العثور على الروم الصوتي")
            return False

        guild = channel.guild
        voice = guild.voice_client

        # متصل بالروم الصحيح
        if voice and voice.is_connected():

            if voice.channel.id == VOICE_CHANNEL_ID:
                return True

            # موجود في روم آخر
            try:

                print("⚠️ البوت في روم آخر، سيتم نقله")

                await voice.move_to(channel)

                print("تم نقل البوت للروم المحدد")

                return True

            except Exception as e:

                print(f"❌ فشل نقل البوت: {e}")

                return False

        # إذا فيه VoiceClient عالق
        if voice:

            print("⚠️ يوجد اتصال صوتي عالق، سيتم تنظيفه")

            try:
                await voice.disconnect(force=True)
            except Exception:
                pass

            await asyncio.sleep(3)

            # التحقق مرة ثانية
            voice = guild.voice_client

            if voice:
                print("⚠️ ما زال الاتصال القديم موجوداً")
                return False

        # الاتصال الجديد
        try:

            print("🔄 محاولة الاتصال بالروم...")

            await channel.connect(
                reconnect=True,
                timeout=30
            )

            print("✅ تم الاتصال بالروم المحدد")

            return True

        except asyncio.TimeoutError:

            print("❌ انتهت مهلة الاتصال")

            return False

        except Exception as e:

            print(f"❌ تعذر الاتصال: {e}")

            return False


# ==========================================
# مراقبة الاتصال
# ==========================================

async def voice_keeper():

    await bot.wait_until_ready()

    while not bot.is_closed():

        try:

            channel = get_fixed_channel()

            if channel is None:

                await asyncio.sleep(20)
                continue

            guild = channel.guild
            voice = guild.voice_client

            # متصل بالروم الصحيح
            if (
                voice
                and voice.is_connected()
                and voice.channel.id == VOICE_CHANNEL_ID
            ):

                await asyncio.sleep(20)
                continue

            print("⚠️ البوت غير متصل بالروم الصحيح")

            await connect_fixed_channel()

            # لا تحاول بسرعة
            await asyncio.sleep(20)

        except Exception as e:

            print(f"⚠️ خطأ في مراقبة الروم: {e}")

            await asyncio.sleep(20)


# ==========================================
# عند تشغيل البوت
# ==========================================

@bot.event
async def on_ready():

    print("================================")
    print(f"البوت شغال: {bot.user}")
    print(f"الروم الثابت: {VOICE_CHANNEL_ID}")
    print("المصدر: SoundCloud")
    print("================================")

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="الموسيقى"
        )
    )

    # تشغيل مراقب الروم مرة واحدة
    if not hasattr(bot, "voice_keeper_task"):

        bot.voice_keeper_task = asyncio.create_task(
            voice_keeper()
        )


# ==========================================
# البحث في SoundCloud
# ==========================================

def search_soundcloud(query):

    options = YDL_OPTIONS.copy()
    options["default_search"] = "scsearch"

    with yt_dlp.YoutubeDL(options) as ydl:

        info = ydl.extract_info(
            f"scsearch1:{query}",
            download=False
        )

        if not info:
            return None

        entries = info.get("entries")

        if not entries:
            return None

        song = entries[0]

        return {
            "url": song.get("url"),
            "title": song.get(
                "title",
                "أغنية غير معروفة"
            ),
            "duration": song.get(
                "duration",
                0
            ),
            "webpage_url": song.get(
                "webpage_url"
            )
        }


# ==========================================
# استخراج رابط الصوت
# ==========================================

def extract_audio_url(webpage_url):

    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:

        info = ydl.extract_info(
            webpage_url,
            download=False
        )

        return info.get("url")


# ==========================================
# تشغيل الأغنية التالية
# ==========================================

async def play_next(guild):

    player = get_player(guild.id)

    voice = guild.voice_client

    if not voice or not voice.is_connected():
        return

    # التأكد من الروم الصحيح
    if voice.channel.id != VOICE_CHANNEL_ID:

        success = await connect_fixed_channel()

        if not success:
            return

        voice = guild.voice_client

        if not voice:
            return

    # لا توجد أغاني
    if not player.queue:

        player.current_song = None

        return

    song = player.queue.pop(0)

    player.current_song = song

    try:

        audio_url = await asyncio.to_thread(
            extract_audio_url,
            song["webpage_url"]
        )

        if not audio_url:

            raise Exception(
                "تعذر الحصول على رابط الصوت"
            )

        audio_source = discord.FFmpegPCMAudio(
            audio_url,
            **FFMPEG_OPTIONS
        )

        def after_playing(error):

            if error:
                print(
                    f"❌ خطأ في التشغيل: {error}"
                )

            asyncio.run_coroutine_threadsafe(
                play_next(guild),
                bot.loop
            )

        voice.play(
            audio_source,
            after=after_playing
        )

        print(
            f"▶️ تشغيل: {song['title']}"
        )

    except Exception as e:

        print(
            f"❌ خطأ في تشغيل الأغنية: {e}"
        )

        player.current_song = None

        await play_next(guild)


# ==========================================
# ش = تشغيل
# ==========================================

@bot.command(name="ش")
async def play_command(ctx, *, search=None):

    if not search:

        await ctx.send(
            "اكتب اسم الأغنية بعد ش"
        )

        return

    channel = get_fixed_channel()

    if channel is None:

        await ctx.send(
            "ما قدرت ألقى الروم الصوتي المحدد"
        )

        return

    guild = channel.guild

    # التأكد من الاتصال
    success = await connect_fixed_channel()

    if not success:

        await ctx.send(
            "تعذر الاتصال بالروم الصوتي"
        )

        return

    await ctx.send(
        f"جاري البحث في SoundCloud عن: {search}"
    )

    try:

        song = await asyncio.to_thread(
            search_soundcloud,
            search
        )

        if not song:

            await ctx.send(
                "ما لقيت الأغنية في SoundCloud"
            )

            return

        player = get_player(guild.id)

        player.queue.append(song)

        duration = song.get("duration", 0)

        if duration:

            duration_text = str(
                timedelta(
                    seconds=int(duration)
                )
            )

        else:

            duration_text = "غير معروف"

        await ctx.send(
            f"تمت الإضافة: {song['title']}\n"
            f"المدة: {duration_text}"
        )

        voice = guild.voice_client

        if (
            voice
            and not voice.is_playing()
            and not voice.is_paused()
        ):

            await play_next(guild)

    except Exception as e:

        print(
            f"❌ SoundCloud error: {e}"
        )

        await ctx.send(
            f"حدث خطأ: {str(e)}"
        )


# ==========================================
# س = تخطي
# ==========================================

@bot.command(name="س")
async def skip_command(ctx):

    voice = ctx.guild.voice_client

    if voice and voice.is_playing():

        voice.stop()

        await ctx.send(
            "تم التخطي"
        )

    else:

        await ctx.send(
            "ما فيه أغنية شغالة"
        )


# ==========================================
# و = إيقاف
# ==========================================

@bot.command(name="و")
async def stop_command(ctx):

    voice = ctx.guild.voice_client

    player = get_player(
        ctx.guild.id
    )

    player.queue.clear()
    player.current_song = None

    if voice:

        if (
            voice.is_playing()
            or voice.is_paused()
        ):

            voice.stop()

    await ctx.send(
        "تم إيقاف التشغيل"
    )


# ==========================================
# ب = إيقاف مؤقت
# ==========================================

@bot.command(name="ب")
async def pause_command(ctx):

    voice = ctx.guild.voice_client

    if voice and voice.is_playing():

        voice.pause()

        await ctx.send(
            "تم الإيقاف المؤقت"
        )

    else:

        await ctx.send(
            "ما فيه أغنية شغالة"
        )


# ==========================================
# ت = استئناف
# ==========================================

@bot.command(name="ت")
async def resume_command(ctx):

    voice = ctx.guild.voice_client

    if voice and voice.is_paused():

        voice.resume()

        await ctx.send(
            "تم استئناف التشغيل"
        )

    else:

        await ctx.send(
            "ما فيه أغنية موقوفة"
        )


# ==========================================
# ع = قائمة التشغيل
# ==========================================

@bot.command(name="ع")
async def queue_command(ctx):

    player = get_player(
        ctx.guild.id
    )

    text = ""

    if player.current_song:

        text += (
            f"تشغيل الآن: "
            f"{player.current_song['title']}\n\n"
        )

    if not player.queue:

        if text:

            await ctx.send(
                text + "ما فيه أغاني بعدها"
            )

        else:

            await ctx.send(
                "قائمة التشغيل فارغة"
            )

        return

    text += "قائمة التشغيل:\n"

    for index, song in enumerate(
        player.queue[:10],
        1
    ):

        text += (
            f"{index}. "
            f"{song['title']}\n"
        )

    if len(player.queue) > 10:

        text += (
            f"... و {len(player.queue) - 10} أغاني أخرى"
        )

    await ctx.send(text)


# ==========================================
# م = المساعدة
# ==========================================

@bot.command(name="م")
async def help_command(ctx):

    await ctx.send(
        "أوامر البوت:\n\n"
        "ش [اسم الأغنية] - تشغيل\n"
        "س - تخطي\n"
        "و - إيقاف\n"
        "ب - إيقاف مؤقت\n"
        "ت - استئناف\n"
        "ع - قائمة التشغيل\n"
        "م - المساعدة\n\n"
        "المصدر: SoundCloud\n"
        "البوت ثابت في الروم المحدد"
    )


# ==========================================
# الأخطاء
# ==========================================

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


# ==========================================
# تشغيل البوت
# ==========================================

token = os.getenv("DISCORD_TOKEN")

if not token:

    raise RuntimeError(
        "DISCORD_TOKEN غير موجود في Railway Variables"
    )

bot.run(token)
