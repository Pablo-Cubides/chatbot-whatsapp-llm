"""Daily and user context data routes extracted from admin_panel.py."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.models.admin_db import get_session
from src.models.models import DailyContext, UserContext
from src.services.auth_system import get_current_user

router = APIRouter(tags=["contexts-data"])


class DailyContextCreate(BaseModel):
    text: str
    active: Optional[bool] = True


@router.post("/api/daily-contexts")
def api_create_daily_context(payload: DailyContextCreate, current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Crea un contexto diario para enriquecer respuestas."""
    session = get_session()
    try:
        context = DailyContext(text=payload.text, active=payload.active)

        session.add(context)
        session.commit()

        return {
            "id": context.id,
            "text": context.text,
            "active": context.active,
            "created_at": context.created_at.isoformat() if context.created_at else None,
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/api/daily-contexts")
def api_list_daily_contexts(current_user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    """Lista los contextos diarios persistidos."""
    session = get_session()
    try:
        contexts = session.query(DailyContext).all()
        return [
            {
                "id": ctx.id,
                "text": ctx.text,
                "active": ctx.active,
                "created_at": ctx.created_at.isoformat() if ctx.created_at else None,
            }
            for ctx in contexts
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


class UserContextCreate(BaseModel):
    user_id: str
    text: str
    source: Optional[str] = "manual_admin"


@router.post("/api/user-contexts")
def api_create_user_context(payload: UserContextCreate, current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Crea contexto manual asociado a un usuario/chat."""
    session = get_session()
    try:
        context = UserContext(user_id=payload.user_id, text=payload.text, source=payload.source)

        session.add(context)
        session.commit()

        return {
            "id": context.id,
            "user_id": context.user_id,
            "text": context.text,
            "source": context.source,
            "created_at": context.created_at.isoformat() if context.created_at else None,
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/api/user-contexts")
def api_list_user_contexts(user_id: Optional[str] = None, current_user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    """Lista contextos por usuario o todos si no se indica filtro."""
    session = get_session()
    try:
        query = session.query(UserContext)
        if user_id:
            query = query.filter(UserContext.user_id == user_id)

        contexts = query.all()
        return [
            {
                "id": ctx.id,
                "user_id": ctx.user_id,
                "text": ctx.text,
                "source": ctx.source,
                "created_at": ctx.created_at.isoformat() if ctx.created_at else None,
            }
            for ctx in contexts
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/user-contexts/{user_id}")
def get_user_contexts_legacy(user_id: str, current_user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    """Endpoint legacy para obtener contextos de un usuario específico."""
    session = get_session()
    try:
        items = session.query(UserContext).filter(UserContext.user_id == user_id).all()
        return [{"id": i.id, "text": i.text, "source": i.source, "created_at": i.created_at} for i in items]
    finally:
        session.close()
