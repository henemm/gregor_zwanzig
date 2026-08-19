"""Issue #1468 — Anker und frischer Stand rechnen mit DEMSELBEN Tagesfenster.

SPEC: docs/specs/modules/feat_1468_onset_verschiebung_alarm.md (E2, AC-10)

WAS HIER BEWACHT WIRD, und warum es eine eigene Datei verdient:

Der Beginn-Alarm vergleicht zwei Staende derselben Tour — den Anker (vom
Briefing-/Versandpfad geschrieben, `trip_report_scheduler._fetch_weather`)
gegen den frischen Stand (vom Alarm-Pfad geholt,
`trip_alert._fetch_fresh_weather`). Beide Seiten muessen ihre Onset-Stunde
unter DEMSELBEN Tagesfenster berechnen. Tun sie das nicht, unterscheiden sich
die beiden Zahlen allein durch die Fensterwahl — und der Nutzer bekommt einen
Alarm, obwohl sich am Wetter nichts geaendert hat. Bei einem Fenster 10-16
gegen den Default 4-19 waeren das in der Fixture unten 2 Stunden
"Verschiebung" aus dem Nichts.

WARUM DIE STRUKTUR DAS LOEST: das Fenster haengt am SEGMENT
(`TripSegment.day_window_start_hour`/`_end_hour`, gesetzt in
`trip_segments.convert_trip_to_segments()` aus `trip.report_config`), nicht an
der Aufrufkette. Beide Pfade holen ihre Segmente aus derselben Quelle, also
koennen sie gar nicht mit verschiedenen Fenstern rechnen.

Der erste Test unten ist nach dieser Umstellung leicht gruen — deshalb steht
die POSITIVKONTROLLE daneben: sie stellt genau die Asymmetrie her, die eine
Uebergabe per Parameter erlaubt haette (ein Aufrufer reicht das Fenster
weiter, der andere vergisst es), und zeigt, dass daraus tatsaechlich ein
Alarm entsteht. Ohne sie bewiese der erste Test nichts — er waere auch dann
gruen, wenn ueberhaupt nie ein Beginn-Alarm entstuende.

Kein Mock (CLAUDE.md, Kern-Schicht): Gewitterstufen aus der ECHTEN Fusion,
Segmente aus dem ECHTEN `convert_trip_to_segments()`, Vergleich ueber den
ECHTEN Detektor. Pfadregel #1409: Prueling relativ zu DIESER Datei.
"""
from __future__ import annotations

import sys
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.model_registry import (  # noqa: E402
    cape_ladder_thresholds_jkg, lpi_thresholds_jkg,
)
from app.models import (  # noqa: E402
    ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider,
    TripReportConfig,
)
from app.trip import Stage, Trip, Waypoint  # noqa: E402
from providers.thunder_enrichment import _fuse_thunder_levels  # noqa: E402
from providers.thunder_routing import thunder_region_for  # noqa: E402
from services.alert_preset import expand_per_metric_levels  # noqa: E402
from services.segment_weather import SegmentWeatherService  # noqa: E402
from services.trip_segments import convert_trip_to_segments  # noqa: E402
from services.weather_change_detection import (  # noqa: E402
    WeatherChangeDetectionService,
)
from services.weather_snapshot import WeatherSnapshotService  # noqa: E402

TH_ONSET_FELD = "thunder_onset_utc"
# Die TOUR liegt auf Island (ganzjaehrig UTC+0, keine Sommerzeit): damit ist
# die UTC-Stunde der Fixture zugleich die Ortszeit-Stunde, nach der die
# Aggregation filtert -- der Test haengt weder an der Systemzone noch an der
# Sommerzeit. Die Gewitter-FUSION nutzt weiterhin die geeichte Alpen-Leiter
# (sie kennt die Koordinaten nicht, sie bekommt die Schwellen uebergeben) --
# dasselbe Vorgehen wie in test_onset_shift_alert.py.
ISLAND_LAT, ISLAND_LON = 64.13, -21.90
ALPEN_LAT, ALPEN_LON, MODELL = 47.0, 12.0, "icon_d2"

# Das erste Etappen-Segment laeuft von 08:00 bis 11:42 Ortszeit (GEHZEIT,
# nicht Tagesfenster -- genau darum wirkt der Fensterschnitt zusaetzlich).
# Der Vorschnitt in `_aggregate_for_segment` ist am Ende EXKLUSIV und
# floort auf die Stunde (Bug #806), es bleiben also die Stunden 08, 09, 10.
# Ein Fenster 10-16 schneidet darin nochmals:
#   Fenster 10-16 sieht als erste die 10:00
#   Default 4-19  sieht als erste die 08:00
# -> 2 Stunden Unterschied allein aus der Fensterwahl. Das reicht bei
#    Empfindlichkeit "sensibel" (ab 2 h spaeter) fuer einen Alarm.
ENG = (10, 16)
GEWITTERSTUNDEN = {8: 400.0, 10: 800.0}


def _tag() -> date:
    return date.today() + timedelta(days=1)


def _dp(stunde: int, cape: float) -> ForecastDataPoint:
    t = _tag()
    return ForecastDataPoint(
        ts=datetime(t.year, t.month, t.day, stunde, 0, tzinfo=timezone.utc),
        t2m_c=16.0, wind10m_kmh=10.0, gust_kmh=20.0, precip_1h_mm=0.2,
        cloud_total_pct=40, humidity_pct=50, pop_pct=30,
        cape_jkg=cape, convective_inhibition_jkg=5.0,
    )


def _reihe() -> NormalizedTimeseries:
    punkte = [_dp(h, GEWITTERSTUNDEN.get(h, 100.0)) for h in range(24)]
    region = thunder_region_for(ALPEN_LAT, ALPEN_LON)
    _fuse_thunder_levels(punkte, cape_ladder_thresholds_jkg(MODELL, region),
                         lpi_thresholds_jkg(region))
    return NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="test",
                          grid_res_km=1.0),
        data=punkte,
    )


def _trip(start: int | None, ende: int | None) -> Trip:
    t = Trip(
        id="symmetrie-trip", name="Symmetrie-Trip",
        stages=[Stage(
            id="S1", name="Etappe", date=_tag(),
            waypoints=[
                Waypoint(id="W1", name="Start", lat=ISLAND_LAT, lon=ISLAND_LON,
                         elevation_m=1000),
                Waypoint(id="W2", name="Ziel", lat=ISLAND_LAT + 0.1,
                         lon=ISLAND_LON + 0.1, elevation_m=1200),
            ],
        )],
    )
    t.report_config = TripReportConfig(
        trip_id=t.id, day_window_start_hour=start, day_window_end_hour=ende,
    )
    return t


def _segmente(start: int | None, ende: int | None):
    segmente = convert_trip_to_segments(_trip(start, ende), _tag())
    assert segmente, "Vorbedingung: die Tour muss Segmente ergeben"
    return segmente


def _aggregiert(segment):
    """Ein Etappen-Aggregat ueber den PRODUKTIVEN Weg -- die Onset-Stunde
    entsteht hier wirklich, sie wird nicht gesetzt."""
    from providers.base import get_provider

    return SegmentWeatherService(get_provider("openmeteo"))._aggregate_for_segment(
        segment, _reihe(), fetched_at=datetime.now(timezone.utc),
    )


def _pruefe_fixture_passt_zum_segment(segment) -> None:
    """Vakuum-Schutz: beide Gewitterstunden muessen INNERHALB der Gehzeit
    dieses Segments liegen. Sonst misst der Test den Segment-Vorschnitt statt
    den Fensterschnitt -- und wuerde bei jeder Aenderung der Etappenzeiten
    stillschweigend blind."""
    von = segment.start_time.astimezone(timezone.utc).hour
    bis = segment.end_time.astimezone(timezone.utc).hour
    for stunde in GEWITTERSTUNDEN:
        # Obergrenze EXKLUSIV: der Vorschnitt floort das Segmentende auf die
        # Stunde und filtert `< end_floor` (Bug #806). Ein `<=` hier waere zu
        # lax und liesse eine Fixture durchgehen, deren letzte Gewitterstunde
        # der Vorschnitt bereits wegschneidet.
        assert von <= stunde < bis, (
            f"Fixture passt nicht zum Segment: Gewitterstunde {stunde:02d}:00 "
            f"liegt ausserhalb der Gehzeit {von:02d}-{bis:02d} (Ende exklusiv) "
            "-- der Test misst dann den Vorschnitt, nicht das Tagesfenster."
        )


def _onset_aenderungen(alt, neu) -> list:
    regeln = expand_per_metric_levels({"thunder_onset": "sensibel"})
    detektor = WeatherChangeDetectionService.from_alert_rules(regeln)
    return [
        c for c in detektor.detect_changes(alt, neu, include_absolute=False)
        if c.metric == TH_ONSET_FELD
    ]


# ==========================================================================
# Die Strukturaussage: das Fenster haengt am Segment
# ==========================================================================

def test_jedes_segment_der_tour_traegt_das_eingestellte_fenster():
    """Auch das ZIEL-Segment — es entsteht in `convert_trip_to_segments()` an
    einer eigenen Stelle und wurde dort frueher vergessen (#1584 setzte dort
    nur das Zeit-Ende aus dem Fenster, nicht die Auswertungsgrenzen)."""
    segmente = _segmente(*ENG)
    kennungen = [str(s.segment_id) for s in segmente]
    assert "Ziel" in kennungen, (
        f"Vorbedingung: die Tour muss ein Ziel-Segment haben: {kennungen!r}"
    )
    for s in segmente:
        assert (s.day_window_start_hour, s.day_window_end_hour) == ENG, (
            f"Segment {s.segment_id!r} traegt das Fenster nicht: "
            f"({s.day_window_start_hour}, {s.day_window_end_hour}) statt {ENG}"
        )


def test_ohne_eingestelltes_fenster_bleiben_die_segmente_leer():
    """Bestandsverhalten: keine Angabe heisst `None` am Segment — die
    Aufloesung auf den Default 4-19 gehoert an den Auswertungsort, nicht
    hierher. Zwei Aufloesungen an zwei Orten waeren die Doppelung, die
    ADR-0035 vermeidet."""
    for s in _segmente(None, None):
        assert s.day_window_start_hour is None and s.day_window_end_hour is None, (
            f"Segment {s.segment_id!r} erfindet ein Fenster: "
            f"({s.day_window_start_hour}, {s.day_window_end_hour})"
        )


# ==========================================================================
# Die Wirkung: kein Alarm aus der Fensterwahl
# ==========================================================================

def test_anker_und_frischer_stand_derselben_tour_erzeugen_keinen_alarm():
    """Beide Vergleichsseiten stammen aus derselben Tour mit Fenster 8-16 und
    DERSELBEN Stundenreihe — es hat sich am Wetter nichts geaendert, also darf
    kein Beginn-Alarm entstehen."""
    segment = _segmente(*ENG)[0]
    _pruefe_fixture_passt_zum_segment(segment)
    anker = _aggregiert(segment)
    frisch = _aggregiert(segment)

    assert anker.aggregated.thunder_onset_utc is not None, (
        "Vorbedingung: beide Staende muessen ueberhaupt einen Beginn fuehren, "
        "sonst ist die Gleichheit unten trivial."
    )
    assert _onset_aenderungen(anker, frisch) == [], (
        "Unveraendertes Wetter erzeugt einen Beginn-Alarm: "
        f"Anker {anker.aggregated.thunder_onset_utc}, "
        f"frisch {frisch.aggregated.thunder_onset_utc}"
    )


def test_asymmetrische_fensterwahl_erzeugt_genau_den_scheinalarm():
    """POSITIVKONTROLLE — ohne sie bewacht der Test darueber nichts.

    Hier bekommt EINE Seite kein Fenster (sie faellt damit auf den Default
    4-19 zurueck), die andere behaelt 8-16. Genau diese Asymmetrie waere
    moeglich gewesen, wenn das Fenster als Parameter durch die Aufrufkette
    liefe und ein Aufrufer ihn nicht weiterreicht. Ergebnis: ein Alarm ueber
    eine Verschiebung, die es gar nicht gab -- beide Seiten sehen dieselbe
    Stundenreihe.
    """
    mit_fenster = _segmente(*ENG)[0]
    _pruefe_fixture_passt_zum_segment(mit_fenster)
    ohne_fenster = replace(
        mit_fenster, day_window_start_hour=None, day_window_end_hour=None,
    )
    anker = _aggregiert(ohne_fenster)
    frisch = _aggregiert(mit_fenster)

    a, f = anker.aggregated.thunder_onset_utc, frisch.aggregated.thunder_onset_utc
    assert a is not None and f is not None, "Vorbedingung: beide Staende brauchen einen Beginn"
    assert a.hour != f.hour, (
        "Vorbedingung: die beiden Fenster muessen zu verschiedenen Stunden "
        f"fuehren, sonst zeigt dieser Test nichts ({a.hour} vs. {f.hour})"
    )
    assert _onset_aenderungen(anker, frisch), (
        f"Die Fenster-Asymmetrie ({a.hour:02d}:00 gegen {f.hour:02d}:00) "
        "erzeugt KEINEN Alarm -- dann kann der Test darueber die Symmetrie "
        "auch nicht bewachen."
    )


# ==========================================================================
# Der Anker traegt das Fenster ueber Speichern und Laden
# ==========================================================================

def test_gespeicherter_anker_behaelt_das_fenster_seines_segments():
    """Der Anker haelt die volle Stundenreihe mit (`_serialize_segment`), aus
    einem geladenen Anker-Segment kann also neu aggregiert werden. Faellt das
    Fenster beim Speichern heraus, rechnete dieselbe Reihe beim naechsten Mal
    unter dem Default -- und die Vergleichsbasis waere wieder schief, ohne
    dass irgendwo ein Fehler auftauchte.

    Deshalb schreibt `_serialize_segment()` die beiden Felder mit; hier ist
    der Nachweis, dass sie den Rueckweg ueberstehen UND dass eine erneute
    Aggregation aus dem GELADENEN Segment dieselbe Stunde liefert.
    """
    dienst = WeatherSnapshotService(user_id="onset-fenster-anker")
    segment = _segmente(*ENG)[0]
    dienst.save_alarm_anchor("fenster-trip", _tag(), [_aggregiert(segment)])

    geladen = dienst.load_alarm_anchor("fenster-trip")
    assert geladen, "Anker liess sich nicht laden"
    zurueck = geladen[0].segment
    assert (zurueck.day_window_start_hour, zurueck.day_window_end_hour) == ENG, (
        "Das Auswertungsfenster ueberlebt den Anker nicht: "
        f"({zurueck.day_window_start_hour}, {zurueck.day_window_end_hour}) "
        f"statt {ENG} -- eine erneute Aggregation aus diesem Segment fiele "
        "still auf den Default zurueck."
    )
    erneut = _aggregiert(zurueck).aggregated.thunder_onset_utc
    original = _aggregiert(segment).aggregated.thunder_onset_utc
    assert erneut == original, (
        f"Neu aggregiert aus dem geladenen Anker-Segment: {erneut}, "
        f"aus dem urspruenglichen: {original} -- die beiden muessen gleich sein."
    )


def test_alt_anker_ohne_fensterfelder_laedt_unveraendert():
    """Bestandsdaten (CLAUDE.md-Pflicht): ein Anker, der vor dieser Aenderung
    geschrieben wurde, kennt die beiden Schluessel nicht. Er muss weiterhin
    laden, das Fenster ist dann `None` -> Default 4-19."""
    import json

    dienst = WeatherSnapshotService(user_id="onset-fenster-altanker")
    segment = _segmente(*ENG)[0]
    dienst.save_alarm_anchor("alt-trip", _tag(), [_aggregiert(segment)])

    pfad = dienst._snapshots_dir / "alt-trip_alarm_anchor.json"
    daten = json.loads(pfad.read_text())
    for eintrag in daten["segments"]:
        eintrag.pop("day_window_start_hour", None)
        eintrag.pop("day_window_end_hour", None)
    pfad.write_text(json.dumps(daten, indent=2))

    geladen = dienst.load_alarm_anchor("alt-trip")
    assert geladen, "Alt-Anker ohne die Fensterfelder liess sich nicht laden"
    zurueck = geladen[0].segment
    assert zurueck.day_window_start_hour is None, (
        "Ein Anker ohne Fensterangabe muss None tragen, nicht einen erfundenen "
        f"Wert: {zurueck.day_window_start_hour!r}"
    )
    assert geladen[0].aggregated.thunder_onset_utc is not None, (
        "Das mitgespeicherte Aggregat des Alt-Ankers ist verlorengegangen."
    )
