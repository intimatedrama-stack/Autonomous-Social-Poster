import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "poster.db")

def init_db():
    """Initializes the SQLite database schema."""
    logger.info(f"Initializing database at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create posts table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT NOT NULL,
        niche TEXT,
        caption TEXT,
        hashtags TEXT,
        media_path TEXT,
        status TEXT DEFAULT 'pending',
        scheduled_time TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create accounts/profiles table if needed
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT NOT NULL,
        username TEXT NOT NULL,
        profile_path TEXT,
        status TEXT DEFAULT 'active'
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS generations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        style_id TEXT,
        combo_key TEXT,
        graphic_level TEXT,
        topic TEXT,
        caption TEXT,
        sd_prompt TEXT,
        seed INTEGER,
        media_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_generations_combo ON generations(combo_key)"
    )
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully.")


def record_generation(
    style_id,
    combo_key,
    graphic_level,
    topic,
    caption=None,
    sd_prompt=None,
    seed=None,
    media_path=None,
):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            INSERT INTO generations (
                style_id, combo_key, graphic_level, topic, caption, sd_prompt, seed, media_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (style_id, combo_key, graphic_level, topic, caption, sd_prompt, seed, media_path),
        )
        conn.commit()
    finally:
        conn.close()


def recent_combo_keys(limit=40):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT combo_key FROM generations WHERE combo_key IS NOT NULL ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [row[0] for row in rows]
    finally:
        conn.close()


def recent_topics(limit=8):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT topic FROM generations WHERE topic IS NOT NULL ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [row[0] for row in rows]
    finally:
        conn.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()

