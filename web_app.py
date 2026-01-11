#!/usr/bin/env python3
"""
NEF Watcher Web UI

A simple Flask web interface for managing NEF Watcher configuration.
"""
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

app = Flask(__name__)
app.secret_key = "nef-watcher-secret-key-change-in-production"

# File paths
BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"
LOG_FILE = BASE_DIR / "activity.log"
PID_FILE = BASE_DIR / ".watcher.pid"


def load_config():
    """Load configuration from config.json."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            config = json.load(f)
            # Migrate old gmail_* fields to new email_* fields
            if "gmail_user" in config and "email_user" not in config:
                config["email_user"] = config.pop("gmail_user")
                config["email_password"] = config.pop("gmail_app_password", "")
                config["email_provider"] = "gmail"
                save_config(config)
            return config
    return {
        "email_provider": "",
        "email_user": "",
        "email_password": "",
        "default_folder": "~/Documents/Legal/_UNROUTED",
        "processed_file": "~/.nef-processed.txt",
        "cases": {}
    }


def save_config(config):
    """Save configuration to config.json."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def load_activity_log():
    """Load recent activity from log file."""
    if LOG_FILE.exists():
        try:
            with open(LOG_FILE) as f:
                logs = json.load(f)
                # Return most recent first
                return list(reversed(logs[-20:]))
        except json.JSONDecodeError:
            return []
    return []


def get_unmapped_cases():
    """Get cases that were routed to _UNROUTED (not in config)."""
    config = load_config()
    mapped_cases = set(config.get("cases", {}).keys())
    unmapped = {}

    if LOG_FILE.exists():
        try:
            with open(LOG_FILE) as f:
                logs = json.load(f)
                for entry in logs:
                    case_num = entry.get("case_num")
                    if case_num and case_num not in mapped_cases and entry.get("status") == "warning":
                        # Track most recent occurrence
                        unmapped[case_num] = entry.get("timestamp", "")
        except json.JSONDecodeError:
            pass

    # Sort by most recent first
    return sorted(unmapped.items(), key=lambda x: x[1], reverse=True)


def create_folder_if_needed(folder_path):
    """Create folder if it doesn't exist."""
    folder = Path(folder_path).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    return folder.exists()


def move_unmapped_files(case_number, destination_folder):
    """Move files for a case from _UNROUTED to the destination folder."""
    config = load_config()
    unrouted = Path(config["default_folder"]).expanduser()
    dest = Path(destination_folder).expanduser()

    moved_files = []

    # Get filenames from activity log for this case
    if LOG_FILE.exists():
        try:
            with open(LOG_FILE) as f:
                logs = json.load(f)

            for entry in logs:
                if entry.get("case_num") == case_number and entry.get("filename"):
                    filename = entry["filename"]
                    source_file = unrouted / filename

                    if source_file.exists():
                        dest_file = dest / filename

                        # Handle duplicates
                        counter = 1
                        while dest_file.exists():
                            stem = source_file.stem
                            suffix = source_file.suffix
                            dest_file = dest / f"{stem}_{counter}{suffix}"
                            counter += 1

                        # Move the file
                        import shutil
                        shutil.move(str(source_file), str(dest_file))
                        moved_files.append(filename)

        except (json.JSONDecodeError, IOError):
            pass

    return moved_files


def get_existing_folders():
    """Get list of folders that actually exist on disk."""
    folders = set()
    home = Path.home()

    # Scan common legal folder locations recursively (up to 2 levels deep)
    common_bases = [
        home / "Documents" / "Legal" / "Clients",
        home / "Documents" / "Legal",
    ]

    for base in common_bases:
        if base.exists():
            # Add the base itself
            try:
                rel = base.relative_to(home)
                folders.add(f"~/{rel}")
            except ValueError:
                folders.add(str(base))

            # Add subdirectories (1 level)
            for child in base.iterdir():
                if child.is_dir() and not child.name.startswith('.'):
                    try:
                        rel = child.relative_to(home)
                        folders.add(f"~/{rel}")
                    except ValueError:
                        folders.add(str(child))

                    # Add grandchildren (2 levels deep)
                    for grandchild in child.iterdir():
                        if grandchild.is_dir() and not grandchild.name.startswith('.'):
                            try:
                                rel = grandchild.relative_to(home)
                                folders.add(f"~/{rel}")
                            except ValueError:
                                folders.add(str(grandchild))

    return sorted(folders)


def is_watcher_running():
    """Check if the watcher process is running."""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            # Check if process exists
            subprocess.run(["kill", "-0", str(pid)], check=True, capture_output=True)
            return True, pid
        except (subprocess.CalledProcessError, ValueError):
            PID_FILE.unlink(missing_ok=True)
    return False, None


@app.route("/")
def index():
    """Main dashboard."""
    config = load_config()
    activity = load_activity_log()
    running, pid = is_watcher_running()
    unmapped = get_unmapped_cases()

    return render_template(
        "index.html",
        config=config,
        cases=config.get("cases", {}),
        activity=activity,
        watcher_running=running,
        watcher_pid=pid,
        unmapped_cases=unmapped
    )


@app.route("/add", methods=["GET", "POST"])
def add_case():
    """Add a new case mapping."""
    # Pre-fill from query param (for quick-add from unmapped)
    prefill_case = request.args.get("case", "")

    if request.method == "POST":
        case_number = request.form.get("case_number", "").strip()
        folder = request.form.get("folder", "").strip()

        if not case_number or not folder:
            flash("Both case number and folder are required.", "error")
            return redirect(url_for("add_case"))

        # Create the folder
        create_folder_if_needed(folder)

        config = load_config()
        config["cases"][case_number] = folder
        save_config(config)

        # Move any existing files from _UNROUTED to the new folder
        moved_files = move_unmapped_files(case_number, folder)

        if moved_files:
            flash(f"Added case {case_number} → {folder} and moved {len(moved_files)} file(s)", "success")
        else:
            flash(f"Added case {case_number} → {folder}", "success")
        return redirect(url_for("index"))

    existing_folders = get_existing_folders()
    return render_template("add_case.html", prefill_case=prefill_case, existing_folders=existing_folders)


@app.route("/edit/<path:case_number>", methods=["GET", "POST"])
def edit_case(case_number):
    """Edit an existing case mapping."""
    config = load_config()

    if case_number not in config.get("cases", {}):
        flash(f"Case {case_number} not found.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        new_case_number = request.form.get("case_number", "").strip()
        folder = request.form.get("folder", "").strip()

        if not new_case_number or not folder:
            flash("Both case number and folder are required.", "error")
            return redirect(url_for("edit_case", case_number=case_number))

        # Create the folder
        create_folder_if_needed(folder)

        # Remove old entry if case number changed
        if new_case_number != case_number:
            del config["cases"][case_number]

        config["cases"][new_case_number] = folder
        save_config(config)

        flash(f"Updated case {new_case_number} → {folder}", "success")
        return redirect(url_for("index"))

    existing_folders = get_existing_folders()
    return render_template(
        "edit_case.html",
        case_number=case_number,
        folder=config["cases"][case_number],
        existing_folders=existing_folders
    )


@app.route("/delete/<path:case_number>", methods=["POST"])
def delete_case(case_number):
    """Delete a case mapping."""
    config = load_config()

    if case_number in config.get("cases", {}):
        del config["cases"][case_number]
        save_config(config)
        flash(f"Deleted case {case_number}", "success")
    else:
        flash(f"Case {case_number} not found.", "error")

    return redirect(url_for("index"))


@app.route("/settings", methods=["GET", "POST"])
def settings():
    """Edit global settings."""
    config = load_config()

    if request.method == "POST":
        config["email_provider"] = request.form.get("email_provider", "gmail").strip()
        config["email_user"] = request.form.get("email_user", "").strip()
        config["email_password"] = request.form.get("email_password", "").strip()
        config["default_folder"] = request.form.get("default_folder", "").strip()

        # Handle custom IMAP server
        if config["email_provider"] == "custom":
            config["imap_server"] = request.form.get("imap_server", "").strip()
            config["imap_port"] = int(request.form.get("imap_port", 993))

        save_config(config)

        flash("Settings saved.", "success")
        return redirect(url_for("index"))

    return render_template("settings.html", config=config)


@app.route("/run", methods=["POST"])
def run_watcher():
    """Run the watcher once."""
    try:
        result = subprocess.run(
            [sys.executable, str(BASE_DIR / "nef_watcher.py")],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            flash("Watcher completed successfully.", "success")
        else:
            flash(f"Watcher error: {result.stderr}", "error")
    except subprocess.TimeoutExpired:
        flash("Watcher timed out.", "error")
    except Exception as e:
        flash(f"Error running watcher: {e}", "error")

    return redirect(url_for("index"))


@app.route("/api/activity")
def api_activity():
    """API endpoint for activity log (for AJAX refresh)."""
    return jsonify(load_activity_log())


@app.route("/api/status")
def api_status():
    """API endpoint for watcher status."""
    running, pid = is_watcher_running()
    return jsonify({"running": running, "pid": pid})


@app.template_filter("format_datetime")
def format_datetime(value):
    """Format ISO datetime string for display."""
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return value


if __name__ == "__main__":
    print("Starting NEF Watcher Web UI...")
    print("Open http://localhost:5050 in your browser")
    app.run(debug=True, port=5050)
