# NEF Watcher - Claude Code Instructions

## What This Project Does

NEF Watcher automatically downloads PACER court documents from email notifications and saves them to the correct client folders. It's designed for attorneys who receive NEF (Notice of Electronic Filing) emails from federal courts.

## For New Users

**Run `/setup` to start the guided setup wizard.** This will walk you through:
- Connecting your email account
- Setting up folder locations
- Adding case-to-folder mappings
- Configuring automatic running

## Project Structure

```
nef_watcher.py    - Main script that checks email and downloads documents
web_app.py        - Web interface for managing cases and settings
config.json       - All configuration (email, folders, case mappings)
activity.log      - Recent download history
templates/        - Web UI templates
```

## Common Tasks

### Start the Web Interface
```bash
python3 web_app.py
# Opens at http://localhost:5050
```

### Run the Watcher Manually
```bash
python3 nef_watcher.py
```

### Add a New Case Mapping
Either use the web interface at http://localhost:5050, or edit config.json:
```json
{
  "cases": {
    "1:24-cv-00123": "~/Documents/Legal/Clients/ClientName"
  }
}
```

### Check Cron Status
```bash
crontab -l | grep nef_watcher
```

## Customization Notes

### Different Email Providers
The current implementation uses Gmail IMAP. To support other providers:
- Outlook: Change IMAP server to `outlook.office365.com`
- Other: Update the IMAP server in `nef_watcher.py`

### Different Court Districts
Currently optimized for EDNC (Eastern District of North Carolina). The email parsing should work for other districts but may need regex adjustments for:
- Case number formats
- Email subject patterns
- Document URL formats

### NEF Email Format
The parser expects emails from `@uscourts.gov` with "Notice of Electronic Filing" in the subject. Key extraction patterns:
- Case number: `\d:\d{2}-[a-z]{2}-\d+` (e.g., 1:24-cv-00123)
- Document URL: Contains `ecf.*.uscourts.gov/doc1/` with `magic_num=` parameter

## Troubleshooting

### "No NEF emails found"
- Verify you have NEF emails in your inbox from @uscourts.gov
- Check the email subject contains "Notice of Electronic Filing"

### "Login failed"
- Use a Gmail App Password, not your regular password
- Enable 2-Factor Authentication on your Google account
- Generate App Password at https://myaccount.google.com/apppasswords

### "Free-look link expired"
- The magic_num links expire after first use or 15 days
- Run the watcher more frequently (every 2-5 minutes recommended)

### Documents going to _UNROUTED
- Add a case mapping via the web interface
- The file will be moved when you create the mapping
