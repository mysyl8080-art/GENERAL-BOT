from datetime import datetime, timedelta, timezone
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, PollAnswer, InlineKeyboardMarkup, InlineKeyboardButton
from app.db import connection
from app.services.common import now_iso

router=Router()
POLL_CORRECT:dict[str,tuple[int,int]]={}

@router.message(Command('word'))
async def word(m:Message):
    raw=(m.text or '').partition(' ')[2].strip()
    if not raw or raw=='list':
        with connection() as db: rows=db.execute('SELECT front,back FROM words WHERE user_id=? ORDER BY id DESC LIMIT 30',(m.from_user.id,)).fetchall()
        return await m.answer(('مفرداتك:\n'+'\n'.join(f'• {r["front"]} = {r["back"]}' for r in rows)) if rows else 'أضف مفردة: /word add hello | مرحبًا')
    if raw.startswith('add '):
        parts=raw[4:].split('|',1)
        if len(parts)!=2 or not all(x.strip() for x in parts): return await m.answer('استخدم: /word add الكلمة | الترجمة')
        with connection() as db:
            try: db.execute('INSERT INTO words(user_id,front,back,due_at) VALUES(?,?,?,?)',(m.from_user.id,parts[0].strip(),parts[1].strip(),now_iso()))
            except Exception: return await m.answer('هذه الكلمة موجودة بالفعل.')
        return await m.answer('تم حفظ المفردة. اكتب /word لعرضها أو /review للمراجعة.')
    await m.answer('استخدم /word add كلمة | ترجمة، أو /word list.')

@router.message(Command('word_quiz'))
async def word_quiz(m:Message):
    with connection() as db: rows=db.execute('SELECT front,back FROM words WHERE user_id=?',(m.from_user.id,)).fetchall()
    if len(rows)<2: return await m.answer('أضف مفردتين على الأقل عبر /word add كلمة | ترجمة ثم أعد المحاولة.')
    import random
    correct=random.choice(rows); distractors=random.sample([r['back'] for r in rows if r['back']!=correct['back']],min(2,len(rows)-1))
    opts=distractors+[correct['back']]; random.shuffle(opts); idx=opts.index(correct['back'])
    poll=await m.answer_poll(f'ما ترجمة: {correct["front"]}؟',opts,type='quiz',correct_option_id=idx,is_anonymous=False,open_period=30)
    POLL_CORRECT[poll.poll.id]=(idx,m.chat.id)

@router.message(Command('card'))
async def card(m:Message):
    raw=(m.text or '').partition(' ')[2].strip()
    if not raw.startswith('add '): return await m.answer('أضف بطاقة: /card add السؤال أو الوجه الأمامي | الإجابة')
    p=raw[4:].split('|',1)
    if len(p)!=2 or not p[0].strip() or not p[1].strip(): return await m.answer('استخدم /card add سؤال | إجابة')
    with connection() as db:
        try: db.execute('INSERT INTO words(user_id,front,back,due_at) VALUES(?,?,?,?)',(m.from_user.id,p[0].strip(),p[1].strip(),now_iso()))
        except Exception: return await m.answer('هذه البطاقة موجودة بالفعل.')
    await m.answer('تم حفظ البطاقة. اكتب /review لبدء المراجعة.')

@router.message(Command('review'))
async def review(m:Message):
    with connection() as db: row=db.execute('SELECT id,front,back FROM words WHERE user_id=? AND due_at<=? ORDER BY due_at,id LIMIT 1',(m.from_user.id,now_iso())).fetchone()
    if not row: return await m.answer('لا توجد بطاقات مستحقة الآن. أضف بطاقة بـ /card add سؤال | جواب')
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='أعرفها (تباعد أكثر)',callback_data=f'review:easy:{row["id"]}'),InlineKeyboardButton(text='أعدها قريبًا',callback_data=f'review:again:{row["id"]}')]])
    from html import escape
    await m.answer(f'بطاقة المراجعة:\n{escape(row["front"])}\n\nالإجابة: <tg-spoiler>{escape(row["back"])}</tg-spoiler>',reply_markup=kb,parse_mode='HTML')

@router.callback_query(lambda c:c.data and c.data.startswith('review:'))
async def review_result(c:CallbackQuery):
    _,kind,rawid=c.data.split(':'); wid=int(rawid)
    with connection() as db:
        row=db.execute('SELECT interval_days FROM words WHERE id=? AND user_id=?',(wid,c.from_user.id)).fetchone()
        if not row: return await c.answer('هذه البطاقة ليست لك أو لم تعد موجودة.',show_alert=True)
        days=max(1,row['interval_days']*2 if kind=='easy' and row['interval_days'] else (3 if kind=='easy' else 0))
        due=(datetime.now(timezone.utc)+timedelta(days=days)).isoformat()
        db.execute('UPDATE words SET interval_days=?,due_at=? WHERE id=?',(days,due,wid))
    await c.message.edit_reply_markup(reply_markup=None); await c.answer('سُجلت المراجعة.')

QUIZ=[('ما عاصمة اليابان؟',['طوكيو','أوساكا','كيوتو'],0),('كم عدد ألوان قوس قزح التقليدي؟',['5','7','9'],1),('ما أكبر كوكب في المجموعة الشمسية؟',['المريخ','المشتري','الزهرة'],1),('ما اللغة الرسمية في البرازيل؟',['الإسبانية','البرتغالية','الفرنسية'],1),('ما العنصر الكيميائي رمزه O؟',['الأكسجين','الذهب','الحديد'],0)]
@router.message(Command('quiz'))
async def quiz(m:Message):
    q,opts,ans=QUIZ[datetime.now().timetuple().tm_yday%len(QUIZ)]
    poll=await m.answer_poll(q,options=opts,type='quiz',correct_option_id=ans,is_anonymous=False,open_period=30,explanation='أجب عن السؤال الثقافي اليومي!')
    POLL_CORRECT[poll.poll.id]=(ans,m.chat.id)

@router.poll_answer()
async def poll_answer(p:PollAnswer):
    expected=POLL_CORRECT.get(p.poll_id)
    if expected and p.option_ids and p.option_ids[0]==expected[0]:
        with connection() as db: db.execute('INSERT INTO quiz_scores(user_id,chat_id,points) VALUES(?,?,1) ON CONFLICT(user_id,chat_id) DO UPDATE SET points=points+1',(p.user.id,expected[1]))

@router.message(Command('leaderboard'))
async def leaderboard(m:Message):
    with connection() as db: rows=db.execute('SELECT user_id,points FROM quiz_scores WHERE chat_id IN (?,0) ORDER BY points DESC LIMIT 10',(m.chat.id,)).fetchall()
    await m.answer('لوحة المتصدرين:\n'+'\n'.join(f'{i+1}. {r["user_id"]} — {r["points"]} نقطة' for i,r in enumerate(rows)) if rows else 'لا توجد نقاط بعد.')
