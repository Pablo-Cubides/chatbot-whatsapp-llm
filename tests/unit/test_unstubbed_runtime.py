"""Exercise a fresh interpreter so conftest's legacy fake cannot hide imports."""

import os
import secrets
import subprocess
import sys
from pathlib import Path


def run_fresh(code: str, database: Path) -> None:
    environment = dict(os.environ)
    for name in ("GEMINI_API_KEY", "OPENAI_API_KEY", "CLAUDE_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"):
        environment.pop(name, None)
    environment.update(
        JWT_SECRET=secrets.token_urlsafe(48),
        ADMIN_PASSWORD=secrets.token_urlsafe(24),
        DATABASE_URL=f"sqlite:///{database}",
        DB_ALLOW_CREATE_ALL="true",
        AUTO_MIGRATE="false",
        AUDIO_TRANSCRIPTION_ENABLED="false",
        RATE_LIMIT_ENABLED="false",
        RATE_LIMIT_REDIS_ENABLED="false",
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[2],
        env=environment,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_real_application_registers_auth_routes(tmp_path: Path) -> None:
    run_fresh(
        """
import os
import stub_chat
from fastapi.testclient import TestClient
from admin_panel import app

assert stub_chat.__file__.endswith('stub_chat.py')
with TestClient(app) as client:
    assert client.get('/healthz').status_code == 200
    response = client.post('/api/auth/login', json={
        'username': os.environ.get('ADMIN_USERNAME', 'admin'),
        'password': os.environ['ADMIN_PASSWORD'],
    })
    assert response.status_code == 200, response.status_code
    assert response.json()['access_token']
    assert client.get('/api/status').status_code == 401
""",
        tmp_path / "runtime.db",
    )


def test_real_chat_adapter_delegates_and_preserves_history(tmp_path: Path) -> None:
    run_fresh(
        """
from unittest.mock import AsyncMock, patch
import stub_chat

history = [{'role': 'assistant', 'content': 'Earlier reply'}]
with patch.object(stub_chat, 'MultiProviderLLM') as factory:
    manager = factory.return_value
    manager.initialize = AsyncMock()
    manager.generate_response = AsyncMock(return_value={'success': True, 'response': 'Provider reply'})
    assert stub_chat.chat('New message', 'synthetic-chat', history) == 'Provider reply'
    manager.generate_response.assert_awaited_once_with(
        history + [{'role': 'user', 'content': 'New message'}],
        business_context={'chat_id': 'synthetic-chat'},
    )
    assert len(history) == 1
    manager.generate_response.return_value = {'success': False, 'error': 'upstream diagnostic'}
    try:
        stub_chat.chat('New message', 'synthetic-chat', [])
    except RuntimeError as error:
        assert 'upstream diagnostic' not in str(error)
    else:
        raise AssertionError('Provider failure must not become a successful canned reply')
""",
        tmp_path / "adapter.db",
    )
