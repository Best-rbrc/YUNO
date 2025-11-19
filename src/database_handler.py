"""
SQLite-Datenbank Handler (Minimal)
Erstellt Tabelle `persons` mit Feldern für Name, Kontext, Foto und Audio.
"""
import sqlite3
import pickle
import numpy as np
import os
from typing import Any
from src.path_manager import PathManager, get_db_path




def init_db(path: str = None):
    """Initialize database. If path is None, uses PathManager default."""
    if path is None:
        PathManager.init_directories()
        path = get_db_path()
    
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS persons (
        id INTEGER PRIMARY KEY,
        name TEXT,
        context TEXT,
        photo_path TEXT,
        audio_path TEXT,
        embedding BLOB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Create sync metadata table for version tracking
    c.execute('''CREATE TABLE IF NOT EXISTS sync_metadata (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    conn.commit()
    conn.close()


def add_person(name: str, context: str, photo_path: str, audio_path: str, embedding: np.ndarray, db_path: str = None) -> int:
    """Adds a person record and returns the new row id.
    Embedding is stored as a pickled BLOB.
    """
    if db_path is None:
        db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    emb_blob = pickle.dumps(embedding) if embedding is not None else None
    c.execute('''INSERT INTO persons (name, context, photo_path, audio_path, embedding)
                 VALUES (?, ?, ?, ?, ?)''', (name, context, photo_path, audio_path, emb_blob))
    conn.commit()
    rowid = c.lastrowid
    conn.close()
    return rowid


def update_person(person_id: int, new_context: str = None, photo_path: str = None, audio_path: str = None, embedding: Any = None, new_name: str = None, db_path: str = None) -> bool:
    """Update an existing person record.

    - Appends `new_context` to the existing context (separated by a newline) if provided.
    - Replaces photo_path/audio_path/embedding if provided.
    - Updates name if new_name is provided.
    Returns True on success.
    """
    if db_path is None:
        db_path = get_db_path()
    if not os.path.exists(db_path):
        return False

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    # Fetch existing context
    c.execute('SELECT context FROM persons WHERE id = ?', (person_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False

    existing_context = row[0] or ''
    updated_context = existing_context
    if new_context:
        if existing_context:
            updated_context = existing_context + '\n' + new_context
        else:
            updated_context = new_context

    updates = []
    params = []
    updates.append('context = ?')
    params.append(updated_context)

    if new_name:
        updates.append('name = ?')
        params.append(new_name)
    if photo_path:
        updates.append('photo_path = ?')
        params.append(photo_path)
    if audio_path:
        updates.append('audio_path = ?')
        params.append(audio_path)
    if embedding is not None:
        emb_blob = pickle.dumps(embedding)
        updates.append('embedding = ?')
        params.append(emb_blob)

    params.append(person_id)
    sql = f"UPDATE persons SET {', '.join(updates)} WHERE id = ?"
    c.execute(sql, tuple(params))
    conn.commit()
    conn.close()
    return True


def get_all_persons(db_path: str = None):
    if db_path is None:
        db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT id, name, context, photo_path, audio_path, created_at, updated_at FROM persons')
    rows = c.fetchall()
    conn.close()
    return rows


def get_person_by_id(person_id: int, db_path: str = None):
    """Hole detaillierte Informationen über eine Person anhand der ID."""
    if db_path is None:
        db_path = get_db_path()
    if not os.path.exists(db_path):
        return None
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT id, name, context, photo_path, audio_path, created_at FROM persons WHERE id = ?', (person_id,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        return None
    
    return {
        'id': row[0],
        'name': row[1],
        'context': row[2],
        'photo_path': row[3],
        'audio_path': row[4],
        'created_at': row[5]
    }


def get_local_db_version(db_path: str = None) -> str:
    """Get the last synced database version from local metadata."""
    if db_path is None:
        db_path = get_db_path()
    if not os.path.exists(db_path):
        return None
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT value FROM sync_metadata WHERE key = 'db_version'")
    row = c.fetchone()
    conn.close()
    
    return row[0] if row else None


def set_local_db_version(version: str, db_path: str = None):
    """Set the current database version in local metadata."""
    if db_path is None:
        db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO sync_metadata (key, value, updated_at) 
                 VALUES ('db_version', ?, CURRENT_TIMESTAMP)''', (version,))
    conn.commit()
    conn.close()


def get_all_embeddings(db_path: str = None):
    """Get all person embeddings for face recognition matching.
    Returns list of (id, name, embedding) tuples.
    """
    if db_path is None:
        db_path = get_db_path()
    if not os.path.exists(db_path):
        return []
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT id, name, embedding FROM persons WHERE embedding IS NOT NULL')
    rows = c.fetchall()
    conn.close()
    
    # Deserialize embeddings
    result = []
    for row in rows:
        person_id, name, emb_blob = row
        if emb_blob:
            embedding = pickle.loads(emb_blob)
            result.append((person_id, name, embedding))
    
    return result


def delete_person(person_id: int, db_path: str = None) -> bool:
    """Delete a person from the database by ID.
    Returns True if successful, False otherwise."""
    if db_path is None:
        db_path = get_db_path()
    if not os.path.exists(db_path):
        return False
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('DELETE FROM persons WHERE id = ?', (person_id,))
    conn.commit()
    deleted = c.rowcount > 0
    conn.close()
    return deleted


def get_all_person_ids(db_path: str = None) -> list:
    """Get all person IDs from the database."""
    if db_path is None:
        db_path = get_db_path()
    if not os.path.exists(db_path):
        return []
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT id FROM persons')
    rows = c.fetchall()
    conn.close()
    
    return [row[0] for row in rows]


def clear_all_persons(db_path: str = None):
    """Clear all persons from the database (used during sync)."""
    if db_path is None:
        db_path = get_db_path()
    if not os.path.exists(db_path):
        return
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('DELETE FROM persons')
    conn.commit()
    conn.close()


def bulk_insert_persons(persons_data: list, db_path: str = None):
    """Bulk insert multiple persons (used during sync from Supabase)."""
    if not persons_data:
        return
    
    if db_path is None:
        db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    for person in persons_data:
        # Convert embedding from hex string back to bytes
        embedding_blob = person.get('embedding')
        if embedding_blob and isinstance(embedding_blob, str):
            # Convert hex string back to bytes
            embedding_blob = bytes.fromhex(embedding_blob)
        
        c.execute('''INSERT OR REPLACE INTO persons 
                     (id, name, context, photo_path, audio_path, embedding, created_at, updated_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (person.get('id'),
                   person.get('name'),
                   person.get('context'),
                   person.get('photo_path'),
                   person.get('audio_path'),
                   embedding_blob,
                   person.get('created_at'),
                   person.get('updated_at')))
    
    conn.commit()
    conn.close()


if __name__ == '__main__':
    init_db()
