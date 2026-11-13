from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from app.config import settings

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS reminders(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, chat_id INTEGER NOT NULL, due_at TEXT NOT NULL, text TEXT NOT NULL, sent INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS habits(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, name TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(user_id,name));
CREATE TABLE IF NOT EXISTS habit_logs(id INTEGER PRIMARY KEY, habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE, day TEXT NOT NULL, UNIQUE(habit_id,day));
CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL, chat_id INTEGER NOT NULL, text TEXT NOT NULL, created_at TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS words(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, front TEXT NOT NULL, back TEXT NOT NULL, due_at TEXT NOT NULL, interval_days INTEGER NOT NULL DEFAULT 0, UNIQUE(user_id,front));
CREATE TABLE IF NOT EXISTS quiz_scores(user_id INTEGER NOT NULL, chat_id INTEGER NOT NULL, points INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(user_id,chat_id));
CREATE TABLE IF NOT EXISTS group_settings(chat_id INTEGER PRIMARY KEY, antispam INTEGER NOT NULL DEFAULT 0, welcome TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS scheduled_posts(id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL, chat_id INTEGER NOT NULL, due_at TEXT NOT NULL, text TEXT NOT NULL, sent INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS bookings(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, chat_id INTEGER NOT NULL, service TEXT NOT NULL, slot TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL, name TEXT NOT NULL, price REAL NOT NULL, description TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS cart(user_id INTEGER NOT NULL, product_id INTEGER NOT NULL REFERENCES products(id), quantity INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(user_id,product_id));
CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, items TEXT NOT NULL, total REAL NOT NULL, status TEXT NOT NULL DEFAULT 'new', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS faqs(id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL, chat_id INTEGER NOT NULL, question TEXT NOT NULL, answer TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS feedback(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, chat_id INTEGER NOT NULL, text TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS price_alerts(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, url TEXT NOT NULL, target REAL NOT NULL, created_at TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS user_settings(user_id INTEGER PRIMARY KEY, timezone TEXT NOT NULL DEFAULT 'Africa/Cairo');
CREATE TABLE IF NOT EXISTS daily_subscriptions(user_id INTEGER NOT NULL, chat_id INTEGER NOT NULL, last_sent TEXT NOT NULL DEFAULT '', PRIMARY KEY(user_id,chat_id));
CREATE TABLE IF NOT EXISTS daily_summaries(user_id INTEGER NOT NULL, chat_id INTEGER NOT NULL, send_time TEXT NOT NULL, last_sent TEXT NOT NULL DEFAULT '', PRIMARY KEY(user_id,chat_id));
CREATE TABLE IF NOT EXISTS recurring_reminders(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, chat_id INTEGER NOT NULL, rule TEXT NOT NULL, send_time TEXT NOT NULL, text TEXT NOT NULL, last_sent TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS shopping_items(id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL, text TEXT NOT NULL, created_at TEXT NOT NULL, checked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS countdown_events(id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL, chat_id INTEGER NOT NULL, title TEXT NOT NULL, event_at TEXT NOT NULL, reminded INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS idea_favorites(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, text TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS captcha_challenges(chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL, correct INTEGER NOT NULL, expires_at TEXT NOT NULL, PRIMARY KEY(chat_id,user_id));
CREATE TABLE IF NOT EXISTS allowed_domains(chat_id INTEGER NOT NULL, domain TEXT NOT NULL, PRIMARY KEY(chat_id,domain));
CREATE TABLE IF NOT EXISTS blocked_words(chat_id INTEGER NOT NULL, word TEXT NOT NULL, PRIMARY KEY(chat_id,word));
CREATE TABLE IF NOT EXISTS group_activity(chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL, day TEXT NOT NULL, messages INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(chat_id,user_id,day));
CREATE TABLE IF NOT EXISTS group_roles(chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL, role TEXT NOT NULL, assigned_at TEXT NOT NULL, PRIMARY KEY(chat_id,user_id));
CREATE TABLE IF NOT EXISTS anonymous_suggestions(id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL, text TEXT NOT NULL, created_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new');
CREATE TABLE IF NOT EXISTS support_tickets(id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL, text TEXT NOT NULL, created_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', rating INTEGER);
CREATE TABLE IF NOT EXISTS ticket_messages(id INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE, sender_id INTEGER NOT NULL, text TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS channel_posts(id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL, created_at TEXT NOT NULL, weekday INTEGER NOT NULL, hour INTEGER NOT NULL, UNIQUE(chat_id,message_id));
CREATE TABLE IF NOT EXISTS coupons(code TEXT PRIMARY KEY, percent INTEGER NOT NULL, max_uses INTEGER NOT NULL, used INTEGER NOT NULL DEFAULT 0, expires_at TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS order_lines(order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE, product_id INTEGER NOT NULL REFERENCES products(id), quantity INTEGER NOT NULL, PRIMARY KEY(order_id,product_id));
CREATE TABLE IF NOT EXISTS order_adjustments(order_id INTEGER PRIMARY KEY REFERENCES orders(id) ON DELETE CASCADE, coupon_code TEXT NOT NULL DEFAULT '', loyalty_points INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS loyalty_events(order_id INTEGER NOT NULL REFERENCES orders(id), event TEXT NOT NULL, points INTEGER NOT NULL, PRIMARY KEY(order_id,event));
CREATE TABLE IF NOT EXISTS cart_coupons(user_id INTEGER PRIMARY KEY, code TEXT NOT NULL REFERENCES coupons(code));
CREATE TABLE IF NOT EXISTS loyalty(user_id INTEGER PRIMARY KEY, points INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS cart_redemptions(user_id INTEGER PRIMARY KEY, points INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS available_slots(id INTEGER PRIMARY KEY, service TEXT NOT NULL, slot TEXT NOT NULL UNIQUE, status TEXT NOT NULL DEFAULT 'open');
CREATE TABLE IF NOT EXISTS order_ratings(order_id INTEGER PRIMARY KEY REFERENCES orders(id), user_id INTEGER NOT NULL, rating INTEGER NOT NULL, comment TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS language_preferences(user_id INTEGER PRIMARY KEY, language TEXT NOT NULL);
"""

@contextmanager
def connection():
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.database_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db() -> None:
    with connection() as conn:
        conn.executescript(SCHEMA)
        product_columns={row['name'] for row in conn.execute('PRAGMA table_info(products)')}
        if 'stock' not in product_columns: conn.execute('ALTER TABLE products ADD COLUMN stock INTEGER NOT NULL DEFAULT -1')
        if 'low_stock_threshold' not in product_columns: conn.execute('ALTER TABLE products ADD COLUMN low_stock_threshold INTEGER NOT NULL DEFAULT 5')
        if 'low_stock_notified' not in product_columns: conn.execute('ALTER TABLE products ADD COLUMN low_stock_notified INTEGER NOT NULL DEFAULT 0')
        group_columns={row['name'] for row in conn.execute('PRAGMA table_info(group_settings)')}
        if 'captcha' not in group_columns: conn.execute('ALTER TABLE group_settings ADD COLUMN captcha INTEGER NOT NULL DEFAULT 0')
