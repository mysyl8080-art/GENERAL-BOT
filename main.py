from __future__ import annotations
import asyncio, logging, random, re, requests
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, BotCommand
from app.config import settings, validate
from app.db import connection, init_db
from app.keyboards import main_menu, category_menu, CATEGORIES
from app.routers_productivity import router as productivity_router
from app.routers_learning import router as learning_router
from app.routers_community_business import router as community_router
from app.routers_ai_tools import router as tools_router, JOKES, QUOTES
from app.routers_media import router as media_router
from app.routers_extra_productivity import router as extra_productivity_router
from app.routers_extra_groups import router as extra_groups_router
from app.routers_extra_business import router as extra_business_router
from app.routers_extra_ai import router as extra_ai_router
from app.services.common import safe_url

logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s: %(message)s')
log=logging.getLogger('telegram-superbot')
root=Router()

@root.message(CommandStart())
async def start(m:Message):
    await m.answer('أهلًا بك في بوت الأدوات الشامل!\n\nمن القائمة اختر المجال، أو اكتب /help لعرض كل الأوامر.\n\nملاحظة: بعض خدمات الذكاء الاصطناعي وأسعار المعادن تحتاج مفاتيح API اختيارية.',reply_markup=main_menu())

@root.message(Command('menu'))
async def menu(m:Message): await m.answer('اختر القسم:',reply_markup=main_menu())

@root.message(Command('help'))
async def help_cmd(m:Message):
    text='''الأوامر المتاحة:
الإنتاجية: /remind /repeat /daily_summary /shopping /meet_poll /event /habit_add /habit_done /habits /task /tasks /note
التعلّم: /word /word_quiz /card /review /quiz /leaderboard
المجموعات والقنوات: /antispam /captcha /allowdomain /badword /welcome /poll /meet_poll /schedule /points /weekly /role /suggest /ticket /channel_stats
الأعمال: /book /slot_add /slots /book_slot /product /stock /shop /cart /checkout /coupon /coupon_add /order /loyalty /redeem /rate_order /faq /feedback /requests
الذكاء الاصطناعي: /ask /ask_file /quiz_from_file /language /practice /audio_tasks /idea /favorite /post /summarize /translate /tutor /transcribe /speak
الأدوات: /currency /crypto /gold /prayer /adhkar /qr /short /price_alert /convert
التسلية: /trivia /guess /adventure /joke /quote /daily_on /daily_off /random

استخدم /menu للواجهة التفاعلية. كل التحويلات في /convert.'''
    await m.answer(text)

@root.callback_query(F.data=='home')
async def back_home(c:CallbackQuery): await c.message.edit_text('اختر القسم:',reply_markup=main_menu()); await c.answer()

@root.callback_query(F.data.startswith('cat:'))
async def category(c:CallbackQuery):
    try:
        _,raw_idx,raw_page=c.data.split(':',2)
        idx,page=int(raw_idx),int(raw_page)
    except (ValueError,AttributeError):
        idx,page=0,0
    vals=list(CATEGORIES)
    if not 0<=idx<len(vals): idx=0
    name=vals[idx]
    await c.message.edit_text(f'{name}\\nاختر الخدمة، وستظهر لك طريقة استخدامها.',reply_markup=category_menu(idx,page)); await c.answer()

@root.callback_query(F.data.startswith('cmd:'))
async def command_help(c:CallbackQuery):
    cmd=c.data.split(':',1)[1]
    # Execute read-only / no-argument actions directly from the menu.
    try:
        if cmd=='adhkar':
            adhkar_items=['سبحان الله وبحمده، سبحان الله العظيم.','أستغفر الله وأتوب إليه.','اللهم صل وسلم على نبينا محمد.','لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير.','حسبي الله لا إله إلا هو عليه توكلت وهو رب العرش العظيم.']
            await c.message.answer('ذكر اليوم: '+random.choice(adhkar_items)); await c.answer(); return
        if cmd=='joke':
            await c.message.answer(random.choice(JOKES)); await c.answer(); return
        if cmd=='quote':
            await c.message.answer(random.choice(QUOTES)); await c.answer(); return
        if cmd=='prayer':
            r=await asyncio.to_thread(requests.get,'https://api.aladhan.com/v1/timingsByCity',params={'city':'Cairo','country':'Egypt','method':5},timeout=15)
            r.raise_for_status(); timings=r.json()['data']['timings']
            names=[('Fajr','الفجر'),('Sunrise','الشروق'),('Dhuhr','الظهر'),('Asr','العصر'),('Maghrib','المغرب'),('Isha','العشاء')]
            await c.message.answer('مواقيت الصلاة — القاهرة:\\n'+'\\n'.join(f'{ar}: {timings[key]}' for key,ar in names)); await c.answer(); return
        if cmd=='tasks':
            with connection() as db: rows=db.execute('SELECT id,text FROM tasks WHERE chat_id=? AND done=0 ORDER BY id DESC LIMIT 30',(c.message.chat.id,)).fetchall()
            await c.message.answer(('المهام المفتوحة:\\n'+'\\n'.join(f'#{r["id"]} — {r["text"]}' for r in rows)) if rows else 'لا توجد مهام مفتوحة.'); await c.answer(); return
        if cmd=='habits':
            with connection() as db: rows=db.execute('SELECT h.name,COUNT(l.id) n FROM habits h LEFT JOIN habit_logs l ON l.habit_id=h.id AND l.day>=date("now","-6 days") WHERE h.user_id=? GROUP BY h.id',(c.from_user.id,)).fetchall()
            await c.message.answer(('عاداتك خلال آخر 7 أيام:\\n'+'\\n'.join(f'• {r["name"]}: {r["n"]}/7' for r in rows)) if rows else 'لا توجد عادات. اضغط «إضافة عادة» لإنشاء واحدة.'); await c.answer(); return
        if cmd=='note':
            with connection() as db:
                db.execute('CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY,user_id INTEGER,text TEXT,created_at TEXT)')
                rows=db.execute('SELECT text FROM notes WHERE user_id=? ORDER BY id DESC LIMIT 10',(c.from_user.id,)).fetchall()
            await c.message.answer(('آخر ملاحظاتك:\\n'+'\\n'.join('• '+r['text'] for r in rows)) if rows else 'لا توجد ملاحظات محفوظة. لإضافة ملاحظة أرسل /note نص الملاحظة.'); await c.answer(); return
        if cmd=='favorites':
            with connection() as db: rows=db.execute('SELECT id,text FROM idea_favorites WHERE user_id=? ORDER BY id DESC LIMIT 20',(c.from_user.id,)).fetchall()
            await c.message.answer(('أفكارك المفضلة:\\n'+'\\n'.join(f'#{r["id"]}: {r["text"]}' for r in rows)) if rows else 'لا توجد أفكار محفوظة.'); await c.answer(); return
    except Exception as e:
        log.exception('Menu quick action failed: %s',cmd)
        await c.answer('حصل خطأ أثناء تنفيذ الخدمة. حاول مرة أخرى.',show_alert=True)
        return
    help_map={
      'remind':'/remind بعد ساعتين | نص التذكير','repeat':'/repeat daily 09:00 | نص أو /repeat weekly fri 17:00 | نص','daily_summary':'/daily_summary 20:00 (خاص) أو /daily_summary off','shopping':'/shopping add حليب؛ /shopping list أو /shopping done رقم','meet_poll':'/meet_poll اختروا الموعد | السبت 10:00 | الأحد 15:00','event':'/event 2026-12-01 18:00 | اسم المناسبة؛ /event list','habit_add':'/habit_add اسم العادة، ثم /habit_done اسمها','habits':'/habits لمتابعة العادات','task':'/task نص المهمة أو /task done رقم','tasks':'/tasks','note':'/note نص أو /note list',
      'word':'/word add كلمة | ترجمة، /word list','word_quiz':'/word_quiz','card':'/card add سؤال | إجابة','review':'/review','quiz':'/quiz سؤال ثقافي يومي','antispam':'داخل المجموعة: /antispam on أو off','captcha':'داخل المجموعة: /captcha on أو off (مشرف)','allowdomain':'/allowdomain add example.com','badword':'/badword add كلمة','welcome':'داخل المجموعة: /welcome نص الترحيب، واستخدم {name}','poll':'/poll سؤال | اختيار 1 | اختيار 2','schedule':'/schedule YYYY-MM-DD HH:MM | نص المنشور','points':'/points ترتيب تراكمي','weekly':'/weekly نشاط وأدوار آخر 7 أيام','role':'رد على رسالة عضو: /role اسم_الدور','roles':'/roles','suggest':'/suggest اقتراح (مجهول للمجموعة)','suggestions':'/suggestions للمشرفين','ticket':'خاص: /ticket وصف المشكلة','tickets':'/tickets للمسؤول','ticket_reply':'/ticket_reply رقم | الرد','ticket_close':'/ticket_close رقم','ticket_rate':'/ticket_rate رقم 1-5','channel_stats':'/channel_stats بعد جعل البوت مشرفًا بالقناة',
      'book':'/book الخدمة | موعد','slot_add':'/slot_add خدمة | موعد (مدير)','slots':'/slots','book_slot':'/book_slot رقم','booking_confirm':'/booking_confirm رقم','product':'/product add اسم | سعر | وصف','stock':'/stock رقم | كمية | حد تنبيه','shop':'/shop','cart':'/cart add رقم أو /cart','coupon_add':'/coupon_add CODE | نسبة | استخدامات | YYYY-MM-DD','coupon':'/coupon CODE','checkout':'/checkout','order':'/order رقم؛ وللمسؤول /order رقم | shipped','loyalty':'/loyalty','redeem':'/redeem 100','rate_order':'/rate_order رقم | 5 | تعليق','ratings':'/ratings (مسؤول)','faq':'/faq السؤال أو /faq add سؤال | جواب','feedback':'/feedback نص','requests':'/requests (مسؤول)',
      'summarize':'/summarize رابط مقال أو YouTube','ask':'/ask سؤالك','ask_file':'أرسل مستندًا مع تعليق /ask_file سؤالك','quiz_from_file':'أرسل مستندًا مع تعليق /quiz_from_file','translate':'/translate English | النص','tutor':'/tutor اشرح الدرس','language':'/language English','practice':'/practice جملتك باللغة التي تتعلمها','audio_tasks':'أرسل رسالة صوتية مع تعليق /audio_tasks','idea':'/idea نوع | مجال','favorite':'/favorite نص الفكرة','favorites':'/favorites','post':'/post موضوع | نبرة','transcribe':'أرسل صوتًا مع تعليق /transcribe','speak':'/speak النص',
      'currency':'/currency 100 USD EGP','crypto':'/crypto bitcoin','gold':'/gold (يتطلب GOLD_API_KEY)','prayer':'/prayer القاهرة','adhkar':'/adhkar','qr':'/qr النص','short':'/short https://example.com','price_alert':'/price_alert رابط | سعر مستهدف','convert':'أرسل ملفًا مع تعليق /convert نوع-التحويل','trivia':'/trivia','guess':'/guess رقم بين 1 و20','adventure':'/adventure','joke':'/joke','quote':'/quote','daily_on':'/daily_on','daily_off':'/daily_off','random':'/random movie أو /random restaurant'
    }
    help_map.update({
      'ask_file':'أرسل الملف كمرفق، واكتب في التعليق: /ask_file ثم سؤالك. المدعوم PDF وDOCX وTXT وMD وCSV.',
      'quiz_from_file':'أرسل الملف كمرفق واكتب في التعليق: /quiz_from_file لإنشاء اختبار منه.',
      'audio_tasks':'أرسل رسالة صوتية واكتب في التعليق /audio_tasks لاستخراج المهام منها.',
      'convert image-to-jpg':'أرسل الصورة مع التعليق: /convert image-to-jpg',
      'convert image-to-webp':'أرسل الصورة مع التعليق: /convert image-to-webp',
      'convert ocr':'أرسل صورة أو PDF مع التعليق: /convert ocr',
      'convert video-to-mp3':'أرسل الفيديو مع التعليق: /convert video-to-mp3',
      'convert video-to-gif':'أرسل الفيديو مع التعليق: /convert video-to-gif',
      'convert video-compress':'أرسل الفيديو مع التعليق: /convert video-compress',
      'convert video-cut':'أرسل الفيديو مع التعليق: /convert video-cut'
    })
    await c.answer()
    await c.message.answer(help_map.get(cmd,f'استخدم الأمر: /{cmd}'),disable_web_page_preview=True)

async def scheduled_worker(bot:Bot):
    while True:
        try:
            now=datetime.now(timezone.utc).isoformat()
            with connection() as db:
                reminders=db.execute('SELECT id,user_id,chat_id,text FROM reminders WHERE sent=0 AND due_at<=? ORDER BY due_at LIMIT 50',(now,)).fetchall()
                posts=db.execute('SELECT id,chat_id,text FROM scheduled_posts WHERE sent=0 AND due_at<=? ORDER BY due_at LIMIT 30',(now,)).fetchall()
            for row in reminders:
                try:
                    await bot.send_message(row['chat_id'],f'تذكير: {row["text"]}')
                    with connection() as db: db.execute('UPDATE reminders SET sent=1 WHERE id=?',(row['id'],))
                except Exception as e: log.warning('Reminder send failed id=%s: %s',row['id'],e)
            for row in posts:
                try:
                    await bot.send_message(row['chat_id'],row['text'])
                    with connection() as db: db.execute('UPDATE scheduled_posts SET sent=1 WHERE id=?',(row['id'],))
                except Exception as e:
                    log.warning('Scheduled post failed id=%s: %s',row['id'],e)
                    with connection() as db: db.execute('UPDATE scheduled_posts SET sent=1 WHERE id=?',(row['id'],))
            from zoneinfo import ZoneInfo
            local_now=datetime.now(ZoneInfo(settings.timezone)); local_day=local_now.date().isoformat()
            daily=[]
            if local_now.hour>=9:
                with connection() as db:
                    daily=db.execute('SELECT user_id,chat_id FROM daily_subscriptions WHERE last_sent<>? OR last_sent=""',(local_day,)).fetchall()
            for sub in daily:
                    try:
                        content=(random.choice(JOKES) if datetime.now().timetuple().tm_yday%2 else random.choice(QUOTES))
                        await bot.send_message(sub['chat_id'],'رسالتك اليومية: '+content)
                        with connection() as db: db.execute('UPDATE daily_subscriptions SET last_sent=? WHERE user_id=? AND chat_id=?',(local_day,sub['user_id'],sub['chat_id']))
                    except Exception as e: log.warning('Daily send failed for %s: %s',sub['user_id'],e)
            await feature_worker_tick(bot)
            await price_alerts_worker_tick(bot)
        except Exception: log.exception('Background worker iteration failed')
        await asyncio.sleep(30)

async def feature_worker_tick(bot:Bot):
    from zoneinfo import ZoneInfo
    local_now=datetime.now(ZoneInfo(settings.timezone)); local_date=local_now.date().isoformat(); clock=local_now.strftime('%H:%M')
    with connection() as db: summaries=db.execute('SELECT user_id,chat_id,send_time FROM daily_summaries WHERE last_sent<>?',(local_date,)).fetchall()
    for sub in summaries:
        if clock<sub['send_time']: continue
        try:
            with connection() as db:
                tasks=db.execute('SELECT text FROM tasks WHERE owner_id=? AND done=0 ORDER BY id DESC LIMIT 12',(sub['user_id'],)).fetchall()
                habits=db.execute('SELECT h.id,h.name FROM habits h WHERE h.user_id=? AND NOT EXISTS (SELECT 1 FROM habit_logs l WHERE l.habit_id=h.id AND l.day=date("now"))',(sub['user_id'],)).fetchall()
                reminders=db.execute('SELECT text,due_at FROM reminders WHERE user_id=? AND sent=0 AND due_at>? ORDER BY due_at LIMIT 10',(sub['user_id'],datetime.now(timezone.utc).isoformat())).fetchall()
            lines=['ملخصك اليومي:']
            lines.append('المهام المفتوحة: '+(', '.join(r['text'] for r in tasks) if tasks else 'لا توجد.'))
            lines.append('عادات لم تُسجل اليوم: '+(', '.join(r['name'] for r in habits) if habits else 'أكملت عاداتك أو لا توجد عادات.'))
            lines.append('التذكيرات القادمة: '+(', '.join(f'{r["text"]} ({r["due_at"][:16]})' for r in reminders) if reminders else 'لا توجد.'))
            await bot.send_message(sub['chat_id'],'\n'.join(lines)[:3900])
            with connection() as db: db.execute('UPDATE daily_summaries SET last_sent=? WHERE user_id=? AND chat_id=?',(local_date,sub['user_id'],sub['chat_id']))
        except Exception as e: log.warning('Daily summary failed for %s: %s',sub['user_id'],e)
    weekday=['mon','tue','wed','thu','fri','sat','sun'][local_now.weekday()]
    with connection() as db: recurring=db.execute('SELECT id,user_id,chat_id,rule,send_time,text FROM recurring_reminders WHERE active=1 AND last_sent<>?',(local_date,)).fetchall()
    for item in recurring:
        if clock<item['send_time']: continue
        rule=item['rule']; matches=rule=='daily' or rule==f'weekly:{weekday}' or rule==f'monthly:{local_now.day}'
        if not matches: continue
        try:
            await bot.send_message(item['chat_id'],'تذكير متكرر: '+item['text'])
            with connection() as db: db.execute('UPDATE recurring_reminders SET last_sent=? WHERE id=?',(local_date,item['id']))
        except Exception as e: log.warning('Recurring reminder failed id=%s: %s',item['id'],e)
    now_utc=datetime.now(timezone.utc)
    with connection() as db: events=db.execute('SELECT id,chat_id,title,event_at FROM countdown_events WHERE reminded=0 AND event_at>? AND event_at<=?',(now_utc.isoformat(),(now_utc+timedelta(hours=24)).isoformat())).fetchall()
    for event in events:
        try:
            due=datetime.fromisoformat(event['event_at']); hours=max(0,int((due-now_utc).total_seconds()//3600))
            await bot.send_message(event['chat_id'],f'تذكير بالحدث «{event["title"]}»: متبقٍ نحو {hours} ساعة.')
            with connection() as db: db.execute('UPDATE countdown_events SET reminded=1 WHERE id=?',(event['id'],))
        except Exception as e: log.warning('Countdown reminder failed id=%s: %s',event['id'],e)
    with connection() as db: expired=db.execute('SELECT chat_id,user_id FROM captcha_challenges WHERE expires_at<=?',(now_utc.isoformat(),)).fetchall()
    for challenge in expired:
        try:
            await bot.ban_chat_member(challenge['chat_id'],challenge['user_id'])
            await bot.unban_chat_member(challenge['chat_id'],challenge['user_id'],only_if_banned=True)
        except Exception as e: log.warning('Could not remove expired captcha member: %s',e)
        finally:
            with connection() as db: db.execute('DELETE FROM captcha_challenges WHERE chat_id=? AND user_id=?',(challenge['chat_id'],challenge['user_id']))

async def price_alerts_worker_tick(bot):
    if not hasattr(price_alerts_worker_tick,'last'): price_alerts_worker_tick.last=0
    import time
    if time.time()-price_alerts_worker_tick.last<settings.price_check_minutes*60: return
    price_alerts_worker_tick.last=time.time()
    with connection() as db: rows=db.execute('SELECT id,user_id,url,target FROM price_alerts WHERE active=1 ORDER BY id LIMIT 20').fetchall()
    for row in rows:
        try:
            if not safe_url(row['url']): continue
            r=requests.get(row['url'],headers={'User-Agent':'Mozilla/5.0 (compatible; TelegramSuperBot/1.0)'},timeout=12,stream=True,allow_redirects=False)
            if r.status_code!=200: continue
            body=next(r.iter_content(300000),b'').decode('utf8',errors='ignore')
            match=re.search(r'"price"\s*:\s*"?([0-9]+(?:\.[0-9]+)?)',body,re.I)
            if not match: match=re.search(r'(?:\$|USD\s*)\s*([0-9]+(?:[.,][0-9]{1,2})?)',re.sub(r'<[^>]+>',' ',body),re.I)
            if match and float(match.group(1).replace(',','.'))<=row['target']:
                await bot.send_message(row['user_id'],f'تنبيه السعر: قد يكون سعر المنتج أقل من {row["target"]} الآن. تحقق من الصفحة يدويًا: {row["url"]}')
                with connection() as db: db.execute('UPDATE price_alerts SET active=0 WHERE id=?',(row['id'],))
        except Exception as e: log.info('Price check ignored id=%s: %s',row['id'],e)

async def main():
    validate(); init_db()
    bot=Bot(settings.bot_token)
    dp=Dispatcher()
    dp.include_router(root)
    dp.include_router(productivity_router)
    dp.include_router(extra_productivity_router)
    dp.include_router(learning_router)
    dp.include_router(community_router)
    dp.include_router(extra_groups_router)
    dp.include_router(extra_business_router)
    dp.include_router(extra_ai_router)
    dp.include_router(tools_router)
    dp.include_router(media_router)
    await bot.set_my_commands([BotCommand(command='start',description='بدء واختيار القائمة'),BotCommand(command='help',description='عرض الأوامر'),BotCommand(command='menu',description='القائمة التفاعلية'),BotCommand(command='convert',description='تحويل المستندات والوسائط'),BotCommand(command='remind',description='إنشاء تذكير'),BotCommand(command='ask',description='مساعد الذكاء الاصطناعي')])
    me=await bot.get_me(); log.info('Starting @%s (polling)',me.username)
    worker=asyncio.create_task(scheduled_worker(bot))
    try: await dp.start_polling(bot,allowed_updates=dp.resolve_used_update_types(),close_bot_session=False)
    finally:
        worker.cancel()
        try: await worker
        except asyncio.CancelledError: pass
        await bot.session.close()

if __name__=='__main__':
    try: asyncio.run(main())
    except KeyboardInterrupt: pass
