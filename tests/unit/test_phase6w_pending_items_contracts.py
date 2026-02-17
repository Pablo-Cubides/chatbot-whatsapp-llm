"""Phase 6W contracts for previously pending beta-hardening items."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    path = ROOT / rel_path
    assert path.exists(), f"Missing file: {rel_path}"
    return path.read_text(encoding="utf-8")


def test_compose_has_service_specific_stop_grace_period_for_core_runtime_services() -> None:
    text = _read("docker-compose.yml")

    assert "stop_grace_period: 15m" not in text
    assert text.count("stop_grace_period:") >= 3

    app_start = text.find("  app:")
    worker_start = text.find("  worker-web:")
    scheduler_start = text.find("  scheduler:")
    redis_start = text.find("  redis:")

    assert app_start != -1 and worker_start != -1 and scheduler_start != -1 and redis_start != -1
    assert "stop_grace_period: 35s" in text[app_start:worker_start]
    assert "stop_grace_period: 60s" in text[worker_start:scheduler_start]
    assert "stop_grace_period: 30s" in text[scheduler_start:redis_start]


def test_business_config_has_five_list_labels_with_for_attribute() -> None:
    text = _read("ui/business_config.html")

    assert '<label for="addServicesBtn">Servicios/Productos Principales</label>' in text
    assert '<label for="addPersonalityBtn">Características de Personalidad</label>' in text
    assert '<label for="addForbiddenBtn">Temas Prohibidos</label>' in text
    assert '<label for="addKeywordsBtn">Palabras Clave de Conversión</label>' in text
    assert '<label for="addQuestionsBtn">Preguntas de Calificación</label>' in text


def test_selected_services_migrate_logger_fstrings_to_lazy_format() -> None:
    silent_transfer = _read("src/services/silent_transfer.py")
    alert_system = _read("src/services/alert_system.py")

    # Verify representative lazy-format migrations in both modules.
    assert "logger.warning(\"🔇 TRANSFERENCIA SILENCIOSA creada: %s\", transfer_id)" in silent_transfer
    assert "logger.warning(\"Transfer ID: %s\", transfer_id)" in silent_transfer
    assert "logger.info(\"✅ Transferencia %s completada\", transfer_id)" in silent_transfer
    assert "logger.error(\"Error obteniendo estadísticas: %s\", e)" in silent_transfer

    assert "logger.warning(\"⚠️ Regex inválido en regla %s: %s - %s\", rule.id, rule.pattern, regex_err)" in alert_system
    assert "logger.info(\"🚨 Alerta creada: %s (regla: %s)\", alert_id, rule.name)" in alert_system
    assert "logger.error(\"❌ Error creando alerta: %s\", e)" in alert_system


def test_api_docs_include_five_practical_curl_examples() -> None:
    text = _read("docs/API.md")

    assert "## Curl examples (5)" in text
    assert "curl -fsS http://localhost:8003/healthz" in text
    assert "curl -fsS -X POST http://localhost:8003/api/auth/login" in text
    assert "curl -fsS http://localhost:8003/api/auth/me -H \"Authorization: Bearer ${TOKEN}\"" in text
    assert "curl -fsS http://localhost:8003/api/chats -H \"Authorization: Bearer ${TOKEN}\"" in text
    assert "curl -fsS http://localhost:8003/api/queue/pending -H \"Authorization: Bearer ${TOKEN}\"" in text
