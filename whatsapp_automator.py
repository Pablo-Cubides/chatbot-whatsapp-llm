"""
whatsapp_automator.py
=====================

Automatiza la lectura y respuesta de mensajes en WhatsApp Web mediante Playwright,
con manejo de contexto persistente a través de chat_sessions.py.

Registra cada paso en logs/automation.log.
"""

import os
import json
import time
import logging
import logging.handlers
from string import Template

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError

import chat_sessions
import stub_chat
from model_manager import ModelManager, simulate_typing_send
from admin_db import get_session
from models import Conversation
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
    # Fallback to default path if not provided
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


def fetch_new_message(page, respond_to_all=False):
    log.debug("→ Entrando a fetch_new_message()")
    log.debug(f"→ respond_to_all = {respond_to_all}")
    try:
        page.wait_for_selector("#pane-side", timeout=5000)
        grid = page.locator("#pane-side")
        rows = grid.locator("div[role='listitem'], div[role='row']")
        count = rows.count()
        log.debug(f"– Rows totales en el grid: {count}")
        for i in range(count):
            row = rows.nth(i)
            
            # Agregar logging detallado para debug
            try:
                row_text = row.inner_text()[:100]  # Primeros 100 chars
                log.debug(f"– Row #{i} contenido: {row_text!r}")
            except Exception:
                log.debug(f"– Row #{i} no se pudo leer contenido")
            
            # Detectar badges de mensajes no leídos con múltiples estrategias
            badge_found = False
            badge_strategies = [
                # Estrategia 1: aria-labels específicos
                "span[aria-label$='mensajes no leídos'], span[aria-label$='mensaje no leído'], span[aria-label$='unread messages'], span[aria-label$='unread message']",
                # Estrategia 2: números en spans (badges típicos)  
                "span:has-text(/^[0-9]+$/)",
                # Estrategia 3: clases conocidas de badges
                "span[data-icon='unread-count'], span.x1rg5ohu",
                # Estrategia 4: búsqueda amplia por colores/estilos de badge
                "span[style*='background-color']:has-text(/^[0-9]+$/)",
                # Estrategia 5: texto en negrita (indicador visual de no leído)
                "[style*='font-weight: 700'], [style*='font-weight:700'], .x1jchvi3"
            ]
            
            for j, strategy in enumerate(badge_strategies):
                badge = row.locator(strategy)
                badge_count = badge.count()
                log.debug(f"– Row #{i} estrategia #{j+1}: encontrados {badge_count} elementos")
                if badge_count > 0:
                    badge_found = True
                    log.info(f"– Row #{i} tiene badge (estrategia #{j+1}: {strategy[:50]}...)")
                    break
            
            if not badge_found:
                # Estrategia final: detectar por posición y contenido sospechoso
                suspect_elements = row.locator("span").all()
                log.debug(f"– Row #{i} revisando {len(suspect_elements)} elementos span para badges numéricos")
                for element in suspect_elements:
                    try:
                        text = element.inner_text().strip()
                        log.debug(f"– Row #{i} span text: {text!r}")
                        if text.isdigit() and int(text) > 0:
                            badge_found = True
                            log.info(f"– Row #{i} tiene badge numérico: {text}")
                            break
                    except Exception:
                        continue
                        
            if not badge_found:
                log.debug(f"– Row #{i} no tiene badges, saltando")
                continue
                
            # Subir al contenedor de la conversación si no lo estamos ya
            try:
                container = row.locator("xpath=ancestor::div[@role='listitem']").first
                if container.count() == 0:
                    container = row.locator("xpath=ancestor::div[@role='row']").first
                if container.count() > 0:
                    row = container
            except Exception:
                pass
                
            # Extraer chat_id con múltiples estrategias
            chat_id = None
            chat_strategies = [
                "span[title]",
                "[data-id] span",
                "span[dir='auto']",
                "div[role='gridcell'] span"
            ]
            
            for strategy in chat_strategies:
                chat_elements = row.locator(strategy)
                if chat_elements.count() > 0:
                    title_attr = chat_elements.first.get_attribute("title")
                    if title_attr and title_attr.strip():
                        chat_id = title_attr.strip()
                        break
                    # Si no hay title, usar el texto interno
                    text_content = chat_elements.first.inner_text().strip()
                    if text_content and len(text_content) > 3:  # Evitar badges numéricos
                        chat_id = text_content
                        break
                        
            if not chat_id:
                log.error("– No se pudo extraer chat_id")
                continue
                
            log.info(f"– chat_id extraído: {chat_id!r}")
            
            # Gate before opening: check if should respond to all or only allowed contacts
            try:
                if not respond_to_all:
                    # Only respond to allowed contacts
                    require = os.getenv("REQUIRE_CONTACT_PROFILE", "true").lower() == "true"
                    if require and not chat_sessions.is_ready_to_reply(chat_id):
                        log.info(f"– {chat_id!r} no habilitado/perfil listo ⇒ se ignora sin abrir")
                        continue
                else:
                    log.info(f"– respond_to_all=True, respondiendo a {chat_id!r}")
            except Exception:
                log.exception("– Error verificando is_ready_to_reply; por seguridad no abriré")
                continue
            
            try:
                row.click()
                log.info("– Click en la conversación")
            except Exception as e:
                log.error(f"– Error haciendo click en la conversación: {e}")
                continue
                
            # Ensure the message input exists (ignore specific data-tab value que puede cambiar)
            try:
                page.wait_for_selector("div[contenteditable='true'][data-tab]", timeout=10000)
            except Exception:
                try:
                    page.wait_for_selector("div[contenteditable='true']", timeout=5000)
                except Exception as e:
                    log.error(f"– No se encontró caja de entrada: {e}")
                    continue
                    
            # Extraer mensaje entrante con selectores robustos
            message_strategies = [
                "div.message-in span.selectable-text",
                "[data-pre-plain-text] span.selectable-text", 
                "span.selectable-text",
                ".message-in .copyable-text span",
                "[role='row'] span[dir='ltr']"
            ]
            
            incoming = ""
            for strategy in message_strategies:
                bubbles = page.locator(strategy)
                total = bubbles.count()
                if total > 0:
                    incoming = bubbles.nth(total-1).inner_text().strip()
                    if incoming:
                        break
                        
            if not incoming:
                log.warning("– No se pudo extraer mensaje entrante, usando placeholder")
                incoming = "[mensaje detectado pero no leído]"
                
            log.info(f"– Incoming message: {incoming!r}")
            return chat_id, incoming
            
        return None, None
    except Exception:
        log.error("¡Exception en fetch_new_message()!", exc_info=True)
        return None, None

def _get_message_input(page):
    """Devuelve el locator de la caja de texto del compositor de mensajes.
    Prueba varios selectores robustos (WA cambia data-tab y atributos a menudo).
    Lanza excepción si no encuentra ningún candidato visible.
    """
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
                # Si hay múltiples, tomar el último (normalmente el compositor, no la búsqueda)
                target = locator.last
                target.wait_for(state="visible", timeout=3000)
                log.debug(f"Input de mensaje encontrado con selector: {sel}")
                return target
        except Exception:
            continue
    raise RuntimeError("No se encontró la caja de texto del mensaje")


def send_reply(page, chat_id, reply_text):
    """
    Envía 'reply_text' en el chat actual (no cierra el hilo).
    """
    input_box = _get_message_input(page)
    # Asegurar foco en la caja
    try:
        input_box.click()
    except Exception:
        pass
    # Default behaviour: fill and press Enter (fast)
    input_box.fill(reply_text)
    input_box.press("Enter")
    log.info(f"Mensaje enviado a {chat_id}")


def send_reply_with_typing(page, chat_id, reply_text, per_char_delay=0.05):
    """Simula typing enviando caracter por caracter con delay configurable.
    Esto usa la caja de input: inserta texto incrementalmente y presiona Enter al final.
    WARNING: Playwright .type() acepta delay en ms por carácter; pero para mayor control
    realizamos fill incremental.
    """
    input_box = _get_message_input(page)
    try:
        input_box.click()
    except Exception:
        pass

    # Borrar caja y luego ir añadiendo por chunks
    input_box.fill("")
    chunk = ""
    for ch in reply_text:
        chunk += ch
        input_box.fill(chunk)
        # Timeout pequeño para UI; per_char_delay en segundos
        page.wait_for_timeout(int(per_char_delay * 1000))
    input_box.press("Enter")
    log.info(f"Mensaje (typing-sim) enviado a {chat_id}")


def main() -> None:
    load_dotenv(override=True)
    setup_logging(os.getenv("LOG_PATH"))
    log.debug("Variables de entorno cargadas")

    cfg = load_config()
    cfg["messageCheckInterval"] = int(cfg.get("messageCheckInterval", 2))
    cfg["maxRetries"] = int(cfg.get("maxRetries", 3))
    cfg["navigationTimeout"] = int(cfg.get("navigationTimeout", 30000))
    log.debug(f"Parámetros ajustados: INTERVAL={cfg['messageCheckInterval']}, RETRIES={cfg['maxRetries']}, TIMEOUT={cfg['navigationTimeout']}")

    chat_sessions.initialize_db()
    log.info("Base de datos de contexto inicializada")

    profile_dir = cfg["userDataDir"]
    os.makedirs(profile_dir, exist_ok=True)
    log.debug(f"Perfil de Chromium: {profile_dir}")

    # Allow keeping the browser/context open for debugging by setting KEEP_AUTOMATOR_OPEN=true
    keep_open = os.getenv("KEEP_AUTOMATOR_OPEN", "false").lower() == "true"

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir, headless=cfg["headless"]
        )
        log.info(f"Browser iniciado. Headless={cfg['headless']}")
        page = ctx.new_page()
        # Navigate to WhatsApp Web and ensure the chats pane loads. If navigation fails,
        # close the context (unless KEEP_AUTOMATOR_OPEN=true) and exit.
        try:
            page.goto(cfg["whatsappUrl"], timeout=cfg["navigationTimeout"])
            log.info(f"Navegando a {cfg['whatsappUrl']}")
            try:
                page.wait_for_selector("canvas[aria-label='Scan me!']", timeout=10000)
                log.info("QR encontrado, esperando escaneo…")
                page.wait_for_selector("div[role='grid']", timeout=0)
                log.info("Sesión de WhatsApp iniciada tras escanear QR")
            except TimeoutError:
                log.info("Sesión previa ya iniciada, sin escaneo de QR")
        except Exception:
            log.exception("Error al cargar WhatsApp Web", exc_info=True)
            if keep_open:
                log.info("KEEP_AUTOMATOR_OPEN=true — manteniendo navegador abierto para depuración")
            else:
                try:
                    ctx.close()
                except Exception:
                    log.exception("Error cerrando el contexto tras fallo de navegación", exc_info=True)
                return

        try:
            page.wait_for_selector("#pane-side", timeout=15000)
            log.info("Panel de chats cargado, entrando al loop principal")
        except TimeoutError:
            log.error("Timeout cargando panel de chats", exc_info=True)
            try:
                ctx.close()
            except Exception:
                log.exception("Error cerrando el contexto tras timeout", exc_info=True)
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

                # Check scheduled messages file and send any 'now' entries
                try:
                    sched_file = os.path.join(os.path.dirname(__file__), 'data', 'scheduled.json')
                    if os.path.exists(sched_file):
                        with open(sched_file,'r',encoding='utf-8') as f:
                            sched = json.load(f)
                        remaining = []
                        for item in sched:
                            if item.get('when') == 'now':
                                try:
                                    log.info(f"Enviando mensaje programado a {item.get('chat_id')}")
                                    send_reply_with_typing(page, item.get('chat_id'), item.get('message'), per_char_delay=0.03)
                                except Exception:
                                    log.exception("Error enviando mensaje programado")
                            else:
                                remaining.append(item)
                        # overwrite with remaining
                        with open(sched_file,'w',encoding='utf-8') as f:
                            json.dump(remaining,f,ensure_ascii=False,indent=2)
                except Exception:
                    log.exception('Error procesando scheduled.json')

                # Leer respond_to_all una sola vez para todo el ciclo
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
                # Si llegamos aquí, fetch_new_message ya validó respond_to_all y contactos permitidos
                history = chat_sessions.load_last_context(chat_id)
                log.debug(f"[{chat_id}] Contexto antes: {history}")
                history.append({"role": "user", "content": incoming})
                try:
                    # Determine which model to use based on rules and message count
                    mm = ModelManager()
                    # Obtain a message count from DB: count of rows for this chat
                    session = get_session()
                    msg_count = session.query(Conversation).filter(Conversation.chat_id == chat_id).count()
                    session.close()
                    chosen_model = mm.choose_model_for_conversation(chat_id, msg_count)
                    log.debug(f"[{chat_id}] Modelo elegido: {chosen_model}")
                    # Optionally, pass chosen_model into stub_chat or ModelManager later
                    reply = stub_chat.chat(incoming, chat_id, history)
                    log.info(f"[{chat_id}] reply generado: '{reply}'")
                except Exception:
                    log.exception("Error generando respuesta con stub_chat")
                    reply = "Lo siento, ocurrió un error al procesar tu mensaje."
                history.append({"role": "assistant", "content": reply})
                chat_sessions.save_context(chat_id, history)
                log.info(f"[{chat_id}] Historial actualizado y guardado ({len(history)} turnos)")

                # Si llegamos aquí, ya se validó respond_to_all en fetch_new_message
                # Leer configuración de typing desde env o cfg
                try:
                    per_char = float(os.getenv("TYPING_PER_CHAR", "0.05"))
                except Exception:
                    per_char = 0.05
                
                if per_char >= 1.0:
                    log.warning("TYPING_PER_CHAR configurado a >=1s; esto provocará latencias muy altas")
                
                try:
                    if not reply:
                        reply = ""
                    send_reply_with_typing(page, chat_id, reply, per_char_delay=per_char)
                except Exception:
                    log.exception("Fallo enviando el mensaje a WhatsApp")
                
                # After sending, increment and possibly trigger reasoner
                try:
                    n = chat_sessions.increment_reply_counter(chat_id)
                    try:
                        threshold = int(_os.getenv('STRATEGY_REFRESH_EVERY', '10') or '10')
                    except Exception:
                        threshold = 10
                    if n >= threshold:
                        chat_sessions.reset_reply_counter(chat_id)
                        try:
                            from reasoner import run_reasoner_for_chat
                            ver = run_reasoner_for_chat(chat_id)
                            log.info(f"[{chat_id}] Razonador ejecutado. Nueva estrategia versión {ver}")
                        except Exception:
                            log.exception(f"[{chat_id}] Falló el razonador; se mantiene estrategia anterior")
                except Exception:
                    log.exception("Error actualizando contadores/razonador")
                
                try:
                    page.click("span[data-icon='status-outline']", timeout=5000)
                    page.wait_for_timeout(500)
                    page.click("span[data-icon='chats-outline']", timeout=5000)
                    log.debug("Vista restablecida a chats")
                except Exception as e:
                    log.warning(f"No pude navegar Status→Chats: {e}")

                log.debug(f"Durmiendo {cfg['messageCheckInterval']}s antes del próximo ciclo")
                time.sleep(cfg["messageCheckInterval"])

        except KeyboardInterrupt:
            log.info("Interrupción manual recibida, cerrando…")
        except Exception:
            log.exception("Excepción no controlada en el loop principal", exc_info=True)
            if keep_open:
                log.info("KEEP_AUTOMATOR_OPEN=true — manteniendo navegador/contexto abierto para depuración")
                try:
                    # Allow the user to inspect the opened browser/profile; block until Enter pressed
                    input("Presiona Enter para cerrar el automator y el navegador...\n")
                except Exception:
                    pass
            else:
                log.info("Cerrando contexto del navegador tras excepción")
        finally:
            if not keep_open:
                try:
                    ctx.close()
                except Exception:
                    log.exception("Error cerrando el contexto del navegador", exc_info=True)
                log.info("Contexto del navegador cerrado, fin del programa")
            else:
                log.info("KEEP_AUTOMATOR_OPEN activo: el contexto del navegador permanece abierto (no se cerrará desde el script)")

if __name__ == "__main__":
    main()
