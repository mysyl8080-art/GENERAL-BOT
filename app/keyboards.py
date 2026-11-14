from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

CATEGORIES={
 'الإنتاجية':['/remind','/repeat','/daily_summary','/shopping','/meet_poll','/event','/habit_add','/habits','/task','/tasks','/note'],
 'التعلّم':['/word','/word_quiz','/card','/review','/quiz'],
 'المجموعات والقنوات':['/antispam','/captcha','/allowdomain','/badword','/welcome','/poll','/schedule','/points','/weekly','/role','/roles','/suggest','/suggestions','/ticket','/tickets','/channel_stats'],
 'الأعمال':['/book','/slot_add','/slots','/book_slot','/booking_confirm','/product','/stock','/shop','/cart','/coupon_add','/coupon','/checkout','/order','/loyalty','/redeem','/rate_order','/ratings','/faq','/feedback','/requests'],
 'الذكاء الاصطناعي':['/ask','/ask_file','/quiz_from_file','/summarize','/translate','/tutor','/language','/practice','/audio_tasks','/transcribe','/speak','/idea','/favorite','/favorites','/post'],
 'الأدوات السريعة':['/currency','/crypto','/gold','/prayer','/adhkar','/qr','/short','/price_alert','/convert'],
 'الصور والوسائط':['/convert image-to-jpg','/convert image-to-webp','/convert ocr','/convert video-to-mp3','/convert video-to-gif','/convert video-compress','/convert video-cut'],
 'التسلية':['/trivia','/guess','/adventure','/joke','/quote','/daily_on','/daily_off','/random']
}

LABELS={
'/remind':'⏰ تذكير جديد','/repeat':'🔁 تذكير متكرر','/daily_summary':'📋 الملخص اليومي','/shopping':'🛒 قائمة المشتريات','/meet_poll':'🗓 استطلاع موعد','/event':'🎯 عداد الأحداث','/habit_add':'➕ إضافة عادة','/habits':'📈 متابعة العادات','/task':'✍️ إضافة مهمة','/tasks':'📝 مهامي','/note':'📒 ملاحظاتي',
'/word':'📚 مفردات','/word_quiz':'🧠 اختبار مفردات','/card':'🃏 بطاقة مراجعة','/review':'🔄 مراجعة مستحقة','/quiz':'❓ سؤال اليوم',
'/antispam':'🛡 مكافحة السبام','/captcha':'🔐 تحقق الأعضاء','/allowdomain':'🔗 روابط مسموحة','/badword':'🚫 كلمات ممنوعة','/welcome':'👋 رسالة الترحيب','/poll':'📊 إنشاء استطلاع','/schedule':'📅 جدولة منشور','/points':'⭐ النقاط','/weekly':'🏆 النشاط الأسبوعي','/role':'🎖 تعيين دور','/roles':'👥 الأدوار','/suggest':'💡 اقتراح مجهول','/suggestions':'📬 مراجعة الاقتراحات','/ticket':'🎫 تذكرة دعم','/tickets':'📥 تذاكر الدعم','/channel_stats':'📊 إحصائيات القناة',
'/book':'📅 طلب حجز','/slot_add':'➕ إضافة موعد','/slots':'🕒 المواعيد المتاحة','/book_slot':'✅ حجز موعد','/booking_confirm':'✔️ تأكيد حجز','/product':'📦 المنتجات','/stock':'📉 المخزون','/shop':'🛍 المتجر','/cart':'🧺 السلة','/coupon_add':'➕ إضافة كوبون','/coupon':'🎟 استخدام كوبون','/checkout':'💳 إتمام الطلب','/order':'📦 حالة الطلب','/loyalty':'💎 نقاط الولاء','/redeem':'🎁 استبدال النقاط','/rate_order':'⭐ تقييم الطلب','/ratings':'📊 تقييمات العملاء','/faq':'❔ الأسئلة الشائعة','/feedback':'🗣 إرسال رأي','/requests':'📨 طلبات العملاء',
'/ask':'🤖 اسأل المساعد','/ask_file':'📄 اسأل عن ملف','/quiz_from_file':'📝 اختبار من ملف','/summarize':'📰 تلخيص رابط','/translate':'🌐 ترجمة','/tutor':'🎓 شرح دراسي','/language':'🗣 لغة التدريب','/practice':'💬 ممارسة اللغة','/audio_tasks':'🎙 مهام من تسجيل صوتي','/transcribe':'✍️ تفريغ صوت','/speak':'🔊 تحويل نص لصوت','/idea':'💡 توليد أفكار','/favorite':'❤️ حفظ فكرة','/favorites':'📌 المفضلة','/post':'🖊 كتابة منشور',
'/currency':'💱 تحويل عملات','/crypto':'₿ أسعار العملات الرقمية','/gold':'🥇 سعر الذهب','/prayer':'🕌 مواقيت الصلاة','/adhkar':'📿 الأذكار','/qr':'🔳 إنشاء QR','/short':'🔗 اختصار رابط','/price_alert':'🔔 تنبيه سعر','/convert':'📂 تحويل ملفات',
'/convert image-to-jpg':'🖼 صورة إلى JPG','/convert image-to-webp':'🖼 صورة إلى WebP','/convert ocr':'🔎 استخراج النص OCR','/convert video-to-mp3':'🎵 فيديو إلى MP3','/convert video-to-gif':'🎞 فيديو إلى GIF','/convert video-compress':'🎬 ضغط فيديو','/convert video-cut':'✂️ قص فيديو',
'/trivia':'🎲 معلومات عامة','/guess':'🔢 لعبة التخمين','/adventure':'🧭 مغامرة','/joke':'😂 نكتة','/quote':'💬 اقتباس','/daily_on':'🔔 تفعيل الرسائل اليومية','/daily_off':'🔕 إيقاف الرسائل اليومية','/random':'🎯 اختيار عشوائي'
}

def main_menu():
    vals=list(CATEGORIES)
    rows=[]
    for i in range(0,len(vals),2):
        row=[InlineKeyboardButton(text=vals[i],callback_data='cat:'+str(i)+':0')]
        if i+1<len(vals): row.append(InlineKeyboardButton(text=vals[i+1],callback_data='cat:'+str(i+1)+':0'))
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)

def category_menu(idx:int,page:int=0):
    vals=list(CATEGORIES)
    if not 0<=idx<len(vals): idx=0
    label=vals[idx]; commands=CATEGORIES[label]
    page_size=8; pages=max(1,(len(commands)+page_size-1)//page_size)
    page=max(0,min(page,pages-1)); selected=commands[page*page_size:(page+1)*page_size]
    rows=[]
    for i in range(0,len(selected),2):
        row=[]
        for cmd in selected[i:i+2]:
            row.append(InlineKeyboardButton(text=LABELS.get(cmd,cmd),callback_data='cmd:'+cmd[1:]))
        rows.append(row)
    nav=[]
    if page>0: nav.append(InlineKeyboardButton(text='⬅️ السابق',callback_data=f'cat:{idx}:{page-1}'))
    if page+1<pages: nav.append(InlineKeyboardButton(text='التالي ➡️',callback_data=f'cat:{idx}:{page+1}'))
    if nav: rows.append(nav)
    rows.append([InlineKeyboardButton(text='🏠 القائمة الرئيسية',callback_data='home')])
    return InlineKeyboardMarkup(inline_keyboard=rows)
