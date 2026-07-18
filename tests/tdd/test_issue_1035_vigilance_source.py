"""TDD RED — Issue #1035: VigilanceSource (Météo-France amtliche Warnungen).

SPEC: docs/specs/modules/issue_1035_vigilance_source.md
AC-1 bis AC-5

Diese Tests schlagen ABSICHTLICH fehl, weil `services.official_alerts.vigilance`
und `services.official_alerts.department_mapper` noch nicht existieren ->
ModuleNotFoundError (Subklasse von ImportError) beim jeweils ersten Import
innerhalb der Testfunktion.

KEINE Mocks (CLAUDE.md-Projektkonvention "KEINE MOCKED TESTS!"):
- AC-1/AC-4 rufen die echte Météo-France-API auf (GZ_METEOFRANCE_APIKEY aus .env,
  Endpunkt real verifiziert waehrend der Analyse-Phase, siehe Spec).
- AC-2 entfernt die ENV-Variable temporaer und prueft echtes fail-soft-Verhalten.
- AC-3 nutzt ein echtes Delegations-Objekt mit Call-Counter (kein Mock/patch),
  registriert ueber den echten `register_official_alert_source()`-Codepfad.
- AC-5 registriert eine echte Test-Fake-Quelle (Muster aus #1034).
"""
from __future__ import annotations

import inspect
import os
from datetime import date, timedelta
from pathlib import Path

import pytest
from dotenv import load_dotenv

from app.profile import ActivityProfile
from app.user import SavedLocation
from services.comparison_engine import ComparisonEngine

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

# Reale Koordinaten aus dem Leitszenario (Epic #1033), alle ausserhalb der
# GeoSphere-Bounding-Box (lat 45-50 / lon 8-18) -> ComparisonEngine waehlt den
# openmeteo-Zweig, der ueber die autouse-Fixture in tests/conftest.py auf den
# Offline-FixtureProvider umgeleitet wird (kein echter Wetter-Netzwerkruf).
NICE = (43.7102, 7.2620)          # Alpes-Maritimes (06)
CANNES = (43.5528, 7.0174)        # Alpes-Maritimes (06)
MARSEILLE = (43.2965, 5.3698)     # Bouches-du-Rhone (13)
AJACCIO = (41.9192, 8.7386)       # Corse-du-Sud (2A)
BASTIA = (42.6979, 9.4508)        # Haute-Corse (2B)
INNSBRUCK = (47.2692, 11.4041)    # Oesterreich, ausserhalb Frankreichs


def _riviera_locations() -> list[SavedLocation]:
    return [
        SavedLocation(id="vig-nice", name="Nizza", lat=NICE[0], lon=NICE[1], elevation_m=10),
        SavedLocation(id="vig-cannes", name="Cannes", lat=CANNES[0], lon=CANNES[1], elevation_m=12),
        SavedLocation(id="vig-marseille", name="Marseille", lat=MARSEILLE[0], lon=MARSEILLE[1], elevation_m=8),
    ]


def _require_meteofrance_key() -> None:
    if not os.environ.get("GZ_METEOFRANCE_APIKEY"):
        pytest.skip("GZ_METEOFRANCE_APIKEY nicht konfiguriert (.env)")


class _SingleLocationOfficialAlertSource:
    """Echte Quelle (kein Mock), zustaendig fuer genau einen Ort (Toleranz
    0.05 Grad), liefert dort genau einen vorgegebenen OfficialAlert."""

    def __init__(self, lat: float, lon: float, alert) -> None:
        self._lat = lat
        self._lon = lon
        self._alert = alert

    @property
    def name(self) -> str:
        return "test-vigilance-single-location"

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat: float, lon: float):
        return [self._alert]


class _CountingSourceDelegate:
    """Echtes Delegations-Objekt (kein Mock) das `fetch()`-Aufrufe zaehlt und
    an eine echte VigilanceSource-Instanz weiterreicht. Beweist AC-3: bei
    covers()==False darf fetch() nie aufgerufen werden."""

    def __init__(self, inner) -> None:
        self._inner = inner
        self.fetch_calls = 0

    @property
    def name(self) -> str:
        return self._inner.name

    def covers(self, lat: float, lon: float) -> bool:
        return self._inner.covers(lat, lon)

    def fetch(self, lat: float, lon: float):
        self.fetch_calls += 1
        return self._inner.fetch(lat, lon)


class TestIssue1035VigilanceSource:
    """TDD-Reihenfolge laut Spec: AC-1 -> AC-2 -> AC-3 -> AC-4 -> AC-5."""

    # Dialt real (Meteo-France Vigilance-API) -- #1211 Scheibe 2b Batch 3, nur via Marker ausfuehren.
    @pytest.mark.live
    def test_ac1_live_warnung_struktureller_vertrag(self):
        """AC-1: echter API-Call gegen die Météo-France-API. Der Live-Zustand
        aendert sich taeglich, daher wird NICHT hart auf "orange"/"Gewitter"
        geprueft, sondern der strukturelle Vertrag fuer JEDEN tatsaechlich
        zum Testzeitpunkt gemeldeten Alert (ueber alle Departements, da EIN
        gecachter National-Call alle Departement-Lookups bedient -- keine
        zusaetzlichen HTTP-Calls durch die Iteration)."""
        _require_meteofrance_key()
        from services.official_alerts.department_mapper import DEPARTMENT_CENTROIDS
        from services.official_alerts.vigilance import VigilanceSource

        source = VigilanceSource()
        found_any = False
        for lat, lon in DEPARTMENT_CENTROIDS.values():
            alerts = source.fetch(lat, lon)
            for alert in alerts:
                found_any = True
                assert alert.source == "meteofrance_vigilance"
                assert alert.hazard in {"wind_gust", "thunderstorm", "extreme_heat"}
                assert alert.level in (2, 3, 4)
                assert alert.label and isinstance(alert.label, str)
                assert alert.valid_from is not None
                assert alert.valid_to is not None

        assert found_any, (
            "Erwartet mindestens eine Vigilance-Warnung >=Stufe 2 irgendwo in "
            "Frankreich zum Testzeitpunkt (Live-Stichprobe 2026-07-06 zeigte "
            "mehrere Departements auf Stufe 2/3 fuer Gewitter/Hitze) -- 0 "
            "Treffer ueber ALLE Departements waere ein Hinweis auf einen "
            "Parser-Fehler, nicht auf eine ruhige Wetterlage."
        )

    # Dialt real (Meteo-France Vigilance-API) -- #1211 Scheibe 2b Batch 3, nur via Marker ausfuehren.
    @pytest.mark.live
    def test_ac1_live_compare_render_ende_zu_ende(self):
        """AC-1 (F002-Lücke): verkettet ECHTE Live-Vigilance-Daten bis zum
        gerenderten Text-Output — nicht nur den isolierten fetch()-Vertrag.
        Sucht über die Zentroid-Tabelle einen Ort mit echtem Alert (Level >=2)
        und einen Kontrast-Ort ohne Alert, laesst beide durch den echten
        ComparisonEngine.run() laufen und prueft, dass render_comparison_text()
        die Warnzeile GENAU beim betroffenen Ort zeigt (Live-Toleranz: das
        tatsaechlich gelieferte label, kein hartes 'muss Gewitter/orange sein').
        Bei zufaellig ruhiger Wetterlage (kein Département mit Level >=2) ->
        pytest.skip statt hartem Fehler."""
        _require_meteofrance_key()
        from services.official_alerts import get_official_alerts_for_location
        from services.official_alerts.department_mapper import DEPARTMENT_CENTROIDS
        from services.official_alerts.vigilance import VigilanceSource
        from output.renderers.comparison import render_comparison_text

        def _fixture_routed(lat: float, lon: float) -> bool:
            # Ausserhalb der GeoSphere-Box (lat 45-50 / lon 8-18) -> openmeteo ->
            # Offline-FixtureProvider (conftest autouse). So bleibt der Wetter-
            # Abruf offline, waehrend die Vigilance-API echt bleibt.
            return not (45.0 <= lat <= 50.0 and 8.0 <= lon <= 18.0)

        source = VigilanceSource()
        affected = None  # (code, lat, lon)
        clean = None     # (code, lat, lon)
        for code, (lat, lon) in DEPARTMENT_CENTROIDS.items():
            if not _fixture_routed(lat, lon):
                continue
            alerts = source.fetch(lat, lon)
            if alerts and affected is None:
                affected = (code, lat, lon)
            elif not alerts and clean is None:
                if not get_official_alerts_for_location(lat, lon):
                    clean = (code, lat, lon)
            if affected and clean:
                break

        if affected is None:
            pytest.skip(
                "Zum Testzeitpunkt kein Département mit Vigilance-Warnung "
                ">=Stufe 2 (bei fixture-routbaren Koordinaten) — ruhige "
                "Wetterlage, kein harter Fehler."
            )
        if clean is None:
            pytest.skip(
                "Zum Testzeitpunkt kein fixture-routbares Département OHNE "
                "amtlichen Alert in der VOLLEN Registry (Vigilance + "
                "Waldbrand) — flächendeckende Warnlage, kein Kontrast-Ort "
                "verfügbar, kein harter Fehler."
            )

        a_code, a_lat, a_lon = affected
        c_code, c_lat, c_lon = clean

        locations = [
            SavedLocation(id="vig-affected", name=f"Dept-{a_code}", lat=a_lat, lon=a_lon, elevation_m=10),
            SavedLocation(id="vig-clean", name=f"Dept-{c_code}", lat=c_lat, lon=c_lon, elevation_m=10),
        ]
        target = date.today() + timedelta(days=1)
        result = ComparisonEngine.run(
            locations,
            time_window=(9, 16),
            target_date=target,
            profile=ActivityProfile.ALLGEMEIN,
        )
        text = render_comparison_text(result)

        # Erwartung strikt aus den echten Registry-Daten ableiten (gecachter
        # National-Call -> keine zusaetzlichen HTTP-Calls durch diese Aufrufe).
        affected_alerts = get_official_alerts_for_location(a_lat, a_lon)
        clean_alerts = get_official_alerts_for_location(c_lat, c_lon)
        assert affected_alerts, "betroffener Ort muss laut Registry Alerts haben"
        assert clean_alerts == [], "Kontrast-Ort darf keine Alerts haben"

        warn_lines = [ln for ln in text.splitlines() if "Amtliche Warnung" in ln]
        assert len(warn_lines) == len(affected_alerts), (
            f"Genau die Alerts des betroffenen Orts duerfen als Warnzeile "
            f"erscheinen — warn_lines={len(warn_lines)}, "
            f"affected_alerts={len(affected_alerts)} (Kontrast-Ort ohne Alert "
            f"darf keine Warnzeile erzeugen)."
        )
        for alert in affected_alerts:
            assert alert.label in text, (
                f"Warnzeile mit tatsaechlich geliefertem label {alert.label!r} "
                f"fehlt im gerenderten Compare-Text."
            )

    def test_ac2_fail_soft_ohne_apikey(self):
        """AC-2: fehlende/leere GZ_METEOFRANCE_APIKEY -> fetch() liefert [],
        kein Crash; ein voller ComparisonEngine-Lauf bleibt fehlerfrei."""
        from services.official_alerts.vigilance import VigilanceSource

        backup = os.environ.pop("GZ_METEOFRANCE_APIKEY", None)
        try:
            source = VigilanceSource()
            assert source.covers(*NICE) is True
            alerts = source.fetch(*NICE)
            assert alerts == [], "fetch() muss bei fehlender ENV [] liefern, kein Crash"

            locations = _riviera_locations()
            target = date.today() + timedelta(days=1)
            result = ComparisonEngine.run(
                locations,
                time_window=(9, 16),
                target_date=target,
                profile=ActivityProfile.ALLGEMEIN,
            )
            assert len(result.locations) == len(locations), (
                "Compare-Mail-Generierung muss trotz fehlender Vigilance-ENV "
                "vollstaendig durchlaufen"
            )
            for loc_result in result.locations:
                assert loc_result.error is None
                assert loc_result.official_alerts == []
        finally:
            if backup is not None:
                os.environ["GZ_METEOFRANCE_APIKEY"] = backup

    def test_ac3_ausserhalb_frankreich_kein_fetch_aufruf(self):
        """AC-3: Ort in Oesterreich -> covers()==False -> fetch() wird von
        get_official_alerts_for_location() gar nicht erst aufgerufen."""
        import services.official_alerts.base as oa_base
        from services.official_alerts import (
            get_official_alerts_for_location,
            register_official_alert_source,
        )
        from services.official_alerts.vigilance import VigilanceSource

        spy = _CountingSourceDelegate(VigilanceSource())
        backup = list(oa_base._REGISTERED_SOURCES)
        oa_base._REGISTERED_SOURCES.clear()
        try:
            register_official_alert_source(spy)

            alerts = get_official_alerts_for_location(*INNSBRUCK)

            assert spy.fetch_calls == 0, (
                f"fetch() darf fuer einen Ort ausserhalb Frankreichs nicht "
                f"aufgerufen werden, war {spy.fetch_calls}x"
            )
            assert alerts == []
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)

    # Dialt real (Meteo-France Vigilance-API) -- #1211 Scheibe 2b Batch 3, nur via Marker ausfuehren.
    @pytest.mark.live
    def test_ac4_korsika_identischer_codepfad_wie_festland(self):
        """AC-4: Ajaccio (2A) und Bastia (2B) laufen durch denselben Mapper
        und dieselbe Quelle wie ein Festland-Ort -- kein Sonderfall-Code."""
        _require_meteofrance_key()
        from services.official_alerts.department_mapper import lookup_department
        import services.official_alerts.vigilance as vigilance_module
        from services.official_alerts.vigilance import VigilanceSource

        assert lookup_department(*AJACCIO) == "2A"
        assert lookup_department(*BASTIA) == "2B"

        source = VigilanceSource()
        for lat, lon in (AJACCIO, BASTIA, NICE):
            assert source.covers(lat, lon) is True
            alerts = source.fetch(lat, lon)
            assert isinstance(alerts, list)
            for alert in alerts:
                assert alert.hazard in {"wind_gust", "thunderstorm", "extreme_heat"}
                assert alert.level in (2, 3, 4)

        src = inspect.getsource(vigilance_module)
        assert '"2A"' not in src and "'2A'" not in src, (
            "vigilance.py darf keinen Korsika-Sonderfall-Code enthalten "
            "(2A/2B muessen generisch ueber department_mapper laufen)"
        )
        assert '"2B"' not in src and "'2B'" not in src

    def test_ac5_text_renderer_zeigt_warnzeile_fuer_betroffenen_ort(self):
        """AC-5: render_comparison_text() zeigt fuer einen Ort mit
        official_alerts eine zusaetzliche Warnzeile; andere Orte bleiben
        bis auf diese eine Zeile identisch zur Baseline."""
        import services.official_alerts.base as oa_base
        from output.renderers.comparison import render_comparison_text
        from services.official_alerts import (
            OfficialAlert,
            register_official_alert_source,
        )

        locations = _riviera_locations()
        nice = locations[0]
        target = date.today() + timedelta(days=1)

        backup = list(oa_base._REGISTERED_SOURCES)
        oa_base._REGISTERED_SOURCES.clear()
        try:
            baseline_result = ComparisonEngine.run(
                locations,
                time_window=(9, 16),
                target_date=target,
                profile=ActivityProfile.ALLGEMEIN,
            )
            baseline_text = render_comparison_text(baseline_result)

            alert = OfficialAlert(
                source="test-vigilance",
                hazard="thunderstorm",
                level=3,
                label="Gewitterwarnung Stufe Orange",
            )
            register_official_alert_source(
                _SingleLocationOfficialAlertSource(nice.lat, nice.lon, alert)
            )

            result = ComparisonEngine.run(
                locations,
                time_window=(9, 16),
                target_date=target,
                profile=ActivityProfile.ALLGEMEIN,
            )
            text = render_comparison_text(result)

            assert text.count(alert.label) == 1, (
                f"Warnzeile mit Label '{alert.label}' muss genau einmal im "
                f"Text erscheinen (nur bei Nizza, nicht bei Cannes/Marseille)"
            )

            baseline_lines = baseline_text.splitlines()
            new_lines = text.splitlines()
            assert len(new_lines) == len(baseline_lines) + 1, (
                f"Erwartet genau eine zusaetzliche Zeile fuer die Warnung, "
                f"baseline={len(baseline_lines)} neu={len(new_lines)}"
            )
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)
