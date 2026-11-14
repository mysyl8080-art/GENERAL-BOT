from __future__ import annotations
import io, random, re, requests
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile
from app.config import settings
from app.services.common import get_ai_reply, extract_web_text, safe_url, now_iso
from app.db import connection
from app.routers_learning import POLL_CORRECT

router=Router()
MOVIES=['The Shawshank Redemption','Inception','Interstellar','The Grand Budapest Hotel','Parasite','Spirited Away','Knives Out']
FOOD=['بيتزا','كشري','سوشي','برغر','مكرونة','شاورما','سلطة']
JOKES=['مرة كمبيوتر راح للدكتور، قال له: عندي فيروس!','واحد بخيل اشترى ساعة، رجّعها عشان عقاربها بتاكل!','مرة كتاب رياضيات زعل، قالوله مالك؟ قال: عندي مسائل كتير!']
QUOTES=['رحلة الألف ميل تبدأ بخطوة.','النجاح هو مجموع الجهود الصغيرة المتكررة يومًا بعد يوم.','لا تؤجل عمل اليوم إلى الغد.','التعلم كنز يتبع صاحبه أينما ذهب.']
GUESS_ROUNDS={}

@router.message(Command('ask'))
async def ask_ai(m:Message):
    prompt=(m.text or '').partition(' ')[2].strip()
    if not prompt: return await m.answer('اكتب سؤالك بعد /ask. يتطلب OPENAI_API_KEY.')
    try: answer=get_ai_reply(prompt)
    except Exception as e: answer=str(e)
    await m.answer(answer[:4000])

@router.message(Command('tutor'))
async def tutor(m:Message):
    prompt=(m.text or '').partition(' ')[2].strip()
    if not prompt: return await m.answer('مثال: /tutor اشرح قانون نيوتن الثاني بمثال بسيط')
    try: answer=get_ai_reply(prompt,'أنت مساعد دراسي عربي. اشرح خطوة بخطوة، اسأل أسئلة توضيحية عند الحاجة، ولا تدّعِ اليقين عند عدم التأكد.')
    except Exception as e: answer=str(e)
    await m.answer(answer[:4000])

@router.message(Command('summarize'))
async def summarize(m:Message):
    url=(m.text or '').partition(' ')[2].strip()
    if not url: return await m.answer('استخدم /summarize رابط_مقال أو رابط YouTube عام. يحتاج تلخيص المحتوى إلى OPENAI_API_KEY.')
    if not safe_url(url): return await m.answer('الرابط غير صالح.')
    try:
        text=''
        if 'youtube.com' in url or 'youtu.be' in url:
            vid=re.search(r'(?:v=|youtu\.be/|shorts/)([\w-]{11})',url)
            if vid:
                try:
                    from youtube_transcript_api import YouTubeTranscriptApi
                    transcript=YouTubeTranscriptApi().fetch(vid.group(1))
                    text=' '.join(x.text for x in transcript)[:18000]
                except Exception: pass
        if not text: text=extract_web_text(url)
        result=get_ai_reply('لخّص المحتوى التالي بالعربية في نقاط رئيسية، مع ذكر الفكرة الأساسية:\n'+text,'أنت محرر عربي تلخص المحتوى بدقة ولا تخترع معلومات.')
        await m.answer(result[:4000])
    except Exception as e: await m.answer(f'تعذر التلخيص: {e}')

@router.message(Command('translate'))
async def translate(m:Message):
    raw=(m.text or '').partition(' ')[2].strip()
    if '|' not in raw: return await m.answer('استخدم: /translate English | صباح الخير\nللصور أرسل الصورة واكتب في التعليق /translate English')
    lang,text=[x.strip() for x in raw.split('|',1)]
    if not lang or not text: return await m.answer('حدّد اللغة والنص بعد علامة |')
    try: result=get_ai_reply(f'ترجم النص التالي إلى {lang}. أخرج الترجمة فقط:\n{text}','أنت مترجم محترف، حافظ على المعنى والنبرة.')
    except Exception as e: result=str(e)
    await m.answer(result[:4000])

@router.message(Command('transcribe'))
async def transcribe_help(m:Message): await m.answer('للتحويل إلى نص، أرسل ملف صوت/رسالة صوتية مع تعليق /transcribe. يتطلب OPENAI_API_KEY، والملفات تُرسل لمزوّد الخدمة.')

@router.message(F.voice | F.audio | (F.document & (F.document.mime_type.startswith('audio/') | F.document.mime_type.startswith('video/'))))
async def transcribe_audio(m:Message,bot):
    caption=(m.caption or '').lower()
    if '/transcribe' not in caption: return
    if not settings.openai_api_key: return await m.answer('التفريغ الصوتي يحتاج OPENAI_API_KEY. لم يتم رفع ملفك لأي جهة خارجية.')
    obj=m.voice or m.audio or m.document
    if obj.file_size and obj.file_size>settings.max_upload_mb*1024*1024: return await m.answer(f'حجم الملف يتجاوز {settings.max_upload_mb}MB.')
    import tempfile, os
    from openai import OpenAI
    path=None
    try:
        with tempfile.NamedTemporaryFile(suffix='.ogg' if m.voice else '.mp3',delete=False) as f: path=f.name
        file=await bot.get_file(obj.file_id); await bot.download_file(file.file_path,path)
        kwargs={'api_key':settings.openai_api_key}
        if settings.openai_base_url: kwargs['base_url']=settings.openai_base_url
        client=OpenAI(**kwargs,timeout=90,max_retries=1)
        with open(path,'rb') as audio: result=client.audio.transcriptions.create(model='whisper-1',file=audio)
        await m.answer(('النص المستخرج:\n'+result.text)[:4000])
    except Exception as e: await m.answer(f'تعذر التفريغ: {e}')
    finally:
        if path and os.path.exists(path): os.unlink(path)

@router.message(Command('speak'))
async def speak(m:Message):
    text=(m.text or '').partition(' ')[2].strip()
    if not text: return await m.answer('استخدم /speak النص لتحويله إلى صوت. يتطلب OPENAI_API_KEY.')
    if not settings.openai_api_key: return await m.answer('تحويل النص إلى صوت يحتاج OPENAI_API_KEY.')
    import tempfile, os
    from openai import OpenAI
    kwargs={'api_key':settings.openai_api_key}
    if settings.openai_base_url: kwargs['base_url']=settings.openai_base_url
    path=None
    try:
        client=OpenAI(**kwargs,timeout=90)
        response=client.audio.speech.create(model='tts-1',voice='alloy',input=text[:3500])
        with tempfile.NamedTemporaryFile(suffix='.mp3',delete=False) as f: path=f.name
        response.stream_to_file(path)
        from aiogram.types import FSInputFile
        await m.answer_audio(FSInputFile(path),caption='الصوت المُنشأ')
    except Exception as e: await m.answer(f'تعذر إنشاء الصوت: {e}')
    finally:
        if path and os.path.exists(path): os.unlink(path)

@router.message(Command('currency'))
async def currency(m:Message):
    args=(m.text or '').split()
    if len(args)!=4: return await m.answer('تحويل عملة: /currency 100 USD EGP\nالمصدر: Frankfurter؛ قد لا تتضمن أسعارًا لحظية.')
    try:
        amount=float(args[1]); frm=args[2].upper(); to=args[3].upper()
        r=requests.get(f'https://api.frankfurter.app/latest?amount={amount}&from={frm}&to={to}',timeout=12); r.raise_for_status(); data=r.json()
        await m.answer(f'{amount:g} {frm} ≈ {data["rates"][to]:,.4f} {to}\nالسعر مرجعي وقد لا يكون لحظيًا.')
    except Exception as e: await m.answer(f'تعذر جلب السعر: {e}')

@router.message(Command('crypto'))
async def crypto(m:Message):
    coin=(m.text or '').partition(' ')[2].strip().lower() or 'bitcoin'
    try:
        r=requests.get('https://api.coingecko.com/api/v3/simple/price',params={'ids':coin,'vs_currencies':'usd,egp'},timeout=12); r.raise_for_status(); data=r.json()[coin]
        await m.answer(f'{coin}: \${data.get("usd","—")} USD | \${data.get("egp","—")} EGP\nالسعر متغير وليس نصيحة استثمارية.')
    except Exception: await m.answer('تعذر جلب العملة. أرسل اسمًا مثل bitcoin أو ethereum.')

@router.message(Command('gold'))
async def gold(m:Message):
    if not settings.gold_api_key: return await m.answer('سعر الذهب يتطلب GOLD_API_KEY من مزود أسعار معادن. لا توجد مفتاح خدمة مضمّن.')
    try:
        r=requests.get('https://www.goldapi.io/api/XAU/USD',headers={'x-access-token':settings.gold_api_key,'Content-Type':'application/json'},timeout=12); r.raise_for_status(); d=r.json()
        await m.answer(f'سعر أونصة الذهب: \${d.get("price")} USD (وقت التحديث: {d.get("timestamp","غير متاح")})')
    except Exception as e: await m.answer(f'تعذر جلب سعر الذهب: {e}')

@router.message(Command('prayer'))
async def prayer(m:Message):
    city=(m.text or '').partition(' ')[2].strip() or 'القاهرة'
    try:
        r=requests.get('https://api.aladhan.com/v1/timingsByCity',params={'city':city,'country':'Egypt','method':5},timeout=15); r.raise_for_status(); d=r.json()['data']['timings']
        names=['Fajr','Sunrise','Dhuhr','Asr','Maghrib','Isha']; trans={'Fajr':'الفجر','Sunrise':'الشروق','Dhuhr':'الظهر','Asr':'العصر','Maghrib':'المغرب','Isha':'العشاء'}
        await m.answer(f'مواقيت الصلاة — {city}:\n'+'\n'.join(f'{trans[n]}: {d[n]}' for n in names))
    except Exception as e: await m.answer(f'تعذر جلب المواقيت: {e}')

@router.message(Command('adhkar'))
async def adhkar(m:Message):
    items=['سبحان الله وبحمده، سبحان الله العظيم.','أستغفر الله وأتوب إليه.','اللهم صل وسلم على نبينا محمد.','لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير.','حسبي الله لا إله إلا هو عليه توكلت وهو رب العرش العظيم.']
    await m.answer('ذكر اليوم:\n'+random.choice(items))

@router.message(Command('qr'))
async def qr(m:Message):
    text=(m.text or '').partition(' ')[2].strip()
    if not text: return await m.answer('استخدم /qr النص أو الرابط لإنشاء رمز QR.')
    try:
        import qrcode
        img=qrcode.make(text[:2000]); b=io.BytesIO(); img.save(b,format='PNG'); b.seek(0)
        await m.answer_photo(BufferedInputFile(b.read(),filename='qr.png'),caption='رمز QR')
    except Exception as e: await m.answer(f'تعذر إنشاء الرمز: {e}')

@router.message(Command('short'))
async def short(m:Message):
    url=(m.text or '').partition(' ')[2].strip()
    if not safe_url(url): return await m.answer('أرسل رابطًا كاملًا يبدأ بـ http:// أو https://')
    try:
        r=requests.get('https://is.gd/create.php',params={'format':'simple','url':url},timeout=15); r.raise_for_status()
        if r.text.startswith('Error:'): raise ValueError(r.text)
        await m.answer('الرابط المختصر: '+r.text.strip())
    except Exception as e: await m.answer(f'تعذر الاختصار: {e}')

@router.message(Command('price_alert'))
async def price_alert(m:Message):
    raw=(m.text or '').partition(' ')[2]
    if '|' not in raw: return await m.answer('استخدم: /price_alert https://example.com/product | 1200\nيُجلب السعر من الصفحة بشكل تقريبي؛ قد لا تعمل الصفحات التي تحجب الروبوتات.')
    url,target=[x.strip() for x in raw.split('|',1)]
    if not safe_url(url): return await m.answer('الرابط غير صالح.')
    try: target=float(target)
    except: return await m.answer('السعر المستهدف يجب أن يكون رقمًا.')
    with connection() as db: db.execute('INSERT INTO price_alerts(user_id,url,target,created_at) VALUES(?,?,?,?)',(m.from_user.id,url,target,now_iso()))
    await m.answer('تم حفظ التنبيه. سيفحص الرابط دوريًا إذا تعذر استخراج السعر فسيتم تجاهله.')

@router.message(Command('joke'))
async def joke(m:Message): await m.answer(random.choice(JOKES))

@router.message(Command('quote'))
async def quote(m:Message): await m.answer(random.choice(QUOTES))

@router.message(Command('daily_on'))
async def daily_on(m:Message):
    with connection() as db: db.execute('INSERT INTO daily_subscriptions(user_id,chat_id) VALUES(?,?) ON CONFLICT(user_id,chat_id) DO NOTHING',(m.from_user.id,m.chat.id))
    await m.answer('تم تفعيل إرسال نكتة/اقتباس يومي هنا. للإيقاف استخدم /daily_off.')

@router.message(Command('daily_off'))
async def daily_off(m:Message):
    with connection() as db: db.execute('DELETE FROM daily_subscriptions WHERE user_id=? AND chat_id=?',(m.from_user.id,m.chat.id))
    await m.answer('تم إيقاف الإرسال اليومي في هذه المحادثة.')

@router.message(Command('random'))
async def random_pick(m:Message):
    kind=(m.text or '').partition(' ')[2].strip().lower()
    if kind in ('movie','فيلم','أفلام'): value=random.choice(MOVIES); title='اقتراح فيلم'
    elif kind in ('restaurant','food','مطعم','أكل'): value=random.choice(FOOD); title='اختيار عشوائي للطعام/المطعم'
    else: return await m.answer('استخدم /random movie أو /random restaurant')
    await m.answer(f'{title}: {value}')

@router.message(Command('trivia'))
async def trivia(m:Message):
    poll=await m.answer_poll('أي كوكب يُعرف بالكوكب الأحمر؟',['الزهرة','المريخ','زحل'],type='quiz',correct_option_id=1,is_anonymous=False,open_period=30)
    POLL_CORRECT[poll.poll.id]=(1,m.chat.id)

@router.message(Command('guess'))
async def guess(m:Message):
    raw=(m.text or '').partition(' ')[2].strip()
    if not raw:
        GUESS_ROUNDS[m.from_user.id]=random.randint(1,20)
        await m.answer('اخترت رقمًا بين 1 و20. خمنه باستخدام /guess رقم. لديك حتى تصيب!'); return
    try: n=int(raw)
    except: return await m.answer('اكتب عددًا بين 1 و20 بعد /guess')
    lucky=GUESS_ROUNDS.get(m.from_user.id)
    if not lucky: return await m.answer('ابدأ جولة جديدة بكتابة /guess أولًا.')
    if n==lucky:
        GUESS_ROUNDS.pop(m.from_user.id,None); await m.answer('صحيح! فزت. اكتب /guess لبدء جولة جديدة.')
    elif n<lucky: await m.answer('الرقم أكبر. حاول مرة أخرى باستخدام /guess رقم.')
    else: await m.answer('الرقم أصغر. حاول مرة أخرى باستخدام /guess رقم.')

@router.message(Command('adventure'))
async def adventure(m:Message):
    choice=(m.text or '').partition(' ')[2].strip().lower()
    if not choice: return await m.answer('مغامرة قصيرة: أمامك كهف وغابة. اختر /adventure cave أو /adventure forest')
    answers={'cave':'دخلت الكهف فوجدت صندوقًا مضيئًا وخريطة كنز. نهاية سعيدة!','forest':'اتبعت أثرًا في الغابة فقادك إلى قرية آمنة. نهاية سعيدة!','beach':'وجدت قاربًا على الشاطئ وأبحرت إلى الجزيرة التالية.','hill':'صعدت التل واكتشفت منارة ترشد السفن.','left':'الباب الأيسر يقود إلى مكتبة سرية.','right':'الباب الأيمن يقود إلى حديقة مضيئة.'}
    await m.answer(answers.get(choice,'اختر cave أو forest بعد /adventure.'))
