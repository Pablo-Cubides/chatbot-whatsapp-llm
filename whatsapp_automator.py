# whatsapp_automator.py - Versión simplificada y robusta

import json
import logging
import logging.handlers
import os
import time
from datetime import datetime, timedelta
# from string import Template  # not used
from playwright.sync_api import sync_playwright
import chat_sessions
from stub_chat import chat as stub_chat
from admin_db import get_session
from models import Conversation, ChatCounter
from model_manager import ModelManager
from settings import settings

# Public API exported from this module. Tests and external callers
# import these names from `whatsapp_automator` so expose them here
# to help static analyzers and attribute access checks.
__all__ = [
    'setup_logging',
    'fetch_new_message',
    'send_reply',
    'send_reply_with_typing',
    '_get_message_input',
    'cleanup_search_and_return_to_normal',
    'send_manual_message',
    'exit_chat_safely',
    'process_manual_queue',
    'main',
]

# --------------------------------------------
# Definición de logger
# --------------------------------------------
log = logging.getLogger(__name__)

def setup_logging(log_path: str) -> None:
    if not log_path:
        log_path = os.path.join(os.path.dirname(__file__), 'logs', 'automation.log')
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    
    class SmartFilter(logging.Filter):
        def __init__(self):
            import re
            import time
            super().__init__()
            self.re = re
            self.time = time
            self.regex = re.compile(r'\+?\d[\d\s\-]{7,}\d')
            self.repeated_count = {}
            self.last_logged_time = {}
            self.spam_patterns = [
                'Toggle AUTOMATION_ACTIVE=true',
                'Revisando \\d+ rows',
                'No hay nuevos mensajes, durmiendo',
                'fetch_new_message retornó: None, None',
                'número oculto.*no habilitado, saltar',
                'Row #\\d+ con badge \\d+',
                '→ Entrando a fetch_new_message'
            ]
        
        def filter(self, record):
            # Aplicar el filtro de números
            original_msg = record.getMessage()
            record.msg = self.regex.sub('[número oculto]', original_msg)
            record.args = ()
            
            # Filtrado inteligente para reducir spam
            msg = record.msg.lower()
            
            # Siempre permitir mensajes importantes
            important_keywords = [
                'nuevo mensaje detectado',
                'respondiendo',
                'error',
                'warning',
                'enviando al modelo',
                'respuesta exitosa',
                'contexto enviado',
                '===',
                'iniciado',
                'finalizando'
            ]
            
            if any(keyword in msg for keyword in important_keywords):
                return True
            
            # Solo filtrar logs DEBUG e INFO rutinarios, nunca WARNING/ERROR
            if record.levelno >= logging.WARNING:
                return True
            
            # Filtrar mensajes repetitivos de DEBUG/INFO rutinarios
            for pattern in self.spam_patterns:
                if self.re.search(pattern, msg, self.re.IGNORECASE):
                    # Contar repeticiones
                    key = f"{record.funcName}:{pattern}"
                    self.repeated_count[key] = self.repeated_count.get(key, 0) + 1
                    
                    # Solo mostrar cada 25 repeticiones o cada 2 minutos
                    current_time = self.time.time()
                    last_time = self.last_logged_time.get(key, 0)
                    
                    if (self.repeated_count[key] == 1 or 
                        self.repeated_count[key] % 25 == 0 or 
                        current_time - last_time > 120):  # 2 minutos
                        
                        if self.repeated_count[key] > 1:
                            record.msg = f"[x{self.repeated_count[key]}] {record.msg}"
                        self.last_logged_time[key] = current_time
                        return True
                    return False
            
            # Permitir otros mensajes no repetitivos
            return True
    
    handler.addFilter(SmartFilter())

    # Crear un handler para la consola (más estricto)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("[%(asctime)s][%(levelname)s] %(funcName)s – %(message)s", "%Y-%m-%d %H:%M:%S"))
    
    class ConsoleFilter(SmartFilter):
        def filter(self, record):
            # En consola solo mostrar WARNING y ERROR, más mensajes importantes
            if record.levelno >= logging.WARNING:
                return super().filter(record)
            
            msg = record.msg.lower()
            # Solo mostrar INFO/DEBUG importantes en consola
            console_important = [
                'nuevo mensaje detectado',
                'respondiendo',
                'enviando al modelo', 
                'respuesta exitosa',
                'iniciado',
                'finalizando'
            ]
            
            if any(keyword in msg for keyword in console_important):
                return super().filter(record)
            
            return False
    
    console_handler.addFilter(ConsoleFilter())

    logging.basicConfig(
        level=logging.DEBUG,
        format="[%(asctime)s][%(levelname)s] %(funcName)s – %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[handler, console_handler] # Añadir ambos handlers
    )
    log.info("=== WhatsApp Automator iniciado ===")


def _get_message_check_interval() -> float:
    """Return a safe numeric message check interval (seconds).
    Tries multiple config locations and coerces to float. Falls back to 5s.
    """
    try:
        # Prefer playwright nested setting
        val = None
        try:
            val = getattr(settings.playwright, 'message_check_interval')
        except Exception:
            val = getattr(settings, 'message_check_interval', None)
        if val is None:
            return 5.0
        return max(0.1, float(val))
    except Exception:
        return 5.0




def fetch_new_message(page, respond_to_all=False):
    """VERSIÓN ULTRA SIMPLE: SOLO responde si hay badge numérico Y último mensaje del usuario"""
    log.debug("→ Entrando a fetch_new_message()")
    
    try:
        page.wait_for_selector("#pane-side", timeout=5000)
        grid = page.locator("#pane-side")
        rows = grid.locator("div[role='listitem'], div[role='row']")
        count = rows.count()
        log.debug(f"– Revisando {count} rows")
        
        for i in range(count):
            row = rows.nth(i)
            
            # PASO 1: Buscar SOLO números visibles
            unread_count = 0
            spans = row.locator("span").all()
            for span in spans:
                try:
                    text = span.inner_text().strip()
                    if text.isdigit() and int(text) > 0:
                        unread_count = int(text)
                        break
                except Exception as e:
                    log.debug(f"Error reading span text: {e}")
                    continue
            
            # PASO 2: SALTAR si no hay número
            if unread_count <= 0:
                continue
                
            log.info(f"– Row #{i} con badge {unread_count}")
            
            # PASO 3: Obtener chat_id
            chat_id = None
            for sel in ["span[title]", "span[dir='auto']"]:
                elements = row.locator(sel)
                if elements.count() > 0:
                    title = elements.first.get_attribute("title")
                    if title and title.strip():
                        chat_id = title.strip()
                        break
                    text = elements.first.inner_text().strip()
                    if text and len(text) > 3:
                        chat_id = text
                        break
            
            if not chat_id:
                continue
                
            # PASO 4: Anti-bucle (cooldown) con base de datos
            try:
                session = get_session()
                counter = session.query(ChatCounter).filter(ChatCounter.chat_id == chat_id).first()
                # counter is a SQLAlchemy model; static type checkers may warn about Column objects
                if counter and counter.last_reply_at:  # type: ignore[truthy-bool]
                    # Use configured cooldown from settings; fallback to 2 minutes if malformed
                    cooldown_min = getattr(settings, 'automator_cooldown_minutes', 2)
                    try:
                        cooldown_delta = timedelta(minutes=float(cooldown_min))
                    except Exception:
                        # If parsing fails, fall back to the default from settings or 2 minutes
                        try:
                            fallback = float(getattr(settings, 'automator_cooldown_minutes', 2))
                            cooldown_delta = timedelta(minutes=fallback)
                        except Exception:
                            cooldown_delta = timedelta(minutes=2)
                    if datetime.utcnow() - counter.last_reply_at < cooldown_delta:  # type: ignore[arg-type]
                        log.info(f"– {chat_id} en cooldown (>{cooldown_min}m), saltar")
                        session.close()
                        continue
                session.close()
            except Exception as e:
                log.debug(f"Error checking cooldown for {chat_id}: {e}")
                pass
                
            # PASO 5: Verificar permisos
            try:
                if not respond_to_all:
                    require = settings.require_contact_profile
                    if require and not chat_sessions.is_ready_to_reply(chat_id):
                        log.info(f"– {chat_id} no habilitado, saltar")
                        continue
            except Exception as e:
                log.debug(f"Error checking permissions for {chat_id}: {e}")
                pass
                
            # PASO 6: Abrir y verificar último mensaje
            try:
                row.click()
                page.wait_for_timeout(1500)
                log.info(f"– Abriendo {chat_id}")
                
                # Buscar último mensaje
                msgs = page.locator("div[data-testid='msg-container']")
                if msgs.count() == 0:
                    msgs = page.locator(".message-in, .message-out")
                
                if msgs.count() > 0:
                    last_msg = msgs.last
                    
                    # ¿Es saliente (del bot)?
                    is_bot = False
                    try:
                        if last_msg.locator(".message-out, [data-testid*='outgoing']").count() > 0:
                            is_bot = True
                        elif "message-out" in (last_msg.get_attribute("class") or ""):
                            is_bot = True
                    except Exception as e:
                        log.debug(f"Error checking message direction: {e}")
                        pass
                        
                    if is_bot:
                        log.info(f"– {chat_id} último mensaje del bot, saltar")
                        continue
                        
                    # Extraer texto
                    try:
                        text_elem = last_msg.locator("span.selectable-text").first
                        incoming = text_elem.inner_text().strip() if text_elem.count() > 0 else "[msg]"
                    except Exception as e:
                        log.debug(f"Error extracting message text: {e}")
                        incoming = "[msg]"
                    
                    log.info(f"– {chat_id} mensaje válido: {incoming[:50]}")
                    return chat_id, incoming
                        
            except Exception as e:
                log.error(f"– Error procesando {chat_id}: {e}")
                continue
        
        return None, None
        
    except Exception as e:
        log.error(f"Error en fetch_new_message: {e}")
        return None, None


def _get_message_input(page):
    """Devuelve el locator de la caja de texto del compositor de mensajes."""
    candidates = [
        "footer div[contenteditable='true'][data-tab][data-lexical-editor='true']",
        "footer div[contenteditable='true'][data-tab]",
        "div[contenteditable='true'][data-tab='10']",
        "div[contenteditable='true'][data-tab]",
        "div[aria-label*='mensaje']",
        "div[aria-label*='message']",
    ]
    for sel in candidates:
        locator = page.locator(sel)
        try:
            if locator.count() > 0:
                target = locator.last
                target.wait_for(state="visible", timeout=3000)
                log.debug(f"Input de mensaje encontrado con selector: {sel}")
                return target
        except Exception:
            continue
    raise RuntimeError("No se encontró la caja de texto del mensaje")

def send_reply(page, chat_id, reply_text):
    """Envía 'reply_text' en el chat actual."""
    input_box = _get_message_input(page)
    try:
        input_box.click()
    except Exception:
        pass
    input_box.fill(reply_text)
    input_box.press("Enter")
    log.info(f"Mensaje enviado a {chat_id}")

def send_reply_with_typing(page, chat_id, reply_text, per_char_delay=0.05):
    """Simula typing enviando caracter por caracter."""
    log.debug(f"📝 Iniciando envío con typing para {chat_id}: {reply_text[:30]}...")
    
    try:
        # Primero intentar con la función existente
        input_box = _get_message_input(page)
        log.debug("✅ Input de mensaje encontrado con función _get_message_input")
    except Exception as e:
        log.warning(f"⚠️ Error con _get_message_input: {e}")
        
        # Intentar con selectores más específicos para el contexto actual
        specific_selectors = [
            "div[data-testid='conversation-compose-box-input']",
            "footer div[contenteditable='true'][data-tab='10']",
            "div[data-tab='10'][contenteditable='true']",
            "footer div[role='textbox']",
            "div[contenteditable='true'][role='textbox']"
        ]
        
        input_box = None
        for selector in specific_selectors:
            try:
                locator = page.locator(selector)
                if locator.count() > 0:
                    input_box = locator.first
                    log.debug(f"✅ Input encontrado con selector específico: {selector}")
                    break
            except Exception:
                continue
        
        if not input_box:
            log.error("❌ No se pudo encontrar el input de mensaje")
            return False

    try:
        # Hacer click en el input para asegurar que está activo
        input_box.click()
        page.wait_for_timeout(200)
        log.debug("✅ Click en input realizado")
    except Exception as e:
        log.warning(f"⚠️ Error haciendo click en input: {e}")

    try:
        # Limpiar el input
        input_box.fill("")
        page.wait_for_timeout(100)
        
        # Escribir caracter por caracter
        chunk = ""
        for ch in reply_text:
            chunk += ch
            input_box.fill(chunk)
            page.wait_for_timeout(int(per_char_delay * 1000))
        
        log.debug(f"✅ Texto escrito: {chunk[:30]}...")
        
        # Presionar Enter para enviar
        input_box.press("Enter")
        page.wait_for_timeout(500)
        
        log.info(f"✅ Mensaje (typing-sim) enviado a {chat_id}")
        return True
        
    except Exception as e:
        log.error(f"❌ Error escribiendo/enviando mensaje: {e}")
        return False

def cleanup_search_and_return_to_normal(page):
    """Limpia la búsqueda y vuelve a la ventana normal de WhatsApp"""
    try:
        log.debug("🧹 Iniciando limpieza de búsqueda...")
        
        # 1. Presionar Esc para salir del chat
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
        log.debug("✅ Esc presionado para salir del chat")
        
        # 2. Buscar y hacer click en la X para cerrar búsqueda
        close_search_selectors = [
            "span[data-icon='close-refreshed']",
            "button[aria-label='Cerrar búsqueda']",
            "span[aria-hidden='true'][data-icon='close-refreshed']",
            # Selector más específico basado en el HTML que proporcionaste
            "span[data-icon='close-refreshed'] svg"
        ]
        
        search_closed = False
        for selector in close_search_selectors:
            try:
                close_button = page.locator(selector)
                if close_button.count() > 0:
                    close_button.first.click(timeout=2000)
                    search_closed = True
                    log.debug(f"✅ Búsqueda cerrada con selector: {selector}")
                    break
            except Exception as e:
                log.debug(f"❌ Error cerrando búsqueda con {selector}: {e}")
                continue
        
        if not search_closed:
            # Método alternativo: hacer click en el área principal
            try:
                page.click("div[data-testid='chat-list']", timeout=2000)
                log.debug("✅ Búsqueda cerrada haciendo click en chat-list")
            except Exception as e:
                log.debug(f"❌ Error con método alternativo: {e}")
        
        page.wait_for_timeout(300)
        log.debug("🏠 Limpieza completada - de vuelta a ventana normal")
        
    except Exception as e:
        log.warning(f"⚠️ Error en limpieza de búsqueda: {e}")

def send_manual_message(page, chat_id, message_text, per_char_delay=0.05):
    """Envía un mensaje manual buscando el chat específico primero."""
    try:
        log.info(f"📤 Iniciando envío manual a {chat_id}: {message_text[:50]}...")
        
        # 1. Salir de cualquier chat actual
        exit_chat_safely(page)
        page.wait_for_timeout(1000)
        
        # 2. Activar búsqueda
        search_clicked = False
        search_selectors = [
            "div[data-testid='chat-list-search']",
            "div[data-tab='3']",
            "div[title='Buscar o empezar un chat nuevo']",
            "label[data-testid='chat-list-search-label']"
        ]
        
        for selector in search_selectors:
            try:
                page.click(selector, timeout=2000)
                search_clicked = True
                log.debug(f"✅ Search activado con: {selector}")
                break
            except Exception:
                continue
        
        if not search_clicked:
            log.error("❌ No se pudo activar la búsqueda")
            return False
        
        page.wait_for_timeout(500)
        
        # 3. Escribir en la búsqueda
        search_input_selectors = [
            "div[data-testid='chat-list-search'] div[contenteditable='true']",
            "div[data-tab='3'][contenteditable='true']",
            "div[contenteditable='true'][data-tab='3']"
        ]
        
        search_input = None
        for selector in search_input_selectors:
            try:
                search_input = page.locator(selector).first
                if search_input.count() > 0:
                    break
            except Exception:
                continue
        
        if not search_input or search_input.count() == 0:
            log.error("❌ No se encontró input de búsqueda")
            return False
        
        # Escribir el contacto
        search_input.fill("")
        search_input.type(chat_id)
        page.wait_for_timeout(2000)  # Esperar resultados
        
        log.debug(f"🔍 Búsqueda realizada para: {chat_id}")
        
        # 4. Seleccionar primera conversación
        # ESTRATEGIA 1: Probar Enter primero
        try:
            search_input.press("Enter")
            page.wait_for_timeout(1500)
            
            # Verificar si se abrió el chat
            chat_input = page.locator("div[data-testid='conversation-compose-box-input']")
            if chat_input.count() > 0:
                log.debug("✅ Enter abrió el chat exitosamente")
                # Enviar mensaje
                # DEBUG: log the send_reply_with_typing call and result
                try:
                    log.debug("[wa-canonical] about to call send_reply_with_typing: %s", send_reply_with_typing)
                except Exception:
                    pass
                message_sent = send_reply_with_typing(page, chat_id, message_text, per_char_delay)
                try:
                    log.debug("[wa-canonical] send_reply_with_typing returned: %s", message_sent)
                except Exception:
                    pass
                
                if message_sent:
                    log.info(f"✅ Mensaje manual enviado exitosamente a {chat_id}")
                    cleanup_search_and_return_to_normal(page)
                    return True
                else:
                    log.error("❌ Error enviando mensaje en chat abierto con Enter")
                    return False
        except Exception as e:
            log.debug(f"❌ Enter no funcionó: {e}")
        
        # ESTRATEGIA 2: Click en primera conversación
        conversation_selectors = [
            "div[data-testid='cell-frame-container'] div[role='gridcell']",
            "div[data-testid='cell-frame-container']",
            "div[role='listitem'] div[role='gridcell']",
            "div[role='listitem']",
            "div[data-animate-chat-entry]"
        ]
        
        for selector in conversation_selectors:
            try:
                conversations = page.locator(selector)
                count = conversations.count()
                if count > 0:
                    log.debug(f"📋 Encontradas {count} conversaciones con: {selector}")
                    
                    click_success = False
                    
                    try:
                        conversations.first.click(timeout=3000)
                        click_success = True
                        log.debug(f"✅ Click normal exitoso con: {selector}")
                    except Exception as e:
                        log.debug(f"❌ Click normal falló con {selector}: {e}")
                    
                    if not click_success:
                        try:
                            conversations.first.dblclick(timeout=3000)
                            click_success = True
                            log.debug(f"✅ Double click exitoso con: {selector}")
                        except Exception as e:
                            log.debug(f"❌ Double click falló con {selector}: {e}")
                    
                    if not click_success:
                        try:
                            conversations.first.click(position={"x": 50, "y": 30}, timeout=3000)
                            click_success = True
                            log.debug(f"✅ Click con coordenadas exitoso con: {selector}")
                        except Exception as e:
                            log.debug(f"❌ Click con coordenadas falló con {selector}: {e}")
                    
                    if click_success:
                        page.wait_for_timeout(2000)  # Esperar más tiempo
                        
                        chat_opened = False
                        chat_indicators = [
                            "div[data-testid='conversation-compose-box-input']",
                            "footer div[contenteditable='true'][data-tab='10']",
                            "div[data-tab='10'][contenteditable='true']",
                            "footer div[role='textbox']",
                            "div[contenteditable='true'][role='textbox']",
                            
                            "header[data-testid='conversation-header']",
                            "div[data-testid='conversation-header']",
                            
                            "div[data-testid='conversation-panel-messages']",
                            "div[role='application'][data-tab='6']",
                            
                            "div[data-testid='conversation-panel-wrapper']",
                            "footer[data-testid='compose-box']"
                        ]
                        
                        for indicator in chat_indicators:
                            try:
                                if page.locator(indicator).count() > 0:
                                    chat_opened = True
                                    log.debug(f"✅ Chat confirmado abierto con indicador: {indicator}")
                                    break
                            except Exception:
                                continue
                        
                        if chat_opened:
                            log.debug(f"✅ Chat abierto con selector: {selector}")
                            message_sent = send_reply_with_typing(page, chat_id, message_text, per_char_delay)
                            
                            if message_sent:
                                log.info(f"✅ Mensaje manual enviado exitosamente a {chat_id}")
                                cleanup_search_and_return_to_normal(page)
                                return True
                            else:
                                log.error(f"❌ Error enviando mensaje en chat abierto con {selector}")
                                return False
                        else:
                            log.debug(f"❌ Click en {selector} no abrió el chat - ningún indicador encontrado")
                    else:
                        log.debug(f"❌ Todos los tipos de click fallaron con {selector}")
                        
            except Exception as e:
                log.debug(f"❌ Error con selector {selector}: {e}")
                continue
        
        log.error(f"❌ No se pudo abrir el chat {chat_id}")
        return False
        
    except Exception as e:
        log.error(f"❌ Error general en envío manual: {e}")
        return False

def exit_chat_safely(page):
    """Sale del chat actual y vuelve a la lista principal."""
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        log.debug("ESC presionado")
        
        try:
            page.click("span[data-icon='status-outline']", timeout=3000)
            page.wait_for_timeout(400)
            page.click("span[data-icon='chats-outline']", timeout=3000)
            log.debug("Navegación Status -> Chats")
        except Exception as e:
            log.debug(f"Error in navigation Status -> Chats: {e}")
            page.click("#pane-side", timeout=3000)
            
        composers = page.locator("footer div[contenteditable='true'][data-tab]")
        if composers.count() > 0:
            page.keyboard.press("Escape")
            log.debug("ESC adicional tras detectar compositor")
            
    except Exception as e:
        log.warning(f"Error saliendo del chat: {e}")

def process_manual_queue(page) -> bool:
    """Procesa la cola de mensajes manuales. Retorna True si se procesó algún mensaje."""
    try:
        here = os.path.dirname(__file__)
        queue_file = os.path.join(here, 'data', 'manual_queue.json')
        
        if not os.path.exists(queue_file):
            return False
        
        with open(queue_file, 'r', encoding='utf-8') as f:
            queue = json.load(f)
        
        pending_messages = [msg for msg in queue if msg.get('status') == 'pending']
        
        if not pending_messages:
            return False
        
        message = pending_messages[0]
        chat_id = message['chat_id']
        content = message['message']
        
        log.info(f"📤 Procesando mensaje manual para {chat_id}: {content[:50]}...")
        
        try:
            per_char = getattr(settings, 'typing_per_char', 0.05)
        except Exception:
            per_char = 0.05

        success = send_manual_message(page, chat_id, content, per_char_delay=per_char)
        
        for msg in queue:
            if msg['id'] == message['id']:
                if success:
                    msg['status'] = 'sent'
                    msg['sent_timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')
                    log.info(f"✅ Mensaje manual enviado a {chat_id}")
                else:
                    msg['status'] = 'failed'
                    msg['failed_timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')
                    log.error(f"❌ Mensaje manual falló para {chat_id} - marcado como failed")
                break
        
        with open(queue_file, 'w', encoding='utf-8') as f:
            json.dump(queue, f, indent=2, ensure_ascii=False)
        
        return success
        
    except Exception as e:
        log.error(f"❌ Error procesando cola manual: {e}")
        return False


def main() -> None:
    log_path = settings.log_path
    if log_path:
        setup_logging(log_path)
    log.debug("Configuración cargada desde settings.py")

    chat_sessions.initialize_db()
    log.info("Base de datos de contexto inicializada")

    # Expand environment variables and provide safe fallback for profile dir
    try:
        raw_profile = getattr(settings.playwright, 'user_data_dir', None)
    except Exception:
        raw_profile = getattr(settings, 'playwright', None) and getattr(settings.playwright, 'user_data_dir', None)

    if not raw_profile:
        raw_profile = os.path.join(os.path.dirname(__file__), 'data', 'playwright_profile')

    profile_dir = os.path.expandvars(str(raw_profile))
    # Verificar si es un archivo y eliminarlo si es necesario
    try:
        if os.path.exists(profile_dir):
            if os.path.isfile(profile_dir):
                os.remove(profile_dir)
            # Si ya es un directorio, no hacer nada
        os.makedirs(profile_dir, exist_ok=True)
    except (OSError, FileExistsError) as e:
        log.debug(f"Error creando directorio de perfil: {e}")
        # Intentar usar el directorio existente si es válido
        if not os.path.isdir(profile_dir):
            # Si no es un directorio válido, usar uno temporal
            import tempfile
            profile_dir = tempfile.mkdtemp(prefix="whatsapp_profile_")
            log.warning(f"Usando directorio temporal: {profile_dir}")
    log.debug(f"Perfil de Chromium: {profile_dir}")

    keep_open = settings.keep_automator_open

    with sync_playwright() as p:
        log.info("Iniciando Playwright...")
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir, headless=settings.playwright.headless
        )
        log.info(f"Contexto del navegador lanzado. Headless={settings.playwright.headless}, UserDataDir={profile_dir}")
        page = ctx.new_page()
        log.info("Nueva página creada.")
        
        try:
            log.info(f"Navegando a {settings.playwright.whatsapp_url} con timeout {settings.playwright.navigation_timeout}ms...")
            page.goto(settings.playwright.whatsapp_url, timeout=settings.playwright.navigation_timeout)
            log.info(f"Navegación a {settings.playwright.whatsapp_url} completada.")
            
            log.info("Esperando selector #pane-side (WhatsApp Web cargado)...")
            page.wait_for_selector("#pane-side", timeout=settings.playwright.navigation_timeout)
            log.info("WhatsApp Web cargado correctamente (#pane-side encontrado).")
        except Exception:
            log.exception("Error al cargar WhatsApp Web o encontrar el selector #pane-side.", exc_info=True)
            if not keep_open:
                try:
                    ctx.close()
                except Exception:
                    pass
                return

        try:
            page.wait_for_selector("#pane-side", timeout=15000)
            log.info("Panel de chats cargado, entrando al loop principal")
        except TimeoutError:
            log.error("Timeout cargando panel de chats")
            try:
                ctx.close()
            except Exception:
                pass
            return

        try:
            while True:
                # Safe toggle getter
                try:
                    toggle = bool(getattr(settings, 'automation_active', True))
                except Exception:
                    toggle = True

                log.debug(f"Toggle AUTOMATION_ACTIVE={toggle}")
                if not toggle:
                    log.info("Automatización desactivada, durmiendo…")
                    time.sleep(_get_message_check_interval())
                    continue

                # Leer respond_to_all (safe)
                try:
                    respond_to_all = bool(getattr(settings, 'respond_to_all', False))
                except Exception:
                    respond_to_all = False

                chat_id, incoming = fetch_new_message(page, respond_to_all)
                log.debug(f"fetch_new_message retornó: {chat_id}, {incoming}")

                if not chat_id or incoming is None:
                    # No hay mensajes nuevos, verificar cola de mensajes manuales
                    manual_processed = process_manual_queue(page)
                    if manual_processed:
                        # Si se procesó un mensaje manual, continuar el ciclo inmediatamente
                        continue

                    log.debug("No hay nuevos mensajes, durmiendo…")
                    time.sleep(_get_message_check_interval())
                    continue

                log.info(f"[{chat_id}] Mensaje entrante: '{incoming}'")
                
                # Generar respuesta
                history = chat_sessions.load_last_context(chat_id)
                history.append({"role": "user", "content": incoming})
                
                try:
                    mm = ModelManager()
                    session = get_session()
                    msg_count = session.query(Conversation).filter(Conversation.chat_id == chat_id).count()
                    session.close()
                    chosen_model = mm.choose_model_for_conversation(chat_id, msg_count)
                    log.debug(f"[{chat_id}] Modelo elegido: {chosen_model}")
                    
                    reply = stub_chat(incoming, chat_id, history)
                    log.info(f"[{chat_id}] reply generado: '{reply}'")
                    
                    # Si no hay respuesta disponible (LM Studio no conectado), no enviar nada
                    if not reply or reply.strip() == "":
                        log.warning(f"[{chat_id}] No se generó respuesta (posible problema con LM Studio)")
                        continue
                except Exception:
                    log.exception("Error generando respuesta con stub_chat")
                    # No enviar mensaje de error al usuario, simplemente continuar sin responder
                    continue
                
                history.append({"role": "assistant", "content": reply})
                chat_sessions.save_context(chat_id, history)
                log.info(f"[{chat_id}] Historial actualizado y guardado ({len(history)} turnos)")

                # Enviar respuesta
                try:
                    per_char = float(os.getenv("TYPING_PER_CHAR", "0.05"))
                except Exception:
                    per_char = 0.05
                
                try:
                    if not reply:
                        reply = ""
                    send_reply_with_typing(page, chat_id, reply, per_char_delay=per_char)
                    
                    # IMPORTANTE: Salir del chat para evitar quedarse en modo escritura
                    exit_chat_safely(page)
                    log.debug("Salida segura del chat después de enviar mensaje")
                    
                    # Marcar tiempo de respuesta
                    session = get_session()
                    counter = session.query(ChatCounter).filter(ChatCounter.chat_id == chat_id).first()
                    if not counter:
                        counter = ChatCounter(chat_id=chat_id)
                        session.add(counter)
                    # Assign last reply time (SQLAlchemy-managed attribute)
                    counter.last_reply_at = datetime.utcnow()  # type: ignore[attr-defined]
                    session.commit()
                    session.close()
                    
                except Exception:
                    log.exception("Fallo enviando el mensaje a WhatsApp")
                
                # Ejecutar reasoner si es necesario
                try:
                    n = chat_sessions.increment_reply_counter(chat_id)
                    threshold = settings.strategy_refresh_every
                    if n >= threshold:
                        chat_sessions.reset_reply_counter(chat_id)
                        try:
                            from reasoner import update_chat_context_and_profile
                            res = update_chat_context_and_profile(chat_id)
                            log.info(f"[{chat_id}] Razonador ejecutado. Estrategia v{res.get('version')} | contexto={res.get('wrote_contexto')} perfil={res.get('wrote_perfil')}")
                        except Exception:
                            log.exception(f"[{chat_id}] Falló el razonador")
                except Exception:
                    log.exception("Error actualizando contadores/razonador")
                
                # Salir del chat de forma segura
                exit_chat_safely(page)

                log.debug(f"Durmiendo {settings.playwright.message_check_interval}s antes del próximo ciclo")
                time.sleep(_get_message_check_interval())

        except KeyboardInterrupt:
            log.info("Interrupción manual recibida, cerrando…")
        except Exception:
            log.exception("Excepción no controlada en el loop principal", exc_info=True)
        finally:
            if not keep_open:
                try:
                    ctx.close()
                except Exception:
                    pass
                log.info("Contexto del navegador cerrado, fin del programa")

if __name__ == "__main__":
    main()
