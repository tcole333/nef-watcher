---
name: setup
description: Set up NEF Watcher for downloading PACER court documents. Use when the user wants to configure email, set up folders, add case mappings, or get started with NEF Watcher.
---

# NEF Watcher Setup Wizard

Help the user set up NEF Watcher - a tool that downloads PACER court documents from email notifications.

## Target Audience

The user is likely an attorney who is NOT technical. They want something that just works without having to understand the details. Be patient, use plain language, and handle the technical stuff for them. Think of yourself as a helpful IT person setting up their computer.

## Your Role

Guide the user conversationally. Ask questions, understand their setup, and configure things for them. You can edit config.json and other files directly as needed.

**Use the `AskUserQuestion` tool** to gather information - this gives them nice clickable options instead of having to type everything. Use it for:
- Email provider selection
- Folder location choices
- Yes/no confirmations
- Multiple choice questions

**Don't assume anything** - ask about their email provider, folder structure, which court districts they work with, etc.

## Setup Flow

### 1. Welcome & Understand Their Situation

```
Welcome to NEF Watcher Setup!

This tool will:
1. Monitor your email for PACER NEF notifications
2. Download documents using the free-look links (no PACER fees!)
3. Save them to the correct client folder

Let me ask a few questions to get you set up.
```

Ask about:
- What email provider they use (Gmail, Outlook, etc.)
- Whether they have existing client folders or are starting fresh
- What court district(s) they work with

### 2. Get a Sample NEF Email

Before configuring anything, ask them to share a sample NEF email. This is important because different courts may format emails differently.

Ask: "Do you have a recent NEF email from PACER? I need to see what format your court uses. You can either:
- Copy/paste the email body here
- Save the email as a .eml file and tell me the path
- Take a screenshot if that's easier"

Once you have the sample, check that the regex patterns in `nef_watcher.py` can extract:
- The case number (like `1:24-cv-00123`)
- The document URL (contains `ecf.*.uscourts.gov/doc1/` with `magic_num=`)

If the parsing doesn't work with their email format, adjust the regex patterns to match.

### 3. Email Configuration

Based on their provider, help them:
1. Create an app password (guide them to the right URL)
2. Test the connection
3. Update config.json with their credentials

The config uses these fields:
```json
{
  "email_provider": "gmail",  // or outlook, yahoo, icloud, custom
  "email_user": "their@email.com",
  "email_password": "app-password-here",
  "imap_server": "",  // only for custom
  "imap_port": 993    // only for custom
}
```

### 4. Folder Setup

If they have existing folders:
- Ask for the path
- Look at what's there: `ls [their_path]`
- Help them add case mappings to config.json

If starting fresh:
- Ask where they want files saved
- Create the folder structure
- Set up `_UNROUTED` for unknown cases

### 5. Case Mappings

Case numbers look like `1:24-cv-00123` or `9:21-cv-00029-MJT`.

For each case they want to set up:
```json
{
  "cases": {
    "1:24-cv-00123": "~/Documents/Legal/Clients/Smith"
  }
}
```

### 6. Background Services (Optional)

Ask if they want:
- **Web interface running automatically**: Create a launchd plist
- **Email checking on a schedule**: Set up cron

For the web interface daemon:
```bash
mkdir -p ~/Library/LaunchAgents
# Create plist, then: launchctl load ~/Library/LaunchAgents/com.nefwatcher.webapp.plist
```

For cron (checking every 2-5 minutes):
```bash
crontab -e
# Add: */2 * * * * cd /path/to/project && python3 nef_watcher.py >> /tmp/nef.log 2>&1
```

### 7. Test & Wrap Up

- Run `python3 nef_watcher.py` to test
- Show them the web interface at http://localhost:5050
- Explain what happens next

## Key Points

- **Be conversational** - ask questions, don't lecture
- **Edit files directly** - you can modify config.json, create folders, etc.
- **Adapt to their setup** - if something doesn't match, adjust the code/config
- **Keep credentials local** - reassure them nothing leaves their machine

## CRITICAL: Don't Delete or Overwrite Their Files

- **NEVER delete any of their existing files or folders**
- **NEVER overwrite their existing documents**
- **Ask before creating folders** - make sure you're not stomping on something
- **If they have existing client folders, work WITH that structure** - don't reorganize
- **Back up config.json before making changes** (copy to config.json.bak)
- **When in doubt, ask first**

They may have years of organized files. One wrong `rm` or overwrite could be catastrophic.
