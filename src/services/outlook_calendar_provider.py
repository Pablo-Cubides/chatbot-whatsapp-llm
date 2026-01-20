"""
📅 Outlook Calendar Provider
Integration with Microsoft Graph API for Outlook/Microsoft 365 Calendar
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pathlib import Path
import uuid

logger = logging.getLogger(__name__)

# Microsoft Graph imports (graceful fallback if not installed)
try:
    import msal
    import httpx
    MSAL_AVAILABLE = True
except ImportError:
    MSAL_AVAILABLE = False
    logger.warning("⚠️ Microsoft libraries not installed. Run: pip install msal httpx")

from .calendar_service import (
    BaseCalendarProvider,
    CalendarConfig,
    CalendarProvider,
    TimeSlot,
    AppointmentData,
    AppointmentResult,
    AppointmentStatus
)


# Microsoft Graph API endpoints
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
AUTHORITY = "https://login.microsoftonline.com"

# OAuth2 scopes for Microsoft Graph
SCOPES = [
    "Calendars.ReadWrite",
    "User.Read",
    "offline_access"
]


class OutlookCalendarProvider(BaseCalendarProvider):
    """
    Microsoft Outlook/365 Calendar integration using Microsoft Graph API.
    
    Supports:
    - OAuth2 authentication with MSAL
    - Microsoft 365 work/school accounts
    - Personal Microsoft accounts (Outlook.com, Hotmail)
    - Calendar availability queries
    - Event creation with Teams meeting integration
    """
    
    def __init__(self, config: CalendarConfig):
        super().__init__(config)
        self._msal_app = None
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        
        # Azure AD App credentials (from environment or config)
        self._client_id = os.getenv("MICROSOFT_CLIENT_ID", "")
        self._client_secret = os.getenv("MICROSOFT_CLIENT_SECRET", "")
        self._tenant_id = os.getenv("MICROSOFT_TENANT_ID", "common")  # "common" for multi-tenant
        
        # Token cache path
        project_root = Path(__file__).parent.parent.parent
        self._token_cache_path = project_root / "config" / "outlook_token_cache.json"
    
    @property
    def provider_name(self) -> str:
        return CalendarProvider.OUTLOOK.value
    
    def configure(self, client_id: str, client_secret: str, tenant_id: str = "common"):
        """Configure Azure AD app credentials"""
        self._client_id = client_id
        self._client_secret = client_secret
        self._tenant_id = tenant_id
    
    def _get_msal_app(self) -> Optional['msal.ConfidentialClientApplication']:
        """Get or create MSAL application"""
        if not MSAL_AVAILABLE:
            return None
            
        if not self._client_id or not self._client_secret:
            logger.error("❌ Microsoft client credentials not configured")
            return None
        
        if not self._msal_app:
            # Load token cache if exists
            cache = msal.SerializableTokenCache()
            if self._token_cache_path.exists():
                cache.deserialize(self._token_cache_path.read_text())
            
            self._msal_app = msal.ConfidentialClientApplication(
                client_id=self._client_id,
                client_credential=self._client_secret,
                authority=f"{AUTHORITY}/{self._tenant_id}",
                token_cache=cache
            )
        
        return self._msal_app
    
    def _save_token_cache(self):
        """Save token cache to file"""
        if self._msal_app and self._msal_app.token_cache.has_state_changed:
            self._token_cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._token_cache_path.write_text(
                self._msal_app.token_cache.serialize()
            )
    
    async def authenticate(self, credentials: Dict[str, Any] = None) -> bool:
        """
        Authenticate with Microsoft Graph API.
        
        Args:
            credentials: Dict with 'access_token' and optionally 'refresh_token'
        """
        if not MSAL_AVAILABLE:
            logger.error("❌ MSAL library not available")
            return False
        
        try:
            # Option 1: Use provided tokens
            if credentials:
                self._access_token = credentials.get("access_token")
                self._refresh_token = credentials.get("refresh_token")
                
                if self._access_token:
                    # Verify token is valid
                    if await self._verify_token():
                        self.is_authenticated = True
                        return True
            
            # Option 2: Try to get token from cache
            app = self._get_msal_app()
            if not app:
                return False
            
            accounts = app.get_accounts()
            if accounts:
                # Try silent token acquisition
                result = app.acquire_token_silent(SCOPES, account=accounts[0])
                
                if result and "access_token" in result:
                    self._access_token = result["access_token"]
                    self._token_expires_at = datetime.now() + timedelta(
                        seconds=result.get("expires_in", 3600)
                    )
                    self._save_token_cache()
                    self.is_authenticated = True
                    logger.info("✅ Outlook Calendar authenticated from cache")
                    return True
            
            logger.info("🔑 No valid credentials. OAuth flow required.")
            return False
            
        except Exception as e:
            logger.error(f"❌ Outlook authentication failed: {e}")
            return False
    
    async def _verify_token(self) -> bool:
        """Verify the access token is valid by making a test request"""
        if not self._access_token:
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GRAPH_API_BASE}/me",
                    headers={"Authorization": f"Bearer {self._access_token}"}
                )
                return response.status_code == 200
        except Exception:
            return False
    
    def get_oauth_url(
        self, 
        redirect_uri: str = "http://localhost:8003/api/calendar/oauth/outlook/callback"
    ) -> Optional[str]:
        """
        Generate OAuth authorization URL for user consent.
        
        Args:
            redirect_uri: Where Microsoft should redirect after authorization
        """
        if not MSAL_AVAILABLE:
            return None
        
        app = self._get_msal_app()
        if not app:
            return None
        
        try:
            authorization_url = app.get_authorization_request_url(
                scopes=SCOPES,
                redirect_uri=redirect_uri,
                state=str(uuid.uuid4())
            )
            return authorization_url
            
        except Exception as e:
            logger.error(f"❌ Failed to generate OAuth URL: {e}")
            return None
    
    async def handle_oauth_callback(
        self, 
        authorization_code: str, 
        redirect_uri: str
    ) -> bool:
        """
        Handle OAuth callback and exchange code for tokens.
        
        Args:
            authorization_code: Code from Microsoft callback
            redirect_uri: Same redirect_uri used in get_oauth_url
        """
        if not MSAL_AVAILABLE:
            return False
        
        app = self._get_msal_app()
        if not app:
            return False
        
        try:
            result = app.acquire_token_by_authorization_code(
                code=authorization_code,
                scopes=SCOPES,
                redirect_uri=redirect_uri
            )
            
            if "access_token" in result:
                self._access_token = result["access_token"]
                self._refresh_token = result.get("refresh_token")
                self._token_expires_at = datetime.now() + timedelta(
                    seconds=result.get("expires_in", 3600)
                )
                
                self._save_token_cache()
                self.is_authenticated = True
                
                logger.info("✅ Outlook OAuth tokens obtained")
                return True
            else:
                error = result.get("error_description", result.get("error", "Unknown error"))
                logger.error(f"❌ OAuth token exchange failed: {error}")
                return False
                
        except Exception as e:
            logger.error(f"❌ OAuth callback failed: {e}")
            return False
    
    async def refresh_token(self) -> bool:
        """Refresh expired access token"""
        app = self._get_msal_app()
        if not app:
            return False
        
        try:
            accounts = app.get_accounts()
            if accounts:
                result = app.acquire_token_silent(SCOPES, account=accounts[0])
                
                if result and "access_token" in result:
                    self._access_token = result["access_token"]
                    self._save_token_cache()
                    return True
            
            return False
        except Exception as e:
            logger.error(f"❌ Token refresh failed: {e}")
            return False
    
    async def _make_graph_request(
        self,
        method: str,
        endpoint: str,
        data: Dict = None
    ) -> Optional[Dict]:
        """Make an authenticated request to Microsoft Graph API"""
        if not self._access_token:
            logger.error("❌ No access token available")
            return None
        
        url = f"{GRAPH_API_BASE}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                if method == "GET":
                    response = await client.get(url, headers=headers)
                elif method == "POST":
                    response = await client.post(url, headers=headers, json=data)
                elif method == "PATCH":
                    response = await client.patch(url, headers=headers, json=data)
                elif method == "DELETE":
                    response = await client.delete(url, headers=headers)
                    if response.status_code == 204:
                        return {"success": True}
                else:
                    return None
                
                if response.status_code in [200, 201]:
                    return response.json()
                elif response.status_code == 401:
                    # Token expired, try refresh
                    if await self.refresh_token():
                        return await self._make_graph_request(method, endpoint, data)
                else:
                    logger.error(f"❌ Graph API error {response.status_code}: {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Graph API request failed: {e}")
            return None
    
    async def get_free_slots(
        self,
        start_date: datetime,
        end_date: datetime,
        duration_minutes: int = 30
    ) -> List[TimeSlot]:
        """
        Get available time slots using Microsoft Graph Calendar API.
        Uses the findMeetingTimes endpoint for availability.
        """
        if not self.is_authenticated:
            logger.warning("⚠️ Not authenticated with Outlook")
            return []
        
        try:
            # Use calendar view to get busy times
            start_iso = start_date.strftime("%Y-%m-%dT%H:%M:%S")
            end_iso = end_date.strftime("%Y-%m-%dT%H:%M:%S")
            
            calendar_id = self.config.calendar_id or "primary"
            endpoint = f"/me/calendars/{calendar_id}/calendarView?startDateTime={start_iso}&endDateTime={end_iso}&$select=start,end"
            
            if calendar_id == "primary":
                endpoint = f"/me/calendarView?startDateTime={start_iso}&endDateTime={end_iso}&$select=start,end"
            
            result = await self._make_graph_request("GET", endpoint)
            
            if not result:
                return []
            
            # Extract busy periods
            busy_periods = []
            for event in result.get("value", []):
                start = event.get("start", {})
                end = event.get("end", {})
                
                if start.get("dateTime") and end.get("dateTime"):
                    busy_periods.append({
                        "start": datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00")),
                        "end": datetime.fromisoformat(end["dateTime"].replace("Z", "+00:00"))
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
            
            logger.info(f"📅 Found {len(all_slots)} available Outlook slots")
            return all_slots
            
        except Exception as e:
            logger.error(f"❌ Error getting free slots: {e}")
            return []
    
    async def create_appointment(
        self,
        appointment: AppointmentData
    ) -> AppointmentResult:
        """
        Create a new event in Outlook Calendar.
        """
        if not self.is_authenticated:
            return AppointmentResult(
                success=False,
                error_message="Not authenticated with Outlook",
                provider=self.provider_name
            )
        
        try:
            # Build event body
            event = {
                "subject": appointment.title,
                "body": {
                    "contentType": "HTML",
                    "content": self._build_description_html(appointment)
                },
                "start": {
                    "dateTime": appointment.start_time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "timeZone": appointment.timezone
                },
                "end": {
                    "dateTime": appointment.end_time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "timeZone": appointment.timezone
                },
                "isReminderOn": True,
                "reminderMinutesBeforeStart": 30
            }
            
            # Add location
            if appointment.location:
                event["location"] = {
                    "displayName": appointment.location
                }
            
            # Add attendee
            if appointment.client_email:
                event["attendees"] = [{
                    "emailAddress": {
                        "address": appointment.client_email,
                        "name": appointment.client_name
                    },
                    "type": "required"
                }]
            
            # Add Teams meeting if requested
            if appointment.add_video_conferencing:
                event["isOnlineMeeting"] = True
                event["onlineMeetingProvider"] = "teamsForBusiness"
            
            # Create event
            calendar_id = self.config.calendar_id or "primary"
            endpoint = f"/me/calendars/{calendar_id}/events"
            if calendar_id == "primary":
                endpoint = "/me/events"
            
            result = await self._make_graph_request("POST", endpoint, event)
            
            if not result:
                return AppointmentResult(
                    success=False,
                    error_message="Failed to create event",
                    provider=self.provider_name
                )
            
            # Extract meeting link
            meeting_link = result.get("webLink")
            if result.get("onlineMeeting"):
                meeting_link = result["onlineMeeting"].get("joinUrl", meeting_link)
            
            logger.info(f"✅ Created Outlook event: {result['id']}")
            
            return AppointmentResult(
                success=True,
                appointment_id=str(uuid.uuid4()),
                external_id=result["id"],
                external_link=meeting_link,
                ical_uid=result.get("iCalUId"),
                provider=self.provider_name
            )
            
        except Exception as e:
            logger.error(f"❌ Error creating Outlook appointment: {e}")
            return AppointmentResult(
                success=False,
                error_message=str(e),
                provider=self.provider_name
            )
    
    def _build_description_html(self, appointment: AppointmentData) -> str:
        """Build HTML description for Outlook event"""
        lines = []
        
        if appointment.description:
            lines.append(f"<p>{appointment.description}</p>")
        
        lines.append("<p><strong>📋 Información del Cliente:</strong></p>")
        lines.append("<ul>")
        lines.append(f"<li>Nombre: {appointment.client_name}</li>")
        
        if appointment.client_email:
            lines.append(f"<li>Email: {appointment.client_email}</li>")
        
        if appointment.client_phone:
            lines.append(f"<li>Teléfono: {appointment.client_phone}</li>")
        
        lines.append("</ul>")
        lines.append("<hr>")
        lines.append("<p><em>Cita agendada automáticamente vía WhatsApp Chatbot</em></p>")
        
        return "\n".join(lines)
    
    async def update_appointment(
        self,
        external_id: str,
        updates: Dict[str, Any]
    ) -> AppointmentResult:
        """Update an existing Outlook event"""
        if not self.is_authenticated:
            return AppointmentResult(
                success=False,
                error_message="Not authenticated",
                provider=self.provider_name
            )
        
        try:
            event_updates = {}
            
            if "title" in updates:
                event_updates["subject"] = updates["title"]
            if "description" in updates:
                event_updates["body"] = {
                    "contentType": "HTML",
                    "content": updates["description"]
                }
            if "start_time" in updates:
                event_updates["start"] = {
                    "dateTime": updates["start_time"].strftime("%Y-%m-%dT%H:%M:%S"),
                    "timeZone": updates.get("timezone", "America/Bogota")
                }
            if "end_time" in updates:
                event_updates["end"] = {
                    "dateTime": updates["end_time"].strftime("%Y-%m-%dT%H:%M:%S"),
                    "timeZone": updates.get("timezone", "America/Bogota")
                }
            if "location" in updates:
                event_updates["location"] = {
                    "displayName": updates["location"]
                }
            
            result = await self._make_graph_request(
                "PATCH",
                f"/me/events/{external_id}",
                event_updates
            )
            
            if result:
                logger.info(f"✅ Updated Outlook event: {external_id}")
                return AppointmentResult(
                    success=True,
                    external_id=external_id,
                    external_link=result.get("webLink"),
                    provider=self.provider_name
                )
            
            return AppointmentResult(
                success=False,
                error_message="Update failed",
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
        """Cancel (delete) an Outlook event"""
        if not self.is_authenticated:
            return False
        
        try:
            result = await self._make_graph_request(
                "DELETE",
                f"/me/events/{external_id}"
            )
            
            if result:
                logger.info(f"✅ Cancelled Outlook event: {external_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error cancelling Outlook event: {e}")
            return False
    
    async def get_appointment(
        self,
        external_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get details of a specific Outlook event"""
        if not self.is_authenticated:
            return None
        
        try:
            result = await self._make_graph_request(
                "GET",
                f"/me/events/{external_id}"
            )
            
            if result:
                return {
                    "id": result["id"],
                    "title": result.get("subject"),
                    "description": result.get("body", {}).get("content"),
                    "start": result.get("start", {}).get("dateTime"),
                    "end": result.get("end", {}).get("dateTime"),
                    "location": result.get("location", {}).get("displayName"),
                    "link": result.get("webLink"),
                    "status": "confirmed" if not result.get("isCancelled") else "cancelled",
                    "attendees": result.get("attendees", [])
                }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting Outlook event: {e}")
            return None
