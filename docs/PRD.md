# NEF Watcher PRD

## Overview

A Python script that monitors a Gmail inbox for PACER NEF (Notice of Electronic Filing) emails from the Eastern District of North Carolina, automatically downloads the associated court documents, and routes them to the appropriate local folder based on case number.

## Goal

Attorney receives NEF email → document automatically appears in the right client folder on their Mac within 5 minutes, no manual intervention.

## Architecture

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   Gmail     │ ──▶  │   Parser    │ ──▶  │  Downloader │ ──▶  │   Router    │
│  (IMAP)     │      │ (extract    │      │  (free look │      │ (case →     │
│             │      │  case/link) │      │   PDF grab) │      │  folder)    │
└─────────────┘      └─────────────┘      └─────────────┘      └─────────────┘
```

Single Python script, runs via cron every few minutes.

## Components

### 1. Gmail Monitor
- Uses IMAP with App Password (simpler than OAuth2)
- Searches for emails matching:
  - From: `@uscourts.gov`
  - Subject: contains "Notice of Electronic Filing"
- Tracks processed message IDs in `~/.nef-processed.txt`

### 2. NEF Parser

NEF emails contain structured fields. Key extraction patterns:

| Field | Regex Pattern |
|-------|--------------|
| Case Number | `r"Case Number:\s*(\d:\d{2}-\w+-\d+)"` |
| Document URL | `r"(https://ecf\.[^/]+\.uscourts\.gov/doc1/[^\s\"<>]+)"` |

**Free Look URL Format:**
```
https://ecf.nced.uscourts.gov/doc1/01713718205?caseid=75736&de_seq_num=30&magic_num=77910494
```
- The `magic_num` parameter enables free one-time download
- Expires after first use OR 15 days

**Case Number Format (EDNC):**
- Pattern: `\d:\d{2}-(cv|cr)-\d+`
- Examples: `1:23-cv-00456`, `5:24-cr-00123`

### 3. Document Downloader
- Downloads PDF via free look URL (no auth required)
- Simple `requests.get()` - no session management needed
- Validates response is actually a PDF

### 4. File Router
- Maps case numbers to local folders (hardcoded in script)
- Filename format: `{date}_{description}.pdf`
  - e.g., `2024-01-15_Motion_to_Dismiss.pdf`
- Unknown cases go to `_UNROUTED/` folder
- Avoids overwriting: appends `_1`, `_2` etc if file exists

## Configuration

Edit variables at top of `nef_watcher.py`:

```python
# Gmail credentials
GMAIL_USER = "your.email@gmail.com"
GMAIL_APP_PASSWORD = "xxxx xxxx xxxx xxxx"  # App Password, not real password

# Case → folder mapping
CASE_FOLDERS = {
    "1:23-cv-00456": Path.home() / "Documents/Legal/Clients/Smith/EDNC",
    "1:24-cv-00789": Path.home() / "Documents/Legal/Clients/Jones/EDNC",
}

# Fallback for unknown cases
DEFAULT_FOLDER = Path.home() / "Documents/Legal/EDNC/_UNROUTED"
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| IMAP login fails | Print error message with App Password instructions |
| Free look link expired | Download fails, user needs to get from PACER manually |
| Case not in routing config | Save to `_UNROUTED` folder |
| Network timeout | requests timeout after 30s, email stays unprocessed |
| Malformed NEF email | Mark as processed, skip |

## Installation & Setup

### 1. Install dependencies
```bash
pip install requests
```

### 2. Create Gmail App Password
1. Go to https://myaccount.google.com/apppasswords
2. Generate a new app password for "Mail"
3. Copy the 16-character password

### 3. Configure the script
Edit `nef_watcher.py`:
- Set `GMAIL_USER` to your Gmail address
- Set `GMAIL_APP_PASSWORD` to the app password
- Add case→folder mappings to `CASE_FOLDERS`

### 4. Test manually
```bash
python3 nef_watcher.py
```

### 5. Set up cron (optional)
```bash
crontab -e
# Add this line to run every 5 minutes:
*/5 * * * * /usr/bin/python3 /path/to/nef_watcher.py >> /tmp/nef.log 2>&1
```

## Nice-to-Haves (Not MVP)

- [ ] Desktop notification when document downloaded
- [ ] CLI command to add new case mapping
- [ ] PACER authenticated fallback for expired free look links
- [ ] Support for multiple districts (not just EDNC)
- [ ] Web UI for configuration

## Out of Scope

- OCR or text extraction from PDFs
- Integration with legal practice management software
- Multi-user / server deployment
- Automatic case-to-client matching (requires manual config)

## References

- [Free Law Project's juriscraper](https://github.com/freelawproject/juriscraper) - NEF email parsing patterns
- [PACER URL formats](https://github.com/freelawproject/juriscraper/blob/main/juriscraper/pacer/notes.md)
