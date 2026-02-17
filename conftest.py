"""
Configuración global para pytest
"""

import os
import sys
from datetime import datetime, timezone

# Configurar variables de entorno para tests
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key-for-testing-purposes-only")
os.environ.setdefault("ADMIN_PASSWORD", "test_admin_password")
os.environ.setdefault("OPERATOR_PASSWORD", "test_operator_password")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("RATE_LIMIT_REDIS_ENABLED", "false")
os.environ.setdefault("DB_ALLOW_CREATE_ALL", "true")

# Mock de APIs para tests
os.environ.setdefault("GEMINI_API_KEY", "test_gemini_key")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_key")
os.environ.setdefault("CLAUDE_API_KEY", "test_claude_key")
os.environ.setdefault("XAI_API_KEY", "test_xai_key")

import asyncio
import types

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

# pytest-asyncio v0.24+ uses asyncio_mode=auto from pytest.ini
# No need for deprecated event_loop fixture


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use default event loop policy for all async tests."""
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture
def mock_env_vars():
    """Fixture para proporcionar variables de entorno mockeadas."""
    return {
        "JWT_SECRET": "test-secret-key-for-testing-only",
        "ADMIN_PASSWORD": "test_admin_pass",
        "OPERATOR_PASSWORD": "test_operator_pass",
        "GEMINI_API_KEY": "test_gemini_key",
        "OPENAI_API_KEY": "test_openai_key",
        "CLAUDE_API_KEY": "test_claude_key",
    }


@pytest.fixture(autouse=True)
def db_transaction_isolation():
    """Run each test inside a DB transaction and rollback afterwards."""
    try:
        import src.models.admin_db as admin_db
    except Exception:
        yield
        return

    connection = admin_db.engine.connect()
    transaction = connection.begin()
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=connection)

    original_session_local = admin_db.SessionLocal
    admin_db.SessionLocal = testing_session_local

    try:
        yield
    finally:
        admin_db.SessionLocal = original_session_local
        if transaction.is_active:
            transaction.rollback()
        connection.close()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Auto-assign `unit`/`integration`/`api` markers by test path."""
    for item in items:
        path = str(item.fspath).replace("\\", "/")
        if "/tests/integration/" in path:
            item.add_marker(pytest.mark.integration)
        elif "/tests/api/" in path:
            item.add_marker(pytest.mark.api)
        elif "/tests/unit/" in path:
            item.add_marker(pytest.mark.unit)


if "stub_chat" not in sys.modules:
    _stub = types.ModuleType("stub_chat")
    _stub.chat = lambda *a, **kw: "stub response"
    sys.modules["stub_chat"] = _stub


@pytest.fixture
def client() -> TestClient:
    """Shared FastAPI test client available to api/unit/integration suites."""
    from admin_panel import app

    return TestClient(app)


@pytest.fixture
def create_user() -> callable:
    """Factory to register a test user directly in auth manager with hashed password.

    Returns a callable:
        create_user(username, password, role='operator', permissions=None) -> dict
    """
    from src.services.auth_system import auth_manager

    created_usernames: list[str] = []

    def _factory(username: str, password: str, role: str = "operator", permissions: list[str] | None = None) -> dict:
        entry = {
            "password_hash": auth_manager._hash_password(password),
            "role": role,
            "permissions": permissions or ["view"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        auth_manager.users[username] = entry
        created_usernames.append(username)
        return {"username": username, "password": password, "role": role}

    try:
        yield _factory
    finally:
        for username in created_usernames:
            auth_manager.users.pop(username, None)


@pytest.fixture
def auth_headers_factory(client: TestClient) -> callable:
    """Factory to obtain Bearer headers via real login endpoint."""

    def _factory(username: str, password: str) -> dict[str, str]:
        response = client.post("/api/auth/login", json={"username": username, "password": password})
        assert response.status_code == 200
        token = response.json().get("access_token")
        assert token
        return {"Authorization": f"Bearer {token}"}

    return _factory


@pytest.fixture
def admin_headers(auth_headers_factory: callable) -> dict[str, str]:
    """Bearer headers for admin user."""
    return auth_headers_factory("admin", os.environ.get("ADMIN_PASSWORD", "test_admin_password"))


@pytest.fixture
def operator_headers(auth_headers_factory: callable) -> dict[str, str]:
    """Bearer headers for operator user."""
    return auth_headers_factory("operator", os.environ.get("OPERATOR_PASSWORD", "test_operator_password"))


@pytest.fixture(autouse=True)
def reset_rate_limiter_state():
    """Ensure in-memory rate limiter state does not leak between tests."""
    from src.services.http_rate_limit import http_rate_limiter

    previous_enabled = http_rate_limiter.enabled
    previous_redis_enabled = http_rate_limiter.redis_enabled
    previous_memory_store = dict(http_rate_limiter._memory_store)

    http_rate_limiter._memory_store.clear()
    http_rate_limiter.enabled = False
    http_rate_limiter.redis_enabled = False

    try:
        yield
    finally:
        http_rate_limiter.enabled = previous_enabled
        http_rate_limiter.redis_enabled = previous_redis_enabled
        http_rate_limiter._memory_store.clear()
        http_rate_limiter._memory_store.update(previous_memory_store)


@pytest.fixture(autouse=True)
def reset_auth_runtime_security_state():
    """Reset in-memory auth security state (blacklists, lockout, attempts) between tests."""
    from src.services.auth_system import auth_manager

    auth_manager.reset_runtime_state()
    try:
        yield
    finally:
        auth_manager.reset_runtime_state()


@pytest.fixture(autouse=True)
def reset_protection_rate_limiter_state():
    """Reset decorator-based rate limiter state between tests."""
    from src.services.protection_system import rate_limiter

    rate_limiter.request_history.clear()
    try:
        yield
    finally:
        rate_limiter.request_history.clear()


@pytest.fixture(autouse=True)
def reset_security_response_runtime_state():
    """Reset in-memory monitoring auto-response state between tests."""
    try:
        from src.routers.monitoring import reset_security_response_runtime_state as _reset_security_state
    except Exception:
        yield
        return

    _reset_security_state()
    try:
        yield
    finally:
        _reset_security_state()
