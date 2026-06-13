"""
ORION WhatsApp Connector — Twilio WhatsApp Business API
Auto-responds to WhatsApp messages from clients.
Requires: Twilio Account with WhatsApp Business API enabled
"""

import os, json, hashlib
from datetime import datetime, timezone

# To activate: import this in app.py and add webhook route.

# Setup steps:
# 1. Sign up at https://twilio.com
# 2. Enable WhatsApp Business API (requires approved business profile)
# 3. Get Account SID and Auth Token
# 4. Set env vars:
#    - TWILIO_ACCOUNT_SID
#    - TWILIO_AUTH_TOKEN
#    - TWILIO_WHATSAPP_NUMBER (format: whatsapp:+14155238886)
#    - WHATSAPP_ENABLED=true

CONFIG = {
    "enabled": os.getenv("WHATSAPP_ENABLED", "false").lower() == "true",
    "account_sid": os.getenv("TWILIO_ACCOUNT_SID", ""),
    "auth_token": os.getenv("TWILIO_AUTH_TOKEN", ""),
    "from_number": os.getenv("TWILIO_WHATSAPP_NUMBER", ""),
}


def handle_whatsapp_message(from_number, message_text, media_urls=None):
    """Process incoming WhatsApp message and generate reply."""
    if not CONFIG["enabled"]:
        return None

    conversation_id = hashlib.md5(f"whatsapp_{from_number}".encode()).hexdigest()

    # The response generation happens through the main app.py flow
    # This function returns the conversation_id for routing
    return {
        "conversation_id": conversation_id,
        "from_number": from_number,
        "platform": "whatsapp",
    }


def send_whatsapp(to_number, message_text):
    """Send WhatsApp message via Twilio API."""
    if not CONFIG["enabled"] or not all([CONFIG["account_sid"], CONFIG["auth_token"], CONFIG["from_number"]]):
        return False

    # Uses Twilio REST API
    # from twilio.rest import Client
    # client = Client(CONFIG["account_sid"], CONFIG["auth_token"])
    # message = client.messages.create(
    #     from_=CONFIG["from_number"],
    #     body=message_text,
    #     to=f'whatsapp:{to_number}'
    # )
    # return True

    return False
