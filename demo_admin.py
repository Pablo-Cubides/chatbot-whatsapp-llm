#!/usr/bin/env python3
"""
Demo script to populate admin panel with sample data and test functionality.
"""

import requests
import json  # noqa: F401
from settings import settings
import logging
_LOG = logging.getLogger(__name__)

# Use centralized settings
UVICORN_PORT = settings.uvicorn_port
BASE_URL = f"http://127.0.0.1:{UVICORN_PORT}"
# AUTH_HEADERS removed as hardcoded tokens are a security risk.
# For demo purposes, assuming endpoints are publicly accessible or authentication is handled externally.

def test_auth():
    return {"username": "admin", "token": "admintoken"}

def demo_create_model():
    _LOG.info("📝 Creating sample LLM model...")
    response = requests.post(
        f"{BASE_URL}/models",
        
        json={
            "name": "gpt-4-reasoning",
            "provider": "openai",
            "config": {"temperature": 0.3, "max_tokens": 2000},
            "active": True
        }
    )
    try:
        _LOG.info("✅ Model created: %s", response.json())
    except ValueError:
        _LOG.warning("⚠️ Unexpected response creating model (status %s): %s", response.status_code, response.text)

def demo_create_rule():
    _LOG.info("📝 Creating routing rule...")
    response = requests.post(
        f"{BASE_URL}/rules",
        
        json={
            "name": "Every 5 messages use reasoning model",
            "every_n_messages": 5,
            "model_id": 1,
            "enabled": True
        }
    )
    try:
        _LOG.info("✅ Rule created: %s", response.json())
    except ValueError:
        _LOG.warning("⚠️ Unexpected response creating rule (status %s): %s", response.status_code, response.text)

def demo_add_contact():
    _LOG.info("📝 Adding allowed contact...")
    response = requests.post(
        f"{BASE_URL}/contacts",
        
        json={
            "contact_id": "+57 310 7601252",
            "label": "Usuario de prueba"
        }
    )
    try:
        _LOG.info("✅ Contact added: %s", response.json())
    except ValueError:
        _LOG.warning("⚠️ Unexpected response adding contact (status %s): %s", response.status_code, response.text)

def demo_add_daily_context():
    _LOG.info("📝 Adding daily context...")
    response = requests.post(
        f"{BASE_URL}/daily-contexts",
        
        json={
            "text": "Hoy es lunes. El usuario principal está trabajando en el proyecto de chatbot. Responde de manera amigable y profesional."
        }
    )
    try:
        _LOG.info("✅ Daily context added: %s", response.json())
    except ValueError:
        _LOG.warning("⚠️ Unexpected response adding daily context (status %s): %s", response.status_code, response.text)

def demo_add_user_context():
    _LOG.info("📝 Adding user-specific context...")
    response = requests.post(
        f"{BASE_URL}/user-contexts",
        
        json={
            "user_id": "+57 310 7601252",
            "text": "Usuario con mucho interés en tecnología. Le gusta hablar de desarrollo de software y automatización.",
            "source": "manual_admin"
        }
    )
    try:
        _LOG.info("✅ User context added: %s", response.json())
    except ValueError:
        _LOG.warning("⚠️ Unexpected response adding user context (status %s): %s", response.status_code, response.text)

def demo_list_data():
    _LOG.info("\n📋 Listing current data...")
    
    # List models
    response = requests.get(f"{BASE_URL}/models", )
    try:
        _LOG.info("Models: %s", response.json())
    except ValueError:
        _LOG.warning("⚠️ Could not decode models response (status %s): %s", response.status_code, response.text)
    
    # List contacts
    response = requests.get(f"{BASE_URL}/contacts", )
    try:
        _LOG.info("Contacts: %s", response.json())
    except ValueError:
        _LOG.warning("⚠️ Could not decode contacts response (status %s): %s", response.status_code, response.text)
    
    # List daily contexts
    response = requests.get(f"{BASE_URL}/daily-contexts", )
    try:
        _LOG.info("Daily contexts: %s", response.json())
    except ValueError:
        _LOG.warning("⚠️ Could not decode daily contexts response (status %s): %s", response.status_code, response.text)


def wait_for_server(timeout: int = 60):
    _LOG.info("Esperando que el admin panel responda en %s (timeout %s s)...", BASE_URL, timeout)
    import time
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{BASE_URL}/docs", headers={"Content-Type": "text/plain"}, timeout=2)
            if r.status_code == 200:
                _LOG.info("Server listo.")
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
    _LOG.warning("Timeout esperando el servidor.")
    return False

if __name__ == "__main__":
    _LOG.info("🚀 Admin Panel Demo")
    _LOG.info("Make sure admin panel is running: uvicorn admin_panel:app --reload --port %s", UVICORN_PORT)
    try:
        ok = wait_for_server(timeout=120)
        if not ok:
            raise RuntimeError("El servidor admin no respondió en el timeout; abortando demo.")

        demo_create_model()
        demo_create_rule()
        demo_add_contact()
        demo_add_daily_context()
        demo_add_user_context()
        demo_list_data()

        _LOG.info("\n✅ Demo completed successfully!")
        _LOG.info("You can now:")
        _LOG.info("- Visit http://localhost:%s/docs for Swagger UI", UVICORN_PORT)
        _LOG.info("- Test WhatsApp automation with configured contact")
        _LOG.info("- Add more contexts through the API")

    except requests.exceptions.ConnectionError:
        _LOG.error("❌ Error: Could not connect to admin panel.")
        _LOG.error("Make sure it's running: uvicorn admin_panel:app --reload --port %s", UVICORN_PORT)
    except Exception as e:
        _LOG.exception("❌ Error: %s", e)