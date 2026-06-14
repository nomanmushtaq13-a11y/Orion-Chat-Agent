"""
ORION Email Connector — Gmail IMAP integration
Reads emails via IMAP, auto-responds via SMTP using Groq + Supabase.
Requires: Gmail App Password (not OAuth2).
"""

import os, re, time, hashlib, email, imaplib, smtplib
from email.header import decode_header
from email.utils import parsedate_to_datetime, formataddr
from datetime import datetime, timezone

EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "")
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "")
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
EMAIL_CHECK_INTERVAL = int(os.getenv("EMAIL_CHECK_INTERVAL", "300"))

IMAP_SERVER = "imap.gmail.com"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

responded_email_ids = set()


def decode_mime_header(value):
    """Decode a MIME encoded header value to plain text."""
    if not value:
        return ""
    decoded_parts = decode_header(value)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(charset or "utf-8", errors="replace"))
            except (LookupError, UnicodeDecodeError):
                result.append(part.decode("utf-8", errors="replace"))
        else:
            result.append(part)
    return " ".join(result)


def extract_email_body(msg):
    """Extract plain text body from an email message."""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdisp = str(part.get("Content-Disposition", ""))
            if ctype == "text/plain" and "attachment" not in cdisp:
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        return payload.decode(charset, errors="replace")
                except Exception:
                    pass
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/html" and "attachment" not in str(part.get("Content-Disposition", "")):
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        text = re.sub(r"<[^>]+>", " ", payload.decode("utf-8", errors="replace"))
                        text = re.sub(r"\s+", " ", text).strip()
                        return text[:2000]
                except Exception:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
        except Exception:
            pass
    return ""


def normalize_subject(subject):
    """Strip Re:/Fwd: prefixes to group threads."""
    if not subject:
        return ""
    s = subject.strip()
    s = re.sub(r"^(Re|Fwd|FW|FWD|RE)\s*:?\s*", "", s).strip()
    return s.lower()


def check_email(mark_read=True):
    """Connect to Gmail via IMAP, fetch unread emails, return parsed list.
    If mark_read=True, marks processed emails as \\Seen on IMAP."""
    if not EMAIL_ENABLED or not EMAIL_APP_PASSWORD or not EMAIL_ADDRESS:
        return []

    results = []
    processed_uids = []
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, timeout=30)
        mail.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        mail.select("INBOX")

        status, messages = mail.search(None, "UNSEEN")
        if status != "OK" or not messages[0]:
            mail.logout()
            return []

        uids = messages[0].split()
        for uid in uids:
            uid_str = uid.decode()
            if uid_str in responded_email_ids:
                continue

            status, data = mail.fetch(uid, "(RFC822)")
            if status != "OK":
                continue

            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)

            sender = decode_mime_header(msg.get("From", ""))
            subject = decode_mime_header(msg.get("Subject", ""))
            message_id = msg.get("Message-ID", "")
            date_str = msg.get("Date", "")

            # Skip auto-replies, bounces, spam
            auto_reply = msg.get("Auto-Submitted", "")
            pref = msg.get("X-Precedence", "")
            if auto_reply.lower() in ("auto-replied", "auto-generated") or "bulk" in pref.lower():
                continue

            # Skip own emails
            sender_email = re.search(r"<([^>]+)>", sender)
            sender_addr = sender_email.group(1).lower() if sender_email else sender.lower().strip()
            if sender_addr == EMAIL_ADDRESS.lower():
                continue

            body = extract_email_body(msg)
            if not body or len(body.strip()) < 5:
                continue

            thread_key = normalize_subject(subject)
            if not thread_key:
                thread_key = hashlib.md5((sender_addr + date_str).encode()).hexdigest()[:16]

            parsed_date = None
            try:
                parsed_date = parsedate_to_datetime(date_str)
            except Exception:
                parsed_date = datetime.now(timezone.utc)

            results.append({
                "uid": uid_str,
                "sender": sender,
                "sender_email": sender_addr,
                "subject": subject,
                "thread_key": thread_key,
                "message_id": message_id,
                "body": body.strip(),
                "received_at": parsed_date.isoformat() if parsed_date else datetime.now(timezone.utc).isoformat(),
            })
            processed_uids.append(uid_str)

        if mark_read and processed_uids:
            mail.store(",".join(processed_uids), "+FLAGS", "\\Seen")

        mail.logout()
    except Exception as e:
        print(f"[Email Connector] Error checking email: {e}")

    return results


def send_email(to_addr, subject, body, in_reply_to=None, references=None):
    """Send an email reply via Gmail SMTP."""
    if not EMAIL_ENABLED or not EMAIL_APP_PASSWORD:
        return False

    try:
        msg = email.message.EmailMessage()
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = to_addr
        msg["Subject"] = subject
        msg["Date"] = email.utils.formatdate(localtime=True)

        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
            msg["References"] = (references or "") + " " + in_reply_to

        msg.set_content(body)

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"[Email Connector] Error sending email: {e}")
        return False
