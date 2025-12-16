"""
Persistent memory store for AI navigation agent.
Uses SQLite to store notes about the environment.
"""

import sqlite3
import threading
import time
import os
from typing import List, Dict
from collections import deque

# Adjusted to place DB in project root (3 levels up from core/memory_store.py)
DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'robocrew_memory.db')

class MemoryStore:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._init_db()
    
    def _init_db(self):
        """Initialize the SQLite database."""
        db_path = os.path.abspath(DB_PATH)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._db_lock = threading.Lock()
        
        with self._db_lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at REAL NOT NULL,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    location_x REAL,
                    location_y REAL
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_notes_category ON notes(category)')
            self.conn.commit()
    
    def save_note(self, category: str, content: str, location: Dict = None) -> int:
        """Save a note to the database."""
        x = location.get('x') if location else None
        y = location.get('y') if location else None
        
        with self._db_lock:
            cursor = self.conn.cursor()
            cursor.execute(
                'INSERT INTO notes (created_at, category, content, location_x, location_y) VALUES (?, ?, ?, ?, ?)',
                (time.time(), category, content, x, y)
            )
            self.conn.commit()
            return cursor.lastrowid
    
    def get_notes(self, limit: int = 20) -> List[Dict]:
        """Get recent notes."""
        with self._db_lock:
            cursor = self.conn.cursor()
            cursor.execute(
                'SELECT id, category, content, location_x, location_y FROM notes ORDER BY created_at DESC LIMIT ?',
                (limit,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def get_notes_by_category(self, category: str, limit: int = 10) -> List[Dict]:
        """Get notes by category."""
        with self._db_lock:
            cursor = self.conn.cursor()
            cursor.execute(
                'SELECT content, location_x, location_y FROM notes WHERE category = ? ORDER BY created_at DESC LIMIT ?',
                (category, limit)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def generate_context_summary(self, max_notes: int = 15) -> str:
        """Generate a compressed summary of stored notes for the AI prompt."""
        notes = self.get_notes(limit=max_notes)
        if not notes:
            return ""
        
        lines = ["PERSISTENT MEMORY:"]
        
        by_category = {}
        for note in notes:
            cat = note['category']
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(note['content'])
        
        for cat, contents in by_category.items():
            if len(contents) == 1:
                lines.append(f"  [{cat}] {contents[0]}")
            else:
                combined = "; ".join(contents[:3])
                if len(contents) > 3:
                    combined += f" (+{len(contents)-3} more)"
                lines.append(f"  [{cat}] {combined}")
        
        return "\n".join(lines)
    
    def clear_all(self):
        """Clear all notes."""
        with self._db_lock:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM notes')
            self.conn.commit()


memory_store = MemoryStore()
