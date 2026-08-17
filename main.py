import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os

# ==================== إعدادات البوت ====================

intents = discord.Intents.default()
intents.message_content = True

# ما نستخدم أوامر discord التقليدية بعلامة !
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

playlists = {}


class MusicPlayer:
    def __init__(self, guild_id):
        self.guild_id = guild_id
        self.queue = []
        self.current_song = None
        self.voice_client = None
        self.manual_leave = False

    def add_to_queue(self, song):
        self.queue.append(song)

    def get_next_song(self):
        if self.queue:
            return self.queue.pop(0)
        return None


# ==================== إعداد SoundCloud ====================

ydl_options = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "extract_flat": False,
}


# ==================== عند تشغيل البوت ====================

@bot.event
async def on_ready():
    print(f"البوت شغال: {bot.user}")

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="الموسيقى"
        )
    )


# ==================== الحصول على MusicPlayer ====================

def get_player(guild_id):
    if guild_id not in playlists:
        playlists[guild_id] = MusicPlayer(guild_id)

    return playlists[guild_id]


# ==================== الدخول للروم تلقائياً ====================

async def ensure_voice(ctx):
    if not ctx.author.voice:
        await ctx.send("ادخل روم صوتي أولاً.")
        return None

    channel = ctx.author.voice.channel
    voice_client = ctx.guild.voice_client

    if voice_client:

        # إذا كان البوت في روم مختلف
        if voice_client.channel.id != channel.id:
            await voice_client.move_to(channel)

        return voice_client

    try:
        voice_client = await channel.connect()
        return voice_client

    except Exception as e:
        await ctx.send(f"تعذر الدخول للروم: {e}")
        return None


# ==================== البحث في SoundCloud ====================

async def search_soundcloud(search):

    def extract():
        options = dict(ydl_options)

        with yt_dlp.YoutubeDL(options) as ydl:

            # إذا المستخدم أعطى رابط مباشر
            if search.startswith("http://") or search.startswith("https://"):
                info = ydl.extract_info(search, download=False)

            else:
                info = ydl.extract_info(
                    f"scsearch1:{search}",
                    download=False
                )

            if not info:
                return None

            if "entries" in info:
                entries = info.get("entries")

                if not entries:
                    return None

                info = entries[0]

            return {
                "url": info.get("url"),
                "title": info.get("title", "أغنية بدون اسم"),
                "duration": info.get("duration", 0),
                "webpage_url": info.get("webpage_url")
            }

    return await asyncio.to_thread(extract)


# ==================== تشغيل الأغنية التالية ====================

async def play_next(guild):

    player = playlists.get(guild.id)

    if not player:
        return

    voice_client = guild.voice_client

    if not voice_client:
        return

    song = player.get_next_song()

    # إذا خلصت القائمة
    # لا نخرج من الروم
    if not song:
        player.current_song = None
        print(f"انتهت القائمة في السيرفر {guild.id}")
        return

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
                print(f"خطأ في التشغيل: {error}")

            future = asyncio.run_coroutine_threadsafe(
                play_next(guild),
                bot.loop
            )

            try:
                future.result()
            except Exception as e:
                print(f"خطأ أثناء تشغيل الأغنية التالية: {e}")

        voice_client.play(
            audio_source,
            after=after_playing
        )

        print(f"تشغيل: {song['title']}")

        # إرسال رسالة للقناة الأصلية
        if player.last_text_channel:
            await player.last_text_channel.send(
                f"الآن يتم التشغيل: {song['title']}"
            )

    except Exception as e:

        print(f"خطأ في تشغيل الصوت: {e}")

        player.current_song = None

        # حاول تشغيل الأغنية التالية
        await play_next(guild)


# ==================== تشغيل أغنية ====================

async def play_song(ctx, search):

    voice_client = await ensure_voice(ctx)

    if not voice_client:
        return

    player = get_player(ctx.guild.id)
    player.voice_client = voice_client
    player.last_text_channel = ctx.channel

    await ctx.send(f"جاري البحث عن: {search}")

    try:

        song = await search_soundcloud(search)

        if not song:
            await ctx.send("لم يتم العثور على الأغنية.")
            return

        player.add_to_queue(song)

        position = len(player.queue)

        await ctx.send(
            f"تمت إضافة الأغنية: {song['title']}\n"
            f"موقعها في القائمة: {position}"
        )

        # إذا ما فيه شيء شغال
        if not voice_client.is_playing() and not voice_client.is_paused():

            await play_next(ctx.guild)

    except Exception as e:

        print(f"خطأ SoundCloud: {e}")

        await ctx.send(
            f"حدث خطأ أثناء البحث: {e}"
        )


# ==================== إيقاف مؤقت ====================

async def pause_music(ctx):

    voice_client = ctx.guild.voice_client

    if voice_client and voice_client.is_playing():

        voice_client.pause()

        await ctx.send("تم الإيقاف المؤقت.")

    else:

        await ctx.send("لا توجد أغنية قيد التشغيل.")


# ==================== استئناف ====================

async def resume_music(ctx):

    voice_client = ctx.guild.voice_client

    if voice_client and voice_client.is_paused():

        voice_client.resume()

        await ctx.send("تم استئناف التشغيل.")

    else:

        await ctx.send("لا توجد أغنية موقوفة.")


# ==================== تخطي ====================

async def skip_music(ctx):

    voice_client = ctx.guild.voice_client

    if voice_client and (
        voice_client.is_playing()
        or voice_client.is_paused()
    ):

        voice_client.stop()

        await ctx.send("تم تخطي الأغنية.")

    else:

        await ctx.send("لا توجد أغنية قيد التشغيل.")


# ==================== إيقاف ومسح القائمة ====================

async def stop_music(ctx):

    voice_client = ctx.guild.voice_client
    player = get_player(ctx.guild.id)

    player.queue.clear()
    player.current_song = None

    if voice_client:

        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop()

    await ctx.send("تم إيقاف التشغيل ومسح القائمة.")


# ==================== عرض القائمة ====================

async def show_queue(ctx):

    player = get_player(ctx.guild.id)

    lines = []

    if player.current_song:

        lines.append(
            f"يعمل الآن: {player.current_song['title']}"
        )

    if player.queue:

        for i, song in enumerate(player.queue[:10], 1):

            lines.append(
                f"{i}. {song['title']}"
            )

    if not lines:

        await ctx.send("القائمة فارغة.")
        return

    await ctx.send(
        "قائمة التشغيل:\n" +
        "\n".join(lines)
    )


# ==================== الخروج ====================

async def leave_voice(ctx):

    voice_client = ctx.guild.voice_client
    player = get_player(ctx.guild.id)

    if not voice_client:

        await ctx.send("البوت غير موجود في روم صوتي.")
        return

    player.manual_leave = True
    player.queue.clear()
    player.current_song = None

    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()

    await voice_client.disconnect()

    await ctx.send("تم الخروج من الروم.")


# ==================== استقبال الأوامر العربية ====================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if not message.guild:
        return

    content = message.content.strip()

    # ==================== ش = تشغيل ====================

    if content.startswith("ش"):

        search = content[1:].strip()

        if not search:
            await message.channel.send(
                "اكتب اسم الأغنية بعد ش."
            )
            return

        ctx = await bot.get_context(message)

        await play_song(ctx, search)

        return

    # ==================== و = إيقاف مؤقت ====================

    if content == "و":

        ctx = await bot.get_context(message)

        await pause_music(ctx)

        return

    # ==================== ك = استئناف ====================

    if content == "ك":

        ctx = await bot.get_context(message)

        await resume_music(ctx)

        return

    # ==================== س = تخطي ====================

    if content == "س":

        ctx = await bot.get_context(message)

        await skip_music(ctx)

        return

    # ==================== ق = إيقاف ومسح ====================

    if content == "ق":

        ctx = await bot.get_context(message)

        await stop_music(ctx)

        return

    # ==================== ل = القائمة ====================

    if content == "ل":

        ctx = await bot.get_context(message)

        await show_queue(ctx)

        return

    # ==================== خ = خروج ====================

    if content == "خ":

        ctx = await bot.get_context(message)

        await leave_voice(ctx)

        return


# ==================== تشغيل البوت ====================

token = os.getenv("DISCORD_TOKEN")

if not token:
    raise RuntimeError(
        "DISCORD_TOKEN غير موجود في Environment Variables"
    )

bot.run(token)
