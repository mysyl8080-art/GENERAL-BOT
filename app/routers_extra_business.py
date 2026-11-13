from __future__ import annotations
from datetime import date, timezone
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from app.db import connection
from app.config import settings
from app.services.common import now_iso, parse_when

router=Router()

def admin(uid:int)->bool: return uid in settings.admin_ids

@router.message(Command('stock'))
async def stock(m:Message):
    if not admin(m.from_user.id): return await m.answer('تحديث المخزون متاح لمسؤول البوت فقط (ADMIN_IDS).')
    raw=(m.text or '').partition(' ')[2]
    if '|' not in raw: return await m.answer('استخدم /stock رقم_المنتج | الكمية | حد التنبيه (مثال: /stock 4 | 20 | 5)')
    try: pid,quantity,threshold=[int(x.strip()) for x in raw.split('|')]
    except: return await m.answer('اكتب رقم المنتج والكمية والحد كأرقام صحيحة.')
    if quantity<0 or threshold<0: return await m.answer('لا يمكن أن تكون الكمية أو الحد سالبًا.')
    with connection() as db: cur=db.execute('UPDATE products SET stock=?,low_stock_threshold=?,low_stock_notified=0 WHERE id=?',(quantity,threshold,pid))
    if not cur.rowcount: return await m.answer('المنتج غير موجود.')
    await m.answer('تم تحديث المخزون.'+(f' تنبيه: الكمية {quantity} عند حد التنبيه أو أقل.' if quantity<=threshold else ''))

@router.message(Command('coupon_add'))
async def coupon_add(m:Message):
    if not admin(m.from_user.id): return await m.answer('إدارة الكوبونات لمسؤول البوت فقط.')
    p=[x.strip() for x in (m.text or '').partition(' ')[2].split('|')]
    if len(p)<3: return await m.answer('استخدم /coupon_add CODE | نسبة الخصم | عدد الاستخدامات | YYYY-MM-DD (تاريخ اختياري)')
    code=p[0].upper()
    try: percent,uses=int(p[1]),int(p[2])
    except: return await m.answer('النسبة وعدد الاستخدامات يجب أن يكونا أرقامًا.')
    if not code.isalnum() or not 1<=percent<=90 or uses<1: return await m.answer('الكود حروف/أرقام، والنسبة 1-90، وعدد الاستخدامات أكبر من صفر.')
    expires=p[3] if len(p)>3 else ''
    if expires:
        try: date.fromisoformat(expires)
        except: return await m.answer('تاريخ الانتهاء يجب أن يكون YYYY-MM-DD.')
    with connection() as db:
        db.execute('INSERT INTO coupons(code,percent,max_uses,expires_at) VALUES(?,?,?,?) ON CONFLICT(code) DO UPDATE SET percent=excluded.percent,max_uses=excluded.max_uses,used=0,expires_at=excluded.expires_at',(code,percent,uses,expires))
    await m.answer(f'تم إنشاء كوبون {code} بخصم {percent}% بحد {uses} استخدام.')

@router.message(Command('coupon'))
async def coupon(m:Message):
    code=(m.text or '').partition(' ')[2].strip().upper()
    if not code: return await m.answer('طبّق كوبونًا على سلتك بـ /coupon CODE أو أزله بـ /coupon_remove.')
    with connection() as db:
        row=db.execute('SELECT percent,max_uses,used,expires_at FROM coupons WHERE code=?',(code,)).fetchone()
        if not row: return await m.answer('الكوبون غير موجود.')
        if row['used']>=row['max_uses'] or row['expires_at'] and row['expires_at']<date.today().isoformat(): return await m.answer('انتهت صلاحية الكوبون أو استُنفدت استخداماته.')
        db.execute('INSERT INTO cart_coupons(user_id,code) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET code=excluded.code',(m.from_user.id,code))
    await m.answer(f'تم تطبيق الكوبون {code} بخصم {row["percent"]}%.')

@router.message(Command('coupon_remove'))
async def coupon_remove(m:Message):
    with connection() as db: db.execute('DELETE FROM cart_coupons WHERE user_id=?',(m.from_user.id,))
    await m.answer('تمت إزالة كوبون السلة.')

@router.message(Command('loyalty'))
async def loyalty(m:Message):
    with connection() as db: row=db.execute('SELECT points FROM loyalty WHERE user_id=?',(m.from_user.id,)).fetchone()
    await m.answer(f'رصيد الولاء: {row["points"] if row else 0} نقطة. عند الدفع: كل 100 نقطة تخصم 1 USD، استخدم /redeem عدد_النقاط.')

@router.message(Command('redeem'))
async def redeem(m:Message):
    try: points=int((m.text or '').split()[1])
    except: return await m.answer('استخدم /redeem 100 لاستبدال 100 نقطة (تعادل 1 USD) في السلة التالية.')
    if points<100 or points%100: return await m.answer('الاستبدال يبدأ من 100 نقطة وبمضاعفات 100.')
    with connection() as db:
        row=db.execute('SELECT points FROM loyalty WHERE user_id=?',(m.from_user.id,)).fetchone()
        if not row or row['points']<points: return await m.answer('رصيد النقاط غير كافٍ.')
        db.execute('INSERT INTO cart_redemptions(user_id,points) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET points=excluded.points',(m.from_user.id,points))
    await m.answer(f'تم إعداد استبدال {points} نقطة (حتى {points/100:.2f} USD) عند الدفع.')

@router.message(Command('order'))
async def order(m:Message):
    parts=(m.text or '').partition(' ')[2].strip()
    if '|' in parts:
        if not admin(m.from_user.id): return await m.answer('تحديث حالة الطلب لمسؤول البوت فقط.')
        raw_id,status=[x.strip().lower() for x in parts.split('|',1)]
        try: oid=int(raw_id)
        except: return await m.answer('رقم الطلب غير صالح.')
        mapping={'new':'new','جديد':'new','processing':'processing','قيد التجهيز':'processing','shipped':'shipped','تم الشحن':'shipped','delivered':'delivered','تم التسليم':'delivered','cancelled':'cancelled','ملغي':'cancelled'}
        new_status=mapping.get(status)
        if not new_status: return await m.answer('الحالات: new أو processing أو shipped أو delivered أو cancelled.')
        with connection() as db:
            row=db.execute('SELECT user_id,total,status FROM orders WHERE id=?',(oid,)).fetchone()
            if not row: return await m.answer('الطلب غير موجود.')
            old=row['status']
            if old=='delivered' and new_status=='cancelled': return await m.answer('الطلب المسلّم يحتاج معالجة يدوية؛ لم يُلغَ تلقائيًا.')
            db.execute('UPDATE orders SET status=? WHERE id=?',(new_status,oid))
            if new_status=='cancelled' and old!='cancelled':
                lines=db.execute('SELECT product_id,quantity FROM order_lines WHERE order_id=?',(oid,)).fetchall()
                for line in lines: db.execute('UPDATE products SET stock=stock+?,low_stock_notified=0 WHERE id=? AND stock>=0',(line['quantity'],line['product_id']))
                adjustment=db.execute('SELECT coupon_code,loyalty_points FROM order_adjustments WHERE order_id=?',(oid,)).fetchone()
                if adjustment:
                    if adjustment['loyalty_points']: db.execute('INSERT INTO loyalty(user_id,points) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET points=points+excluded.points',(row['user_id'],adjustment['loyalty_points']))
                    if adjustment['coupon_code']: db.execute('UPDATE coupons SET used=MAX(0,used-1) WHERE code=?',(adjustment['coupon_code'],))
            if new_status=='delivered' and old!='delivered':
                points=max(1,int(row['total']))
                existing=db.execute("SELECT order_id FROM loyalty_events WHERE order_id=? AND event='earned'",(oid,)).fetchone()
                if not existing:
                    db.execute("INSERT INTO loyalty_events(order_id,event,points) VALUES(?,'earned',?)",(oid,points))
                    db.execute('INSERT INTO loyalty(user_id,points) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET points=points+excluded.points',(row['user_id'],points))
        try:
            await m.bot.send_message(row['user_id'],f'تحديث طلبك #{oid}: {new_status}.')
            if new_status=='delivered': await m.bot.send_message(row['user_id'],f'قيّم الطلب باستخدام /rate_order {oid} | 5 | تعليقك. كسبت {max(1,int(row["total"]))} نقطة ولاء.')
        except Exception: pass
        return await m.answer(f'تم تحديث الطلب #{oid} إلى {new_status}.')
    try: oid=int(parts)
    except: return await m.answer('استخدم /order رقم_الطلب لمعرفة حالته، أو للمسؤول: /order رقم | delivered')
    with connection() as db: row=db.execute('SELECT user_id,items,total,status FROM orders WHERE id=?',(oid,)).fetchone()
    if not row or row['user_id']!=m.from_user.id and not admin(m.from_user.id): return await m.answer('الطلب غير موجود أو ليس تابعًا لك.')
    await m.answer(f'الطلب #{oid}\nالحالة: {row["status"]}\nالعناصر: {row["items"]}\nالإجمالي: {row["total"]:.2f} USD')

@router.message(Command('rate_order'))
async def rate_order(m:Message):
    raw=(m.text or '').partition(' ')[2]
    p=[x.strip() for x in raw.split('|')]
    if len(p)<2: return await m.answer('بعد استلام طلبك، قيّمه: /rate_order رقم | 1-5 | تعليق اختياري')
    try: oid,rating=int(p[0]),int(p[1])
    except: return await m.answer('رقم الطلب والتقييم يجب أن يكونا أرقامًا.')
    if not 1<=rating<=5: return await m.answer('التقييم من 1 إلى 5.')
    with connection() as db:
        order=db.execute('SELECT user_id,status FROM orders WHERE id=?',(oid,)).fetchone()
        if not order or order['user_id']!=m.from_user.id or order['status']!='delivered': return await m.answer('يمكن تقييم طلبك بعد تسجيله كـ delivered فقط.')
        try: db.execute('INSERT INTO order_ratings(order_id,user_id,rating,comment,created_at) VALUES(?,?,?,?,?)',(oid,m.from_user.id,rating,p[2] if len(p)>2 else '',now_iso()))
        except: return await m.answer('سبق أن قيّمت هذا الطلب.')
    await m.answer('شكرًا على تقييمك.')

@router.message(Command('ratings'))
async def ratings(m:Message):
    if not admin(m.from_user.id): return await m.answer('هذا الأمر لمسؤول البوت فقط.')
    with connection() as db: rows=db.execute('SELECT rating,comment,order_id FROM order_ratings ORDER BY created_at DESC LIMIT 30').fetchall(); avg=db.execute('SELECT AVG(rating) a,COUNT(*) n FROM order_ratings').fetchone()
    await m.answer(f'متوسط التقييم {avg["a"] or 0:.2f}/5 من {avg["n"]} تقييمًا:\n'+'\n'.join(f'#{r["order_id"]} — {r["rating"]}/5: {r["comment"]}' for r in rows))

@router.message(Command('slot_add'))
async def slot_add(m:Message):
    if not admin(m.from_user.id): return await m.answer('إضافة المواعيد متاحة لمسؤول البوت فقط.')
    raw=(m.text or '').partition(' ')[2]
    if '|' not in raw: return await m.answer('أضف خانة متاحة: /slot_add الخدمة | 2026-11-15 14:00')
    service,when=[x.strip() for x in raw.split('|',1)]; parsed=parse_when(when)
    if not parsed: return await m.answer('تعذر فهم التاريخ والوقت.')
    with connection() as db:
        try: cur=db.execute('INSERT INTO available_slots(service,slot) VALUES(?,?)',(service,parsed.astimezone(timezone.utc).isoformat(timespec='minutes')))
        except: return await m.answer('الخانة موجودة بالفعل.')
    await m.answer(f'تمت إضافة الخانة #{cur.lastrowid}.')

@router.message(Command('slots'))
async def slots(m:Message):
    with connection() as db: rows=db.execute("SELECT id,service,slot FROM available_slots WHERE status='open' ORDER BY slot LIMIT 30").fetchall()
    await m.answer(('المواعيد المتاحة:\n'+'\n'.join(f'#{r["id"]} {r["service"]} — {r["slot"]}' for r in rows)) if rows else 'لا توجد خانات متاحة حاليًا.')

@router.message(Command('book_slot'))
async def book_slot(m:Message):
    try: sid=int((m.text or '').split()[1])
    except: return await m.answer('استخدم /book_slot رقم_الخانة بعد عرض /slots.')
    with connection() as db:
        row=db.execute("SELECT service,slot FROM available_slots WHERE id=? AND status='open'",(sid,)).fetchone()
        if not row: return await m.answer('الخانة غير متاحة أو سبق حجزها.')
        db.execute("UPDATE available_slots SET status='booked' WHERE id=? AND status='open'",(sid,))
        cur=db.execute('INSERT INTO bookings(user_id,chat_id,service,slot,status,created_at) VALUES(?,?,?,?,?,?)',(m.from_user.id,m.chat.id,row['service'],row['slot'],'new',now_iso()))
    await m.answer(f'أُرسل طلب الحجز #{cur.lastrowid} للمراجعة. الموعد غير مؤكد حتى موافقة المسؤول.')

@router.message(Command('booking_confirm'))
async def booking_confirm(m:Message):
    if not admin(m.from_user.id): return await m.answer('تأكيد الحجز للمسؤول فقط.')
    try: bid=int((m.text or '').split()[1])
    except: return await m.answer('استخدم /booking_confirm رقم الحجز')
    with connection() as db: cur=db.execute("UPDATE bookings SET status='confirmed' WHERE id=? AND status='new'",(bid,))
    await m.answer('تم تأكيد الحجز.' if cur.rowcount else 'الحجز غير موجود أو ليس جديدًا.')
