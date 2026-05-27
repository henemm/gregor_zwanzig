"""
TDD RED -- Epic #404 Phase 2: IST-Screenshots Script
Spec: docs/specs/modules/epic_404_phase2_ist_screenshots.md

Alle Tests prüfen Struktur und Inhalt von
claude-code-handoff/soll-audit-2026-05-27/take-ist-screenshots.js.
Da das Script noch nicht existiert, MÜSSEN alle RED-Tests scheitern.
"""
import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "claude-code-handoff/soll-audit-2026-05-27/take-ist-screenshots.js"
SOLL_DIR = REPO_ROOT / "claude-code-handoff/soll-audit-2026-05-27/soll-screenshots"

EXPECTED_DESKTOP = [
    "desktop-home.png",
    "desktop-trips-list.png",
    "desktop-trip-detail.png",
    "desktop-metrics.png",
    "desktop-alerts.png",
    "desktop-email-preview.png",
    "desktop-sms-preview.png",
    "desktop-wp-editor.png",
    "desktop-wizard-step1.png",
    "desktop-wizard-step2.png",
    "desktop-wizard-step3.png",
    "desktop-wizard-step4.png",
    "desktop-compare-main.png",
    "desktop-archive.png",
    "desktop-location-new.png",
]

EXPECTED_MOBILE = [
    "mobile-m-home.png",
    "mobile-m-trips.png",
    "mobile-m-trip-detail.png",
    "mobile-m-alerts.png",
    "mobile-m-metrics.png",
    "mobile-m-wiz-1.png",
    "mobile-m-wiz-2.png",
    "mobile-m-wiz-3.png",
    "mobile-m-wiz-4.png",
    "mobile-m-compare.png",
    "mobile-m-wp-editor.png",
]


# ---------------------------------------------------------------------------
# Voraussetzungs-Tests (grüner Stand vor Implementierung erwartet)
# ---------------------------------------------------------------------------

def test_soll_screenshots_vorhanden():
    """Voraussetzung: Phase-1-SOLL-Screenshots als Referenz vorhanden."""
    assert SOLL_DIR.exists(), f"SOLL-Verzeichnis fehlt: {SOLL_DIR}"
    pngs = list(SOLL_DIR.glob("*.png"))
    assert len(pngs) >= 20, f"Zu wenige SOLL-Screenshots: {len(pngs)}"


def test_soll_naming_deckt_expected_desktop_ab():
    """Voraussetzung: Jeder geplante IST-Desktop-Name hat ein SOLL-Pendant."""
    soll_names = {f.name for f in SOLL_DIR.glob("desktop-*.png")}
    for name in EXPECTED_DESKTOP:
        assert name in soll_names, (
            f"Kein SOLL-Pendant fuer '{name}' -- Screenshot-Namen in Spec prüfen"
        )


def test_soll_naming_deckt_expected_mobile_ab():
    """Voraussetzung: Jeder geplante IST-Mobile-Name hat ein SOLL-Pendant."""
    soll_names = {f.name for f in SOLL_DIR.glob("mobile-m-*.png")}
    for name in EXPECTED_MOBILE:
        assert name in soll_names, (
            f"Kein SOLL-Pendant fuer '{name}' -- Screenshot-Namen in Spec prüfen"
        )


def test_gpx_fixture_vorhanden():
    """Voraussetzung: GPX-Fixture fuer Wizard-Step-2-Upload vorhanden."""
    gpx = REPO_ROOT / "frontend/e2e/fixtures/test-trip.gpx"
    assert gpx.exists(), f"GPX-Fixture fehlt: {gpx}"


def test_env_playwright_vorhanden():
    """Voraussetzung: Staging-Credentials-Datei vorhanden."""
    env = REPO_ROOT / "frontend/.env.playwright"
    assert env.exists(), f".env.playwright fehlt: {env}"
    content = env.read_text()
    assert "E2E_USER" in content
    assert "E2E_PASS" in content


# ---------------------------------------------------------------------------
# RED-Tests -- MÜSSEN scheitern (Script existiert noch nicht)
# ---------------------------------------------------------------------------

def _script() -> str:
    assert SCRIPT_PATH.exists(), (
        f"Script fehlt: {SCRIPT_PATH}\n"
        "  -> Implementierung noch nicht erfolgt (erwartetes RED)"
    )
    return SCRIPT_PATH.read_text(encoding="utf-8")


def test_script_existiert():
    """AC-1: Script-Datei am erwarteten Pfad vorhanden."""
    assert SCRIPT_PATH.exists(), f"Script nicht gefunden: {SCRIPT_PATH}"


def test_script_definiert_staging_url():
    """AC-2: Script muss BASE_URL auf Staging zeigen."""
    script = _script()
    assert "https://staging.gregor20.henemm.com" in script


def test_script_definiert_trip_id():
    """AC-3: Script muss TRIP_ID = 'e2e-cockpit-test' enthalten."""
    script = _script()
    assert "e2e-cockpit-test" in script


def test_script_definiert_login_funktion():
    """AC-2: Script muss login()-Funktion mit waitForURL definieren."""
    script = _script()
    assert "login" in script
    assert "waitForURL" in script


def test_script_definiert_seed_trip_funktion():
    """AC-3: Script muss seedTrip()-Funktion definieren."""
    script = _script()
    assert "seedTrip" in script


def test_script_definiert_wizard_steps_funktion():
    """AC-6: Script muss wizardSteps()-Funktion mit setInputFiles definieren."""
    script = _script()
    assert "wizardSteps" in script
    assert "setInputFiles" in script


def test_script_enthaelt_gpx_upload_referenz():
    """AC-6: Script muss GPX-Fixture-Pfad fuer Wizard-Upload referenzieren."""
    script = _script()
    assert "test-trip.gpx" in script


def test_script_referenziert_alle_desktop_screenshots():
    """AC-4: Script muss alle 15 Desktop-Screenshot-Namen enthalten."""
    script = _script()
    missing = [name for name in EXPECTED_DESKTOP if name not in script]
    assert not missing, f"Fehlende Desktop-Referenzen: {missing}"


def test_script_referenziert_alle_mobile_screenshots():
    """AC-5: Script muss alle 11 Mobile-Screenshot-Namen enthalten."""
    script = _script()
    missing = [name for name in EXPECTED_MOBILE if name not in script]
    assert not missing, f"Fehlende Mobile-Referenzen: {missing}"


def test_script_verwendet_desktop_viewport():
    """AC-4: Script muss Desktop-Viewport 1440 px Breite definieren."""
    script = _script()
    assert "1440" in script


def test_script_verwendet_mobile_viewport():
    """AC-5: Script muss Mobile-Viewport 390 px Breite definieren."""
    script = _script()
    assert "390" in script


def test_script_enthaelt_zusammenfassung():
    """AC-7: Script muss Abschluss-Zusammenfassung ausgeben."""
    script = _script()
    assert "fertig" in script.lower()


def test_script_setzt_exit_code_bei_fehler():
    """AC-7: Script muss bei Fehlern mit Exit-Code 1 enden."""
    script = _script()
    assert "process.exit(1)" in script


def test_ist_screenshots_count_gesamt():
    """AC-4 + AC-5: Gesamt-Screenshot-Anzahl muss 26 ergeben (15+11)."""
    assert len(EXPECTED_DESKTOP) == 15, f"Desktop-Liste: {len(EXPECTED_DESKTOP)} Eintraege, erwartet 15"
    assert len(EXPECTED_MOBILE) == 11, f"Mobile-Liste: {len(EXPECTED_MOBILE)} Eintraege, erwartet 11"
    assert len(EXPECTED_DESKTOP) + len(EXPECTED_MOBILE) == 26
