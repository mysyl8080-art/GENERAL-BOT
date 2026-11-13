# بوت تيليجرام الشامل

بوت Telegram متعدد الوظائف مبني باستخدام Python وaiogram 3، مع قاعدة بيانات SQLite وواجهة عربية، ومهيأ للبناء عبر Docker والنشر على Railway.

## الملفات الأساسية
- `main.py`: نقطة تشغيل البوت.
- `requirements.txt`: اعتماديات Python.
- `Dockerfile`: بيئة التشغيل والأدوات المساعدة (LibreOffice وFFmpeg وTesseract وغيرها).
- `railway.json`: إعدادات البناء والتشغيل على Railway.
- `LICENSE`: رخصة MIT.

## متطلبات التشغيل
- Python 3.12 أو Docker.
- Telegram Bot Token من @BotFather.
- بعض الميزات اختيارية وتحتاج مفاتيح API مثل `OPENAI_API_KEY` و`GOLD_API_KEY`.

## النشر على Railway
1. اختر Deploy from GitHub Repo وحدد هذا المستودع.
2. أضف `BOT_TOKEN` في Variables.
3. أضف Volume على المسار `/data`، واضبط `DATABASE_PATH=/data/bot.sqlite3`.
4. استخدم Replica واحدة لأن التطبيق يعمل بـ long polling وSQLite.
5. راجع Logs وتأكد من ظهور رسالة بدء البوت.

## تنبيه مهم حول اكتمال المشروع
ملف `main.py` يستورد وحدات من مجلد `app/` (الإعدادات، قاعدة البيانات، لوحات المفاتيح، routers والخدمات). يجب رفع مجلد `app/` وجميع ملفاته والاختبارات المطلوبة من مصدر المشروع قبل النشر؛ الملفات الأساسية وحدها لا تكفي لتشغيل البوت. لا ترفع `.env` أو أي مفاتيح سرية أو قاعدة بيانات إلى GitHub.
