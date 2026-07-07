"""TDD RED — Issue #1036: MeteoForetsSource (Waldbrand-Gefahrenstufe).

SPEC: docs/specs/modules/issue_1036_meteo_forets_source.md
AC-1 bis AC-3

Diese Tests schlagen ABSICHTLICH fehl, weil `services.official_alerts.meteo_forets`
noch nicht existiert -> ModuleNotFoundError (Subklasse von ImportError) beim
jeweils ersten Import innerhalb der Testfunktion.

KEINE Mocks (CLAUDE.md-Projektkonvention "KEINE MOCKED TESTS!"):
- AC-1 ruft die echte Météo-France-API auf (GZ_METEOFRANCE_APIKEY aus .env,
  Endpunkt real verifiziert waehrend der Analyse-Phase, siehe Spec).
- AC-2 testet die reine Funktion `_is_season(month)` direkt mit echten
  Integer-Werten (kein Mock der Systemuhr noetig) plus einen realen
  `covers()`-Aufruf zur Laufzeit (heutiges Testdatum liegt in der Saison).
- AC-3 entfernt die ENV-Variable temporaer und prueft echtes fail-soft-Verhalten.
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

import pytest
from dotenv import load_dotenv

from app.profile import ActivityProfile
from app.user import SavedLocation
from services.comparison_engine import ComparisonEngine
from services.official_alerts.department_mapper import DEPARTMENT_CENTROIDS

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

# Leitszenario Epic #1033: Côte d'Azur + Korsika. Alle Zentroide liegen
# ausserhalb der GeoSphere-Bounding-Box (lat 45-50 / lon 8-18) -> ComparisonEngine
# waehlt den openmeteo-Zweig, der ueber die autouse-Fixture in tests/conftest.py
# auf den Offline-FixtureProvider umgeleitet wird (kein echter Wetter-Netzwerkruf) --
# waehrend die Meteo-France-API real bleibt.
_SCENARIO_DEPARTMENTS = ["83", "06", "13", "2A", "2B"]  # Var, Alpes-Maritimes, Bouches-du-Rhone, Corse-du-Sud, Haute-Corse


def _require_meteofrance_key() -> None:
    if not os.environ.get("GZ_METEOFRANCE_APIKEY"):
        pytest.skip("GZ_METEOFRANCE_APIKEY nicht konfiguriert (.env)")


class TestIssue1036MeteoForetsSource:
    """TDD-Reihenfolge laut Spec: AC-1 -> AC-2 -> AC-3."""

    def test_ac1_live_waldbrandgefahr_struktureller_vertrag_und_badge(self):
        """AC-1: echter API-Call fuer die Leitszenario-Departements. Heutiges
        Testdatum liegt in der Saison (Juni-September). Da sich das
        tatsaechlich gemeldete Level taeglich aendert, wird NICHT hart auf
        Stufe 4 geprueft, sondern der strukturelle Vertrag fuer JEDES
        gemeldete Level bewiesen -- und zusaetzlich, FALLS ein Departement
        tatsaechlich Stufe 4 meldet, der rote Badge im gerenderten
        HTML-Output (compare_html.py, Farbe G_DANGER)."""
        _require_meteofrance_key()
        from services.official_alerts.meteo_forets import MeteoForetsSource
        from output.renderers.email.compare_html import render_compare_html
        from output.renderers.email.design_tokens import G_DANGER

        source = MeteoForetsSource()
        level4_location = None
        for dep in _SCENARIO_DEPARTMENTS:
            lat, lon = DEPARTMENT_CENTROIDS[dep]
            assert source.covers(lat, lon) is True, (
                f"Departement {dep} liegt im Leitszenario und die Saison "
                f"laeuft (heutiges Testdatum in Juni-September) -- covers() "
                f"muss True liefern"
            )
            alerts = source.fetch(lat, lon)
            assert isinstance(alerts, list)
            for alert in alerts:
                assert alert.source == "meteo_forets"
                assert alert.hazard == "wildfire_risk"
                assert alert.level in (1, 2, 3, 4)
                assert alert.label == f"Waldbrand-Gefahr — Stufe {alert.level}"
                if alert.level == 4 and level4_location is None:
                    level4_location = (dep, lat, lon)

        if level4_location is None:
            pytest.skip(
                "Zum Testzeitpunkt kein Leitszenario-Departement mit Stufe 4 "
                "-- struktureller Vertrag oben bereits bewiesen, kein hartes "
                "'muss Stufe 4 sein' moeglich."
            )

        dep, lat, lon = level4_location
        locations = [
            SavedLocation(id="forets-hot", name=f"Dept-{dep}", lat=lat, lon=lon, elevation_m=10),
        ]
        target = date.today() + timedelta(days=1)
        result = ComparisonEngine.run(
            locations,
            time_window=(9, 16),
            target_date=target,
            profile=ActivityProfile.ALLGEMEIN,
        )
        html = render_compare_html(result)
        assert "Waldbrand-Gefahr — Stufe 4" in html
        assert G_DANGER in html

    def test_ac2_saison_gate_pure_function_und_live_covers(self):
        """AC-2: `_is_season(month)` wird mit ECHTEN Integer-Werten fuer alle
        12 Monate geprueft -- kein Mock der Systemuhr noetig, da eine reine
        Funktion mit explizitem Parameter getestet wird (Januar muss False
        liefern, obwohl das heutige Testdatum in der Saison liegt). Zusaetzlich
        ein realer `covers()`-Aufruf zur Laufzeit (heutiges Testdatum liegt in
        der Saison)."""
        from services.official_alerts.meteo_forets import MeteoForetsSource, _is_season

        for month in range(1, 13):
            expected = month in {6, 7, 8, 9}
            assert _is_season(month) is expected, (
                f"_is_season({month}) muss {expected} liefern"
            )

        source = MeteoForetsSource()
        var_lat, var_lon = DEPARTMENT_CENTROIDS["83"]
        assert source.covers(var_lat, var_lon) is True, (
            "Heutiges Testdatum liegt in Juni-September -- covers() muss fuer "
            "einen franzoesischen Ort True liefern (reale Systemzeit)"
        )

    def test_ac3_fail_soft_ohne_apikey(self):
        """AC-3: fehlende/leere GZ_METEOFRANCE_APIKEY -> fetch() liefert [],
        kein Crash; ein voller ComparisonEngine-Lauf bleibt fehlerfrei."""
        from services.official_alerts.meteo_forets import MeteoForetsSource

        backup = os.environ.pop("GZ_METEOFRANCE_APIKEY", None)
        try:
            source = MeteoForetsSource()
            var_lat, var_lon = DEPARTMENT_CENTROIDS["83"]
            assert source.covers(var_lat, var_lon) is True
            alerts = source.fetch(var_lat, var_lon)
            assert alerts == [], "fetch() muss bei fehlender ENV [] liefern, kein Crash"

            locations = [
                SavedLocation(id="forets-var", name="Var", lat=var_lat, lon=var_lon, elevation_m=10),
            ]
            target = date.today() + timedelta(days=1)
            result = ComparisonEngine.run(
                locations,
                time_window=(9, 16),
                target_date=target,
                profile=ActivityProfile.ALLGEMEIN,
            )
            assert len(result.locations) == len(locations), (
                "Compare-Mail-Generierung muss trotz fehlender Meteo-France-ENV "
                "vollstaendig durchlaufen"
            )
            for loc_result in result.locations:
                assert loc_result.error is None
                assert loc_result.official_alerts == []
        finally:
            if backup is not None:
                os.environ["GZ_METEOFRANCE_APIKEY"] = backup
