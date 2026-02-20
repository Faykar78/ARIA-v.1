import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
import logging

# ==============================================================================
# 🔒 SECURITY CONFIGURATION
# ==============================================================================
EMAIL_CONFIG = {
    "email": "harshamerugu78@gmail.com",
    "password": "srgs pajs loqm iuws ",  # Generate App Password if using Gmail 2FA
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "imap_server": "imap.gmail.com",
    "imap_port": 993
}
# ==============================================================================

logger = logging.getLogger(__name__)

class EmailBridge:
    def __init__(self):
        self.config = EMAIL_CONFIG

    def _is_configured(self):
        return (self.config["email"] != "YOUR_EMAIL@gmail.com" and 
                self.config["password"] != "YOUR_APP_PASSWORD_HERE")

    def send_email(self, to_email: str, subject: str, body: str):
        """Sends an email via SMTP."""
        if not self._is_configured():
            return {"success": False, "error": "Email not configured in src/bridges/email_bridge.py"}

        try:
            msg = MIMEMultipart()
            msg['From'] = self.config["email"]
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            server = smtplib.SMTP(self.config["smtp_server"], self.config["smtp_port"])
            server.starttls()
            server.login(self.config["email"], self.config["password"])
            text = msg.as_string()
            server.sendmail(self.config["email"], to_email, text)
            server.quit()
            
            logger.info(f"✅ Email sent to {to_email}")
            return {"success": True}
        except Exception as e:
            logger.error(f"❌ Email Send Error: {e}")
            return {"success": False, "error": str(e)}

    def read_emails(self, limit=5, unread_only=True):
        """Reads recent emails via IMAP."""
        if not self._is_configured():
            return {"success": False, "error": "Email not configured"}

        try:
            mail = imaplib.IMAP4_SSL(self.config["imap_server"])
            mail.login(self.config["email"], self.config["password"])
            mail.select("inbox")

            criteria = "UNSEEN" if unread_only else "ALL"
            status, messages = mail.search(None, criteria)
            
            if status != "OK":
                return {"success": False, "error": "Failed to search emails"}

            email_ids = messages[0].split()
            # Get latest 'limit' emails
            latest_email_ids = email_ids[-limit:]
            
            results = []
            
            for e_id in reversed(latest_email_ids):
                _, msg_data = mail.fetch(e_id, "(RFC822)")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        # Decode subject
                        subject, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding if encoding else "utf-8")
                        
                        # Get Sender
                        from_ = msg.get("From")
                        
                        # Get Body
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    body = part.get_payload(decode=True).decode()
                                    break
                        else:
                            body = msg.get_payload(decode=True).decode()

                        results.append({
                            "id": e_id.decode(),
                            "from": from_,
                            "subject": subject,
                            "body": body[:200] + "..." if len(body) > 200 else body
                        })
            
            mail.close()
            mail.logout()
            return {"success": True, "emails": results, "count": len(results)}

        except Exception as e:
            logger.error(f"❌ Email Read Error: {e}")
            return {"success": False, "error": str(e)}

# Singleton
email_bridge = EmailBridge()
