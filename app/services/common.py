from __future__ import annotations
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
import ipaddress, socket
import re
import dateparser
import requests
from app.config import settings

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def parse_when(text: str):
    normalized=text.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹','01234567890123456789')).strip().lower()
    number_words={'واحد':1,'واحدة':1,'واحده':1,'اثنين':2,'اثنتين':2,'اثنان':2,'ثلاث':3,'ثلاثة':3,'اربعة':4,'أربعة':4,'خمس':5,'خمسة':5,'ست':6,'ستة':6,'سبع':7,'سبعة':7,'ثمان':8,'ثمانية':8,'تسع':9,'تسعة':9,'عشر':10,'عشرة':10}
    units={'ثانية':'seconds','ثواني':'seconds','ثانيتين':'seconds','دقيقة':'minutes','دقائق':'minutes','دقيقتين':'minutes','ساعة':'hours','ساعات':'hours','ساعتين':'hours','يوم':'days','أيام':'days','ايام':'days','يومين':'days','أسبوع':'weeks','اسبوع':'weeks','أسابيع':'weeks','اسابيع':'weeks','أسبوعين':'weeks','اسبوعين':'weeks','شهر':'months','أشهر':'months','اشهر':'months','شهرين':'months','second':'seconds','seconds':'seconds','minute':'minutes','minutes':'minutes','hour':'hours','hours':'hours','day':'days','days':'days','week':'weeks','weeks':'weeks'}
    units_pattern='|'.join(sorted(map(re.escape,units),key=len,reverse=True))
    match=re.search(rf'(?:بعد|خلال|في)\s*(?:(\d+|[\u0600-\u06ff]+)\s*)?({units_pattern})\b',normalized)
    if match:
        token=match.group(1); unit=units[match.group(2)]
        dual=match.group(2) in {'ثانيتين','دقيقتين','ساعتين','يومين','أسبوعين','اسبوعين','شهرين'}
        amount=int(token) if token and token.isdigit() else number_words.get(token,2 if dual else 1)
        multiplier={'seconds':1,'minutes':60,'hours':3600,'days':86400,'weeks':604800,'months':2592000}[unit]
        return datetime.now(ZoneInfo(settings.timezone))+timedelta(seconds=amount*multiplier)
    return dateparser.parse(text,languages=["ar","en"],settings={"PREFER_DATES_FROM":"future","TIMEZONE":settings.timezone,"RETURN_AS_TIMEZONE_AWARE":True})

def safe_url(url: str) -> bool:
    try:
        p=urlparse(url)
        if p.scheme not in ("http","https") or not p.hostname: return False
        host=p.hostname.rstrip('.').lower()
        if host in ('localhost','localhost.localdomain') or host.endswith(('.local','.internal','.test')): return False
        try: addresses=[ipaddress.ip_address(host)]
        except ValueError: addresses=[ipaddress.ip_address(x[4][0]) for x in socket.getaddrinfo(host,None,type=socket.SOCK_STREAM)]
        return bool(addresses) and all(a.is_global for a in addresses)
    except Exception: return False

def get_ai_reply(prompt: str, system: str = "أجب بالعربية بوضوح واختصار.") -> str:
    if not settings.openai_api_key: raise RuntimeError("ميزة الذكاء الاصطناعي تحتاج OPENAI_API_KEY في متغيرات Railway أو ملف .env.")
    from openai import OpenAI
    kwargs={"api_key":settings.openai_api_key}
    if settings.openai_base_url: kwargs["base_url"]=settings.openai_base_url
    client=OpenAI(**kwargs,timeout=45,max_retries=1)
    result=client.chat.completions.create(model=settings.openai_model,messages=[{"role":"system","content":system},{"role":"user","content":prompt}],max_tokens=900)
    return (result.choices[0].message.content or "لم يصل رد.").strip()

def extract_web_text(url: str) -> str:
    if not safe_url(url): raise ValueError("الرابط غير صالح أو غير مسموح.")
    import trafilatura
    response=requests.get(url,headers={'User-Agent':'Mozilla/5.0 (compatible; TelegramSuperBot/1.0)'},timeout=15,allow_redirects=False,stream=True)
    if response.is_redirect: raise RuntimeError("الرابط يحوّل إلى عنوان آخر؛ افتح الرابط المباشر للمقال.")
    if response.status_code!=200: raise RuntimeError(f"تعذر جلب الصفحة (HTTP {response.status_code}).")
    body=next(response.iter_content(1500000),b'').decode(response.encoding or 'utf-8',errors='replace')
    text=trafilatura.extract(body,include_comments=False,include_tables=False)
    if not text: raise RuntimeError("لم أستطع استخراج نص من الرابط.")
    return text[:18000]

def parse_duration(s: str) -> int:
    if re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?",s):
        parts=list(map(int,s.split(':')))
        return parts[-1]+60*parts[-2]+(3600*parts[-3] if len(parts)==3 else 0)
    total=0
    for n,u in re.findall(r"(\d+)\s*(h|m|s)",s.lower()): total+=int(n)*{"h":3600,"m":60,"s":1}[u]
    if total<=0: raise ValueError("أدخل المدة مثل 15s أو 2m30s أو 00:00:15")
    return total
