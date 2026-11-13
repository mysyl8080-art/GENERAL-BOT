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
HELP='''أرسل الملف مع تعليق يبدأ بـ /convert ثم نوع التحويل.

أمثلة:
• /convert pdf-to-docx | /convert docx-to-pdf | /convert pdf-to-xlsx | /convert pdf-to-pptx
• /convert pdf-to-txt | /convert pdf-to-images | /convert pdf-split 1-3
• /convert pdf-compress | /convert pdf-rotate 90 | /convert pdf-protect كلمة | /convert pdf-unlock كلمة
• /convert pdf-reorder 3,1,2 | /convert pdf-watermark نص | /convert pdf-page-numbers | /convert pdf-ocr
• /convert docx-to-txt | /convert txt-to-docx | /convert docx-to-html | /convert html-to-docx | /convert docx-to-md | /convert md-to-docx | /convert docx-to-pptx | /convert pptx-to-docx
• /convert xlsx-to-csv | /convert csv-to-xlsx | /convert xlsx-to-json | /convert json-to-xlsx | /convert csv-to-json | /convert json-to-csv
• /convert image-to-pdf | /convert image-to-jpg | /convert image-to-png | /convert image-to-webp
• /convert image-resize 800x600 | /convert image-compress | /convert image-sticker | /convert image-bg | /convert ocr
• /convert video-to-mp3 | /convert video-to-gif | /convert video-compress | /convert video-cut 00:00:10|20s
• /convert audio-to-mp3 | /convert audio-to-wav | /convert audio-to-ogg | /convert epub-to-pdf
• /convert unzip (ZIP/RAR/7z) | /convert zip (يرشف الملف المرسل)
• /archive add (على كل ملف) ثم /archive create لإنشاء ZIP من عدة ملفات.
• /pdfmerge add (على كل PDF) ثم /pdfmerge create لدمج عدة ملفات PDF.
• /convert pdf-to-epub | /convert epub-to-pdf

لتحويل Office إلى PDF: docx-to-pdf أو xlsx-to-pdf أو pptx-to-pdf. لمحوّل Word ⇄ PowerPoint استخدم docx-to-pptx أو pptx-to-docx.
حد الملف الافتراضي {limit}MB. بعض التحويلات تحتاج LibreOffice/FFmpeg/Tesseract المثبتة في صورة Railway.'''

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
