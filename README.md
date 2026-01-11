# NEF Watcher

Automatically download PACER court documents from email notifications and route them to client folders.

## What It Does

When you receive a NEF (Notice of Electronic Filing) email from a federal court:
1. NEF Watcher detects the email in your inbox
2. Downloads the document using the free-look link (no PACER fees!)
3. Saves it to the correct client folder based on case number
4. Unknown cases go to an `_UNROUTED` folder for you to organize later

## Quick Start with Claude Code

The easiest way to set this up is with [Claude Code](https://claude.com/product/claude-code) (the terminal app):

```bash
# Clone the repo
git clone https://github.com/tcole333/nef-watcher
cd nef-watcher

# Open Claude Code and run the setup wizard
claude
# Then ask claude to help you get it set up
```

The setup wizard will walk you through everything.

## Manual Setup

### 1. Install Dependencies
```bash
pip3 install flask requests
```

### 2. Configure Email
Edit `config.json`:
```json
{
  "email_provider": "gmail",
  "email_user": "your.email@gmail.com",
  "email_password": "xxxx xxxx xxxx xxxx",
  "default_folder": "~/Documents/Legal/_UNROUTED",
  "cases": {}
}
```

Supported providers: `gmail`, `outlook`, `yahoo`, `icloud`, or `custom` (with your own IMAP server).

You'll need an App Password (not your regular password) - the setup wizard will help you create one.

### 3. Run It
```bash
# Start the web interface
python3 web_app.py

# Or run the watcher directly
python3 nef_watcher.py
```

### 4. Set Up Automatic Running
```bash
# Check for new documents every 2 minutes
crontab -e
# Add: */2 * * * * /usr/bin/python3 /path/to/nef_watcher.py >> /tmp/nef.log 2>&1
```

## Web Interface

The web UI at http://localhost:5050 lets you:
- View and manage case-to-folder mappings
- See unmapped cases and quickly assign them to folders
- Files are automatically moved when you create a mapping
- Run the watcher manually
- Update settings

## How It Works

NEF emails contain a "free look" link that lets you download the document once without PACER charges. The link includes a `magic_num` parameter that expires after first use or 15 days.

NEF Watcher:
1. Connects to your email via IMAP
2. Searches for emails from `@uscourts.gov` with "Notice of Electronic Filing" in subject
3. Extracts the case number and document URL from the email
4. Downloads the PDF via the free-look link
5. Routes it to the mapped folder (or `_UNROUTED` if unknown)

## Requirements

- Python 3.7+
- Gmail account with App Password (or other IMAP-enabled email)
- macOS, Linux, or Windows with Python

## License

MIT
