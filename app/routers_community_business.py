import re, secrets
from datetime import datetime, timedelta, timezone
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ChatMemberUpdated, LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
from aiogram.enums import ChatType
from app.db import connection
from app.services.common import now_iso, parse_when
from app.config import settings

router=Router()

def is_admin(user_id:int)->bool: return user_id in settings.admin_ids

@router.message(Command('antispam'))
async def antispam(m:Message):
    if m.chat.type=='private': return await m.answer('أضف البوت لمجموعة ثم اجعله مشرفًا بصلاحية حذف الرسائل، وبعدها استخدم /antispam on أو /antispam off.')
    member=await m.chat.get_member(m.from_user.id)
    if member.status not in ('administrator','creator'): return await m.answer('هذا الأمر لمشرفي المجموعة فقط.')
    state=(m.text or '').partition(' ')[2].strip().lower()
    if state not in ('on','off'): return await m.answer('استخدم /antispam on لتفعيل حذف الرسائل ذات الروابط، أو /antispam off لإيقافه.')
    with connection() as db: db.execute('INSERT INTO group_settings(chat_id,antispam) VALUES(?,?) ON CONFLICT(chat_id) DO UPDATE SET antispam=excluded.antispam',(m.chat.id,int(state=='on')))
    await m.answer('تم تفعيل مكافحة الروابط والسبام.' if state=='on' else 'تم إيقاف مكافحة السبام.')

@router.message(Command('welcome'))
async def welcome_set(m:Message):
    if m.chat.type=='private': return await m.answer('استخدم هذا الأمر داخل المجموعة: /welcome أهلاً بك {name}!')
    member=await m.chat.get_member(m.from_user.id)
    if member.status not in ('administrator','creator'): return await m.answer('هذا الأمر لمشرفي المجموعة فقط.')
    text=(m.text or '').partition(' ')[2].strip()
    with connection() as db: db.execute('INSERT INTO group_settings(chat_id,welcome) VALUES(?,?) ON CONFLICT(chat_id) DO UPDATE SET welcome=excluded.welcome',(m.chat.id,text))
    await m.answer('تم حفظ رسالة الترحيب.' if text else 'أُزيلت رسالة الترحيب.')

@router.chat_member()
async def welcome_new_member(ev:ChatMemberUpdated,bot):
    old=ev.old_chat_member.status; new=ev.new_chat_member.status
    if old in ('left','kicked') and new not in ('left','kicked'):
        with connection() as db: row=db.execute('SELECT welcome,captcha FROM group_settings WHERE chat_id=?',(ev.chat.id,)).fetchone()
        if row and row['captcha']:
            a,b=secrets.randbelow(5)+1,secrets.randbelow(5)+1
            answer=a+b
            options={answer}
            while len(options)<4:
                candidate=secrets.randbelow(9)+1
                options.add(candidate)
            options=list(options); secrets.SystemRandom().shuffle(options)
            expires=(datetime.now(timezone.utc)+timedelta(minutes=2)).isoformat()
            with connection() as db: db.execute('INSERT INTO captcha_challenges(chat_id,user_id,correct,expires_at) VALUES(?,?,?,?) ON CONFLICT(chat_id,user_id) DO UPDATE SET correct=excluded.correct,expires_at=excluded.expires_at',(ev.chat.id,ev.new_chat_member.user.id,answer,expires))
            try:
                await bot.restrict_chat_member(ev.chat.id,ev.new_chat_member.user.id,permissions=ChatPermissions(can_send_messages=False,can_send_audios=False,can_send_documents=False,can_send_photos=False,can_send_videos=False,can_send_video_notes=False,can_send_voice_notes=False,can_send_polls=False,can_send_other_messages=False,can_add_web_page_previews=False))
                kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=str(n),callback_data=f'cap:{ev.chat.id}:{ev.new_chat_member.user.id}:{n}') for n in options]])
                await bot.send_message(ev.chat.id,f'أهلًا {ev.new_chat_member.user.full_name}. للتحقق احسب {a} + {b} واختر الإجابة خلال دقيقتين.',reply_markup=kb)
                return
            except Exception:
                try: await bot.restrict_chat_member(ev.chat.id,ev.new_chat_member.user.id,permissions=ChatPermissions(can_send_messages=True,can_send_audios=True,can_send_documents=True,can_send_photos=True,can_send_videos=True,can_send_video_notes=True,can_send_voice_notes=True,can_send_polls=True,can_send_other_messages=True,can_add_web_page_previews=True,can_invite_users=True))
                except Exception: pass
                with connection() as db: db.execute('DELETE FROM captcha_challenges WHERE chat_id=? AND user_id=?',(ev.chat.id,ev.new_chat_member.user.id))
        txt=(row['welcome'] if row and row['welcome'] else 'أهلًا بك {name} في {chat}!').replace('{name}',ev.new_chat_member.user.full_name).replace('{chat}',ev.chat.title or '')
        await bot.send_message(ev.chat.id,txt)

@router.message(Command('poll'))
async def make_poll(m:Message):
    raw=(m.text or '').partition(' ')[2]
    p=[x.strip() for x in raw.split('|') if x.strip()]
    if len(p)<3: return await m.answer('استخدم: /poll السؤال | اختيار أول | اختيار ثانٍ | ... (حتى 10 اختيارات)')
    if len(p)>11: return await m.answer('الحد الأقصى 10 اختيارات.')
    await m.answer_poll(p[0],p[1:],is_anonymous=False)

@router.message(Command('schedule'))
async def schedule_post(m:Message):
    raw=(m.text or '').partition(' ')[2]
    if '|' not in raw: return await m.answer('جدولة منشور في المحادثة الحالية: /schedule 2026-11-14 18:00 | نص المنشور\nيجب أن يكون البوت مشرفًا في القناة/المجموعة.')
    when_text,text=[x.strip() for x in raw.split('|',1)]
    due=parse_when(when_text)
    if not due or not text: return await m.answer('تعذر فهم التاريخ أو نص المنشور.')
    with connection() as db: db.execute('INSERT INTO scheduled_posts(owner_id,chat_id,due_at,text) VALUES(?,?,?,?)',(m.from_user.id,m.chat.id,due.astimezone(timezone.utc).isoformat(),text))
    await m.answer(f'تمت الجدولة للنشر في {due.strftime("%Y-%m-%d %H:%M %Z")} في هذه المحادثة.')

@router.message(Command('points'))
async def points(m:Message):
    with connection() as db: rows=db.execute('SELECT user_id,points FROM quiz_scores WHERE chat_id=? ORDER BY points DESC LIMIT 10',(m.chat.id,)).fetchall()
    if not rows: return await m.answer('لم تُسجل نقاط بعد. التفاعل برسائل المجموعة يكسب نقاطًا.')
    await m.answer('مستويات ونقاط الأعضاء:\n'+'\n'.join(f'{i+1}. {r["user_id"]}: المستوى {1+r["points"]//50} — {r["points"]} نقطة' for i,r in enumerate(rows)))

@router.message(Command('book'))
async def book(m:Message):
    raw=(m.text or '').partition(' ')[2]
    if '|' not in raw: return await m.answer('طلب حجز: /book الخدمة | 2026-11-15 14:30')
    service,slot=[x.strip() for x in raw.split('|',1)]
    if not service or not slot: return await m.answer('اكتب اسم الخدمة والموعد بعد الفاصل |')
    with connection() as db:
        existing=db.execute("SELECT id FROM bookings WHERE slot=? AND status NOT IN ('cancelled','rejected') LIMIT 1",(slot,)).fetchone()
        if existing: return await m.answer('هذا الموعد محجوز بالفعل؛ اختر موعدًا آخر.')
        cur=db.execute('INSERT INTO bookings(user_id,chat_id,service,slot,created_at) VALUES(?,?,?,?,?)',(m.from_user.id,m.chat.id,service,slot,now_iso()))
    await m.answer(f'وصل طلب الحجز #{cur.lastrowid}. سيتم التواصل معك لتأكيده؛ الحجز غير نهائي حتى موافقة المسؤول.')

@router.message(Command('product'))
async def product(m:Message):
    raw=(m.text or '').partition(' ')[2].strip()
    if not raw.startswith('add '): return await shop(m)
    allowed=is_admin(m.from_user.id)
    if m.chat.type!='private':
        member=await m.chat.get_member(m.from_user.id)
        allowed=allowed or member.status in ('administrator','creator')
    if not allowed: return await m.answer('إضافة المنتجات متاحة لمسؤول البوت الموجود في ADMIN_IDS أو لمشرف المجموعة.')
    p=raw[4:].split('|')
    if len(p)<2: return await m.answer('لإضافة منتج: /product add الاسم | السعر | وصف اختياري (للمالك أضف ADMIN_IDS).')
    if not p[0].strip(): return await m.answer('اكتب اسم المنتج.')
    try: price=float(p[1].strip())
    except: return await m.answer('السعر يجب أن يكون رقمًا موجبًا.')
    if price<=0: return await m.answer('السعر يجب أن يكون أكبر من صفر.')
    with connection() as db: cur=db.execute('INSERT INTO products(owner_id,name,price,description) VALUES(?,?,?,?)',(m.from_user.id,p[0].strip(),price,p[2].strip() if len(p)>2 else ''))
    await m.answer(f'تمت إضافة المنتج #{cur.lastrowid}.')

@router.message(Command('shop'))
async def shop(m:Message):
    with connection() as db: rows=db.execute('SELECT id,name,price,description,stock FROM products WHERE active=1 ORDER BY id DESC LIMIT 40').fetchall()
    await m.answer(('المتجر (أضف للسلة بـ /cart add رقم):\n'+'\n'.join(f'#{r["id"]} {r["name"]} — {r["price"]:.2f} USD {r["description"]}'+(f' | المتاح: {r["stock"]}' if r['stock']>=0 else '') for r in rows)) if rows else 'المتجر فارغ. أضف منتجًا بـ /product add الاسم | السعر | وصف.')

@router.message(Command('cart'))
async def cart(m:Message):
    raw=(m.text or '').partition(' ')[2].strip()
    with connection() as db:
        if raw.startswith('add '):
            try: pid=int(raw.split()[1])
            except: return await m.answer('استخدم /cart add رقم_المنتج')
            product=db.execute('SELECT id,stock FROM products WHERE id=? AND active=1',(pid,)).fetchone()
            if not product: return await m.answer('المنتج غير موجود.')
            in_cart=db.execute('SELECT quantity FROM cart WHERE user_id=? AND product_id=?',(m.from_user.id,pid)).fetchone()
            if product['stock']==0 or product['stock']>=0 and in_cart and in_cart['quantity']>=product['stock']: return await m.answer('الكمية المتاحة غير كافية حاليًا.')
            db.execute('INSERT INTO cart(user_id,product_id,quantity) VALUES(?,?,1) ON CONFLICT(user_id,product_id) DO UPDATE SET quantity=quantity+1',(m.from_user.id,pid))
        rows=db.execute('SELECT p.id,p.name,p.price,c.quantity FROM cart c JOIN products p ON p.id=c.product_id WHERE c.user_id=?',(m.from_user.id,)).fetchall()
    if not rows: return await m.answer('سلتك فارغة. استعرض /shop ثم أضف بـ /cart add رقم.')
    total=sum(r['price']*r['quantity'] for r in rows)
    await m.answer('سلتك:\n'+'\n'.join(f'{r["name"]} × {r["quantity"]} = {r["price"]*r["quantity"]:.2f} USD' for r in rows)+f'\nالإجمالي: {total:.2f} USD\nاستخدم /checkout لإرسال الطلب أو الدفع عبر Telegram عند إعداد مزود الدفع.')

@router.message(Command('checkout'))
async def checkout(m:Message):
    low_stock_alerts=[]
    with connection() as db:
        rows=db.execute('SELECT p.id,p.name,p.price,p.stock,c.quantity FROM cart c JOIN products p ON p.id=c.product_id WHERE c.user_id=?',(m.from_user.id,)).fetchall()
        if not rows: return await m.answer('السلة فارغة؛ ابدأ بـ /shop.')
        for r in rows:
            if r['stock']>=0 and r['quantity']>r['stock']: return await m.answer(f'المخزون لا يكفي للمنتج {r["name"]}.')
        subtotal=sum(r['price']*r['quantity'] for r in rows)
        coupon=db.execute('SELECT c.code,c.percent,c.max_uses,c.used,c.expires_at FROM cart_coupons cc JOIN coupons c ON c.code=cc.code WHERE cc.user_id=?',(m.from_user.id,)).fetchone()
        if coupon and (coupon['used']>=coupon['max_uses'] or coupon['expires_at'] and coupon['expires_at']<datetime.now(timezone.utc).date().isoformat()): coupon=None
        coupon_discount=subtotal*coupon['percent']/100 if coupon else 0
        redemption=db.execute('SELECT points FROM cart_redemptions WHERE user_id=?',(m.from_user.id,)).fetchone()
        balance=db.execute('SELECT points FROM loyalty WHERE user_id=?',(m.from_user.id,)).fetchone()
        redeem_points=min(redemption['points'],balance['points'],int(max(0,subtotal-coupon_discount)*100)) if redemption and balance else 0
        total=max(0,subtotal-coupon_discount-redeem_points/100)
        items='; '.join(f'{r["name"]} x{r["quantity"]}' for r in rows)
        cur=db.execute('INSERT INTO orders(user_id,items,total,created_at) VALUES(?,?,?,?)',(m.from_user.id,items,total,now_iso())); oid=cur.lastrowid
        for r in rows:
            db.execute('INSERT INTO order_lines(order_id,product_id,quantity) VALUES(?,?,?)',(oid,r['id'],r['quantity']))
            if r['stock']>=0:
                db.execute('UPDATE products SET stock=stock-? WHERE id=?',(r['quantity'],r['id']))
                current=db.execute('SELECT name,stock,low_stock_threshold,low_stock_notified FROM products WHERE id=?',(r['id'],)).fetchone()
                if current['stock']<=current['low_stock_threshold'] and not current['low_stock_notified']:
                    db.execute('UPDATE products SET low_stock_notified=1 WHERE id=?',(r['id'],))
                    low_stock_alerts.append((current['name'],current['stock']))
        if coupon:
            db.execute('UPDATE coupons SET used=used+1 WHERE code=?',(coupon['code'],))
        if redeem_points: db.execute('UPDATE loyalty SET points=points-? WHERE user_id=?',(redeem_points,m.from_user.id))
        db.execute('INSERT INTO order_adjustments(order_id,coupon_code,loyalty_points) VALUES(?,?,?)',(oid,coupon['code'] if coupon else '',redeem_points))
    for name,quantity in low_stock_alerts:
        for admin_id in settings.admin_ids:
            try: await m.bot.send_message(admin_id,f'تنبيه مخزون منخفض: {name} — المتبقي {quantity}. حدّثه عبر /stock رقم | كمية | حد.')
            except Exception: pass
    payment_failed=False
    if settings.telegram_payment_token and total>=0.01:
        try:
            prices=[LabeledPrice(label='طلب المتجر',amount=max(1,round(total*100)))]
            summary=f'{items}; خصم كوبون {coupon["code"]}' if coupon else items
            await m.answer_invoice(title='طلب متجر Telegram',description=summary[:250],payload=f'order:{oid}',provider_token=settings.telegram_payment_token,currency='USD',prices=prices)
        except Exception as e:
            payment_failed=True
            await m.answer(f'تعذر بدء الدفع (تحقق من مزود الدفع والعملة): {e}')
    else:
        note=' أضف TELEGRAM_PAYMENT_TOKEN لتفعيل الدفع داخل تيليجرام.' if not settings.telegram_payment_token else ' لا يلزم دفع إلكتروني لهذا الطلب.'
        await m.answer(f'تم إرسال طلبك #{oid} بقيمة {total:.2f} USD للمراجعة.{note} لا ترسل بيانات بطاقتك في المحادثة.')
    if payment_failed:
        with connection() as db:
            db.execute("UPDATE orders SET status='cancelled' WHERE id=?",(oid,))
            for line in db.execute('SELECT product_id,quantity FROM order_lines WHERE order_id=?',(oid,)).fetchall():
                db.execute('UPDATE products SET stock=stock+?,low_stock_notified=0 WHERE id=? AND stock>=0',(line['quantity'],line['product_id']))
            adjustment=db.execute('SELECT coupon_code,loyalty_points FROM order_adjustments WHERE order_id=?',(oid,)).fetchone()
            if adjustment:
                if adjustment['loyalty_points']: db.execute('UPDATE loyalty SET points=points+? WHERE user_id=?',(adjustment['loyalty_points'],m.from_user.id))
                if adjustment['coupon_code']: db.execute('UPDATE coupons SET used=MAX(0,used-1) WHERE code=?',(adjustment['coupon_code'],))
    else:
        with connection() as db:
            db.execute('DELETE FROM cart WHERE user_id=?',(m.from_user.id,)); db.execute('DELETE FROM cart_coupons WHERE user_id=?',(m.from_user.id,)); db.execute('DELETE FROM cart_redemptions WHERE user_id=?',(m.from_user.id,))

@router.pre_checkout_query()
async def pre_checkout(q:PreCheckoutQuery): await q.answer(ok=True)

@router.message(F.successful_payment)
async def payment_success(m:Message):
    payload=m.successful_payment.invoice_payload
    if payload.startswith('order:'):
        oid=payload.split(':',1)[1]
        with connection() as db: db.execute("UPDATE orders SET status='paid' WHERE id=? AND user_id=?",(oid,m.from_user.id))
    await m.answer('تم استلام الدفع بنجاح. شكرًا لطلبك!')

@router.message(Command('faq'))
async def faq(m:Message):
    raw=(m.text or '').partition(' ')[2].strip()
    if raw.startswith('add '):
        if '|' not in raw[4:]: return await m.answer('إضافة سؤال/جواب: /faq add السؤال | الإجابة (لمسؤول البوت).')
        q,a=[x.strip() for x in raw[4:].split('|',1)]
        if not (is_admin(m.from_user.id) or m.chat.type!='private' and (await m.chat.get_member(m.from_user.id)).status in ('administrator','creator')): return await m.answer('إضافة الأسئلة متاحة لمشرف البوت أو مشرف المجموعة.')
        with connection() as db: db.execute('INSERT INTO faqs(owner_id,chat_id,question,answer) VALUES(?,?,?,?)',(m.from_user.id,m.chat.id,q,a))
        return await m.answer('تمت إضافة الإجابة إلى قاعدة الأسئلة الشائعة.')
    if not raw: return await m.answer('اسأل سؤالًا بعد /faq، أو أضف سؤالًا: /faq add السؤال | الإجابة')
    with connection() as db: rows=db.execute('SELECT question,answer FROM faqs WHERE chat_id IN (?,0) ORDER BY id DESC LIMIT 100',(m.chat.id,)).fetchall()
    import difflib
    match=difflib.get_close_matches(raw,[r['question'] for r in rows],n=1,cutoff=.35)
    if match:
        ans=next(r['answer'] for r in rows if r['question']==match[0]); await m.answer(ans)
    else: await m.answer('لم أجد جوابًا مطابقًا. اكتب /feedback لسؤال أو طلب دعم.')

@router.message(Command('feedback'))
async def feedback(m:Message):
    text=(m.text or '').partition(' ')[2].strip()
    if not text: return await m.answer('أرسل طلبك بعد الأمر: /feedback أحتاج مساعدة في...')
    with connection() as db: cur=db.execute('INSERT INTO feedback(user_id,chat_id,text,created_at) VALUES(?,?,?,?)',(m.from_user.id,m.chat.id,text,now_iso()))
    await m.answer(f'وصلت رسالتك #{cur.lastrowid}. شكرًا على التقييم/الطلب.')

@router.message(Command('requests'))
async def requests_list(m:Message):
    if not is_admin(m.from_user.id): return await m.answer('هذه القائمة مخصصة لمسؤول البوت (ADMIN_IDS).')
    with connection() as db:
        f=db.execute('SELECT id,user_id,text FROM feedback ORDER BY id DESC LIMIT 10').fetchall(); b=db.execute("SELECT id,user_id,service,slot,status FROM bookings ORDER BY id DESC LIMIT 10").fetchall(); o=db.execute("SELECT id,user_id,items,total,status FROM orders ORDER BY id DESC LIMIT 10").fetchall()
    text=['طلبات الدعم/التقييم:']+[f'#{r["id"]} من {r["user_id"]}: {r["text"]}' for r in f]+['الحجوزات:']+[f'#{r["id"]} من {r["user_id"]}: {r["service"]} — {r["slot"]} ({r["status"]})' for r in b]+['الطلبات التجارية:']+[f'#{r["id"]} من {r["user_id"]}: {r["items"]} — {r["total"]:.2f} ({r["status"]})' for r in o]
    await m.answer('\n'.join(text)[:4000])

@router.message(F.chat.type.in_({ChatType.GROUP,ChatType.SUPERGROUP}),lambda m:not ((m.text or '').startswith('/') or (m.caption or '').startswith('/')))
async def group_moderation_and_points(m:Message):
    if not m.from_user or m.from_user.is_bot: return
    if (m.text or '').startswith('/') or (m.caption or '').startswith('/'): return
    with connection() as db:
        row=db.execute('SELECT antispam FROM group_settings WHERE chat_id=?',(m.chat.id,)).fetchone()
        text=(m.text or m.caption or '').lower()
        blocked=[r['word'] for r in db.execute('SELECT word FROM blocked_words WHERE chat_id=?',(m.chat.id,)).fetchall()]
        allowed=[r['domain'] for r in db.execute('SELECT domain FROM allowed_domains WHERE chat_id=?',(m.chat.id,)).fetchall()]
    if any(word in text for word in blocked):
        try: await m.delete()
        except Exception: pass
        return
    if row and row['antispam']:
        found=re.findall(r'(?:https?://|www\.|t\.me/)([^/\s?#:]+)',text)
        domains=[x.lower().removeprefix('www.') for x in found]
        if domains and not all(any(d==a or d.endswith('.'+a) for a in allowed) for d in domains):
            try: await m.delete()
            except Exception: pass
            return
    with connection() as db:
        db.execute('INSERT INTO quiz_scores(user_id,chat_id,points) VALUES(?,?,1) ON CONFLICT(user_id,chat_id) DO UPDATE SET points=points+1',(m.from_user.id,m.chat.id))
        db.execute('INSERT INTO group_activity(chat_id,user_id,day,messages) VALUES(?,?,date("now"),1) ON CONFLICT(chat_id,user_id,day) DO UPDATE SET messages=messages+1',(m.chat.id,m.from_user.id))
