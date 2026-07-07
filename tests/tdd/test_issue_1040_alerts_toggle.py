"""TDD RED — Issue #1040: Amtliche Alerts Slice 5 — Konfiguration pro Orts-Vergleich.

SPEC: docs/specs/modules/issue_1040_alerts_toggle.md
AC-1, AC-2, AC-3 (Python-Teil)

Diese Tests schlagen ABSICHTLICH fehl, weil `ComparisonEngine.run()` den
Parameter `official_alerts_enabled` noch nicht kennt (TypeError bei AC-1/AC-2 --
gilt laut Team-Lead-Briefing als gueltiges RED, analog zum Compile-Fehler bei
Go) bzw. weil `send_one_compare_preset()` den Parameter noch nicht an
`ComparisonEngine.run()` durchreicht (AC-3, Python-Teil).

KEINE Mocks (Projektkonvention CLAUDE.md): Die Test-Fake-Quelle ist ein echtes
Python-Objekt, das das `OfficialAlertSource`-Protocol strukturell erfuellt und
ueber `register_official_alert_source()` im echten Codepfad registriert wird --
kein `Mock()`/`patch()`/`MagicMock`. Fuer AC-3 (Python-Teil) wird -- analog zum
etablierten Muster in `tests/tdd/test_issue_764_compare_forecast_hours_consume.py`
-- eine echte Subklasse von `ComparisonEngine` verwendet, die den durchgereichten
Kwarg aufzeichnet und danach gezielt via Sentinel-Exception abbricht, BEVOR
Netzwerk (Open-Meteo) oder SMTP beruehrt werden.

Alle Engine-Aufrufe (AC-1/AC-2) fahren gegen den Offline-`FixtureProvider`
(aktiviert automatisch via die autouse-Fixture in `tests/conftest.py`,
GZ_TEST_FIXTURE_DIR). Die Orte liegen bewusst ausserhalb der GeoSphere-
Bounding-Box (lat 45-50, lon 8-18) an der Cote d'Azur (Primaer-Szenario des
Epics #1033), damit `_select_provider_for_location()` den `openmeteo`-Zweig
waehlt und der Fixture-Provider greift statt eines echten GeoSphere-Netzwerkrufs.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest

from app.profile import ActivityProfile
from app.user import SavedLocation
from output.renderers.comparison import render_comparison_text
from output.renderers.email.compare_html import render_compare_html
from services.comparison_engine import ComparisonEngine


def _riviera_locations() -> list[SavedLocation]:
    """Drei reale Cote-d'Azur-Orte, alle ausserhalb der GeoSphere-Bounding-Box
    (lat 45-50 / lon 8-18) -> ComparisonEngine waehlt den openmeteo-Zweig, der
    ueber die autouse-Fixture in tests/conftest.py auf den Offline-
    FixtureProvider umgeleitet wird (kein echter Netzwerkruf)."""
    return [
        SavedLocation(id="riviera-nice", name="Nizza", lat=43.7102, lon=7.2620, elevation_m=10),
        SavedLocation(id="riviera-cannes", name="Cannes", lat=43.5528, lon=7.0174, elevation_m=12),
        SavedLocation(id="riviera-marseille", name="Marseille", lat=43.2965, lon=5.3698, elevation_m=8),
    ]


class _CountingSingleLocationOfficialAlertSource:
    """Echte Quelle (kein Mock), die nur fuer einen konkreten Ort (bbox-Toleranz
    0.05 Grad) zustaendig ist, dort genau einen OfficialAlert liefert und jeden
    fetch()-Aufruf zaehlt (Beweis fuer AC-1: Fetch darf bei False nicht passieren)."""

    def __init__(self, lat: float, lon: float, alert) -> None:
        self._lat = lat
        self._lon = lon
        self._alert = alert
        self.fetch_calls = 0

    @property
    def name(self) -> str:
        return "test-toggle-source"

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat: float, lon: float):
        self.fetch_calls += 1
        return [self._alert]


class TestIssue1040AlertsToggleAC1AC2:
    """AC-1/AC-2: `ComparisonEngine.run(..., official_alerts_enabled=...)` steuert,
    ob die registrierten Official-Alert-Quellen ueberhaupt aufgerufen werden."""

    def test_ac1_disabled_skips_fetch_and_hides_warning(self):
        """AC-1: official_alerts_enabled=False -> Fake-Quelle wird NICHT
        aufgerufen (Call-Counter=0), keine Warnzeile in HTML/Text.

        RED: `ComparisonEngine.run()` kennt den Kwarg `official_alerts_enabled`
        noch nicht -> TypeError beim Aufruf. Gilt als gueltiges RED (analog zum
        Go-Compile-Fehler).
        """
        import services.official_alerts.base as oa_base
        from services.official_alerts import OfficialAlert, register_official_alert_source

        backup = list(oa_base._REGISTERED_SOURCES)
        oa_base._REGISTERED_SOURCES.clear()
        try:
            locations = _riviera_locations()
            nice = locations[0]
            alert = OfficialAlert(
                source="test-toggle",
                hazard="thunderstorm",
                level=3,
                label="Gewitterwarnung Stufe Orange",
            )
            counting_source = _CountingSingleLocationOfficialAlertSource(nice.lat, nice.lon, alert)
            register_official_alert_source(counting_source)

            target = date.today() + timedelta(days=1)

            result = ComparisonEngine.run(
                locations,
                time_window=(9, 16),
                target_date=target,
                profile=ActivityProfile.ALLGEMEIN,
                official_alerts_enabled=False,
            )

            assert counting_source.fetch_calls == 0, (
                f"official_alerts_enabled=False muss den Fetch der registrierten "
                f"Quelle verhindern, aber fetch() wurde {counting_source.fetch_calls}x aufgerufen"
            )
            for loc_result in result.locations:
                assert loc_result.official_alerts == [], (
                    f"Bei official_alerts_enabled=False muss official_alerts fuer "
                    f"jeden Ort leer bleiben, war {loc_result.official_alerts!r} "
                    f"fuer {loc_result.location.name}"
                )

            html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)
            assert alert.label not in html, (
                "Bei official_alerts_enabled=False darf die Warn-Zeile nicht im HTML erscheinen"
            )
            text = render_comparison_text(result, profile=ActivityProfile.ALLGEMEIN)
            assert alert.label not in text, (
                "Bei official_alerts_enabled=False darf die Warn-Zeile nicht im Text erscheinen"
            )
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)

    def test_ac2_enabled_true_calls_source_and_shows_warning(self):
        """AC-2: official_alerts_enabled=True (bzw. Default ohne Parameter) ->
        Fake-Quelle wird aufgerufen (Call-Counter>=1), Warnzeile erscheint in
        HTML und Text -- Verhalten identisch zu #1034-#1037.

        RED: `ComparisonEngine.run()` kennt den Kwarg `official_alerts_enabled`
        noch nicht -> TypeError beim expliziten True-Aufruf.
        """
        import services.official_alerts.base as oa_base
        from services.official_alerts import OfficialAlert, register_official_alert_source

        backup = list(oa_base._REGISTERED_SOURCES)
        oa_base._REGISTERED_SOURCES.clear()
        try:
            locations = _riviera_locations()
            nice = locations[0]
            alert = OfficialAlert(
                source="test-toggle",
                hazard="thunderstorm",
                level=3,
                label="Gewitterwarnung Stufe Orange",
            )
            counting_source = _CountingSingleLocationOfficialAlertSource(nice.lat, nice.lon, alert)
            register_official_alert_source(counting_source)

            target = date.today() + timedelta(days=1)

            result = ComparisonEngine.run(
                locations,
                time_window=(9, 16),
                target_date=target,
                profile=ActivityProfile.ALLGEMEIN,
                official_alerts_enabled=True,
            )

            assert counting_source.fetch_calls >= 1, (
                f"official_alerts_enabled=True muss den Fetch der registrierten "
                f"Quelle ausloesen, aber fetch() wurde {counting_source.fetch_calls}x aufgerufen"
            )

            html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)
            assert alert.label in html, (
                "Bei official_alerts_enabled=True muss die Warn-Zeile im HTML erscheinen"
            )
            text = render_comparison_text(result, profile=ActivityProfile.ALLGEMEIN)
            assert alert.label in text, (
                "Bei official_alerts_enabled=True muss die Warn-Zeile im Text erscheinen"
            )
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)

    def test_ac2_default_without_parameter_behaves_like_enabled(self):
        """AC-2: Aufruf ganz OHNE den Parameter (Default) -> Verhalten identisch
        zu #1034-#1037 (Quelle wird aufgerufen, Badge erscheint).

        Dieser Teil ist bereits heute gruen (Default-Verhalten unveraendert),
        dient aber als Beweis, dass der neue Parameter additiv/abwaertskompatibel
        eingefuehrt werden muss -- nach Einfuehrung des Kwargs (GREEN) muss er
        weiterhin gruen bleiben.
        """
        import services.official_alerts.base as oa_base
        from services.official_alerts import OfficialAlert, register_official_alert_source

        backup = list(oa_base._REGISTERED_SOURCES)
        oa_base._REGISTERED_SOURCES.clear()
        try:
            locations = _riviera_locations()
            nice = locations[0]
            alert = OfficialAlert(
                source="test-toggle",
                hazard="thunderstorm",
                level=3,
                label="Gewitterwarnung Stufe Orange",
            )
            counting_source = _CountingSingleLocationOfficialAlertSource(nice.lat, nice.lon, alert)
            register_official_alert_source(counting_source)

            target = date.today() + timedelta(days=1)

            result = ComparisonEngine.run(
                locations,
                time_window=(9, 16),
                target_date=target,
                profile=ActivityProfile.ALLGEMEIN,
            )

            assert counting_source.fetch_calls >= 1, (
                f"Ohne Parameter (Default) muss der Fetch weiterhin ausgeloest werden, "
                f"aber fetch() wurde {counting_source.fetch_calls}x aufgerufen"
            )
            html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)
            assert alert.label in html, (
                "Ohne Parameter (Default) muss die Warn-Zeile weiterhin im HTML erscheinen"
            )
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)


class _OfficialAlertsEnabledRecorded(Exception):
    """Sentinel: bricht send_one_compare_preset gezielt nach dem Engine-Aufruf
    ab, bevor Netzwerk/SMTP beruehrt werden. Traegt den aufgezeichneten Kwarg-Wert
    (oder den Sentinel-String "NOT_PASSED", wenn der Kwarg fehlt)."""

    def __init__(self, official_alerts_enabled):
        self.official_alerts_enabled = official_alerts_enabled
        super().__init__(f"recorded official_alerts_enabled={official_alerts_enabled!r}")


def _fresh_user() -> str:
    return f"test1040-{uuid.uuid4().hex[:8]}"


def _resolvable_location(loc_id: str) -> SavedLocation:
    """Eine echte SavedLocation (in-memory), durchgereicht ueber den
    all_locations_cache-Parameter von send_one_compare_preset, damit der
    Orte-Resolve NICHT vorher abbricht -- ohne Schreib-Seiteneffekt im echten
    data/-Verzeichnis (Muster aus test_issue_764_compare_forecast_hours_consume.py)."""
    return SavedLocation(id=loc_id, name="Innsbruck", lat=47.27, lon=11.39, elevation_m=574)


def _preset(preset_id: str, official_alerts_enabled, loc_id: str) -> dict:
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
    if official_alerts_enabled is not None:
        p["official_alerts_enabled"] = official_alerts_enabled
    return p


def _capture_official_alerts_enabled(preset: dict, location, tmp_path) -> object:
    """Fuehrt send_one_compare_preset mit einer echten Recording-Engine aus und
    gibt den an ComparisonEngine.run durchgereichten official_alerts_enabled-Wert
    zurueck (oder "NOT_PASSED", wenn der Kwarg fehlt).

    Mock-frei: echte Subklasse + Attribut-Rebind, restauriert in finally.
    Bricht via Sentinel-Exception ab, bevor Netz/SMTP beruehrt werden -- Muster
    aus test_issue_764_compare_forecast_hours_consume.py::_capture_forecast_hours.
    """
    import services.comparison_engine as ce_mod
    from app.config import Settings
    from services.scheduler_dispatch_service import send_one_compare_preset as _send_one_compare_preset

    user_id = preset["_user_id"]
    settings = Settings().with_user_profile(user_id)

    original_engine = ce_mod.ComparisonEngine

    class RecordingEngine(original_engine):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            value = kwargs.get("official_alerts_enabled", "NOT_PASSED")
            raise _OfficialAlertsEnabledRecorded(value)

    ce_mod.ComparisonEngine = RecordingEngine
    try:
        with pytest.raises(_OfficialAlertsEnabledRecorded) as exc:
            _send_one_compare_preset(
                {k: v for k, v in preset.items() if k != "_user_id"},
                settings,
                user_id,
                str(tmp_path),
                all_locations_cache=[location],
            )
        return exc.value.official_alerts_enabled
    finally:
        ce_mod.ComparisonEngine = original_engine


class TestIssue1040AlertsToggleAC3Passthrough:
    """AC-3 (Python-Teil): `send_one_compare_preset()` interpretiert
    `preset.get("official_alerts_enabled", True)` und reicht den Wert an
    `ComparisonEngine.run()` durch.

    RED: der Versandpfad reicht den Parameter aktuell GAR NICHT durch (der
    Fetch bei False passiert also heute IMMER) -- die Assertions decken dieses
    falsche Verhalten auf.
    """

    def test_preset_with_official_alerts_disabled_passes_false_to_engine(self, tmp_path):
        """GIVEN: Preset mit official_alerts_enabled=False
        WHEN: send_one_compare_preset() laeuft
        THEN: ComparisonEngine.run() erhaelt official_alerts_enabled=False

        RED: aktuell reicht der Versandpfad den Parameter gar nicht durch ->
        captured=="NOT_PASSED" != False.
        """
        user_id = _fresh_user()
        loc = _resolvable_location("loc-1040-a")
        preset = _preset("cp-1040-off", official_alerts_enabled=False, loc_id="loc-1040-a")
        preset["_user_id"] = user_id

        captured = _capture_official_alerts_enabled(preset, loc, tmp_path)
        assert captured is False, (
            f"RED: ComparisonEngine.run erhielt official_alerts_enabled={captured!r}, "
            "erwartet False -- der Versandpfad reicht preset.get('official_alerts_enabled') "
            "noch nicht durch."
        )

    def test_preset_with_official_alerts_enabled_passes_true_to_engine(self, tmp_path):
        """GIVEN: Preset mit official_alerts_enabled=True
        THEN: ComparisonEngine.run() erhaelt official_alerts_enabled=True (Round-Trip-Beweis).
        """
        user_id = _fresh_user()
        loc = _resolvable_location("loc-1040-b")
        preset = _preset("cp-1040-on", official_alerts_enabled=True, loc_id="loc-1040-b")
        preset["_user_id"] = user_id

        captured = _capture_official_alerts_enabled(preset, loc, tmp_path)
        assert captured is True, (
            f"ComparisonEngine.run erhielt official_alerts_enabled={captured!r}, erwartet True."
        )

    def test_legacy_preset_without_field_interprets_as_true(self, tmp_path):
        """GIVEN: Preset OHNE official_alerts_enabled-Feld (Altdaten)
        THEN: preset.get('official_alerts_enabled', True) liefert True bei
        fehlendem Schluessel, der Versandpfad reicht True durch (kein Crash,
        kein 0/None) -- identisch zum Verhalten vor diesem Slice.
        """
        user_id = _fresh_user()
        loc = _resolvable_location("loc-1040-c")
        preset = _preset("cp-1040-legacy", official_alerts_enabled=None, loc_id="loc-1040-c")
        preset["_user_id"] = user_id

        assert preset.get("official_alerts_enabled", True) is True, (
            "preset.get('official_alerts_enabled', True) muss bei fehlendem "
            "Schluessel True liefern"
        )

        captured = _capture_official_alerts_enabled(preset, loc, tmp_path)
        assert captured is True, (
            f"Legacy-Preset ohne official_alerts_enabled: erwartet Default True, "
            f"durchgereicht wurde {captured!r}."
        )
