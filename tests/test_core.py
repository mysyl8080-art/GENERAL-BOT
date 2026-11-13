from app.db import init_db, connection
from app.services.common import parse_duration, parse_when, safe_url
from datetime import datetime, timedelta
from app.services.files import ALIASES


def test_duration_parser():
    assert parse_duration('15s') == 15
    assert parse_duration('2m30s') == 150
    assert parse_duration('01:02:03') == 3723


def test_arabic_relative_reminder_time():
    before = datetime.now().astimezone() + timedelta(hours=1, minutes=50)
    after = datetime.now().astimezone() + timedelta(hours=2, minutes=10)
    parsed = parse_when('بعد ساعتين')
    assert parsed is not None and before < parsed < after


def test_requested_conversion_aliases_are_present():
    required = {
        'pdf-to-docx', 'docx-to-pdf', 'pdf-to-xlsx', 'pdf-to-pptx',
        'xlsx-to-csv', 'csv-to-xlsx', 'xlsx-to-json', 'json-to-xlsx',
        'docx-to-txt', 'txt-to-docx', 'docx-to-html', 'html-to-docx',
        'docx-to-md', 'md-to-docx', 'docx-to-pptx', 'pptx-to-docx',
        'pdf-to-epub', 'epub-to-pdf', 'video-to-mp3', 'video-to-gif',
        'audio-to-mp3', 'audio-to-wav', 'audio-to-ogg', 'compress-pdf',
        'merge-pdf', 'split-pdf', 'rotate-pdf', 'protect-pdf', 'unlock-pdf',
    }
    assert required.issubset(ALIASES)


def test_private_hosts_are_rejected():
    assert safe_url('http://127.0.0.1:8080') is False
    assert safe_url('http://localhost') is False
    assert safe_url('file:///etc/passwd') is False


def test_sqlite_schema_initializes():
    init_db()
    with connection() as db:
        tables = {r['name'] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        products = {r['name'] for r in db.execute('PRAGMA table_info(products)')}
    assert {'reminders','habits','tasks','words','orders','daily_subscriptions','daily_summaries','recurring_reminders','shopping_items','countdown_events','captcha_challenges','anonymous_suggestions','support_tickets','channel_posts','coupons','loyalty','available_slots','order_ratings'} <= tables
    assert {'stock','low_stock_threshold','low_stock_notified'} <= products
