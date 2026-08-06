# 🎵 Music Bot - بوت تشغيل الأغاني

بوت Discord متقدم لتشغيل الأغاني والموسيقى مباشرة في الخادم الخاص بك!

## ✨ المميزات

✅ تشغيل الأغاني من YouTube  
✅ نظام قائمة انتظار متقدم  
✅ التحكم الكامل (تشغيل، إيقاف، تخطي)  
✅ عرض قائمة التشغيل  
✅ واجهة سهلة وودودة  
✅ دعم اللغة العربية

## 📋 المتطلبات

- Python 3.8+
- FFmpeg
- Discord Bot Token

## 🚀 التثبيت والتشغيل

### 1️⃣ نسخ المستودع
```bash
git clone https://github.com/xtx5051/Music-bot.git
cd Music-bot
```

### 2️⃣ تثبيت المكتبات
```bash
pip install -r requirements.txt
```

### 3️⃣ تثبيت FFmpeg

**Windows:**
```bash
choco install ffmpeg
```

**Linux:**
```bash
sudo apt-get install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

### 4️⃣ إنشاء Bot على Discord

1. اذهب إلى [Discord Developer Portal](https://discord.com/developers/applications)
2. اضغط على "New Application"
3. انسخ ال Token من صفحة "Bot"
4. أضفه في ملف `main.py` بدل `YOUR_TOKEN_HERE`

### 5️⃣ إعطاء الصلاحيات
في Discord Developer Portal، اذهب إلى OAuth2 → URL Generator:
```
- scopes: bot
- permissions: 
  - Send Messages
  - Connect
  - Speak
  - Read Message History
```

### 6️⃣ تشغيل البوت
```bash
python main.py
```

## 🎮 الأوامر

| الأمر | الوصف |
|------|-------|
| `!join` | دخول الغرفة الصوتية |
| `!leave` | مغادرة الغرفة الصوتية |
| `!play [اسم/رابط]` | تشغيل أغنية |
| `!pause` | إيقاف مؤقت |
| `!resume` | استئناف التشغيل |
| `!stop` | إيقاف التشغيل |
| `!skip` | تخطي للأغنية التالية |
| `!queue` | عرض قائمة التشغيل |
| `!help` | عرض جميع الأوامر |

## 💡 أمثلة الاستخدام

```
!join                           # دخول الغرفة الصوتية
!play اغنية ام كلثوم           # البحث عن أغنية
!play https://youtube.com/...   # تشغيل من رابط مباشر
!queue                          # عرض الأغاني المتبقية
!skip                           # تخطي للأغنية التالية
!stop                           # إيقاف التشغيل
!leave                          # الخروج من الغرفة
```

## 📝 الملفات

```
Music-bot/
├── main.py          # الملف الرئيسي للبوت
├── requirements.txt # المكتبات المطلوبة
├── .env             # ملف الإعدادات (Token)
└── README.md        # هذا الملف
```

## 🐛 حل المشاكل

### البوت لا يتصل
- تأكد من صحة Token
- تأكد من أن البوت له صلاحيات الصوت

### لا صوت بعد التشغيل
- تأكد من تثبيت FFmpeg
- حاول إعادة تشغيل البوت

### خطأ في البحث
- تأكد من الاتصال بالإنترنت
- جرب رابط مباشر من YouTube

## 📞 الدعم

إذا واجهت أي مشكلة، افتح Issue في المستودع!

## 📄 الترخيص

هذا المشروع مفتوح المصدر ومتاح للجميع.

---

**استمتع بالموسيقى! 🎶🎵**
