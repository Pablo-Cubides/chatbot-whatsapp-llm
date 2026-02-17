"""Legacy non-/api data endpoints extracted from admin_panel."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.models.admin_db import get_session
from src.models.models import Contact, ModelConfig, Rule
from src.services.auth_system import get_current_user

router = APIRouter(tags=["legacy-admin-data"])


class ModelIn(BaseModel):
    name: str
    provider: str
    model_type: Optional[str] = "local"  # 'local' or 'online'
    config: Optional[dict] = None
    active: Optional[bool] = True


class RuleIn(BaseModel):
    name: str
    every_n_messages: int
    model_id: int
    enabled: Optional[bool] = True


class ContactIn(BaseModel):
    contact_id: str
    label: Optional[str]


@router.post("/models", response_model=dict)
def create_model(payload: ModelIn, current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Crea un modelo de configuración legacy si no existe por nombre."""
    session = get_session()
    try:
        existing = session.query(ModelConfig).filter(ModelConfig.name == payload.name).first()
        if existing:
            return {"id": existing.id, "name": existing.name}

        model = ModelConfig(name=payload.name, provider=payload.provider, config=payload.config, active=payload.active)
        session.add(model)
        session.commit()
        session.refresh(model)
        return {"id": model.id, "name": model.name}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create model: {e}")
    finally:
        session.close()


@router.get("/models", response_model=list[dict])
def list_models(model_type: Optional[str] = None, current_user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    """Lista modelos filtrables por tipo (`local`/`online`)."""
    session = get_session()
    try:
        query = session.query(ModelConfig)
        if model_type:
            query = query.filter(ModelConfig.model_type == model_type)
        items = query.all()
        return [
            {
                "id": item.id,
                "name": item.name,
                "provider": item.provider,
                "model_type": getattr(item, "model_type", "local"),
                "active": item.active,
            }
            for item in items
        ]
    finally:
        session.close()


@router.post("/rules")
def create_rule(payload: RuleIn, current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Crea una regla legacy de enrutamiento de modelo."""
    session = get_session()
    try:
        rule = Rule(
            name=payload.name,
            every_n_messages=payload.every_n_messages,
            model_id=payload.model_id,
            enabled=payload.enabled,
        )
        session.add(rule)
        session.commit()
        session.refresh(rule)
        return {"id": rule.id}
    finally:
        session.close()


@router.post("/contacts")
def add_contact(payload: ContactIn, current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Crea/actualiza contacto legacy por `contact_id`."""
    session = get_session()
    try:
        contact = session.query(Contact).filter(Contact.chat_id == payload.contact_id).first()
        if contact is None:
            contact = Contact()
            contact.chat_id = payload.contact_id
            contact.name = payload.label or None
            session.add(contact)
        elif payload.label:
            contact.name = payload.label

        session.commit()
        return {"chat_id": contact.chat_id, "name": contact.name}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
