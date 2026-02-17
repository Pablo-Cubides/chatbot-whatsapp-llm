"""Phase 5A appointment end-to-end conversational flow tests."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src.services.appointment_flow import AppointmentFlowManager
from src.services.calendar_service import AppointmentResult, TimeSlot

pytestmark = pytest.mark.integration


class _ReadyCalendarManager:
    def __init__(self) -> None:
        self.created_payloads = []

    def is_ready(self) -> bool:
        return True

    async def get_free_slots(self, start_date: datetime, end_date: datetime, duration_minutes: int = 30) -> list[TimeSlot]:
        slot_start = start_date.replace(hour=10, minute=0, second=0, microsecond=0)
        if slot_start < datetime.now() + timedelta(minutes=40):
            slot_start = slot_start + timedelta(days=1)
        slot_end = slot_start + timedelta(minutes=duration_minutes)
        return [TimeSlot(start=slot_start, end=slot_end, duration_minutes=duration_minutes)]

    async def create_appointment(self, appointment):
        self.created_payloads.append(appointment)
        return AppointmentResult(
            success=True,
            appointment_id="appt_phase5",
            external_id="external_phase5",
            external_link="https://meet.example.com/phase5",
            provider="fake-calendar",
        )


@pytest.mark.asyncio
async def test_appointment_flow_with_calendar_provider_success() -> None:
    calendar = _ReadyCalendarManager()
    manager = AppointmentFlowManager(calendar_mgr=calendar)

    response, completed = await manager.process_message("chat-phase5", "quiero agendar una cita")
    assert completed is False
    assert "nombre" in response.lower()

    response, completed = await manager.process_message("chat-phase5", "Ana López")
    assert completed is False
    assert "correo" in response.lower()

    response, completed = await manager.process_message("chat-phase5", "ana@example.com")
    assert completed is False
    assert "motivo" in response.lower()

    response, completed = await manager.process_message("chat-phase5", "consulta de seguimiento")
    assert completed is False
    assert "fecha" in response.lower()

    response, completed = await manager.process_message("chat-phase5", "mañana")
    assert completed is False
    assert "horarios disponibles" in response.lower()

    response, completed = await manager.process_message("chat-phase5", "1")
    assert completed is False
    assert "resumen de tu cita" in response.lower()

    response, completed = await manager.process_message("chat-phase5", "sí")
    assert completed is True
    assert "cita confirmada" in response.lower()
    assert "https://meet.example.com/phase5" in response

    assert len(calendar.created_payloads) == 1
    created = calendar.created_payloads[0]
    assert created.client_name == "Ana López"
    assert created.client_email == "ana@example.com"
    assert "seguimiento" in (created.description or "")
