"""TDD GREEN — Issue #1107: Ortsvergleich D — Stundenverlauf-Sektion abschaltbar.

Spec: docs/specs/modules/issue_1107_compare_hourly_toggle.md (AC-1..AC-4)
Kontext: docs/context/fix-1107-compare-sections-validator.md

Deckt diese Ebene ab:

  1. ``render_compare_html(hourly_enabled=...)`` (AC-1/AC-2),
     ``TestRenderCompareHtmlHourlyToggle``.
  2. ``send_one_compare_preset()`` liest ``preset["hourly_enabled"]`` und
     reicht es an ``render_compare_email()`` durch (``TestDispatchWiring``,
     AC-3 Wiring-Teil, offline).
  3. Der reale Versand- + IMAP-Pfad setzt den
     ``X-GZ-Compare-Hourly-Enabled``-Header und zeigt/versteckt die Sektion
     korrekt fuer beide Werte (``TestHourlySectionE2E``, AC-3, echter
     SMTP-Versand + echter IMAP-Abruf aus ``gregor-test@henemm.com``, kein
     Mock).
  4. ``render_compare_email_preview()`` reicht ``body.hourly_enabled`` an
     ``render_compare_html()`` durch (``TestPreviewParity``, AC-4, offline).

**Scope-Korrektur (2026-07-08, PO-Entscheidung):** Die urspruenglich in AC-3
vorgesehene Config-Awareness von ``.claude/hooks/email_spec_validator.py``
(``validate_structure(hourly_enabled=...)``) ist NICHT Teil dieses Workflows.
Validator-Dateien werden nie im selben Workflow geaendert, dessen Ergebnis sie
pruefen sollen (Praezedenz #1110/#1108) -- ausgelagert nach Issue #1150, s.
Spec Known Limitations. ``TestValidatorHourlyEnabledGating`` bleibt als
dokumentierte, uebersprungene (``@pytest.mark.skip``) Testklasse fuer #1150
in dieser Datei stehen, damit die Erwartung nicht verloren geht.

KEINE Mocks (Projektkonvention CLAUDE.md):
- ``TestRenderCompareHtmlHourlyToggle``/``TestPreviewParity`` sind reine
  Pure-Function-Tests gegen synthetische ``ComparisonResult``-Fixtures (kein
  Netzwerk, kein E-Mail-/API-Mock).
- ``TestDispatchWiring`` nutzt echtes Attribut-Rebind (kein ``patch()``/
  ``Mock()``) auf ``output.renderers.comparison.render_compare_email``,
  analog ``tests/tdd/test_issue_1104_compare_config_foundation.py`` — der
  vorgelagerte ``ComparisonEngine``-Lauf (inkl. Offline-Fixture-Provider aus
  ``tests/conftest.py``) findet dabei vollstaendig echt statt.
- ``TestHourlySectionE2E`` sendet real per SMTP (Stalwart-Testkonto) und
  ruft die zugestellte Mail real per IMAP aus ``gregor-test@henemm.com`` ab
  — analog ``tests/tdd/test_issue_1106_hourly_metrics_config.py::TestHourMetricsE2E``.

Go-Teil (AC-5) und Frontend-Teil (AC-6) liegen in separaten Dateien:
``internal/handler/compare_preset_hourly_enabled_test.go`` bzw.
``frontend/src/lib/components/compare/compareEditorHourlyToggle.test.ts``.
"""
from __future__ import annotations

import email as email_mod
import imaplib
import importlib.util
import time as time_mod
import uuid
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models import ForecastDataPoint, ThunderLevel
from app.profile import ActivityProfile
from app.user import ComparisonResult, LocationResult, SavedLocation


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / ".claude" / "hooks" / "email_spec_validator.py"


# ---------------------------------------------------------------------------
# Fixtures (synthetisch, offline, analog test_issue_1106_hourly_metrics_config.py)
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
    """Mindestens drei Orte mit vollstaendigen Stundendaten (AC-1 Given)."""
    locations = [
        LocationResult(
            location=_loc(f"loc-1107-{i}", name),
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


# ---------------------------------------------------------------------------
# Class 1 — render_compare_html() Renderer-Unit-Tests (AC-1/AC-2, offline)
# ---------------------------------------------------------------------------


class TestRenderCompareHtmlHourlyToggle:
    """RED: ``render_compare_html()`` kennt das Kwarg ``hourly_enabled`` noch
    nicht -> TypeError bei jedem Aufruf, der es explizit uebergibt."""

    def test_ac1_hourly_enabled_false_hides_section_but_keeps_overview(self):
        from output.renderers.email.compare_html import render_compare_html

        result = _make_comparison_result(["Ort A", "Ort B", "Ort C"])
        html = render_compare_html(
            result, profile=ActivityProfile.ALLGEMEIN, hourly_enabled=False
        )

        assert "STUNDEN" not in html, (
            "RED: Sektionskopf 'STUNDEN' muss bei hourly_enabled=False vollstaendig "
            "fehlen -- render_compare_html() kennt hourly_enabled noch nicht (der "
            "Aufruf haette bereits mit TypeError scheitern muessen)"
        )
        assert ">ORT</span>" not in html, (
            "RED: kein 'ORT <Name>'-Marker fuer irgendeinen Ort darf bei "
            "hourly_enabled=False im HTML vorkommen"
        )
        assert "Amtliche Warnungen" in html, (
            "Die Uebersichtstabelle (erste Datenzeile 'Amtliche Warnungen') muss "
            "trotz abgeschalteter Stundenverlauf-Sektion vollstaendig erhalten bleiben"
        )

    def test_ac2_hourly_enabled_true_shows_full_section_per_location(self):
        from output.renderers.email.compare_html import render_compare_html

        result = _make_comparison_result(["Ort A", "Ort B", "Ort C"])
        html_explicit = render_compare_html(
            result, profile=ActivityProfile.ALLGEMEIN, hourly_enabled=True
        )
        html_default = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)

        for html, label in ((html_explicit, "hourly_enabled=True"), (html_default, "Default")):
            assert "STUNDEN" in html, (
                f"RED ({label}): Sektionskopf 'STUNDEN' muss vorhanden sein "
                "(Regressionsschutz gegen vor diesem Slice)"
            )
            assert html.count(">ORT</span>") == 3, (
                f"RED ({label}): erwartet 3 'ORT'-Bloecke (einen je Ort), "
                f"gefunden {html.count('>ORT</span>')}"
            )


# ---------------------------------------------------------------------------
# Class 2 — send_one_compare_preset() Dispatch-Wiring (AC-3, offline, Sentinel)
# ---------------------------------------------------------------------------


class _RenderCallRecorded1107(Exception):
    """Sentinel: bricht send_one_compare_preset gezielt nach dem
    render_compare_email-Aufruf ab, bevor SMTP beruehrt wird."""

    def __init__(self, hourly_enabled):
        self.hourly_enabled = hourly_enabled
        super().__init__(f"recorded hourly_enabled={hourly_enabled!r}")


def _fresh_user() -> str:
    return f"test1107-{uuid.uuid4().hex[:8]}"


def _resolvable_location(loc_id: str) -> SavedLocation:
    """lon=25.0 liegt bewusst AUSSERHALB GEOSPHERE_BOUNDS (Alpenraum
    lat 45-50/lon 8-18, comparison_engine.py::_select_provider_for_location)
    -- erzwingt den openmeteo-Pfad, der ueber GZ_TEST_FIXTURE_DIR (autouse-
    Fixture tests/conftest.py) vollstaendig offline bedient wird. Muster aus
    test_issue_1106_hourly_metrics_config.py::_fixture_location."""
    from app.loader import SavedLocation as LoaderSavedLocation

    return LoaderSavedLocation(id=loc_id, name="Fixtureort1107", lat=47.2692, lon=25.0, elevation_m=574)


def _preset(preset_id: str, hourly_enabled, loc_id: str) -> dict:
    p = {
        "id": preset_id,
        "name": f"Vergleich {preset_id}",
        "location_ids": [loc_id],
        "schedule": "daily",
        "profil": "SUMMER_TREKKING",
        "hour_from": 9,
        "hour_to": 16,
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-01-01T00:00:00Z",
    }
    if hourly_enabled is not None:
        p["hourly_enabled"] = hourly_enabled
    return p


def _capture_hourly_enabled_kwarg(preset: dict, location, tmp_path):
    """Fuehrt send_one_compare_preset mit echtem Attribut-Rebind von
    render_compare_email aus (kein Mock) und liest zurueck, mit welchem
    hourly_enabled-Wert der Renderer tatsaechlich aufgerufen wurde."""
    import output.renderers.comparison as compare_render_mod
    from app.config import Settings
    from services.scheduler_dispatch_service import send_one_compare_preset as _send_one_compare_preset

    user_id = preset["_user_id"]
    settings = Settings().with_user_profile(user_id)

    original_render = compare_render_mod.render_compare_email

    def _recording_render_compare_email(*args, **kwargs):
        raise _RenderCallRecorded1107(kwargs.get("hourly_enabled", "NOT_PASSED"))

    compare_render_mod.render_compare_email = _recording_render_compare_email
    try:
        with pytest.raises(_RenderCallRecorded1107) as exc:
            _send_one_compare_preset(
                {k: v for k, v in preset.items() if k != "_user_id"},
                settings,
                user_id,
                str(tmp_path),
                all_locations_cache=[location],
            )
        return exc.value.hourly_enabled
    finally:
        compare_render_mod.render_compare_email = original_render


class TestDispatchWiring:
    """RED: send_one_compare_preset() liest preset['hourly_enabled'] heute
    nicht -> render_compare_email() erhaelt hourly_enabled gar nicht
    ('NOT_PASSED' statt True/False)."""

    def test_hourly_enabled_false_is_read_from_preset_and_passed_through(self, tmp_path):
        user_id = _fresh_user()
        loc = _resolvable_location("loc-1107-a")
        preset = _preset("cp-1107-false", hourly_enabled=False, loc_id="loc-1107-a")
        preset["_user_id"] = user_id

        hourly_enabled = _capture_hourly_enabled_kwarg(preset, loc, tmp_path)
        assert hourly_enabled is False, (
            f"RED: render_compare_email erhielt hourly_enabled={hourly_enabled!r}, "
            "erwartet False -- send_one_compare_preset() liest preset['hourly_enabled'] "
            "noch nicht (Top-Level-Feld, NICHT display_config) und uebergibt es nicht."
        )

    def test_missing_hourly_enabled_defaults_to_true(self, tmp_path):
        user_id = _fresh_user()
        loc = _resolvable_location("loc-1107-b")
        preset = _preset("cp-1107-default", hourly_enabled=None, loc_id="loc-1107-b")
        preset["_user_id"] = user_id

        hourly_enabled = _capture_hourly_enabled_kwarg(preset, loc, tmp_path)
        assert hourly_enabled is True, (
            f"RED: render_compare_email erhielt hourly_enabled={hourly_enabled!r}, "
            "erwartet Default True (Altdaten ohne Feld) -- kommt heute als "
            "'NOT_PASSED' an, nicht als True."
        )


# ---------------------------------------------------------------------------
# Class 3 — Echter E2E-Versand + IMAP + Validator (AC-3, kein Mock)
# ---------------------------------------------------------------------------


def _fresh_test_user() -> str:
    return f"test1107e2e-{uuid.uuid4().hex[:8]}"


def _send_compare_preset_and_fetch_message(hourly_enabled, tag: str):
    """Sendet ein Compare-Preset ECHT per SMTP ueber den echten Preset-
    Versandpfad send_one_compare_preset() und ruft die zugestellte Mail ECHT
    per IMAP aus gregor-test@henemm.com ab. Gibt das geparste
    email.message.Message zurueck (Header + Body). Muster aus
    test_issue_1106_hourly_metrics_config.py::_send_compare_preset_and_fetch_html."""
    import tempfile

    from app.config import Settings
    from services.scheduler_dispatch_service import send_one_compare_preset

    user_id = _fresh_test_user()
    settings = Settings().with_user_profile(user_id)
    if not settings.can_send_email():
        pytest.skip("SMTP nicht konfiguriert (Test-Creds fehlen)")

    unique = uuid.uuid4().hex[:8]
    preset = {
        "id": f"cp-1107-{tag}",
        "name": f"AC1107-{tag}-{unique}",
        "location_ids": ["loc-1107-e2e"],
        "schedule": "daily",
        "profil": "SUMMER_TREKKING",
        "hour_from": 9,
        "hour_to": 10,
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-01-01T00:00:00Z",
    }
    if hourly_enabled is not None:
        preset["hourly_enabled"] = hourly_enabled

    from app.loader import SavedLocation as LoaderSavedLocation

    location = LoaderSavedLocation(
        id="loc-1107-e2e", name="Fixtureort1107E2E", lat=47.2692, lon=25.0, elevation_m=574
    )

    with tempfile.TemporaryDirectory() as tmp:
        send_one_compare_preset(preset, settings, user_id, tmp, all_locations_cache=[location])

    time_mod.sleep(5)

    imap_host = settings.imap_host or settings.smtp_host
    imap_user = settings.test_imap_user or settings.imap_user or settings.smtp_user
    imap_pass = settings.test_imap_pass or settings.imap_pass or settings.smtp_pass
    imap = imaplib.IMAP4_SSL(imap_host, settings.imap_port)
    imap.login(imap_user, imap_pass)
    imap.select("INBOX")

    _, data = imap.search(None, f'SUBJECT "{unique}"')
    msg_ids = data[0].split()
    assert msg_ids, f"Compare-Mail mit ID {unique} nicht in INBOX gefunden"

    _, msg_data = imap.fetch(msg_ids[-1], "(RFC822)")
    msg = email_mod.message_from_bytes(msg_data[0][1])

    imap.close()
    imap.logout()
    return msg


def _html_body(msg) -> str:
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            return part.get_payload(decode=True).decode("utf-8")
    return ""


@pytest.mark.email
class TestHourlySectionE2E:
    """ECHTER E2E-Test: sendet via SMTP, ruft via IMAP ab. Kein Mocking.

    Beweist den Versandpfad (Header + Sektions-Sichtbarkeit) fuer beide
    hourly_enabled-Werte. Der Validator-Teil (email_spec_validator.py
    config-bewusst machen) ist NICHT Teil dieses Workflows -- Validator-
    Dateien werden nie im selben Workflow geaendert, dessen Ergebnis sie
    pruefen sollen (Praezedenz #1110/#1108). Ausgelagert nach Issue #1150,
    siehe Spec Known Limitations.
    """

    def test_hourly_enabled_false_delivers_mail_without_hour_section(self):
        msg = _send_compare_preset_and_fetch_message(hourly_enabled=False, tag="ac3false")

        assert msg.get("X-GZ-Compare-Hourly-Enabled") == "false", (
            f"Header X-GZ-Compare-Hourly-Enabled fehlt/ist "
            f"{msg.get('X-GZ-Compare-Hourly-Enabled')!r}, erwartet 'false'."
        )
        body = _html_body(msg)
        assert "STUNDEN" not in body, (
            "zugestellte Mail zeigt trotz hourly_enabled=false weiterhin die "
            "Stundenverlauf-Sektion."
        )

    def test_hourly_enabled_true_delivers_mail_with_hour_section(self):
        msg = _send_compare_preset_and_fetch_message(hourly_enabled=True, tag="ac3true")

        assert msg.get("X-GZ-Compare-Hourly-Enabled") == "true", (
            f"Header X-GZ-Compare-Hourly-Enabled fehlt/ist "
            f"{msg.get('X-GZ-Compare-Hourly-Enabled')!r}, erwartet 'true'."
        )
        body = _html_body(msg)
        assert "STUNDEN" in body, (
            "zugestellte Mail sollte bei hourly_enabled=true die "
            "Stundenverlauf-Sektion zeigen (Regressionsschutz)."
        )


# ---------------------------------------------------------------------------
# Class 4 — Validator (AC-3, dritter Teil): echtes HTML, synthetischer Splice
# ---------------------------------------------------------------------------


def _load_validator():
    """Laedt den Validator als isoliertes Modul (vermeidet sys.modules-
    Kontamination), analog test_issue_1106_hourly_metrics_config.py::_load_validator."""
    spec = importlib.util.spec_from_file_location("esv1107", str(VALIDATOR_PATH))
    if spec is None or spec.loader is None:
        raise ImportError(f"Validator nicht ladbar: {VALIDATOR_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _real_html_with_missing_location_table(missing_location_name: str = "Ort B") -> str:
    """Rendert eine echte 3-Orte-Compare-Mail (render_compare_html) und
    entfernt gezielt NUR die Stundentabelle EINES Ortes -- reiner
    String-Eingriff am echten Render-Output (Muster aus #1106, AC-6-Test),
    kein Handbau der gesamten Mail."""
    from output.renderers.email.compare_html import render_compare_html

    result = _make_comparison_result(["Ort A", missing_location_name, "Ort C"])
    html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)

    import re

    m = re.search(r">ORT</span>\s*<span[^>]*>" + re.escape(missing_location_name) + r"</span>", html)
    assert m is not None, f"Fixture-Fehler: ORT-Kopf fuer '{missing_location_name}' nicht gefunden"
    table_start = html.find("<table", m.end())
    table_end = html.find("</table>", table_start) + len("</table>")
    return html[:table_start] + html[table_end:]


@pytest.mark.skip(
    reason="Validator-Config-Awareness (email_spec_validator.py hourly_enabled-Kwarg) "
    "ausgelagert nach Issue #1150 -- Validator-Dateien werden nie im selben Workflow "
    "geaendert, dessen Ergebnis sie pruefen sollen (Praezedenz #1110/#1108), siehe Spec "
    "Known Limitations."
)
class TestValidatorHourlyEnabledGating:
    """Ausgelagert nach #1150: validate_structure() soll dort ein hourly_enabled-Kwarg
    bekommen. In diesem Workflow bewusst nicht implementiert (Scope-Korrektur)."""

    def test_hourly_enabled_false_skips_table_presence_requirement(self):
        mod = _load_validator()
        result = _make_comparison_result(["Ort A", "Ort B", "Ort C"])
        from output.renderers.email.compare_html import render_compare_html

        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN, hourly_enabled=False)

        errors = mod.validate_structure(html, hourly_enabled=False)
        assert errors == [], (
            f"RED: bei hourly_enabled=False duerfen keine Stundentabellen-Fehler "
            f"gemeldet werden (Sektion ist bewusst abgeschaltet), bekommen: {errors}"
        )

    def test_hourly_enabled_true_still_flags_missing_table_for_one_location(self):
        """Adversary-Analogie (Spec AC-3, dritter Testfall): der strikte Pfad
        darf durch die neue hourly_enabled-Ausnahme nicht global aufgeweicht
        werden -- eine tatsaechlich fehlende Stundentabelle bei
        hourly_enabled=True MUSS weiterhin gemeldet werden."""
        mod = _load_validator()
        html = _real_html_with_missing_location_table("Ort B")

        errors = mod.validate_structure(html, hourly_enabled=True)
        assert errors, (
            "RED: fehlende Stundentabelle fuer 'Ort B' muss bei hourly_enabled=True "
            "weiterhin als Fehler gemeldet werden (strikter Pfad darf nicht global "
            "aufgeweicht werden)"
        )
        assert any("Ort B" in e for e in errors), (
            f"RED: Fehlermeldung muss den betroffenen Ort 'Ort B' benennen, bekommen: {errors}"
        )


# ---------------------------------------------------------------------------
# Class 5 — Preview-Parität (AC-4, offline, Referenzfall #954)
# ---------------------------------------------------------------------------


class TestPreviewParity:
    """RED: render_compare_email_preview() liest body.hourly_enabled nicht
    und reicht es nicht an render_compare_html() durch -> die Vorschau zeigt
    trotz hourly_enabled=False weiterhin die Stundenverlauf-Sektion."""

    def _body(self, hourly_enabled: bool) -> SimpleNamespace:
        return SimpleNamespace(
            profile="allgemein",
            time_window=[9, 16],
            target_date="2026-07-08",
            winner_tags=[],
            hourly_enabled=hourly_enabled,
        )

    def test_hourly_enabled_false_hides_section_in_preview(self):
        from services.validator_render_service import render_compare_email_preview

        html = render_compare_email_preview(self._body(hourly_enabled=False))

        assert "STUNDEN" not in html, (
            "RED: Vorschau-HTML zeigt trotz hourly_enabled=False weiterhin den "
            "Sektionskopf 'STUNDEN' -- render_compare_email_preview() reicht "
            "body.hourly_enabled noch nicht an render_compare_html() durch "
            "(Referenzfall #954: Vorschau- und Versandpfad divergieren)."
        )
        assert ">ORT</span>" not in html, (
            "RED: Vorschau-HTML zeigt trotz hourly_enabled=False weiterhin einen "
            "'ORT'-Block."
        )

    def test_hourly_enabled_true_shows_section_in_preview(self):
        from services.validator_render_service import render_compare_email_preview

        html = render_compare_email_preview(self._body(hourly_enabled=True))
        assert "STUNDEN" in html, (
            "Regressionsschutz: hourly_enabled=True muss die Sektion in der "
            "Vorschau weiterhin zeigen."
        )
