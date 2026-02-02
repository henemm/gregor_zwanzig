"""
E2E Test: Weather Config UI (Feature 2.6)

Tests the weather metrics configuration UI for trips.
This is a REAL browser test using Playwright - NO MOCKS!

Expected RED: UI doesn't exist yet, tests will fail.
Expected GREEN: After implementation, all tests pass in Safari.

Feature: Story 2, Feature 2.6 - Wetter-Config (WebUI)
SPEC: docs/specs/modules/weather_config.md
"""
import time
from playwright.sync_api import sync_playwright


def test_weather_config_button_exists_on_trips_page():
    """
    E2E Test: Trips page should have "Wetter-Metriken" button.

    Expected Result (RED): Button doesn't exist yet
    Expected Result (GREEN): Button renders and is clickable
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1400, 'height': 1000})

        # Navigate to trips page
        page.goto('http://localhost:8080/trips', timeout=10000)
        time.sleep(2)

        # Take screenshot
        page.screenshot(path='/tmp/weather_config_trips_page.png')

        # Look for "Wetter-Metriken" button
        weather_button = page.locator('button:has-text("Wetter-Metriken")')
        assert weather_button.count() > 0, (
            "Weather Config button not found on trips page. "
            "Feature 2.6 not implemented yet."
        )

        browser.close()
        print("✅ Test PASSED: Weather Config button exists")


def test_weather_config_dialog_opens_with_checkboxes():
    """
    E2E Test: Click "Wetter-Metriken" button, dialog with checkboxes appears.

    Expected Result (RED): Dialog doesn't exist yet
    Expected Result (GREEN): Dialog opens with 13 metric checkboxes
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1400, 'height': 1000})

        # Navigate to trips page
        page.goto('http://localhost:8080/trips', timeout=10000)
        time.sleep(2)

        # Click weather config button
        weather_button = page.locator('button:has-text("Wetter-Metriken")')
        weather_button.click()
        time.sleep(1)

        # Take screenshot after click
        page.screenshot(path='/tmp/weather_config_dialog.png')

        # Verify dialog appeared
        dialog_title = page.locator('text=Wetter-Metriken konfigurieren')
        assert dialog_title.count() > 0, (
            "Weather Config dialog did not appear. "
            "Dialog title not found."
        )

        # Verify checkboxes exist (should be 13 total)
        checkboxes = page.locator('input[type="checkbox"]')
        checkbox_count = checkboxes.count()
        assert checkbox_count == 13, (
            f"Expected 13 metric checkboxes, found {checkbox_count}. "
            "All 13 metrics (8 basis + 5 extended) should be present."
        )

        browser.close()
        print("✅ Test PASSED: Dialog opens with 13 checkboxes")


def test_weather_config_default_state():
    """
    E2E Test: Default state shows 8 basis metrics checked, 5 extended unchecked.

    Expected Result (RED): Default state not implemented
    Expected Result (GREEN): 8 checkboxes checked initially
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1400, 'height': 1000})

        # Navigate and open dialog
        page.goto('http://localhost:8080/trips', timeout=10000)
        time.sleep(2)
        page.locator('button:has-text("Wetter-Metriken")').click()
        time.sleep(1)

        # Count checked checkboxes (NiceGUI uses Quasar structure)
        checked_boxes = page.locator('div.q-checkbox[aria-checked="true"]')
        checked_count = checked_boxes.count()

        assert checked_count == 8, (
            f"Expected 8 basis metrics checked by default, found {checked_count}. "
            "Default: all 8 basis metrics should be checked."
        )

        browser.close()
        print("✅ Test PASSED: Default state correct (8 checked)")


def test_weather_config_save_button_validates_minimum_one():
    """
    E2E Test: Validation - cannot save with 0 metrics selected.

    Expected Result (RED): Validation not implemented
    Expected Result (GREEN): Error notification appears, dialog stays open
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1400, 'height': 1000})

        # Navigate and open dialog
        page.goto('http://localhost:8080/trips', timeout=10000)
        time.sleep(2)
        page.locator('button:has-text("Wetter-Metriken")').click()
        time.sleep(1)

        # Uncheck all checkboxes (NiceGUI uses Quasar structure)
        checked_boxes = page.locator('div.q-checkbox[aria-checked="true"]')
        count = checked_boxes.count()
        for i in range(count):
            # Always click first checked box (count decreases each iteration)
            page.locator('div.q-checkbox[aria-checked="true"]').first.click()
            time.sleep(0.1)

        # Try to save
        save_button = page.locator('button:has-text("Speichern")')
        save_button.click()
        time.sleep(1)

        # Take screenshot of error
        page.screenshot(path='/tmp/weather_config_validation_error.png')

        # Verify error notification appears (use :text-matches for partial match)
        error_notification = page.locator(':text("Mindestens 1 Metrik")')
        assert error_notification.count() > 0, (
            "Validation error notification not shown. "
            "Should display 'Mindestens 1 Metrik muss ausgewählt sein!'"
        )

        # Verify dialog is still open (not closed)
        dialog_title = page.locator('text=Wetter-Metriken konfigurieren')
        assert dialog_title.count() > 0, (
            "Dialog closed after validation error. "
            "Should stay open to let user correct the issue."
        )

        browser.close()
        print("✅ Test PASSED: Validation prevents saving 0 metrics")


def test_weather_config_saves_and_persists():
    """
    E2E Test: Select metrics, save, reload page, verify persistence.

    Expected Result (RED): Persistence not implemented
    Expected Result (GREEN): Selected metrics saved and reload correctly

    Safari Test: Factory pattern ensures save button works!
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1400, 'height': 1000})

        # Navigate and open dialog
        page.goto('http://localhost:8080/trips', timeout=10000)
        time.sleep(2)
        page.locator('button:has-text("Wetter-Metriken")').click()
        time.sleep(1)

        # Uncheck 5 metrics, keep only 3
        # (Start with 8 checked, uncheck 5, should have 3 left)
        for i in range(5):
            page.locator('div.q-checkbox[aria-checked="true"]').first.click()
            time.sleep(0.1)

        # Verify 3 are still checked
        checked_count = page.locator('div.q-checkbox[aria-checked="true"]').count()
        assert checked_count == 3, f"Expected 3 checked after unchecking 5, got {checked_count}"

        # Save
        save_button = page.locator('button:has-text("Speichern")')
        save_button.click()
        time.sleep(1)

        # Take screenshot after save
        page.screenshot(path='/tmp/weather_config_after_save.png')

        # Verify success notification
        success_notification = page.locator(':text("Metriken gespeichert")')
        assert success_notification.count() > 0, (
            "Success notification not shown after save. "
            "Should display '[N] Metriken gespeichert!'"
        )

        # Reload page
        page.reload()
        time.sleep(2)

        # Re-open config dialog
        page.locator('button:has-text("Wetter-Metriken")').click()
        time.sleep(1)

        # Take screenshot after reload
        page.screenshot(path='/tmp/weather_config_after_reload.png')

        # Verify persistence: should still have 3 checked
        checked_after_reload = page.locator('div.q-checkbox[aria-checked="true"]').count()
        assert checked_after_reload == 3, (
            f"Config not persisted: expected 3 checked after reload, got {checked_after_reload}. "
            "Config should be saved to JSON and loaded correctly."
        )

        browser.close()
        print("✅ Test PASSED: Config saves and persists across reload")


if __name__ == "__main__":
    # Run tests manually for TDD RED phase
    print("=" * 60)
    print("E2E Test Suite: Weather Config (Feature 2.6)")
    print("Expected: ALL TESTS FAIL (RED) - UI not implemented yet")
    print("=" * 60)

    tests = [
        ("Weather Config Button Exists", test_weather_config_button_exists_on_trips_page),
        ("Dialog Opens with Checkboxes", test_weather_config_dialog_opens_with_checkboxes),
        ("Default State (8 Checked)", test_weather_config_default_state),
        ("Validation (Minimum 1)", test_weather_config_save_button_validates_minimum_one),
        ("Save & Persistence", test_weather_config_saves_and_persists),
    ]

    failed = 0
    passed = 0

    for test_name, test_func in tests:
        print(f"\n▶ Running: {test_name}")
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"  ❌ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  ⚠️  ERROR: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {failed} FAILED, {passed} PASSED")
    print("Expected: All 5 tests FAIL (RED phase)")
    print("=" * 60)
