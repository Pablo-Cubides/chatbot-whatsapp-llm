# whatsapp_automator.py - Versión simplificada y robusta

import json
import logging
import logging.handlers
import os
import time
from string import Template
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import chat_sessions
from stub_chat import chat as stub_chat
from admin_db import get_session
from models import Conversation
from model_manager import ModelManager
import os as _os

# --------------------------------------------
# Definición de logger
# --------------------------------------------
log = logging.getLogger(__name__)

def load_config() -> dict:
    here = os.path.dirname(__file__)
    fp = os.path.join(here, "config", "playwright_config.json")
    raw = open(fp, encoding="utf-8").read()
    filled = Template(raw).substitute(os.environ)
    cfg = json.loads(filled)
    log.debug(f"Configuración cargada: {cfg}")
    return cfg

def setup_logging(log_path: str) -> None:
    if not log_path:
        log_path = os.path.join(os.path.dirname(__file__), 'logs', 'automation.log')
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    class MaskFilter(logging.Filter):
        import re
        regex = re.compile(r'\+?\d[\d\s\-]{7,}\d')
        def filter(self, record):
            record.msg = self.regex.sub('[número oculto]', record.getMessage())
            record.args = ()
            return True
    handler.addFilter(MaskFilter())
    logging.basicConfig(
        level=logging.DEBUG,
        format="[%(asctime)s][%(levelname)s] %(funcName)s – %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[handler]
    )
    log.info("=== WhatsApp Automator iniciado ===")

# Registro de últimas respuestas para evitar bucles
LAST_REPLIED = {}

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
                except:
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
                if time.time() - last_time < 120:  # 2 minutos
                    log.info(f"– {chat_id} en cooldown, saltar")
                    continue
            except:
                pass
                
            # PASO 5: Verificar permisos
            try:
                if not respond_to_all:
                    require = os.getenv("REQUIRE_CONTACT_PROFILE", "true").lower() == "true"
                    if require and not chat_sessions.is_ready_to_reply(chat_id):
                        log.info(f"– {chat_id} no habilitado, saltar")
                        continue
            except:
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
                    except:
                        pass
                        
                    if is_bot:
                        log.info(f"– {chat_id} último mensaje del bot, saltar")
                        continue
                        
                    # Extraer texto
                    try:
                        text_elem = last_msg.locator("span.selectable-text").first
                        incoming = text_elem.inner_text().strip() if text_elem.count() > 0 else "[msg]"
                    except:
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
    input_box = _get_message_input(page)
    try:
        input_box.click()
    except Exception:
        pass

    input_box.fill("")
    chunk = ""
    for ch in reply_text:
        chunk += ch
        input_box.fill(chunk)
        page.wait_for_timeout(int(per_char_delay * 1000))
    input_box.press("Enter")
    log.info(f"Mensaje (typing-sim) enviado a {chat_id}")

def exit_chat_safely(page):
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
        except:
            # Fallback: click en el sidebar
            page.click("#pane-side", timeout=3000)
            
        # Verificar que no hay compositor activo
        composers = page.locator("footer div[contenteditable='true'][data-tab]")
        if composers.count() > 0:
            page.keyboard.press("Escape")
            log.debug("ESC adicional tras detectar compositor")
            
    except Exception as e:
        log.warning(f"Error saliendo del chat: {e}")

def main() -> None:
    load_dotenv(override=True)
    setup_logging(os.getenv("LOG_PATH"))
    log.debug("Variables de entorno cargadas")

    cfg = load_config()
    cfg["messageCheckInterval"] = int(cfg.get("messageCheckInterval", 2))
    cfg["maxRetries"] = int(cfg.get("maxRetries", 3))
    cfg["navigationTimeout"] = int(cfg.get("navigationTimeout", 30000))

    chat_sessions.initialize_db()
    log.info("Base de datos de contexto inicializada")

    profile_dir = cfg["userDataDir"]
    os.makedirs(profile_dir, exist_ok=True)
    log.debug(f"Perfil de Chromium: {profile_dir}")

    keep_open = os.getenv("KEEP_AUTOMATOR_OPEN", "false").lower() == "true"

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir, headless=cfg["headless"]
        )
        log.info(f"Browser iniciado. Headless={cfg['headless']}")
        page = ctx.new_page()
        
        try:
            page.goto(cfg["whatsappUrl"], timeout=cfg["navigationTimeout"])
            log.info(f"Navegando a {cfg['whatsappUrl']}")
            # Simplemente esperar a que aparezca el panel de chats
            log.info("Esperando que cargue WhatsApp Web...")
            page.wait_for_selector("#pane-side", timeout=30000)
            log.info("WhatsApp Web cargado correctamente")
            log.info("WhatsApp Web cargado correctamente")
        except Exception:
            log.exception("Error al cargar WhatsApp Web", exc_info=True)
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
                load_dotenv(override=True)
                toggle = os.getenv("AUTOMATION_ACTIVE", "true").lower()
                log.debug(f"Toggle AUTOMATION_ACTIVE={toggle}")
                if toggle != "true":
                    log.info("Automatización desactivada, durmiendo…")
                    time.sleep(cfg["messageCheckInterval"])
                    continue

                # Leer respond_to_all
                respond_to_all = False
                try:
                    settings_file = os.path.join(os.path.dirname(__file__), 'data', 'settings.json')
                    if os.path.exists(settings_file):
                        with open(settings_file, 'r', encoding='utf-8') as f:
                            settings = json.load(f)
                            respond_to_all = settings.get('respond_to_all', False)
                except Exception:
                    pass
                
                chat_id, incoming = fetch_new_message(page, respond_to_all)
                log.debug(f"fetch_new_message retornó: {chat_id}, {incoming}")
                
                if not chat_id or incoming is None:
                    log.debug("No hay nuevos mensajes, durmiendo…")
                    time.sleep(cfg["messageCheckInterval"])
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
                except Exception:
                    log.exception("Error generando respuesta con stub_chat")
                    reply = "Lo siento, ocurrió un error al procesar tu mensaje."
                
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
                    
                    # Marcar tiempo de respuesta
                    LAST_REPLIED[chat_id] = time.time()
                    
                except Exception:
                    log.exception("Fallo enviando el mensaje a WhatsApp")
                
                # Ejecutar reasoner si es necesario
                try:
                    n = chat_sessions.increment_reply_counter(chat_id)
                    threshold = int(_os.getenv('STRATEGY_REFRESH_EVERY', '10') or '10')
                    if n >= threshold:
                        chat_sessions.reset_reply_counter(chat_id)
                        try:
                            from reasoner import run_reasoner_for_chat
                            ver = run_reasoner_for_chat(chat_id)
                            log.info(f"[{chat_id}] Razonador ejecutado. Nueva estrategia versión {ver}")
                        except Exception:
                            log.exception(f"[{chat_id}] Falló el razonador")
                except Exception:
                    log.exception("Error actualizando contadores/razonador")
                
                # Salir del chat de forma segura
                exit_chat_safely(page)

                log.debug(f"Durmiendo {cfg['messageCheckInterval']}s antes del próximo ciclo")
                time.sleep(cfg["messageCheckInterval"])

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
