"""
Gmail Tool for ARIA
Uses Gmail API v1 with OAuth2 for unlimited free access.

Setup:
1. Enable "Gmail API" in Google Cloud Console
2. Create OAuth 2.0 Client ID (Desktop app) — can reuse same credentials as Calendar
3. Download credentials.json to data/google_credentials.json
4. First run will open browser for one-time auth
"""
import os
import json
import base64
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CREDS_FILE = BASE_DIR / "data" / "google_credentials.json"
TOKEN_FILE = BASE_DIR / "data" / "google_gmail_token.json"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify"
]


def _get_service():
    """Authenticate and return Gmail API service."""
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDS_FILE.exists():
                return None, "OAuth credentials not found. Place google_credentials.json in data/ folder."
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    service = build("gmail", "v1", credentials=creds)
    return service, None


def send_email(to: str, subject: str, body: str, attachment_path: str = None) -> dict:
    """
    Send an email via Gmail.

    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body text
        attachment_path: Optional file path to attach

    Returns:
        dict with success and message
    """
    service, error = _get_service()
    if error:
        return {"success": False, "error": error}

    try:
        if attachment_path and os.path.exists(attachment_path):
            message = MIMEMultipart()
            message["to"] = to
            message["subject"] = subject
            message.attach(MIMEText(body, "plain"))

            # Attach file
            filename = os.path.basename(attachment_path)
            with open(attachment_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename={filename}")
                message.attach(part)
        else:
            message = MIMEText(body)
            message["to"] = to
            message["subject"] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        result = service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()

        return {
            "success": True,
            "message_id": result.get("id"),
            "message": f"Email sent to {to}."
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def read_emails(max_results: int = 5, unread_only: bool = True) -> dict:
    """
    Read recent emails from inbox.

    Args:
        max_results: Number of emails to return
        unread_only: Only show unread emails

    Returns:
        dict with success and email list
    """
    service, error = _get_service()
    if error:
        return {"success": False, "error": error}

    try:
        query = "is:unread" if unread_only else ""
        results = service.users().messages().list(
            userId="me", maxResults=max_results, q=query, labelIds=["INBOX"]
        ).execute()

        messages = results.get("messages", [])
        emails = []

        for msg_ref in messages:
            msg = service.users().messages().get(
                userId="me", id=msg_ref["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()

            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            emails.append({
                "id": msg_ref["id"],
                "from": headers.get("From", "Unknown"),
                "subject": headers.get("Subject", "No subject"),
                "date": headers.get("Date", ""),
                "snippet": msg.get("snippet", "")
            })

        if not emails:
            return {"success": True, "emails": [], "message": "No unread emails." if unread_only else "Inbox empty."}

        return {"success": True, "emails": emails,
                "message": f"Found {len(emails)} email(s)."}

    except Exception as e:
        return {"success": False, "error": str(e)}


def search_emails(query: str, max_results: int = 5) -> dict:
    """
    Search emails by query.

    Args:
        query: Search query (same as Gmail search syntax)
        max_results: Number of results

    Returns:
        dict with success and email list
    """
    service, error = _get_service()
    if error:
        return {"success": False, "error": error}

    try:
        results = service.users().messages().list(
            userId="me", maxResults=max_results, q=query
        ).execute()

        messages = results.get("messages", [])
        emails = []

        for msg_ref in messages:
            msg = service.users().messages().get(
                userId="me", id=msg_ref["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()

            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            emails.append({
                "id": msg_ref["id"],
                "from": headers.get("From", "Unknown"),
                "subject": headers.get("Subject", "No subject"),
                "date": headers.get("Date", ""),
                "snippet": msg.get("snippet", "")
            })

        return {"success": True, "emails": emails,
                "message": f"Found {len(emails)} result(s) for '{query}'."}

    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "auth":
        print("Authenticating with Gmail...")
        svc, err = _get_service()
        if err:
            print(f"Error: {err}")
        else:
            print("✅ Authenticated! Token saved.")
            result = read_emails(3)
            if result["success"]:
                print(f"\nRecent emails:")
                for e in result["emails"]:
                    print(f"  - {e['from']}: {e['subject']}")
            else:
                print(f"Error: {result['error']}")
    else:
        print("Usage: python google_gmail.py auth")
