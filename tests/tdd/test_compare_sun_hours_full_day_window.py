"""TDD RED — Issue #1268 (AC-8): Die Spalte "Sonne" zaehlt nach dem Fix die
Sonnenstunden des ganzen Tages, nicht nur die eines 9–16-Uhr-Fensters.

Spec: docs/specs/modules/issue_1268_compare_timewindow_removal.md § AC-8
      + Implementation Details Punkt 5 (Tabelle der sichtbaren Mail-Aenderungen)

--- Warum Engine-Ebene und nicht Renderer-Ebene (bewusste Entscheidung) ---
Die Spec verortet AC-8 bei tests/tdd/test_compare_html_email.py. Das ist an
dieser Stelle nicht aussagekraeftig: der Renderer liest `sunny_hours` fertig aus
`LocationResult` und formatiert es nur (compare_html.py CV2_METRICS, key
"sunny_hours", decimals 1). Ein Renderer-Test wuerde also ausschliesslich
beweisen, dass eine selbst gesetzte Fixture-Zahl wieder herauskommt — er wuerde
die eigene Annahme zurueckspiegeln (genau das "Mock-Theater", das CLAUDE.md
verbietet) und waere vor UND nach dem Fix gruen. Er kann den Bug nicht fangen.

Das Verhalten aus AC-8 entsteht eine Schicht tiefer: `ComparisonEngine.run()`
filtert die Rohdaten mit `start_hour <= dp.ts.hour <= end_hour`
(comparison_engine.py:90-94) und uebergibt NUR die gefilterten Punkte an
`WeatherMetricsService.calculate_sunny_hours()`. Das Bewertungsfenster
entscheidet also ueber den Sonnen-Wert. Genau dort setzt dieser Test an — mit
echten Datenpunkten durch die echte Metrik-Berechnung.

Zusammen mit test_compare_dispatch_fixed_window.py (AC-4: der Dispatch uebergibt
(0, 23)) ist die Kette zum Nutzer geschlossen: Dispatch → Fenster → sunny_hours
→ Mail-Spalte.

KEINE Mocks (CLAUDE.md):
  Kein unittest.mock / patch() / MagicMock. `fetch_forecast_for_location` ist
  eine echte Modul-Funktion und die einzige Netz-Grenze der Engine; sie wird per
  plain Attribut-Rebind (in finally restauriert) durch eine echte Funktion
  ersetzt, die ein aufgezeichnetes Stundenprofil zurueckgibt. Alles danach —
  Filter, calculate_sunny_hours, DNI-Band — laeuft als echter Produktionscode.

RED-Erwartung (vor Fix):
  Der Test uebergibt (0, 23) direkt an die Engine und ist damit fuer die
  Engine-Signatur schon jetzt gruen (die Signatur aendert sich laut Spec nicht).
  Rot ist der Nachweis-Test unten, der das Fenster aus dem DISPATCH bezieht.
  Siehe die Docstrings der einzelnen Tests.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.loader import SavedLocation
from app.models import ForecastDataPoint
from app.profile import ActivityProfile

TARGET_DATE = date(2026, 7, 16)

# DNI-Band (Default 60/180 W/m², Issue #347): >= 180 zaehlt als volle Sonnenstunde.
DNI_SONNIG = 800.0
DNI_DUNKEL = 0.0

# Aufgezeichnetes Stundenprofil: Sonne AUSSCHLIESSLICH ausserhalb 9–16 Uhr
# (frueher Morgen 6,7,8 Uhr + Abend 17,18,19 Uhr = 6 Sonnenstunden).
# Innerhalb 9–16 Uhr ist es bedeckt (DNI 0) — dadurch trennt der Test die
# beiden Fenster maximal scharf: (9,16) -> 0.0 h, (0,23) -> 6.0 h.
SONNIGE_STUNDEN = {6, 7, 8, 17, 18, 19}


def _hourly_profile() -> list[ForecastDataPoint]:
    """24 echte ForecastDataPoints fuer den Zieltag."""
    points = []
    for hour in range(24):
        sonnig = hour in SONNIGE_STUNDEN
        points.append(
            ForecastDataPoint(
                ts=datetime(TARGET_DATE.year, TARGET_DATE.month, TARGET_DATE.day, hour),
                t2m_c=12.0 + hour * 0.5,
                wind10m_kmh=10.0,
                gust_kmh=20.0,
                cloud_total_pct=10 if sonnig else 95,
                dni_wm2=DNI_SONNIG if sonnig else DNI_DUNKEL,
            )
        )
    return points


def _location() -> SavedLocation:
    return SavedLocation(id="loc-1268-sun", name="Innsbruck", lat=47.27, lon=11.39, elevation_m=574)


def _run_engine_with_window(time_window: tuple[int, int]) -> float:
    """Laesst die ECHTE ComparisonEngine mit dem aufgezeichneten Stundenprofil
    laufen und gibt die berechneten sunny_hours zurueck.

    Mock-frei: echte Funktion an der einzigen Netz-Grenze, Rebind in finally
    zurueckgesetzt.
    """
    import services.comparison_engine as ce_mod

    loc = _location()
    original_fetch = ce_mod.fetch_forecast_for_location

    def recorded_fetch(location, hours=48, settings=None):  # echte Funktion, kein Mock
        return {
            "location": location,
            "error": None,
            "forecast_hours": hours,
            "snow_source": None,
            "raw_data": _hourly_profile(),
        }

    ce_mod.fetch_forecast_for_location = recorded_fetch
    try:
        result = ce_mod.ComparisonEngine.run(
            locations=[loc],
            time_window=time_window,
            target_date=TARGET_DATE,
            forecast_hours=48,
            profile=ActivityProfile.SUMMER_TREKKING,
            official_alerts_enabled=False,
        )
    finally:
        ce_mod.fetch_forecast_for_location = original_fetch

    assert result.locations, "Engine lieferte kein LocationResult"
    lr = result.locations[0]
    assert lr.error is None, f"Engine-Fehler: {lr.error}"
    return lr.sunny_hours


class TestSunHoursDependsOnWindow:
    """Beweist, dass das Bewertungsfenster den Sonnen-Wert bestimmt."""

    def test_altes_fenster_verliert_morgen_und_abendsonne(self):
        """GIVEN: ein Ort mit Sonne nur um 6–8 und 17–19 Uhr
        WHEN: die Engine mit dem ALTEN Fenster (9, 16) rechnet
        THEN: sunny_hours = 0.0 — die Randsonne faellt komplett unter den Tisch.

        Ausgangslage-Beleg fuer AC-8 (gruen vor und nach dem Fix): dokumentiert
        das Verhalten, das #1268 ablegt, und beweist zugleich, dass die Fixture
        die beiden Fenster ueberhaupt unterscheidbar macht. Ohne diesen Anker
        koennte der Test unten auch bei einer kaputten Fixture gruen werden.
        """
        sunny = _run_engine_with_window((9, 16))

        assert sunny == 0.0, (
            f"Fenster (9, 16) ergab {sunny} Sonnenstunden, erwartet 0.0 — "
            "die Fixture hat innerhalb 9–16 Uhr bewusst DNI 0."
        )

    def test_ganztags_fenster_zaehlt_morgen_und_abendsonne_mit(self):
        """GIVEN: derselbe Ort mit Sonne um 6–8 und 17–19 Uhr
        WHEN: die Engine mit dem NEUEN Ganztags-Fenster (0, 23) rechnet
        THEN: sunny_hours = 6.0 — alle sechs Randstunden zaehlen mit.

        AC-8, Kern-Nachweis auf der Schicht, die den Wert erzeugt.
        """
        sunny = _run_engine_with_window((0, 23))

        assert sunny == 6.0, (
            f"Ganztags-Fenster (0, 23) ergab {sunny} Sonnenstunden, erwartet 6.0 "
            f"(Stunden {sorted(SONNIGE_STUNDEN)} mit DNI {DNI_SONNIG} W/m²)."
        )


class TestSunHoursThroughDispatch:
    """AC-8 end-to-end ueber den Pfad, den der Nutzer tatsaechlich bekommt."""

    def test_dispatch_liefert_ganztags_sonnenstunden_in_die_mail_spalte(self, tmp_path):
        """GIVEN: ein Bestands-Preset mit gespeichertem Zeitfenster 9–16 Uhr und
                  ein Ort, dessen Sonne ausschliesslich um 6–8 und 17–19 Uhr scheint
        WHEN: der Dispatch das Vergleichs-Ergebnis erzeugt
        THEN: der Sonnen-Wert der Mail-Spalte betraegt 6.0 h (ganzer Tag),
              nicht 0.0 h (altes Preset-Fenster).

        AC-8 am Nutzer-Ergebnis: schliesst die Kette Preset → Dispatch →
        Fenster → sunny_hours. Dieser Test ist der ROTE — er bezieht das
        Fenster NICHT als Testparameter, sondern aus dem echten Dispatch-Code.

        RED vor Fix: der Dispatch reicht das Preset-Fenster (9, 16) durch →
        sunny_hours = 0.0 statt 6.0.

        Der Test greift das ComparisonResult am Renderer-Uebergang ab: er
        laesst den echten Dispatch bis unmittelbar hinter die Engine laufen und
        bricht vor Netz/SMTP ab (Sentinel), traegt aber das echte, von der
        echten Engine berechnete Ergebnis heraus.
        """
        import services.comparison_engine as ce_mod
        from services.scheduler_dispatch_service import send_one_compare_preset
        from app.config import Settings

        user_id = "test1268-sun"
        loc = _location()
        preset = {
            "id": "cp-1268-sun",
            "name": "Sonnen-Vergleich",
            "location_ids": [loc.id],
            "schedule": "daily",
            "profil": "SUMMER_TREKKING",
            "hour_from": 9,
            "hour_to": 16,
            "forecast_hours": 24,
            "empfaenger": ["gregor-test@henemm.com"],
            "created_at": "2026-01-01T00:00:00Z",
        }
        settings = Settings().with_user_profile(user_id)

        original_fetch = ce_mod.fetch_forecast_for_location
        original_engine = ce_mod.ComparisonEngine

        def recorded_fetch(location, hours=48, settings=None):  # echte Funktion
            return {
                "location": location,
                "error": None,
                "forecast_hours": hours,
                "snow_source": None,
                "raw_data": _hourly_profile(),
            }

        class _ResultCaptured(Exception):
            def __init__(self, result):
                self.result = result
                super().__init__("captured ComparisonResult")

        class CapturingEngine(original_engine):  # echte Subklasse, kein Mock
            @staticmethod
            def run(*args, **kwargs):
                # ECHTE Engine-Berechnung, danach Abbruch vor Renderer/SMTP.
                raise _ResultCaptured(original_engine.run(*args, **kwargs))

        ce_mod.fetch_forecast_for_location = recorded_fetch
        ce_mod.ComparisonEngine = CapturingEngine
        try:
            with pytest.raises(_ResultCaptured) as exc:
                send_one_compare_preset(
                    preset,
                    settings,
                    user_id,
                    str(tmp_path),
                    target_date=TARGET_DATE,
                    all_locations_cache=[loc],
                )
            result = exc.value.result
        finally:
            ce_mod.fetch_forecast_for_location = original_fetch
            ce_mod.ComparisonEngine = original_engine

        sunny = result.locations[0].sunny_hours
        assert sunny == 6.0, (
            f"RED: der Dispatch lieferte {sunny} Sonnenstunden, erwartet 6.0. "
            "Er reicht offenbar noch das gespeicherte Preset-Fenster (9, 16) durch, "
            "statt den ganzen Tag (0, 23) zu bewerten — die Mail-Spalte 'Sonne' "
            "verliert damit Morgen- und Abendsonne (Spec #1268 AC-8)."
        )
