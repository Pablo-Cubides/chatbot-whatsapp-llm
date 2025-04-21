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


def fetch_new_message(page):
    log.debug("→ Entrando a fetch_new_message()")
    try:
        page.wait_for_selector("#pane-side div[role='grid']", timeout=5000)
        grid = page.locator("#pane-side div[role='grid']")
        rows = grid.locator("div[role='listitem'], div[role='row']")
        count = rows.count()
        log.debug(f"– Rows totales en el grid: {count}")
        for i in range(count):
            row = rows.nth(i)
            badge = row.locator(
                "span[aria-label*='mensaje no leído'],"
                "span[aria-label*='mensajes no leídos'],"
                "span[aria-label*='unread message'],"
                "span[aria-label*='unread messages']"
            )
            if badge.count() == 0:
                continue
            log.info(f"– Row #{i} tiene badge")
            chat_span = row.locator("span[title]").first
            if chat_span.count() == 0:
                log.error("– No encontré <span title> para extraer chat_id")
                continue
            chat_id = chat_span.get_attribute("title")
            log.info(f"– chat_id extraído: {chat_id!r}")
            row.click()
            log.info("– Click en la conversación")
            page.wait_for_selector("div[contenteditable='true'][data-tab='10']", timeout=10000)
            bubbles = page.locator("div.message-in span.selectable-text")
            total = bubbles.count()
            incoming = bubbles.nth(total-1).inner_text().strip() if total else ""
            log.info(f"– Incoming message: {incoming!r}")
            return chat_id, incoming
        return None, None
    except Exception:
        log.error("¡Exception en fetch_new_message()!", exc_info=True)
        return None, None


def send_reply(page, chat_id, reply_text):
    """
    Envía 'reply_text' en el chat actual (no cierra el hilo).
    """
    input_box = page.locator("div[contenteditable='true'][data-tab='10']")
    input_box.wait_for(state="visible", timeout=10000)
    input_box.fill(reply_text)
    input_box.press("Enter")
    log.info(f"Mensaje enviado a {chat_id}")


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

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir, headless=cfg["headless"]
        )
        log.info(f"Browser iniciado. Headless={cfg['headless']}")
        page = ctx.new_page()
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
            return

        try:
            page.wait_for_selector("#pane-side", timeout=15000)
            log.info("Panel de chats cargado, entrando al loop principal")
        except TimeoutError:
            log.error("Timeout cargando panel de chats", exc_info=True)
            ctx.close()
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

                chat_id, incoming = fetch_new_message(page)
                log.debug(f"fetch_new_message retornó: {chat_id}, {incoming}")
                if not chat_id or incoming is None:
                    log.debug("No hay nuevos mensajes, durmiendo…")
                    time.sleep(cfg["messageCheckInterval"])
                    continue

                log.info(f"[{chat_id}] Mensaje entrante: '{incoming}'")
                history = chat_sessions.load_last_context(chat_id)
                log.debug(f"[{chat_id}] Contexto antes: {history}")
                history.append({"role": "user", "content": incoming})
                try:
                    reply = stub_chat.chat(incoming, chat_id, history)
                    log.info(f"[{chat_id}] reply generado: '{reply}'")
                except Exception:
                    log.exception("Error generando respuesta con stub_chat")
                    reply = "Lo siento, ocurrió un error al procesar tu mensaje."
                history.append({"role": "assistant", "content": reply})
                chat_sessions.save_context(chat_id, history)
                log.info(f"[{chat_id}] Historial actualizado y guardado ({len(history)} turnos)")

                # Enviar respuesta y deseleccionar hilo
                send_reply(page, chat_id, reply)
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
        finally:
            ctx.close()
            log.info("Contexto del navegador cerrado, fin del programa")

if __name__ == "__main__":
    main()
