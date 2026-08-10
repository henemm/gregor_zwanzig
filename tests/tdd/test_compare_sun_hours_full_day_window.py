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

# Aufgezeichnetes Stundenprofil: Sonne frueher Morgen 6,7,8 Uhr + Abend
# 17,18,19 Uhr = 6 Sonnenstunden, dazwischen bedeckt (DNI 0).
#
# ACHTUNG Zeitbasis (Issue #1378): `ts` ist naive UTC (Hausnorm #1345), die
# Fenster-Auswertung laeuft seit #1378 in ORTSZEIT. Der Fixture-Ort ist
# Innsbruck (Europe/Vienna, im Juli UTC+2) — die Sonnenstunden liegen also in
# ORTSZEIT bei 8,9,10 und 19,20,21 Uhr. Deshalb trennt das Profil die Fenster
# weiterhin scharf, aber mit anderen Zahlen als vor #1378:
#   Fenster (9,16) Ortszeit = UTC 7..14 -> sonnig UTC 7,8            -> 2.0 h
#   Fenster (4,19) Ortszeit = UTC 2..17 -> sonnig UTC 6,7,8,17       -> 4.0 h
#   Fenster (0,23) Ortszeit = UTC 0..21 -> sonnig UTC 6,7,8,17,18,19 -> 6.0 h
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
        """GIVEN: ein Ort mit Sonne um 6–8 und 17–19 Uhr UTC
        WHEN: die Engine mit dem ALTEN Fenster (9, 16) rechnet
        THEN: sunny_hours = 2.0 — vier der sechs Sonnenstunden fallen unter
              den Tisch.

        Ausgangslage-Beleg fuer AC-8 (gruen vor und nach dem #1268-Fix):
        dokumentiert das Verhalten, das #1268 ablegt, und beweist zugleich, dass
        die Fixture die beiden Fenster ueberhaupt unterscheidbar macht (2.0 vs.
        6.0). Ohne diesen Anker koennte der Test unten auch bei einer kaputten
        Fixture gruen werden.

        Erwartungswert hergeleitet (Issue #1378 — Fenster gilt in ORTSZEIT):
          Fenster 9–16 Ortszeit, Innsbruck = Europe/Vienna, Juli = UTC+2
            -> ausgewertet werden die Serverstunden 7..14
          sonnige Serverstunden {6,7,8,17,18,19} ∩ [7..14] = {7, 8}
            -> 2 Sonnenstunden (in Ortszeit: 9 und 10 Uhr)
          neu DRIN gegenueber der Serverzeit-Auswertung: UTC 7, 8
          neu DRAUSSEN: keine (vor #1378 lag keine Sonnenstunde im Fenster)
        """
        sunny = _run_engine_with_window((9, 16))

        assert sunny == 2.0, (
            f"Fenster (9, 16) ergab {sunny} Sonnenstunden, erwartet 2.0 — "
            "in Ortszeit 9–16 Uhr (= UTC 7–14) liegen genau die Sonnenstunden "
            "UTC 7 und 8, die restlichen vier liegen ausserhalb."
        )

    def test_ganztags_fenster_zaehlt_morgen_und_abendsonne_mit(self):
        """GIVEN: derselbe Ort mit Sonne um 6–8 und 17–19 Uhr
        WHEN: die Engine mit dem NEUEN Ganztags-Fenster (0, 23) rechnet
        THEN: sunny_hours = 6.0 — alle sechs Randstunden zaehlen mit.

        AC-8, Kern-Nachweis auf der Schicht, die den Wert erzeugt.

        Wert unveraendert nach Issue #1378: Fenster 0–23 Ortszeit umfasst am
        Ortstag die Serverstunden 0..21 (Innsbruck, UTC+2 -> Ortszeit 2..23);
        die dabei herausfallenden Serverstunden 22/23 sind in der Fixture
        ohnehin bedeckt, alle sechs Sonnenstunden liegen in 0..21.
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
        THEN: der Sonnen-Wert der Mail-Spalte betraegt 4.0 h (konfiguriertes
              Tagesfenster), nicht 2.0 h (altes Preset-Fenster 9–16).

        AC-8 am Nutzer-Ergebnis: schliesst die Kette Preset → Dispatch →
        Fenster → sunny_hours. Dieser Test ist der ROTE — er bezieht das
        Fenster NICHT als Testparameter, sondern aus dem echten Dispatch-Code.

        RED vor Fix: der Dispatch reicht das Preset-Fenster (9, 16) durch →
        sunny_hours 2.0 statt 4.0 (vor #1378: 0.0 statt 6.0).

        Erwartungswert hergeleitet (zwei Schritte, keine Ablesung):
          1. Fenster-Quelle: das Preset traegt KEIN
             `day_window_start_hour`/`day_window_end_hour`, also liefert
             `resolve_compare_time_window()` -> `resolve_configured_window(
             None, None)` den Default (4, 19) (day_window.py) — NICHT die
             deprecateten Preset-Felder hour_from/hour_to (9, 16).
          2. Zeitbasis (Issue #1378): 4–19 Ortszeit, Innsbruck =
             Europe/Vienna, Juli = UTC+2 -> Serverstunden 2..17.
             sonnige Serverstunden {6,7,8,17,18,19} ∩ [2..17] = {6,7,8,17}
             -> 4 Sonnenstunden (in Ortszeit: 8, 9, 10 und 19 Uhr).
             Neu DRAUSSEN gegenueber der Serverzeit-Auswertung: UTC 18 und 19
             (= 20/21 Uhr Ortszeit, liegen hinter dem Fensterende 19 Uhr).
             Neu DRIN: keine.
          Der Test bleibt damit scharf: das falsche (Preset-)Fenster ergaebe
          2.0 h (UTC 7..14 -> sonnig 7, 8), das richtige 4.0 h.

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
                    # #1661 (F003): Zieltag und Versatz gehoeren zusammen und
                    # kommen aus derselben Zeitabfrage — hier Morgen-Slot, 0.
                    tage_ab_ortstag=0,
                    all_locations_cache=[loc],
                )
            result = exc.value.result
        finally:
            ce_mod.fetch_forecast_for_location = original_fetch
            ce_mod.ComparisonEngine = original_engine

        sunny = result.locations[0].sunny_hours
        assert sunny == 4.0, (
            f"RED: der Dispatch lieferte {sunny} Sonnenstunden, erwartet 4.0 "
            "(Tagesfenster 4–19 Ortszeit = UTC 2–17, sonnig UTC 6,7,8,17). "
            "Bei 2.0 reicht er noch das gespeicherte Preset-Fenster (9, 16) "
            "durch — die Mail-Spalte 'Sonne' verliert dann Morgen- und "
            "Abendsonne (Spec #1268 AC-8)."
        )
