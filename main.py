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

playlists = {}


# ==========================================
# Music Player
# ==========================================

class MusicPlayer:
    def __init__(self, guild_id):
        self.guild_id = guild_id
        self.queue = []
        self.current_song = None
        self.voice_client = None


# ==========================================
# إعدادات yt-dlp
# ==========================================

ydl_options = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "extractor_args": {
        "youtube": {
            "player_client": ["android", "web"]
        }
    }
}


# ==========================================
# جلب معلومات الأغنية
# ==========================================

def get_song(search):

    with yt_dlp.YoutubeDL(ydl_options) as ydl:

        if search.startswith("http://") or search.startswith("https://"):
            info = ydl.extract_info(
                search,
                download=False
            )
        else:
            info = ydl.extract_info(
                f"ytsearch1:{search}",
                download=False
            )

        if "entries" in info:
            entries = info.get("entries")

            if not entries:
                return None

            info = entries[0]

        return {
            "url": info["url"],
            "title": info.get("title", "أغنية بدون اسم"),
            "duration": info.get("duration", 0)
        }


# ==========================================
# تشغيل الأغنية التالية
# ==========================================

async def play_next(guild_id, text_channel):

    player = playlists.get(guild_id)

    if player is None:
        return

    voice_client = player.voice_client

    if voice_client is None or not voice_client.is_connected():
        print("لا يوجد اتصال صوتي")
        return

    if not player.queue:
        player.current_song = None
        return

    song = player.queue.pop(0)

    player.current_song = song

    try:

        audio_source = discord.FFmpegPCMAudio(
            song["url"],
            before_options=(
                "-reconnect 1 "
                "-reconnect_streamed 1 "
                "-reconnect_delay_max 5"
            ),
            options="-vn"
        )

        def after_playing(error):

            if error:
                print(
                    f"خطأ في التشغيل: "
                    f"{type(error).__name__}: {error}"
                )

            asyncio.run_coroutine_threadsafe(
                play_next(
                    guild_id,
                    text_channel
                ),
                bot.loop
            )

        voice_client.play(
            audio_source,
            after=after_playing
        )

        await text_channel.send(
            f"الآن يتم التشغيل: {song['title']}"
        )

    except Exception as e:

        print(
            f"خطأ في تشغيل الأغنية: "
            f"{type(e).__name__}: {e}"
        )

        player.current_song = None

        await play_next(
            guild_id,
            text_channel
        )


# ==========================================
# الاتصال بالروم المحدد
# ==========================================

async def keep_connected():

    await bot.wait_until_ready()

    while not bot.is_closed():

        try:

            channel = bot.get_channel(
                VOICE_CHANNEL_ID
            )

            if channel is None:

                print(
                    "لم يتم العثور على الروم الصوتي"
                )

                await asyncio.sleep(15)
                continue

            if not isinstance(
                channel,
                discord.VoiceChannel
            ):

                print(
                    "الـ ID ليس لروم صوتي"
                )

                await asyncio.sleep(15)
                continue

            voice_client = discord.utils.get(
                bot.voice_clients,
                guild=channel.guild
            )

            # لا يوجد اتصال صوتي
            if voice_client is None:

                print(
                    "البوت غير متصل، محاولة الاتصال..."
                )

                voice_client = await channel.connect()

                print(
                    f"تم الاتصال بالروم: "
                    f"{channel.name}"
                )

            # الاتصال موجود لكنه غير متصل فعليًا
            elif not voice_client.is_connected():

                print(
                    "الاتصال الصوتي انقطع، "
                    "إعادة الاتصال..."
                )

                try:
                    await voice_client.disconnect(
                        force=True
                    )
                except Exception:
                    pass

                voice_client = await channel.connect()

            # البوت في روم مختلف
            elif voice_client.channel.id != VOICE_CHANNEL_ID:

                print(
                    "البوت موجود في روم آخر، "
                    "نقله للروم المحدد..."
                )

                await voice_client.move_to(
                    channel
                )

                print(
                    f"تم نقل البوت إلى: "
                    f"{channel.name}"
                )

            # تحديث MusicPlayer
            player = playlists.get(
                channel.guild.id
            )

            if player is None:

                player = MusicPlayer(
                    channel.guild.id
                )

                playlists[
                    channel.guild.id
                ] = player

            player.voice_client = voice_client

        except Exception as e:

            print(
                f"خطأ في الاتصال الصوتي: "
                f"{type(e).__name__}: {e}"
            )

        await asyncio.sleep(15)


# ==========================================
# عند تشغيل البوت
# ==========================================

@bot.event
async def on_ready():

    print(
        f"البوت شغال: {bot.user}"
    )

    if not hasattr(
        bot,
        "voice_connection_task"
    ):

        bot.voice_connection_task = (
            asyncio.create_task(
                keep_connected()
            )
        )


# ==========================================
# ش = تشغيل أغنية
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

    player = playlists.get(
        ctx.guild.id
    )

    if player is None:

        player = MusicPlayer(
            ctx.guild.id
        )

        playlists[
            ctx.guild.id
        ] = player

    voice_client = player.voice_client

    # التأكد من وجود الاتصال
    if (
        voice_client is None
        or not voice_client.is_connected()
    ):

        channel = bot.get_channel(
            VOICE_CHANNEL_ID
        )

        if channel is None:

            await ctx.send(
                "لم يتم العثور على الروم الصوتي"
            )

            return

        try:

            voice_client = discord.utils.get(
                bot.voice_clients,
                guild=channel.guild
            )

            if voice_client is None:

                voice_client = await channel.connect()

            elif voice_client.channel.id != VOICE_CHANNEL_ID:

                await voice_client.move_to(
                    channel
                )

            player.voice_client = voice_client

        except Exception as e:

            print(
                f"VOICE ERROR: "
                f"{type(e).__name__}: {e}"
            )

            await ctx.send(
                f"خطأ الاتصال بالروم: "
                f"{type(e).__name__}: {e}"
            )

            return

    await ctx.send(
        f"جاري البحث عن: {search}"
    )

    try:

        song = await asyncio.to_thread(
            get_song,
            search
        )

        if song is None:

            await ctx.send(
                "لم يتم العثور على الأغنية"
            )

            return

        player.queue.append(song)

        duration = song["duration"] or 0

        duration_str = str(
            timedelta(
                seconds=int(duration)
            )
        )

        await ctx.send(
            f"تمت إضافة: {song['title']}\n"
            f"المدة: {duration_str}\n"
            f"في الانتظار: {len(player.queue)}"
        )

        # إذا ما فيه أغنية شغالة
        if (
            not voice_client.is_playing()
            and not voice_client.is_paused()
        ):

            await play_next(
                ctx.guild.id,
                ctx.channel
            )

    except Exception as e:

        print(
            f"خطأ في البحث: "
            f"{type(e).__name__}: {e}"
        )

        await ctx.send(
            f"حدث خطأ: {e}"
        )


# ==========================================
# س = سكب
# ==========================================

@bot.command(name="س")
async def skip_command(ctx):

    player = playlists.get(
        ctx.guild.id
    )

    if not player or not player.voice_client:

        await ctx.send(
            "ما فيه أغنية شغالة"
        )

        return

    voice_client = player.voice_client

    if (
        voice_client.is_playing()
        or voice_client.is_paused()
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

    player = playlists.get(
        ctx.guild.id
    )

    if not player or not player.voice_client:

        await ctx.send(
            "ما فيه أغنية شغالة"
        )

        return

    voice_client = player.voice_client

    if (
        voice_client.is_playing()
        or voice_client.is_paused()
    ):

        voice_client.stop()

        player.queue.clear()
        player.current_song = None

        await ctx.send(
            "تم إيقاف التشغيل وحذف قائمة الانتظار"
        )

    else:

        await ctx.send(
            "ما فيه أغنية شغالة"
        )


# ==========================================
# ب = إيقاف مؤقت
# ==========================================

@bot.command(name="ب")
async def pause_command(ctx):

    player = playlists.get(
        ctx.guild.id
    )

    if (
        player
        and player.voice_client
        and player.voice_client.is_playing()
    ):

        player.voice_client.pause()

        await ctx.send(
            "تم الإيقاف المؤقت"
        )

        return

    await ctx.send(
        "ما فيه أغنية شغالة"
    )


# ==========================================
# ت = استئناف
# ==========================================

@bot.command(name="ت")
async def resume_command(ctx):

    player = playlists.get(
        ctx.guild.id
    )

    if (
        player
        and player.voice_client
        and player.voice_client.is_paused()
    ):

        player.voice_client.resume()

        await ctx.send(
            "تم استئناف التشغيل"
        )

        return

    await ctx.send(
        "ما فيه أغنية موقوفة"
    )


# ==========================================
# ع = قائمة الانتظار
# ==========================================

@bot.command(name="ع")
async def queue_command(ctx):

    player = playlists.get(
        ctx.guild.id
    )

    if not player or not player.queue:

        await ctx.send(
            "قائمة الانتظار فارغة"
        )

        return

    message = "قائمة الانتظار:\n\n"

    for i, song in enumerate(
        player.queue[:10],
        1
    ):

        message += (
            f"{i}. "
            f"{song['title']}\n"
        )

    if len(player.queue) > 10:

        message += (
            f"\nو {len(player.queue) - 10} "
            f"أغاني أخرى"
        )

    await ctx.send(
        message
    )


# ==========================================
# م = المساعدة
# ==========================================

@bot.command(name="م")
async def help_command(ctx):

    message = """
أوامر البوت:

ش اسم الأغنية
تشغيل أغنية

س
تخطي الأغنية

و
إيقاف التشغيل وحذف قائمة الانتظار

ب
إيقاف مؤقت

ت
استئناف التشغيل

ع
عرض قائمة الانتظار

م
عرض الأوامر

البوت يدخل الروم المحدد تلقائيًا ولا يخرج منه.
"""

    await ctx.send(
        message
    )


# ==========================================
# تشغيل البوت
# ==========================================

async def main():

    token = os.getenv(
        "DISCORD_TOKEN"
    )

    if not token:

        raise RuntimeError(
            "DISCORD_TOKEN غير موجود "
            "في Environment Variables"
        )

    await bot.start(
        token
    )


# ==========================================
# البداية
# ==========================================

if __name__ == "__main__":

    asyncio.run(
        main()
    )
