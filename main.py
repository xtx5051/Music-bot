# الردود التلقائية
@bot.event
async def on_message(message):
    # تجاهل رسائل البوت نفسه
    if message.author.bot:
        return

    text = message.content.strip()

    responses = {
        "يا جابر": "وا ايري",
        "يا قمنو": "ايري في",
        "بو مشاري": "زبي في أستك",
    }

    if text in responses:
        await message.channel.send(responses[text])

    # تشغيل أوامر البوت
    await bot.process_commands(message)
