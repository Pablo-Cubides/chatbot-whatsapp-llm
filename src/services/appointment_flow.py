"""
📅 Appointment Flow Manager
Conversational flow for scheduling appointments via WhatsApp
"""

import os
import re
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import uuid

logger = logging.getLogger(__name__)

from .calendar_service import (
    CalendarManager,
    CalendarConfig,
    CalendarProvider,
    TimeSlot,
    AppointmentData,
    AppointmentResult,
    calendar_manager
)


class AppointmentState(str, Enum):
    """States in the appointment booking flow"""
    NONE = "none"
    DETECTING_INTENT = "detecting_intent"
    COLLECTING_NAME = "collecting_name"
    COLLECTING_EMAIL = "collecting_email"
    COLLECTING_PHONE = "collecting_phone"
    COLLECTING_DATE = "collecting_date"
    COLLECTING_TIME = "collecting_time"
    COLLECTING_REASON = "collecting_reason"
    SHOWING_SLOTS = "showing_slots"
    CONFIRMING = "confirming"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class AppointmentSession:
    """Tracks the state of an appointment booking conversation"""
    chat_id: str
    state: AppointmentState = AppointmentState.NONE
    
    # Collected data
    client_name: Optional[str] = None
    client_email: Optional[str] = None
    client_phone: Optional[str] = None
    preferred_date: Optional[datetime] = None
    preferred_time: Optional[str] = None
    reason: Optional[str] = None
    
    # Available slots shown to user
    available_slots: List[TimeSlot] = field(default_factory=list)
    selected_slot: Optional[TimeSlot] = None
    
    # Result
    appointment_result: Optional[AppointmentResult] = None
    
    # Timestamps
    started_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Retry counters
    retry_count: int = 0
    max_retries: int = 3
    
    def update(self):
        self.updated_at = datetime.now()
    
    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """Check if session has expired"""
        return (datetime.now() - self.updated_at).total_seconds() > timeout_minutes * 60
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "chat_id": self.chat_id,
            "state": self.state.value,
            "client_name": self.client_name,
            "client_email": self.client_email,
            "client_phone": self.client_phone,
            "preferred_date": self.preferred_date.isoformat() if self.preferred_date else None,
            "reason": self.reason,
            "started_at": self.started_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class AppointmentFlowManager:
    """
    Manages the conversational flow for booking appointments.
    
    Flow:
    1. Detect appointment intent from user message
    2. Collect required information (name, email, date, time, reason)
    3. Check calendar availability
    4. Present available slots
    5. Confirm and create appointment
    6. Send confirmation message
    """
    
    def __init__(self, calendar_mgr: CalendarManager = None):
        self._calendar = calendar_mgr or calendar_manager
        self._sessions: Dict[str, AppointmentSession] = {}
        
        # Intent detection keywords
        self._appointment_keywords = [
            "cita", "agendar", "reservar", "programar", "turno",
            "appointment", "schedule", "book", "reserve",
            "reunión", "meeting", "consulta", "visita",
            "disponibilidad", "horario", "cuando puedo"
        ]
        
        # Date parsing patterns
        self._date_patterns = [
            r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})",  # DD/MM/YYYY or DD-MM-YYYY
            r"(mañana|pasado mañana|hoy)",
            r"(lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo)",
            r"próximo\s+(lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo)",
            r"esta semana",
            r"próxima semana|la semana que viene"
        ]
        
        # Time parsing patterns  
        self._time_patterns = [
            r"(\d{1,2}):(\d{2})\s*(am|pm)?",
            r"(\d{1,2})\s*(am|pm)",
            r"(mañana|tarde|noche)",
            r"a las (\d{1,2})"
        ]
        
        # Email validation
        self._email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        
        # Phone validation (flexible)
        self._phone_pattern = r"[\d\s\-\+\(\)]{7,}"
    
    def get_session(self, chat_id: str) -> Optional[AppointmentSession]:
        """Get existing session for a chat"""
        session = self._sessions.get(chat_id)
        if session and not session.is_expired():
            return session
        return None
    
    def create_session(self, chat_id: str) -> AppointmentSession:
        """Create a new appointment session"""
        session = AppointmentSession(chat_id=chat_id)
        self._sessions[chat_id] = session
        logger.info(f"📅 Created appointment session for {chat_id}")
        return session
    
    def end_session(self, chat_id: str):
        """End and remove a session"""
        if chat_id in self._sessions:
            del self._sessions[chat_id]
            logger.info(f"📅 Ended appointment session for {chat_id}")
    
    def has_active_session(self, chat_id: str) -> bool:
        """Check if chat has an active appointment session"""
        session = self.get_session(chat_id)
        return session is not None and session.state != AppointmentState.NONE
    
    def detect_appointment_intent(self, message: str) -> bool:
        """
        Detect if the user wants to schedule an appointment.
        
        Args:
            message: User's message text
            
        Returns:
            True if appointment intent detected
        """
        message_lower = message.lower()
        
        # Check for appointment keywords
        for keyword in self._appointment_keywords:
            if keyword in message_lower:
                logger.info(f"📅 Appointment intent detected: '{keyword}'")
                return True
        
        return False
    
    async def process_message(
        self,
        chat_id: str,
        message: str,
        client_phone: str = None
    ) -> Tuple[str, bool]:
        """
        Process a message in the appointment flow.
        
        Args:
            chat_id: WhatsApp chat ID
            message: User's message
            client_phone: Client's phone number if known
            
        Returns:
            Tuple of (response_message, flow_completed)
        """
        session = self.get_session(chat_id)
        
        # No active session - check for appointment intent
        if not session:
            if self.detect_appointment_intent(message):
                session = self.create_session(chat_id)
                session.client_phone = client_phone
                session.state = AppointmentState.COLLECTING_NAME
                session.update()
                
                return (
                    "¡Perfecto! Te ayudo a agendar una cita 📅\n\n"
                    "Para comenzar, ¿me podrías dar tu nombre completo?",
                    False
                )
            return ("", False)  # No intent detected, let normal flow continue
        
        # Process based on current state
        session.update()
        
        if session.state == AppointmentState.COLLECTING_NAME:
            return await self._process_name(session, message)
        
        elif session.state == AppointmentState.COLLECTING_EMAIL:
            return await self._process_email(session, message)
        
        elif session.state == AppointmentState.COLLECTING_PHONE:
            return await self._process_phone(session, message)
        
        elif session.state == AppointmentState.COLLECTING_REASON:
            return await self._process_reason(session, message)
        
        elif session.state == AppointmentState.COLLECTING_DATE:
            return await self._process_date(session, message)
        
        elif session.state == AppointmentState.SHOWING_SLOTS:
            return await self._process_slot_selection(session, message)
        
        elif session.state == AppointmentState.CONFIRMING:
            return await self._process_confirmation(session, message)
        
        return ("", False)
    
    async def _process_name(
        self, 
        session: AppointmentSession, 
        message: str
    ) -> Tuple[str, bool]:
        """Process name input"""
        name = message.strip()
        
        # Basic validation - at least 2 words or 3 characters
        if len(name) < 3:
            session.retry_count += 1
            if session.retry_count >= session.max_retries:
                self.end_session(session.chat_id)
                return ("Lo siento, no pude entender tu nombre. Intenta nuevamente más tarde.", True)
            return ("Por favor, escribe tu nombre completo:", False)
        
        session.client_name = name
        session.retry_count = 0
        
        # Skip email if we want faster flow
        if os.getenv("APPOINTMENT_SKIP_EMAIL", "false").lower() == "true":
            session.state = AppointmentState.COLLECTING_REASON
            return (
                f"Gracias {name.split()[0]} 👋\n\n"
                "¿Cuál es el motivo de tu cita? (ej: consulta, asesoría, etc.)",
                False
            )
        
        session.state = AppointmentState.COLLECTING_EMAIL
        return (
            f"Gracias {name.split()[0]} 👋\n\n"
            "¿Cuál es tu correo electrónico? (para enviarte la confirmación)",
            False
        )
    
    async def _process_email(
        self, 
        session: AppointmentSession, 
        message: str
    ) -> Tuple[str, bool]:
        """Process email input"""
        email_match = re.search(self._email_pattern, message)
        
        if not email_match:
            # Allow skipping email
            if any(word in message.lower() for word in ["no tengo", "no", "skip", "saltar", "omitir"]):
                session.state = AppointmentState.COLLECTING_REASON
                return (
                    "Sin problema. ¿Cuál es el motivo de tu cita?",
                    False
                )
            
            session.retry_count += 1
            if session.retry_count >= session.max_retries:
                session.state = AppointmentState.COLLECTING_REASON
                return (
                    "Continuemos sin email. ¿Cuál es el motivo de tu cita?",
                    False
                )
            return (
                "No pude identificar un email válido. Por favor escríbelo nuevamente "
                "(o escribe 'no' para omitir):",
                False
            )
        
        session.client_email = email_match.group()
        session.retry_count = 0
        session.state = AppointmentState.COLLECTING_REASON
        
        return (
            "Perfecto ✅\n\n¿Cuál es el motivo de tu cita? (ej: consulta, asesoría, reunión)",
            False
        )
    
    async def _process_phone(
        self, 
        session: AppointmentSession, 
        message: str
    ) -> Tuple[str, bool]:
        """Process phone input (if needed)"""
        phone_match = re.search(self._phone_pattern, message)
        
        if phone_match:
            session.client_phone = phone_match.group().strip()
        
        session.state = AppointmentState.COLLECTING_REASON
        return (
            "¿Cuál es el motivo de tu cita?",
            False
        )
    
    async def _process_reason(
        self, 
        session: AppointmentSession, 
        message: str
    ) -> Tuple[str, bool]:
        """Process reason/description input"""
        session.reason = message.strip()
        session.state = AppointmentState.COLLECTING_DATE
        
        return (
            "Entendido 📝\n\n"
            "¿Para qué fecha te gustaría la cita?\n"
            "(Puedes escribir: mañana, próximo lunes, 25/01/2026, etc.)",
            False
        )
    
    async def _process_date(
        self, 
        session: AppointmentSession, 
        message: str
    ) -> Tuple[str, bool]:
        """Process date input and show available slots"""
        parsed_date = self._parse_date(message)
        
        if not parsed_date:
            session.retry_count += 1
            if session.retry_count >= session.max_retries:
                # Default to tomorrow
                parsed_date = datetime.now() + timedelta(days=1)
            else:
                return (
                    "No pude entender la fecha. Por favor escribe algo como:\n"
                    "• mañana\n"
                    "• próximo lunes\n"
                    "• 25/01/2026",
                    False
                )
        
        session.preferred_date = parsed_date
        session.retry_count = 0
        
        # Check if calendar is configured
        if not self._calendar.is_ready():
            # Return generic slots based on working hours
            return await self._show_generic_slots(session)
        
        # Get real availability from calendar
        return await self._show_calendar_slots(session)
    
    async def _show_generic_slots(
        self, 
        session: AppointmentSession
    ) -> Tuple[str, bool]:
        """Show generic time slots when no calendar is connected"""
        # Generate default slots (9 AM - 5 PM, every 30 min)
        date = session.preferred_date
        slots = []
        
        for hour in range(9, 17):
            for minute in [0, 30]:
                start = date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                end = start + timedelta(minutes=30)
                slots.append(TimeSlot(start=start, end=end, duration_minutes=30))
        
        # Filter past slots
        now = datetime.now()
        slots = [s for s in slots if s.start > now + timedelta(minutes=30)]
        
        if not slots:
            session.preferred_date = date + timedelta(days=1)
            return (
                f"No hay horarios disponibles para {self._format_date(date)}.\n"
                f"¿Te parece bien para {self._format_date(session.preferred_date)}?",
                False
            )
        
        session.available_slots = slots[:8]  # Max 8 options
        session.state = AppointmentState.SHOWING_SLOTS
        
        return self._format_slots_message(session)
    
    async def _show_calendar_slots(
        self, 
        session: AppointmentSession
    ) -> Tuple[str, bool]:
        """Show real availability from connected calendar"""
        date = session.preferred_date
        start = date.replace(hour=0, minute=0, second=0)
        end = start + timedelta(days=3)  # Look 3 days ahead
        
        try:
            slots = await self._calendar.get_free_slots(start, end, 30)
            
            if not slots:
                return (
                    f"No encontré horarios disponibles en los próximos días.\n"
                    "¿Te gustaría que busque en otra semana?",
                    False
                )
            
            session.available_slots = slots[:8]
            session.state = AppointmentState.SHOWING_SLOTS
            
            return self._format_slots_message(session)
            
        except Exception as e:
            logger.error(f"❌ Error getting calendar slots: {e}")
            return await self._show_generic_slots(session)
    
    def _format_slots_message(
        self, 
        session: AppointmentSession
    ) -> Tuple[str, bool]:
        """Format available slots for display"""
        lines = ["Estos son los horarios disponibles:\n"]
        
        for i, slot in enumerate(session.available_slots, 1):
            lines.append(f"{i}. {slot.format_for_user()}")
        
        lines.append("\nEscribe el número del horario que prefieres:")
        
        return ("\n".join(lines), False)
    
    async def _process_slot_selection(
        self, 
        session: AppointmentSession, 
        message: str
    ) -> Tuple[str, bool]:
        """Process slot selection"""
        # Try to extract number
        numbers = re.findall(r"\d+", message)
        
        if not numbers:
            session.retry_count += 1
            if session.retry_count >= session.max_retries:
                self.end_session(session.chat_id)
                return ("Lo siento, no pude entender tu selección. Intenta agendar nuevamente.", True)
            return ("Por favor escribe el número del horario (ej: 1, 2, 3...):", False)
        
        selection = int(numbers[0])
        
        if selection < 1 or selection > len(session.available_slots):
            return (f"Por favor elige un número entre 1 y {len(session.available_slots)}:", False)
        
        session.selected_slot = session.available_slots[selection - 1]
        session.state = AppointmentState.CONFIRMING
        
        # Build confirmation message
        slot = session.selected_slot
        return (
            "📅 *Resumen de tu cita:*\n\n"
            f"👤 Nombre: {session.client_name}\n"
            f"📧 Email: {session.client_email or 'No proporcionado'}\n"
            f"📝 Motivo: {session.reason}\n"
            f"🗓️ Fecha: {slot.format_for_user()}\n\n"
            "¿Confirmas esta cita? (sí/no)",
            False
        )
    
    async def _process_confirmation(
        self, 
        session: AppointmentSession, 
        message: str
    ) -> Tuple[str, bool]:
        """Process confirmation and create appointment"""
        message_lower = message.lower().strip()
        
        # Check for confirmation
        if any(word in message_lower for word in ["sí", "si", "yes", "confirmo", "confirmar", "ok", "dale", "listo"]):
            return await self._create_appointment(session)
        
        # Check for cancellation
        if any(word in message_lower for word in ["no", "cancelar", "cancel", "cambiar"]):
            self.end_session(session.chat_id)
            return (
                "Entendido, he cancelado la reserva. "
                "Puedes escribir 'agendar cita' cuando quieras intentar de nuevo.",
                True
            )
        
        return ("Por favor confirma con 'sí' o cancela con 'no':", False)
    
    async def _create_appointment(
        self, 
        session: AppointmentSession
    ) -> Tuple[str, bool]:
        """Create the appointment in the calendar"""
        slot = session.selected_slot
        
        appointment_data = AppointmentData(
            title=f"Cita: {session.client_name} - {session.reason}",
            start_time=slot.start,
            end_time=slot.end,
            client_name=session.client_name,
            client_email=session.client_email,
            client_phone=session.client_phone,
            description=session.reason,
            send_notifications=True,
            add_video_conferencing=True
        )
        
        # Try to create in calendar
        if self._calendar.is_ready():
            try:
                result = await self._calendar.create_appointment(appointment_data)
                session.appointment_result = result
                
                if result.success:
                    self.end_session(session.chat_id)
                    
                    response = (
                        "✅ *¡Cita confirmada!*\n\n"
                        f"📅 {slot.format_for_user()}\n"
                    )
                    
                    if result.external_link:
                        response += f"\n🔗 Link: {result.external_link}\n"
                    
                    if session.client_email:
                        response += f"\n📧 Te envié una confirmación a {session.client_email}"
                    
                    response += "\n\n¡Nos vemos pronto! 👋"
                    
                    return (response, True)
                else:
                    return (
                        f"❌ Hubo un problema al crear la cita: {result.error_message}\n"
                        "Por favor intenta nuevamente más tarde.",
                        True
                    )
                    
            except Exception as e:
                logger.error(f"❌ Error creating appointment: {e}")
        
        # Calendar not configured - just confirm
        self.end_session(session.chat_id)
        return (
            "✅ *¡Cita registrada!*\n\n"
            f"📅 {slot.format_for_user()}\n"
            f"👤 {session.client_name}\n"
            f"📝 {session.reason}\n\n"
            "Te contactaremos pronto para confirmar. ¡Gracias!",
            True
        )
    
    def _parse_date(self, text: str) -> Optional[datetime]:
        """Parse natural language date"""
        text_lower = text.lower().strip()
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Relative dates
        if "hoy" in text_lower:
            return today
        if "mañana" in text_lower:
            return today + timedelta(days=1)
        if "pasado mañana" in text_lower:
            return today + timedelta(days=2)
        
        # Day names
        days_es = {
            "lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2,
            "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6
        }
        
        for day_name, day_num in days_es.items():
            if day_name in text_lower:
                days_ahead = (day_num - today.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7  # Next week if same day
                if "próximo" in text_lower or "proximo" in text_lower:
                    days_ahead += 7
                return today + timedelta(days=days_ahead)
        
        # Explicit date DD/MM/YYYY or DD-MM-YYYY
        date_match = re.search(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?", text)
        if date_match:
            day = int(date_match.group(1))
            month = int(date_match.group(2))
            year = int(date_match.group(3)) if date_match.group(3) else today.year
            
            if year < 100:
                year += 2000
            
            try:
                return datetime(year, month, day)
            except ValueError:
                pass
        
        return None
    
    def _format_date(self, date: datetime) -> str:
        """Format date for display"""
        days = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        months = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                  "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        
        return f"{days[date.weekday()]} {date.day} de {months[date.month - 1]}"
    
    def cancel_session(self, chat_id: str) -> str:
        """Cancel an appointment session"""
        session = self.get_session(chat_id)
        if session:
            self.end_session(chat_id)
            return "Reserva cancelada. Puedes escribir 'agendar' cuando quieras intentar de nuevo."
        return ""


# Global appointment flow manager
appointment_flow = AppointmentFlowManager()
