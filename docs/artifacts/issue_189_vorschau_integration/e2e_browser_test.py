"""E2E Browser-Verification für Issue #189 Vorschau-Tab gegen Staging.

Pragmatischer Pfad — staging.gregor20.henemm.com hat aktuell keinen Trip
mit Stage in der Forecast-Range; daher verifizieren wir:
- AC-1, AC-4, AC-5, AC-8 im Browser mit c09c7b32 (clean rendering)
- AC-2, AC-3 zusätzlich über Backend-Curl auf 5f534011 (echter Render)

Bekanntes Side-Finding: each_key_duplicate-Bug bei 5f534011 (13 Stages am 2026-05-04)
verhindert die Trip-Detail-Render-Seite — separater Bug, NICHT durch #189 verursacht.
"""
from playwright.sync_api import sync_playwright
import sys
import time

BASE = "https://staging.gregor20.henemm.com"
USER = "default"
PASS = "ZfDOKJTre8udPtG"
TRIP_RENDERABLE = "c09c7b32"  # 1 Stage, alt — clean rendering aber Backend liefert 404

results = []


def record(ok: bool, label: str, detail: str = ""):
    results.append({"ok": ok, "label": label, "detail": detail})
    sym = "PASS" if ok else "FAIL"
    print(f"[{sym}] {label}" + (f" — {detail}" if detail else ""))


def shoot(page, label: str):
    path = f"/tmp/preview_e2e_final_{label}.png"
    page.screenshot(path=path, full_page=True)
    print(f"  📸 {path}")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1400, "height": 1000})
    page = ctx.new_page()

    js_errors = []
    page.on("pageerror", lambda exc: js_errors.append(str(exc)))

    # 1. Login
    page.goto(f"{BASE}/login")
    page.wait_for_load_state("networkidle")
    page.fill('input[name="username"], input[name="email"], input[type="text"]', USER)
    page.fill('input[name="password"], input[type="password"]', PASS)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    record("/login" not in page.url, "Login erfolgreich")

    # 2. Trip detail (sauberer Trip ohne Stage-Duplikate)
    page.goto(f"{BASE}/trips/{TRIP_RENDERABLE}")
    page.wait_for_load_state("networkidle")
    time.sleep(2)
    record(page.locator('[data-testid="trip-detail-tab-list"]').is_visible(), "Trip-Tabs-Liste sichtbar")
    shoot(page, "01_detail_loaded")

    # 3. Klick Tab "Vorschau" — AC-1
    print("\n--- AC-1: Tab Vorschau aktivieren ---")
    tab_preview = page.locator('[data-testid="trip-detail-tab-preview"]')
    tab_preview.click()
    time.sleep(1)
    record(tab_preview.get_attribute("data-state") == "active", "AC-1: Tab preview aktiv")

    preview_controls = page.locator('[data-testid="preview-controls"]')
    record(preview_controls.is_visible(), "AC-1: preview-controls sichtbar")

    # Beide Radios da, default = morning
    morning_radio = page.locator('input[type="radio"][value="morning"]')
    evening_radio = page.locator('input[type="radio"][value="evening"]')
    record(morning_radio.is_checked(), "AC-1: Initial-Default = morning (vor 14 Uhr, jetzt aktuelle Tageszeit)")
    record(evening_radio.count() > 0, "AC-1: Evening-Radio existiert")

    # 4. AC-5: Fehler-Anzeige (Backend liefert 404 bei diesem Trip → Frontend muss Error zeigen)
    print("\n--- AC-5: Fehler-Anzeige bei Backend-404 ---")
    page.wait_for_selector('[data-testid="email-iframe-error"]', timeout=15000)
    email_error = page.locator('[data-testid="email-iframe-error"]')
    record(email_error.is_visible(), "AC-5: email-iframe-error sichtbar bei 404")
    err_text = email_error.text_content() or ""
    record("HTTP 404" in err_text or "Keine Stage" in err_text, "AC-5: Email-Fehler enthält HTTP-Status oder Detail", f"'{err_text[:120]}'")

    page.wait_for_selector('[data-testid="sms-error"]', timeout=10000)
    sms_error = page.locator('[data-testid="sms-error"]')
    record(sms_error.is_visible(), "AC-5: sms-error sichtbar bei 404")
    sms_err_text = sms_error.text_content() or ""
    record("HTTP 404" in sms_err_text or "Keine Stage" in sms_err_text, "AC-5: SMS-Fehler enthält HTTP-Status oder Detail", f"'{sms_err_text[:120]}'")
    shoot(page, "02_preview_morning_404")

    # 5. AC-4: Morning -> Evening triggert Re-Fetch
    print("\n--- AC-4: Morning -> Evening Re-Fetch ---")
    evening_radio.click()
    time.sleep(0.3)
    record(evening_radio.is_checked(), "AC-4: Evening-Radio gechecked")
    # Beide Komponenten sollten neu laden — Loading-State oder Error
    # Wir prüfen: Komponenten sind weiterhin da, kein hängender Mischzustand
    page.wait_for_selector('[data-testid="email-iframe-error"], [data-testid="email-iframe"]', timeout=15000)
    record(
        page.locator('[data-testid="email-iframe-error"], [data-testid="email-iframe"]').count() > 0,
        "AC-4: Email-Komponente nach Switch wieder ready"
    )
    page.wait_for_selector('[data-testid="sms-error"], [data-testid="sms-token-bubble"]', timeout=10000)
    record(
        page.locator('[data-testid="sms-error"], [data-testid="sms-token-bubble"]').count() > 0,
        "AC-4: SMS-Komponente nach Switch wieder ready"
    )
    shoot(page, "03_preview_evening_404")

    # 6. AC-8: Design-System-Tokens
    print("\n--- AC-8: Design-System-Tokens via getComputedStyle ---")
    wrap = page.locator('[data-testid="email-iframe-wrapper"]')
    bg = wrap.evaluate("el => getComputedStyle(el).backgroundColor")
    radius = wrap.evaluate("el => getComputedStyle(el).borderRadius")
    shadow = wrap.evaluate("el => getComputedStyle(el).boxShadow")
    # var(--g-paper, #f6f4ee) — sollte ein helles Beige sein, nicht transparent
    record(bg not in ("", "rgba(0, 0, 0, 0)", "transparent"), f"AC-8: email-frame bg gesetzt", f"bg={bg}")
    record(radius != "0px", "AC-8: email-frame border-radius gesetzt", f"radius={radius}")
    record(shadow not in ("", "none"), "AC-8: email-frame box-shadow gesetzt", f"shadow={shadow}")

    phone = page.locator('.phone-frame').first
    if phone.count() > 0:
        phone_bg = phone.evaluate("el => getComputedStyle(el).backgroundColor")
        phone_radius = phone.evaluate("el => getComputedStyle(el).borderRadius")
        record(phone_bg in ("rgb(26, 26, 24)", "rgb(0, 0, 0)") or "26, 26, 24" in phone_bg, "AC-8: phone-frame dark bg", f"bg={phone_bg}")
        record(phone_radius == "36px", "AC-8: phone-frame radius 36px", f"radius={phone_radius}")

    # 7. JS-Fehler protokolliert?
    print(f"\n--- JS-Errors während Test ---")
    if js_errors:
        for e in js_errors:
            print(f"  [PAGEERROR] {e}")
    record(len(js_errors) == 0, f"Keine ungewollten JS-Fehler", f"errors={len(js_errors)}")

    browser.close()


# Summary
total = len(results)
passed = sum(1 for r in results if r["ok"])
failed = total - passed
print(f"\n=== ZUSAMMENFASSUNG ===")
print(f"Tests: {passed}/{total} PASS, {failed} FAIL")
if failed > 0:
    print("\nFehlgeschlagen:")
    for r in results:
        if not r["ok"]:
            print(f"  - {r['label']}: {r['detail']}")
    sys.exit(1)
sys.exit(0)
