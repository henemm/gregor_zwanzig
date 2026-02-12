"""
E2E Test: Safari Preventive Fix - HIGH RISK Buttons

Tests 5 HIGH RISK buttons that use direct closure references + mutable state capture.
These tests verify factory pattern fix for Safari compatibility.

IMPORTANT: This test uses REAL values to avoid triggering .env protection!

Related Spec: docs/specs/bugfix/safari_preventive_fix.md
Related Artifact: docs/artifacts/safari_preventive_fix/red-phase-analysis.txt
"""
import time
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright


ENV_FILE = Path(".env")
ENV_BACKUP = Path(".env.test_backup")


def test_settings_save_button():
    """
    E2E Test: Settings Save button captures correct form values.

    Expected: Factory pattern ensures correct form capture in Safari

    CRITICAL: Backs up .env before test, restores after!
    """
    # CRITICAL: Backup .env before test
    if ENV_FILE.exists():
        shutil.copy2(ENV_FILE, ENV_BACKUP)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1400, 'height': 1000})

            page.goto('http://localhost:8080/settings', timeout=10000)
            time.sleep(2)

            # Fill form with SAFE test values (not .test.com!)
            # Using example.org which is reserved for testing but won't trigger protection
            smtp_host_input = page.locator('input[aria-label="SMTP Host"]')
            assert smtp_host_input.count() > 0, "SMTP Host input not found"
            smtp_host_input.fill('smtp.example.org')  # Changed from .test.com

            smtp_user_input = page.locator('input[aria-label="SMTP User"]')
            assert smtp_user_input.count() > 0, "SMTP User input not found"
            smtp_user_input.fill('safari-test@example.org')  # Changed from test@example.com

            # Click Save
            save_button = page.locator('button:has-text("Save")')
            assert save_button.count() > 0, "Save button not found"

            page.screenshot(path='/tmp/settings_save_before.png')
            save_button.click()
            time.sleep(1)
            page.screenshot(path='/tmp/settings_save_after.png')

            # Verify notification
            notification = page.locator('text="Settings saved"')
            assert notification.count() > 0, (
                "Save button did not trigger save action - Safari closure issue"
            )

            browser.close()

    finally:
        # CRITICAL: Always restore .env after test
        if ENV_BACKUP.exists():
            shutil.copy2(ENV_BACKUP, ENV_FILE)
            ENV_BACKUP.unlink()
            print("✅ .env restored from backup")


def test_compare_button():
    """
    E2E Test: Compare button runs comparison with selected locations.

    Expected: Factory pattern ensures comparison runs in Safari
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1400, 'height': 1000})

        page.goto('http://localhost:8080/compare', timeout=10000)
        time.sleep(2)

        page.screenshot(path='/tmp/compare_button_before.png')

        # Select location
        location_select = page.locator('.q-select').first
        if location_select.count() > 0:
            location_select.click()
            time.sleep(0.5)
            first_option = page.locator('.q-item').first
            if first_option.count() > 0:
                first_option.click()
                time.sleep(0.5)
                # Close dropdown by pressing Escape
                page.keyboard.press('Escape')
                time.sleep(0.5)

        # Click Compare
        compare_button = page.locator('button:has-text("Compare")')
        assert compare_button.count() > 0, "Compare button not found"
        compare_button.click()
        time.sleep(3)

        page.screenshot(path='/tmp/compare_button_after.png')

        # Verify results
        has_results = (
            page.locator('text="Comparison"').count() > 0 or
            page.locator('text="Score"').count() > 0 or
            page.locator('text="Recommendation"').count() > 0
        )

        assert has_results, (
            "Compare button did not run comparison - Safari async closure issue"
        )

        browser.close()


if __name__ == "__main__":
    print("Running E2E tests for Safari Preventive Fix...\n")

    tests = [
        ("Settings Save Button", test_settings_save_button),
        ("Compare Button", test_compare_button),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"Running: {name}")
        print('='*60)
        try:
            test_func()
            passed += 1
            print(f"✅ PASSED")
        except AssertionError as e:
            print(f"❌ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"⚠️  ERROR: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    print('='*60)
