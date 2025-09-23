from typing import Any, Dict
import logging
import requests

from settings import settings

BASE = settings.admin_base
LM_PORT = settings.lm_studio_port


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
    _LOG = logging.getLogger(__name__)
    _LOG.info("== Admin health ==")
    _LOG.info(get("/healthz"))

    # Load desired model from settings
    model = settings.payload.model
    _LOG.info(f"Model to load: {model}")

    _LOG.info("== Start LM Studio server ==")
    _LOG.info(post("/api/lmstudio/server/start"))

    _LOG.info("== Load model ==")
    _LOG.info(post("/api/lmstudio/load", {"model": model}))
    
    _LOG.info("== Load embeddings model ==")
    embeddings_model = "text-embedding-nomic-embed-text-v1.5"
    _LOG.info(f"Loading embeddings model: {embeddings_model}")
    _LOG.info(post("/api/lmstudio/load", {"model": embeddings_model}))

    _LOG.info("== Warmup ==")
    _LOG.info(post("/api/lmstudio/warmup", {"model": model}))

    _LOG.info("== Start WhatsApp automator ==")
    _LOG.info(post("/api/whatsapp/start"))

    _LOG.info("== WhatsApp status ==")
    _LOG.info(get("/api/whatsapp/status"))

    _LOG.info("== LM Studio models (HTTP) ==")
    try:
        r = requests.get(f"http://127.0.0.1:{LM_PORT}/v1/models", timeout=10)
        _LOG.info({"status_code": r.status_code, "body": r.text[-1000:]})
    except Exception as e:
        _LOG.error({"error": str(e)})


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
