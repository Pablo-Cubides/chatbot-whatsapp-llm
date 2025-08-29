#!/usr/bin/env python3
"""
Demo script to populate admin panel with sample data and test functionality.
"""

import requests
import json
import os

# Get port from environment or use default
UVICORN_PORT = os.getenv("UVICORN_PORT", "8002")
BASE_URL = f"http://127.0.0.1:{UVICORN_PORT}"
AUTH_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": "Bearer admintoken"
}

def test_auth():
    return {"username": "admin", "token": "admintoken"}

def demo_create_model():
    print("📝 Creating sample LLM model...")
    response = requests.post(
        f"{BASE_URL}/models",
        headers=AUTH_HEADERS,
        json={
            "name": "gpt-4-reasoning",
            "provider": "openai",
            "config": {"temperature": 0.3, "max_tokens": 2000},
            "active": True
        }
    )
    try:
        print(f"✅ Model created: {response.json()}")
    except ValueError:
        print(f"⚠️ Unexpected response creating model (status {response.status_code}): {response.text}")

def demo_create_rule():
    print("📝 Creating routing rule...")
    response = requests.post(
        f"{BASE_URL}/rules",
        headers=AUTH_HEADERS,
        json={
            "name": "Every 5 messages use reasoning model",
            "every_n_messages": 5,
            "model_id": 1,
            "enabled": True
        }
    )
    try:
        print(f"✅ Rule created: {response.json()}")
    except ValueError:
        print(f"⚠️ Unexpected response creating rule (status {response.status_code}): {response.text}")

def demo_add_contact():
    print("📝 Adding allowed contact...")
    response = requests.post(
        f"{BASE_URL}/contacts",
        headers=AUTH_HEADERS,
        json={
            "contact_id": "+57 310 7601252",
            "label": "Usuario de prueba"
        }
    )
    try:
        print(f"✅ Contact added: {response.json()}")
    except ValueError:
        print(f"⚠️ Unexpected response adding contact (status {response.status_code}): {response.text}")

def demo_add_daily_context():
    print("📝 Adding daily context...")
    response = requests.post(
        f"{BASE_URL}/daily-contexts",
        headers=AUTH_HEADERS,
        json={
            "text": "Hoy es lunes. El usuario principal está trabajando en el proyecto de chatbot. Responde de manera amigable y profesional."
        }
    )
    try:
        print(f"✅ Daily context added: {response.json()}")
    except ValueError:
        print(f"⚠️ Unexpected response adding daily context (status {response.status_code}): {response.text}")

def demo_add_user_context():
    print("📝 Adding user-specific context...")
    response = requests.post(
        f"{BASE_URL}/user-contexts",
        headers=AUTH_HEADERS,
        json={
            "user_id": "+57 310 7601252",
            "text": "Usuario con mucho interés en tecnología. Le gusta hablar de desarrollo de software y automatización.",
            "source": "manual_admin"
        }
    )
    try:
        print(f"✅ User context added: {response.json()}")
    except ValueError:
        print(f"⚠️ Unexpected response adding user context (status {response.status_code}): {response.text}")

def demo_list_data():
    print("\n📋 Listing current data...")
    
    # List models
    response = requests.get(f"{BASE_URL}/models", headers=AUTH_HEADERS)
    try:
        print(f"Models: {response.json()}")
    except ValueError:
        print(f"⚠️ Could not decode models response (status {response.status_code}): {response.text}")
    
    # List contacts
    response = requests.get(f"{BASE_URL}/contacts", headers=AUTH_HEADERS)
    try:
        print(f"Contacts: {response.json()}")
    except ValueError:
        print(f"⚠️ Could not decode contacts response (status {response.status_code}): {response.text}")
    
    # List daily contexts
    response = requests.get(f"{BASE_URL}/daily-contexts", headers=AUTH_HEADERS)
    try:
        print(f"Daily contexts: {response.json()}")
    except ValueError:
        print(f"⚠️ Could not decode daily contexts response (status {response.status_code}): {response.text}")


def wait_for_server(timeout: int = 60):
    print(f"Esperando que el admin panel responda en {BASE_URL} (timeout {timeout}s)...")
    import time
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{BASE_URL}/docs", headers={"Content-Type": "text/plain"}, timeout=2)
            if r.status_code == 200:
                print("Server listo.")
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
    print("Timeout esperando el servidor.")
    return False

if __name__ == "__main__":
    print("🚀 Admin Panel Demo")
    print(f"Make sure admin panel is running: uvicorn admin_panel:app --reload --port {UVICORN_PORT}")
    print()
    
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
        
        print("\n✅ Demo completed successfully!")
        print("You can now:")
        print("- Visit http://localhost:8001/docs for Swagger UI")
        print("- Test WhatsApp automation with configured contact")
        print("- Add more contexts through the API")
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to admin panel.")
        print("Make sure it's running: uvicorn admin_panel:app --reload --port 8001")
    except Exception as e:
        print(f"❌ Error: {e}")
