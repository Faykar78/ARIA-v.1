"""
WhatsApp MCP Client for ARIA
============================
A client that interfaces with the whatsapp-mcp Go bridge to send/receive messages.
Uses the same HTTP API as the MCP server on localhost:8080.

Prerequisites:
1. Go bridge must be running: cd whatsapp-mcp/whatsapp-bridge && go run main.go
2. Scan QR code with WhatsApp mobile app on first run
"""

import sqlite3
import requests
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Any
from dataclasses import dataclass

# Configuration
WHATSAPP_MCP_PATH = os.path.join(os.path.dirname(__file__), '../../whatsapp-mcp')
MESSAGES_DB_PATH = os.path.join(WHATSAPP_MCP_PATH, 'whatsapp-bridge', 'store', 'messages.db')
WHATSAPP_API_BASE_URL = "http://localhost:8080/api"


@dataclass
class Contact:
    phone_number: str
    name: Optional[str]
    jid: str


@dataclass
class Chat:
    jid: str
    name: Optional[str]
    last_message_time: Optional[datetime]
    last_message: Optional[str] = None


class WhatsAppMCPClient:
    """Client for WhatsApp MCP bridge"""
    
    def __init__(self, db_path: str = None, api_url: str = None):
        self.db_path = db_path or MESSAGES_DB_PATH
        self.api_url = api_url or WHATSAPP_API_BASE_URL
    
    def is_bridge_running(self) -> bool:
        """Check if the Go bridge is running"""
        try:
            response = requests.get(f"{self.api_url}/status", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def search_contacts(self, query: str) -> List[Contact]:
        """Search for contacts by name or phone number"""
        try:
            if not os.path.exists(self.db_path):
                return []
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            search_pattern = f'%{query}%'
            cursor.execute("""
                SELECT DISTINCT jid, name
                FROM chats
                WHERE (LOWER(name) LIKE LOWER(?) OR LOWER(jid) LIKE LOWER(?))
                    AND jid NOT LIKE '%@g.us'
                ORDER BY name, jid
                LIMIT 20
            """, (search_pattern, search_pattern))
            
            contacts = []
            for row in cursor.fetchall():
                contacts.append(Contact(
                    phone_number=row[0].split('@')[0],
                    name=row[1],
                    jid=row[0]
                ))
            
            conn.close()
            return contacts
            
        except Exception as e:
            print(f"[WhatsApp MCP] Search error: {e}")
            return []
    
    def list_chats(self, limit: int = 20) -> List[Chat]:
        """List recent chats"""
        try:
            if not os.path.exists(self.db_path):
                return []
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT c.jid, c.name, c.last_message_time, m.content
                FROM chats c
                LEFT JOIN messages m ON c.jid = m.chat_jid 
                    AND c.last_message_time = m.timestamp
                ORDER BY c.last_message_time DESC
                LIMIT ?
            """, (limit,))
            
            chats = []
            for row in cursor.fetchall():
                chats.append(Chat(
                    jid=row[0],
                    name=row[1],
                    last_message_time=datetime.fromisoformat(row[2]) if row[2] else None,
                    last_message=row[3]
                ))
            
            conn.close()
            return chats
            
        except Exception as e:
            print(f"[WhatsApp MCP] List chats error: {e}")
            return []
    
    def find_contact_by_name(self, name: str) -> Optional[str]:
        """Find a contact's JID by name (case-insensitive)"""
        contacts = self.search_contacts(name)
        if contacts:
            # Prefer exact match
            for c in contacts:
                if c.name and c.name.lower() == name.lower():
                    return c.jid
            # Otherwise return first match
            return contacts[0].jid
        return None
    
    def send_message(self, recipient: str, message: str) -> Tuple[bool, str]:
        """
        Send a WhatsApp message.
        
        Args:
            recipient: Phone number (without +) or JID or contact name
            message: Message text
        
        Returns:
            Tuple of (success, status_message)
        """
        try:
            # Check if bridge is running
            if not self.is_bridge_running():
                return False, "WhatsApp bridge not running. Start with: cd whatsapp-mcp/whatsapp-bridge && go run main.go"
            
            # If recipient looks like a name (has spaces or no @), try to find contact
            if ' ' in recipient or '@' not in recipient:
                if not recipient.isdigit():
                    jid = self.find_contact_by_name(recipient)
                    if jid:
                        recipient = jid
                    else:
                        # Try searching
                        contacts = self.search_contacts(recipient)
                        if contacts:
                            recipient = contacts[0].jid
                        else:
                            return False, f"Contact '{recipient}' not found"
            
            # Format as JID if it's just a phone number
            if '@' not in recipient:
                recipient = f"{recipient}@s.whatsapp.net"
            
            url = f"{self.api_url}/send"
            payload = {
                "recipient": recipient,
                "message": message
            }
            
            response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return result.get("success", False), result.get("message", "Unknown response")
            else:
                return False, f"HTTP {response.status_code}: {response.text}"
                
        except requests.exceptions.ConnectionError:
            return False, "WhatsApp bridge not running. Start with: cd whatsapp-mcp/whatsapp-bridge && go run main.go"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def send_file(self, recipient: str, file_path: str) -> Tuple[bool, str]:
        """Send a file via WhatsApp"""
        try:
            if not self.is_bridge_running():
                return False, "WhatsApp bridge not running"
            
            if not os.path.exists(file_path):
                return False, f"File not found: {file_path}"
            
            # Find/format recipient
            if ' ' in recipient or '@' not in recipient:
                if not recipient.isdigit():
                    jid = self.find_contact_by_name(recipient)
                    if jid:
                        recipient = jid
            
            if '@' not in recipient:
                recipient = f"{recipient}@s.whatsapp.net"
            
            url = f"{self.api_url}/send"
            payload = {
                "recipient": recipient,
                "media_path": os.path.abspath(file_path)
            }
            
            response = requests.post(url, json=payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                return result.get("success", False), result.get("message", "Unknown response")
            else:
                return False, f"HTTP {response.status_code}: {response.text}"
                
        except Exception as e:
            return False, f"Error: {str(e)}"


# Singleton instance for ARIA
_client: Optional[WhatsAppMCPClient] = None

def get_client() -> WhatsAppMCPClient:
    """Get or create the WhatsApp MCP client singleton"""
    global _client
    if _client is None:
        _client = WhatsAppMCPClient()
    return _client


# Convenience functions for ARIA

def send_whatsapp_mcp(contact: str, message: str) -> Dict[str, Any]:
    """
    Send WhatsApp message via MCP bridge.
    
    Args:
        contact: Contact name or phone number
        message: Message to send
    
    Returns:
        Dict with success status and message
    """
    client = get_client()
    success, status = client.send_message(contact, message)
    return {"success": success, "message": status}


def search_whatsapp_contacts(query: str) -> List[Dict[str, Any]]:
    """Search WhatsApp contacts by name or number"""
    client = get_client()
    contacts = client.search_contacts(query)
    return [{"name": c.name, "phone": c.phone_number, "jid": c.jid} for c in contacts]


def list_whatsapp_chats(limit: int = 20) -> List[Dict[str, Any]]:
    """List recent WhatsApp chats"""
    client = get_client()
    chats = client.list_chats(limit)
    return [{"name": c.name, "jid": c.jid, "last_message": c.last_message} for c in chats]


def check_whatsapp_bridge() -> Dict[str, Any]:
    """Check if WhatsApp bridge is running"""
    client = get_client()
    running = client.is_bridge_running()
    return {"running": running, "api_url": client.api_url}


# Test
if __name__ == "__main__":
    import sys
    
    client = WhatsAppMCPClient()
    
    if len(sys.argv) > 2:
        contact = sys.argv[1]
        message = " ".join(sys.argv[2:])
        print(f"Sending to {contact}: {message}")
        success, status = client.send_message(contact, message)
        print(f"{'✅' if success else '❌'} {status}")
    else:
        print("WhatsApp MCP Client for ARIA")
        print("=" * 40)
        print(f"Bridge running: {client.is_bridge_running()}")
        print(f"\nRecent chats:")
        for chat in client.list_chats(10):
            print(f"  - {chat.name or chat.jid}: {chat.last_message[:50] if chat.last_message else 'No messages'}...")
        print(f"\nUsage: python whatsapp_mcp_client.py <contact> <message>")
