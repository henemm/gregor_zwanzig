"""#1848 A1, Adversary-Nachzug (implementation-validator, 2026-08-20):
`_build_stage_trend()` muss das Gehzeit-Fenster (AC-1) bis in die
gerenderte Ausblick-Zeile durchreichen -- nicht nur `build_outlook_row()`
isoliert.

**Warum dieser Test noetig ist.** AC-1..AC-3 riefen bisher ausschliesslich
`build_outlook_row()` DIREKT auf, mit von Hand gebautem
`hiking_extrema={"t2m_c": hiking}` (`test_outlook_uses_hiking_window.py`).
Das beweist, dass `build_outlook_row()` einen Override RICHTIG anwendet --
nicht, dass der Scheduler ihn tatsaechlich UEBERGIBT. Die Zusicherung war
dort geprueft, wo der Code STEHT (`outlook.py`), nicht wo er WIRKT
(`trip_report_scheduler.py::_build_stage_trend()`, Zeile ~2348
`segments=seg_weather`). Der Adversary hat das per Mutation belegt: mit
`segments=None` blieben ALLE 625 Tests gruen -- exakt die Fehlerklasse,
die #1417 schon einmal ausgeloest hat (SMS/Telegram/Kurzzusammenfassung
umgestellt, Ausblick vergessen, monatelang unbemerkt, weil keine Wache an
der Naht sass).

Dieser Test ruft `_build_stage_trend()` -- den ECHTEN Scheduler-Pfad --
auf einer echten `TripReportSchedulerService`-Unterklasse, die nur die
drei Netz-/Fetch-Schritte ersetzt (Vorbild
`test_outlook_day_night_thunder_split.py::_TrendSchedulerWithFixedWeather`,
Muster fuer #1653 Adversary-Finding F001 -- dieselbe Fehlerklasse: eine
Fenster-/Override-Uebergabe, die nur an der Aufrufstelle geprueft wird,
nicht an der Verdrahtung dahinter).

Kern-Schicht: keine Mocks, kein Netz, echte Segmente aus dem
Produktivpfad (`_hiking_window_fixtures.build_segments()` ->
`SegmentWeatherService._aggregate_for_segment()`).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from tests.tdd import _hiking_window_fixtures as F


class _SchedulerWithFixedSegments:
    """Echter Scheduler -- `_build_stage_trend()` laeuft UNVERAENDERT --,
    nur die drei Netz-/Fetch-Schritte durch feste Werte ersetzt."""

    @staticmethod
    def build(segments):
        from services.trip_report_scheduler import TripReportSchedulerService

        class _Fixed(TripReportSchedulerService):
            def _convert_trip_to_segments(self, trip, target_date):
                # Rueckgabewert ist irrelevant -- _fetch_weather() unten
                # ignoriert ihn und liefert die festen Segmente.
                return ["ein-segment"]

            def _fetch_weather(self, seg, provider=None):
                return segments

            def _enrich_ensemble_for_trip(self, trip, weather_data):
                return None

        return _Fixed()


def _trip_with_stage(stage_date: date):
    from app.trip import Stage, Trip, Waypoint

    return Trip(
        id="i1848-a1-wiring", name="Wiring-Test",
        stages=[Stage(
            id="S1", name="E7", date=stage_date,
            waypoints=[Waypoint(id="W1", name="Ort", lat=42.0, lon=9.0, elevation_m=500)],
        )],
    )


def test_ac1_vorbedingung_stage_aggregat_und_gehzeit_fenster_divergieren():
    """Kein AC, Testaufbau-Beleg (Muster #1841/#1848-A1-Vorlage): die
    Konstellation ``extremwert_an_der_ankunftsstunde`` muss ueberhaupt
    divergieren, sonst prueft der Wiring-Test unten nichts.

    GEMESSEN (nicht von Hand geschaetzt): ``aggregate_stage()`` liefert
    ``temp_max_c=15.0`` (Segment 2s EXKLUSIVES Fenster [10,12) schliesst
    die Ankunftsstunde 12 Uhr aus -- keine andere Stunde im Etappenfenster
    traegt einen Extremwert, die Basis-Temperatur 15.0 C bleibt Maximum).
    ``hiking_field_min_max()`` liefert ``22.0`` (das Gehzeit-Fenster
    schliesst die Ankunftsstunde beim LETZTEN Segment INKLUSIVE ein --
    genau dort liegt mit 22.0 C die waermste Stunde des Tages)."""
    from output.renderers.day_window import (
        collect_hiking_window_points, hiking_field_min_max,
    )
    from services.weather_metrics import aggregate_stage

    segments = F.CONSTELLATIONS_BY_NAME["extremwert_an_der_ankunftsstunde"].segments()
    agg = aggregate_stage(segments)
    hiking = hiking_field_min_max(collect_hiking_window_points(segments), "t2m_c")

    assert agg.temp_max_c == 15.0, (
        f"Vorbedingung verletzt: Etappenaggregat-Hoch ist {agg.temp_max_c}, "
        "erwartet 15.0 -- die Konstellation liefert nicht mehr das gemessene "
        "Ausgangs-Setup, der Wiring-Test unten koennte nichts pruefen."
    )
    assert hiking is not None and hiking[1] == 22.0, (
        f"Vorbedingung verletzt: Gehzeit-Hoch ist {hiking}, erwartet 22.0."
    )
    assert int(agg.temp_max_c) != int(hiking[1]), (
        f"Vorbedingung verletzt: Etappenaggregat ({agg.temp_max_c}) und "
        f"Gehzeit-Hoch ({hiking[1]}) sind (gerundet) gleich -- der Wiring-"
        "Test koennte eine kaputte Verdrahtung nicht von einer intakten "
        "unterscheiden."
    )


def test_ac1_scheduler_wiring_carries_hiking_window_into_the_outlook_row():
    """AC-1 (Wirkort): der ECHTE Scheduler-Pfad (``_build_stage_trend()``,
    NICHT ``build_outlook_row()`` direkt) muss das Gehzeit-Fenster bis in
    die gerenderte Ausblick-Zeile durchreichen -- die Ankunftsstunde traegt
    hier das Tageshoch (22.0 C), das volle Etappenfenster sieht dagegen nur
    15.0 C (Vorbedingung oben gemessen und belegt).

    Positivkontrolle per Mutation (Pflicht-Nachweis, s. Commit-Message):
    ``segments=seg_weather`` -> ``segments=None`` in
    ``trip_report_scheduler.py::_build_stage_trend()`` macht GENAU diesen
    Test rot -- der Ausblick faellt dann fail-soft auf das
    Etappenaggregat (15) zurueck, dieser Test erwartet aber 22."""
    segments = F.CONSTELLATIONS_BY_NAME["extremwert_an_der_ankunftsstunde"].segments()

    stage_date = date.today() + timedelta(days=1)
    trip = _trip_with_stage(stage_date)
    service = _SchedulerWithFixedSegments.build(segments)

    result = service._build_stage_trend(
        trip, date.today(), now_utc=datetime.now(timezone.utc), tz=ZoneInfo("UTC"),
    )

    assert result.rows, f"Kein Ausblick gebaut (state={result.state}) -- der Test misst sonst nichts."
    row = result.rows[0]
    assert row["temp_hi"] == 22, (
        f"Der ECHTE Scheduler-Pfad zeigt {row['temp_hi']!r} statt 22 (Gehzeit-"
        "Hoch) -- entweder faellt er auf das Etappenaggregat (15) zurueck "
        "(die Uebergabe `segments=seg_weather` an build_outlook_row() fehlt "
        "oder wurde entfernt), oder ein anderer Wert wird geliefert. "
        f"row={row}"
    )
