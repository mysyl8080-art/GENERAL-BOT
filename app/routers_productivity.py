from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from datetime import datetime, timezone
from app.db import connection
from app.services.common import parse_when, now_iso

router=Router()

@router.message(Command('remind'))
async def remind(m:Message):
    raw=(m.text or '').partition(' ')[2].strip()
    if '|' not in raw:
        await m.answer('استخدم: /remind بعد ساعتين | راجع الدرس\nأو: /remind 2026-11-14 15:30 | موعد الطبيب')
        return
    when_text,body=[x.strip() for x in raw.split('|',1)]
    due=parse_when(when_text)
    if not due or not body:
        await m.answer('لم أفهم الموعد. جرّب «بعد ساعتين» أو تاريخًا بصيغة YYYY-MM-DD HH:MM.')
        return
    if due.tzinfo is None: due=due.replace(tzinfo=timezone.utc)
    if due.astimezone(timezone.utc)<=datetime.now(timezone.utc):
        await m.answer('يجب أن يكون الموعد في المستقبل.'); return
    with connection() as db:
        db.execute('INSERT INTO reminders(user_id,chat_id,due_at,text) VALUES(?,?,?,?)',(m.from_user.id,m.chat.id,due.astimezone(timezone.utc).isoformat(),body))
    await m.answer(f'تم حفظ التذكير: {body}\nالموعد: {due.strftime("%Y-%m-%d %H:%M %Z")}')

@router.message(Command('habit_add'))
async def habit_add(m:Message):
    name=(m.text or '').partition(' ')[2].strip()
    if not name: return await m.answer('استخدم: /habit_add قراءة 20 دقيقة')
    with connection() as db:
        try: db.execute('INSERT INTO habits(user_id,name,created_at) VALUES(?,?,?)',(m.from_user.id,name,now_iso()))
        except Exception: return await m.answer('هذه العادة موجودة بالفعل.')
    await m.answer(f'أُضيفت عادة «{name}». سجّل إنجازك بـ /habit_done {name}')

@router.message(Command('habit_done'))
async def habit_done(m:Message):
    name=(m.text or '').partition(' ')[2].strip()
    with connection() as db:
        row=db.execute('SELECT id,name FROM habits WHERE user_id=? AND (?="" OR name LIKE ?) ORDER BY id LIMIT 1',(m.from_user.id,name,'%'+name+'%')).fetchone()
        if not row: return await m.answer('لم أجد العادة. اعرضها عبر /habits أو أضفها بـ /habit_add اسم العادة')
        try: db.execute('INSERT INTO habit_logs(habit_id,day) VALUES(?,?)',(row['id'],datetime.now().date().isoformat()))
        except Exception: return await m.answer('تم تسجيل إنجاز هذه العادة اليوم بالفعل.')
        count=db.execute('SELECT COUNT(*) n FROM habit_logs WHERE habit_id=? AND day>=date("now","-6 days")',(row['id'],)).fetchone()['n']
    await m.answer(f'أحسنت! سُجل إنجاز «{row["name"]}». إنجازات آخر 7 أيام: {count}')

@router.message(Command('habits'))
async def habits(m:Message):
    with connection() as db: rows=db.execute('SELECT h.id,h.name,COUNT(l.id) n FROM habits h LEFT JOIN habit_logs l ON l.habit_id=h.id AND l.day>=date("now","-6 days") WHERE h.user_id=? GROUP BY h.id ORDER BY h.id',(m.from_user.id,)).fetchall()
    if not rows: return await m.answer('لا توجد عادات بعد. ابدأ بـ /habit_add اسم العادة')
    await m.answer('عاداتك (إنجازات آخر 7 أيام):\n'+'\n'.join(f'• {r["name"]}: {r["n"]}/7' for r in rows))

@router.message(Command('task'))
async def task(m:Message):
    raw=(m.text or '').partition(' ')[2].strip()
    if raw.lower().startswith('done '):
        try: tid=int(raw.split()[1])
        except: return await m.answer('استخدم: /task done رقم_المهمة')
        with connection() as db: cur=db.execute('UPDATE tasks SET done=1 WHERE id=? AND chat_id=?',(tid,m.chat.id))
        return await m.answer('تم إغلاق المهمة.' if cur.rowcount else 'لم أعثر على مهمة بهذا الرقم في هذه المحادثة.')
    if not raw: return await m.answer('استخدم /task نص المهمة لإضافة مهمة للفرد أو للفريق.\n/task done رقم لإكمالها، /tasks لعرضها.')
    with connection() as db: cur=db.execute('INSERT INTO tasks(owner_id,chat_id,text,created_at) VALUES(?,?,?,?)',(m.from_user.id,m.chat.id,raw,now_iso()))
    await m.answer(f'أُضيفت المهمة #{cur.lastrowid}: {raw}')

@router.message(Command('tasks'))
async def tasks(m:Message):
    with connection() as db: rows=db.execute('SELECT id,text,owner_id FROM tasks WHERE chat_id=? AND done=0 ORDER BY id DESC LIMIT 40',(m.chat.id,)).fetchall()
    if not rows: return await m.answer('لا توجد مهام مفتوحة هنا.')
    await m.answer('المهام المفتوحة:\n'+'\n'.join(f'#{r["id"]} — {r["text"]} (أضافها {r["owner_id"]})' for r in rows))

@router.message(Command('note'))
async def note(m:Message):
    text=(m.text or '').partition(' ')[2].strip()
    if not text: return await m.answer('استخدم /note نص الملاحظة. لإظهار آخر ملاحظاتك: /note list')
    with connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY,user_id INTEGER,text TEXT,created_at TEXT)')
        if text=='list': rows=db.execute('SELECT text,created_at FROM notes WHERE user_id=? ORDER BY id DESC LIMIT 20',(m.from_user.id,)).fetchall()
        else: db.execute('INSERT INTO notes(user_id,text,created_at) VALUES(?,?,?)',(m.from_user.id,text,now_iso())); rows=[]
    if text=='list': await m.answer('ملاحظاتك:\n'+'\n'.join('• '+r['text'] for r in rows) if rows else 'لا توجد ملاحظات محفوظة.')
    else: await m.answer('تم حفظ الملاحظة في حسابك.')
