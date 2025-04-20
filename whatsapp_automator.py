"""
whatsapp_automator.py
=====================

Automatiza la lectura y respuesta de mensajes en WhatsApp Web mediante Playwright,
**con manejo de contexto persistente** a través de chat_sessions.py.

• Carga variables de entorno desde .env.
• Usa un perfil persistente de Chromium para evitar re‑loguear el QR.
• Registra eventos en logs/automation.log con rotación y enmascara números.
• Integra chat_sessions.py:   – carga historial antes de responder
                              – guarda historial luego de responder
• Se controla en caliente mediante la variable AUTOMATION_ACTIVE=true/false.
"""

# ---------- Imports estándar ----------
import os
import json
import time
import logging
import logging.handlers
from string import Template

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError

# ---------- Módulos propios ----------
import chat_sessions              # → persistencia SQLite
import stub_chat                  # → generación de respuestas (placeholder)
# -------------------------------------

# --------------------------------------------------------------------------- #
# 1. Utilidades de configuración y logging
# --------------------------------------------------------------------------- #
def load_config() -> dict:
    """
    Lee el archivo config/playwright_config.jsonc y reemplaza las variables
    estilo ${VAR} por los valores que existan en el entorno (.env incluido).
    """
    here = os.path.dirname(__file__)
    fp = os.path.join(here, "config", "playwright_config.json")
    with open(fp, encoding="utf-8") as f:
        raw = f.read()

    filled = Template(raw).substitute(os.environ)   # ${VAR} → valor
    return json.loads(filled)                       # devuelve dict


def setup_logging(log_path: str) -> None:
    """
    Configura un logger con rotación y filtro para ocultar números telefónicos.
    Log final = logs/automation.log (ruta viene de .env)
    """
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    # Rotación: 5 MB × 3 archivos
    handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )

    # Filtro → anonimizar números de teléfono
    class MaskFilter(logging.Filter):
        import re
        regex = re.compile(r'\+?\d[\d\s\-]{7,}\d')
        def filter(self, record):
            record.msg = self.regex.sub('[número oculto]', record.getMessage())
            return True
    handler.addFilter(MaskFilter())

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s][%(levelname)s] %(funcName)s – %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[handler]
    )
    logging.info("=== WhatsApp Automator iniciado ===")


# --------------------------------------------------------------------------- #
# 2. Helpers Playwright – leer y enviar mensajes
# --------------------------------------------------------------------------- #
def fetch_new_message(page):
    """
    Devuelve (chat_id, texto) si existe un chat con mensajes no leídos.
    Si no hay mensajes pendientes, retorna (None, None).

    • Selector de badge 'unread' puede variar en futuras versiones de WhatsApp Web.
    • chat_id se extrae de atributo 'data-id' que añade WhatsApp internamente.
    """
    unread_badge = page.query_selector('span[aria-label*="unread message"]')
    if not unread_badge:
        return None, None

    # Subir al contenedor de la fila de chat
    chat_row = unread_badge.evaluate_handle("e => e.closest('div[role=row]')")
    chat_id = chat_row.get_attribute("data-id")
    chat_row.click()

    # Espera a que cargue el hilo y localiza el último bubble entrante
    page.wait_for_selector('div[role="textbox"]', timeout=15_000)
    bubbles = page.query_selector_all('div.message-in div.selectable-text.copyable-text')
    if not bubbles:
        return None, None
    incoming_text = bubbles[-1].inner_text().strip()

    return chat_id, incoming_text


def send_message(page, chat_id: str, text: str) -> None:
    """
    Escribe y envía 'text' en el chat actualmente abierto.
    Se asume que el chat correcto YA está seleccionado (lo hace fetch_new_message).
    """
    box = page.query_selector('div[contenteditable="true"][data-tab="10"]')
    if not box:
        logging.error(f"Input box no encontrado para {chat_id}")
        return
    box.fill(text)
    box.press("Enter")


# --------------------------------------------------------------------------- #
# 3. Función principal
# --------------------------------------------------------------------------- #
def main() -> None:
    # 3.1 Cargar variables de entorno (.env) y config JSONC
    load_dotenv(override=True)              # refresca en cada inicio
    cfg = load_config()                     # dict con claves de playwright_config
    cfg["messageCheckInterval"] = int(cfg["messageCheckInterval"])

    # 3.2 Logging + inicializar base SQLite
    setup_logging(os.getenv("LOG_PATH"))
    chat_sessions.initialize_db()

    # 3.3 Asegurar directorio de perfil Chromium
    profile_dir = cfg["userDataDir"]
    os.makedirs(profile_dir, exist_ok=True)

    # 3.4 Lanzar Playwright en modo persistente
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=cfg["headless"]
        )
        page = ctx.new_page()

                # 3.4.1 Abrir WhatsApp Web
        try:
            page.goto(cfg["whatsappUrl"], timeout=cfg["navigationTimeout"])

            # ——— Intento de login por QR ———
            try:
                page.wait_for_selector('canvas[aria-label="Scan me!"]', timeout=10_000)
                logging.info("Escanea el QR y presiona Ctrl+C si tardas demasiado.")
                
                # Espera indefinida al grid de chats
                page.wait_for_selector('div[role="grid"]')
            except Exception as e:
                logging.info(f"No se detectó QR o grid: {e}")

        except Exception as e:
            logging.exception(f"Error cargando WhatsApp Web: {e}")
            return

        logging.info("WhatsApp Web listo, comenzando loop…")

        # ------------------------------------------------------------------- #
        # 3.5 Bucle principal
        # ------------------------------------------------------------------- #
        try:
            while True:
                # Permite pausar en caliente con .env
                load_dotenv(override=True)
                if os.getenv("AUTOMATION_ACTIVE", "true").lower() != "true":
                    time.sleep(cfg["messageCheckInterval"])
                    continue

                # a) Buscar mensaje nuevo
                chat_id, incoming = fetch_new_message(page)
                if not chat_id:
                    time.sleep(cfg["messageCheckInterval"])
                    continue

                logging.info(f"[{chat_id}] Mensaje entrante: {incoming}")

                # b) Recuperar historial persistente
                history = chat_sessions.load_last_context(chat_id)
                logging.info(f"[{chat_id}] Historial recuperado: {len(history)} turnos")

                # c) Añadir turno del usuario
                history.append({"role": "user", "content": incoming})

                # d) Generar respuesta usando stub_chat (o API real)
                reply = stub_chat.chat(incoming, chat_id, history)

                # e) Añadir turno del asistente
                history.append({"role": "assistant", "content": reply})

                # f) Guardar historial actualizado
                chat_sessions.save_context(chat_id, history)
                logging.info(f"[{chat_id}] Historial guardado: {len(history)} turnos")

                # g) Enviar la respuesta
                send_message(page, chat_id, reply)

                # h) Espera antes de la siguiente iteración
                time.sleep(cfg["messageCheckInterval"])

        except KeyboardInterrupt:
            logging.info("Interrupción manual recibida, saliendo…")
        finally:
            ctx.close()
            logging.info("Contexto de navegador cerrado.")

# --------------------------------------------------------------------------- #
# 4. Entry‑point
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    main()
    # → main() se ejecuta al correr el script directamente
    # → si se importa como módulo, no se ejecuta nada   
