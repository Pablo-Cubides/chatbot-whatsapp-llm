# whatsapp_automator.py - Versión simplificada y robusta

import contextlib
import json
import logging
import logging.handlers
import os
import os as _os
import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from string import Template
from typing import Any

from dotenv import load_dotenv
from model_manager import ModelManager
from playwright.sync_api import sync_playwright
from stub_chat import chat as stub_chat

import chat_sessions
from admin_db import get_session
from models import Conversation
from src.services.queue_system import queue_manager

# --------------------------------------------
# Definición de logger
# --------------------------------------------
log = logging.getLogger(__name__)

# --------------------------------------------
# Constantes operativas (evitar valores mágicos)
# --------------------------------------------
NAVIGATION_TIMEOUT_MS = 30000
PAGE_LOAD_TIMEOUT_MS = 30000
REPLY_DELAY_SECONDS = 0.05
LOOP_SLEEP_INTERVAL = 2
COOLDOWN_SECONDS = 120
TEXT_LENGTH_TYPING_THRESHOLD = 60
MAX_REPLY_LENGTH = 8000
PER_CHAR_TYPING_DELAY = 0.05


def sanitize_message_content(text: str) -> str:
    """Redacta contenido de mensajes en logs conservando metadatos operativos."""
    if not text:
        return ""

    redacted = str(text)
    # Patrones comunes de logs que incluyen contenido textual del mensaje.
    redacted = redacted.replace("mensaje válido:", "mensaje válido: [contenido redactado]")
    redacted = redacted.replace("Contexto enviado:", "Contexto enviado: [contenido redactado]")
    redacted = redacted.replace("enviando al modelo:", "enviando al modelo: [contenido redactado]")

    # También redacción defensiva de trazas tipo key=value para contenido.
    import re

    return re.sub(r"(message|content|texto|mensaje)\s*[=:]\s*.+", r"\1=[contenido redactado]", redacted, flags=re.IGNORECASE)


def load_config() -> dict:
    here = os.path.dirname(__file__)
    fp = os.path.join(here, "config", "playwright_config.json")
    raw = open(fp, encoding="utf-8").read()

    # Definir valores por defecto para las variables de entorno
    env_defaults = {
        "PLAYWRIGHT_PROFILE_DIR": "./data/whatsapp-profile",
        "WHATSAPP_URL": "https://web.whatsapp.com/",
        "MESSAGE_CHECK_INTERVAL": "2",
    }

    # Crear un diccionario combinando variables de entorno y valores por defecto
    env_vars = {}
    for key, default_value in env_defaults.items():
        env_vars[key] = os.environ.get(key, default_value)

    try:
        filled = Template(raw).substitute(env_vars)
        cfg = json.loads(filled)
    except (KeyError, ValueError) as e:
        log.warning(f"Error al procesar configuración: {e}. Usando valores por defecto.")
        # Configuración por defecto si falla el archivo
        cfg = {
            "userDataDir": "./data/whatsapp-profile",
            "whatsappUrl": "https://web.whatsapp.com/",
            "headless": False,
            "messageCheckInterval": "2",
            "maxRetries": 3,
            "navigationTimeout": NAVIGATION_TIMEOUT_MS,
        }

    log.debug(f"Configuración cargada: {cfg}")
    return cfg


def setup_logging(log_path: str) -> None:
    if not log_path:
        log_path = os.path.join(os.path.dirname(__file__), "logs", "automation.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(log_path, maxBytes=5_000_000, backupCount=3, encoding="utf-8")

    class SmartFilter(logging.Filter):
        def __init__(self) -> None:
            import re
            import time

            super().__init__()
            self.re = re
            self.time = time
            self.regex = re.compile(r"\+?\d[\d\s\-]{7,}\d")
            self.repeated_count = {}
            self.last_logged_time = {}
            self.spam_patterns = [
                "Toggle AUTOMATION_ACTIVE=true",
                "Revisando \\d+ rows",
                "No hay nuevos mensajes, durmiendo",
                "fetch_new_message retornó: None, None",
                "número oculto.*no habilitado, saltar",
                "Row #\\d+ con badge \\d+",
                "→ Entrando a fetch_new_message",
            ]

        def filter(self, record) -> bool:
            # Aplicar el filtro de números
            original_msg = record.getMessage()
            sanitized_msg = sanitize_message_content(original_msg)
            record.msg = self.regex.sub("[número oculto]", sanitized_msg)
            record.args = ()

            # Filtrado inteligente para reducir spam
            msg = record.msg.lower()

            # Siempre permitir mensajes importantes
            important_keywords = [
                "nuevo mensaje detectado",
                "respondiendo",
                "error",
                "warning",
                "enviando al modelo",
                "respuesta exitosa",
                "contexto enviado",
                "===",
                "iniciado",
                "finalizando",
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

                    if (
                        self.repeated_count[key] == 1
                        or self.repeated_count[key] % 25 == 0
                        or current_time - last_time > COOLDOWN_SECONDS
                    ):
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
    console_handler.setFormatter(
        logging.Formatter("[%(asctime)s][%(levelname)s] %(funcName)s – %(message)s", "%Y-%m-%d %H:%M:%S")
    )

    class ConsoleFilter(SmartFilter):
        def filter(self, record):
            # En consola solo mostrar WARNING y ERROR, más mensajes importantes
            if record.levelno >= logging.WARNING:
                return super().filter(record)

            msg = record.msg.lower()
            # Solo mostrar INFO/DEBUG importantes en consola
            console_important = [
                "nuevo mensaje detectado",
                "respondiendo",
                "enviando al modelo",
                "respuesta exitosa",
                "iniciado",
                "finalizando",
            ]

            if any(keyword in msg for keyword in console_important):
                return super().filter(record)

            return False

    console_handler.addFilter(ConsoleFilter())

    logging.basicConfig(
        level=logging.DEBUG,
        format="[%(asctime)s][%(levelname)s] %(funcName)s – %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[handler, console_handler],  # Añadir ambos handlers
    )
    log.info("=== WhatsApp Automator iniciado ===")


# Registro de últimas respuestas para evitar bucles
LAST_REPLIED = {}
MAX_LAST_REPLIED = int(os.getenv("MAX_LAST_REPLIED", "5000"))
SHUTDOWN_EVENT = threading.Event()


def _request_shutdown(signum, _frame) -> None:
    """Signal handler para detener el loop principal sin cortar recursos abruptamente."""
    SHUTDOWN_EVENT.set()
    log.info("Señal %s recibida. Iniciando apagado ordenado...", signum)


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

            # PASO 4: Anti-bucle (cooldown)
            try:
                last_time = LAST_REPLIED.get(chat_id, 0)
                if time.time() - last_time < COOLDOWN_SECONDS:
                    log.info(f"– {chat_id} en cooldown, saltar")
                    continue
            except Exception as e:
                log.debug(f"Error checking cooldown for {chat_id}: {e}")
                pass

            # PASO 5: Verificar permisos
            try:
                if not respond_to_all:
                    require = os.getenv("REQUIRE_CONTACT_PROFILE", "true").lower() == "true"
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
                        if last_msg.locator(".message-out, [data-testid*='outgoing']").count() > 0 or "message-out" in (
                            last_msg.get_attribute("class") or ""
                        ):
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


def send_reply(page, chat_id, reply_text) -> None:
    """Envía 'reply_text' en el chat actual."""
    input_box = _get_message_input(page)
    with contextlib.suppress(Exception):
        input_box.click()
    input_box.fill(reply_text)
    input_box.press("Enter")
    log.info(f"Mensaje enviado a {chat_id}")


def send_reply_with_typing(page, chat_id, reply_text, per_char_delay=PER_CHAR_TYPING_DELAY) -> bool | None:
    """Simula typing de forma eficiente (chunked/instant/human) evitando latencias extremas."""
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
            "div[contenteditable='true'][role='textbox']",
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
        page.wait_for_timeout(60)

        mode = os.getenv("AUTOMATOR_TYPING_MODE", "chunked").lower()
        text_len = len(reply_text or "")

        if mode == "instant" or text_len > 900:
            input_box.fill(reply_text)
            page.wait_for_timeout(80)
            log.debug("✅ Texto escrito en modo instant")
        elif mode == "human":
            # Mantener modo humano para mensajes cortos; para largos cae a chunked
            if text_len <= (TEXT_LENGTH_TYPING_THRESHOLD * 3):
                input_box.type(reply_text, delay=max(1, int(per_char_delay * 1000)))
            else:
                mode = "chunked"

        if mode == "chunked":
            chunk_size = max(
                25,
                int(
                    os.getenv("AUTOMATOR_TYPING_CHUNK_SIZE", str(TEXT_LENGTH_TYPING_THRESHOLD))
                    or str(TEXT_LENGTH_TYPING_THRESHOLD)
                ),
            )
            base_pause_ms = max(10, int(os.getenv("AUTOMATOR_TYPING_CHUNK_PAUSE_MS", "35") or "35"))

            current = ""
            for i in range(0, text_len, chunk_size):
                current += reply_text[i : i + chunk_size]
                input_box.fill(current)
                # Pausa ligera para simular escritura sin costo O(n^2) en segundos
                page.wait_for_timeout(base_pause_ms)

            log.debug(f"✅ Texto escrito en modo chunked: {current[:30]}...")

        # Presionar Enter para enviar
        input_box.press("Enter")
        page.wait_for_timeout(180)

        log.info(f"✅ Mensaje (typing-sim) enviado a {chat_id}")
        return True

    except Exception as e:
        log.error(f"❌ Error escribiendo/enviando mensaje: {e}")
        return False


def cleanup_search_and_return_to_normal(page) -> None:
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
            "span[data-icon='close-refreshed'] svg",
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


def send_manual_message(page, chat_id, message_text, per_char_delay=0.05) -> bool | None:
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
            "label[data-testid='chat-list-search-label']",
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
            "div[contenteditable='true'][data-tab='3']",
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
                message_sent = send_reply_with_typing(page, chat_id, message_text, per_char_delay)

                if message_sent:
                    log.info(f"✅ Mensaje manual enviado exitosamente a {chat_id}")
                    # PASO ADICIONAL: Limpiar búsqueda y volver a ventana normal
                    cleanup_search_and_return_to_normal(page)
                    return True
                log.error("❌ Error enviando mensaje en chat abierto con Enter")
                return False
        except Exception as e:
            log.debug(f"❌ Enter no funcionó: {e}")

        # ESTRATEGIA 2: Click en primera conversación
        conversation_selectors = [
            # Selectores más específicos para elementos clickeables
            "div[data-testid='cell-frame-container'] div[role='gridcell']",
            "div[data-testid='cell-frame-container']",
            "div[role='listitem'] div[role='gridcell']",
            "div[role='listitem']",
            "div[data-animate-chat-entry]",
        ]

        for selector in conversation_selectors:
            try:
                conversations = page.locator(selector)
                count = conversations.count()
                if count > 0:
                    log.debug(f"📋 Encontradas {count} conversaciones con: {selector}")

                    # Probar diferentes estrategias de click
                    click_success = False

                    # Estrategia A: Click normal
                    try:
                        conversations.first.click(timeout=3000)
                        click_success = True
                        log.debug(f"✅ Click normal exitoso con: {selector}")
                    except Exception as e:
                        log.debug(f"❌ Click normal falló con {selector}: {e}")

                    # Estrategia B: Double click si el click normal no funcionó
                    if not click_success:
                        try:
                            conversations.first.dblclick(timeout=3000)
                            click_success = True
                            log.debug(f"✅ Double click exitoso con: {selector}")
                        except Exception as e:
                            log.debug(f"❌ Double click falló con {selector}: {e}")

                    # Estrategia C: Click con coordenadas específicas
                    if not click_success:
                        try:
                            conversations.first.click(position={"x": 50, "y": 30}, timeout=3000)
                            click_success = True
                            log.debug(f"✅ Click con coordenadas exitoso con: {selector}")
                        except Exception as e:
                            log.debug(f"❌ Click con coordenadas falló con {selector}: {e}")

                    if click_success:
                        page.wait_for_timeout(2000)  # Esperar más tiempo

                        # Verificar si se abrió el chat con múltiples indicadores
                        chat_opened = False
                        chat_indicators = [
                            # Input de mensaje
                            "div[data-testid='conversation-compose-box-input']",
                            "footer div[contenteditable='true'][data-tab='10']",
                            "div[data-tab='10'][contenteditable='true']",
                            "footer div[role='textbox']",
                            "div[contenteditable='true'][role='textbox']",
                            # Header del chat
                            "header[data-testid='conversation-header']",
                            "div[data-testid='conversation-header']",
                            # Área de mensajes
                            "div[data-testid='conversation-panel-messages']",
                            "div[role='application'][data-tab='6']",
                            # Otros indicadores
                            "div[data-testid='conversation-panel-wrapper']",
                            "footer[data-testid='compose-box']",
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
                            # Enviar mensaje
                            message_sent = send_reply_with_typing(page, chat_id, message_text, per_char_delay)

                            if message_sent:
                                log.info(f"✅ Mensaje manual enviado exitosamente a {chat_id}")
                                # PASO ADICIONAL: Limpiar búsqueda y volver a ventana normal
                                cleanup_search_and_return_to_normal(page)
                                return True
                            log.error(f"❌ Error enviando mensaje en chat abierto con {selector}")
                            return False
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


def exit_chat_safely(page) -> None:
    """Sale del chat actual y vuelve a la lista principal."""
    try:
        # ESC para salir
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        log.debug("ESC presionado")

        # Status -> Chats
        try:
            page.click("span[data-icon='status-outline']", timeout=3000)
            page.wait_for_timeout(400)
            page.click("span[data-icon='chats-outline']", timeout=3000)
            log.debug("Navegación Status -> Chats")
        except Exception as e:
            log.debug(f"Error in navigation Status -> Chats: {e}")
            # Fallback: click en el sidebar
            page.click("#pane-side", timeout=3000)

        # Verificar que no hay compositor activo
        composers = page.locator("footer div[contenteditable='true'][data-tab]")
        if composers.count() > 0:
            page.keyboard.press("Escape")
            log.debug("ESC adicional tras detectar compositor")

    except Exception as e:
        log.warning(f"Error saliendo del chat: {e}")


def process_manual_queue(page) -> bool:
    """Procesa mensajes pendientes desde cola DB. Retorna True si se procesó algún mensaje."""
    try:
        pending_messages = queue_manager.get_pending_messages(limit=1, include_scheduled=True)
        if not pending_messages:
            return False

        # Procesar el primer mensaje pendiente
        message = pending_messages[0]
        chat_id = message["chat_id"]
        content = message["message"]
        queue_id = message.get("message_id")

        log.info(f"📤 Procesando mensaje manual para {chat_id}: {content[:50]}...")

        # Enviar el mensaje
        try:
            per_char = float(os.getenv("TYPING_PER_CHAR", "0.05"))
        except Exception:
            per_char = 0.05

        # Usar la nueva función que incluye navegación al chat
        success = send_manual_message(page, chat_id, content, per_char_delay=per_char)

        if queue_id:
            if success:
                queue_manager.mark_as_sent(queue_id)
                log.info(f"✅ Mensaje en cola enviado a {chat_id}")
            else:
                queue_manager.mark_as_failed(queue_id, "send_manual_message_failed")
                log.error(f"❌ Mensaje en cola falló para {chat_id} - marcado como failed/retry")

        return success

    except Exception as e:
        log.error(f"❌ Error procesando cola manual: {e}")
        return False


def _prepare_runtime() -> tuple[dict[str, Any], str, bool, int, int, int]:
    load_dotenv(override=True)
    log_path = os.getenv("LOG_PATH")
    if log_path:
        setup_logging(log_path)
    log.debug("Variables de entorno cargadas")

    cfg = load_config()
    cfg["messageCheckInterval"] = int(cfg.get("messageCheckInterval", LOOP_SLEEP_INTERVAL))
    cfg["maxRetries"] = int(cfg.get("maxRetries", 3))
    cfg["navigationTimeout"] = int(cfg.get("navigationTimeout", NAVIGATION_TIMEOUT_MS))

    chat_sessions.initialize_db()
    log.info("Base de datos de contexto inicializada")

    profile_dir = cfg["userDataDir"]
    try:
        if os.path.exists(profile_dir) and os.path.isfile(profile_dir):
            os.remove(profile_dir)
        os.makedirs(profile_dir, exist_ok=True)
    except (OSError, FileExistsError) as e:
        log.debug(f"Error creando directorio de perfil: {e}")
        if not os.path.isdir(profile_dir):
            import tempfile

            profile_dir = tempfile.mkdtemp(prefix="whatsapp_profile_")
            log.warning(f"Usando directorio temporal: {profile_dir}")

    keep_open = os.getenv("KEEP_AUTOMATOR_OPEN", "false").lower() == "true"
    llm_workers = max(1, int(os.getenv("AUTOMATOR_LLM_WORKERS", "2") or "2"))
    reasoner_timeout = max(5, int(os.getenv("AUTOMATOR_REASONER_TIMEOUT", "90") or "90"))
    llm_timeout = max(5, int(os.getenv("AUTOMATOR_LLM_TIMEOUT", "60") or "60"))

    return cfg, profile_dir, keep_open, llm_workers, reasoner_timeout, llm_timeout


def _setup_browser(playwright_instance, cfg: dict[str, Any], profile_dir: str):
    ctx = playwright_instance.chromium.launch_persistent_context(user_data_dir=profile_dir, headless=cfg["headless"])
    log.info(f"Browser iniciado. Headless={cfg['headless']}")
    page = ctx.new_page()
    return ctx, page


def _navigate_to_whatsapp(page, cfg: dict[str, Any], keep_open: bool, ctx) -> bool:
    try:
        page.goto(cfg["whatsappUrl"], timeout=cfg["navigationTimeout"])
        log.info(f"Navegando a {cfg['whatsappUrl']}")
        log.info("Esperando que cargue WhatsApp Web...")
        page.wait_for_selector("#pane-side", timeout=PAGE_LOAD_TIMEOUT_MS)
        log.info("WhatsApp Web cargado correctamente")
        page.wait_for_selector("#pane-side", timeout=15000)
        log.info("Panel de chats cargado, entrando al loop principal")
        return True
    except Exception:
        log.exception("Error al cargar WhatsApp Web", exc_info=True)
        if not keep_open:
            with contextlib.suppress(Exception):
                ctx.close()
        return False


def _read_respond_to_all_flag() -> bool:
    respond_to_all = False
    try:
        settings_file = os.path.join(os.path.dirname(__file__), "data", "settings.json")
        if os.path.exists(settings_file):
            with open(settings_file, encoding="utf-8") as f:
                settings = json.load(f)
                respond_to_all = settings.get("respond_to_all", False)
    except Exception:
        pass
    return respond_to_all


def _resolve_typing_delay() -> float:
    try:
        return float(os.getenv("TYPING_PER_CHAR", str(PER_CHAR_TYPING_DELAY)))
    except Exception:
        return REPLY_DELAY_SECONDS


def _graceful_shutdown(page, ctx, keep_open: bool) -> None:
    if keep_open and not SHUTDOWN_EVENT.is_set():
        return
    with contextlib.suppress(Exception):
        page.close()
    with contextlib.suppress(Exception):
        ctx.close()
    with contextlib.suppress(Exception):
        if getattr(ctx, "browser", None):
            ctx.browser.close()
    log.info("Recursos Playwright cerrados correctamente")


def _process_incoming_messages(page, worker_pool, llm_timeout: int, reasoner_timeout: int) -> bool:
    respond_to_all = _read_respond_to_all_flag()
    chat_id, incoming = fetch_new_message(page, respond_to_all)
    log.debug(f"fetch_new_message retornó: {chat_id}, {incoming}")

    if not chat_id or incoming is None:
        return False

    log.info(f"[{chat_id}] Mensaje entrante: '{incoming}'")
    history = chat_sessions.load_last_context(chat_id)
    history.append({"role": "user", "content": incoming})

    try:
        mm = ModelManager()
        session = get_session()
        msg_count = session.query(Conversation).filter(Conversation.chat_id == chat_id).count()
        session.close()
        chosen_model = mm.choose_model_for_conversation(chat_id, msg_count)
        log.debug(f"[{chat_id}] Modelo elegido: {chosen_model}")
        reply = worker_pool.submit(stub_chat, incoming, chat_id, history).result(timeout=llm_timeout)
        if not reply or not reply.strip():
            log.warning(f"[{chat_id}] No se generó respuesta (posible problema con LM Studio)")
            return True
    except FuturesTimeoutError:
        log.error(f"[{chat_id}] Timeout generando respuesta con modelo")
        return True
    except Exception:
        log.exception("Error generando respuesta con stub_chat")
        return True

    history.append({"role": "assistant", "content": (reply or "")[:MAX_REPLY_LENGTH]})
    chat_sessions.save_context(chat_id, history)

    try:
        send_reply_with_typing(page, chat_id, (reply or "")[:MAX_REPLY_LENGTH], per_char_delay=_resolve_typing_delay())
        exit_chat_safely(page)
        LAST_REPLIED[chat_id] = time.time()
        if len(LAST_REPLIED) > MAX_LAST_REPLIED:
            oldest_chat = min(LAST_REPLIED, key=LAST_REPLIED.get)
            LAST_REPLIED.pop(oldest_chat, None)
    except Exception:
        log.exception("Fallo enviando el mensaje a WhatsApp")

    try:
        n = chat_sessions.increment_reply_counter(chat_id)
        threshold = int(_os.getenv("STRATEGY_REFRESH_EVERY", "10") or "10")
        if n >= threshold:
            chat_sessions.reset_reply_counter(chat_id)
            from reasoner import update_chat_context_and_profile

            reasoner_future = worker_pool.submit(update_chat_context_and_profile, chat_id)
            try:
                res = reasoner_future.result(timeout=reasoner_timeout) or {}
                log.info(
                    f"[{chat_id}] Razonador ejecutado. Estrategia v{res.get('version')} | contexto={res.get('wrote_contexto')} perfil={res.get('wrote_perfil')}"
                )
            except FuturesTimeoutError:
                log.warning(f"[{chat_id}] Razonador en background excedió timeout")
    except Exception:
        log.exception("Error actualizando contadores/razonador")

    exit_chat_safely(page)
    return True


def main() -> None:
    cfg, profile_dir, keep_open, llm_workers, reasoner_timeout, llm_timeout = _prepare_runtime()
    with contextlib.suppress(Exception):
        signal.signal(signal.SIGTERM, _request_shutdown)
    with contextlib.suppress(Exception):
        signal.signal(signal.SIGINT, _request_shutdown)

    with ThreadPoolExecutor(max_workers=llm_workers) as worker_pool, sync_playwright() as p:
        ctx, page = _setup_browser(p, cfg, profile_dir)
        if not _navigate_to_whatsapp(page, cfg, keep_open, ctx):
            return

        try:
            while True:
                if SHUTDOWN_EVENT.is_set():
                    log.info("Shutdown solicitado. Saliendo del loop principal...")
                    break

                load_dotenv(override=True)
                toggle = os.getenv("AUTOMATION_ACTIVE", "true").lower()
                if toggle != "true":
                    log.info("Automatización desactivada, durmiendo…")
                    time.sleep(cfg["messageCheckInterval"])
                    continue

                handled_incoming = _process_incoming_messages(page, worker_pool, llm_timeout, reasoner_timeout)
                if not handled_incoming:
                    manual_processed = process_manual_queue(page)
                    if not manual_processed:
                        time.sleep(cfg["messageCheckInterval"])
                    continue

                time.sleep(cfg["messageCheckInterval"])
        except KeyboardInterrupt:
            log.info("Interrupción manual recibida, cerrando…")
        except Exception:
            log.exception("Excepción no controlada en el loop principal", exc_info=True)
        finally:
            _graceful_shutdown(page, ctx, keep_open)


if __name__ == "__main__":
    main()
