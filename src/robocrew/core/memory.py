import sqlite3
import os
from datetime import datetime

class Memory:
    def __init__(self, db_path="robot_memory.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize the database with the memories table."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                image_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def add_memory(self, text, image_path=None):
        """Add a new memory to the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO memories (text, image_path)
            VALUES (?, ?)
        ''', (text, image_path))
        conn.commit()
        conn.close()
        return f"Memory added: {text}"

    def search_memory(self, query):
        """Search for memories matching the query."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Simple LIKE search for now
        cursor.execute('''
            SELECT text, created_at FROM memories
            WHERE text LIKE ?
            ORDER BY created_at DESC
        ''', (f'%{query}%',))
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return "No matching memories found."
        
        formatted_results = "\n".join([f"- [{row[1]}] {row[0]}" for row in results])
        return f"Found memories:\n{formatted_results}"

    def get_all_memories(self):
        """Retrieve all memories (for debugging)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM memories')
        results = cursor.fetchall()
        conn.close()
        return results
