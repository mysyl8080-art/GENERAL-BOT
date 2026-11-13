from __future__ import annotations
import json, os, re, tempfile
from datetime import datetime, timezone
from pathlib import Path
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from app.db import connection
from app.config import settings
from app.services.common import get_ai_reply, now_iso, parse_when

router=Router()

@router.message(Command('idea'))
async def idea(m:Message):
    raw=(m.text or '').partition(' ')[2].strip()
    if not raw: return await m.answer('استخدم /idea نوع الفكرة | المجال (مثال: /idea اسم مشروع | متجر قهوة)')
    parts=[x.strip() for x in raw.split('|',1)]; ask=f'اقترح 10 {parts[0]} مميزة لمجال {parts[1] if len(parts)>1 else "عام"}. اجعلها قصيرة ومختلفة.'
    try: result=get_ai_reply(ask,'أنت مستشار إبداعي عربي. أعط اقتراحات قابلة للاستخدام ولا تكرر الاسم نفسه.')
    except Exception:
        result='اقتراحات أولية:\n'+ '\n'.join(f'• {parts[1] if len(parts)>1 else "فكرة"} {x}' for x in ['نقطة','مسار','نبض','أفق','خطوة','لمسة','بداية','فكرة','وصلة','إبداع'])
    await m.answer(result[:3800]+'\n\nلحفظ اقتراح في المفضلة: /favorite نص الاقتراح')

@router.message(Command('favorite'))
async def favorite(m:Message):
    text=(m.text or '').partition(' ')[2].strip()
    if not text: return await m.answer('احفظ فكرة أو اسمًا: /favorite النص')
    with connection() as db: cur=db.execute('INSERT INTO idea_favorites(user_id,text,created_at) VALUES(?,?,?)',(m.from_user.id,text,now_iso()))
    await m.answer(f'حُفظت فكرتك #{cur.lastrowid}. اعرضها عبر /favorites.')

@router.message(Command('favorites'))
async def favorites(m:Message):
    with connection() as db: rows=db.execute('SELECT id,text FROM idea_favorites WHERE user_id=? ORDER BY id DESC LIMIT 30',(m.from_user.id,)).fetchall()
    await m.answer(('المفضلة:\n'+'\n'.join(f'#{r["id"]}: {r["text"]}' for r in rows)) if rows else 'لا توجد أفكار محفوظة.')

@router.message(Command('language'))
async def language(m:Message):
    target=(m.text or '').partition(' ')[2].strip()
    if not target: return await m.answer('حدد لغة التدريب: /language English أو /language Français. ثم تدرّب بـ /practice جملتك.')
    with connection() as db: db.execute('INSERT INTO language_preferences(user_id,language) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET language=excluded.language',(m.from_user.id,target))
    await m.answer(f'تم ضبط لغة التدريب: {target}. أرسل /practice جملة قصيرة لبدء المحادثة.')

@router.message(Command('practice'))
async def practice(m:Message):
    text=(m.text or '').partition(' ')[2].strip()
    if not text: return await m.answer('اكتب جملة باللغة التي تتعلمها: /practice I have went to school.')
    with connection() as db: row=db.execute('SELECT language FROM language_preferences WHERE user_id=?',(m.from_user.id,)).fetchone()
    target=row['language'] if row else 'English'
    prompt=f'الطالب يتدرب على {target}. صحح جملته إن لزم، وضح الخطأ بالعربية باختصار، ثم واصل محادثة قصيرة بسؤال واحد باللغة المستهدفة. جملته: {text}'
    try: answer=get_ai_reply(prompt,'أنت مدرب لغة مشجع. لا تعط أكثر من تصحيح واحد وسؤال متابعة واحد.')
    except Exception as e: answer=str(e)
    await m.answer(answer[:3500])

@router.message(Command('post'))
async def post_assistant(m:Message):
    raw=(m.text or '').partition(' ')[2].strip()
    if not raw: return await m.answer('استخدم /post موضوع المنشور | النبرة (مثال: إطلاق منتج جديد | ودية)')
    try: answer=get_ai_reply(f'اكتب منشورًا عربيًا جاهزًا للنشر عن: {raw}. قدم عنوانًا، نصًا قصيرًا، ودعوة واضحة للتفاعل، ثم حتى 5 وسوم مناسبة.','أنت محرر محتوى عربي؛ لا تخترع أسعارًا أو حقائق.')
    except Exception as e: answer=str(e)
    await m.answer(answer[:3500])

def read_attachment(path:str,name:str)->str:
    suffix=Path(name).suffix.lower()
    if suffix=='.pdf':
        import fitz
        doc=fitz.open(path)
        if len(doc)>80: raise ValueError('الحد 80 صفحة للمستند الواحد.')
        return '\n'.join(page.get_text() for page in doc)[:14000]
    if suffix=='.docx':
        from docx import Document
        doc=Document(path); return '\n'.join(p.text for p in doc.paragraphs)[:14000]
    if suffix in ('.txt','.md','.csv'):
        return Path(path).read_text(encoding='utf8',errors='replace')[:14000]
    raise ValueError('الصيغ المدعومة: PDF وDOCX وTXT وMD وCSV.')

@router.message(F.document & (F.caption.startswith('/ask_file') | F.caption.startswith('/quiz_from_file')))
async def study_file(m:Message,bot):
    doc=m.document
    if doc.file_size and doc.file_size>settings.max_upload_mb*1024*1024: return await m.answer(f'حجم الملف يتجاوز {settings.max_upload_mb}MB.')
    caption=(m.caption or '').strip(); is_quiz=caption.startswith('/quiz_from_file')
    instruction=caption.partition(' ')[2].strip()
    if not is_quiz and not instruction: return await m.answer('أضف سؤالك في التعليق: /ask_file ما الفكرة الأساسية؟')
    if is_quiz and not settings.openai_api_key: return await m.answer('إنشاء الاختبار من الملف يحتاج OPENAI_API_KEY.')
    if not is_quiz and not settings.openai_api_key: return await m.answer('شرح الملف يحتاج OPENAI_API_KEY. سيُرسل النص المستخرج لمزوّد الذكاء الاصطناعي عند تفعيل المفتاح.')
    path=None
    try:
        suffix=Path(doc.file_name or 'file').suffix
        with tempfile.NamedTemporaryFile(suffix=suffix,delete=False) as f: path=f.name
        tg=await bot.get_file(doc.file_id); await bot.download_file(tg.file_path,path)
        text=read_attachment(path,doc.file_name or '')
        if not text.strip(): return await m.answer('الملف لا يحتوي نصًا قابلًا للاستخراج؛ قد يكون PDF ممسوحًا ضوئيًا.')
        if is_quiz:
            result=get_ai_reply('أنشئ اختبار مراجعة من 5 أسئلة اختيار من متعدد عن النص، وأربع إجابات لكل سؤال، وحدد الإجابة الصحيحة. أخرجها بالعربية بتنسيق مرقم واضح، ثم مفتاح الإجابات في النهاية.\nالنص:\n'+text,'أنت معلم. لا تسأل عن معلومات غير موجودة في النص.')
            await m.answer(('اختبار مستخرج من الملف:\n'+result)[:3900])
        else:
            result=get_ai_reply(f'أجب عن السؤال اعتمادًا على محتوى الملف فقط. إذا لم تجد الإجابة فقل ذلك.\nالسؤال: {instruction}\n\nمحتوى الملف:\n{text}','أنت مساعد دراسة يلخص المستندات بدقة.')
            await m.answer(result[:3900])
    except Exception as e: await m.answer(f'تعذر معالجة الملف: {e}')
    finally:
        if path and os.path.exists(path): os.unlink(path)

@router.message(F.voice & F.caption.startswith('/audio_tasks'))
async def audio_tasks(m:Message,bot):
    if not settings.openai_api_key: return await m.answer('تحويل الصوت إلى مهام يحتاج OPENAI_API_KEY.')
    path=None
    try:
        from openai import OpenAI
        with tempfile.NamedTemporaryFile(suffix='.ogg',delete=False) as f: path=f.name
        tg=await bot.get_file(m.voice.file_id); await bot.download_file(tg.file_path,path)
        kwargs={'api_key':settings.openai_api_key}
        if settings.openai_base_url: kwargs['base_url']=settings.openai_base_url
        client=OpenAI(**kwargs,timeout=90,max_retries=1)
        with open(path,'rb') as audio: transcript=client.audio.transcriptions.create(model='whisper-1',file=audio).text
        raw=get_ai_reply('استخرج المهام القابلة للتنفيذ من التفريغ الصوتي. أخرج JSON صالحًا بالشكل {"tasks":[{"text":"...","when":"عبارة موعد أو فارغ"}]}. لا تخترع موعدًا.\nالنص: '+transcript,'أخرج JSON فقط.')
        match=re.search(r'\{.*\}',raw,re.S); data=json.loads(match.group(0) if match else raw)
        tasks=data.get('tasks',[])
        created=[]
        with connection() as db:
            for item in tasks[:8]:
                text=str(item.get('text','')).strip()
                if not text: continue
                cur=db.execute('INSERT INTO tasks(owner_id,chat_id,text,created_at) VALUES(?,?,?,?)',(m.from_user.id,m.chat.id,text,now_iso()))
                when=str(item.get('when','')).strip(); due=parse_when(when) if when else None
                if due and due>datetime.now(due.tzinfo): db.execute('INSERT INTO reminders(user_id,chat_id,due_at,text) VALUES(?,?,?,?)',(m.from_user.id,m.chat.id,due.astimezone(timezone.utc).isoformat(),text))
                created.append(f'#{cur.lastrowid} {text}'+(f' (تذكير {when})' if due else ''))
        await m.answer(('أُنشئت المهام من التسجيل:\n'+'\n'.join(created)) if created else 'لم أستخرج مهام واضحة. النص المسموع: '+transcript[:1500])
    except Exception as e: await m.answer(f'تعذر تحويل الصوت إلى مهام: {e}')
    finally:
        if path and os.path.exists(path): os.unlink(path)
