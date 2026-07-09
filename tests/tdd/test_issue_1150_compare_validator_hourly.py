"""Issue #1150 — Compare-Mail-Validator config-bewusst fuer hourly_enabled.

RED-Phase: `email_spec_validator.py` kennt das `hourly_enabled`-Kwarg noch
nicht und liest den Marker-Header `X-GZ-Compare-Hourly-Enabled` nicht. Diese
Tests belegen das gewuenschte Verhalten aus Nutzersicht gegen ECHTES
Renderer-HTML (`render_compare_html`) — kein Mock, kein Patch, echter Parser.

Muster: analog test_issue_1106_hourly_metrics_config.py / test_issue_1110 —
reales HTML aus dem Renderer wird an die reine Parse-Funktion
`validate_structure()` gegeben. Der volle IMAP-/Header-Pfad (`run_validation`)
wird zusaetzlich per echter Zustellung ans Stalwart-Test-Postfach verifiziert
(AC-1/AC-2, Validate-Phase).
"""

from __future__ import annotations

import email.message
import importlib.util
import inspect
import time as time_mod
import uuid
from datetime import date, datetime
from pathlib import Path

import pytest

from app.models import ForecastDataPoint, ThunderLevel
from app.profile import ActivityProfile
from app.user import ComparisonResult, LocationResult, SavedLocation


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / ".claude" / "hooks" / "email_spec_validator.py"


# ---------------------------------------------------------------------------
# Fixtures (synthetisch, offline, analog test_issue_1107_compare_sections.py)
# ---------------------------------------------------------------------------


def _loc(loc_id: str, name: str) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=47.27, lon=11.39, elevation_m=574)


def _dp(hour: int, **overrides) -> ForecastDataPoint:
    defaults = dict(
        ts=datetime(2026, 7, 8, hour, 0),
        t2m_c=20.0,
        wind_chill_c=19.0,
        wind10m_kmh=10.0,
        gust_kmh=18.0,
        precip_1h_mm=0.0,
        cloud_total_pct=30,
        uv_index=4.0,
        thunder_level=ThunderLevel.NONE,
        pop_pct=15,
        visibility_m=9000,
    )
    defaults.update(overrides)
    return ForecastDataPoint(**defaults)


def _make_comparison_result(names: list) -> ComparisonResult:
    """Mindestens drei Orte mit vollstaendigen Stundendaten."""
    locations = [
        LocationResult(
            location=_loc(f"loc-1150-{i}", name),
            temp_max=20.0 + i,
            wind_max=10.0,
            sunny_hours=5.0,
            cloud_avg=30,
            official_alerts=[],
            hourly_data=[_dp(9), _dp(10)],
        )
        for i, name in enumerate(names)
    ]
    return ComparisonResult(
        locations=locations,
        time_window=(9, 16),
        target_date=date(2026, 7, 8),
        created_at=datetime(2026, 7, 8, 4, 0),
    )


def _load_validator():
    """Laedt den Validator als isoliertes Modul (vermeidet sys.modules-
    Kontamination), analog test_issue_1106/1107::_load_validator."""
    spec = importlib.util.spec_from_file_location("esv1150", str(VALIDATOR_PATH))
    if spec is None or spec.loader is None:
        raise ImportError(f"Validator nicht ladbar: {VALIDATOR_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _real_html_with_missing_location_table(missing_location_name: str = "Ort B") -> str:
    """Rendert eine echte 3-Orte-Compare-Mail (render_compare_html) und
    entfernt gezielt NUR die Stundentabelle EINES Ortes — reiner String-
    Eingriff am echten Render-Output (Muster #1106 AC-6), kein Handbau."""
    from output.renderers.email.compare_html import render_compare_html
    import re

    result = _make_comparison_result(["Ort A", missing_location_name, "Ort C"])
    html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)

    m = re.search(
        r">ORT</span>\s*<span[^>]*>" + re.escape(missing_location_name) + r"</span>", html
    )
    assert m is not None, f"Fixture-Fehler: ORT-Kopf fuer '{missing_location_name}' nicht gefunden"
    table_start = html.find("<table", m.end())
    table_end = html.find("</table>", table_start) + len("</table>")
    return html[:table_start] + html[table_end:]


def _render_and_drop_table(names: list, drop_name: str) -> str:
    """Rendert eine echte Compare-Mail (render_compare_html) mit gegebener
    Ortsliste und entfernt gezielt NUR die Stundentabelle EINES benannten
    Ortes (reiner String-Eingriff am echten Render-Output, Muster wie
    _real_html_with_missing_location_table). Erlaubt es, auch den ERSTEN oder
    LETZTEN Ort zu treffen (Adversary F001, Issue #1150)."""
    from output.renderers.email.compare_html import render_compare_html
    import re

    result = _make_comparison_result(names)
    html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)

    m = re.search(
        r">ORT</span>\s*<span[^>]*>" + re.escape(drop_name) + r"</span>", html
    )
    assert m is not None, f"Fixture-Fehler: ORT-Kopf fuer '{drop_name}' nicht gefunden"
    table_start = html.find("<table", m.end())
    table_end = html.find("</table>", table_start) + len("</table>")
    return html[:table_start] + html[table_end:]


# ---------------------------------------------------------------------------
# AC-1 — hourly_enabled=False ueberspringt die Stundentabellen-Pflicht
# ---------------------------------------------------------------------------


def test_ac1_hourly_false_skips_hourly_table_requirement():
    """Given eine echte Compare-Mail mit abgeschaltetem Stundenverlauf
    (hourly_enabled=False, keine Orts-Stundentabellen) / When
    validate_structure(html, hourly_enabled=False) laeuft / Then keine
    STRUKTUR-Fehler zu fehlenden Stundentabellen."""
    from output.renderers.email.compare_html import render_compare_html

    mod = _load_validator()
    result = _make_comparison_result(["Ort A", "Ort B", "Ort C"])
    html = render_compare_html(
        result, profile=ActivityProfile.ALLGEMEIN, hourly_enabled=False
    )

    errors = mod.validate_structure(html, hourly_enabled=False)
    assert errors == [], (
        f"Bei hourly_enabled=False duerfen keine Stundentabellen-Fehler gemeldet "
        f"werden (Sektion bewusst abgeschaltet), bekommen: {errors}"
    )


# ---------------------------------------------------------------------------
# AC-2 — hourly_enabled=True bleibt fuer die vollstaendige Mail streng gruen
# ---------------------------------------------------------------------------


def test_ac2_hourly_true_full_mail_passes():
    """Given eine echte, vollstaendige Compare-Mail mit Stundentabellen /
    When validate_structure(html, hourly_enabled=True) laeuft / Then keine
    Fehler (unveraendertes strenges Verhalten fuer den aktivierten Fall)."""
    from output.renderers.email.compare_html import render_compare_html

    mod = _load_validator()
    result = _make_comparison_result(["Ort A", "Ort B", "Ort C"])
    html = render_compare_html(
        result, profile=ActivityProfile.ALLGEMEIN, hourly_enabled=True
    )

    errors = mod.validate_structure(html, hourly_enabled=True)
    assert errors == [], (
        f"Vollstaendige Mail mit hourly_enabled=True muss weiterhin fehlerfrei "
        f"validieren, bekommen: {errors}"
    )


# ---------------------------------------------------------------------------
# AC-3 — Gold-Standard-Negativfall: hourly=True + fehlende Tabelle => Fehler
# ---------------------------------------------------------------------------


def test_ac3_hourly_true_flags_missing_table_for_one_location():
    """Given echt gerendertes HTML mit gezielt fehlender Stundentabelle fuer
    EINEN Ort / When validate_structure(html, hourly_enabled=True) laeuft /
    Then mindestens ein STRUKTUR-Fehler, der den Ort benennt. Erosionsschutz:
    ein globales Aufweichen (if hourly_enabled entfernt/invertiert) macht den
    Test rot."""
    mod = _load_validator()
    html = _real_html_with_missing_location_table("Ort B")

    errors = mod.validate_structure(html, hourly_enabled=True)
    assert errors, (
        "Fehlende Stundentabelle fuer 'Ort B' MUSS bei hourly_enabled=True als "
        "Fehler gemeldet werden (strikter Pfad darf nicht global aufgeweicht werden)"
    )
    assert any("Ort B" in e for e in errors), (
        f"Fehlermeldung muss den betroffenen Ort 'Ort B' benennen, bekommen: {errors}"
    )


# ---------------------------------------------------------------------------
# AC-4 — sicherer Default: Bestandsaufruf (ohne Kwarg == True) bleibt streng
# ---------------------------------------------------------------------------


def test_ac4_default_stays_strict_for_missing_table():
    """Given echt gerendertes HTML mit fehlender Stundentabelle / When
    validate_structure(html) OHNE Kwarg (== Bestandsvertrag, wie run_validation
    ihn bei fehlendem Header ueber Default True erzeugt) UND explizit mit
    hourly_enabled=True aufgerufen wird / Then beide melden den Fehler — der
    Default weicht das Verhalten nicht auf."""
    mod = _load_validator()
    html = _real_html_with_missing_location_table("Ort B")

    errors_default = mod.validate_structure(html)
    errors_explicit_true = mod.validate_structure(html, hourly_enabled=True)

    assert errors_default, (
        "Bestandsaufruf validate_structure(html) (Default True) muss die fehlende "
        "Stundentabelle weiterhin melden — Default ist der sichere strenge Pfad"
    )
    assert errors_explicit_true, "hourly_enabled=True muss den Fehler ebenfalls melden"


# ---------------------------------------------------------------------------
# AC-5 — Fetch-Refactor: neue Helfer existieren, oeffentlicher Vertrag bleibt
# ---------------------------------------------------------------------------


def test_ac5_fetch_refactor_helpers_exist_and_contract_preserved():
    """Given den Fetch-Refactor / When das Validator-Modul geladen wird / Then
    existieren die Helfer _fetch_latest_message und _extract_html_body, und
    validate_structure akzeptiert das optionale hourly_enabled-Kwarg mit
    Default True (oeffentlicher Vertrag fetch_latest_email() -> str bleibt)."""
    mod = _load_validator()

    assert hasattr(mod, "_fetch_latest_message"), (
        "Refactor unvollstaendig: Helfer _fetch_latest_message fehlt"
    )
    assert hasattr(mod, "_extract_html_body"), (
        "Refactor unvollstaendig: Helfer _extract_html_body fehlt"
    )
    assert hasattr(mod, "fetch_latest_email"), "Oeffentlicher Vertrag fehlt"

    sig = inspect.signature(mod.validate_structure)
    assert "hourly_enabled" in sig.parameters, (
        "validate_structure muss ein hourly_enabled-Kwarg haben"
    )
    assert sig.parameters["hourly_enabled"].default is True, (
        "hourly_enabled muss den sicheren Default True haben"
    )


def test_ac5_extract_html_body_parses_real_message():
    """Given eine echt geparste multipart-Mail mit text/html-Teil / When
    _extract_html_body(msg) laeuft / Then wird der HTML-Body zurueckgegeben
    (echter email-Parser, kein Mock) — beweist den Body/Header-Split des
    Refactors."""
    mod = _load_validator()

    msg = email.message.EmailMessage()
    msg["Subject"] = "Compare Test"
    msg["X-GZ-Compare-Hourly-Enabled"] = "false"
    msg.set_content("Plaintext-Variante")
    msg.add_alternative("<html><body><p>Hallo Welt</p></body></html>", subtype="html")

    body = mod._extract_html_body(msg)
    assert "Hallo Welt" in body, (
        f"_extract_html_body muss den text/html-Teil liefern, bekommen: {body!r}"
    )
    # Header aus derselben Nachricht lesbar (Basis der run_validation-Logik)
    assert msg.get("X-GZ-Compare-Hourly-Enabled") == "false"


# ---------------------------------------------------------------------------
# F001 (Adversary, Issue #1150) — fehlende Tabelle beim LETZTEN/ERSTEN Ort
# darf nicht die Legende/Footer-Tabelle einsammeln (falsche Meldung), sondern
# muss korrekt "nicht gefunden" melden.
# ---------------------------------------------------------------------------


def test_last_location_missing_table_is_flagged():
    """Given echt gerendertes HTML, bei dem die Stundentabelle des LETZTEN
    Ortes ('Ort C') fehlt (kein Folge-ORT-Kopf, Legende/Footer folgen) / When
    validate_structure(html, hourly_enabled=True) laeuft / Then ein Fehler,
    der 'Ort C' UND 'nicht gefunden' nennt — NICHT 'Mindestspalten' (die
    Legende/Footer-Tabelle darf nicht faelschlich eingesammelt werden)."""
    mod = _load_validator()
    html = _render_and_drop_table(["Ort A", "Ort B", "Ort C"], "Ort C")

    errors = mod.validate_structure(html, hourly_enabled=True)
    matching = [e for e in errors if "Ort C" in e]
    assert matching, (
        f"Fehlende Stundentabelle des LETZTEN Ortes 'Ort C' muss gemeldet werden, "
        f"bekommen: {errors}"
    )
    assert any("nicht gefunden" in e for e in matching), (
        f"Meldung fuer 'Ort C' muss 'nicht gefunden' lauten (nicht die "
        f"faelschlich eingesammelte Footer/Legende-Tabelle), bekommen: {matching}"
    )
    assert not any("Mindestspalten" in e for e in matching), (
        f"Meldung fuer 'Ort C' darf NICHT 'Mindestspalten' sein (Maskierung durch "
        f"Legende/Footer-Tabelle), bekommen: {matching}"
    )


def test_first_location_missing_table_is_flagged():
    """Given echt gerendertes HTML, bei dem die Stundentabelle des ERSTEN
    Ortes ('Ort A') fehlt / When validate_structure(html, hourly_enabled=True)
    laeuft / Then ein Fehler, der 'Ort A' UND 'nicht gefunden' nennt."""
    mod = _load_validator()
    html = _render_and_drop_table(["Ort A", "Ort B", "Ort C"], "Ort A")

    errors = mod.validate_structure(html, hourly_enabled=True)
    matching = [e for e in errors if "Ort A" in e]
    assert matching, (
        f"Fehlende Stundentabelle des ERSTEN Ortes 'Ort A' muss gemeldet werden, "
        f"bekommen: {errors}"
    )
    assert any("nicht gefunden" in e for e in matching), (
        f"Meldung fuer 'Ort A' muss 'nicht gefunden' lauten, bekommen: {matching}"
    )


# ---------------------------------------------------------------------------
# AC-1/AC-2 (Validate-Phase) — ECHTER E2E-Zustellpfad: reale Compare-Mail ueber
# den Preset-Versandpfad an gregor-test@henemm.com senden und vom ECHTEN
# Validator (run_validation, IMAP-Fetch + Header-Auswertung) bewerten lassen.
# KEIN Mock. Muster: test_issue_1107_compare_sections.py::TestHourlySectionE2E
# und test_issue_1106_hourly_metrics_config.py::_send_compare_preset_and_fetch_html.
# ---------------------------------------------------------------------------


def _fixture_locations_3(loc_ids: list) -> list:
    """Drei aufloesbare Fixture-Orte. lon=25.0 liegt bewusst AUSSERHALB der
    GEOSPHERE_BOUNDS (comparison_engine.py::_select_provider_for_location,
    Alpenraum lat 45-50/lon 8-18) -- erzwingt den openmeteo-Pfad, der ueber
    GZ_TEST_FIXTURE_DIR (autouse-Fixture tests/conftest.py) vollstaendig
    offline bedient wird (nearest() -> zillertal.json). Drei verschiedene
    IDs/Namen ergeben drei Spalten in der Uebersichtstabelle (>=3 Orte fuer
    validate_location_count), identische Koordinaten ergeben identische
    Stundenspalten (Cross-Location-Konsistenz gruen)."""
    from app.loader import SavedLocation as LoaderSavedLocation

    names = ["Fixtureort1150A", "Fixtureort1150B", "Fixtureort1150C"]
    return [
        LoaderSavedLocation(id=lid, name=nm, lat=47.2692, lon=25.0, elevation_m=574)
        for lid, nm in zip(loc_ids, names)
    ]


def _send_compare_preset_3loc(hourly_enabled, tag: str) -> str:
    """Sendet ECHT ein Compare-Preset mit DREI Orten per SMTP ueber den echten
    Preset-Versandpfad send_one_compare_preset() an gregor-test@henemm.com
    (kein Mock, kein Intercept). hour_from=9/hour_to=16 deckt den vom Validator
    hart geprueften Stundenfenster-Vertrag (validate_hourly_table Default 9-16)
    ab. Gibt den eindeutigen Subject-Tag zurueck, damit der Aufrufer
    verifizieren kann, dass die zuletzt zugestellte Mail die eigene ist
    (run_validation nimmt all_ids[-1])."""
    import tempfile

    from app.config import Settings
    from services.scheduler_dispatch_service import send_one_compare_preset

    user_id = f"test1150e2e-{uuid.uuid4().hex[:8]}"
    settings = Settings().with_user_profile(user_id)
    if not settings.can_send_email():
        pytest.skip("SMTP nicht konfiguriert (Test-Creds fehlen)")

    unique = uuid.uuid4().hex[:8]
    loc_ids = ["loc-1150-e2e-a", "loc-1150-e2e-b", "loc-1150-e2e-c"]
    preset = {
        "id": f"cp-1150-{tag}",
        "name": f"AC1150-{tag}-{unique}",
        "location_ids": loc_ids,
        "schedule": "daily",
        "profil": "SUMMER_TREKKING",
        "hour_from": 9,
        "hour_to": 16,
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-01-01T00:00:00Z",
    }
    if hourly_enabled is not None:
        preset["hourly_enabled"] = hourly_enabled

    locations = _fixture_locations_3(loc_ids)
    with tempfile.TemporaryDirectory() as tmp:
        send_one_compare_preset(preset, settings, user_id, tmp, all_locations_cache=locations)

    # Anti-Race: kurz warten, damit die eigene Mail als letzte in der INBOX
    # liegt (run_validation liest all_ids[-1]). Muster aus der #1107-Vorlage.
    time_mod.sleep(5)
    return unique


def _assert_latest_is_ours(mod, unique: str, expected_header: str):
    """Holt die neueste Mail ueber den ECHTEN Validator-Fetch
    (_fetch_latest_message) und stellt sicher, dass es die eigene ist
    (Subject enthaelt den unique-Tag) UND den erwarteten Marker-Header traegt.
    Verhindert, dass run_validation eine fremde Mail bewertet (gemeinsames
    Postfach)."""
    msg = mod._fetch_latest_message()
    subject = msg.get("Subject", "")
    if unique not in subject:
        pytest.skip(
            f"Gemeinsames Test-Postfach: neueste Mail ist nicht die eigene "
            f"(Subject={subject!r}, erwartet Tag {unique}). Race mit anderer "
            f"Session -- Zustellnachweis nicht eindeutig, kein Fehlurteil."
        )
    actual = msg.get("X-GZ-Compare-Hourly-Enabled")
    assert actual == expected_header, (
        f"Marker-Header X-GZ-Compare-Hourly-Enabled der zugestellten Mail ist "
        f"{actual!r}, erwartet {expected_header!r}."
    )


@pytest.mark.email
def test_ac1_e2e_hourly_false_validator_passes():
    """AC-1 (E2E): Eine REAL ueber den Preset-Versandpfad zugestellte Compare-
    Mail mit hourly_enabled=False (>=3 Orte, KEINE Stundentabellen) wird vom
    ECHTEN Validator (run_validation, IMAP-Fetch + Header-Auswertung) als
    fehlerfrei bewertet -- der Header 'false' ueberspringt die
    Stundentabellen-Pflicht."""
    unique = _send_compare_preset_3loc(hourly_enabled=False, tag="ac1false")
    mod = _load_validator()

    _assert_latest_is_ours(mod, unique, expected_header="false")

    success, errors = mod.run_validation(min_locations=3)
    assert success is True, (
        f"AC-1: reale hourly_enabled=false-Mail muss vom Validator bestanden "
        f"werden (Stundentabellen-Pflicht entfaellt), Fehler: {errors}"
    )
    assert errors == [], f"AC-1: keine Fehler erwartet, bekommen: {errors}"


@pytest.mark.email
def test_ac2_e2e_hourly_true_validator_passes():
    """AC-2 (E2E): Eine REAL zugestellte Compare-Mail mit hourly_enabled=True
    (>=3 Orte, vollstaendige Stundentabellen 09:00-16:00) bleibt auf dem
    strengen Validator-Pfad (run_validation) gruen -- der Header 'true' aendert
    das bisherige strenge Verhalten nicht."""
    unique = _send_compare_preset_3loc(hourly_enabled=True, tag="ac2true")
    mod = _load_validator()

    _assert_latest_is_ours(mod, unique, expected_header="true")

    success, errors = mod.run_validation(min_locations=3)
    assert success is True, (
        f"AC-2: reale hourly_enabled=true-Mail (vollstaendige Stundentabellen) "
        f"muss den strengen Validator-Pfad bestehen, Fehler: {errors}"
    )
    assert errors == [], f"AC-2: keine Fehler erwartet, bekommen: {errors}"
