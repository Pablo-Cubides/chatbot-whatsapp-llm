import pytest
from sqlalchemy import String, cast, func, select
from sqlalchemy.dialects import postgresql, sqlite

from src.models.admin_db import get_session
from src.models.models import SilentTransfer
from src.services.adaptive_layer import AdaptiveLayerManager
from src.services.queue_system import MessageStatus, QueuedMessage, queue_manager


pytestmark = pytest.mark.unit


def test_campaign_cancel_endpoint_marks_campaign_and_queued_messages_cancelled(
    client,
    admin_headers: dict[str, str],
) -> None:
    campaign_id = queue_manager.create_campaign(
        name="Campaña cancelable",
        created_by="admin",
        total_messages=2,
        metadata={"template": "hola"},
    )
    queue_manager.enqueue_message("573001112233", "hola", metadata={"campaign_id": campaign_id})
    queue_manager.enqueue_message("573001112244", "hola", metadata={"campaign_id": campaign_id})

    response = client.post(f"/api/campaigns/{campaign_id}/cancel", headers=admin_headers)
    assert response.status_code == 200
    assert response.json().get("success") is True

    campaign_status = queue_manager.get_campaign_status(campaign_id)
    assert campaign_status is not None
    assert campaign_status["status"] == "cancelled"

    session = get_session()
    try:
        campaign_messages = [
            msg
            for msg in session.query(QueuedMessage).all()
            if msg.extra_data and msg.extra_data.get("campaign_id") == campaign_id
        ]
        assert campaign_messages
        normalized_statuses = {
            status.value if isinstance((status := msg.status), MessageStatus) else str(status) for msg in campaign_messages
        }
        assert normalized_statuses == {MessageStatus.CANCELLED.value}
    finally:
        session.close()

    pending = queue_manager.get_pending_messages(limit=200)
    assert all((msg.get("metadata") or {}).get("campaign_id") != campaign_id for msg in pending)


@pytest.mark.asyncio
async def test_adaptive_layer_run_adaptive_cycle_async_no_event_loop_crash() -> None:
    class _DeepAnalyzerStub:
        enabled = True
        trigger_every_n_conversations = 1
        trigger_every_n_days = 1
        conversations_since_last_analysis = 0
        last_analysis_date = None

        @staticmethod
        def should_trigger_analysis() -> bool:
            return True

        @staticmethod
        async def analyze_batch(conversations, business_objectives=None):
            return []

        @staticmethod
        def record_conversation_end() -> None:
            return None

    class _ABManagerStub:
        enabled = False
        experiments = {}

        @staticmethod
        def get_stats() -> dict:
            return {}

    manager = AdaptiveLayerManager(deep_analyzer_instance=_DeepAnalyzerStub(), ab_manager=_ABManagerStub())
    result = await manager.run_adaptive_cycle(conversations=[{"chat_id": "chat-1", "messages": []}], force=True)
    assert result["success"] is True


def test_admin_panel_has_single_healthz_route() -> None:
    from admin_panel import app

    health_routes = [route for route in app.routes if route.path == "/healthz" and "GET" in getattr(route, "methods", set())]
    assert len(health_routes) == 1


def test_healthz_returns_503_without_leaking_db_error(client, monkeypatch) -> None:
    import admin_panel

    def _broken_get_session():
        raise RuntimeError("database credentials invalid")

    monkeypatch.setattr(admin_panel, "get_session", _broken_get_session)

    response = client.get("/healthz")
    assert response.status_code == 503
    assert response.json() == {"status": "unhealthy"}


def test_silent_transfer_aggregate_sql_compiles_for_sqlite_and_postgresql() -> None:
    pg_stmt = select(func.string_agg(cast(SilentTransfer.chat_id, String), ","))
    sqlite_stmt = select(func.group_concat(cast(SilentTransfer.chat_id, String), ","))

    pg_sql = str(pg_stmt.compile(dialect=postgresql.dialect())).lower()
    sqlite_sql = str(sqlite_stmt.compile(dialect=sqlite.dialect())).lower()

    assert "string_agg" in pg_sql
    assert "group_concat" in sqlite_sql
