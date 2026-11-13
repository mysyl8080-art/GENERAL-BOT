from __future__ import annotations
import re
from datetime import datetime, timezone
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from app.db import connection
from app.services.common import now_iso, parse_when

router=Router()

@router.message(Command('daily_summary'))
async def daily_summary(m:Message):
    if m.chat.type!='private': return await m.answer('لخصوصية بيانات مهامك وعاداتك، فعّل الملخص من المحادثة الخاصة مع البوت.')
    value=(m.text or '').partition(' ')[2].strip().lower()
    if value=='off':
        with connection() as db: db.execute('DELETE FROM daily_summaries WHERE user_id=? AND chat_id=?',(m.from_user.id,m.chat.id))
        return await m.answer('تم إيقاف الملخص اليومي.')
    if not re.fullmatch(r'\d{2}:\d{2}',value): return await m.answer('استخدم /daily_summary 20:00 لتحديد وقت الإرسال، أو /daily_summary off للإيقاف. الوقت حسب TIMEZONE.')
    hh,mm=map(int,value.split(':'))
    if hh>23 or mm>59: return await m.answer('الوقت غير صالح؛ استخدم صيغة 24 ساعة مثل 20:00.')
    with connection() as db: db.execute('INSERT INTO daily_summaries(user_id,chat_id,send_time,last_sent) VALUES(?,?,?,"") ON CONFLICT(user_id,chat_id) DO UPDATE SET send_time=excluded.send_time,last_sent=""',(m.from_user.id,m.chat.id,value))
    await m.answer(f'تم تفعيل ملخصك اليومي الساعة {value}. لإيقافه استخدم /daily_summary off.')

@router.message(Command('repeat'))
async def repeat(m:Message):
    raw=(m.text or '').partition(' ')[2].strip()
    if raw=='list':
        with connection() as db: rows=db.execute('SELECT id,rule,send_time,text FROM recurring_reminders WHERE user_id=? AND active=1 ORDER BY id',(m.from_user.id,)).fetchall()
        return await m.answer(('تذكيراتك المتكررة:\n'+'\n'.join(f'#{r["id"]} {r["rule"]} {r["send_time"]} — {r["text"]}' for r in rows)) if rows else 'لا توجد تذكيرات متكررة.')
    if raw.startswith('off '):
        try: rid=int(raw.split()[1])
        except: return await m.answer('استخدم /repeat off رقم')
        with connection() as db: cur=db.execute('UPDATE recurring_reminders SET active=0 WHERE id=? AND user_id=?',(rid,m.from_user.id))
        return await m.answer('تم إيقاف التذكير.' if cur.rowcount else 'لم أجد تذكيرًا بهذا الرقم.')
    if '|' not in raw: return await m.answer('أمثلة:\n/repeat daily 09:00 | اشرب ماء\n/repeat weekly fri 17:30 | راجع الخطة\n/repeat monthly 1 08:00 | ادفع الفاتورة\n/repeat list أو /repeat off رقم')
    spec,text=[x.strip() for x in raw.split('|',1)]; parts=spec.split()
    if not text or len(parts)<2: return await m.answer('صيغة غير مكتملة. استخدم أحد أمثلة /repeat.')
    kind=parts[0].lower()
    if kind=='daily' and len(parts)==2: rule='daily'; clock=parts[1]
    elif kind=='weekly' and len(parts)==3 and parts[1].lower() in ('mon','tue','wed','thu','fri','sat','sun'):
        rule='weekly:'+parts[1].lower(); clock=parts[2]
    elif kind=='monthly' and len(parts)==3 and parts[1].isdigit() and 1<=int(parts[1])<=31:
        rule='monthly:'+str(int(parts[1])); clock=parts[2]
    else: return await m.answer('استخدم daily HH:MM أو weekly mon|tue|wed|thu|fri|sat|sun HH:MM أو monthly رقم_اليوم HH:MM.')
    if not re.fullmatch(r'\d{2}:\d{2}',clock) or int(clock[:2])>23 or int(clock[3:])>59: return await m.answer('الوقت غير صالح؛ استخدم HH:MM مثل 09:00.')
    with connection() as db: cur=db.execute('INSERT INTO recurring_reminders(user_id,chat_id,rule,send_time,text) VALUES(?,?,?,?,?)',(m.from_user.id,m.chat.id,rule,clock,text))
    await m.answer(f'تم إنشاء التذكير المتكرر #{cur.lastrowid}.')

@router.message(Command('shopping'))
async def shopping(m:Message):
    raw=(m.text or '').partition(' ')[2].strip(); cmd,_,value=raw.partition(' ')
    with connection() as db:
        if cmd=='add' and value:
            cur=db.execute('INSERT INTO shopping_items(chat_id,user_id,text,created_at) VALUES(?,?,?,?)',(m.chat.id,m.from_user.id,value,now_iso()))
            return await m.answer(f'أُضيف #{cur.lastrowid}: {value}')
        if cmd in ('done','remove'):
            try: item_id=int(value)
            except: return await m.answer('استخدم /shopping done رقم أو /shopping remove رقم')
            if cmd=='done': cur=db.execute('UPDATE shopping_items SET checked=1 WHERE id=? AND chat_id=?',(item_id,m.chat.id))
            else: cur=db.execute('DELETE FROM shopping_items WHERE id=? AND chat_id=?',(item_id,m.chat.id))
            return await m.answer('تم التحديث.' if cur.rowcount else 'لم أعثر على العنصر.')
        rows=db.execute('SELECT id,user_id,text,checked FROM shopping_items WHERE chat_id=? ORDER BY checked,id DESC LIMIT 100',(m.chat.id,)).fetchall()
    await m.answer(('قائمة التسوق المشتركة:\n'+'\n'.join(f'{"✓" if r["checked"] else "□"} #{r["id"]} {r["text"]} — أضافه {r["user_id"]}' for r in rows)) if rows else 'القائمة فارغة. أضف عنصرًا بـ /shopping add حليب')

@router.message(Command('meet_poll'))
async def meet_poll(m:Message):
    parts=[x.strip() for x in (m.text or '').partition(' ')[2].split('|') if x.strip()]
    if len(parts)<3 or len(parts)>11: return await m.answer('استفتاء موعد: /meet_poll اختروا الموعد | السبت 10:00 | الأحد 15:00 (من 2 إلى 10 خيارات).')
    await m.answer_poll(parts[0],options=parts[1:],is_anonymous=False)

@router.message(Command('event'))
async def event(m:Message):
    raw=(m.text or '').partition(' ')[2].strip()
    if raw=='list':
        with connection() as db: rows=db.execute('SELECT id,title,event_at FROM countdown_events WHERE chat_id=? AND event_at>? ORDER BY event_at LIMIT 30',(m.chat.id,now_iso())).fetchall()
        return await m.answer(('المواعيد القادمة:\n'+'\n'.join(f'#{r["id"]} {r["title"]} — {r["event_at"]}' for r in rows)) if rows else 'لا توجد أحداث قادمة.')
    if '|' not in raw: return await m.answer('أضف حدثًا: /event 2026-12-01 18:00 | حفلة التخرج\nللعرض: /event list')
    when,title=[x.strip() for x in raw.split('|',1)]; due=parse_when(when)
    if not due or due<=datetime.now(due.tzinfo): return await m.answer('أدخل موعدًا مستقبليًا واضحًا.')
    with connection() as db: cur=db.execute('INSERT INTO countdown_events(owner_id,chat_id,title,event_at) VALUES(?,?,?,?)',(m.from_user.id,m.chat.id,title,due.astimezone(timezone.utc).isoformat()))
    await m.answer(f'تم حفظ الحدث #{cur.lastrowid}. سأرسل تنبيهًا قبل موعده بنحو 24 ساعة.')
