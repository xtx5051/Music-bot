import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os
from datetime import timedelta

# =========================
# إعدادات البوت
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


# =========================
# مشغل الموسيقى
# =========================

class MusicPlayer:
    def __init__(self, guild_id):
        self.guild_id = guild_id
        self.queue = []
        self.current_song = None
        self.voice_client = None
        self.is_idle = False


# =========================
# إعداد yt-dlp
# =========================

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


# =========================
# عند تشغيل البوت
# =========================

@bot.event
async def on_ready():
    print(f"البوت شغال: {bot.user}")

    channel = bot.get_channel(VOICE_CHANNEL_ID)

    if channel is None:
        print("❌ لم يتم العثور على الروم الصوتي")
        return

    if not isinstance(channel, discord.VoiceChannel):
        print("❌ الـ ID المضاف ليس رومًا صوتيًا")
        return

    player = playlists.get(channel.guild.id)

    if player is None:
        player = MusicPlayer(channel.guild.id)
        playlists[channel.guild.id] = player

    try:
        voice_client = discord.utils.get(
            bot.voice_clients,
            guild=channel.guild
        )

        if voice_client:
            if voice_client.channel.id != VOICE_CHANNEL_ID:
                await voice_client.move_to(channel)
        else:
            voice_client = await channel.connect()

        player.voice_client = voice_client

        print(f"✅ تم الدخول للروم: {channel.name}")
        # شغل موسيقى الخلفية
        await play_idle_music(channel.guild.id, voice_client)

    except discord.Forbidden:
        print(f"❌ البوت ما عنده صلاحية الدخول للروم الصوتي")
    except discord.ClientException as e:
        print(f"❌ خطأ الاتصال: {e}")
    except Exception as e:
        print(f"❌ خطأ غير متوقع: {type(e).__name__}: {e}")


# =========================
# تشغيل صوت لاستمرار الاتصال (جاب من YouTube)
# =========================

async def play_idle_music(guild_id, voice_client):
    """تشغيل فيديو طويل من YouTube بصوت طبيعي"""
    
    if not voice_client or not voice_client.is_connected():
        return

    player = playlists.get(guild_id)
    if not player:
        return

    try:
        # فيديو طويل جداً من YouTube (موسيقى هادئة)
        idle_url = "https://www.youtube.com/watch?v=5qap5aO4i9A"
        
        print(f"🔍 جاري تحميل الفيديو للحفاظ على الاتصال...")
        
        with yt_dlp.YoutubeDL(ydl_options) as ydl:
            try:
                info = ydl.extract_info(idle_url, download=False)
                url = info.get("url")
                
                if not url:
                    print("❌ فشل في الحصول على رابط الفيديو")
                    return
                
            except Exception as e:
                print(f"❌ خطأ في تحميل الفيديو: {e}")
                return
        
        audio_source = discord.FFmpegPCMAudio(
            url,
            before_options=(
                "-reconnect 1 "
                "-reconnect_streamed 1 "
                "-reconnect_delay_max 5"
            ),
            options="-vn -filter:a 'volume=0.1'"  # صوت 10% (مسموع قليل)
        )
        
        def after_idle_playing(error):
            if error:
                print(f"⚠️ خطأ في الموسيقى: {error}")
            else:
                print(f"🔄 انتهت الموسيقى، إعادة تشغيل...")
            
            # أعد التشغيل
            if not bot.is_closed():
                asyncio.run_coroutine_threadsafe(
                    play_idle_music(guild_id, voice_client),
                    bot.loop
                )
        
        if not voice_client.is_playing():
            voice_client.play(audio_source, after=after_idle_playing)
            player.is_idle = True
            print(f"🎵 تم تشغيل الموسيقى المستمرة")
        else:
            print(f"⚠️ هناك موسيقى تشتغل بالفعل")

    except Exception as e:
        print(f"❌ خطأ في play_idle_music: {e}")


# =========================
# إعادة الاتصال بالروم
# =========================

async def keep_connected():
    await bot.wait_until_ready()
    print("🔄 بدء عملية الحفاظ على الاتصال...")

    while not bot.is_closed():
        try:
            channel = bot.get_channel(VOICE_CHANNEL_ID)

            if channel is not None:
                voice_client = discord.utils.get(
                    bot.voice_clients,
                    guild=channel.guild
                )

                # لم يكن متصل
                if voice_client is None or not voice_client.is_connected():
                    print("❌ البوت غير متصل، محاولة الاتصال...")
                    try:
                        voice_client = await channel.connect()
                        player = playlists.get(channel.guild.id)
                        if player:
                            player.voice_client = voice_client
                        print(f"✅ تم الاتصال بـ {channel.name}")
                        
                        # شغل الموسيقى
                        await play_idle_music(channel.guild.id, voice_client)
                        
                    except discord.Forbidden:
                        print("❌ البوت ما عنده صلاحية")
                    except discord.ClientException:
                        print("⚠️ البوت موجود في روم آخر")
                    except Exception as e:
                        print(f"❌ خطأ في الاتصال: {e}")

                # متصل ولكن في روم مختلف
                elif voice_client.channel.id != VOICE_CHANNEL_ID:
                    try:
                        await voice_client.move_to(channel)
                        print(f"📍 تم النقل إلى {channel.name}")
                    except Exception as e:
                        print(f"⚠️ خطأ النقل: {e}")
                
                # متصل في الروم الصحيح
                else:
                    # تأكد من التشغيل
                    if not voice_client.is_playing():
                        print("⏸️ لا توجد موسيقى تشغالة، شغل الآن...")
                        player = playlists.get(channel.guild.id)
                        if player:
                            player.voice_client = voice_client
                            await play_idle_music(channel.guild.id, voice_client)

        except Exception as e:
            print(f"⚠️ خطأ في keep_connected: {e}")

        # تحقق كل 10 ثوان
        await asyncio.sleep(10)


# =========================
# البحث عن أغنية
# =========================

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
            if not info["entries"]:
                return None

            info = info["entries"][0]

        return {
            "url": info["url"],
            "title": info.get("title", "أغنية بدون اسم"),
            "duration": info.get("duration", 0)
        }


# =========================
# تشغيل الأغنية التالية
# =========================

async def play_next(guild_id, channel):

    player = playlists.get(guild_id)

    if not player:
        return

    if not player.queue:
        player.current_song = None
        # شغل الموسيقى الخلفية
        voice_client = player.voice_client
        if voice_client and voice_client.is_connected():
            await play_idle_music(guild_id, voice_client)
        return

    voice_client = player.voice_client

    if voice_client is None or not voice_client.is_connected():
        return

    song = player.queue.pop(0)
    player.current_song = song
    player.is_idle = False

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
                print(f"❌ خطأ في التشغيل: {error}")

            asyncio.run_coroutine_threadsafe(
                play_next(guild_id, channel),
                bot.loop
            )

        voice_client.play(
            audio_source,
            after=after_playing
        )

        asyncio.run_coroutine_threadsafe(
            channel.send(f"🎵 الآن يتم التشغيل: {song['title']}"),
            bot.loop
        )

    except Exception as e:
        print(f"❌ خطأ في تشغيل الأغنية: {e}")
        player.current_song = None
        asyncio.run_coroutine_threadsafe(
            play_next(guild_id, channel),
            bot.loop
        )


# =========================
# أمر تشغيل الأغنية
# ش اسم الأغنية
# =========================

@bot.command(name="ش")
async def play_command(ctx, *, search=None):

    if not search:
        await ctx.send("⚠️ اكتب اسم الأغنية بعد ش")
        return

    channel = bot.get_channel(VOICE_CHANNEL_ID)

    if channel is None:
        await ctx.send("❌ لم يتم العثور على الروم الصوتي")
        return

    player = playlists.get(ctx.guild.id)

    if player is None:
        player = MusicPlayer(ctx.guild.id)
        playlists[ctx.guild.id] = player

    voice_client = player.voice_client

    if voice_client is None or not voice_client.is_connected():
        try:
            voice_client = await channel.connect()
            player.voice_client = voice_client
            print(f"✅ تم الاتصال بـ {channel.name}")

        except discord.Forbidden:
            await ctx.send("❌ البوت ما عنده صلاحية الدخول للروم الصوتي")
            return

        except discord.ClientException:
            await ctx.send("❌ البوت موجود في روم آخر")
            return

        except Exception as e:
            await ctx.send(f"❌ خطأ الاتصال: {type(e).__name__}")
            return

    await ctx.send(f"🔍 جاري البحث عن: {search}")

    try:

        song = await asyncio.to_thread(get_song, search)

        if song is None:
            await ctx.send("❌ لم يتم العثور على الأغنية")
            return

        player.queue.append(song)

        duration = song["duration"] or 0
        duration_str = str(timedelta(seconds=int(duration)))

        await ctx.send(
            f"✅ تمت إضافة: {song['title']}\n"
            f"⏱️ المدة: {duration_str}\n"
            f"⏳ في الانتظار: {len(player.queue)}"
        )

        # إيقاف الموسيقى الخلفية وتشغيل الأغنية
        if voice_client.is_playing() or player.is_idle:
            voice_client.stop()
        
        await play_next(ctx.guild.id, ctx.channel)

    except Exception as e:
        await ctx.send(f"❌ حدث خطأ: {type(e).__name__}")
        print(f"❌ Search error: {e}")


# =========================
# س = تخطي
# =========================

@bot.command(name="س")
async def skip_command(ctx):

    player = playlists.get(ctx.guild.id)

    if not player or not player.voice_client:
        await ctx.send("⚠️ ما فيه أغنية شغالة")
        return

    voice_client = player.voice_client

    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()
        await ctx.send("✅ تم التخطي")
    else:
        await ctx.send("⚠️ ما فيه أغنية شغالة")


# =========================
# و = إيقاف
# =========================

@bot.command(name="و")
async def stop_command(ctx):

    player = playlists.get(ctx.guild.id)

    if not player or not player.voice_client:
        await ctx.send("⚠️ ما فيه أغنية شغالة")
        return

    voice_client = player.voice_client

    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()
        player.queue.clear()
        player.current_song = None
        await ctx.send("✅ تم إيقاف التشغيل وحذف قائمة الانتظار")
        
        # شغل الموسيقى الخلفية
        await play_idle_music(ctx.guild.id, voice_client)
    else:
        await ctx.send("⚠️ ما فيه أغنية شغالة")


# =========================
# ب = إيقاف مؤقت
# =========================

@bot.command(name="ب")
async def pause_command(ctx):

    player = playlists.get(ctx.guild.id)

    if player and player.voice_client:
        if player.voice_client.is_playing():
            player.voice_client.pause()
            await ctx.send("✅ تم الإيقاف المؤقت")
            return

    await ctx.send("⚠️ ما فيه أغنية شغالة")


# =========================
# ت = استئناف
# =========================

@bot.command(name="ت")
async def resume_command(ctx):

    player = playlists.get(ctx.guild.id)

    if player and player.voice_client:
        if player.voice_client.is_paused():
            player.voice_client.resume()
            await ctx.send("✅ تم استئناف التشغيل")
            return

    await ctx.send("⚠️ ما فيه أغنية موقوفة")


# =========================
# ع = قائمة الانتظار
# =========================

@bot.command(name="ع")
async def queue_command(ctx):

    player = playlists.get(ctx.guild.id)

    if not player or not player.queue:
        await ctx.send("📭 قائمة الانتظار فارغة")
        return

    message = "📋 قائمة الانتظار:\n\n"

    for i, song in enumerate(player.queue[:10], 1):
        message += f"{i}. {song['title']}\n"

    if len(player.queue) > 10:
        message += f"\nو {len(player.queue) - 10} أغاني أخرى"

    await ctx.send(message)


# =========================
# م = المساعدة
# =========================

@bot.command(name="م")
async def help_command(ctx):

    message = """
📖 **أوامر البوت:**

**ش** اسم الأغنية → تشغيل أغنية
**س** → تخطي الأغنية
**و** → إيقاف التشغيل وحذف الانتظار
**ب** → إيقاف مؤقت
**ت** → استئناف التشغيل
**ع** → عرض قائمة الانتظار

ℹ️ البوت يبقى في الروم بشكل دائم ويحافظ على الاتصال
"""

    await ctx.send(message)


# =========================
# تشغيل البوت
# =========================

async def main():
    token = os.getenv("DISCORD_TOKEN")

    if not token:
        raise RuntimeError(
            "❌ لم يتم العثور على DISCORD_TOKEN في Environment Variables"
        )

    asyncio.create_task(keep_connected())
    await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
