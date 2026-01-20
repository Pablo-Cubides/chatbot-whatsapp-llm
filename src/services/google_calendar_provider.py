"""
📅 Google Calendar Provider
Integration with Google Calendar API v3 for appointment scheduling
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pathlib import Path
import uuid

logger = logging.getLogger(__name__)

# Google API imports (graceful fallback if not installed)
try:
    from google.oauth2.credentials import Credentials
    from google.oauth2.service_account import Credentials as ServiceAccountCredentials
    from google_auth_oauthlib.flow import InstalledAppFlow, Flow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    logger.warning("⚠️ Google Calendar API libraries not installed. Run: pip install google-api-python-client google-auth-oauthlib")

from .calendar_service import (
    BaseCalendarProvider,
    CalendarConfig,
    CalendarProvider,
    TimeSlot,
    AppointmentData,
    AppointmentResult,
    AppointmentStatus
)


# OAuth2 scopes for Google Calendar
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.events'
]


class GoogleCalendarProvider(BaseCalendarProvider):
    """
    Google Calendar integration using Google Calendar API v3.
    
    Supports:
    - OAuth2 authentication (user consent flow)
    - Service account authentication (server-to-server)
    - FreeBusy queries for availability
    - Event creation with Google Meet integration
    - Event updates and cancellations
    """
    
    def __init__(self, config: CalendarConfig):
        super().__init__(config)
        self._service = None
        self._credentials_path: Optional[Path] = None
        self._token_path: Optional[Path] = None
        
        # Default paths
        project_root = Path(__file__).parent.parent.parent
        self._credentials_path = project_root / "config" / "google_credentials.json"
        self._token_path = project_root / "config" / "google_token.json"
    
    @property
    def provider_name(self) -> str:
        return CalendarProvider.GOOGLE_CALENDAR.value
    
    def set_credentials_path(self, credentials_path: str, token_path: str = None):
        """Set custom paths for credentials files"""
        self._credentials_path = Path(credentials_path)
        if token_path:
            self._token_path = Path(token_path)
    
    async def authenticate(self, credentials: Dict[str, Any] = None) -> bool:
        """
        Authenticate with Google Calendar API.
        
        Supports:
        1. Existing token file
        2. Service account credentials
        3. OAuth2 flow (requires user interaction)
        
        Args:
            credentials: Optional dict with 'type', 'access_token', 'refresh_token', etc.
        """
        if not GOOGLE_API_AVAILABLE:
            logger.error("❌ Google API libraries not available")
            return False
        
        try:
            creds = None
            
            # Option 1: Use provided credentials dict
            if credentials:
                if credentials.get("type") == "service_account":
                    creds = ServiceAccountCredentials.from_service_account_info(
                        credentials, scopes=SCOPES
                    )
                else:
                    creds = Credentials(
                        token=credentials.get("access_token"),
                        refresh_token=credentials.get("refresh_token"),
                        token_uri="https://oauth2.googleapis.com/token",
                        client_id=credentials.get("client_id"),
                        client_secret=credentials.get("client_secret"),
                        scopes=SCOPES
                    )
            
            # Option 2: Load from token file
            elif self._token_path and self._token_path.exists():
                creds = Credentials.from_authorized_user_file(str(self._token_path), SCOPES)
            
            # Refresh if expired
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    self._save_token(creds)
                except Exception as e:
                    logger.warning(f"⚠️ Failed to refresh token: {e}")
                    creds = None
            
            # Option 3: Generate authorization URL for OAuth flow
            if not creds or not creds.valid:
                logger.info("🔑 No valid credentials. OAuth flow required.")
                return False
            
            # Build the service
            self._service = build('calendar', 'v3', credentials=creds)
            self._credentials = creds
            self.is_authenticated = True
            
            logger.info("✅ Google Calendar authenticated successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Google Calendar authentication failed: {e}")
            return False
    
    def get_oauth_url(self, redirect_uri: str = "http://localhost:8003/api/calendar/oauth/google/callback") -> Optional[str]:
        """
        Generate OAuth authorization URL for user consent.
        
        Args:
            redirect_uri: Where Google should redirect after authorization
            
        Returns:
            Authorization URL to redirect user to
        """
        if not GOOGLE_API_AVAILABLE:
            return None
            
        if not self._credentials_path or not self._credentials_path.exists():
            logger.error(f"❌ Credentials file not found: {self._credentials_path}")
            return None
        
        try:
            flow = Flow.from_client_secrets_file(
                str(self._credentials_path),
                scopes=SCOPES,
                redirect_uri=redirect_uri
            )
            
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'
            )
            
            # Store state for verification (in production, use session/redis)
            self._oauth_state = state
            
            return authorization_url
            
        except Exception as e:
            logger.error(f"❌ Failed to generate OAuth URL: {e}")
            return None
    
    async def handle_oauth_callback(self, authorization_code: str, redirect_uri: str) -> bool:
        """
        Handle OAuth callback and exchange code for tokens.
        
        Args:
            authorization_code: Code from Google callback
            redirect_uri: Same redirect_uri used in get_oauth_url
            
        Returns:
            True if tokens obtained successfully
        """
        if not GOOGLE_API_AVAILABLE:
            return False
            
        try:
            flow = Flow.from_client_secrets_file(
                str(self._credentials_path),
                scopes=SCOPES,
                redirect_uri=redirect_uri
            )
            
            flow.fetch_token(code=authorization_code)
            creds = flow.credentials
            
            # Save token for future use
            self._save_token(creds)
            
            # Authenticate with new credentials
            return await self.authenticate()
            
        except Exception as e:
            logger.error(f"❌ OAuth callback failed: {e}")
            return False
    
    def _save_token(self, creds: 'Credentials'):
        """Save credentials to token file"""
        if self._token_path:
            self._token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._token_path, 'w') as f:
                f.write(creds.to_json())
            logger.info(f"💾 Token saved to {self._token_path}")
    
    async def refresh_token(self) -> bool:
        """Refresh expired access token"""
        if not self._credentials or not self._credentials.refresh_token:
            return False
        
        try:
            self._credentials.refresh(Request())
            self._save_token(self._credentials)
            return True
        except Exception as e:
            logger.error(f"❌ Token refresh failed: {e}")
            return False
    
    async def get_free_slots(
        self,
        start_date: datetime,
        end_date: datetime,
        duration_minutes: int = 30
    ) -> List[TimeSlot]:
        """
        Get available time slots using Google Calendar FreeBusy API.
        
        Args:
            start_date: Start of date range
            end_date: End of date range  
            duration_minutes: Required slot duration
            
        Returns:
            List of available TimeSlot objects
        """
        if not self.is_authenticated or not self._service:
            logger.warning("⚠️ Not authenticated with Google Calendar")
            return []
        
        try:
            # Query FreeBusy API
            body = {
                "timeMin": start_date.isoformat() + 'Z' if start_date.tzinfo is None else start_date.isoformat(),
                "timeMax": end_date.isoformat() + 'Z' if end_date.tzinfo is None else end_date.isoformat(),
                "items": [{"id": self.config.calendar_id}]
            }
            
            result = self._service.freebusy().query(body=body).execute()
            
            # Extract busy periods
            busy_periods = []
            calendar_busy = result.get('calendars', {}).get(self.config.calendar_id, {}).get('busy', [])
            
            for period in calendar_busy:
                busy_periods.append({
                    "start": datetime.fromisoformat(period['start'].replace('Z', '+00:00')),
                    "end": datetime.fromisoformat(period['end'].replace('Z', '+00:00'))
                })
            
            # Generate slots for each day
            all_slots = []
            current_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            
            while current_date < end_date:
                day_slots = self._generate_slots_from_working_hours(
                    current_date, 
                    busy_periods, 
                    duration_minutes
                )
                all_slots.extend(day_slots)
                current_date += timedelta(days=1)
            
            # Filter out past slots
            all_slots = self._filter_past_slots(all_slots)
            
            logger.info(f"📅 Found {len(all_slots)} available slots")
            return all_slots
            
        except HttpError as e:
            logger.error(f"❌ Google Calendar API error: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Error getting free slots: {e}")
            return []
    
    async def create_appointment(
        self,
        appointment: AppointmentData
    ) -> AppointmentResult:
        """
        Create a new event in Google Calendar.
        
        Args:
            appointment: Appointment details
            
        Returns:
            AppointmentResult with event ID and link
        """
        if not self.is_authenticated or not self._service:
            return AppointmentResult(
                success=False,
                error_message="Not authenticated with Google Calendar",
                provider=self.provider_name
            )
        
        try:
            # Build event body
            event = {
                "summary": appointment.title,
                "description": self._build_description(appointment),
                "start": {
                    "dateTime": appointment.start_time.isoformat(),
                    "timeZone": appointment.timezone
                },
                "end": {
                    "dateTime": appointment.end_time.isoformat(),
                    "timeZone": appointment.timezone
                },
                "attendees": [],
                "reminders": {
                    "useDefault": False,
                    "overrides": [
                        {"method": "email", "minutes": 24 * 60},  # 1 day before
                        {"method": "popup", "minutes": 30}  # 30 min before
                    ]
                }
            }
            
            # Add location if provided
            if appointment.location:
                event["location"] = appointment.location
            
            # Add attendee if email provided
            if appointment.client_email:
                event["attendees"].append({
                    "email": appointment.client_email,
                    "displayName": appointment.client_name
                })
            
            # Add Google Meet if requested
            if appointment.add_video_conferencing:
                event["conferenceData"] = {
                    "createRequest": {
                        "requestId": str(uuid.uuid4()),
                        "conferenceSolutionKey": {"type": "hangoutsMeet"}
                    }
                }
            
            # Create event
            created_event = self._service.events().insert(
                calendarId=self.config.calendar_id,
                body=event,
                sendUpdates="all" if appointment.send_notifications else "none",
                conferenceDataVersion=1 if appointment.add_video_conferencing else 0
            ).execute()
            
            # Extract meeting link
            meeting_link = None
            if "conferenceData" in created_event:
                entry_points = created_event["conferenceData"].get("entryPoints", [])
                for ep in entry_points:
                    if ep.get("entryPointType") == "video":
                        meeting_link = ep.get("uri")
                        break
            
            # If no meeting link from conference, use htmlLink
            if not meeting_link:
                meeting_link = created_event.get("htmlLink")
            
            logger.info(f"✅ Created Google Calendar event: {created_event['id']}")
            
            return AppointmentResult(
                success=True,
                appointment_id=str(uuid.uuid4()),
                external_id=created_event['id'],
                external_link=meeting_link,
                ical_uid=created_event.get('iCalUID'),
                provider=self.provider_name
            )
            
        except HttpError as e:
            error_msg = f"Google Calendar API error: {e.reason}"
            logger.error(f"❌ {error_msg}")
            return AppointmentResult(
                success=False,
                error_message=error_msg,
                provider=self.provider_name
            )
        except Exception as e:
            logger.error(f"❌ Error creating appointment: {e}")
            return AppointmentResult(
                success=False,
                error_message=str(e),
                provider=self.provider_name
            )
    
    def _build_description(self, appointment: AppointmentData) -> str:
        """Build event description with client info"""
        lines = []
        
        if appointment.description:
            lines.append(appointment.description)
            lines.append("")
        
        lines.append("📋 Información del Cliente:")
        lines.append(f"• Nombre: {appointment.client_name}")
        
        if appointment.client_email:
            lines.append(f"• Email: {appointment.client_email}")
        
        if appointment.client_phone:
            lines.append(f"• Teléfono: {appointment.client_phone}")
        
        lines.append("")
        lines.append("---")
        lines.append("Cita agendada automáticamente vía WhatsApp Chatbot")
        
        return "\n".join(lines)
    
    async def update_appointment(
        self,
        external_id: str,
        updates: Dict[str, Any]
    ) -> AppointmentResult:
        """
        Update an existing Google Calendar event.
        
        Args:
            external_id: Google Calendar event ID
            updates: Fields to update (start_time, end_time, title, etc.)
        """
        if not self.is_authenticated or not self._service:
            return AppointmentResult(
                success=False,
                error_message="Not authenticated",
                provider=self.provider_name
            )
        
        try:
            # Get existing event
            event = self._service.events().get(
                calendarId=self.config.calendar_id,
                eventId=external_id
            ).execute()
            
            # Apply updates
            if "title" in updates:
                event["summary"] = updates["title"]
            if "description" in updates:
                event["description"] = updates["description"]
            if "start_time" in updates:
                event["start"]["dateTime"] = updates["start_time"].isoformat()
            if "end_time" in updates:
                event["end"]["dateTime"] = updates["end_time"].isoformat()
            if "location" in updates:
                event["location"] = updates["location"]
            
            # Update event
            updated_event = self._service.events().update(
                calendarId=self.config.calendar_id,
                eventId=external_id,
                body=event,
                sendUpdates="all"
            ).execute()
            
            logger.info(f"✅ Updated Google Calendar event: {external_id}")
            
            return AppointmentResult(
                success=True,
                external_id=updated_event['id'],
                external_link=updated_event.get('htmlLink'),
                provider=self.provider_name
            )
            
        except HttpError as e:
            return AppointmentResult(
                success=False,
                error_message=f"API error: {e.reason}",
                provider=self.provider_name
            )
        except Exception as e:
            return AppointmentResult(
                success=False,
                error_message=str(e),
                provider=self.provider_name
            )
    
    async def cancel_appointment(
        self,
        external_id: str,
        send_notification: bool = True
    ) -> bool:
        """
        Cancel (delete) a Google Calendar event.
        
        Args:
            external_id: Google Calendar event ID
            send_notification: Whether to notify attendees
        """
        if not self.is_authenticated or not self._service:
            return False
        
        try:
            self._service.events().delete(
                calendarId=self.config.calendar_id,
                eventId=external_id,
                sendUpdates="all" if send_notification else "none"
            ).execute()
            
            logger.info(f"✅ Cancelled Google Calendar event: {external_id}")
            return True
            
        except HttpError as e:
            logger.error(f"❌ Failed to cancel event: {e.reason}")
            return False
        except Exception as e:
            logger.error(f"❌ Error cancelling appointment: {e}")
            return False
    
    async def get_appointment(
        self,
        external_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get details of a specific event"""
        if not self.is_authenticated or not self._service:
            return None
        
        try:
            event = self._service.events().get(
                calendarId=self.config.calendar_id,
                eventId=external_id
            ).execute()
            
            return {
                "id": event['id'],
                "title": event.get('summary'),
                "description": event.get('description'),
                "start": event.get('start', {}).get('dateTime'),
                "end": event.get('end', {}).get('dateTime'),
                "location": event.get('location'),
                "link": event.get('htmlLink'),
                "status": event.get('status'),
                "attendees": event.get('attendees', [])
            }
            
        except HttpError as e:
            if e.resp.status == 404:
                return None
            logger.error(f"❌ Error getting event: {e.reason}")
            return None
        except Exception as e:
            logger.error(f"❌ Error getting appointment: {e}")
            return None
