import sqlite3
import json
from typing import Optional, Dict, List

class Database:
    def __init__(self, db_path: str = "bot_data.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    secret TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    
    def add_user(self, user_id: int, username: str, secret: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO users (user_id, username, secret, is_active) VALUES (?, ?, ?, 1)",
                    (user_id, username, secret)
                )
                conn.commit()
                return True
        except Exception as e:
            print(f"Error adding user: {e}")
            return False
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def deactivate_user(self, user_id: int) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("UPDATE users SET is_active = 0 WHERE user_id = ?", (user_id,))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error deactivating user: {e}")
            return False
    
    def get_all_active_users(self) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM users WHERE is_active = 1")
            return [dict(row) for row in cursor.fetchall()]