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

def main_menu():
    rows=[]
    vals=list(CATEGORIES)
    for i in range(0,len(vals),2):
        row=[InlineKeyboardButton(text=vals[i],callback_data='cat:'+str(i))]
        if i+1<len(vals): row.append(InlineKeyboardButton(text=vals[i+1],callback_data='cat:'+str(i+1)))
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)

def category_menu(idx:int):
    vals=list(CATEGORIES)
    label=vals[idx] if 0<=idx<len(vals) else vals[0]
    commands=CATEGORIES[label]
    rows=[[InlineKeyboardButton(text=c,callback_data='cmd:'+c[1:])] for c in commands]
    rows.append([InlineKeyboardButton(text='القائمة الرئيسية',callback_data='home')])
    return InlineKeyboardMarkup(inline_keyboard=rows)
