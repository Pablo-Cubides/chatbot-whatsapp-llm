from datetime import datetime

import pytest

from src.services.appointment_flow import AppointmentFlowManager, AppointmentState


class FakeCalendarManager:
    def is_ready(self) -> bool:
        return False


@pytest.mark.asyncio
async def test_full_flow_without_calendar_provider() -> None:
    manager = AppointmentFlowManager(calendar_mgr=FakeCalendarManager())

    response, completed = await manager.process_message("chat-1", "quiero agendar una cita")
    assert completed is False
    assert "agendar una cita" in response.lower()

    response, completed = await manager.process_message("chat-1", "Ana López")
    assert completed is False
    assert "correo" in response.lower()

    response, completed = await manager.process_message("chat-1", "no")
    assert completed is False
    assert "motivo" in response.lower()

    response, completed = await manager.process_message("chat-1", "consulta general")
    assert completed is False
    assert "fecha" in response.lower()

    response, completed = await manager.process_message("chat-1", "mañana")
    assert completed is False
    assert "horarios disponibles" in response.lower()

    response, completed = await manager.process_message("chat-1", "1")
    assert completed is False
    assert "resumen de tu cita" in response.lower()

    response, completed = await manager.process_message("chat-1", "sí")
    assert completed is True
    assert "cita registrada" in response.lower()


def test_detect_appointment_intent_and_parse_date() -> None:
    manager = AppointmentFlowManager(calendar_mgr=FakeCalendarManager())

    assert manager.detect_appointment_intent("Me ayudas a agendar una cita?") is True
    assert manager.detect_appointment_intent("solo quería saludar") is False

    parsed = manager._parse_date("próximo lunes")
    assert isinstance(parsed, datetime)


@pytest.mark.asyncio
async def test_slot_selection_rejects_out_of_range() -> None:
    manager = AppointmentFlowManager(calendar_mgr=FakeCalendarManager())
    session = manager.create_session("chat-2")
    session.state = AppointmentState.SHOWING_SLOTS
    session.available_slots = []

    # si no hay slots, cualquier número debe pedir rango válido sin explotar
    response, completed = await manager._process_slot_selection(session, "9")

    assert completed is False
    assert "entre 1 y 0" in response.lower()
