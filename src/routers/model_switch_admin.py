"""Model selection admin routes extracted from admin_panel."""

import importlib
import json
import os
from typing import Any

import stub_chat
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.services.auth_system import get_current_user, require_admin

router = APIRouter(tags=["model-switch-admin"])


class ReasonerModelChangeRequest(BaseModel):
    model: str


class ModelChangeRequest(BaseModel):
    model: str


@router.get("/api/reasoner-model")
def api_get_reasoner_model(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Get current reasoner model from payload_reasoner.json."""
    try:
        payload_path = os.path.join(os.path.dirname(__file__), "..", "..", "payload_reasoner.json")
        payload_path = os.path.abspath(payload_path)
        with open(payload_path, encoding="utf-8") as f:
            payload = json.load(f)
        return {"reasoner_model": payload.get("model", "unknown")}
    except Exception as e:
        return {"error": str(e), "reasoner_model": "unknown"}


@router.put("/api/reasoner-model")
def api_set_reasoner_model(
    request: ReasonerModelChangeRequest, current_user: dict[str, Any] = Depends(require_admin)
) -> dict[str, Any]:
    """Update reasoner model in payload_reasoner.json."""
    try:
        payload_path = os.path.join(os.path.dirname(__file__), "..", "..", "payload_reasoner.json")
        payload_path = os.path.abspath(payload_path)
        with open(payload_path, encoding="utf-8") as f:
            payload = json.load(f)
        payload["model"] = request.model
        with open(payload_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4, ensure_ascii=False)
        return {"success": True, "reasoner_model": request.model}
    except Exception as e:
        return {"error": str(e), "success": False}


@router.get("/api/current-model")
def api_get_current_model(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Get current model from payload.json."""
    try:
        payload_path = os.path.join(os.path.dirname(__file__), "..", "..", "payload.json")
        payload_path = os.path.abspath(payload_path)
        with open(payload_path, encoding="utf-8") as f:
            payload = json.load(f)
        return {"current_model": payload.get("model", "unknown")}
    except Exception as e:
        return {"error": str(e), "current_model": "unknown"}


@router.put("/api/current-model")
def api_set_current_model(request: ModelChangeRequest, current_user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    """Update current model in payload.json."""
    try:
        payload_path = os.path.join(os.path.dirname(__file__), "..", "..", "payload.json")
        payload_path = os.path.abspath(payload_path)

        with open(payload_path, encoding="utf-8") as f:
            payload = json.load(f)

        payload["model"] = request.model

        with open(payload_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4, ensure_ascii=False)

        importlib.reload(stub_chat)

        return {"success": True, "new_model": request.model}
    except Exception as e:
        return {"error": str(e), "success": False}
