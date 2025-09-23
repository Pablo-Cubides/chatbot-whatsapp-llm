#!/usr/bin/env python3
"""
Script de utilidad para desarrollo del Chatbot WhatsApp LLM
Automatiza tareas comunes de desarrollo
"""

import sys
import json
import os
import logging
from pathlib import Path
from datetime import datetime

def clean_manual_queue():
    """Limpia la cola de mensajes manuales"""
    queue_file = "manual_queue.json"
    
    if os.path.exists(queue_file):
        try:
            with open(queue_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if data and isinstance(data, list):
                logging.getLogger(__name__).info(f"✅ Cola limpiada. Se eliminaron {len(data)} mensajes.")
            else:
                logging.getLogger(__name__).info("✅ Cola ya estaba vacía.")
        except Exception as e:
            logging.getLogger(__name__).warning(f"⚠️ Error leyendo cola existente: {e}")
    
    # Crear archivo vacío
    try:
        with open(queue_file, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        logging.getLogger(__name__).info(f"✅ Archivo {queue_file} reiniciado.")
    except Exception as e:
        logging.getLogger(__name__).error(f"❌ Error limpiando cola: {e}")

def add_manual_message(chat_id, message):
    """Agregar un mensaje manual a la cola."""
    queue_file = "manual_queue.json"
    
    # Leer cola existente
    try:
        if os.path.exists(queue_file):
            with open(queue_file, 'r', encoding='utf-8') as f:
                queue = json.load(f)
        else:
            queue = []
    except Exception as e:
        logging.getLogger(__name__).warning(f"⚠️ Error leyendo cola: {e}")
        queue = []
    
    # Agregar nuevo mensaje
    new_message = {
        "chat_id": chat_id,
        "message": message,
        "timestamp": datetime.now().isoformat(),
        "status": "pending"
    }
    
    queue.append(new_message)
    
    # Guardar cola
    try:
        with open(queue_file, 'w', encoding='utf-8') as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)
        logging.getLogger(__name__).info(f"✅ Mensaje agregado a la cola para {chat_id}")
    except Exception as e:
        logging.getLogger(__name__).error(f"❌ Error guardando cola: {e}")

def clean_logs(keep_lines=50):
    """Limpia los logs manteniendo solo las últimas N líneas"""
    log_file = Path("logs/automation.log")
    
    if not log_file.exists():
        logging.getLogger(__name__).error("❌ Archivo de logs no encontrado")
        return
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if len(lines) <= keep_lines:
            logging.getLogger(__name__).info(f"✅ Logs no necesitan limpieza ({len(lines)} líneas)")
            return
        
        # Mantener solo las últimas líneas
        keep_lines_data = lines[-keep_lines:]
        
        with open(log_file, 'w', encoding='utf-8') as f:
            f.writelines(keep_lines_data)
        logging.getLogger(__name__).info(f"✅ Logs limpiados: {len(lines)} → {len(keep_lines_data)} líneas")
    except Exception as e:
        logging.getLogger(__name__).error(f"❌ Error limpiando logs: {e}")

def show_recent_logs(lines=50):
    """Muestra las últimas N líneas de los logs"""
    log_file = Path("logs/automation.log")
    
    if not log_file.exists():
        logging.getLogger(__name__).error("❌ Archivo de logs no encontrado")
        return
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        recent_lines = all_lines[-lines:]
        
        logging.getLogger(__name__).info(f"📋 ÚLTIMAS {len(recent_lines)} LÍNEAS DE LOGS:")
        logging.getLogger(__name__).info("=" * 80)
        
        for line in recent_lines:
            logging.getLogger(__name__).info(line.rstrip())
        logging.getLogger(__name__).info("=" * 80)
        
    except Exception as e:
        logging.getLogger(__name__).error(f"❌ Error leyendo logs: {e}")

def analyze_logs():
    """Analiza los logs buscando patrones problemáticos"""
    log_file = Path("logs/automation.log")
    
    if not log_file.exists():
        logging.getLogger(__name__).error("❌ Archivo de logs no encontrado")
        return
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Patrones a buscar
        problems = {
            "USUARIO:": "Bot revelando naturaleza artificial",
            "CHAT ACTUAL:": "Respuestas de sistema internas", 
            "información relevante": "Terminología prohibida",
            "Escribe un mensaje": "Instrucciones del sistema",
            "El modelo configurado no está disponible": "Problema de conexión LM Studio",
            "❌ Error": "Errores en el sistema",
            "⚠️ Respuesta artificial detectada": "Sistema de filtros activado"
        }
        
        logging.getLogger(__name__).info("🔍 ANÁLISIS DE LOGS:")
        logging.getLogger(__name__).info("=" * 50)

        found_issues = False
        for pattern, description in problems.items():
            if pattern in content:
                count = content.count(pattern)
                logging.getLogger(__name__).warning(f"⚠️  {pattern}: {count} veces - {description}")
                found_issues = True
        
        if not found_issues:
            logging.getLogger(__name__).info("✅ No se encontraron patrones problemáticos en los logs")
        
        # Verificar última respuesta
        lines = content.split('\n')
        for line in reversed(lines):
            if "reply generado:" in line:
                logging.getLogger(__name__).info("\n📤 Última respuesta generada:")
                logging.getLogger(__name__).info(f"   {line}")
                break
        
        logging.getLogger(__name__).info("=" * 50)
    except Exception as e:
        logging.getLogger(__name__).error(f"❌ Error analizando logs: {e}")

def main():
    """Función principal"""
    if len(sys.argv) < 2:
        logging.getLogger(__name__).info("🛠️ UTILIDADES DE DESARROLLO - CHATBOT WHATSAPP LLM")
        logging.getLogger(__name__).info("\nUso:")
        logging.getLogger(__name__).info("  python dev_utils.py clean [líneas]    - Limpiar logs (default: 50 líneas)")
        logging.getLogger(__name__).info("  python dev_utils.py show [líneas]     - Mostrar logs recientes (default: 50)")
        logging.getLogger(__name__).info("  python dev_utils.py analyze           - Analizar logs buscando problemas")
        logging.getLogger(__name__).info("  python dev_utils.py clear-queue       - Limpiar cola de mensajes manuales")
        logging.getLogger(__name__).info("  python dev_utils.py add-manual        - Agregar mensaje manual a la cola")
        logging.getLogger(__name__).info("  python dev_utils.py prep              - Preparar para desarrollo (clean + show + analyze)")
        return
    
    command = sys.argv[1].lower()
    
    if command == "clean":
        lines = int(sys.argv[2]) if len(sys.argv) > 2 else 50
        clean_logs(lines)
    
    elif command == "show":
        lines = int(sys.argv[2]) if len(sys.argv) > 2 else 50
        show_recent_logs(lines)
    
    elif command == "analyze":
        analyze_logs()
    
    elif command == "clear-queue":
        clean_manual_queue()
    
    elif command == "add-manual":
        chat_id = input("Chat ID: ").strip()
        message = input("Mensaje: ").strip()
        add_manual_message(chat_id, message)
    
    elif command == "prep":
        logging.getLogger(__name__).info("🚀 PREPARANDO ENTORNO DE DESARROLLO...")
        logging.getLogger(__name__).info("\n1. Limpiando logs...")
        clean_logs(50)
        logging.getLogger(__name__).info("\n2. Mostrando logs recientes...")
        show_recent_logs(50)
        logging.getLogger(__name__).info("\n3. Analizando problemas...")
        analyze_logs()
        logging.getLogger(__name__).info("\n✅ Entorno preparado. Ahora ejecuta: python clean_start.py")
    
    else:
        logging.getLogger(__name__).error(f"❌ Comando desconocido: {command}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()