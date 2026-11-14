from __future__ import annotations
import asyncio, os, zipfile
from pathlib import Path
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from app.config import settings
from app.services.files import convert_file
from app.services.common import get_ai_reply

router=Router()
STAGED:dict[tuple[int,str],list[str]]={}
HELP='''📂 تحويل الملفات — اختار رقم وبس!

طريقة الاستخدام:
1) اختار رقم التحويل من القائمة.
2) ابعت الملف للبوت كـ «ملف / Document».
3) في تعليق الملف اكتب: /convert رقم العملية
4) استلم الملف بعد التحويل.

📄 ملفات PDF وWord:
1- PDF إلى Word
2- Word إلى PDF
3- PDF إلى نص
4- ضغط PDF وتقليل حجمه
5- صور إلى PDF
6- PDF إلى صور
7- تقسيم PDF (مثال: /convert 7 1-3)
8- تدوير صفحات PDF (مثال: /convert 8 90)
9- حماية PDF بكلمة مرور (مثال: /convert 9 كلمةالمرور)
10- فك حماية PDF (مثال: /convert 10 كلمةالمرور)
11- إضافة أرقام الصفحات
12- إضافة علامة مائية (مثال: /convert 12 سري)
13- PDF إلى Excel
14- PDF إلى PowerPoint
15- PDF إلى EPUB
16- EPUB إلى PDF

📝 ملفات Word وExcel:
17- Word إلى نص
18- نص إلى Word
19- Word إلى HTML
20- Word إلى Markdown
21- Word إلى PowerPoint
22- PowerPoint إلى Word
23- Excel إلى CSV
24- CSV إلى Excel
25- Excel إلى JSON
26- JSON إلى Excel
27- CSV إلى JSON
28- JSON إلى CSV

🖼 الصور:
29- صورة إلى JPG
30- صورة إلى PNG
31- صورة إلى WebP
32- تصغير أبعاد الصورة (مثال: /convert 32 800x600)
33- ضغط الصورة
34- استخراج الكلام من صورة (OCR)

🎬 الفيديو والصوت:
35- فيديو إلى MP3
36- فيديو إلى GIF
37- ضغط الفيديو
38- قص الفيديو (مثال: /convert 38 00:00:10|20s)
39- صوت إلى MP3
40- صوت إلى WAV
41- صوت إلى OGG

🗜 ملفات مضغوطة:
42- فك ضغط ZIP أو RAR أو 7z
43- ضغط الملف في ZIP

📚 عمليات إضافية:
44- دمج ملفات PDF: ابعت كل PDF بالتعليق /pdfmerge add ثم اكتب /pdfmerge create.
45- جمع عدة ملفات في ZIP: ابعت كل ملف بالتعليق /archive add ثم اكتب /archive create.

💡 أمثلة سهلة:
• لتحويل PDF إلى Word: ابعت ملف PDF واكتب في التعليق /convert 1
• لتحويل Word إلى PDF: ابعت ملف Word واكتب /convert 2
• لضغط PDF: ابعت الملف واكتب /convert 4

الحد الأقصى لحجم الملف: {limit}MB.
لو ظهر لك خطأ، ابعت رسالة الخطأ كما هي.'''

# أرقام التحويلات — الأرقام الظاهرة للمستخدم تقابل عمليات التحويل الفعلية.
CONVERT_OPTIONS={
 1:('pdf-docx',''), 2:('office-pdf',''), 3:('pdf-txt',''), 4:('pdf-compress',''),
 5:('image-pdf',''), 6:('pdf-images',''), 7:('pdf-split',''), 8:('pdf-rotate',''),
 9:('pdf-protect',''), 10:('pdf-unlock',''), 11:('pdf-page-numbers',''), 12:('pdf-watermark',''),
 13:('pdf-xlsx',''), 14:('pdf-pptx',''), 15:('pdf-epub',''), 16:('epub-pdf',''),
 17:('docx-txt',''), 18:('text-docx',''), 19:('docx-html',''), 20:('docx-md',''),
 21:('docx-pptx',''), 22:('pptx-docx',''), 23:('xlsx-csv',''), 24:('csv-xlsx',''),
 25:('xlsx-json',''), 26:('json-xlsx',''), 27:('csv-json',''), 28:('json-csv',''),
 29:('image-jpg',''), 30:('image-png',''), 31:('image-webp',''), 32:('image-resize',''),
 33:('image-compress',''), 34:('ocr',''), 35:('video-mp3',''), 36:('video-gif',''),
 37:('video-compress',''), 38:('video-cut',''), 39:('audio-mp3',''), 40:('audio-wav',''),
 41:('audio-ogg',''), 42:('archive-unpack',''), 43:('archive-pack','')
}

@router.message(Command('convert'))
async def convert_help(m:Message):
    raw=(m.text or '').partition(' ')[2].strip()
    if raw: return await m.answer('أرسل الملف كـ Document واجعل التعليق: /convert '+raw+'\nتأكد أن العملية مدعومة بنوع الملف.\nاكتب /convert لعرض القائمة.')
    await m.answer(HELP.format(limit=settings.max_upload_mb))

@router.message(Command('archive'))
async def archive_command(m:Message):
    action=(m.text or '').partition(' ')[2].strip().lower()
    key=(m.from_user.id,'archive')
    if action=='create':
        files=STAGED.get(key,[])
        if not files: return await m.answer('لا توجد ملفات مؤقتة. أرسل كل ملف مع التعليق /archive add ثم اكتب /archive create.')
        out=os.path.join(settings.temp_dir,f'archive-{m.from_user.id}.zip')
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
            for f in files: z.write(f,Path(f).name)
        await m.answer_document(FSInputFile(out),caption=f'أُنشئ أرشيف من {len(files)} ملفات.')
        for f in files:
            try: os.unlink(f)
            except: pass
        STAGED.pop(key,None)
        try: os.unlink(out)
        except: pass
    elif action=='clear':
        for f in STAGED.pop(key,[]):
            try: os.unlink(f)
            except: pass
        await m.answer('تم مسح قائمة الملفات المؤقتة.')
    else: await m.answer('أرسل كل ملف مع التعليق /archive add، ثم /archive create. لمسح القائمة: /archive clear.')

@router.message(Command('pdfmerge'))
async def pdfmerge_command(m:Message):
    action=(m.text or '').partition(' ')[2].strip().lower(); key=(m.from_user.id,'pdfmerge')
    if action=='create':
        files=STAGED.get(key,[])
        if len(files)<2: return await m.answer('يلزم ملفا PDF على الأقل. أرسل كل ملف مع التعليق /pdfmerge add ثم /pdfmerge create.')
        try:
            from pypdf import PdfReader, PdfWriter
            writer=PdfWriter()
            for f in files:
                for page in PdfReader(f).pages: writer.add_page(page)
            out=os.path.join(settings.temp_dir,f'merged-{m.from_user.id}.pdf')
            with open(out,'wb') as f: writer.write(f)
            await m.answer_document(FSInputFile(out),caption=f'تم دمج {len(files)} ملفات PDF.')
            os.unlink(out)
        except Exception as e: await m.answer(f'تعذر الدمج: {e}')
        finally:
            for f in files:
                try: os.unlink(f)
                except: pass
            STAGED.pop(key,None)
    elif action=='clear':
        for f in STAGED.pop(key,[]):
            try: os.unlink(f)
            except: pass
        await m.answer('تم مسح الملفات المرحلية.')
    else: await m.answer('أرسل كل PDF مع التعليق /pdfmerge add، ثم اكتب /pdfmerge create. لمسحها: /pdfmerge clear.')

@router.message(F.photo)
async def photo_tools(m:Message,bot):
    caption=(m.caption or '').strip()
    if not caption.lower().startswith('/translate') and not caption.lower().startswith('/ocr'):
        return
    if caption.lower().startswith('/translate') and '|' in caption:
        lang=caption.split('|',1)[1].strip()
    else: lang=caption.partition(' ')[2].strip() or 'ara+eng'
    f=await bot.get_file(m.photo[-1].file_id)
    path=os.path.join(settings.temp_dir,f'{m.from_user.id}-{m.photo[-1].file_unique_id}.jpg')
    try:
        await bot.download_file(f.file_path,path)
        import pytesseract
        from PIL import Image
        text=pytesseract.image_to_string(Image.open(path),lang='ara+eng').strip()
        if not text: return await m.answer('لم أستطع استخراج نص. تأكد من وضوح الصورة وتثبيت Tesseract.')
        if caption.lower().startswith('/translate'):
            try: text=get_ai_reply(f'ترجم النص التالي إلى {lang}. أخرج الترجمة فقط:\n{text}','أنت مترجم دقيق.')
            except Exception as e: return await m.answer(f'تم استخراج النص لكن الترجمة غير متاحة: {e}\n\nالنص:\n{text[:3500]}')
        await m.answer(text[:4000])
    except Exception as e: await m.answer(f'تعذر تنفيذ OCR: {e}')
    finally:
        try: os.unlink(path)
        except: pass

@router.message(F.document)
async def document_tools(m:Message,bot):
    caption=(m.caption or '').strip()
    stage=None
    if caption.lower().startswith('/archive add'): stage='archive'
    elif caption.lower().startswith('/pdfmerge add'): stage='pdfmerge'
    if stage:
        size=m.document.file_size or 0
        if size>settings.max_upload_mb*1024*1024: return await m.answer(f'حجم الملف أكبر من الحد ({settings.max_upload_mb}MB).')
        name=Path(m.document.file_name or 'file').name
        if stage=='pdfmerge' and Path(name).suffix.lower()!='.pdf': return await m.answer('ارفع ملف PDF فقط مع /pdfmerge add.')
        target=os.path.join(settings.temp_dir,f'stage-{m.from_user.id}-{m.document.file_unique_id}-{name}')
        tgfile=await bot.get_file(m.document.file_id); await bot.download_file(tgfile.file_path,target)
        STAGED.setdefault((m.from_user.id,stage),[]).append(target)
        return await m.answer(f'تمت إضافة الملف #{len(STAGED[(m.from_user.id,stage)])}. أكمل الرفع ثم نفّذ أمر create.')
    if caption.lower()!='/convert' and not caption.lower().startswith('/convert '): return
    raw=caption.partition(' ')[2].strip()
    if not raw: return await m.answer(HELP.format(limit=settings.max_upload_mb))
    op,*rest=raw.split(' ',1); extra=rest[0].strip() if rest else ''
    # يقبل رقم العملية بدل الاسم الطويل، مع إبقاء الاسم القديم متاحًا.
    if op.isdigit():
        option=CONVERT_OPTIONS.get(int(op))
        if not option:
            return await m.answer('رقم التحويل غير موجود. اكتب /convert لعرض الأرقام المتاحة.')
        op=option[0]
        if op in ('pdf-split','pdf-rotate','pdf-protect','pdf-unlock','pdf-watermark','image-resize','video-cut') and not extra:
            examples={'pdf-split':'1-3','pdf-rotate':'90','pdf-protect':'كلمةالمرور','pdf-unlock':'كلمةالمرور','pdf-watermark':'نص العلامة','image-resize':'800x600','video-cut':'00:00:10|20s'}
            return await m.answer('تمام! ابعت الملف مرة تانية واكتب في التعليق:\n/convert '+str(int(raw.split()[0]))+' '+examples[op])

    if '|' in extra and op not in ('video-cut',): extra=extra.split('|',1)[0].strip() if op=='video-cut' else extra
    size=m.document.file_size or 0
    if size>settings.max_upload_mb*1024*1024: return await m.answer(f'حجم الملف أكبر من الحد ({settings.max_upload_mb}MB).')
    original=Path(m.document.file_name or 'upload.bin').name
    suffix=Path(original).suffix[:12]
    src=os.path.join(settings.temp_dir,f'{m.from_user.id}-{m.document.file_unique_id}{suffix}')
    await m.answer('جاري التحويل، قد يستغرق الملف الكبير بعض الوقت…')
    try:
        tgfile=await bot.get_file(m.document.file_id); await bot.download_file(tgfile.file_path,src)
        outputs=await asyncio.to_thread(convert_file,src,op,extra)
        if len(outputs)>5: await m.answer(f'أنتج التحويل {len(outputs)} صفحات؛ أُرسلها مجمعة في ملف ZIP إن كان متاحًا.')
        for output in outputs:
            p=Path(output)
            if p.stat().st_size>49*1024*1024: raise RuntimeError(f'الملف الناتج {p.name} أكبر من حد الإرسال. جرّب ضغطًا أقل أو ملفًا أصغر.')
            await m.answer_document(FSInputFile(str(p)),caption=f'تم: {op} — {p.name}')
    except Exception as e:
        await m.answer(f'فشل التحويل: {str(e)[:900]}\nراجع نوع الملف واكتب /convert للمساعدة.')
    finally:
        try: os.unlink(src)
        except: pass
        # Clean files produced by this request only.
        try:
            import shutil
            for child in Path(settings.temp_dir).glob('out-*'):
                if child.is_dir() and child.stat().st_mtime<__import__('time').time()-3600: shutil.rmtree(child,ignore_errors=True)
        except: pass
