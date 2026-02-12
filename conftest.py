"""
Configuración global para pytest
"""

import os
import sys
from pathlib import Path

# Añadir el directorio src y sub-paquetes al path de Python
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(src_path / "models"))
sys.path.insert(0, str(src_path / "services"))

# Configurar variables de entorno para tests
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key-for-testing-purposes-only")
os.environ.setdefault("ADMIN_PASSWORD", "test_admin_password")
os.environ.setdefault("OPERATOR_PASSWORD", "test_operator_password")
os.environ.setdefault("DEBUG", "true")

# Mock de APIs para tests
os.environ.setdefault("GEMINI_API_KEY", "test_gemini_key")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_key")
os.environ.setdefault("CLAUDE_API_KEY", "test_claude_key")
os.environ.setdefault("XAI_API_KEY", "test_xai_key")

import asyncio

import pytest

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
