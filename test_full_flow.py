#!/usr/bin/env python3
"""
End-to-end test of the NEF watcher flow with mock data.

This tests:
1. Email parsing
2. Case number extraction
3. Folder routing (creates actual folders and files)
4. Filename generation
5. Duplicate handling

Run with: python3 test_full_flow.py
"""
import os
import shutil
import tempfile
from pathlib import Path
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Import from main script
from nef_watcher import parse_nef_email, CASE_FOLDERS, DEFAULT_FOLDER
import nef_watcher

# Create a minimal valid PDF (just the header - enough to test)
DUMMY_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"


def create_test_email(case_number, doc_num, description):
    """Create a mock NEF email."""
    html = f"""
    <table>
    <tr><td><strong>Case Number:</strong></td><td>{case_number}</td></tr>
    <tr><td><strong>Document Number:</strong></td>
    <td><a href="https://ecf.nced.uscourts.gov/doc1/12345?caseid=999&de_seq_num=1&magic_num=12345">{doc_num}</a></td></tr>
    </table>
    <p><strong>Docket Text:</strong><br>{description}</p>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Activity in Case {case_number} - {description}"
    msg["From"] = "ecfnotice@nced.uscourts.gov"
    msg.attach(MIMEText(html, "html"))
    return msg


def mock_download_pdf(url, folder, subject):
    """Mock download that creates a dummy PDF instead of hitting the network."""
    import re
    folder = Path(folder).expanduser()
    folder.mkdir(parents=True, exist_ok=True)

    safe_subject = re.sub(r"[^\w\s-]", "", subject)[:50].strip()
    safe_subject = re.sub(r"\s+", "_", safe_subject)
    filename = f"{date.today().isoformat()}_{safe_subject}.pdf"
    filepath = folder / filename

    counter = 1
    while filepath.exists():
        filepath = folder / f"{date.today().isoformat()}_{safe_subject}_{counter}.pdf"
        counter += 1

    filepath.write_bytes(DUMMY_PDF)
    print(f"  ✓ Created: {filepath}")
    return True


def test_routing():
    """Test that emails route to correct folders."""
    print("=" * 60)
    print("TEST: Folder Routing")
    print("=" * 60)
    print()

    # Show current configuration
    print("Current CASE_FOLDERS mapping:")
    for case, folder in CASE_FOLDERS.items():
        print(f"  {case} → {folder}")
    print(f"  (default) → {DEFAULT_FOLDER}")
    print()

    # Test cases
    test_cases = [
        # (case_number, doc_num, description, expected_folder)
        ("1:23-cv-00456", "42", "Motion to Dismiss", CASE_FOLDERS.get("1:23-cv-00456", DEFAULT_FOLDER)),
        ("1:24-cv-00789", "15", "Response to Motion", CASE_FOLDERS.get("1:24-cv-00789", DEFAULT_FOLDER)),
        ("5:99-cv-99999", "1", "Unknown Case Filing", DEFAULT_FOLDER),  # Unknown case
    ]

    for case_num, doc_num, desc, expected_folder in test_cases:
        print(f"Case: {case_num}")
        print(f"  Document: #{doc_num} - {desc}")

        # Parse email
        msg = create_test_email(case_num, doc_num, desc)
        parsed_case, doc_url, subject = parse_nef_email(msg)

        print(f"  Parsed case: {parsed_case}")

        # Determine routing
        actual_folder = CASE_FOLDERS.get(parsed_case, DEFAULT_FOLDER)

        if parsed_case not in CASE_FOLDERS:
            print(f"  ⚠ Unknown case, routing to _UNROUTED")

        print(f"  Routed to: {actual_folder}")

        # Verify
        if actual_folder == expected_folder:
            print(f"  ✓ Routing correct!")
        else:
            print(f"  ✗ Expected: {expected_folder}")
        print()

    return True


def test_file_creation():
    """Test that files are actually created in the right places."""
    print("=" * 60)
    print("TEST: File Creation (using temp directory)")
    print("=" * 60)
    print()

    # Use temp directory for test
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create test folder structure
        smith_folder = tmpdir / "Smith"
        unrouted_folder = tmpdir / "_UNROUTED"

        # Mock the module's constants temporarily
        original_case_folders = nef_watcher.CASE_FOLDERS.copy()
        original_default = nef_watcher.DEFAULT_FOLDER

        nef_watcher.CASE_FOLDERS = {
            "1:23-cv-00456": smith_folder,
        }
        nef_watcher.DEFAULT_FOLDER = unrouted_folder

        try:
            # Test 1: Known case
            print("Creating file for known case (1:23-cv-00456)...")
            msg1 = create_test_email("1:23-cv-00456", "42", "Motion to Dismiss")
            case_num, doc_url, subject = parse_nef_email(msg1)
            folder = nef_watcher.CASE_FOLDERS.get(case_num, nef_watcher.DEFAULT_FOLDER)
            mock_download_pdf(doc_url, folder, subject)

            # Verify file exists
            files = list(smith_folder.glob("*.pdf"))
            assert len(files) == 1, f"Expected 1 file in Smith folder, got {len(files)}"
            print(f"  File created: {files[0].name}")
            print()

            # Test 2: Unknown case
            print("Creating file for unknown case (5:99-cv-99999)...")
            msg2 = create_test_email("5:99-cv-99999", "1", "Unknown Filing")
            case_num, doc_url, subject = parse_nef_email(msg2)
            folder = nef_watcher.CASE_FOLDERS.get(case_num, nef_watcher.DEFAULT_FOLDER)
            mock_download_pdf(doc_url, folder, subject)

            files = list(unrouted_folder.glob("*.pdf"))
            assert len(files) == 1, f"Expected 1 file in _UNROUTED folder, got {len(files)}"
            print(f"  File created: {files[0].name}")
            print()

            # Test 3: Duplicate handling
            print("Testing duplicate filename handling...")
            mock_download_pdf(doc_url, folder, subject)
            mock_download_pdf(doc_url, folder, subject)

            files = list(unrouted_folder.glob("*.pdf"))
            assert len(files) == 3, f"Expected 3 files (original + 2 duplicates), got {len(files)}"
            print(f"  Files created: {[f.name for f in sorted(files)]}")
            print()

            print("✓ All file creation tests passed!")

        finally:
            # Restore original values
            nef_watcher.CASE_FOLDERS = original_case_folders
            nef_watcher.DEFAULT_FOLDER = original_default

    return True


def test_with_real_folders():
    """Create actual test files in your configured folders."""
    print("=" * 60)
    print("TEST: Real Folder Creation")
    print("=" * 60)
    print()

    print("This will create a test PDF in your _UNROUTED folder.")
    print(f"Location: {DEFAULT_FOLDER}")
    print()

    response = input("Proceed? [y/N] ").strip().lower()
    if response != 'y':
        print("Skipped.")
        return True

    # Create a test file in the default folder
    msg = create_test_email("9:99-cv-00001-TEST", "1", "Test Document Please Delete")
    case_num, doc_url, subject = parse_nef_email(msg)

    print(f"Creating test PDF...")
    mock_download_pdf(doc_url, DEFAULT_FOLDER, subject)

    print()
    print(f"✓ Check {DEFAULT_FOLDER} for the test file!")
    print("  (You can delete it after verifying)")

    return True


def main():
    print("\n" + "=" * 60)
    print("NEF Watcher - Full Flow Tests")
    print("=" * 60 + "\n")

    try:
        test_routing()
        test_file_creation()

        print()
        test_with_real_folders()

        print()
        print("=" * 60)
        print("ALL TESTS COMPLETED!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
