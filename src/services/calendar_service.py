"""
📅 Calendar Service - Base Classes and Interfaces
Abstract base classes for calendar integration (Google Calendar, Outlook)
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CalendarProvider(str, Enum):
    """Supported calendar providers"""

    GOOGLE_CALENDAR = "google_calendar"
    OUTLOOK = "outlook"


class AppointmentStatus(str, Enum):
    """Possible appointment statuses"""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    RESCHEDULED = "rescheduled"


@dataclass
class TimeSlot:
    """Represents an available time slot"""

    start: datetime
    end: datetime
    duration_minutes: int = 30
    is_available: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "duration_minutes": self.duration_minutes,
            "is_available": self.is_available,
        }

    def format_for_user(self, timezone: str = "America/Bogota") -> str:
        """Format the slot for display to user in WhatsApp"""
        # Format: "Martes 21 de Enero, 10:00 AM - 10:30 AM"
        days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        months = [
            "Enero",
            "Febrero",
            "Marzo",
            "Abril",
            "Mayo",
            "Junio",
            "Julio",
            "Agosto",
            "Septiembre",
            "Octubre",
            "Noviembre",
            "Diciembre",
        ]

        day_name = days[self.start.weekday()]
        month_name = months[self.start.month - 1]

        start_str = self.start.strftime("%I:%M %p").lstrip("0")
        end_str = self.end.strftime("%I:%M %p").lstrip("0")

        return f"{day_name} {self.start.day} de {month_name}, {start_str} - {end_str}"


@dataclass
class AppointmentData:
    """Data required to create an appointment"""

    title: str
    start_time: datetime
    end_time: datetime
    client_name: str
    client_email: Optional[str] = None
    client_phone: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    timezone: str = "America/Bogota"
    send_notifications: bool = True
    add_video_conferencing: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_minutes(self) -> int:
        return int((self.end_time - self.start_time).total_seconds() / 60)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "client_name": self.client_name,
            "client_email": self.client_email,
            "client_phone": self.client_phone,
            "description": self.description,
            "location": self.location,
            "timezone": self.timezone,
            "duration_minutes": self.duration_minutes,
            "metadata": self.metadata,
        }


@dataclass
class AppointmentResult:
    """Result of creating/updating an appointment"""

    success: bool
    appointment_id: Optional[str] = None
    external_id: Optional[str] = None
    external_link: Optional[str] = None
    ical_uid: Optional[str] = None
    error_message: Optional[str] = None
    provider: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "appointment_id": self.appointment_id,
            "external_id": self.external_id,
            "external_link": self.external_link,
            "ical_uid": self.ical_uid,
            "error_message": self.error_message,
            "provider": self.provider,
        }


@dataclass
class CalendarConfig:
    """Configuration for a calendar provider"""

    provider: CalendarProvider
    calendar_id: str = "primary"
    default_duration_minutes: int = 30
    buffer_between_appointments: int = 15
    working_hours: dict[str, dict[str, str]] = field(default_factory=dict)
    send_notifications: bool = True
    add_video_conferencing: bool = True

    def get_working_hours_for_day(self, day: str) -> Optional[dict[str, str]]:
        """Get working hours for a specific day (monday, tuesday, etc.)"""
        day_config = self.working_hours.get(day.lower(), {})
        if day_config.get("closed", False):
            return None
        return day_config if day_config.get("start") and day_config.get("end") else None


class BaseCalendarProvider(ABC):
    """
    Abstract base class for calendar providers.
    Implementations: GoogleCalendarProvider, OutlookCalendarProvider
    """

    def __init__(self, config: CalendarConfig):
        self.config = config
        self.is_authenticated = False
        self._credentials = None

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'google_calendar', 'outlook')"""
        pass

    @abstractmethod
    async def authenticate(self, credentials: dict[str, Any]) -> bool:
        """
        Authenticate with the calendar service.

        Args:
            credentials: OAuth credentials or API keys

        Returns:
            True if authentication successful, False otherwise
        """
        pass

    @abstractmethod
    async def refresh_token(self) -> bool:
        """
        Refresh the OAuth access token if expired.

        Returns:
            True if refresh successful, False otherwise
        """
        pass

    @abstractmethod
    async def get_free_slots(self, start_date: datetime, end_date: datetime, duration_minutes: int = 30) -> list[TimeSlot]:
        """
        Get available time slots within a date range.

        Args:
            start_date: Start of the date range
            end_date: End of the date range
            duration_minutes: Required slot duration

        Returns:
            List of available TimeSlot objects
        """
        pass

    @abstractmethod
    async def create_appointment(self, appointment: AppointmentData) -> AppointmentResult:
        """
        Create a new appointment in the calendar.

        Args:
            appointment: Appointment data

        Returns:
            AppointmentResult with success status and IDs
        """
        pass

    @abstractmethod
    async def update_appointment(self, external_id: str, updates: dict[str, Any]) -> AppointmentResult:
        """
        Update an existing appointment.

        Args:
            external_id: The external calendar event ID
            updates: Dictionary of fields to update

        Returns:
            AppointmentResult with success status
        """
        pass

    @abstractmethod
    async def cancel_appointment(self, external_id: str, send_notification: bool = True) -> bool:
        """
        Cancel an appointment.

        Args:
            external_id: The external calendar event ID
            send_notification: Whether to send cancellation notice

        Returns:
            True if cancellation successful
        """
        pass

    @abstractmethod
    async def get_appointment(self, external_id: str) -> Optional[dict[str, Any]]:
        """
        Get details of a specific appointment.

        Args:
            external_id: The external calendar event ID

        Returns:
            Appointment details or None if not found
        """
        pass

    def _generate_slots_from_working_hours(
        self, date: datetime, busy_periods: list[dict[str, datetime]], duration_minutes: int
    ) -> list[TimeSlot]:
        """
        Generate available slots for a day based on working hours and busy periods.

        Args:
            date: The date to generate slots for
            busy_periods: List of busy time ranges
            duration_minutes: Required slot duration

        Returns:
            List of available TimeSlot objects
        """
        day_name = date.strftime("%A").lower()
        working_hours = self.config.get_working_hours_for_day(day_name)

        if not working_hours:
            return []  # Day is closed

        # Parse working hours
        start_hour, start_min = map(int, working_hours["start"].split(":"))
        end_hour, end_min = map(int, working_hours["end"].split(":"))

        work_start = date.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
        work_end = date.replace(hour=end_hour, minute=end_min, second=0, microsecond=0)

        slots = []
        current = work_start
        buffer = timedelta(minutes=self.config.buffer_between_appointments)
        slot_duration = timedelta(minutes=duration_minutes)

        while current + slot_duration <= work_end:
            slot_end = current + slot_duration

            # Check if slot overlaps with any busy period
            is_busy = False
            for busy in busy_periods:
                busy_start = busy.get("start")
                busy_end = busy.get("end")
                if busy_start and busy_end:
                    # Add buffer around busy periods
                    busy_start_buffered = busy_start - buffer
                    busy_end_buffered = busy_end + buffer

                    if not (slot_end <= busy_start_buffered or current >= busy_end_buffered):
                        is_busy = True
                        break

            if not is_busy:
                slots.append(TimeSlot(start=current, end=slot_end, duration_minutes=duration_minutes, is_available=True))

            # Move to next slot (with buffer)
            current = slot_end + buffer

        return slots

    def _filter_past_slots(self, slots: list[TimeSlot]) -> list[TimeSlot]:
        """Remove slots that are in the past"""
        now = datetime.now()
        # Add a small buffer (30 min) to avoid booking appointments too close to now
        min_time = now + timedelta(minutes=30)
        return [slot for slot in slots if slot.start > min_time]


class CalendarManager:
    """
    Manager class that handles multiple calendar providers.
    Provides a unified interface for calendar operations.
    """

    def __init__(self):
        self._providers: dict[str, BaseCalendarProvider] = {}
        self._active_provider: Optional[str] = None
        self._config: Optional[CalendarConfig] = None

    def register_provider(self, provider: BaseCalendarProvider):
        """Register a calendar provider"""
        self._providers[provider.provider_name] = provider
        logger.info(f"📅 Registered calendar provider: {provider.provider_name}")

    def set_active_provider(self, provider_name: str) -> bool:
        """Set the active calendar provider"""
        if provider_name in self._providers:
            self._active_provider = provider_name
            logger.info(f"📅 Active calendar provider set to: {provider_name}")
            return True
        logger.warning(f"⚠️ Provider not found: {provider_name}")
        return False

    def get_active_provider(self) -> Optional[BaseCalendarProvider]:
        """Get the currently active provider"""
        if self._active_provider:
            return self._providers.get(self._active_provider)
        return None

    async def get_free_slots(self, start_date: datetime, end_date: datetime, duration_minutes: int = 30) -> list[TimeSlot]:
        """Get free slots from the active provider"""
        provider = self.get_active_provider()
        if not provider:
            logger.error("❌ No active calendar provider")
            return []

        return await provider.get_free_slots(start_date, end_date, duration_minutes)

    async def create_appointment(self, appointment: AppointmentData) -> AppointmentResult:
        """Create appointment using active provider"""
        provider = self.get_active_provider()
        if not provider:
            return AppointmentResult(success=False, error_message="No active calendar provider configured")

        return await provider.create_appointment(appointment)

    async def cancel_appointment(self, external_id: str, send_notification: bool = True) -> bool:
        """Cancel appointment using active provider"""
        provider = self.get_active_provider()
        if not provider:
            return False

        return await provider.cancel_appointment(external_id, send_notification)

    def get_available_providers(self) -> list[str]:
        """Get list of registered provider names"""
        return list(self._providers.keys())

    def is_ready(self) -> bool:
        """Check if a provider is configured and authenticated"""
        provider = self.get_active_provider()
        return provider is not None and provider.is_authenticated


# Global calendar manager instance
calendar_manager = CalendarManager()
