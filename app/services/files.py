from __future__ import annotations
import io, subprocess, tempfile, zipfile
from pathlib import Path
from app.config import settings

ALIASES={
 'pdf-to-docx':'pdf-docx','pdf->word':'pdf-docx','pdf-to-word':'pdf-docx',
 'docx-to-pdf':'office-pdf','word-to-pdf':'office-pdf','xlsx-to-pdf':'office-pdf','excel-to-pdf':'office-pdf','pptx-to-pdf':'office-pdf','powerpoint-to-pdf':'office-pdf',
 'docx-to-txt':'docx-txt','word-to-txt':'docx-txt','txt-to-docx':'text-docx','html-to-docx':'text-docx','md-to-docx':'text-docx','markdown-to-docx':'text-docx','docx-to-html':'docx-html','word-to-html':'docx-html','docx-to-md':'docx-md','word-to-markdown':'docx-md','docx-to-pptx':'docx-pptx','word-to-pptx':'docx-pptx','pptx-to-docx':'pptx-docx','powerpoint-to-word':'pptx-docx',
 'pdf-to-txt':'pdf-txt','pdf-to-xlsx':'pdf-xlsx','pdf-to-excel':'pdf-xlsx','pdf-to-pptx':'pdf-pptx','pdf-to-powerpoint':'pdf-pptx','pdf-to-images':'pdf-images','pdf-to-png':'pdf-images',
 'xlsx-to-csv':'xlsx-csv','excel-to-csv':'xlsx-csv','csv-to-xlsx':'csv-xlsx','csv-to-json':'csv-json','json-to-csv':'json-csv','xlsx-to-json':'xlsx-json','excel-to-json':'xlsx-json','json-to-xlsx':'json-xlsx',
 'image-to-pdf':'image-pdf','img-to-pdf':'image-pdf','compress-image':'image-compress','resize-image':'image-resize','image-to-webp':'image-webp','image-to-jpg':'image-jpg','image-to-png':'image-png','to-sticker':'image-sticker','ocr':'ocr',
 'video-to-mp3':'video-mp3','video-to-gif':'video-gif','compress-video':'video-compress','audio-to-mp3':'audio-mp3','audio-to-wav':'audio-wav','audio-to-ogg':'audio-ogg','cut-video':'video-cut',
 'merge-pdf':'pdf-merge','split-pdf':'pdf-split','rotate-pdf':'pdf-rotate','reorder-pdf':'pdf-reorder','protect-pdf':'pdf-protect','unlock-pdf':'pdf-unlock','compress-pdf':'pdf-compress','watermark-pdf':'pdf-watermark','page-numbers':'pdf-page-numbers','pdf-ocr':'pdf-ocr','epub-to-pdf':'epub-pdf','pdf-to-epub':'pdf-epub','unzip':'archive-unpack','zip':'archive-pack'
}

def _run(args,timeout=180):
    p=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
    if p.returncode: raise RuntimeError((p.stderr or p.stdout or 'فشل التحويل')[-900:])

def convert_file(src: str,operation: str,extra: str='') -> list[str]:
    p=Path(src); op=ALIASES.get(operation.lower().strip(),operation.lower().strip())
    outdir=Path(tempfile.mkdtemp(prefix='out-',dir=settings.temp_dir)); out=[]
    ext=p.suffix.lower()
    if op=='office-pdf' or op=='epub-pdf':
        _run(['libreoffice','-env:UserInstallation=file://'+str(outdir/'lo-profile'),'--headless','--convert-to','pdf','--outdir',str(outdir),str(p)],240)
        out=[str(outdir/(p.stem+'.pdf'))]
    elif op=='pdf-epub':
        import fitz,html
        from ebooklib import epub
        book=epub.EpubBook(); book.set_identifier(p.stem); book.set_title(p.stem); book.set_language('ar')
        doc=fitz.open(p); spine=['nav']
        for i,page in enumerate(doc):
            chapter=epub.EpubHtml(title=f'صفحة {i+1}',file_name=f'page{i+1}.xhtml',lang='ar')
            chapter.content=f'<html><body><h1>صفحة {i+1}</h1><pre>{html.escape(page.get_text())}</pre></body></html>'
            book.add_item(chapter); spine.append(chapter)
        book.add_item(epub.EpubNcx()); book.add_item(epub.EpubNav()); book.spine=spine
        dest=outdir/(p.stem+'.epub'); epub.write_epub(str(dest),book); out=[str(dest)]
    elif op=='pdf-docx':
        from pdf2docx import Converter
        target=outdir/(p.stem+'.docx'); cv=Converter(str(p))
        try: cv.convert(str(target),start=0,end=None)
        finally: cv.close()
        out=[str(target)]
    elif op=='pdf-txt':
        import fitz
        doc=fitz.open(p); target=outdir/(p.stem+'.txt'); target.write_text('\n\n'.join(page.get_text() for page in doc),encoding='utf-8'); out=[str(target)]
    elif op=='pdf-xlsx':
        import pdfplumber
        from openpyxl import Workbook
        wb=Workbook(); ws=wb.active
        with pdfplumber.open(p) as pdf:
            for page in pdf.pages:
                tables=page.extract_tables()
                if tables:
                    for table in tables:
                        for row in table: ws.append([c or '' for c in row])
                else:
                    for line in (page.extract_text() or '').splitlines(): ws.append([line])
        target=outdir/(p.stem+'.xlsx'); wb.save(target); out=[str(target)]
    elif op=='pdf-pptx':
        import fitz
        from pptx import Presentation
        from pptx.util import Inches
        doc=fitz.open(p); prs=Presentation(); prs.slide_width=Inches(10); prs.slide_height=Inches(7.5)
        for i,page in enumerate(doc):
            img=outdir/f'p{i}.png'; page.get_pixmap(matrix=fitz.Matrix(1.3,1.3),alpha=False).save(img)
            slide=prs.slides.add_slide(prs.slide_layouts[6]); slide.shapes.add_picture(str(img),0,0,width=prs.slide_width,height=prs.slide_height)
        target=outdir/(p.stem+'.pptx'); prs.save(target); out=[str(target)]
    elif op=='pdf-images':
        import fitz
        doc=fitz.open(p)
        for i,page in enumerate(doc):
            target=outdir/f'{p.stem}-{i+1}.png'; page.get_pixmap(matrix=fitz.Matrix(1.6,1.6),alpha=False).save(target); out.append(str(target))
        if len(out)>1:
            z=outdir/(p.stem+'-pages.zip')
            with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as f:
                for fpath in out:f.write(fpath,Path(fpath).name)
            out=[str(z)]
    elif op=='pdf-merge':
        if not zipfile.is_zipfile(p): raise ValueError('لدمج عدة ملفات، ضع ملفات PDF داخل ZIP واحد ثم أرسله مع /convert pdf-merge.')
        from pypdf import PdfReader,PdfWriter
        writer=PdfWriter()
        with zipfile.ZipFile(p) as z:
            members=[x for x in z.namelist() if x.lower().endswith('.pdf') and not x.startswith('/') and '..' not in Path(x).parts]
            if not members: raise ValueError('لم أجد ملفات PDF داخل ZIP.')
            info={x.filename:x.file_size for x in z.infolist()}
            if len(members)>20 or sum(info.get(x,0) for x in members)>150*1024*1024: raise ValueError('الدمج يقبل حتى 20 ملفًا وبحجم غير مضغوط إجمالي 150MB.')
            for name in members:
                data=z.read(name); reader=PdfReader(io.BytesIO(data))
                for page in reader.pages: writer.add_page(page)
        dest=outdir/(p.stem+'-merged.pdf')
        with open(dest,'wb') as f: writer.write(f)
        out=[str(dest)]
    elif op=='pdf-ocr':
        import fitz,pytesseract
        from PIL import Image
        doc=fitz.open(p); parts=[]
        if len(doc)>60: raise ValueError('OCR PDF يدعم حتى 60 صفحة في هذه النسخة.')
        for page in doc:
            pix=page.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False)
            parts.append(pytesseract.image_to_string(Image.frombytes('RGB',[pix.width,pix.height],pix.samples),lang='ara+eng'))
        dest=outdir/(p.stem+'-ocr.txt'); dest.write_text('\n\n'.join(parts),encoding='utf8'); out=[str(dest)]
    elif op.startswith('pdf-') and op in ('pdf-compress','pdf-rotate','pdf-protect','pdf-unlock','pdf-split','pdf-reorder','pdf-watermark','pdf-page-numbers'):
        import pikepdf
        if op=='pdf-compress':
            dest=outdir/(p.stem+'-compressed.pdf')
            with pikepdf.open(p) as pdf: pdf.save(dest,compress_streams=True,recompress_flate=True,linearize=True)
        elif op=='pdf-rotate':
            dest=outdir/(p.stem+'-rotated.pdf'); degrees=int(extra or 90)
            with pikepdf.open(p) as pdf:
                for page in pdf.pages: page.Rotate=(int(page.get('/Rotate',0))+degrees)%360
                pdf.save(dest)
        elif op=='pdf-protect':
            if not extra: raise ValueError('أرسل كلمة المرور بعد الأمر، مثال: /convert pdf-protect كلمة_المرور')
            dest=outdir/(p.stem+'-protected.pdf')
            with pikepdf.open(p) as pdf: pdf.save(dest,encryption=pikepdf.Encryption(user=extra,owner=extra,R=6))
        elif op=='pdf-unlock':
            if not extra: raise ValueError('أرسل كلمة مرور الملف بعد الأمر.')
            dest=outdir/(p.stem+'-unlocked.pdf')
            with pikepdf.open(p,password=extra) as pdf: pdf.save(dest)
        elif op in ('pdf-split','pdf-reorder'):
            from pypdf import PdfReader,PdfWriter
            reader=PdfReader(p); ranges=extra or '1'; selected=[]
            if op=='pdf-reorder': selected=[int(x) for x in ranges.split(',') if x.strip()]
            else:
                for bit in ranges.split(','):
                    a,*b=bit.split('-'); start=int(a); end=int(b[0]) if b and b[0] else start
                    selected.extend(range(start,end+1))
            writer=PdfWriter()
            for page_no in selected:
                if 1<=page_no<=len(reader.pages): writer.add_page(reader.pages[page_no-1])
            if not writer.pages: raise ValueError('لم يتم تحديد أي صفحة صالحة.')
            dest=outdir/(p.stem+('-reordered.pdf' if op=='pdf-reorder' else '-pages.pdf'))
            with open(dest,'wb') as f: writer.write(f)
        elif op in ('pdf-watermark','pdf-page-numbers'):
            from pypdf import PdfReader,PdfWriter
            from reportlab.pdfgen import canvas
            reader=PdfReader(p); writer=PdfWriter(); txt=extra or ('علامة مائية' if op=='pdf-watermark' else '')
            if op=='pdf-watermark' and not txt: raise ValueError('اكتب العلامة بعد الأمر.')
            for i,page in enumerate(reader.pages):
                packet=io.BytesIO(); c=canvas.Canvas(packet,pagesize=(float(page.mediabox.width),float(page.mediabox.height)))
                c.saveState(); c.setFillAlpha(.25); c.setFont('Helvetica',24)
                c.drawCentredString(float(page.mediabox.width)/2,40,txt if op=='pdf-watermark' else f'{i+1}')
                c.restoreState(); c.save(); packet.seek(0); page.merge_page(PdfReader(packet).pages[0]); writer.add_page(page)
            dest=outdir/(p.stem+('-watermarked.pdf' if op=='pdf-watermark' else '-numbered.pdf'))
            with open(dest,'wb') as f: writer.write(f)
        out=[str(dest)]
    elif op=='text-docx':
        from docx import Document
        doc=Document()
        if ext in ('.html','.htm'):
            from bs4 import BeautifulSoup
            content=BeautifulSoup(p.read_text(encoding='utf8',errors='replace'),'html.parser').get_text('\n')
        else: content=p.read_text(encoding='utf8',errors='replace')
        for line in content.splitlines(): doc.add_paragraph(line)
        dest=outdir/(p.stem+'.docx'); doc.save(dest); out=[str(dest)]
    elif op=='pptx-docx':
        from pptx import Presentation
        from docx import Document
        prs=Presentation(p); doc=Document()
        for i,slide in enumerate(prs.slides):
            doc.add_heading(f'الشريحة {i+1}',level=1)
            for shape in slide.shapes:
                if getattr(shape,'has_text_frame',False) and shape.text.strip(): doc.add_paragraph(shape.text)
        dest=outdir/(p.stem+'.docx'); doc.save(dest); out=[str(dest)]
    elif op.startswith('docx-'):
        from docx import Document
        doc=Document(p); paras='\n'.join(x.text for x in doc.paragraphs)
        if op=='docx-txt':
            dest=outdir/(p.stem+'.txt'); dest.write_text(paras,encoding='utf8'); out=[str(dest)]
        elif op in ('docx-html','docx-md'):
            content='\n'.join(('<p>'+x.text+'</p>' if op=='docx-html' else x.text) for x in doc.paragraphs)
            dest=outdir/(p.stem+('.html' if op=='docx-html' else '.md')); dest.write_text(content,encoding='utf8'); out=[str(dest)]
        elif op=='docx-pptx':
            from pptx import Presentation
            prs=Presentation()
            for para in [x for x in doc.paragraphs if x.text.strip()]:
                slide=prs.slides.add_slide(prs.slide_layouts[1]); slide.shapes.title.text=para.text[:100]
            dest=outdir/(p.stem+'.pptx'); prs.save(dest); out=[str(dest)]
        else: raise ValueError('التحويل غير معروف.')
    elif op in ('xlsx-csv','csv-xlsx','csv-json','json-csv','xlsx-json','json-xlsx'):
        import csv,json
        if op=='xlsx-csv':
            from openpyxl import load_workbook
            wb=load_workbook(p,data_only=True); ws=wb.active; dest=outdir/(p.stem+'.csv')
            with open(dest,'w',newline='',encoding='utf-8-sig') as f: csv.writer(f).writerows(ws.values)
        elif op=='csv-xlsx':
            from openpyxl import Workbook
            wb=Workbook(); ws=wb.active
            with open(p,newline='',encoding='utf-8-sig') as f:
                for row in csv.reader(f): ws.append(row)
            dest=outdir/(p.stem+'.xlsx'); wb.save(dest)
        elif op=='xlsx-json':
            from openpyxl import load_workbook
            wb=load_workbook(p,data_only=True); ws=wb.active; rows=list(ws.values)
            headers=[str(x) if x is not None else '' for x in (rows[0] if rows else [])]
            data=[dict(zip(headers,row)) for row in rows[1:] if any(x is not None for x in row)]
            dest=outdir/(p.stem+'.json'); dest.write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str),encoding='utf8')
        elif op=='json-xlsx':
            from openpyxl import Workbook
            data=json.loads(p.read_text(encoding='utf8')); rows=data if isinstance(data,list) else [data]
            if not rows or not isinstance(rows[0],dict): raise ValueError('JSON يجب أن يكون كائنًا أو قائمة كائنات.')
            wb=Workbook(); ws=wb.active; headers=list(rows[0].keys()); ws.append(headers)
            for row in rows: ws.append([row.get(k) for k in headers])
            dest=outdir/(p.stem+'.xlsx'); wb.save(dest)
        elif op=='csv-json':
            with open(p,newline='',encoding='utf-8-sig') as f: data=list(csv.DictReader(f))
            dest=outdir/(p.stem+'.json'); dest.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
        else:
            data=json.loads(p.read_text(encoding='utf8')); rows=data if isinstance(data,list) else [data]
            if not rows or not isinstance(rows[0],dict): raise ValueError('JSON يجب أن يكون كائنًا أو قائمة كائنات.')
            dest=outdir/(p.stem+'.csv')
            with open(dest,'w',newline='',encoding='utf-8-sig') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
        out=[str(dest)]
    elif op.startswith('image-') or op in ('image-pdf','ocr'):
        from PIL import Image
        img=Image.open(p)
        if op=='ocr':
            import pytesseract
            target=outdir/(p.stem+'-ocr.txt'); target.write_text(pytesseract.image_to_string(img,lang='ara+eng'),encoding='utf8'); out=[str(target)]
        elif op=='image-pdf':
            dest=outdir/(p.stem+'.pdf'); img.convert('RGB').save(dest); out=[str(dest)]
        elif op=='image-resize':
            wh=(extra or '1280x1280').lower().split('x'); img.thumbnail((int(wh[0]),int(wh[1])))
            dest=outdir/(p.stem+'-resized.png'); img.save(dest); out=[str(dest)]
        elif op=='image-compress':
            dest=outdir/(p.stem+'-compressed.jpg'); img.convert('RGB').save(dest,'JPEG',quality=65,optimize=True); out=[str(dest)]
        elif op in ('image-webp','image-sticker'):
            dest=outdir/(p.stem+'.webp'); img.thumbnail((512,512)); img.save(dest,'WEBP',quality=85,method=6); out=[str(dest)]
        elif op=='image-jpg':
            dest=outdir/(p.stem+'.jpg'); img.convert('RGB').save(dest,'JPEG',quality=92); out=[str(dest)]
        elif op=='image-png':
            dest=outdir/(p.stem+'.png'); img.save(dest,'PNG'); out=[str(dest)]
        elif op=='image-bg':
            try:
                from rembg import remove
                dest=outdir/(p.stem+'-nobg.png'); dest.write_bytes(remove(p.read_bytes())); out=[str(dest)]
            except ImportError: raise RuntimeError('إزالة الخلفية اختيارية؛ ثبت rembg في Docker أو فعّل خدمة إزالة خلفية خارجية.')
    elif op in ('video-mp3','video-gif','video-compress','video-cut','audio-mp3','audio-wav','audio-ogg'):
        if op=='video-mp3': dest=outdir/(p.stem+'.mp3'); args=['ffmpeg','-y','-i',str(p),'-vn','-b:a','192k',str(dest)]
        elif op=='video-gif': dest=outdir/(p.stem+'.gif'); args=['ffmpeg','-y','-i',str(p),'-vf','fps=12,scale=480:-1:flags=lanczos','-loop','0',str(dest)]
        elif op=='video-compress': dest=outdir/(p.stem+'-small.mp4'); args=['ffmpeg','-y','-i',str(p),'-vcodec','libx264','-crf','30','-preset','veryfast','-acodec','aac',str(dest)]
        elif op=='video-cut':
            try: start,duration=extra.split('|',1); seconds=__import__('app.services.common',fromlist=['parse_duration']).parse_duration(duration)
            except Exception: raise ValueError('أرسل البداية والمدة مفصولتين بـ | مثال: /convert video-cut 00:01:00|30s')
            dest=outdir/(p.stem+'-cut.mp4'); args=['ffmpeg','-y','-ss',start,'-i',str(p),'-t',str(seconds),'-c','copy',str(dest)]
        else:
            fmt=op.split('-')[1]; dest=outdir/(p.stem+'.'+fmt); args=['ffmpeg','-y','-i',str(p),str(dest)]
        _run(args,300); out=[str(dest)]
    elif op=='archive-unpack':
        dest=outdir/(p.stem+'-files'); dest.mkdir()
        if zipfile.is_zipfile(p):
            with zipfile.ZipFile(p) as z:
                infos=z.infolist()
                if len(infos)>250 or sum(x.file_size for x in infos)>250*1024*1024: raise ValueError('الأرشيف أكبر من الحدود المسموحة.')
                for item in infos:
                    target=(dest/item.filename).resolve()
                    if dest.resolve() not in target.parents and target!=dest.resolve(): raise ValueError('الأرشيف يحتوي مسارات غير آمنة.')
                z.extractall(dest)
        else: _run(['7z','x','-y','-o'+str(dest),str(p)],180)
        z=outdir/(p.stem+'-files.zip')
        with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as f:
            for fp in dest.rglob('*'):
                if fp.is_file(): f.write(fp,fp.relative_to(dest))
        out=[str(z)]
    elif op=='archive-pack':
        dest=outdir/(p.stem+'.zip')
        with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z: z.write(p,p.name)
        out=[str(dest)]
    else: raise ValueError('نوع التحويل غير معروف. استخدم /convert لعرض الخيارات.')
    if not out or any(not Path(x).exists() for x in out): raise RuntimeError('لم ينتج ملف صالح من التحويل.')
    return out
