from __future__ import annotations
import re
from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from app.db import connection
from app.config import settings
from app.services.common import now_iso

router=Router()

def is_admin(user_id:int)->bool: return user_id in settings.admin_ids
async def chat_admin(m:Message)->bool:
    if is_admin(m.from_user.id): return True
    if m.chat.type=='private': return False
    return (await m.chat.get_member(m.from_user.id)).status in ('administrator','creator')

@router.message(Command('captcha'))
async def captcha_toggle(m:Message):
    if m.chat.type=='private': return await m.answer('استخدم /captcha on أو /captcha off داخل المجموعة كمشرف. اجعل البوت مشرفًا بصلاحية حظر/تقييد الأعضاء.')
    if not await chat_admin(m): return await m.answer('هذا الأمر لمشرفي المجموعة فقط.')
    value=(m.text or '').partition(' ')[2].strip().lower()
    if value not in ('on','off'): return await m.answer('استخدم /captcha on أو /captcha off.')
    with connection() as db: db.execute('INSERT INTO group_settings(chat_id,captcha) VALUES(?,?) ON CONFLICT(chat_id) DO UPDATE SET captcha=excluded.captcha',(m.chat.id,int(value=='on')))
    await m.answer('تم تفعيل اختبار التحقق للمنضمين الجدد.' if value=='on' else 'تم إيقاف اختبار التحقق.')

@router.callback_query(F.data.startswith('cap:'))
async def captcha_answer(c:CallbackQuery,bot):
    try: _,raw_chat,raw_user,raw_answer=c.data.split(':'); chat_id=int(raw_chat); user_id=int(raw_user); answer=int(raw_answer)
    except Exception: return await c.answer('زر غير صالح.',show_alert=True)
    if c.from_user.id!=user_id: return await c.answer('هذا الاختبار مخصص لعضو آخر.',show_alert=True)
    with connection() as db: row=db.execute('SELECT correct,expires_at FROM captcha_challenges WHERE chat_id=? AND user_id=?',(chat_id,user_id)).fetchone()
    if not row: return await c.answer('انتهت صلاحية الاختبار أو تم حله.',show_alert=True)
    if datetime.fromisoformat(row['expires_at'])<=datetime.now(timezone.utc): return await c.answer('انتهى وقت التحقق. سيُزال العضو تلقائيًا.',show_alert=True)
    if answer!=row['correct']: return await c.answer('إجابة غير صحيحة، حاول مرة أخرى.',show_alert=True)
    try:
        from aiogram.types import ChatPermissions
        await bot.restrict_chat_member(chat_id,user_id,permissions=ChatPermissions(can_send_messages=True,can_send_audios=True,can_send_documents=True,can_send_photos=True,can_send_videos=True,can_send_video_notes=True,can_send_voice_notes=True,can_send_polls=True,can_send_other_messages=True,can_add_web_page_previews=True,can_invite_users=True))
        with connection() as db: db.execute('DELETE FROM captcha_challenges WHERE chat_id=? AND user_id=?',(chat_id,user_id))
        await c.message.edit_text('تم التحقق بنجاح. مرحبًا بك!')
        await c.answer('تم التحقق.')
    except Exception as e: await c.answer(f'تعذر رفع التقييد؛ تحقق من صلاحيات البوت: {e}',show_alert=True)

@router.message(Command('allowdomain'))
async def allow_domain(m:Message):
    if m.chat.type=='private' or not await chat_admin(m): return await m.answer('إدارة القائمة متاحة لمشرفي المجموعة داخلها فقط.')
    parts=(m.text or '').split(maxsplit=2)
    if len(parts)==2 and parts[1]=='list':
        with connection() as db: rows=db.execute('SELECT domain FROM allowed_domains WHERE chat_id=? ORDER BY domain',(m.chat.id,)).fetchall()
        return await m.answer('النطاقات المسموحة:\n'+'\n'.join(r['domain'] for r in rows) if rows else 'قائمة السماح فارغة.')
    if len(parts)<3 or parts[1] not in ('add','remove'): return await m.answer('استخدم /allowdomain add example.com أو /allowdomain remove example.com أو /allowdomain list')
    domain=parts[2].lower().strip().removeprefix('https://').removeprefix('http://').split('/')[0].split(':')[0].split('?')[0].split('#')[0].removeprefix('www.')
    if not re.fullmatch(r'[a-z0-9.-]{1,253}',domain): return await m.answer('اسم النطاق غير صالح.')
    with connection() as db:
        if parts[1]=='add': db.execute('INSERT OR IGNORE INTO allowed_domains(chat_id,domain) VALUES(?,?)',(m.chat.id,domain))
        else: db.execute('DELETE FROM allowed_domains WHERE chat_id=? AND domain=?',(m.chat.id,domain))
    await m.answer(('أُضيف إلى السماح: ' if parts[1]=='add' else 'أُزيل من السماح: ')+domain)

@router.message(Command('badword'))
async def badword(m:Message):
    if m.chat.type=='private' or not await chat_admin(m): return await m.answer('إدارة الكلمات متاحة لمشرفي المجموعة داخلها فقط.')
    parts=(m.text or '').split(maxsplit=2)
    if len(parts)==2 and parts[1]=='list':
        with connection() as db: rows=db.execute('SELECT word FROM blocked_words WHERE chat_id=? ORDER BY word',(m.chat.id,)).fetchall()
        return await m.answer('الكلمات المحظورة:\n'+'\n'.join(r['word'] for r in rows) if rows else 'قائمة الكلمات المحظورة فارغة.')
    if len(parts)<3 or parts[1] not in ('add','remove'): return await m.answer('استخدم /badword add كلمة أو /badword remove كلمة أو /badword list')
    word=parts[2].strip().lower()
    if not word or len(word)>80: return await m.answer('الكلمة فارغة أو طويلة جدًا.')
    with connection() as db:
        if parts[1]=='add': db.execute('INSERT OR IGNORE INTO blocked_words(chat_id,word) VALUES(?,?)',(m.chat.id,word))
        else: db.execute('DELETE FROM blocked_words WHERE chat_id=? AND word=?',(m.chat.id,word))
    await m.answer('تم تحديث قائمة الكلمات المحظورة.')

@router.message(Command('role'))
async def role(m:Message):
    if m.chat.type=='private': return await m.answer('استخدم الأمر في المجموعة ردًا على رسالة العضو: /role اسم_الدور أو /role remove')
    member=await m.chat.get_member(m.from_user.id)
    if member.status not in ('administrator','creator'): return await m.answer('إدارة الأدوار للمشرفين فقط.')
    target=m.reply_to_message.from_user if m.reply_to_message else None
    if not target: return await m.answer('ردّ على رسالة العضو واكتب /role اسم_الدور، أو /role remove.')
    value=(m.text or '').partition(' ')[2].strip()
    with connection() as db:
        if value=='remove': db.execute('DELETE FROM group_roles WHERE chat_id=? AND user_id=?',(m.chat.id,target.id)); reply='تم حذف الدور.'
        elif value and len(value)<=32:
            db.execute('INSERT INTO group_roles(chat_id,user_id,role,assigned_at) VALUES(?,?,?,?) ON CONFLICT(chat_id,user_id) DO UPDATE SET role=excluded.role,assigned_at=excluded.assigned_at',(m.chat.id,target.id,value,now_iso())); reply=f'تم تعيين دور «{value}» لـ {target.full_name}.'
        else: return await m.answer('اكتب اسم الدور بعد الأمر.')
    await m.answer(reply)

@router.message(Command('roles'))
async def roles(m:Message):
    with connection() as db: rows=db.execute('SELECT user_id,role FROM group_roles WHERE chat_id=? ORDER BY role,user_id',(m.chat.id,)).fetchall()
    await m.answer(('أدوار المجموعة:\n'+'\n'.join(f'• {r["user_id"]}: {r["role"]}' for r in rows)) if rows else 'لم تُعيّن أدوار بعد.')

@router.message(Command('weekly'))
async def weekly(m:Message):
    with connection() as db:
        rows=db.execute('SELECT a.user_id,SUM(a.messages) n,r.role FROM group_activity a LEFT JOIN group_roles r ON r.chat_id=a.chat_id AND r.user_id=a.user_id WHERE a.chat_id=? AND a.day>=date("now","-6 days") GROUP BY a.user_id ORDER BY n DESC LIMIT 20',(m.chat.id,)).fetchall()
        for r in rows:
            role='عضو نشط' if r['n']>=20 else ('مساهم' if r['n']>=5 else 'مبتدئ')
            if r['role'] not in ('مشرف','مميز','عضو نشط','مساهم','مبتدئ'):
                db.execute('INSERT INTO group_roles(chat_id,user_id,role,assigned_at) VALUES(?,?,?,?) ON CONFLICT(chat_id,user_id) DO UPDATE SET role=excluded.role,assigned_at=excluded.assigned_at',(m.chat.id,r['user_id'],role,now_iso()))
    await m.answer(('نشاط آخر 7 أيام — تم تحديث الأدوار تلقائيًا:\n'+'\n'.join(f'{i+1}. {r["user_id"]}: {r["n"]} رسالة — {"عضو نشط" if r["n"]>=20 else ("مساهم" if r["n"]>=5 else "مبتدئ")}' for i,r in enumerate(rows))) if rows else 'لا توجد بيانات نشاط للأسبوع الحالي.')

@router.message(Command('suggest'))
async def suggest(m:Message):
    text=(m.text or '').partition(' ')[2].strip()
    if not text: return await m.answer('اكتب اقتراحك: /suggest نص الاقتراح. لن يظهر اسمك في قائمة الاقتراحات.')
    with connection() as db: cur=db.execute('INSERT INTO anonymous_suggestions(chat_id,user_id,text,created_at) VALUES(?,?,?,?)',(m.chat.id,m.from_user.id,text,now_iso()))
    await m.answer(f'تم إرسال اقتراحك دون إظهار اسمك للمجموعة. رقم المتابعة #{cur.lastrowid}.')

@router.message(Command('suggestions'))
async def suggestions(m:Message):
    if not await chat_admin(m): return await m.answer('قائمة الاقتراحات لمشرفي المجموعة فقط.')
    with connection() as db: rows=db.execute("SELECT id,text FROM anonymous_suggestions WHERE chat_id=? AND status='new' ORDER BY id DESC LIMIT 30",(m.chat.id,)).fetchall()
    await m.answer(('الاقتراحات (دون أسماء):\n'+'\n'.join(f'#{r["id"]}: {r["text"]}' for r in rows)) if rows else 'لا توجد اقتراحات جديدة.')

@router.message(Command('ticket'))
async def ticket(m:Message):
    if m.chat.type!='private': return await m.answer('لحماية الخصوصية، افتح تذكرة في المحادثة الخاصة مع البوت: /ticket وصف المشكلة')
    text=(m.text or '').partition(' ')[2].strip()
    if not text: return await m.answer('اكتب وصف المشكلة: /ticket لا أستطيع إكمال الطلب')
    with connection() as db: cur=db.execute('INSERT INTO support_tickets(chat_id,user_id,text,created_at) VALUES(?,?,?,?)',(m.chat.id,m.from_user.id,text,now_iso()))
    await m.answer(f'تم فتح تذكرة الدعم #{cur.lastrowid}. لمتابعة الرد سيصلك هنا.')

@router.message(Command('tickets'))
async def tickets(m:Message):
    if not is_admin(m.from_user.id): return await m.answer('هذا الأمر لمسؤول البوت فقط.')
    with connection() as db: rows=db.execute("SELECT id,user_id,text,created_at FROM support_tickets WHERE status='open' ORDER BY id LIMIT 30").fetchall()
    await m.answer(('التذاكر المفتوحة:\n'+'\n'.join(f'#{r["id"]} من {r["user_id"]}: {r["text"]}' for r in rows)) if rows else 'لا توجد تذاكر مفتوحة.')

@router.message(Command('ticket_reply'))
async def ticket_reply(m:Message,bot):
    if not is_admin(m.from_user.id): return await m.answer('هذا الأمر لمسؤول البوت فقط.')
    raw=(m.text or '').partition(' ')[2]
    if '|' not in raw: return await m.answer('استخدم /ticket_reply رقم | نص الرد')
    rid,text=[x.strip() for x in raw.split('|',1)]
    try: rid=int(rid)
    except: return await m.answer('رقم التذكرة غير صالح.')
    with connection() as db:
        row=db.execute("SELECT user_id FROM support_tickets WHERE id=? AND status='open'",(rid,)).fetchone()
        if not row: return await m.answer('التذكرة غير موجودة أو مغلقة.')
        db.execute('INSERT INTO ticket_messages(ticket_id,sender_id,text,created_at) VALUES(?,?,?,?)',(rid,m.from_user.id,text,now_iso()))
    try: await bot.send_message(row['user_id'],f'رد الدعم على التذكرة #{rid}:\n{text}')
    except Exception: return await m.answer('حُفظ الرد لكن لم أستطع إرسال رسالة خاصة. اطلب من صاحب التذكرة بدء محادثة البوت.')
    await m.answer('تم إرسال الرد.')

@router.message(Command('ticket_close'))
async def ticket_close(m:Message):
    if not is_admin(m.from_user.id): return await m.answer('هذا الأمر لمسؤول البوت فقط.')
    try: rid=int((m.text or '').split()[1])
    except: return await m.answer('استخدم /ticket_close رقم')
    with connection() as db: cur=db.execute("UPDATE support_tickets SET status='closed' WHERE id=? AND status='open'",(rid,))
    await m.answer('تم إغلاق التذكرة.' if cur.rowcount else 'التذكرة غير موجودة أو مغلقة.')

@router.message(Command('ticket_rate'))
async def ticket_rate(m:Message):
    p=(m.text or '').split(maxsplit=2)
    if len(p)<3: return await m.answer('قيّم تذكرتك المغلقة: /ticket_rate رقم 1-5')
    try: rid=int(p[1]); rating=int(p[2])
    except: return await m.answer('اكتب رقم التذكرة وتقييمًا من 1 إلى 5.')
    if not 1<=rating<=5: return await m.answer('التقييم يجب أن يكون من 1 إلى 5.')
    with connection() as db: cur=db.execute("UPDATE support_tickets SET rating=? WHERE id=? AND user_id=? AND status='closed'",(rating,rid,m.from_user.id))
    await m.answer('شكرًا على تقييمك.' if cur.rowcount else 'التذكرة غير موجودة أو لم تُغلق بعد.')

@router.channel_post(lambda m:not ((m.text or '').startswith('/') or (m.caption or '').startswith('/')))
async def record_channel_post(m:Message):
    with connection() as db: db.execute('INSERT OR IGNORE INTO channel_posts(chat_id,message_id,created_at,weekday,hour) VALUES(?,?,?,?,?)',(m.chat.id,m.message_id,now_iso(),m.date.weekday(),m.date.hour))

@router.message(Command('channel_stats'))
async def channel_stats(m:Message,bot):
    arg=(m.text or '').partition(' ')[2].strip()
    if arg.startswith('@'):
        try: target=await bot.get_chat(arg); target_id=target.id
        except Exception: return await m.answer('لم أستطع الوصول للقناة؛ تأكد أن البوت مشرف فيها واستخدم @username.')
    elif m.chat.type=='channel': target_id=m.chat.id
    else: return await m.answer('استخدم /channel_stats @username للقناة. يجب إضافة البوت مشرفًا؛ يبدأ التسجيل من وقت الإضافة.')
    await _send_channel_stats(m,target_id)

@router.channel_post(Command('channel_stats'))
async def channel_stats_in_channel(m:Message): await _send_channel_stats(m,m.chat.id)

async def _send_channel_stats(m:Message,target_id:int):
    with connection() as db:
        total=db.execute('SELECT COUNT(*) n FROM channel_posts WHERE chat_id=?',(target_id,)).fetchone()['n']
        rows=db.execute('SELECT hour,COUNT(*) n FROM channel_posts WHERE chat_id=? GROUP BY hour ORDER BY n DESC LIMIT 3',(target_id,)).fetchall()
    await m.answer(f'منذ إضافة البوت: تم تسجيل {total} منشورًا. أكثر ساعات النشر تكرارًا: '+(', '.join(f'{r["hour"]:02d}:00 ({r["n"]})' for r in rows) if rows else 'لا توجد بيانات بعد.')+'\nهذه إحصاءات المنشورات التي استقبلها البوت فقط؛ لا تتضمن مشاهدات أو تاريخًا سابقًا.')
