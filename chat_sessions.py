import sqlite3
import json
import os
from datetime import datetime

# Ruta de la base de datos SQLite
DB_PATH = 'chatbot_context.db'

# Crear la base de datos y tabla si no existe
def initialize_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            context TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

# Guardar o actualizar contexto
def save_context(chat_id, context):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    context_json = json.dumps(context, ensure_ascii=False)

    cursor.execute('''
        INSERT INTO conversations (chat_id, context, timestamp)
        VALUES (?, ?, ?)
    ''', (chat_id, context_json, datetime.now()))
    
    conn.commit()
    conn.close()

# Recuperar último contexto por chat_id
def load_last_context(chat_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT context FROM conversations
        WHERE chat_id = ?
        ORDER BY timestamp DESC
        LIMIT 1
    ''', (chat_id,))
    
    row = cursor.fetchone()
    conn.close()

    if row:
        return json.loads(row[0])
    else:
        return []

# Inicializar automáticamente al importar
initialize_db()
