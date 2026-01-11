#!/usr/bin/env python3
"""
NEF Watcher - Downloads PACER documents from email NEF notifications

Monitors your email for NEF (Notice of Electronic Filing) emails from PACER,
downloads the documents via free look links, and routes them to case-specific folders.

Supports Gmail, Outlook/Microsoft 365, and other IMAP-enabled providers.
"""
import imaplib
import email
import html
import json
import re
import requests
from pathlib import Path
from datetime import date, datetime

# Config file location
CONFIG_FILE = Path(__file__).parent / "config.json"
LOG_FILE = Path(__file__).parent / "activity.log"


def load_config():
    """Load configuration from config.json."""
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"Config file not found: {CONFIG_FILE}")

    with open(CONFIG_FILE) as f:
        return json.load(f)


def log_activity(message, case_num=None, filename=None, status="info"):
    """Log activity to the log file for the web UI to display."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "message": message,
        "case_num": case_num,
        "filename": filename,
        "status": status
    }

    # Append to log file
    logs = []
    if LOG_FILE.exists():
        try:
            with open(LOG_FILE) as f:
                logs = json.load(f)
        except json.JSONDecodeError:
            logs = []

    logs.append(entry)

    # Keep only last 100 entries
    logs = logs[-100:]

    with open(LOG_FILE, "w") as f:
        json.dump(logs, f, indent=2)


def get_processed_ids(config):
    """Load set of already-processed message IDs."""
    processed_file = Path(config["processed_file"]).expanduser()
    if processed_file.exists():
        return set(processed_file.read_text().splitlines())
    return set()


def mark_processed(config, msg_id):
    """Append message ID to processed file."""
    processed_file = Path(config["processed_file"]).expanduser()
    with open(processed_file, "a") as f:
        f.write(msg_id + "\n")


def parse_nef_email(msg):
    """
    Extract case number and document URL from NEF email.

    Returns:
        Tuple of (case_number, document_url, subject)
    """
    # Get email body (prefer plain text, fall back to HTML)
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode(errors="replace")
                break
            elif content_type == "text/html" and not body:
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode(errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode(errors="replace")

    # Decode HTML entities (e.g., &amp; -> &)
    body = html.unescape(body)

    # Extract case number - pattern like 1:23-cv-00456 or 9:21-cv-00029-MJT
    # Can appear anywhere in the body (not just after "Case Number:")
    case_match = re.search(r"(\d:\d{2}-[a-z]{2}-\d+(?:-[A-Z]+)?)", body, re.IGNORECASE)
    case_num = case_match.group(1) if case_match else None

    # Extract document URL with magic_num parameter (free look link)
    # Format: https://ecf.txed.uscourts.gov/doc1/175011894066?caseid=204173&de_seq_num=37&magic_num=11505292
    # The URL appears in href attributes in HTML or as plain text
    url_match = re.search(
        r'(https://ecf\.[a-z]+\.uscourts\.gov/doc1/\d+\?[^"\s<>]+magic_num=\d+)',
        body,
        re.IGNORECASE
    )
    doc_url = url_match.group(1) if url_match else None

    # Get subject for filename
    subject = str(msg.get("Subject", ""))

    return case_num, doc_url, subject


def download_pdf(url, folder, subject):
    """
    Download PDF from URL and save to folder.

    Args:
        url: The document URL (with magic_num for free look)
        folder: Destination folder path
        subject: Email subject (used in filename)

    Returns:
        Tuple of (success, filepath or None)
    """
    folder = Path(folder).expanduser()
    folder.mkdir(parents=True, exist_ok=True)

    # Generate filename: 2024-01-15_Motion_to_Dismiss.pdf
    safe_subject = re.sub(r"[^\w\s-]", "", subject)[:50].strip()
    safe_subject = re.sub(r"\s+", "_", safe_subject)
    filename = f"{date.today().isoformat()}_{safe_subject}.pdf"
    filepath = folder / filename

    # Avoid overwriting existing files
    counter = 1
    while filepath.exists():
        filepath = folder / f"{date.today().isoformat()}_{safe_subject}_{counter}.pdf"
        counter += 1

    # Download the PDF
    try:
        resp = requests.get(url, timeout=30)
        content_type = resp.headers.get("content-type", "")

        if resp.status_code == 200 and "pdf" in content_type.lower():
            filepath.write_bytes(resp.content)
            print(f"✓ Saved: {filepath}")
            return True, filepath
        elif resp.status_code == 200 and "html" in content_type.lower():
            # Free-look link expired - returns PACER login page
            print(f"✗ Free-look link expired (got login page instead of PDF)")
            print(f"  You'll need to download manually from PACER")
            return False, None
        else:
            print(f"✗ Download failed: {url}")
            print(f"  Status: {resp.status_code}, Content-Type: {content_type}")
            return False, None
    except requests.RequestException as e:
        print(f"✗ Network error: {e}")
        return False, None


def get_imap_server(config):
    """Get IMAP server settings based on provider or custom config."""
    # Provider presets
    PROVIDERS = {
        "gmail": {
            "server": "imap.gmail.com",
            "port": 993,
            "help_url": "https://myaccount.google.com/apppasswords"
        },
        "outlook": {
            "server": "outlook.office365.com",
            "port": 993,
            "help_url": "https://support.microsoft.com/en-us/account-billing/app-passwords"
        },
        "yahoo": {
            "server": "imap.mail.yahoo.com",
            "port": 993,
            "help_url": "https://help.yahoo.com/kb/generate-third-party-passwords-sln15241.html"
        },
        "icloud": {
            "server": "imap.mail.me.com",
            "port": 993,
            "help_url": "https://support.apple.com/en-us/HT204397"
        }
    }

    provider = config.get("email_provider", "gmail").lower()

    if provider == "custom":
        return {
            "server": config.get("imap_server", ""),
            "port": config.get("imap_port", 993),
            "help_url": None
        }

    return PROVIDERS.get(provider, PROVIDERS["gmail"])


def main():
    """Main entry point - check email for NEF emails and download documents."""
    # Load config
    try:
        config = load_config()
    except FileNotFoundError as e:
        print(f"✗ {e}")
        return

    processed = get_processed_ids(config)
    cases = config.get("cases", {})
    default_folder = Path(config["default_folder"]).expanduser()

    # Get IMAP settings
    imap_settings = get_imap_server(config)
    provider = config.get("email_provider", "gmail")

    # Connect via IMAP
    print(f"Connecting to {imap_settings['server']}...")
    try:
        mail = imaplib.IMAP4_SSL(imap_settings["server"], imap_settings["port"])
        mail.login(config["email_user"], config["email_password"])
    except imaplib.IMAP4.error as e:
        print(f"✗ Login failed: {e}")
        if imap_settings.get("help_url"):
            print(f"  Make sure you're using an App Password, not your regular password.")
            print(f"  Generate one at: {imap_settings['help_url']}")
        else:
            print("  Check your email credentials and IMAP server settings.")
        log_activity(f"Login failed: {e}", status="error")
        return

    mail.select("inbox")

    # Search for NEF emails from uscourts.gov
    _, message_ids = mail.search(
        None, '(FROM "@uscourts.gov" SUBJECT "Notice of Electronic Filing")'
    )

    ids = message_ids[0].split()
    if not ids:
        print("No NEF emails found.")
        mail.close()
        mail.logout()
        return

    print(f"Found {len(ids)} NEF email(s)")

    new_count = 0
    for msg_id in ids:
        msg_id_str = msg_id.decode()

        # Skip already-processed emails
        if msg_id_str in processed:
            continue

        new_count += 1
        _, msg_data = mail.fetch(msg_id, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])

        case_num, doc_url, subject = parse_nef_email(msg)
        print(f"\nProcessing: {subject[:60]}...")

        if doc_url:
            # Route to case folder or default
            folder = cases.get(case_num, str(default_folder))
            folder = Path(folder).expanduser()

            if case_num and case_num not in cases:
                print(f"  ⚠ Unknown case {case_num}, saving to _UNROUTED")
                log_activity(
                    f"Unknown case {case_num}, saved to _UNROUTED",
                    case_num=case_num,
                    status="warning"
                )

            success, filepath = download_pdf(doc_url, folder, subject)
            if success:
                mark_processed(config, msg_id_str)
                log_activity(
                    f"Downloaded document",
                    case_num=case_num,
                    filename=filepath.name if filepath else None,
                    status="success"
                )
            else:
                log_activity(
                    f"Download failed - free look expired",
                    case_num=case_num,
                    status="error"
                )
        else:
            print(f"  ⚠ No document URL found in email")
            mark_processed(config, msg_id_str)  # Mark processed to avoid retrying

    mail.close()
    mail.logout()

    if new_count == 0:
        print("No new emails to process.")
    else:
        print(f"\nProcessed {new_count} new email(s)")


if __name__ == "__main__":
    main()
