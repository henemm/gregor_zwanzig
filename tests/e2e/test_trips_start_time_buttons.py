"""
E2E Test: Trip Test-Report Buttons + Stage Start Time UI

Tests the new /trips UI elements:
1. "Test Morning" / "Test Evening" buttons on trip cards
2. "Startzeit (HH:MM)" input in Add/Edit stage dialogs

This is a REAL browser test using Playwright - NO MOCKS!

SPEC: docs/specs/modules/trips_test_reports_start_times.md v1.0
"""
import time

from playwright.sync_api import sync_playwright


def test_test_report_buttons_exist_on_trip_card():
    """
    E2E Test: Trip cards should have "Test Morning" and "Test Evening" buttons.

    Precondition: At least one trip exists in the system.

    Expected Result (GREEN): Both buttons render on each trip card.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})

        page.goto("http://localhost:8080/trips", timeout=10000)
        time.sleep(2)

        page.screenshot(path="/tmp/trips_test_buttons.png")

        # Check "Test Morning" button exists
        morning_btn = page.locator('button:has-text("Test Morning")')
        assert morning_btn.count() > 0, (
            "Test Morning button not found on trips page. "
            "Precondition: at least one trip must exist."
        )

        # Check "Test Evening" button exists
        evening_btn = page.locator('button:has-text("Test Evening")')
        assert evening_btn.count() > 0, (
            "Test Evening button not found on trips page."
        )

        browser.close()
        print("Test PASSED: Test Morning/Evening buttons exist on trip cards")


def test_test_morning_button_clickable():
    """
    E2E Test: "Test Morning" button triggers report send (shows notification).

    Verifies the Safari factory pattern works: button click triggers handler.
    We expect a notification (either success or error, depending on SMTP config).
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})

        page.goto("http://localhost:8080/trips", timeout=10000)
        time.sleep(2)

        # Click first "Test Morning" button
        morning_btn = page.locator('button:has-text("Test Morning")').first
        morning_btn.click()
        time.sleep(3)

        page.screenshot(path="/tmp/trips_test_morning_click.png")

        # Should show a notification (info "Sende..." or positive/negative result)
        # NiceGUI notifications appear as Quasar q-notification elements
        notification = page.locator(".q-notification")
        assert notification.count() > 0, (
            "No notification appeared after clicking Test Morning. "
            "Factory pattern may not be binding correctly (Safari issue)."
        )

        browser.close()
        print("Test PASSED: Test Morning button clickable, notification shown")


def test_test_evening_button_clickable():
    """
    E2E Test: "Test Evening" button triggers report send (shows notification).
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})

        page.goto("http://localhost:8080/trips", timeout=10000)
        time.sleep(2)

        # Click first "Test Evening" button
        evening_btn = page.locator('button:has-text("Test Evening")').first
        evening_btn.click()
        time.sleep(3)

        page.screenshot(path="/tmp/trips_test_evening_click.png")

        notification = page.locator(".q-notification")
        assert notification.count() > 0, (
            "No notification appeared after clicking Test Evening. "
            "Factory pattern may not be binding correctly (Safari issue)."
        )

        browser.close()
        print("Test PASSED: Test Evening button clickable, notification shown")


def test_start_time_input_in_edit_dialog():
    """
    E2E Test: Edit dialog shows "Startzeit (HH:MM)" input for each stage.

    Precondition: At least one trip with at least one stage exists.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})

        page.goto("http://localhost:8080/trips", timeout=10000)
        time.sleep(2)

        # Click first Edit button (pencil icon)
        edit_btn = page.locator('button:has(i:text("edit"))').first
        edit_btn.click()
        time.sleep(1)

        page.screenshot(path="/tmp/trips_edit_start_time.png")

        # Check for "Startzeit (HH:MM)" input field
        start_time_input = page.locator('input[aria-label="Startzeit (HH:MM)"]')
        assert start_time_input.count() > 0, (
            "Startzeit input not found in Edit dialog. "
            "The time picker was not added to the stage editor."
        )

        # Verify default value is "08:00"
        first_value = start_time_input.first.input_value()
        assert first_value == "08:00", (
            f"Expected default start time '08:00', got '{first_value}'"
        )

        browser.close()
        print("Test PASSED: Startzeit input exists in Edit dialog with default 08:00")


def test_start_time_input_in_add_dialog():
    """
    E2E Test: Add dialog shows "Startzeit (HH:MM)" input when a stage is added.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})

        page.goto("http://localhost:8080/trips", timeout=10000)
        time.sleep(2)

        # Click "New Trip" button
        new_trip_btn = page.locator('button:has-text("New Trip")')
        new_trip_btn.click()
        time.sleep(1)

        # Click "Add Stage" button inside dialog
        add_stage_btn = page.locator('button:has-text("Add Stage")')
        add_stage_btn.click()
        time.sleep(1)

        page.screenshot(path="/tmp/trips_add_start_time.png")

        # Check for "Startzeit (HH:MM)" input field
        start_time_input = page.locator('input[aria-label="Startzeit (HH:MM)"]')
        assert start_time_input.count() > 0, (
            "Startzeit input not found in Add dialog after adding a stage."
        )

        # Verify default value is "08:00"
        first_value = start_time_input.first.input_value()
        assert first_value == "08:00", (
            f"Expected default start time '08:00', got '{first_value}'"
        )

        # Close dialog
        cancel_btn = page.locator('button:has-text("Cancel")')
        cancel_btn.click()
        time.sleep(0.5)

        browser.close()
        print("Test PASSED: Startzeit input exists in Add dialog with default 08:00")


if __name__ == "__main__":
    print("Running E2E tests for Trip Test-Report Buttons + Start Time...")
    tests = [
        ("Test 1: Test report buttons exist", test_test_report_buttons_exist_on_trip_card),
        ("Test 2: Morning button clickable", test_test_morning_button_clickable),
        ("Test 3: Evening button clickable", test_test_evening_button_clickable),
        ("Test 4: Start time in Edit dialog", test_start_time_input_in_edit_dialog),
        ("Test 5: Start time in Add dialog", test_start_time_input_in_add_dialog),
    ]
    for name, test_fn in tests:
        print(f"\n{'='*60}")
        print(name)
        print("=" * 60)
        try:
            test_fn()
        except AssertionError as e:
            print(f"FAILED: {e}")
        except Exception as e:
            print(f"ERROR: {e}")
