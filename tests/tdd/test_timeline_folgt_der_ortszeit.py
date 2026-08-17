"""TDD RED — Fix #1795: Timeline und Query-Familie folgen der Ortszeit der Tour.

SPEC: docs/specs/modules/fix_1795_timeline_ortszeit.md (AC-1 bis AC-8, AC-11)
KONTEXT: docs/context/fix-1795-timeline-ortszeit.md

Deckt die Query-Familie (`glance`, `heute_gewitter`, `timeline_heute`,
`timeline_morgen`, `heute`, `morgen`) ab: `_handle_query` bestimmt heute den
Kalendertag ueber den UTC-Tag der Nachricht (`received_at.date()`) statt ueber
den Ortstag der Tour (ADR-0044), und `_fmt_timeline` formatiert Ankunftszeiten
roh in UTC statt in der Ortszeit des Wegpunkts.

Testpolitik (CLAUDE.md "Test-Politik: Zwei Schichten"): Kern-Schicht, kein
Netz. Echte ``Trip``/``Stage``/``Waypoint``-Objekte, echter
``TripCommandProcessor`` ueber den PRODUKTIVEN Eintrittspunkt
``process()``, echte Wetter-Schnappschuesse (``WeatherSnapshotService.save``)
-- kein ``Mock()``/``patch()``. Fuer AC-8 laeuft der echte Fetch-Pfad ueber
die projektweit autouse gesetzte ``GZ_TEST_FIXTURE_DIR`` (Issue #346,
``tests/conftest.py``): kein Live-API-Call, kein Mock-Theater.

Pfadregel #1409: diese Datei liest nichts vom Hauptrepo-Pfad; ADR-0044
(AC-11) wird relativ zur eigenen Testdatei aufgeloest.

🔴 Jeder Test, der einen Wetter-Schnappschuss braucht, bestueckt ihn
ausdruecklich mit Segmenten fuer HEUTE UND MORGEN (#1818: ein einspuriger
Scheduler-Anker deckt strukturell nur einen Tag ab -- s. Spec "Nicht in
dieser Scheibe").
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from app.loader import save_trip
from app.models import GPXPoint, SegmentWeatherData, SegmentWeatherSummary, TripSegment
from app.trip import Stage, Trip, Waypoint
from services.trip_alert import TripAlertService
from services.trip_day import trip_local_today
from services.trip_report_scheduler import TripReportSchedulerService
from services.weather_snapshot import WeatherSnapshotService
from tests.tdd.conftest import WP_KORSIKA, WP_NZ, _anker, trip_two_zones
from tests.tdd.test_befehlspfade_folgen_ortszone import (
    D20,
    D21,
    D22,
    D23,
    KORSIKA_ZONE,
    MITTAGS_UTC,
    NACHTS_UTC,
    WELLINGTON_ZONE,
    _befehl,
    _trip,
)

_ADR_0044 = (
    Path(__file__).resolve().parents[2]
    / "docs" / "adr" / "0044-kalendertage-folgen-der-ortszeit.md"
)


# ---------------------------------------------------------------------------
# Helfer -- Wetter-Schnappschuss mit kontrolliertem `arrival_time`
# ---------------------------------------------------------------------------

def _seg(arrival_time: datetime, coords: tuple[float, float], *,
         elevation_m: int = 1500, seg_id: int = 1,
         wind_max_kmh: float = 20.0) -> SegmentWeatherData:
    """Ein Timeline-Punkt mit kontrolliertem ``arrival_time`` (aware UTC) --
    Metriken sind Platzhalter, nur ``arrival_time``/Koordinaten sind fuer
    diese Suite relevant (Filter-/Formatier-Logik, nicht Wetterinhalt).
    ``wind_max_kmh`` optional erhoehbar (Adversary-Fix F002/AC-4-Nachtrag):
    ab 40 km/h loest ``_timeline_buttons`` den Wind-Drilldown-Button aus --
    ein von aussen beobachtbares Signal, OB ein Wegpunkt gefunden wurde."""
    lat, lon = coords
    segment = TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=elevation_m - 100),
        end_point=GPXPoint(lat=lat, lon=lon, elevation_m=elevation_m),
        start_time=arrival_time - timedelta(hours=2), end_time=arrival_time,
        duration_hours=2.0, distance_km=5.0, ascent_m=100.0, descent_m=0.0,
    )
    aggregated = SegmentWeatherSummary(
        temp_min_c=10.0, temp_max_c=18.0, wind_max_kmh=wind_max_kmh,
    )
    return SegmentWeatherData(
        segment=segment, timeseries=None, aggregated=aggregated,
        fetched_at=arrival_time, provider="test",
    )


def _save_snapshot(trip_id: str, segments: list[SegmentWeatherData],
                    user_id: str = "default") -> None:
    """Speichert Segmente als UNDATIERTEN Schnappschuss -- derselbe Weg, den
    ``WeatherExtractor.timeline()`` liest. Die Tagestrennung passiert erst
    beim Formatieren (weather_extractor.py), nicht hier."""
    WeatherSnapshotService(user_id).save(
        trip_id, segments, segments[0].segment.end_time.date(),
    )


def _stage_mit_zwei_wegpunkten(stage_id: str, tag: date,
                                coords: tuple[float, float]) -> Stage:
    """Etappe mit ZWEI Wegpunkten -- ``convert_trip_to_segments()`` verwirft
    Etappen mit weniger (``trip_segments.py``)."""
    lat, lon = coords
    return Stage(
        id=stage_id, name=f"Etappe {tag:%d.%m.}", date=tag,
        waypoints=[
            Waypoint(id=f"{stage_id}-A", name="Start", lat=lat, lon=lon, elevation_m=500),
            Waypoint(id=f"{stage_id}-B", name="Ziel", lat=lat + 0.05, lon=lon + 0.05,
                     elevation_m=800),
        ],
    )


# ══════════════════════ AC-1: Uhrzeit-Umrechnung, AUSSERHALB des Mismatch-Fensters ══════════════════════


def test_ac1_timeline_zeigt_ortszeit_nicht_die_rohe_utc_zeit():
    """AC-1.

    GIVEN eine Korsika-Etappe (Europe/Paris, im August UTC+2) hat einen
          Wegpunkt mit ``arrival_time`` 06:00 UTC (= 08:00 Ortszeit),
    WHEN  ``timeline_heute`` zu MITTAGS_UTC (14:00 UTC) abgefragt wird --
          bewusst AUSSERHALB des Mismatch-Fensters, damit allein die
          Uhrzeitumrechnung geprueft wird, kein Tageswechsel,
    THEN  zeigt die Timeline-Zeile "🕐 08:00", nicht "🕐 06:00".
    """
    assert MITTAGS_UTC.astimezone(ZoneInfo(KORSIKA_ZONE)).date() == D20 == MITTAGS_UTC.date(), (
        "Testaufbau (Kontrolllauf): MITTAGS_UTC muss AUSSERHALB des Mismatch-"
        "Fensters liegen (Orts- und Weltzeit-Tag identisch), sonst prueft "
        "AC-1 versehentlich einen Tageswechsel statt der Uhrzeit"
    )
    ankunft = datetime(2026, 8, 20, 6, 0, tzinfo=timezone.utc)

    with freeze_time(MITTAGS_UTC):
        trip = _trip("ac1-uhrzeit", [D20], WP_KORSIKA)
        save_trip(trip)
        _save_snapshot(trip.id, [_seg(ankunft, WP_KORSIKA)])

        body = _befehl(trip, "### query: timeline_heute", MITTAGS_UTC).confirmation_body

    assert "🕐 08:00" in body, (
        f"AC-1: erwartete Ortszeit '🕐 08:00' (Ankunft 06:00 UTC, Korsika "
        f"UTC+2) fehlt in der Timeline:\n{body}"
    )
    assert "🕐 06:00" not in body, (
        f"AC-1: die Timeline zeigt noch die rohe UTC-Zeit '🕐 06:00' statt "
        f"der umgerechneten Ortszeit:\n{body}"
    )


# ══════════════════════ AC-2: alle vier Kommandos folgen dem Ortstag ══════════════════════


@pytest.mark.parametrize("query_key, body_cmd, erwartete_tage", [
    pytest.param("glance", "### query: glance", (D21, D22), id="glance"),
    pytest.param("heute_gewitter", "### query: heute_gewitter", (D21,), id="heute_gewitter"),
    pytest.param("timeline_heute", "### query: timeline_heute", (D21,), id="timeline_heute"),
    pytest.param("timeline_morgen", "### query: timeline_morgen", (D22,), id="timeline_morgen"),
])
def test_ac2_vier_kommandos_folgen_dem_ortstag(query_key, body_cmd, erwartete_tage):
    """AC-2.

    GIVEN eine Korsika-Tour mit Etappen fuer den Ortstag D+1/D+2,
    WHEN  eine Nachricht zu NACHTS_UTC (22:30 UTC = 00:30 Ortszeit des
          Folgetags, Mismatch-Fenster) fuer eines der vier Kommandos kommt,
    THEN  bezieht sich "heute"/"morgen" auf den ORTSTAG (D+1/D+2) -- vor dem
          Fix trugen alle vier noch den UTC-Tag der Nachricht (D/D+1).
    """
    with freeze_time(NACHTS_UTC):
        _anker(NACHTS_UTC, KORSIKA_ZONE, D21)
        trip = _trip(f"ac2-{query_key}", [D21, D22], WP_KORSIKA)
        save_trip(trip)
        _save_snapshot(trip.id, [
            _seg(datetime(2026, 8, 21, 10, 0, tzinfo=timezone.utc), WP_KORSIKA, seg_id=1),
            _seg(datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc), WP_KORSIKA, seg_id=2),
        ])

        body = _befehl(trip, body_cmd, NACHTS_UTC).confirmation_body

    for tag in erwartete_tage:
        erwartet = f"({tag:%d.%m})"
        assert erwartet in body, (
            f"AC-2 [{query_key}]: erwartete Ortstag-Beschriftung {erwartet!r} "
            f"fehlt in der Kopfzeile — vor dem Fix trug sie den UTC-Tag der "
            f"Nachricht ({NACHTS_UTC.date():%d.%m}/"
            f"{NACHTS_UTC.date() + timedelta(days=1):%d.%m}).\n{body}"
        )


# ══════════════════════ AC-3: Kopplung Datum + Uhrzeit ══════════════════════


def test_ac3_timeline_heute_koppelt_datum_und_uhrzeit():
    """AC-3.

    GIVEN ein Wetter-Snapshot traegt eine Etappe fuer den Ortstag D+1, die
          Nachricht kommt zu NACHTS_UTC (Mismatch-Fenster, Ortstag = D+1),
    WHEN  ``timeline_heute`` abgefragt wird,
    THEN  nennt die Kopfzeile den Ortstag D+1 UND darunter steht mindestens
          eine ortszeitrichtig umgerechnete 🕐-Zeile -- EINE Assertion-Gruppe
          prueft BEIDES gemeinsam, ein Halb-Fix (nur Filter ODER nur
          Formatierung umgestellt) muss hier durchfallen.

    🔴 Nachbesserung (Adversary-Befund F001): die urspruengliche Fassung
    waehlte ``ankunft_heute`` so, dass roher UTC-Tag (21.08.) UND Ortstag
    (21.08.) zufaellig zusammenfielen -- ein auf rohes UTC zurueckgedrehter
    Filter (``p.arrival_time.date() == target_date``) fand denselben Punkt
    TROTZDEM, der Test blieb bei diesem Halb-Fix gruen. ``ankunft_heute``
    liegt jetzt bewusst im Mismatch-Fenster (22:30 UTC am VORTAG = 00:30
    Ortszeit): roher UTC-Tag (20.08.) != Ortstag (21.08.) -- ein
    zurueckgedrehter Filter findet den Punkt NICHT mehr (Timeline leer,
    uhrzeit_ok wird False), eine zurueckgedrehte Formatierung zeigt "22:30"
    statt "00:30" (uhrzeit_ok ebenfalls False). Beide Richtungen fallen
    ueber dieselbe Assertion durch. Die Drei-Wege-Vorbedingung (Ortstag ==
    D21, roher Tag != D21) wird im Testkoerper GEMESSEN, nicht nur im
    Kommentar behauptet.

    🔴 Zweite Nachbesserung (eigene Mutations-Gegenprobe): ``ankunft_morgen``
    lag urspruenglich EBENFALLS im Mismatch-Fenster (21.08. 22:30 UTC), mit
    rohem UTC-Tag 21.08. -- IDENTISCH mit ``D21``, dem Zieltag von "heute".
    Unter dem zurueckgedrehten Filter fiel dadurch nicht "kein Punkt
    gefunden" auf, sondern der FALSCHE Punkt (``ankunft_morgen`` statt
    ``ankunft_heute``) wurde als "heute" gezeigt -- zufaellig mit derselben
    lokalen Uhrzeit "00:30", sodass die Assertion trotzdem gruen blieb. Die
    Mutations-Gegenprobe deckte das auf. ``ankunft_morgen`` liegt jetzt
    bewusst AUSSERHALB des Mismatch-Fensters (roher Tag == Ortstag == D22),
    kann also unter keiner Filter-Variante mit D21 verwechselt werden --
    im Testkoerper gemessen, nicht nur behauptet.
    """
    ankunft_heute = datetime(2026, 8, 20, 22, 30, tzinfo=timezone.utc)   # 00:30 Korsika am 21.08, Mismatch-Fenster
    ankunft_morgen = datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc)  # 12:00 Korsika am 22.08, ausserhalb des Fensters

    with freeze_time(NACHTS_UTC):
        assert ankunft_heute.astimezone(ZoneInfo(KORSIKA_ZONE)).date() == D21, (
            "Testaufbau: ankunft_heute muss lokal (Korsika) auf den Ortstag "
            f"{D21} fallen"
        )
        assert ankunft_heute.date() != D21, (
            "Testaufbau nicht diskriminierend: roher UTC-Tag von "
            f"ankunft_heute ({ankunft_heute.date()}) darf nicht mit dem "
            f"Ortstag ({D21}) zusammenfallen -- sonst faende ein auf rohes "
            "UTC zurueckgedrehter Filter denselben Punkt trotzdem (Adversary "
            "F001)"
        )
        assert ankunft_morgen.date() != D21, (
            "Testaufbau nicht diskriminierend: roher UTC-Tag von "
            f"ankunft_morgen ({ankunft_morgen.date()}) darf nicht mit D21 "
            "zusammenfallen -- sonst koennte ein zurueckgedrehter Filter "
            "diesen Punkt statt ankunft_heute als 'heute' zeigen und die "
            "Assertion zufaellig gruen bleiben"
        )

        _anker(NACHTS_UTC, KORSIKA_ZONE, D21)
        trip = _trip("ac3-kopplung", [D21, D22], WP_KORSIKA)
        save_trip(trip)
        _save_snapshot(trip.id, [
            _seg(ankunft_heute, WP_KORSIKA, seg_id=1),
            _seg(ankunft_morgen, WP_KORSIKA, seg_id=2),
        ])

        body = _befehl(trip, "### query: timeline_heute", NACHTS_UTC).confirmation_body

    kopfzeile_ok = f"({D21:%d.%m})" in body
    uhrzeit_ok = "🕐 00:30" in body
    assert kopfzeile_ok and uhrzeit_ok, (
        "AC-3: EINE Assertion-Gruppe muss BEIDE Bestandteile pruefen -- den "
        "Kopfzeilen-Ortstag UND eine ortszeitrichtig umgerechnete 🕐-Zeile "
        f"(kopfzeile_ok={kopfzeile_ok}, uhrzeit_ok={uhrzeit_ok}):\n{body}"
    )


# ══════════════════════ AC-4: Mehrzonen — je Tag die eigene Zone ══════════════════════


def test_ac4_glance_nutzt_je_tag_die_eigene_zone():
    """AC-4.

    GIVEN eine Tour hat die heutige Etappe in Neuseeland (Pacific/Auckland,
          UTC+12) und die morgige auf Korsika (Europe/Paris, UTC+2),
    WHEN  ``glance`` abgefragt wird,
    THEN  beschriftet/filtert ``_fmt_glance`` den heutigen Abschnitt in der
          neuseelaendischen Zone und den morgigen in der korsischen Zone --
          je Tag die Zone SEINER EIGENEN Etappe, nicht eine gemeinsame Zone.

    🔴 Nachbesserung (PO-Review): die urspruengliche Fassung diskriminierte
    nur EINE falsche Abkuerzung ("immer Korsika-Zone"), nicht "immer
    Wellington-Zone". Die Wegpunkt-Zeiten sind jetzt so gewaehlt, dass alle
    DREI moeglichen Lagen ein VERSCHIEDENES Ergebnis liefern:

      (i)   je Tag die eigene Zone (KORREKT)   -> heute gefunden, morgen gefunden
      (ii)  immer Wellington-Zone (falsch)     -> heute gefunden, morgen NICHT gefunden
      (iii) immer Korsika-Zone (falsch)        -> heute NICHT gefunden, morgen gefunden

    Vier Vorbedingungen tragen das:
      1. heute_zeit liegt lokal (Wellington) auf ortstag_heute            [i, ii]
      2. heute_zeit liegt lokal (Korsika) NICHT auf ortstag_heute         [iii]
      3. morgen_zeit liegt lokal (Korsika) auf korsika_tag                [i, iii]
      4. morgen_zeit liegt lokal (Wellington) NICHT auf korsika_tag       [ii]

    🔴 Belegte Grenze (statt behauptet): heute_zeit traegt zusaetzlich ein
    rohes UTC-Datum ≠ Wellington-Ortsdatum (treibt das RED des HEUTIGEN,
    unreparierten Codes, der nach rohem UTC filtert). Dieselbe Eigenschaft
    fuer morgen_zeit (rohes UTC-Datum ≠ Korsika-Ortsdatum) ist mit
    Bedingung 4 NICHT gleichzeitig erfuellbar -- Rechnung:
    Korsika-Ortstag(korsika_tag) deckt UTC [D-1 22:00, D 22:00). Darin ist
    "rohes Datum ≠ korsika_tag" nur das erste Zweistundenfenster
    [D-1 22:00, D 00:00). Wellington-Ortstag(korsika_tag) deckt UTC
    [D-1 12:00, D 12:00) -- und [D-1 22:00, D 00:00) liegt VOLLSTAENDIG
    darin. Jeder Punkt mit rohem Datum ≠ korsika_tag faellt also zwangs-
    laeufig auch in Wellingtons korsika_tag-Fenster (Bedingung 4 verletzt).
    Ein einzelner Zeitpunkt kann beide Eigenschaften nicht gleichzeitig
    tragen. Das RED des Ist-Zustands haengt deshalb ausschliesslich an
    heute_zeit -- ausreichend, da EINE fehlschlagende Assertion genuegt.
    """
    heute_zeit = datetime(2026, 8, 18, 20, 0, tzinfo=timezone.utc)     # 08:00 Wellington am 19.08, RAW-UTC 18.08
    morgen_zeit = datetime(2026, 8, 20, 18, 0, tzinfo=timezone.utc)    # 20:00 Korsika am 20.08, 06:00 Wellington am 21.08
    abfrage = datetime(2026, 8, 19, 6, 0, tzinfo=timezone.utc)

    with freeze_time(abfrage):
        ortstag_heute = abfrage.astimezone(ZoneInfo(WELLINGTON_ZONE)).date()
        assert ortstag_heute == date(2026, 8, 19), (
            f"Testaufbau: Ortstag heute (Wellington) muss 19.08 sein, ist {ortstag_heute}"
        )
        korsika_tag = ortstag_heute + timedelta(days=1)

        # Bedingung 1 + 2 (heute_zeit): eigene Zone trifft, fremde (Korsika) nicht.
        assert heute_zeit.astimezone(ZoneInfo(WELLINGTON_ZONE)).date() == ortstag_heute, (
            "Testaufbau: heute_zeit muss lokal (Wellington) auf den Ortstag heute fallen"
        )
        assert heute_zeit.astimezone(ZoneInfo(KORSIKA_ZONE)).date() != ortstag_heute, (
            "Testaufbau nicht diskriminierend: heute_zeit muesste unter der "
            "falschen Korsika-Zone ZUFAELLIG denselben Ortstag treffen -- "
            "Mutante (iii) waere damit ungefangen"
        )
        assert heute_zeit.date() != ortstag_heute, (
            "Testaufbau nicht diskriminierend: RAW-UTC-Datum und Wellington-"
            "Ortsdatum des heutigen Wegpunkts sind gleich (#1726 F002) -- "
            "treibt das RED des unreparierten (roh-UTC-filternden) Codes"
        )

        # Bedingung 3 + 4 (morgen_zeit): eigene Zone trifft, fremde (Wellington) nicht.
        assert morgen_zeit.astimezone(ZoneInfo(KORSIKA_ZONE)).date() == korsika_tag, (
            "Testaufbau: morgen_zeit muss lokal (Korsika) auf den Folgetag fallen"
        )
        assert morgen_zeit.astimezone(ZoneInfo(WELLINGTON_ZONE)).date() != korsika_tag, (
            "Testaufbau nicht diskriminierend: morgen_zeit muesste unter der "
            "falschen Wellington-Zone ZUFAELLIG denselben Ortstag treffen -- "
            "Mutante (ii) waere damit ungefangen"
        )

        trip = trip_two_zones(ortstag_heute, trip_id="ac4-mehrzonen")
        save_trip(trip)
        _save_snapshot(trip.id, [
            _seg(heute_zeit, WP_NZ, seg_id=1),
            _seg(morgen_zeit, WP_KORSIKA, seg_id=2),
        ])

        body = _befehl(trip, "### query: glance", abfrage).confirmation_body

    assert f"heute ({ortstag_heute:%d.%m})" in body, f"AC-4: Kopfzeile 'heute' fehlt:\n{body}"
    assert f"morgen ({korsika_tag:%d.%m})" in body, f"AC-4: Kopfzeile 'morgen' fehlt:\n{body}"
    assert f"heute ({ortstag_heute:%d.%m}): Keine Etappe geplant" not in body, (
        "AC-4: die NEUSEELAND-Etappe (eigene Zone: Wellington) wurde nicht "
        f"gefunden -- rohe UTC-Filterung (Ist-Zustand) bzw. eine "
        f"gemeinsame Korsika-Zone (Mutante iii) findet sie nicht:\n{body}"
    )
    assert f"morgen ({korsika_tag:%d.%m}): Keine Etappe geplant" not in body, (
        f"AC-4: die KORSIKA-Etappe (eigene Zone: Europe/Paris) wurde nicht "
        f"gefunden -- eine gemeinsame Wellington-Zone (Mutante ii) findet "
        f"sie nicht:\n{body}"
    )


# ═══════════ Adversary-Fix F005 (schliesst die Fehlerklasse aus F002/F004) ═══════════
#
# Ausgezaehlt: SIEBEN Zonen-Entscheidungspunkte in `_handle_query` --
# `glance` reicht ZWEI Argumente durch (`tz_heute` fuer heute, `tz_morgen`
# fuer morgen, EIN Aufruf `_fmt_glance(..., tz_heute, tz_morgen)`),
# `heute_gewitter` EINES, `timeline_heute` ZWEI (Text via `_fmt_timeline`,
# Buttons via `_timeline_buttons`), `timeline_morgen` ebenfalls ZWEI.
# AC-2/AC-3 nutzen einzonige Korsika-Touren (`tz_heute == tz_morgen` dort),
# AC-4 deckt nur `glance` ab -- ein Zonentausch an JEDEM der sechs
# UEBRIGEN Punkte blieb dadurch fuer sich genommen unsichtbar (F002/F004,
# beide inzwischen geschlossen -- s. Bericht).
#
# EIN parametrisierter Test statt vier/fuenf Einzeltests, auf EINER
# Mehrzonen-Tour (`trip_two_zones`: heute Wellington, morgen Korsika):
# fuer jedes der vier Kommandos ein Wegpunkt, dessen Ortszeit unter der
# EIGENEN Zone einen ANDEREN Tag/eine andere Uhrzeit ergibt als unter der
# Zone des jeweils ANDEREN Tages. Wo ein `reply_markup` existiert
# (`timeline_heute`/`timeline_morgen`), traegt es eine eigene Assertion --
# sonst bliebe der Button-Pfad unbewacht. Ersetzt die drei F002-Tests und
# den F004-Test vollstaendig (geloescht -- die Matrix deckt exakt dieselbe
# Fehlerklasse ab, staerker: alle sieben Punkte statt einzelner, s. Beleg
# im Bericht des Auftrags: Mutations-Gegenprobe ueber alle sieben Punkte).

_F005_ABFRAGE = datetime(2026, 8, 19, 6, 0, tzinfo=timezone.utc)
_F005_HEUTE_ZEIT = datetime(2026, 8, 18, 15, 0, tzinfo=timezone.utc)    # 03:00 Wellington 19.08, 17:00 Korsika 18.08
_F005_MORGEN_ZEIT = datetime(2026, 8, 20, 18, 0, tzinfo=timezone.utc)   # 20:00 Korsika 20.08, 06:00 Wellington 21.08


@pytest.mark.parametrize("query_key, body_cmd", [
    pytest.param("glance", "### query: glance", id="glance"),
    pytest.param("heute_gewitter", "### query: heute_gewitter", id="heute_gewitter"),
    pytest.param("timeline_heute", "### query: timeline_heute", id="timeline_heute"),
    pytest.param("timeline_morgen", "### query: timeline_morgen", id="timeline_morgen"),
])
def test_f005_alle_vier_kommandos_nutzen_die_zone_ihrer_eigenen_etappe(query_key, body_cmd):
    """Adversary-Fix F005.

    GIVEN eine Mehrzonen-Tour hat die heutige Etappe in Neuseeland
          (Pacific/Auckland) und die morgige auf Korsika (Europe/Paris), je
          ein Wegpunkt liegt so, dass seine Ortszeit unter der EIGENEN Zone
          einen anderen Tag/eine andere Uhrzeit ergibt als unter der Zone
          des jeweils ANDEREN Tages,
    WHEN  eines der vier Query-Kommandos abgefragt wird,
    THEN  spiegeln Text UND (wo vorhanden) ``reply_markup`` den unter der
          EIGENEN Zone gefundenen Wegpunkt -- ein Tausch der Zone an JEDEM
          der sieben Entscheidungspunkte in ``_handle_query`` (glance
          heute/morgen, heute_gewitter, timeline_heute Text/Buttons,
          timeline_morgen Text/Buttons) muss fuer das jeweils betroffene
          Kommando durchfallen.
    """
    ortstag_heute = _F005_ABFRAGE.astimezone(ZoneInfo(WELLINGTON_ZONE)).date()
    morgen_tag = ortstag_heute + timedelta(days=1)

    heute_wellington = _F005_HEUTE_ZEIT.astimezone(ZoneInfo(WELLINGTON_ZONE))
    heute_korsika = _F005_HEUTE_ZEIT.astimezone(ZoneInfo(KORSIKA_ZONE))
    morgen_korsika = _F005_MORGEN_ZEIT.astimezone(ZoneInfo(KORSIKA_ZONE))
    morgen_wellington = _F005_MORGEN_ZEIT.astimezone(ZoneInfo(WELLINGTON_ZONE))

    # Vorbedingungen -- fuer JEDEN Parameterfall gemessen (nicht behauptet):
    # die EIGENE Zone muss den Wegpunkt auf den erwarteten Ortstag legen,
    # die FREMDE Zone auf einen ANDEREN Tag UND eine andere Uhrzeit --
    # sonst waere der jeweilige Zonentausch strukturell unsichtbar.
    assert ortstag_heute == date(2026, 8, 19), (
        f"Testaufbau: Ortstag heute (Wellington) muss 19.08 sein, ist {ortstag_heute}"
    )
    assert heute_wellington.date() == ortstag_heute, (
        "Testaufbau: heute_zeit muss lokal (Wellington, EIGENE Zone der "
        f"heutigen Etappe) auf den heutigen Ortstag {ortstag_heute} fallen"
    )
    assert heute_korsika.date() != ortstag_heute, (
        "Testaufbau nicht diskriminierend: unter der FALSCHEN Zone "
        "(Korsika, Zone von MORGEN) muss heute_zeit auf einen ANDEREN Tag "
        "fallen -- sonst faende ein Zonentausch den Wegpunkt trotzdem"
    )
    assert heute_wellington.strftime("%H:%M") != heute_korsika.strftime("%H:%M"), (
        "Testaufbau nicht diskriminierend: die beiden Zonen muessen fuer "
        "heute_zeit tatsaechlich verschiedene Ortszeiten ergeben"
    )
    assert morgen_korsika.date() == morgen_tag, (
        "Testaufbau: morgen_zeit muss lokal (Korsika, EIGENE Zone der "
        f"morgigen Etappe) auf den morgigen Ortstag {morgen_tag} fallen"
    )
    assert morgen_wellington.date() != morgen_tag, (
        "Testaufbau nicht diskriminierend: unter der FALSCHEN Zone "
        "(Wellington, Zone von HEUTE) muss morgen_zeit auf einen ANDEREN "
        "Tag fallen -- sonst faende ein Zonentausch den Wegpunkt trotzdem"
    )
    assert morgen_korsika.strftime("%H:%M") != morgen_wellington.strftime("%H:%M"), (
        "Testaufbau nicht diskriminierend: die beiden Zonen muessen fuer "
        "morgen_zeit tatsaechlich verschiedene Ortszeiten ergeben"
    )

    with freeze_time(_F005_ABFRAGE):
        trip = trip_two_zones(ortstag_heute, trip_id=f"f005-{query_key}")
        save_trip(trip)
        _save_snapshot(trip.id, [
            _seg(_F005_HEUTE_ZEIT, WP_NZ, seg_id=1, wind_max_kmh=45.0),
            _seg(_F005_MORGEN_ZEIT, WP_KORSIKA, seg_id=2, wind_max_kmh=45.0),
        ])

        ergebnis = _befehl(trip, body_cmd, _F005_ABFRAGE)
        body = ergebnis.confirmation_body

    if query_key == "glance":
        assert f"heute ({ortstag_heute:%d.%m}): Keine Etappe geplant" not in body, (
            "F005 [glance, heute-Argument]: der heutige Wegpunkt "
            f"(Wellington) wurde nicht gefunden:\n{body}"
        )
        assert f"morgen ({morgen_tag:%d.%m}): Keine Etappe geplant" not in body, (
            "F005 [glance, morgen-Argument]: der morgige Wegpunkt (Korsika) "
            f"wurde nicht gefunden:\n{body}"
        )
    elif query_key == "heute_gewitter":
        assert "Keine Etappe geplant" not in body, (
            "F005 [heute_gewitter]: der heutige Wegpunkt (Wellington) wurde "
            f"nicht gefunden:\n{body}"
        )
    elif query_key == "timeline_heute":
        erwartete_zeile = f"🕐 {heute_wellington.strftime('%H:%M')}"
        assert erwartete_zeile in body, (
            "F005 [timeline_heute, Text]: die ortszeitrichtige "
            f"(Wellington-)Uhrzeit fehlt:\n{body}"
        )
        callbacks = [
            btn["callback_data"]
            for row in ergebnis.reply_markup["inline_keyboard"]
            for btn in row
        ]
        assert "dd_wind_today" in callbacks, (
            "F005 [timeline_heute, Buttons]: der Wind-Drilldown-Button "
            f"fehlt: {callbacks!r}"
        )
    elif query_key == "timeline_morgen":
        erwartete_zeile = f"🕐 {morgen_korsika.strftime('%H:%M')}"
        assert erwartete_zeile in body, (
            "F005 [timeline_morgen, Text]: die ortszeitrichtige "
            f"(Korsika-)Uhrzeit fehlt:\n{body}"
        )
        callbacks = [
            btn["callback_data"]
            for row in ergebnis.reply_markup["inline_keyboard"]
            for btn in row
        ]
        assert "dd_wind_tomorrow" in callbacks, (
            "F005 [timeline_morgen, Buttons]: der Wind-Drilldown-Button "
            f"fehlt: {callbacks!r}"
        )


# ═══════ Dokumentierte Grenze der F005-Matrix: EIN Rest-Fall aus F002 ═══════
#
# Die F005-Matrix oben deckt (per Mutations-Gegenprobe belegt, s. Bericht des
# Auftrags) alle SIEBEN `_handle_query`-Entscheidungspunkte UND zusaetzlich,
# als Nebeneffekt derselben Konstruktion, drei der vier urspruenglichen
# F002-Mutationen (den internen UTC-Ruckfall in `_fmt_gewitter`,
# `_timeline_buttons` und im HEUTE-Zweig von `_fmt_glance`). EINE
# F002-Mutation bleibt strukturell unerreichbar: der interne UTC-Ruckfall im
# MORGEN-Zweig von `_fmt_glance` (`agg_morgen = self._aggregate_day(...,
# UTC)` statt `tz_morgen`).
#
# Beweis (nicht nur behauptet): fuer einen Wegpunkt, der unter Korsika
# (+2h) auf den morgigen Ortstag T faellt, aber unter Weltzeit NICHT (also
# den internen UTC-Ruckfall faengt), MUSS der Zeitpunkt in der zweistuen-
# digen Luecke [T-1 22:00, T 00:00) UTC liegen (dem Teil von Korsikas
# Tagesfenster [T-1 22:00, T 22:00), der VOR dem UTC-Tageswechsel liegt).
# Wellingtons Tagesfenster fuer T ist [T-1 12:00, T 12:00) (+12h) -- und
# [T-1 22:00, T 00:00) liegt VOLLSTAENDIG darin (T-1 22:00 >= T-1 12:00,
# T 00:00 <= T 12:00). JEDER Zeitpunkt, der den UTC-Ruckfall faengt, faellt
# also zwangslaeufig AUCH unter Wellington auf T -- ein Wellington/Korsika-
# Tausch (F004/F005s Fehlerklasse) waere an genau diesem Punkt dann NICHT
# mehr diskriminierbar. Beide Eigenschaften gleichzeitig sind fuer EINEN
# Wegpunkt auf dieser Zweizonen-Tour unerreichbar -- deshalb bleibt dieser
# EINE Fall als eigener, einzoniger Test stehen (Mismatch-Fenster-Muster,
# unveraendert aus F002 uebernommen) statt in der Matrix aufzugehen.


def test_f002_rest_glance_morgen_internen_utc_ruckfall():
    """Adversary-Fix F002, Rest-Fall (s. Beweis oben): der MORGEN-Zweig von
    ``_fmt_glance`` muss ``tz_morgen`` tatsaechlich verwenden -- nicht nur
    einen ANDEREN Zonenwert (das deckt F005), sondern auch nicht intern auf
    UTC zurueckfallen. Einzonige Korsika-Tour, Wegpunkt im Mismatch-Fenster.
    """
    morgen_zeit = datetime(2026, 8, 21, 22, 30, tzinfo=timezone.utc)  # 00:30 Korsika am 22.08
    heute_zeit = datetime(2026, 8, 21, 10, 0, tzinfo=timezone.utc)    # unauffaellig, kein Mismatch

    with freeze_time(NACHTS_UTC):
        assert morgen_zeit.astimezone(ZoneInfo(KORSIKA_ZONE)).date() == D22, (
            "Testaufbau: morgen_zeit muss lokal (Korsika) auf D22 fallen"
        )
        assert morgen_zeit.date() != D22, (
            "Testaufbau nicht diskriminierend: roher UTC-Tag von morgen_zeit "
            "darf nicht mit D22 zusammenfallen -- sonst faende ein interner "
            "UTC-Ruckfall denselben Punkt trotzdem"
        )

        _anker(NACHTS_UTC, KORSIKA_ZONE, D21)
        trip = _trip("f002-rest-glance-morgen", [D21, D22], WP_KORSIKA)
        save_trip(trip)
        _save_snapshot(trip.id, [
            _seg(heute_zeit, WP_KORSIKA, seg_id=1),
            _seg(morgen_zeit, WP_KORSIKA, seg_id=2),
        ])

        body = _befehl(trip, "### query: glance", NACHTS_UTC).confirmation_body

    assert f"morgen ({D22:%d.%m}): Keine Etappe geplant" not in body, (
        "F002 (Rest): der morgige Wegpunkt wurde nicht gefunden -- der "
        f"MORGEN-Zweig von _fmt_glance nutzt offenbar nicht tz_morgen:\n{body}"
    )


# ══════════════════════ AC-5: Sommerzeit-Wechseltage ══════════════════════


@pytest.mark.parametrize(
    "wechseltag, punkte_utc, erwartete_lokalzeiten, abfrage_utc",
    [
        pytest.param(
            date(2026, 3, 29),
            [
                datetime(2026, 3, 29, 0, 30, tzinfo=timezone.utc),
                datetime(2026, 3, 29, 1, 30, tzinfo=timezone.utc),
                datetime(2026, 3, 29, 2, 0, tzinfo=timezone.utc),
            ],
            ["01:30", "03:30", "04:00"],
            datetime(2026, 3, 29, 12, 0, tzinfo=timezone.utc),
            id="fruehjahr-luecke-23h",
        ),
        pytest.param(
            date(2026, 10, 25),
            [
                datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc),
                datetime(2026, 10, 25, 1, 30, tzinfo=timezone.utc),
                datetime(2026, 10, 25, 2, 0, tzinfo=timezone.utc),
            ],
            ["02:30", "02:30", "03:00"],
            datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc),
            id="herbst-doppelstunde-25h",
        ),
    ],
)
def test_ac5_sommerzeit_wechseltage_zeigen_die_korrekte_ortsstunde(
    wechseltag, punkte_utc, erwartete_lokalzeiten, abfrage_utc,
):
    """AC-5.

    GIVEN eine Korsika-Tour (Europe/Paris) hat Wegpunkte rund um einen
          Sommerzeit-Wechseltag -- 29.03. (Luecke, Ortstag 23h) oder 25.10.
          (Doppelstunde, Ortstag 25h),
    WHEN  ``timeline_heute`` abgefragt wird,
    THEN  zeigt jede 🕐-Zeile die korrekte Ortsstunde -- geprueft auf die
          exakte %H:%M-Zeichenkette JEDER Zeile (ADR-0044), nicht nur die
          Zeilenzahl. Am 25.10. muss "02:30" ZWEIMAL erscheinen (echte
          Doppelstunde), nicht dedupliziert.
    """
    with freeze_time(abfrage_utc):
        offsets = {p.astimezone(ZoneInfo(KORSIKA_ZONE)).utcoffset() for p in punkte_utc}
        assert len(offsets) == 2, (
            f"Testaufbau: die Wegpunkte muessen VOR und NACH dem Sommerzeit-"
            f"Wechsel liegen (zwei UTC-Offsets), gesehen: {offsets}"
        )
        trip = _trip(f"ac5-{wechseltag.isoformat()}", [wechseltag], WP_KORSIKA)
        save_trip(trip)
        _save_snapshot(trip.id, [_seg(t, WP_KORSIKA, seg_id=i) for i, t in enumerate(punkte_utc)])

        body = _befehl(trip, "### query: timeline_heute", abfrage_utc).confirmation_body

    beobachtete_zeilen = [ln for ln in body.splitlines() if ln.startswith("🕐 ")]
    beobachtete_zeiten = [ln.split(" ", 1)[1].split(" ", 1)[0] for ln in beobachtete_zeilen]
    assert beobachtete_zeiten == erwartete_lokalzeiten, (
        f"AC-5 ({wechseltag:%d.%m.}): erwartete Ortsstunden {erwartete_lokalzeiten}, "
        f"beobachtet {beobachtete_zeiten} (rohe UTC-Zeiten waeren "
        f"{[t.strftime('%H:%M') for t in punkte_utc]}).\n{body}"
    )


# ══════════════════════ AC-6: Parameter schlaegt die Systemuhr ══════════════════════
#
# Vorlage: tests/tdd/test_befehlspfade_folgen_ortszone.py:517-670 (Adversary-
# Befund F001 aus S5a: "Parameter behalten, im Rumpf ignorieren"). Anders als
# dort (wo `date.today()`/`datetime.now()` schon HEUTE aufgerufen wird)
# nutzt `_handle_query` bereits `received_at` -- der aktuelle Fehler ist "roher
# UTC-Tag statt Ortstag", nicht "ignoriert den Parameter".
#
# 🔴 Nachbesserung (PO-Review): die urspruengliche Systemuhr (20.08. 12:00Z,
# Ortstag Korsika 20.08.) fiel zufaellig mit dem ROHEN UTC-Tag von NACHTS_UTC
# (ebenfalls 20.08.) zusammen -- zwei verschiedene Fehlerursachen ("liest die
# Systemuhr" vs. "faellt in den heutigen Ist-Zustand zurueck") erzeugten
# dieselbe Ausgabe, der Test war damit eine Dublette von AC-2 statt eigen-
# staendig aussagekraeftig. Die neue Systemuhr (18.08. 12:00Z, Ortstag
# Korsika 18.08.) traegt einen Ortstag, der sich von BEIDEN unterscheidet:
# vom Ortstag des Parameters (21.08.) UND von dessen rohem UTC-Tag (20.08.).
# Die Drei-Wege-Trennung ist PFLICHT-Vorbedingung im Testkoerper selbst,
# nicht nur ein Kommentar.

_AC6_SYSTEMUHR = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)   # Ortstag Korsika 18.08, kein Mismatch


def _ac6_setup_und_frage(trip_id: str, body_cmd: str) -> "frozenset[str]":
    trip = _trip(trip_id, [D20, D21, D22, D23], WP_KORSIKA)
    save_trip(trip)
    _save_snapshot(trip.id, [
        _seg(datetime(2026, 8, 21, 10, 0, tzinfo=timezone.utc), WP_KORSIKA, seg_id=1),
        _seg(datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc), WP_KORSIKA, seg_id=2),
    ])
    body = _befehl(trip, body_cmd, NACHTS_UTC).confirmation_body
    return _daten_in_kopfzeile(body)


_DATUM_RE = re.compile(r"\((\d{2}\.\d{2})\)")


def _daten_in_kopfzeile(body: str) -> "frozenset[str]":
    """Alle 'DD.MM'-Datumsangaben in Klammern im Antworttext."""
    return frozenset(_DATUM_RE.findall(body))


def _erwartete_daten(rollen: tuple[str, ...], heute: date, morgen: date) -> "frozenset[str]":
    """Formatiert die als 'heute'/'morgen' erwarteten Kopfzeilen-Daten fuer
    genau die Rollen, die das jeweilige Kommando zeigt (glance zeigt beide,
    die anderen drei genau eine)."""
    werte = {"heute": heute, "morgen": morgen}
    return frozenset(f"{werte[r]:%d.%m}" for r in rollen)


@pytest.mark.parametrize("trip_id, body_cmd, rollen", [
    pytest.param("ac6-glance", "### query: glance", ("heute", "morgen"), id="glance"),
    pytest.param("ac6-gewitter", "### query: heute_gewitter", ("heute",), id="heute_gewitter"),
    pytest.param("ac6-tl-heute", "### query: timeline_heute", ("heute",), id="timeline_heute"),
    pytest.param("ac6-tl-morgen", "### query: timeline_morgen", ("morgen",), id="timeline_morgen"),
])
def test_ac6_vier_kommandos_folgen_dem_parameter_nicht_der_systemuhr(trip_id, body_cmd, rollen):
    """AC-6.

    GIVEN freeze_time(_AC6_SYSTEMUHR) ist aktiv UND gleichzeitig wird
          received_at = NACHTS_UTC uebergeben -- Systemuhr-Ortstag, Parameter-
          Ortstag UND der ROHE UTC-Tag des Parameters liegen auf DREI
          verschiedenen Tagen,
    WHEN  eine der vier Query-Kommandos verarbeitet wird,
    THEN  folgt das Ergebnis dem ORTSTAG des Parameters -- weder der
          eingefrorenen Systemuhr noch (der heute noch beobachtbare
          Ist-Zustand) dem rohen UTC-Tag des Parameters.

    Drei-Wege-Vorbedingung: erwartet_parameter, erwartet_systemuhr und
    erwartet_roh_utc muessen PAARWEISE verschieden sein -- sonst kann der
    Test zwei verschiedene Fehlerursachen ("liest die Systemuhr" vs. "faellt
    auf den unreparierten roh-UTC-Ist-Zustand zurueck") nicht auseinander-
    halten.
    """
    heute_param = NACHTS_UTC.astimezone(ZoneInfo(KORSIKA_ZONE)).date()
    heute_uhr = _AC6_SYSTEMUHR.astimezone(ZoneInfo(KORSIKA_ZONE)).date()
    heute_roh = NACHTS_UTC.date()

    erwartet_parameter = _erwartete_daten(rollen, heute_param, heute_param + timedelta(days=1))
    erwartet_systemuhr = _erwartete_daten(rollen, heute_uhr, heute_uhr + timedelta(days=1))
    erwartet_roh_utc = _erwartete_daten(rollen, heute_roh, heute_roh + timedelta(days=1))

    assert len({erwartet_parameter, erwartet_systemuhr, erwartet_roh_utc}) == 3, (
        "Testaufbau nicht trennscharf: Parameter-, Systemuhr- und Roh-UTC-"
        "Erwartung muessen PAARWEISE verschieden sein, sonst kann der Test "
        "nicht zwischen 'liest die Systemuhr' und 'faellt auf den rohen "
        f"UTC-Tag zurueck' unterscheiden (parameter={erwartet_parameter!r}, "
        f"systemuhr={erwartet_systemuhr!r}, roh_utc={erwartet_roh_utc!r})"
    )

    with freeze_time(_AC6_SYSTEMUHR):
        assert heute_uhr != heute_param, (
            f"Testaufbau: Systemuhr ({heute_uhr}) und Parameter ({heute_param}) "
            "muessen auf verschiedene ORTSTAGE fallen"
        )
        assert datetime.now(tz=timezone.utc) == _AC6_SYSTEMUHR, (
            "Testaufbau: freeze_time greift nicht, die Systemuhr steht auf "
            f"{datetime.now(tz=timezone.utc).isoformat()}"
        )
        beobachtet = _ac6_setup_und_frage(trip_id, body_cmd)

    hinweis = ""
    if beobachtet == erwartet_systemuhr:
        hinweis = (
            f"\n  Das ist GENAU das Ergebnis zur eingefrorenen Systemuhr "
            f"({heute_uhr:%d.%m.%Y}) -- der Pruefling liest die Systemuhr "
            "statt des Parameters."
        )
    elif beobachtet == erwartet_roh_utc:
        hinweis = (
            f"\n  Das ist GENAU der heutige Ist-Zustand: der Pruefling nutzt "
            f"zwar den Parameter, aber dessen ROHEN UTC-Tag "
            f"({heute_roh:%d.%m.%Y}) statt des Ortstags (ADR-0044 hier noch "
            "nicht angewendet)."
        )
    assert beobachtet == erwartet_parameter, (
        f"AC-6: das Ergebnis folgte nicht dem Ortstag des uebergebenen "
        f"Zeitpunkts.\n"
        f"  uebergeben:      {NACHTS_UTC.isoformat()} (Ortstag {heute_param:%d.%m.%Y}, "
        f"roher UTC-Tag {heute_roh:%d.%m.%Y})\n"
        f"  Systemuhr:       {_AC6_SYSTEMUHR.isoformat()} (Ortstag {heute_uhr:%d.%m.%Y})\n"
        f"  erwartet:        {sorted(erwartet_parameter)}\n"
        f"  beobachtet:      {sorted(beobachtet)}{hinweis}"
    )


# ══════════════════════ AC-7: Rueckgabe-Zieltag ══════════════════════


def test_ac7_fehlertext_nennt_den_tatsaechlich_benutzten_zieltag():
    """AC-7.

    GIVEN eine Nachricht wird EMPFANGEN um 23:00 Ortszeit (Ortstag 20.08.),
          aber die VERARBEITUNG laeuft erst um 03:00 Ortszeit des naechsten
          Tages (Ortstag 21.08.) -- eine reale Verzoegerung, die den vom
          Aufrufer aus `received_at` geratenen Zieltag (20.08.) vom
          TATSAECHLICH von `_get_target_date()` (Systemuhr zum
          Ausfuehrungszeitpunkt) benutzten Zieltag (21.08.) trennt,
    WHEN  ``send_on_demand_report()`` direkt aufgerufen wird UND ueber den
          vollen Befehlspfad (### heute) der Fehlertext gerendert wird,
    THEN  traegt das zurueckgegebene ``OnDemandErgebnis.zieltag`` den
          TATSAECHLICH benutzten Tag (21.08.), und der Fehlertext nennt
          GENAU dieses Datum -- nicht das vom Aufrufer geratene (20.08.).

    Der Typ ``OnDemandErgebnis`` existiert noch nicht -> dieser Test ist
    zulaessig per ``AttributeError`` rot (Spec-Vorgabe): ``send_on_demand_
    report()`` liefert heute einen bloßen String, ``"no_stage".outcome``
    wirft ``AttributeError``.
    """
    empfangen = datetime(2026, 8, 20, 21, 0, tzinfo=timezone.utc)     # 23:00 Korsika, Ortstag 20.08
    verarbeitet = datetime(2026, 8, 21, 1, 0, tzinfo=timezone.utc)    # 03:00 Korsika, Ortstag 21.08
    assert empfangen.astimezone(ZoneInfo(KORSIKA_ZONE)).date() == D20, (
        "Testaufbau: Empfangszeitpunkt muss auf Ortstag 20.08 fallen"
    )
    assert verarbeitet.astimezone(ZoneInfo(KORSIKA_ZONE)).date() == D21, (
        "Testaufbau: Verarbeitungszeitpunkt muss auf Ortstag 21.08 fallen -- "
        "sonst gibt es keine Luecke zwischen Empfang und Verarbeitung"
    )

    trip = _trip("ac7-zieltag", [D20], WP_KORSIKA)
    save_trip(trip)

    with freeze_time(verarbeitet):
        assert datetime.now(tz=timezone.utc) == verarbeitet, (
            "Testaufbau: freeze_time greift nicht"
        )
        direkt = TripReportSchedulerService(user_id="default").send_on_demand_report(
            trip, "morning",
        )
        assert direkt.outcome == "no_stage", (
            f"Testaufbau: erwartet 'no_stage' (keine Etappe am Ortstag "
            f"{D21:%d.%m.%Y}), beobachtet {direkt!r}"
        )
        assert direkt.zieltag == D21, (
            f"AC-7: OnDemandErgebnis.zieltag muss der TATSAECHLICH benutzte "
            f"Ortstag sein ({D21:%d.%m.%Y}), beobachtet {direkt!r}"
        )

        ergebnis = _befehl(trip, "### heute", empfangen)

    assert ergebnis.success is True, ergebnis.confirmation_body
    assert "(21.08.2026)" in ergebnis.confirmation_body, (
        "AC-7: der Fehlertext muss den TATSAECHLICH von send_on_demand_report "
        "benutzten Zieltag (21.08., Ortstag zum Verarbeitungszeitpunkt) "
        "nennen, nicht das vom Aufrufer aus dem Empfangszeitpunkt geratene "
        f"Datum (20.08.).\n{ergebnis.confirmation_body!r}"
    )
    assert "(20.08.2026)" not in ergebnis.confirmation_body, (
        "AC-7: der Fehlertext zeigt noch das vom Aufrufer geratene, falsche "
        f"Datum (20.08.):\n{ergebnis.confirmation_body!r}"
    )


# ══════════════════════ AC-8: Anker-Schluessel ══════════════════════


def test_ac8_anker_traegt_den_ortstag_und_ist_als_geometrie_ladbar():
    """AC-8.

    GIVEN eine Tour im Mismatch-Fenster hat noch keinen ladbaren
          Wetter-Snapshot,
    WHEN  ``_handle_query`` daraufhin ``_fetch_and_save_snapshot`` ausloest
          (echter Fetch ueber die autouse-``GZ_TEST_FIXTURE_DIR``, kein
          Mock),
    THEN  traegt die geschriebene Ankerdatei ``target_date`` = Ortstag D21
          (nicht UTC-Tag D20) -- und zwar genau den Tag, den der Alarm-Pfad
          als "heute" dieser Tour ansieht --, und sie ist ladbar.

    Frueher indirekt gemessen ueber ``_get_cached_weather(...,
    tagesgleicher_anker_noetig=True) is not None``. Das traegt seit #1699
    nicht mehr: ein Anker aus einer reinen ABFRAGE wird im Abweichungs-Pfad
    jetzt mit ``reason="not_briefing_backed"`` abgelehnt -- unabhaengig von
    seinem Datum und ausdruecklich gewollt. Wer hier landet, sucht also
    vergeblich nach ``wrong_day``. Der Tagesbezug wird deshalb DIREKT
    gelesen, und dass die #1661-Datumspruefung nichts zu beanstanden haette,
    zeigt der Vergleich mit ``trip_local_today`` -- genau der Groesse, gegen
    die sie prueft.
    """
    with freeze_time(NACHTS_UTC):
        _anker(NACHTS_UTC, KORSIKA_ZONE, D21)
        trip = Trip(id="ac8-anker", name="ac8-anker", stages=[
            _stage_mit_zwei_wegpunkten("S1", D21, WP_KORSIKA),
            _stage_mit_zwei_wegpunkten("S2", D22, WP_KORSIKA),
        ])
        save_trip(trip)

        ergebnis = _befehl(trip, "### query: glance", NACHTS_UTC)
        assert ergebnis.success is True, ergebnis.confirmation_body

        geometrie = TripAlertService(user_id="default")._get_cached_weather(
            trip, tagesgleicher_anker_noetig=False, now_utc=NACHTS_UTC,
        )
        ortstag = trip_local_today(trip, NACHTS_UTC)

    ankertag = WeatherSnapshotService(user_id="default").load_target_date("ac8-anker")
    assert ankertag == D21, (
        "AC-8: der von _fetch_and_save_snapshot geschriebene Anker muss den "
        f"ORTSTAG {D21.isoformat()} tragen, nicht den UTC-Tag der Nachricht "
        f"({NACHTS_UTC.date().isoformat()}); gelesen: {ankertag}"
    )
    assert ankertag == ortstag, (
        "AC-8: der Tagesbezug muss dem entsprechen, was der Alarm-Pfad als "
        "'heute' dieser Tour ansieht -- sonst verwuerfe die #1661-Pruefung ihn "
        f"mit reason=wrong_day. Anker {ankertag}, Ortstag {ortstag}"
    )
    assert geometrie is not None, (
        "AC-8: die Ankerdatei muss ladbar sein -- der amtliche Pfad liest sie "
        "als Geometrie (dort greift die #1699-Herkunftspruefung bewusst nicht)"
    )


# ══════════════════════ AC-11: ADR-0044-Restliste ist aktuell ══════════════════════

# doc-compliance-test

_AC11_NAMEN = (
    "_show_status", "_show_now", "command_date",
    "inbound_telegram_reader.py", "_handle_query",
)


def test_ac11_adr_restliste_ist_aktuell():
    """AC-11, doc-compliance-test.

    # doc-compliance-test: prueft eine im ADR GEMACHTE Zusicherung (die
    Restliste "Noch nicht umgesetzt"), weil AC-11 der Spec ausdruecklich
    einen Doku-Abgleich verlangt -- kein Ersatz fuer einen Verhaltensnachweis
    (das sind AC-1 bis AC-8 oben, ueber den Produktionspfad).

    GIVEN die Restliste "Noch nicht umgesetzt" nennt fuenf Stellen, die
          laengst geliefert sind (_show_status, _show_now, command_date,
          inbound_telegram_reader.py aus #1727 S5a; _handle_query aus dieser
          Scheibe),
    WHEN  diese Scheibe live geht,
    THEN  stehen alle fuenf NICHT MEHR unterhalb "Noch nicht umgesetzt", und
          _handle_query steht unter "Umgesetzt".
    """
    text = _ADR_0044.read_text(encoding="utf-8")

    ueberschrift = "### Noch nicht umgesetzt"
    assert ueberschrift in text, f"AC-11: Ueberschrift {ueberschrift!r} fehlt im ADR"
    _, _, rest = text.partition(ueberschrift)
    rest_bis_naechster_abschnitt = rest.split("\n## ", 1)[0]

    verbliebene = [n for n in _AC11_NAMEN if n in rest_bis_naechster_abschnitt]
    assert not verbliebene, (
        f"AC-11: die folgenden Namen stehen noch unter {ueberschrift!r}, "
        f"obwohl sie geliefert sind: {verbliebene}"
    )

    umgesetzt_teil, _, _ = text.partition(ueberschrift)
    assert "_handle_query" in umgesetzt_teil, (
        "AC-11: '_handle_query' muss unter 'Umgesetzt' auftauchen"
    )
