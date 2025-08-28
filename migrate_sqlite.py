"""
Simple migration helper: if the existing SQLite `conversations` table exists (as used
by the old `chat_sessions.py`), this script will create ORM tables and copy rows
into the SQLAlchemy-managed `conversations` table (idempotent for same rows).

Run: python migrate_sqlite.py
"""
import sqlite3
from admin_db import initialize_schema, get_engine
from models import Conversation
from sqlalchemy.orm import Session
import os


def read_legacy_rows(db_path="chatbot_context.db"):
    if not os.path.exists(db_path):
        return []
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, chat_id, timestamp, context FROM conversations")
        rows = cur.fetchall()
        return rows
    except Exception:
        return []
    finally:
        conn.close()


def migrate():
    initialize_schema()
    engine = get_engine()
    rows = read_legacy_rows()
    if not rows:
        print("No legacy rows found or table missing. Schema created/ensured.")
        return

    with Session(engine) as session:
        existing = { (c.chat_id, c.timestamp.isoformat() if c.timestamp else None) for c in session.query(Conversation).all() }
        inserted = 0
        for rid, chat_id, timestamp, context in rows:
            key = (chat_id, timestamp)
            # naive dedupe based on chat_id+timestamp string
            if key in existing:
                continue
            # Convert string timestamp to datetime if needed
            if isinstance(timestamp, str):
                from datetime import datetime
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except:
                    timestamp = datetime.utcnow()
            conv = Conversation(chat_id=chat_id, timestamp=timestamp, context=context)
            session.add(conv)
            inserted += 1
        session.commit()
    print(f"Migration finished. Inserted {inserted} rows.")


if __name__ == "__main__":
    migrate()
