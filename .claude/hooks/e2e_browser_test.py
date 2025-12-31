#!/usr/bin/env python3
"""
E2E Test Hook (Browser + Email)

Führt echte E2E-Tests durch:
- Browser: Playwright öffnet echten Browser, macht Screenshots
- Email: Sendet echte E-Mail via SMTP, prüft via IMAP

Verwendung:
    # Browser Test
    python3 e2e_browser_test.py browser --check "Windrichtung" --url "/compare" --action "compare"

    # Email Test
    python3 e2e_browser_test.py email --check "Windrichtung" --send-from-ui

Exit codes:
    0 = Element gefunden (GREEN)
    1 = Element nicht gefunden (RED)
    2 = Fehler (Server nicht erreichbar, etc.)
"""

import argparse
import sys
import time
import imaplib
import email
from pathlib import Path


def run_browser_test(url: str, check_text: str, action: str = None) -> tuple[bool, str, str]:
    """
    Führt Browser-Test durch.

    Returns:
        (success, message, screenshot_path)
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "Playwright nicht installiert: uv add playwright", None

    screenshot_path = f"/tmp/e2e_test_{int(time.time())}.png"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1400, 'height': 1000})

            # Navigate to page
            full_url = f"http://localhost:8080{url}"
            try:
                page.goto(full_url, timeout=5000)
            except Exception as e:
                return False, f"Server nicht erreichbar: {full_url}", None

            time.sleep(2)

            # Perform action if specified
            if action == "compare":
                # Open location dropdown
                try:
                    page.locator('.q-field__native').first.click(timeout=3000)
                    time.sleep(1)

                    # Select first 3 locations (minimum for spec compliance)
                    items = page.locator('.q-item__label').all()
                    for i in range(min(3, len(items))):
                        items[i].click()
                        time.sleep(0.3)

                    # Close dropdown
                    page.keyboard.press('Escape')
                    time.sleep(0.5)

                    # Click Vergleichen
                    page.locator('button:has-text("VERGLEICHEN")').click(timeout=3000)
                    time.sleep(8)  # Wait for API

                except Exception as e:
                    return False, f"Action 'compare' fehlgeschlagen: {e}", None

            # Take screenshot
            page.screenshot(path=screenshot_path, full_page=True)

            # Check for text
            content = page.content()
            found = check_text.lower() in content.lower()

            browser.close()

            if found:
                return True, f"✅ '{check_text}' gefunden", screenshot_path
            else:
                return False, f"❌ '{check_text}' NICHT gefunden", screenshot_path

    except Exception as e:
        return False, f"Browser-Test Fehler: {e}", None


def run_email_test(check_text: str, send_from_ui: bool = False) -> tuple[bool, str]:
    """
    Führt E-Mail E2E Test durch.

    1. Optional: Sendet E-Mail über Browser UI
    2. Prüft IMAP Posteingang auf neuste E-Mail
    3. Sucht nach check_text im HTML Body

    Returns:
        (success, message)
    """
    # Load settings for IMAP
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
    try:
        from app.config import Settings
        settings = Settings()
    except Exception as e:
        return False, f"Settings laden fehlgeschlagen: {e}"

    if not settings.smtp_user or not settings.smtp_pass:
        return False, "SMTP nicht konfiguriert"

    # Step 1: Send email from UI if requested
    if send_from_ui:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width': 1400, 'height': 1000})

                page.goto('http://localhost:8080/compare', timeout=5000)
                time.sleep(2)

                # Select first 3 locations (minimum for spec compliance)
                page.locator('.q-field__native').first.click(timeout=3000)
                time.sleep(1)
                items = page.locator('.q-item__label').all()
                for i in range(min(3, len(items))):
                    items[i].click()
                    time.sleep(0.3)
                page.keyboard.press('Escape')
                time.sleep(0.5)

                # Click Vergleichen
                page.locator('button:has-text("VERGLEICHEN")').click(timeout=3000)
                time.sleep(8)

                # Click "Per E-Mail senden"
                page.locator('button:has-text("E-MAIL")').click(timeout=3000)
                time.sleep(5)

                browser.close()
                print("   E-Mail über UI gesendet")

        except Exception as e:
            return False, f"E-Mail senden über UI fehlgeschlagen: {e}"

    # Step 2: Wait for email delivery
    time.sleep(5)

    # Step 3: Check IMAP
    try:
        imap = imaplib.IMAP4_SSL('imap.gmail.com')
        imap.login(settings.smtp_user, settings.smtp_pass)
        imap.select('"[Google Mail]/Gesendet"')

        # Get latest email
        _, data = imap.search(None, 'ALL')
        all_ids = data[0].split()
        if not all_ids:
            imap.logout()
            return False, "Keine E-Mails gefunden"

        _, msg_data = imap.fetch(all_ids[-1], '(RFC822)')
        msg = email.message_from_bytes(msg_data[0][1])

        subject = msg.get('Subject', '')
        print(f"   Letzte E-Mail: {subject[:50]}")

        # Get HTML body
        body = ''
        for part in msg.walk():
            if part.get_content_type() == 'text/html':
                body = part.get_payload(decode=True).decode('utf-8')
                break

        imap.close()
        imap.logout()

        # Check for text
        if check_text.lower() in body.lower():
            return True, f"✅ '{check_text}' in E-Mail gefunden"
        else:
            return False, f"❌ '{check_text}' NICHT in E-Mail gefunden"

    except Exception as e:
        return False, f"IMAP Fehler: {e}"


def main():
    parser = argparse.ArgumentParser(description="E2E Test (Browser + Email)")
    subparsers = parser.add_subparsers(dest="mode", help="Test-Modus")

    # Browser subcommand
    browser_parser = subparsers.add_parser("browser", help="Browser/UI Test")
    browser_parser.add_argument("--check", required=True, help="Text der im UI sichtbar sein muss")
    browser_parser.add_argument("--url", default="/compare", help="URL path")
    browser_parser.add_argument("--action", choices=["compare", "none"], default="none")
    browser_parser.add_argument("--expect-fail", action="store_true", help="RED-Phase")

    # Email subcommand
    email_parser = subparsers.add_parser("email", help="Email Test")
    email_parser.add_argument("--check", required=True, help="Text der in E-Mail sein muss")
    email_parser.add_argument("--send-from-ui", action="store_true", help="E-Mail über Browser senden")
    email_parser.add_argument("--expect-fail", action="store_true", help="RED-Phase")

    args = parser.parse_args()

    if not args.mode:
        parser.print_help()
        sys.exit(2)

    expect_fail = args.expect_fail

    if args.mode == "browser":
        print(f"🔍 E2E BROWSER Test")
        print(f"   URL: http://localhost:8080{args.url}")
        print(f"   Check: '{args.check}'")
        print(f"   Action: {args.action}")
        print(f"   Expect: {'RED' if expect_fail else 'GREEN'}")
        print()

        success, message, screenshot = run_browser_test(args.url, args.check, args.action)
        print(message)
        if screenshot:
            print(f"   Screenshot: {screenshot}")

    elif args.mode == "email":
        print(f"📧 E2E EMAIL Test")
        print(f"   Check: '{args.check}'")
        print(f"   Send from UI: {args.send_from_ui}")
        print(f"   Expect: {'RED' if expect_fail else 'GREEN'}")
        print()

        success, message = run_email_test(args.check, args.send_from_ui)
        print(message)

    # RED/GREEN Logic
    if expect_fail:
        if not success:
            print("\n🔴 RED PHASE OK - Feature fehlt noch (erwartet)")
            sys.exit(0)
        else:
            print("\n⚠️  RED PHASE FEHLER - Feature existiert bereits!")
            sys.exit(1)
    else:
        if success:
            print("\n🟢 GREEN PHASE OK - Feature funktioniert!")
            sys.exit(0)
        else:
            print("\n❌ GREEN PHASE FEHLER - Feature fehlt!")
            sys.exit(1)


if __name__ == "__main__":
    main()
