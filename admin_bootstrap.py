import json
import os
import sys
import time
from typing import Any, Dict

import requests

BASE = os.environ.get("ADMIN_BASE", "http://127.0.0.1:8001")
LM_PORT = int(os.environ.get("LM_STUDIO_PORT", "1234"))


def post(path: str, json_body: Dict[str, Any] | None = None) -> Dict[str, Any]:
    url = f"{BASE}{path}"
    try:
        r = requests.post(url, json=json_body, timeout=60)
        try:
            data = r.json()
        except Exception:
            data = {"raw": r.text}
        return {"status_code": r.status_code, "data": data}
    except Exception as e:
        return {"error": str(e)}


def get(path: str) -> Dict[str, Any]:
    url = f"{BASE}{path}"
    try:
        r = requests.get(url, timeout=30)
        try:
            data = r.json()
        except Exception:
            data = {"raw": r.text}
        return {"status_code": r.status_code, "data": data}
    except Exception as e:
        return {"error": str(e)}


def main():
    print("== Admin health ==")
    print(get("/healthz"))

    # Load desired model from payload.json
    payload_path = os.path.join(os.path.dirname(__file__), "payload.json")
    try:
        with open(payload_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        model = payload.get("model") or "phi-4-Q4_K_M"
    except Exception:
        model = "phi-4-Q4_K_M"
    print(f"Model to load: {model}")

    print("== Start LM Studio server ==")
    print(post("/api/lmstudio/server/start"))

    print("== Load model ==")
    print(post("/api/lmstudio/load", {"model": model}))
    
    print("== Load embeddings model ==")
    embeddings_model = "text-embedding-nomic-embed-text-v1.5"
    print(f"Loading embeddings model: {embeddings_model}")
    print(post("/api/lmstudio/load", {"model": embeddings_model}))

    print("== Warmup ==")
    print(post("/api/lmstudio/warmup", {"model": model}))

    print("== Start WhatsApp automator ==")
    print(post("/api/whatsapp/start"))

    print("== WhatsApp status ==")
    print(get("/api/whatsapp/status"))

    print("== LM Studio models (HTTP) ==")
    try:
        r = requests.get(f"http://127.0.0.1:{LM_PORT}/v1/models", timeout=10)
        print({"status_code": r.status_code, "body": r.text[-1000:]})
    except Exception as e:
        print({"error": str(e)})


if __name__ == "__main__":
    main()
