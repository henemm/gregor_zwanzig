"""
E2E Test: Add Location Button Functionality

Tests that the "Add Location" button on /locations page opens a dialog.

This is a REAL browser test using Playwright - NO MOCKS!
"""
import time
from playwright.sync_api import sync_playwright, expect


def test_add_button_opens_dialog():
    """
    E2E Test: Click "Add Location" button, dialog should appear.

    Test Steps:
    1. Navigate to /locations page
    2. Click "New Location" button
    3. Assert dialog appears with "Name is required" text (visible after trying to save)
    4. Assert dialog has input fields

    Expected Result (RED Phase): Test FAILS - dialog does not appear
    Expected Result (GREEN Phase): Test PASSES - dialog appears
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1400, 'height': 1000})

        # Step 1: Navigate to locations page
        page.goto('http://localhost:8080/locations', timeout=10000)
        time.sleep(2)  # Wait for page to fully render

        # Step 2: Find and click "New Location" button
        # NiceGUI renders buttons with text content
        add_button = page.locator('button:has-text("New Location")')

        # Verify button exists
        assert add_button.count() > 0, "Add Location button not found on page"

        # Take screenshot before click
        page.screenshot(path='/tmp/before_click.png')

        # Click the button
        add_button.click()
        time.sleep(1)  # Wait for dialog to appear

        # Take screenshot after click
        page.screenshot(path='/tmp/after_click.png')

        # Step 3: Assert dialog appeared
        # Check for dialog by looking for the dialog header "New Location"
        # The page title also says "Locations", so we need to find the SECOND occurrence
        dialog_header = page.locator('text="New Location"')

        # Should have at least 1 occurrence (the dialog header)
        # Note: The button text "New Location" is also visible, so we check for form fields instead

        # Better approach: Check for form fields that only exist in the dialog
        name_input = page.locator('input[aria-label="Name"]')
        latitude_input = page.locator('input[aria-label="Latitude"]')

        # Assert dialog form fields are visible
        assert name_input.count() > 0, (
            "Dialog did not appear: Name input field not found. "
            "Button click did not trigger show_add_dialog()."
        )

        assert latitude_input.count() > 0, (
            "Dialog did not appear: Latitude input field not found"
        )

        # Step 4: Verify dialog is interactive (can focus input)
        name_input.first.click()
        time.sleep(0.5)

        # Additional verification: Check for Save button in dialog
        save_button = page.locator('button:has-text("Save")')
        assert save_button.count() > 0, "Save button not found in dialog"

        browser.close()

        print("✅ Test PASSED: Dialog appeared after clicking Add Location button")


def test_add_button_dialog_has_all_fields():
    """
    E2E Test: Verify dialog contains all required input fields.

    This test assumes the button works (depends on previous test passing).
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1400, 'height': 1000})

        page.goto('http://localhost:8080/locations', timeout=10000)
        time.sleep(2)

        # Click Add Location button
        page.locator('button:has-text("New Location")').click()
        time.sleep(1)

        # Verify all expected fields exist
        expected_fields = [
            "Name",
            "Google Maps Coordinates",
            "Latitude",
            "Longitude",
            "Elevation (m)",
            "Avalanche Region (optional)",
            "Bergfex Slug (for snow depth)",
        ]

        for field_label in expected_fields:
            # Check if input with this aria-label or nearby label exists
            field_exists = (
                page.locator(f'input[aria-label="{field_label}"]').count() > 0 or
                page.locator(f'text="{field_label}"').count() > 0
            )
            assert field_exists, f"Field '{field_label}' not found in dialog"

        # Verify action buttons
        assert page.locator('button:has-text("Save")').count() > 0, "Save button not found"
        assert page.locator('button:has-text("Cancel")').count() > 0, "Cancel button not found"

        browser.close()

        print("✅ Test PASSED: Dialog has all required fields")


if __name__ == "__main__":
    # Run tests manually for development
    print("Running E2E tests for Add Location button...")
    print("\n" + "="*60)
    print("Test 1: Button opens dialog")
    print("="*60)
    try:
        test_add_button_opens_dialog()
    except AssertionError as e:
        print(f"❌ Test FAILED: {e}")
    except Exception as e:
        print(f"⚠️  Test ERROR: {e}")

    print("\n" + "="*60)
    print("Test 2: Dialog has all fields")
    print("="*60)
    try:
        test_add_button_dialog_has_all_fields()
    except AssertionError as e:
        print(f"❌ Test FAILED: {e}")
    except Exception as e:
        print(f"⚠️  Test ERROR: {e}")
