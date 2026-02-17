from datetime import datetime

import pytest

from src.services.calendar_service import (
    AppointmentData,
    AppointmentResult,
    BaseCalendarProvider,
    CalendarConfig,
    CalendarManager,
    CalendarProvider,
)


class DummyProvider(BaseCalendarProvider):
    @property
    def provider_name(self) -> str:
        return "dummy"

    async def authenticate(self, credentials: dict[str, object]) -> bool:
        self.is_authenticated = True
        return True

    async def refresh_token(self) -> bool:
        return True

    async def get_free_slots(self, start_date: datetime, end_date: datetime, duration_minutes: int = 30):
        return []

    async def create_appointment(self, appointment: AppointmentData) -> AppointmentResult:
        return AppointmentResult(success=True, appointment_id="appt-1")

    async def update_appointment(self, external_id: str, updates: dict[str, object]) -> AppointmentResult:
        return AppointmentResult(success=True, appointment_id=external_id)

    async def cancel_appointment(self, external_id: str, send_notification: bool = True) -> bool:
        return True

    async def get_appointment(self, external_id: str):
        return {"id": external_id}


def test_generate_slots_from_working_hours_respects_busy_periods_and_buffer() -> None:
    cfg = CalendarConfig(
        provider=CalendarProvider.GOOGLE_CALENDAR,
        working_hours={"monday": {"start": "09:00", "end": "10:30", "closed": False}},
        buffer_between_appointments=15,
    )
    provider = DummyProvider(cfg)

    monday = datetime(2026, 2, 16, 0, 0)  # lunes
    busy_periods = [{"start": monday.replace(hour=9, minute=45), "end": monday.replace(hour=10, minute=15)}]

    slots = provider._generate_slots_from_working_hours(monday, busy_periods, duration_minutes=30)

    assert len(slots) == 1
    assert slots[0].start.hour == 9
    assert slots[0].start.minute == 0


@pytest.mark.asyncio
async def test_calendar_manager_delegates_to_active_provider() -> None:
    cfg = CalendarConfig(provider=CalendarProvider.GOOGLE_CALENDAR)
    provider = DummyProvider(cfg)
    provider.is_authenticated = True

    manager = CalendarManager()
    manager.register_provider(provider)
    assert manager.set_active_provider("dummy") is True
    assert manager.is_ready() is True

    result = await manager.create_appointment(
        AppointmentData(
            title="Consulta",
            start_time=datetime(2026, 2, 16, 11, 0),
            end_time=datetime(2026, 2, 16, 11, 30),
            client_name="Ana",
        )
    )

    assert result.success is True
    assert result.appointment_id == "appt-1"
