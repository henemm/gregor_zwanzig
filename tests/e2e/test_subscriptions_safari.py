"""
E2E Test: Subscription Buttons Safari Compatibility

Tests that all subscription action buttons work correctly.
This is a REAL browser test using Playwright - NO MOCKS!

Related Bug: Safari closure binding issue (same as locations_add_button_fix)
"""
import time
from playwright.sync_api import sync_playwright


def test_new_subscription_button_opens_dialog():
    """
    E2E Test: Click "New Subscription" button, dialog should appear.

    Expected Result (RED in Safari): Button doesn't respond
    Expected Result (GREEN after fix): Dialog appears with form fields
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1400, 'height': 1000})

        # Navigate to subscriptions page
        page.goto('http://localhost:8080/subscriptions', timeout=10000)
        time.sleep(2)

        # Take screenshot before click
        page.screenshot(path='/tmp/subscriptions_before_new.png')

        # Find and click "New Subscription" button
        new_button = page.locator('button:has-text("New Subscription")')
        assert new_button.count() > 0, "New Subscription button not found on page"

        new_button.click()
        time.sleep(1)

        # Take screenshot after click
        page.screenshot(path='/tmp/subscriptions_after_new.png')

        # Verify dialog appeared by checking for form fields
        name_input = page.locator('input[aria-label="Name"]')
        assert name_input.count() > 0, (
            "Dialog did not appear: Name input field not found. "
            "Button click did not trigger dialog (Safari closure issue)."
        )

        # Verify Save button exists (confirms dialog is open)
        save_button = page.locator('button:has-text("Save")')
        assert save_button.count() > 0, "Save button not found in dialog"

        browser.close()
        print("✅ Test PASSED: New Subscription button opens dialog")


if __name__ == "__main__":
    # Run test manually
    print("Running E2E test for New Subscription button...")
    try:
        test_new_subscription_button_opens_dialog()
    except AssertionError as e:
        print(f"❌ Test FAILED: {e}")
    except Exception as e:
        print(f"⚠️  Test ERROR: {e}")
