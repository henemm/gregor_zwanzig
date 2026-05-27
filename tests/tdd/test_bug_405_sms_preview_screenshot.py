"""
TDD RED Tests — Issue #405: SMS-Preview-Screenshot zeigt E-Mail-Inhalt

SPEC: docs/specs/modules/bug_405_sms_preview_screenshot.md

Hintergrund:
  take-ist-screenshots.js versucht für desktop-sms-preview.png einen
  Radio-Button mit Selektor input[type="radio"][value="sms"] zu klicken.
  Dieser Selektor existiert nicht — der Preview-Tab zeigt EmailIframe und
  SmsPhoneFrame immer nebeneinander (kein Channel-Toggle). Der Klick schlägt
  stumm fehl (.catch(() => {})), der Screenshot ist byte-identisch mit dem
  Email-Screenshot.

Fix:
  Kaputten Radio-Klick-Block durch page.locator('[data-testid="sms-phone-wrapper"]')
  .screenshot() ersetzen. Fehlschläge erhöhen ERRORS und loggen auf stderr.

RED-Zustand (jetzt):
  Gebrochener Selektor + .catch(() => {}) noch im Script → ac1-Tests FAIL.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

SCRIPT = (
    REPO_ROOT
    / "claude-code-handoff"
    / "soll-audit-2026-05-27"
    / "take-ist-screenshots.js"
)


# ---------------------------------------------------------------------------
# Grundprüfung
# ---------------------------------------------------------------------------


def test_script_exists():
    """Das zu ändernde Script muss im Repository existieren."""
    assert SCRIPT.exists(), f"Script nicht gefunden: {SCRIPT}"


# ---------------------------------------------------------------------------
# AC-1 — Kaputten Radio-Selektor entfernt, Element-Screenshot stattdessen
# ---------------------------------------------------------------------------


def test_ac1_broken_radio_selector_absent():
    """
    GIVEN take-ist-screenshots.js nach dem Fix
    WHEN  wir nach dem kaputten Radio-Selektor suchen
    THEN  darf 'input[type="radio"][value="sms"]' nicht mehr im Script stehen

    Hintergrund: Dieser Selektor existiert nicht in der Preview-UI.
    Email und SMS werden immer nebeneinander angezeigt (kein Toggle).
    """
    src = SCRIPT.read_text()
    assert 'input[type="radio"][value="sms"]' not in src, (
        "Script enthält noch den kaputten Radio-Selektor "
        "'input[type=\"radio\"][value=\"sms\"]' — Fix nicht angewendet"
    )


def test_ac1_preview_channel_sms_testid_absent():
    """
    GIVEN take-ist-screenshots.js nach dem Fix
    WHEN  wir nach dem zweiten kaputten Selektor suchen
    THEN  darf 'preview-channel-sms' nicht mehr im Script stehen

    Hintergrund: Auch dieser data-testid existiert nicht in der aktuellen UI.
    """
    src = SCRIPT.read_text()
    assert "preview-channel-sms" not in src, (
        "Script enthält noch den nicht-existierenden Selektor "
        "'[data-testid=\"preview-channel-sms\"]' — Fix nicht angewendet"
    )


def test_ac1_element_screenshot_used_for_sms():
    """
    GIVEN take-ist-screenshots.js nach dem Fix
    WHEN  wir nach dem korrekten Element-Screenshot-Aufruf suchen
    THEN  muss 'sms-phone-wrapper' und '.screenshot(' innerhalb von 300 Zeichen stehen

    Hintergrund: SmsPhoneFrame liefert data-testid="sms-phone-wrapper" — dieses
    Element ist immer sichtbar und kann per locator().screenshot() isoliert werden.
    """
    src = SCRIPT.read_text()
    assert "sms-phone-wrapper" in src, (
        "Script enthält 'sms-phone-wrapper' nicht — Element-Screenshot-Fix fehlt"
    )
    wrapper_pos = src.find("sms-phone-wrapper")
    screenshot_in_range = ".screenshot(" in src[wrapper_pos : wrapper_pos + 300]
    assert screenshot_in_range, (
        "'.screenshot(' kommt nicht innerhalb von 300 Zeichen nach 'sms-phone-wrapper' — "
        "Element-Screenshot-Aufruf fehlt oder falsch platziert"
    )


# ---------------------------------------------------------------------------
# AC-2 — Kein stummes Catch, ERRORS-Zähler korrekt
# ---------------------------------------------------------------------------


def test_ac2_no_silent_catch_after_sms_wrapper():
    """
    GIVEN take-ist-screenshots.js nach dem Fix
    WHEN  wir den Code-Block nach sms-phone-wrapper lesen
    THEN  darf kein '.catch(() => {})' innerhalb von 400 Zeichen danach stehen

    Hintergrund: Das Original-Script schluckt Fehler stumm mit .catch(() => {}).
    Der Fix muss stattdessen ERRORS++ und console.error() im catch-Block verwenden.
    """
    src = SCRIPT.read_text()
    wrapper_pos = src.find("sms-phone-wrapper")
    if wrapper_pos == -1:
        return  # test_ac1_element_screenshot_used_for_sms deckt diesen Fall ab
    block = src[wrapper_pos : wrapper_pos + 400]
    assert ".catch(() => {})" not in block, (
        "In den 400 Zeichen nach 'sms-phone-wrapper' steht noch '.catch(() => {})' — "
        "Fehler werden stumm geschluckt statt ERRORS++ auszulösen"
    )


def test_ac2_errors_incremented_in_sms_block():
    """
    GIVEN take-ist-screenshots.js nach dem Fix
    WHEN  wir den Catch-Block um sms-phone-wrapper lesen
    THEN  muss 'ERRORS++' innerhalb von 400 Zeichen nach 'sms-phone-wrapper' vorkommen

    Hintergrund: AC-2 fordert, dass Fehlschläge beim SMS-Screenshot den globalen
    ERRORS-Zähler erhöhen, damit Exit-Code und Log korrekt sind.
    """
    src = SCRIPT.read_text()
    wrapper_pos = src.find("sms-phone-wrapper")
    if wrapper_pos == -1:
        return  # test_ac1_element_screenshot_used_for_sms deckt diesen Fall ab
    block = src[wrapper_pos : wrapper_pos + 400]
    assert "ERRORS++" in block, (
        "Kein 'ERRORS++' in den 400 Zeichen nach 'sms-phone-wrapper' — "
        "Fehlschläge beim SMS-Screenshot werden nicht korrekt gezählt"
    )
