"""
Google Calendar Tool for ARIA
Uses Google Calendar API v3 with OAuth2 for unlimited free access.

Setup:
1. Enable "Google Calendar API" in Google Cloud Console
2. Create OAuth 2.0 Client ID (Desktop app)
3. Download credentials.json to data/google_credentials.json
4. First run will open browser for one-time auth
"""
import os
import json
import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CREDS_FILE = BASE_DIR / "data" / "google_credentials.json"
TOKEN_FILE = BASE_DIR / "data" / "google_calendar_token.json"
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _get_service():
    """Authenticate and return Calendar API service."""
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = None

    # Load existing token
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    # Refresh or get new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDS_FILE.exists():
                return None, "OAuth credentials not found. Place google_credentials.json in data/ folder."
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for next time
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    service = build("calendar", "v3", credentials=creds)
    return service, None


def list_events(max_results: int = 10, date: str = None) -> dict:
    """
    List upcoming calendar events.

    Args:
        max_results: Number of events to return (default 10)
        date: Specific date in YYYY-MM-DD format (default: today)

    Returns:
        dict with success, events list, and message
    """
    service, error = _get_service()
    if error:
        return {"success": False, "error": error}

    try:
        if date:
            start = datetime.datetime.fromisoformat(date)
        else:
            start = datetime.datetime.now()

        time_min = start.replace(hour=0, minute=0, second=0).isoformat() + "Z"
        time_max = start.replace(hour=23, minute=59, second=59).isoformat() + "Z"

        result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        events = result.get("items", [])
        event_list = []
        for event in events:
            start_time = event["start"].get("dateTime", event["start"].get("date"))
            event_list.append({
                "summary": event.get("summary", "No title"),
                "start": start_time,
                "location": event.get("location", ""),
                "id": event.get("id")
            })

        if not event_list:
            return {"success": True, "events": [], "message": "No events found for this day."}

        return {"success": True, "events": event_list,
                "message": f"Found {len(event_list)} event(s)."}

    except Exception as e:
        return {"success": False, "error": str(e)}


def create_event(summary: str, start_time: str, end_time: str = None,
                 description: str = "", location: str = "") -> dict:
    """
    Create a new calendar event.

    Args:
        summary: Event title
        start_time: Start time in "YYYY-MM-DD HH:MM" or "HH:MM" (today) format
        end_time: End time (default: 1 hour after start)
        description: Optional description
        location: Optional location

    Returns:
        dict with success and event details
    """
    service, error = _get_service()
    if error:
        return {"success": False, "error": error}

    try:
        # Parse start time
        now = datetime.datetime.now()
        if len(start_time) <= 5:  # "HH:MM" format
            hour, minute = map(int, start_time.split(":"))
            start_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            start_dt = datetime.datetime.fromisoformat(start_time.replace(" ", "T"))

        # Default end = 1 hour after start
        if end_time:
            if len(end_time) <= 5:
                hour, minute = map(int, end_time.split(":"))
                end_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            else:
                end_dt = datetime.datetime.fromisoformat(end_time.replace(" ", "T"))
        else:
            end_dt = start_dt + datetime.timedelta(hours=1)

        timezone = "Asia/Kolkata"  # IST

        event = {
            "summary": summary,
            "location": location,
            "description": description,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": timezone},
        }

        created = service.events().insert(calendarId="primary", body=event).execute()

        return {
            "success": True,
            "event_id": created.get("id"),
            "link": created.get("htmlLink"),
            "message": f"Event '{summary}' created at {start_time}."
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def delete_event(event_id: str) -> dict:
    """Delete a calendar event by ID."""
    service, error = _get_service()
    if error:
        return {"success": False, "error": error}

    try:
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        return {"success": True, "message": f"Event {event_id} deleted."}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "auth":
        print("Authenticating with Google Calendar...")
        svc, err = _get_service()
        if err:
            print(f"Error: {err}")
        else:
            print("✅ Authenticated! Token saved.")
            result = list_events(5)
            if result["success"]:
                print(f"\nUpcoming events:")
                for e in result["events"]:
                    print(f"  - {e['start']}: {e['summary']}")
            else:
                print(f"Error: {result['error']}")
    else:
        print("Usage: python google_calendar.py auth")
