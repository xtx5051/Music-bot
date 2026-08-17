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


# ==========================================
# إعدادات SoundCloud
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
# العثور على السيرفر والروم
# ==========================================

def get_voice_channel():

    channel = bot.get_channel(VOICE_CHANNEL_ID)

    if channel is None:
        return None

    if not isinstance(
        channel,
        discord.VoiceChannel
    ):
        return None

    return channel


# ==========================================
# الاتصال بالروم عند تشغيل البوت
# ==========================================

async def connect_to_fixed_channel():

    await bot.wait_until_ready()

    channel = get_voice_channel()

    if channel is None:

        print(
            f"لم يتم العثور على الروم الصوتي: "
            f"{VOICE_CHANNEL_ID}"
        )

        return None

    guild = channel.guild

    voice_client = guild.voice_client

    # إذا كان متصل بالروم الصحيح
    if (
        voice_client
        and voice_client.is_connected()
        and voice_client.channel
        and voice_client.channel.id == VOICE_CHANNEL_ID
    ):

        print("البوت متصل بالروم المحدد")

        return voice_client

    # إذا كان فيه اتصال قديم عالق
    if voice_client:

        print("يوجد اتصال صوتي قديم، سيتم تنظيفه")

        try:
            await voice_client.disconnect(force=True)
        except Exception as e:
            print(f"خطأ أثناء تنظيف الاتصال: {e}")

        await asyncio.sleep(2)

    # الاتصال بالروم
    try:

        print("جاري الاتصال بالروم المحدد...")

        voice_client = await channel.connect(
            reconnect=True,
            timeout=30
        )

        print("تم الاتصال بالروم المحدد")

        return voice_client

    except Exception as e:

        print(
            f"تعذر الاتصال بالروم الصوتي: {e}"
        )

        return None


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

    # محاولة واحدة للاتصال
    await connect_to_fixed_channel()


# ==========================================
# إذا انقطع البوت من الروم
# ==========================================

@bot.event
async def on_voice_state_update(
    member,
    before,
    after
):

    # لا نتدخل في حالة البوت نفسه
    if member.id == bot.user.id:
        return

    channel = get_voice_channel()

    if channel is None:
        return

    guild = channel.guild

    voice_client = guild.voice_client

    if voice_client is None:
        return

    # إذا البوت ما زال في الروم الصحيح
    if (
        voice_client.is_connected()
        and voice_client.channel
        and voice_client.channel.id == VOICE_CHANNEL_ID
    ):
        return


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
# تشغيل الأغنية التالية
# ==========================================

async def play_next(guild):

    player = get_player(guild.id)

    voice_client = guild.voice_client

    if not voice_client:
        return

    if not voice_client.is_connected():
        return

    if not player.queue:

        player.current_song = None

        return

    song = player.queue.pop(0)

    player.current_song = song

    try:

        # استخراج رابط الصوت
        def get_audio():

            options = YDL_OPTIONS.copy()

            with yt_dlp.YoutubeDL(options) as ydl:

                info = ydl.extract_info(
                    song["webpage_url"],
                    download=False
                )

                return info["url"]

        audio_url = await asyncio.to_thread(
            get_audio
        )

        audio_source = discord.FFmpegPCMAudio(
            audio_url,
            **FFMPEG_OPTIONS
        )

        def after_playing(error):

            if error:

                print(
                    f"خطأ في التشغيل: {error}"
                )

            asyncio.run_coroutine_threadsafe(
                play_next(guild),
                bot.loop
            )

        voice_client.play(
            audio_source,
            after=after_playing
        )

        print(
            f"تشغيل: {song['title']}"
        )

    except Exception as e:

        print(
            f"خطأ في تشغيل الأغنية: {e}"
        )

        player.current_song = None

        await play_next(guild)


# ==========================================
# ش = تشغيل
# ==========================================

@bot.command(name="ش")
async def play_command(
    ctx,
    *,
    search=None
):

    if not search:

        await ctx.send(
            "اكتب اسم الأغنية بعد ش"
        )

        return

    guild = ctx.guild

    channel = get_voice_channel()

    if channel is None:

        await ctx.send(
            "ما قدرت ألقى الروم الصوتي المحدد"
        )

        return

    voice_client = guild.voice_client

    # إذا البوت غير متصل
    if (
        voice_client is None
        or not voice_client.is_connected()
    ):

        voice_client = await connect_to_fixed_channel()

        if voice_client is None:

            await ctx.send(
                "تعذر الاتصال بالروم الصوتي"
            )

            return

    # إذا البوت في روم مختلف
    elif (
        voice_client.channel
        and voice_client.channel.id != VOICE_CHANNEL_ID
    ):

        try:

            await voice_client.move_to(
                channel
            )

        except Exception as e:

            print(
                f"تعذر نقل البوت: {e}"
            )

            await ctx.send(
                "تعذر الانتقال للروم المحدد"
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

        if not song["webpage_url"]:

            await ctx.send(
                "تعذر الحصول على رابط الأغنية"
            )

            return

        player = get_player(
            guild.id
        )

        player.queue.append(song)

        duration = song["duration"]

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

        voice_client = guild.voice_client

        if (
            voice_client
            and not voice_client.is_playing()
            and not voice_client.is_paused()
        ):

            await play_next(guild)

    except Exception as e:

        print(
            f"SoundCloud error: {e}"
        )

        await ctx.send(
            f"حدث خطأ: {str(e)}"
        )


# ==========================================
# س = تخطي
# ==========================================

@bot.command(name="س")
async def skip_command(ctx):

    voice_client = ctx.guild.voice_client

    if (
        voice_client
        and voice_client.is_playing()
    ):

        voice_client.stop()

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

    voice_client = ctx.guild.voice_client

    player = get_player(
        ctx.guild.id
    )

    player.queue.clear()
    player.current_song = None

    if (
        voice_client
        and (
            voice_client.is_playing()
            or voice_client.is_paused()
        )
    ):

        voice_client.stop()

    await ctx.send(
        "تم إيقاف التشغيل"
    )


# ==========================================
# ب = إيقاف مؤقت
# ==========================================

@bot.command(name="ب")
async def pause_command(ctx):

    voice_client = ctx.guild.voice_client

    if (
        voice_client
        and voice_client.is_playing()
    ):

        voice_client.pause()

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

    voice_client = ctx.guild.voice_client

    if (
        voice_client
        and voice_client.is_paused()
    ):

        voice_client.resume()

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

        if not text:

            await ctx.send(
                "قائمة التشغيل فارغة"
            )

        else:

            await ctx.send(
                text + "ما فيه أغاني بعدها"
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
            f"... و "
            f"{len(player.queue) - 10} "
            f"أغاني أخرى"
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
# تجاهل الأوامر غير المعروفة
# ==========================================

@bot.event
async def on_command_error(
    ctx,
    error
):

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

token = os.getenv(
    "DISCORD_TOKEN"
)

if not token:

    raise RuntimeError(
        "DISCORD_TOKEN غير موجود في Railway Variables"
    )

bot.run(token)
