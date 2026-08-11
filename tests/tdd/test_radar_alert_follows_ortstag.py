"""TDD RED — Issue #1697: Alarm-Pfad folgt dem Ortstag der Tour, nicht der
Serveruhr (Kette A, ``TripAlertService.check_radar_alerts``).

SPEC: docs/specs/modules/fix_1697_ortstag_statt_servertag.md (AC-1 … AC-5)

RED-Grund heute (gemessen):
- ``check_radar_alerts()`` bestimmt "welcher Tag ist heute" ueber
  ``date_type.today()`` (Serveruhr) statt ueber die Ortszeit der Tour
  (``services.trip_day.trip_local_today`` — Modul existiert noch nicht).
  Weicht Ortsdatum und Serverdatum voneinander ab, findet
  ``convert_trip_to_segments()`` keine Etappe -> leere Segmentliste ->
  ``continue`` -> 0 Nowcast-Abrufe (AC-1/AC-3/AC-5-Symptom).
- ``check_radar_alerts()`` hat KEINEN Horizont-Guard vor dem Nowcast-Abruf
  (``NOWCAST_HORIZON_MIN`` kommt in ``trip_alert.py`` nicht vor) -> ein
  Segment, das erst in > 60 Minuten beginnt, loest trotzdem einen Abruf aus
  (AC-4-Symptom).

AC-2 ist ein Bestandsschutz-Test (analog #818 AC-3/AC-5/AC-7 — "Guard-Tests,
vor Implementierung bereits gruen"): ausserhalb der 22:00-00:00-UTC-Randzeit
liefern alte und neue Formel fuer Korsika (UTC+2) dasselbe Ergebnis, der
Test ist also schon heute gruen und bleibt es nach der Umstellung.

Teilungsregel: Trip-Bau, Persistenz und die Nowcast-DI-Naht kommen aus dem
BESTEHENDEN geteilten Helfer ``tests/helpers/nowcast_gate_fixtures.py``
(``make_trip``/``trip_stage``/``save_trip``/``fresh_uid``/
``CountingFrameSource``/``radar_service``/``reset_radar_cache``/
``settings_email_only``) statt lokal nachgebaut zu werden — ``make_trip``
wurde fuer #1697 additiv um Etappen-Datum/Koordinaten/Ankunftszeiten/eine
zweite Etappe erweitert (Defaults bit-identisch zum bisherigen Verhalten,
belegt per Testlauf der bestehenden Aufrufer, s. Commit-Historie). Nur der
Briefing-Schnappschuss-Schreiber (``_write_briefing_snapshot``) ist neu und
bleibt lokal — kein Pendant im geteilten Helfer.

Testpolitik (CLAUDE.md "Test-Politik: Zwei Schichten"):
- Kein Mock-Theater: kein ``Mock()``/``patch()``/``MagicMock``. Der
  Nowcast-Abruf laeuft ueber die ECHTE DI-Naht
  ``RadarNowcastService(frame_source=...)`` (Konstruktor-Parameter
  ``TripAlertService(radar_service=...)``); ``CountingFrameSource``
  protokolliert jeden Aufruf mit echten Koordinaten und liefert echte
  ``RadarFrame``-Objekte (``wet_frames()``) — kein Live-Netz, kein
  monkeypatch auf Klassenebene.
- Wirkung ueber Koordinaten, nicht ueber einen Alarm-Zaehler (Nachweis-
  Strategie der Spec): ein Zaehler haette eine Falsch-Ortung (falsches
  Segment, richtiger Alarm) nie bemerkt.
- 🔴 Radar-Cache ist Prozess-Singleton mit TTL 300 s — unter gestellter Uhr
  laeuft er nie ab. Jeder Test, der ueber die DI-Naht Aufrufe zaehlt, ruft
  deshalb ``reset_radar_cache()`` VOR dem Aufbau seiner eigenen
  ``CountingFrameSource``, sonst misst ein zweiter Test an denselben
  Koordinaten einen Cache-Treffer statt der Segmentwahl.
- Trip-Persistenz per ``save_trip()`` (aus dem geteilten Helfer), NICHT
  ``Trip(...).save()`` — ``save_trip()`` umgeht Naismith-Compute-on-Save
  (#802), das die exakt gesetzten ``arrival_calculated``-Werte
  ueberschreiben wuerde.
- Uhr: ``freeze_time`` (freezegun). Isolation: ``tests/conftest.py::
  _isolate_data_root`` (autouse, #1133) — keine manuelle Aufraeumung noetig.

Erweitert 2026-08-11 (Issue #1667 Scheibe S3, SPEC:
docs/specs/modules/fix_1667_s3_tagesuebergreifende_segmente.md) um die
tagesuebergreifende Segment-Auswahl — eigener Abschnitt am Dateiende, dieselben
Helfer, dieselbe Nachweis-Strategie (Koordinaten statt Alarm-Zaehler).

Ausfuehrung:
    uv run pytest tests/tdd/test_radar_alert_follows_ortstag.py -v \
        --disable-socket --allow-hosts=127.0.0.1
"""
from __future__ import annotations

import json
import uuid
from datetime import date as date_type
from datetime import datetime, timedelta, timezone

import pytest
from freezegun import freeze_time

from app.trip import Trip
from services.trip_alert import TripAlertService
from services.trip_segments import convert_trip_to_segments, resolve_current_segment

from tests.helpers.nowcast_gate_fixtures import (
    CountingFrameSource,
    fresh_uid,
    make_trip,
    radar_service,
    reset_radar_cache,
    save_trip,
    settings_email_only,
    trip_stage,
)

# Pacific/Auckland (UTC+12 im August, keine Sommerzeit dort im Winter) —
# AC-1/AC-5: Ortsdatum weicht vom Serverdatum ab.
AUCKLAND_LAT, AUCKLAND_LON = -36.8485, 174.7633
# Europe/Paris (UTC+2 im Sommer) — AC-2/AC-3: die 22:00-00:00-UTC-Randzeit.
CORSICA_LAT, CORSICA_LON = 42.20, 9.10
# Atlantic/Reykjavik (UTC+0 ganzjaehrig) — AC-4: Horizont-Guard ohne
# Zeitzonen-Rechnung, DI-Naht ueber exakte Minutenabstaende.
REYKJAVIK_LAT, REYKJAVIK_LON = 64.1466, -21.9426
# America/Los_Angeles (UTC-7 im August) — F002: NEGATIVER Versatz, das
# Serverdatum laeuft dem Ortstag VORAUS (date.today() = Ortstag D + 1) —
# genau die Richtung, in der die Ueberwachung etwas VERLIERT (Tour gilt
# faelschlich als abgelaufen).
LOS_ANGELES_LAT, LOS_ANGELES_LON = 34.0522, -118.2437


def _write_briefing_snapshot(
    user_id: str, trip_id: str, target_date: date_type, segment_id,
    onset_hour_naive: datetime, precip_mm: float,
) -> None:
    """Minimaler Briefing-Snapshot mit EINER Regen-Stunde am Onset — Format
    entspricht ``WeatherSnapshotService.save_dated()`` (naive UTC-Zeitstempel,
    Muster ``tests/tdd/test_issue_818_radar_briefing_integration.py::
    _write_snapshot``, hier mit explizitem ``target_date``-Parameter statt
    ``date_type.today()`` — genau das ist der Streitpunkt von AC-5). Neu,
    kein Pendant im geteilten Helfer (der kennt keine Briefing-Snapshots)."""
    from app.loader import get_snapshots_dir

    snapshots_dir = get_snapshots_dir(user_id)
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    hourly = [
        {
            "ts": (onset_hour_naive + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%S"),
            "precip_1h_mm": precip_mm if h == 0 else 0.0,
        }
        for h in range(-2, 3)
    ]
    segment_entry = {
        "segment_id": segment_id,
        "start_time": (onset_hour_naive - timedelta(hours=1)).isoformat(),
        "end_time": (onset_hour_naive + timedelta(hours=2)).isoformat(),
        "start_lat": 0.0, "start_lon": 0.0, "start_elevation_m": 0.0,
        "start_distance_from_start_km": 0.0,
        "end_lat": 0.0, "end_lon": 0.0, "end_elevation_m": 0.0,
        "end_distance_from_start_km": 0.0,
        "distance_km": 0.0, "ascent_m": 0.0, "descent_m": 0.0,
        "duration_hours": 3.0,
        "aggregated": {},
        "hourly": hourly,
    }
    snapshot = {
        "trip_id": trip_id,
        "target_date": target_date.isoformat(),
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
        "provider": "openmeteo",
        "segments": [segment_entry],
    }
    path = snapshots_dir / f"{trip_id}_{target_date.isoformat()}.json"
    path.write_text(json.dumps(snapshot, indent=2))


def _aktives_segment(segments, now_utc):
    """Spiegelt die Segment-Auswahl aus ``check_radar_alerts()`` 1:1 (aktives
    ODER naechstes Segment, #822) — als lokal hinterlegte Referenz fuer
    AC-2, unabhaengig vom Pruefling aufgebaut."""
    for seg in segments:
        if seg.start_time <= now_utc <= seg.end_time:
            return seg
    if segments and now_utc < segments[0].start_time:
        return segments[0]
    return None


# ══════════════════════════════════ AC-1 ══════════════════════════════════


def test_ac1_auckland_koordinatennachweis():
    """AC-1: Ortsdatum D (Auckland) weicht vom Serverdatum SD ab — der
    Nowcast-Abruf muss an den Koordinaten der D-Etappe erfolgen.

    RED-Symptom heute: ``today = date.today()`` = SD findet die D-Etappe
    nicht, ``convert_trip_to_segments()`` liefert ``[]``, der Trip wird per
    ``continue`` uebersprungen — 0 Aufrufe statt der D-Koordinaten.
    """
    from zoneinfo import ZoneInfo

    reset_radar_cache()
    frame_source = CountingFrameSource(onset_minutes=10)

    uid = fresh_uid("ac1")
    trip_id = f"trip-ac1-{uuid.uuid4().hex[:8]}"
    with freeze_time("2026-08-10T13:00:00+00:00"):
        now_utc = datetime.now(timezone.utc)
        sd = date_type.today()
        d_ort = now_utc.astimezone(ZoneInfo("Pacific/Auckland")).date()
        assert d_ort != sd, "Testvoraussetzung: Ortsdatum muss vom Serverdatum abweichen"

        trip = make_trip(trip_id, stage_date=d_ort, lat=AUCKLAND_LAT, lon=AUCKLAND_LON)
        save_trip(trip, uid)

        svc = TripAlertService(
            settings=settings_email_only(), user_id=uid, throttle_hours=2,
            radar_service=radar_service(frame_source),
        )
        svc.check_radar_alerts()

    assert frame_source.calls, (
        f"AC-1: Am Ortsdatum {d_ort} (Serverdatum {sd}) haette der Nowcast-"
        f"Abruf an den Koordinaten der D-Etappe erfolgen muessen — "
        f"calls={frame_source.calls!r}. RED: `today = date.today()` findet "
        "die D-Etappe nicht, der Trip wird uebersprungen."
    )
    lat, lon = frame_source.calls[0]
    assert lat == pytest.approx(AUCKLAND_LAT) and lon == pytest.approx(AUCKLAND_LON), (
        f"AC-1: Abruf-Koordinaten {frame_source.calls[0]!r} passen nicht zur "
        f"D-Etappe ({AUCKLAND_LAT}, {AUCKLAND_LON})"
    )


# ══════════════════════════════════ AC-2 ══════════════════════════════════


@pytest.mark.parametrize("hour_utc", list(range(0, 22)))
def test_ac2_bestandsschutz_korsika_ausserhalb_der_randzeit(hour_utc):
    """AC-2 (Bestandsschutz): Ausserhalb 22:00-00:00 UTC muss das gewaehlte
    Segment eines Korsika-Trips identisch zur ALTEN ``date.today()``-Formel
    bleiben — Korsika (UTC+2) wechselt den Ortstag nur in dieser Randzeit.

    Dieser Test ist — wie AC-3/AC-5/AC-7 in #818 — bereits VOR der
    Implementierung gruen (Guard-Test): fuer diese 22 Stichproben stimmen
    alte und neue Formel ueberein.

    Bewusst die GANZTAGS-Etappe (``make_trip``-Default 00:00-23:59), nicht
    die realistische 08:00-16:00-Etappe aus AC-3: nur so ist bei JEDER der
    22 Stichproben (auch morgens vor 08:00 und abends nach 16:00) ueberhaupt
    ein Segment aktiv oder "als naechstes" waehlbar — die realistische
    Etappe waere z. B. um 20:00 UTC schon laengst "alle Segmente vorbei" und
    der Bestandsschutz-Vergleich liefe ins Leere (``erwartet is None``).
    """
    reset_radar_cache()
    frame_source = CountingFrameSource(onset_minutes=10)

    uid = fresh_uid(f"ac2-{hour_utc:02d}")
    trip_id = f"trip-ac2-{uuid.uuid4().hex[:8]}"
    zeitpunkt = f"2026-08-10T{hour_utc:02d}:00:00+00:00"
    with freeze_time(zeitpunkt):
        now_utc = datetime.now(timezone.utc)
        alte_formel_heute = date_type.today()

        trip = make_trip(trip_id, stage_date=alte_formel_heute, lat=CORSICA_LAT, lon=CORSICA_LON)
        save_trip(trip, uid)

        referenz_segmente = convert_trip_to_segments(trip, alte_formel_heute)
        erwartet = _aktives_segment(referenz_segmente, now_utc)
        assert erwartet is not None, (
            f"Testvoraussetzung bei {zeitpunkt}: die alte Formel muss ein "
            "aktives Segment liefern"
        )

        svc = TripAlertService(
            settings=settings_email_only(), user_id=uid, throttle_hours=2,
            radar_service=radar_service(frame_source),
        )
        svc.check_radar_alerts()

    assert frame_source.calls, (
        f"AC-2 bei {zeitpunkt}: kein Nowcast-Abruf erfolgt, erwartet war ein "
        f"aktives Segment an ({erwartet.start_point.lat}, {erwartet.start_point.lon})"
    )
    lat, lon = frame_source.calls[0]
    assert lat == pytest.approx(erwartet.start_point.lat) and lon == pytest.approx(erwartet.start_point.lon), (
        f"AC-2 bei {zeitpunkt}: Abruf-Koordinaten {frame_source.calls[0]!r} "
        f"weichen von der alten Formel ({erwartet.start_point.lat}, "
        f"{erwartet.start_point.lon}) ab — Bestandsschutz verletzt"
    )


# ══════════════════════════════════ AC-3 ══════════════════════════════════


def test_ac3_das_ehrliche_fenster_waehlt_die_folgetags_etappe(caplog):
    """AC-3 (Spec-Wortlaut): 22:30 UTC = 00:30 Ortszeit des FOLGETAGS auf
    Korsika. Die Etappe des Folgetags muss gewaehlt werden — fachlich
    gewollt (#822 "aktives ODER naechstes Segment"), kein Fehlerbild.

    REALISTISCHE Etappe (Start 08:00, Ankunft 16:00 Ortszeit) statt der
    Ganztags-Fixture aus AC-2: mit 00:00-23:59 wuerde der #1584-Randfall-
    Guard das Ziel-Segment des AKTUELLEN Tages bis 22:59 UTC verlaengern
    (Ankunft 23:59 Ortszeit liegt nach dem Tagesfenster-Ende -> minimales
    Fenster "Ankunft + 1 h") — um 22:30 UTC waere dann noch etwas vom
    HEUTIGEN Tag aktiv und der Test praeft die falsche Verzweigung (nicht
    "continue", sondern eine andere Etappenwahl). Nachgemessen: mit
    08:00-16:00 endet auch das Ziel-Segment des heutigen Tages um 17:00 UTC
    (Tagesfenster-Ende 19:00 Ortszeit = 17:00 UTC liegt NACH der Ankunft,
    der Randfall-Guard greift nicht) — um 22:30 UTC ist die heutige Etappe
    dann wirklich vollstaendig vorbei, genau wie das AC woertlich beschreibt.

    🔴 GREEN-Phase-Korrektur (#1697, PO-Feedback nach erster GREEN-Runde):
    die urspruengliche RED-Fassung prüfte den Etappenwechsel ueber
    ``frame_source.calls`` (ein TATSAECHLICHER Nowcast-Abruf). Das
    kollidiert nachweislich mit AC-4 (Horizont-Guard, aus DERSELBEN Spec):
    das gewaehlte Folgetags-Segment beginnt hier um 06:00 UTC — von
    22:30 UTC aus 7,5 h in der Zukunft, weit ausserhalb
    ``NOWCAST_HORIZON_MIN`` (60 min). Genau dieses Muster (samt der exakten
    "7,5 Stunden") nennt die Spec selbst als Beleg FUER AC-4 (Kontext-
    Dokument, Abschnitt "Nachgemessen und korrigiert": "...ein Segment
    abgerufen, das erst in 7,5 Stunden beginnt — fachlich sinnlos"). Ein
    Nowcast-Abruf DARF hier also nicht erfolgen; die urspruengliche
    Zusicherung war falsch, nicht bloss unguenstig formuliert.

    Positiver Beleg statt Negativ-Check: eine leere Segmentliste allein zu
    verneinen ("alle Segmente vorbei" nicht im Log) beweist nicht, DASS die
    Folgetags-Etappe gewaehlt wurde — nur, dass irgendein Segment gefunden
    wurde. Der Horizont-Guard (``check_radar_alerts()``,
    ``src/services/trip_alert.py``) nennt seit #1697 im Debug-Log den
    Startzeitpunkt des uebersprungenen Segments (#1405-Linie: was
    uebersprungen wird, wird benannt). Dieser Test extrahiert ihn aus dem
    ECHTEN Log von ``check_radar_alerts()`` und vergleicht ihn gegen den
    Start der Folgetags-Etappe — die Zusicherung sitzt damit an der Stelle,
    an der die Auswahl WIRKT (der SUT-Aufruf selbst), nicht an einer
    Nachrechnung daneben. Die separate Referenzrechnung
    (``trip_local_today`` + ``convert_trip_to_segments``) bleibt reine
    Testvoraussetzung (zeigt, was die Fixture ueberhaupt hergibt) und traegt
    keine Zusicherung ueber das Verhalten von ``check_radar_alerts()`` mehr.

    RED heute: ``today = date.today()`` bleibt auf dem AKTUELLEN Server-Tag;
    dessen Segmente sind um 22:30 UTC alle vorbei -> ``continue``
    ("alle Segmente vorbei" im Log), statt die Folgetags-Etappe zu waehlen
    (kein Log-Eintrag mit dem Start der Folgetags-Etappe).
    """
    import logging
    import re

    from services.trip_day import trip_local_today
    from services.trip_segments import convert_trip_to_segments

    reset_radar_cache()
    frame_source = CountingFrameSource(onset_minutes=10)

    uid = fresh_uid("ac3")
    trip_id = f"trip-ac3-{uuid.uuid4().hex[:8]}"
    with freeze_time("2026-08-10T22:30:00+00:00"):
        heute = date_type.today()
        folgetag = heute + timedelta(days=1)

        trip = make_trip(
            trip_id, stage_date=heute, lat=CORSICA_LAT, lon=CORSICA_LON,
            arrival_start="08:00", arrival_end="16:00",
            extra_stages=[
                trip_stage(
                    "S2", folgetag, CORSICA_LAT + 0.5, CORSICA_LON + 0.5,
                    arrival_start="08:00", arrival_end="16:00", wp_prefix="S2WP",
                ),
            ],
        )
        save_trip(trip, uid)

        # Nur TESTVORAUSSETZUNG: zeigt, was die Fixture hergibt (dieselben
        # Bausteine wie check_radar_alerts() intern, aber separat
        # aufgerufen) — trägt selbst KEINE Zusicherung über das Verhalten
        # des SUT (s. Docstring "Positiver Beleg statt Negativ-Check").
        now_utc = datetime.now(timezone.utc)
        referenz_tag = trip_local_today(trip, now_utc)
        assert referenz_tag == folgetag, (
            f"Testvoraussetzung: trip_local_today() haette {folgetag} "
            f"liefern muessen, war {referenz_tag}"
        )
        referenz_segmente = convert_trip_to_segments(trip, referenz_tag)
        assert referenz_segmente, "Testvoraussetzung: Folgetags-Etappe muss Segmente liefern"
        assert referenz_segmente[0].start_point.lat == pytest.approx(CORSICA_LAT + 0.5), (
            "Testvoraussetzung: erstes Segment der Folgetags-Etappe muss an "
            "den S2-Koordinaten liegen"
        )
        erwarteter_start = referenz_segmente[0].start_time

        svc = TripAlertService(
            settings=settings_email_only(), user_id=uid, throttle_hours=2,
            radar_service=radar_service(frame_source),
        )
        with caplog.at_level(logging.DEBUG, logger="trip_alert"):
            svc.check_radar_alerts()

    # Positiver Beleg (am SUT-Aufruf selbst, nicht an der Referenz daneben):
    # der Horizont-Guard-Log nennt den Start des uebersprungenen Segments —
    # der muss der Start der FOLGETAGS-Etappe sein, nicht "irgendein"
    # Segment und nicht die Abwesenheit von "alle Segmente vorbei".
    treffer = re.search(r"Start=(\S+)\)", caplog.text)
    assert treffer, (
        "AC-3: der Horizont-Guard-Log haette den Start des uebersprungenen "
        "Segments nennen muessen (kein Treffer fuer 'Start=...'). Entweder "
        "wurde ueberhaupt kein Segment gewaehlt (RED: `date.today()` findet "
        f"die Folgetags-Etappe nicht) oder der Log fehlt.\nLog:\n{caplog.text}"
    )
    geloggter_start = datetime.fromisoformat(treffer.group(1))
    assert geloggter_start == erwarteter_start, (
        f"AC-3: der Horizont-Guard uebersprang ein Segment mit Start "
        f"{geloggter_start.isoformat()}, erwartet war der Start der "
        f"Folgetags-Etappe {erwarteter_start.isoformat()} — vermutlich wurde "
        f"noch die Etappe von {heute} gewaehlt oder gar keine."
    )
    # AC-4 (Horizont-Guard) unterdrueckt hier zu Recht den tatsaechlichen
    # Nowcast-Abruf — das Segment beginnt 7,5 h in der Zukunft, weit
    # ausserhalb NOWCAST_HORIZON_MIN. Das ist AC-4s Aufgabe, kein AC-3-Fund.
    assert not frame_source.calls, (
        "AC-3 (Kopplung zu AC-4): das Folgetags-Segment liegt weit ausserhalb "
        "des Nowcast-Horizonts — ein tatsaechlicher Abruf waere eine "
        f"AC-4-Regression. calls={frame_source.calls!r}"
    )


# ══════════════════════════════════ AC-4 ══════════════════════════════════


def test_ac4_horizont_guard_fern_kein_abruf_nah_ein_abruf():
    """AC-4: Segment > ``NOWCAST_HORIZON_MIN`` (60 min) entfernt -> KEIN
    Nowcast-Abruf; Segment innerhalb -> genau EIN Abruf (Gegenprobe im
    selben Test — der Nah-Fall allein waere nicht diskriminierend, weil
    er auch ohne jeden Guard schon einen Abruf ausloest).

    RED heute: ``check_radar_alerts()`` hat KEINEN Horizont-Guard — der
    Fern-Fall ruft ``get_nowcast()`` trotzdem auf.
    """
    from services.radar_service import NOWCAST_HORIZON_MIN

    assert NOWCAST_HORIZON_MIN == 60, (
        f"Testvoraussetzung: NOWCAST_HORIZON_MIN muss 60 sein, war {NOWCAST_HORIZON_MIN!r}"
    )

    with freeze_time("2026-08-10T10:00:00+00:00"):
        heute = date_type.today()

        # Fern: Segment beginnt in 90 Minuten (> 60) -> kein Abruf.
        reset_radar_cache()
        frame_source_fern = CountingFrameSource(onset_minutes=10)
        uid_fern = fresh_uid("ac4-fern")
        trip_fern_id = f"trip-ac4-fern-{uuid.uuid4().hex[:8]}"
        trip_fern = make_trip(
            trip_fern_id, stage_date=heute, lat=REYKJAVIK_LAT, lon=REYKJAVIK_LON,
            arrival_start="11:30", arrival_end="15:00",
        )
        save_trip(trip_fern, uid_fern)
        TripAlertService(
            settings=settings_email_only(), user_id=uid_fern, throttle_hours=2,
            radar_service=radar_service(frame_source_fern),
        ).check_radar_alerts()

        assert frame_source_fern.calls == [], (
            "AC-4: Segment beginnt erst in 90 Minuten (> NOWCAST_HORIZON_MIN=60) "
            f"— get_nowcast() darf NICHT aufgerufen werden, war "
            f"{frame_source_fern.calls!r}. RED: check_radar_alerts() hat noch "
            "keinen Horizont-Guard."
        )

        # Nah (Gegenprobe): Segment beginnt in 30 Minuten (<= 60) -> Abruf MUSS erfolgen.
        reset_radar_cache()
        frame_source_nah = CountingFrameSource(onset_minutes=10)
        uid_nah = fresh_uid("ac4-nah")
        trip_nah_id = f"trip-ac4-nah-{uuid.uuid4().hex[:8]}"
        trip_nah = make_trip(
            trip_nah_id, stage_date=heute, lat=REYKJAVIK_LAT, lon=REYKJAVIK_LON,
            arrival_start="10:30", arrival_end="15:00",
        )
        save_trip(trip_nah, uid_nah)
        TripAlertService(
            settings=settings_email_only(), user_id=uid_nah, throttle_hours=2,
            radar_service=radar_service(frame_source_nah),
        ).check_radar_alerts()

        assert len(frame_source_nah.calls) >= 1, (
            "AC-4 (Gegenprobe): Segment beginnt in 30 Minuten (<= Horizont) — "
            f"get_nowcast() MUSS aufgerufen werden, war {frame_source_nah.calls!r}."
        )


# ══════════════════════════════════ AC-5 ══════════════════════════════════


def test_ac5_segmentwahl_und_schnappschuss_lesen_denselben_ortstag():
    """AC-5: Ortstag D (Auckland) weicht vom Serverdatum SD ab. Ein
    Briefing-Schnappschuss NUR unter D unterdrueckt den Alarm (Regen war
    angekuendigt); derselbe Schnappschuss NUR unter SD wird nicht gefunden,
    der Alarm feuert. Beweist, dass Segmentwahl UND Schnappschuss-Lesung
    denselben ``today`` benutzen (kein halbierter Umbau).

    RED heute in BEIDEN Haelften: ``today = date.today()`` = SD findet die
    D-Etappe gar nicht -> 0 Aufrufe, egal wo der Schnappschuss liegt. Die
    Unterdrueckungs-Erwartung (count == 0) ist damit heute schon zufaellig
    erfuellt (wie die Bestandsschutz-Haelfte in AC-2); die Gegenprobe
    (count >= 1) ist es NICHT und macht diesen Test rot.
    """
    from zoneinfo import ZoneInfo

    def _run(*, snapshot_under_ortsdatum: bool) -> int:
        reset_radar_cache()
        frame_source = CountingFrameSource(onset_minutes=10)
        mails: list = []

        uid = fresh_uid("ac5-supp" if snapshot_under_ortsdatum else "ac5-gegen")
        trip_id = f"trip-ac5-{uuid.uuid4().hex[:8]}"
        with freeze_time("2026-08-10T13:00:00+00:00"):
            now_utc = datetime.now(timezone.utc)
            sd = date_type.today()
            d_ort = now_utc.astimezone(ZoneInfo("Pacific/Auckland")).date()
            assert d_ort != sd, "Testvoraussetzung: Ortsdatum muss vom Serverdatum abweichen"

            trip = make_trip(trip_id, stage_date=d_ort, lat=AUCKLAND_LAT, lon=AUCKLAND_LON)
            save_trip(trip, uid)

            onset_hour_naive = (now_utc + timedelta(minutes=10)).replace(
                minute=0, second=0, microsecond=0, tzinfo=None,
            )
            snapshot_datum = d_ort if snapshot_under_ortsdatum else sd
            _write_briefing_snapshot(
                uid, trip_id, snapshot_datum, segment_id=1,
                onset_hour_naive=onset_hour_naive, precip_mm=1.2,
            )

            svc = TripAlertService(
                settings=settings_email_only(), user_id=uid, throttle_hours=2,
                radar_service=radar_service(frame_source),
                mail_sink=lambda subject, body: mails.append((subject, body)),
            )
            count = svc.check_radar_alerts()
        return count

    unterdrueckt = _run(snapshot_under_ortsdatum=True)
    assert unterdrueckt == 0, (
        "AC-5: Schnappschuss liegt unter dem ORTSTAG D mit angekuendigtem "
        f"Regen (1.2 mm) — der Alarm haette unterdrueckt werden muessen, "
        f"war count={unterdrueckt}"
    )

    feuert = _run(snapshot_under_ortsdatum=False)
    assert feuert >= 1, (
        "AC-5 (Gegenprobe): derselbe Schnappschuss liegt NUR unter dem "
        "SERVERDATUM SD — er darf dort NICHT gefunden werden (Segmentwahl "
        "und Schnappschuss-Lesung muessen denselben Ortstag D verwenden), "
        f"der Alarm haette feuern muessen, war count={feuert}. "
        "RED: heute wird ueberhaupt keine Etappe gefunden (Ortsdatum D "
        "fehlt der alten `date.today()`-Formel), der Alarm feuert nicht."
    )


# ═══════════════════ Fix-Loop F001 (Adversary, CRITICAL) ═══════════════════
#
# Der Adversary hat ``_get_cached_weather()`` (``trip_alert.py:584``, der
# DELTA-Alarm-Pfad ueber ``check_all_trips() -> _get_cached_weather() ->
# load_dated()``) unbewacht gefunden: eine Mutation, die genau diese Zeile
# von ``today = trip_local_today(trip, now_utc or datetime.now(timezone.utc))``
# auf ``today = date.today()`` zurueckdreht, liess ALLE 218 bis dahin
# gelaufenen Tests gruen (u.a. alle 26 in dieser Datei, `test_alert_anchor_
# day_guard.py`, `test_issue_823_snapshot_date_guard.py`,
# `test_issue_1088_official_alert_triggers.py`, `test_success_status_guard.py`).
# Grund: AC-5 hier oben sichert ausschliesslich ``check_radar_alerts()`` ab,
# das SEINE EIGENE ``today``-Variable benutzt (``trip_alert.py:901``) — eine
# von ZWEI unabhaengigen Aufrufstellen von ``trip_local_today()`` in Kette A.
# Die andere (der Delta-Pfad) hatte keinen Test.
#
# Wirkort ist deshalb bewusst ``_get_cached_weather()`` SELBST — nicht
# ``check_all_trips()`` mit echtem Fresh-Fetch (der braeuchte Live-Netz) —,
# analog zum bestehenden Muster ``test_alert_anchor_day_guard.py::
# cached_weather()``, das exakt dieselbe Methode fuer #1661 direkt aufruft.
# Diese Wahl beruehrt NUR den DATIERTEN Zweig (``dated = svc.load_dated(...)``
# wird sofort zurueckgegeben, wenn nicht ``None``) — der undatierte
# Rueckfall-Zweig mit ``anchor_date == today`` (#1661, ``trip_alert.py:607``)
# wird von diesem Test NICHT beruehrt: es existiert keine undatierte Datei,
# der Fund-Fall greift bereits bei ``load_dated()``. Keine Kopplungs-
# Ueberraschung zu #1661 aufgetreten.


def _wetter_mit_boe(boe_kmh: float, segment_id: str = "1"):
    """Minimaler Δ-Anker mit erkennbarem, sonst voellig beliebigem
    Boeenwert — Muster ``test_alert_anchor_day_guard.py::_wetter``. Der
    Delta-Pfad (``_get_cached_weather``) braucht nur eine ladbare
    ``SegmentWeatherData``-Liste, keine zur Trip-Etappe passende Segment-
    Geometrie (die Kopplung Segmentwahl<->Schnappschuss ist AC-5s Aufgabe,
    nicht diese hier)."""
    from app.models import (
        ForecastDataPoint,
        ForecastMeta,
        GPXPoint,
        NormalizedTimeseries,
        Provider,
        SegmentWeatherData,
        SegmentWeatherSummary,
        TripSegment,
    )

    stunde = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    punkte = [
        ForecastDataPoint(
            ts=stunde + timedelta(hours=h), t2m_c=12.0 + h,
            wind10m_kmh=boe_kmh / 2, gust_kmh=boe_kmh, precip_1h_mm=0.0,
        )
        for h in range(4)
    ]
    segment = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=AUCKLAND_LAT, lon=AUCKLAND_LON, elevation_m=500.0,
                             distance_from_start_km=0.0),
        end_point=GPXPoint(lat=AUCKLAND_LAT + 0.1, lon=AUCKLAND_LON + 0.1,
                           elevation_m=600.0, distance_from_start_km=6.0),
        start_time=stunde, end_time=stunde + timedelta(hours=4),
        duration_hours=4.0, distance_km=6.0, ascent_m=100.0, descent_m=0.0,
    )
    return SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=punkte,
        ),
        aggregated=SegmentWeatherSummary(
            gust_max_kmh=boe_kmh, wind_max_kmh=boe_kmh / 2,
            temp_max_c=15.0, temp_min_c=8.0, precip_sum_mm=0.0,
        ),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def test_f001_delta_anker_wird_unter_ortstag_gesucht_nicht_servertag():
    """F001-Fix: ``_get_cached_weather()`` (Delta-Alarm-Pfad) sucht den
    DATIERTEN Anker unter dem ORTSTAG D der Tour, nicht dem Serverdatum SD.

    Aufbau wie AC-1/AC-5 (Auckland, Ortsdatum D weicht vom Serverdatum SD
    ab, ``freeze_time("2026-08-10T13:00:00+00:00")``): Schnappschuss NUR
    unter D abgelegt -> muss gefunden werden. Gegenprobe im selben Test:
    derselbe Schnappschuss NUR unter SD -> darf NICHT gefunden werden
    (genau das waere das Verhalten der Mutation ``today = date.today()``).
    """
    from zoneinfo import ZoneInfo

    from services.weather_snapshot import WeatherSnapshotService

    def _pruefen(*, snapshot_unter_ortstag: bool):
        uid = fresh_uid("f001-anker" if snapshot_unter_ortstag else "f001-gegen")
        trip_id = f"trip-f001-{uuid.uuid4().hex[:8]}"
        with freeze_time("2026-08-10T13:00:00+00:00"):
            now_utc = datetime.now(timezone.utc)
            sd = date_type.today()
            d_ort = now_utc.astimezone(ZoneInfo("Pacific/Auckland")).date()
            assert d_ort != sd, "Testvoraussetzung: Ortsdatum muss vom Serverdatum abweichen"

            trip = make_trip(trip_id, stage_date=d_ort, lat=AUCKLAND_LAT, lon=AUCKLAND_LON)
            save_trip(trip, uid)

            snapshot_datum = d_ort if snapshot_unter_ortstag else sd
            WeatherSnapshotService(uid).save_dated(
                trip_id, snapshot_datum, [_wetter_mit_boe(200.0)],
            )

            svc = TripAlertService(
                settings=settings_email_only(), user_id=uid, throttle_hours=2,
            )
            ergebnis = svc._get_cached_weather(
                trip, tagesgleicher_anker_noetig=True, now_utc=now_utc,
            )
        return ergebnis

    gefunden = _pruefen(snapshot_unter_ortstag=True)
    assert gefunden, (
        "F001: Schnappschuss liegt unter dem ORTSTAG D — "
        "_get_cached_weather() haette ihn finden muessen. RED bei Mutation "
        "`today = date.today()`: der Anker wird unter dem SERVERDATUM SD "
        "gesucht und nicht gefunden."
    )
    assert gefunden[0].aggregated.gust_max_kmh == pytest.approx(200.0), (
        f"F001: gefundener Anker traegt den falschen Boeenwert: "
        f"{gefunden[0].aggregated.gust_max_kmh!r}"
    )

    nicht_gefunden = _pruefen(snapshot_unter_ortstag=False)
    assert nicht_gefunden is None, (
        "F001 (Gegenprobe): derselbe Schnappschuss liegt NUR unter dem "
        "SERVERDATUM SD — er darf unter dem korrekt aufgeloesten Ortstag D "
        f"NICHT gefunden werden. Zurueckgekommen: {nicht_gefunden!r}. Das "
        "waere genau das Verhalten der Mutation `today = date.today()`."
    )


# ═══════════════════ Fix-Loop F002 (Adversary, HIGH) ═══════════════════
#
# Der Adversary hat ``check_all_trips()`` (``trip_alert.py:404`` — eigene
# ``today``-Zuweisung je Trip; einziger Verbraucher ``:447`` der Ablauf-
# Filter ``trip.end_date < today``) unbewacht gefunden: die Mutation
# ``today = trip_local_today(trip, now_utc)`` -> ``today = date.today()``
# an DIESER Stelle liess den gesamten bisherigen #1697-Bestand (266 Tests,
# inkl. F001) gruen — F001 sichert nur ``_get_cached_weather()``s EIGENE
# ``today``-Berechnung ab (``trip_alert.py:584``), nicht die von
# ``check_all_trips()`` unabhaengig berechnete.
#
# Hauptfall bewusst NEGATIVER Versatz (Los Angeles, UTC-7): das ist die
# gefaehrliche Richtung — das Serverdatum laeuft dem Ortstag VORAUS
# (``date.today()`` = Ortstag D + 1), die Tour gilt an ihrem LETZTEN
# Ortstag D deshalb faelschlich schon als abgelaufen und wird nie wieder
# geprueft (Original-Fehlerbild).
#
# Wirkort: der positive Beleg kommt NICHT aus einem vollen Alarm-Versand
# (bräuchte Live-Fresh-Fetch/amtliche Quellen, kein Netz im Testlauf) —
# sondern aus dem bestehenden Produktions-Signal
# ``_report_missing_anchor()``: ein "laufender" Trip (``start_date <= today
# <= end_date``) OHNE jeden Schnappschuss protokolliert eine ECHTE WARNUNG
# mit Trip-Kennung (``trip_alert.py:662-666``). Diese WARNUNG erscheint nur,
# wenn der Trip den Ablauf-Filter ueberhaupt passiert — sie ist damit ein
# direktes Signal DAFUER, dass ``check_all_trips()`` den Trip an diesem Tag
# noch prueft, nicht dafuer uebersprungen zu haben.


def test_f002_ablauf_filter_prueft_den_letzten_ortstag_noch(caplog):
    """F002-Fix: ``check_all_trips()`` filtert abgelaufene Touren ueber den
    ORTSTAG der Tour, nicht das Serverdatum.

    Hauptfall: Trip mit ``end_date == D`` (Ortstag, Los Angeles) unter einer
    gestellten Uhr, zu der ``date.today()`` bereits ``D+1`` waere -> der
    Trip MUSS an D noch geprueft werden (WARNUNG "obwohl die Tour laeuft"
    erscheint, statt eines stillen Ablauf-Skips).

    Gegenprobe im selben Test: ein Trip, dessen ``end_date`` D-1 ist (nach
    Ortstag TATSAECHLICH abgelaufen), erzeugt KEINE solche WARNUNG — sonst
    prueft der Test nur "irgendetwas passiert", nicht den Filter selbst.

    RED bei Mutation ``today = date.today()`` an ``trip_alert.py:404``: SD
    (Serverdatum) = D+1, der Hauptfall-Trip mit ``end_date=D`` faellt durch
    ``trip.end_date < today`` (``D < D+1``) und wird VOR
    ``_get_cached_weather()`` per ``continue`` uebersprungen — keine
    WARNUNG.
    """
    import logging
    from zoneinfo import ZoneInfo

    def _lauf(*, end_date_ist_heute: bool):
        uid = fresh_uid("f002-heute" if end_date_ist_heute else "f002-abgelaufen")
        trip_id = f"trip-f002-{uuid.uuid4().hex[:8]}"
        with freeze_time("2026-08-11T05:00:00+00:00"):
            now_utc = datetime.now(timezone.utc)
            sd = date_type.today()
            d_ort = now_utc.astimezone(ZoneInfo("America/Los_Angeles")).date()
            assert d_ort == sd - timedelta(days=1), (
                "Testvoraussetzung: Serverdatum muss dem LA-Ortstag genau "
                "einen Tag vorauslaufen"
            )

            stage_datum = d_ort if end_date_ist_heute else d_ort - timedelta(days=1)
            trip = make_trip(
                trip_id, stage_date=stage_datum,
                lat=LOS_ANGELES_LAT, lon=LOS_ANGELES_LON,
            )
            assert trip.end_date == stage_datum, (
                "Testvoraussetzung: end_date muss dem einzigen Etappentag "
                "entsprechen"
            )
            save_trip(trip, uid)

            svc = TripAlertService(settings=settings_email_only(), user_id=uid)
            with caplog.at_level(logging.DEBUG, logger="trip_alert"):
                svc.check_all_trips()
        return caplog.text

    log_heute = _lauf(end_date_ist_heute=True)
    assert "obwohl die Tour laeuft" in log_heute, (
        "F002: Trip mit end_date == Ortstag D haette den Ablauf-Filter "
        "passieren muessen (WARNUNG 'obwohl die Tour laeuft' erwartet). "
        f"Log:\n{log_heute}"
    )
    caplog.clear()

    log_abgelaufen = _lauf(end_date_ist_heute=False)
    assert "obwohl die Tour laeuft" not in log_abgelaufen, (
        "F002 (Gegenprobe): ein tatsaechlich abgelaufener Trip (end_date == "
        "D-1) darf NICHT als 'laufend' behandelt werden — sonst ist der "
        f"Ablauf-Filter selbst wirkungslos. Log:\n{log_abgelaufen}"
    )


# ════════ Issue #1667 S3 — tagesuebergreifende Segment-Auswahl (AC-1…AC-5) ═══════
#
# SPEC: docs/specs/modules/fix_1667_s3_tagesuebergreifende_segmente.md
#
# ``check_radar_alerts()`` fragt genau EINEN Kalendertag ab (``trip_alert.py:911-913``).
# Eine Etappe mit Abendstart und Ankunft nach Mitternacht hat seit S2 ein
# Ziel-Segment bis ins Tagesfenster-Ende des FOLGETAGS — ``get_stage_for_date``
# loest aber strikt per ``==`` auf. Folge: Ein-Etappen-Trip -> ``[]`` ->
# ``continue`` (bis zu 11 h 50 min ohne Ueberwachung); Mehr-Etappen-Trip ->
# Vorschau auf die Folgeetappe, also die FALSCHE Koordinate, solange deren Start
# <= ``NOWCAST_HORIZON_MIN`` (60 min) entfernt ist (darueber unterdrueckt der
# Horizont-Guard aus #1697 bereits alles).
#
# Alle Zusicherungen zielen auf die abgefragten KOORDINATEN
# (``frame_source.calls``), nie auf einen Alarm-Zaehler — an einem Zaehler waere
# die Falsch-Ortung jahrelang vorbeigelaufen. Uhr durchgehend ``freeze_time``.
# Reykjavik (UTC+0) dort, wo Zonenversatz nur Rechenrauschen waere; Korsika
# (UTC+2) fuer den realistischen 60-Minuten-Fall.


def _radar_lauf(uid: str, trip, *, mails: list | None = None):
    """Ein ``check_radar_alerts()``-Lauf gegen eine frische Zaehl-Naht; liefert
    ``(frame_source, Anzahl Alarme)``. ``reset_radar_cache()`` ist Pflicht
    (Modul-Docstring: Prozess-Singleton, TTL 300 s, eingefroren nie ablaufend)."""
    reset_radar_cache()
    frame_source = CountingFrameSource(onset_minutes=10)
    save_trip(trip, uid)
    svc = TripAlertService(
        settings=settings_email_only(), user_id=uid, throttle_hours=2,
        radar_service=radar_service(frame_source),
        mail_sink=(lambda subject, body: mails.append((subject, body)))
        if mails is not None else None,
    )
    return frame_source, svc.check_radar_alerts()


def _nacht_trip(trip_id: str, tag: date_type, *, folgeetappe=None):
    """Etappe 22:00->02:00 Ortszeit (Reykjavik, UTC+0): der Modulo-Wrap aus S2
    legt das Ziel-Segment auf ``tag+1``, 02:00 bis Tagesfenster-Ende 19:00."""
    return make_trip(
        trip_id, stage_date=tag, lat=REYKJAVIK_LAT, lon=REYKJAVIK_LON,
        arrival_start="22:00", arrival_end="02:00",
        extra_stages=[folgeetappe] if folgeetappe is not None else None,
    )


ZIEL_GESTERN = (REYKJAVIK_LAT + 0.1, REYKJAVIK_LON + 0.1)


def test_heutiges_segment_gewinnt_gegen_noch_aktives_vortagssegment():
    """S3 AC-1 (Vorrangkette): Bei echter Ueberlappung gewinnt das HEUTIGE
    Segment; ist heute nichts aktiv, gewinnt das noch laufende gestrige.

    Fixture: Etappe 10.8. 22:00->02:00 (Ziel-Segment 11.8. 02:00-19:00 UTC),
    Folgeetappe 11.8. 03:00->12:00 UTC, 1 Grad noerdlich versetzt.

    Beide Haelften noetig, keine ist fuer sich diskriminierend:
    - 04:00 UTC (Ueberlappung) ist heute schon gruen — solange heute etwas aktiv
      ist, ist S3 laut Spec bitgleich. Faengt die falsche Umsetzung
      "zusammengefuehrte Liste", in der das gestrige Ziel-Segment vorn stuende.
    - 01:00 UTC (Gegenprobe) ist die ROTE Haelfte: heute nichts aktiv, gestern
      laeuft seg1 noch. Heute waehlt der Code die Vorschau auf die 03:00-Etappe,
      der Horizont-Guard (120 min > 60) unterdrueckt sie -> 0 Abrufe.
    """
    heute = date_type(2026, 8, 11)
    heute_lat = REYKJAVIK_LAT + 1.0

    def _trip(trip_id: str):
        return _nacht_trip(
            trip_id, heute - timedelta(days=1),
            folgeetappe=trip_stage(
                "S2", heute, heute_lat, REYKJAVIK_LON,
                arrival_start="03:00", arrival_end="12:00", wp_prefix="S2WP",
            ),
        )

    with freeze_time("2026-08-11T04:00:00+00:00"):
        fs_ueberlappung, _ = _radar_lauf(fresh_uid("s3ac1-ueber"), _trip("trip-s3ac1-a"))
    assert fs_ueberlappung.calls == pytest.approx([(heute_lat, REYKJAVIK_LON)]), (
        f"S3 AC-1: abgefragt wurde {fs_ueberlappung.calls!r}, erwartet war genau "
        f"ein Abruf am HEUTIGEN Segment ({heute_lat}, {REYKJAVIK_LON}) — das "
        f"ebenfalls aktive gestrige Ziel {ZIEL_GESTERN!r} darf nicht gewinnen."
    )

    with freeze_time("2026-08-11T01:00:00+00:00"):
        fs_nur_gestern, _ = _radar_lauf(fresh_uid("s3ac1-gestern"), _trip("trip-s3ac1-b"))
    assert fs_nur_gestern.calls == pytest.approx([(REYKJAVIK_LAT, REYKJAVIK_LON)]), (
        "S3 AC-1 (Gegenprobe): um 01:00 UTC laeuft nur noch seg1 der GESTRIGEN "
        f"Etappe ({REYKJAVIK_LAT}, {REYKJAVIK_LON}) — genau dort steht der "
        f"Wanderer. Abgefragt wurde {fs_nur_gestern.calls!r}. RED: der Code kennt "
        "nur den heutigen Kalendertag; seine Vorschau auf die 03:00-Etappe faellt "
        "in den Horizont-Guard."
    )


def test_aktives_vortagsziel_schlaegt_die_bald_startende_folgeetappe():
    """S3 AC-2 (verengtes Falsch-Ortungs-Fenster): Startet die heutige
    Folgeetappe INNERHALB von ``NOWCAST_HORIZON_MIN``, greift der Guard nicht —
    abgefragt werden muss trotzdem das noch aktive GESTRIGE Ziel-Segment.

    Fixture (Korsika, UTC+2): Etappe 10.8. 22:00->02:00 Ortszeit -> Ziel-Segment
    11.8. 00:00-17:00 UTC (aktiv); Folgeetappe 11.8. 08:00-16:00 Ortszeit ->
    Start 06:00 UTC. Pruefzeitpunkt 05:30 UTC = 30 min davor.

    RED heute: die Vorschau-Regel waehlt ``segments[0]`` der Folgeetappe und
    ``get_nowcast`` laeuft real mit deren Koordinaten, waehrend der Wanderer nach
    der Ankunft um 02:00 noch am Vortagesziel steht.
    """
    heute = date_type(2026, 8, 11)
    ziel_gestern = (CORSICA_LAT + 0.1, CORSICA_LON + 0.1)
    start_folgeetappe = (CORSICA_LAT + 0.5, CORSICA_LON + 0.5)

    with freeze_time("2026-08-11T05:30:00+00:00"):
        trip = make_trip(
            f"trip-s3ac2-{uuid.uuid4().hex[:8]}", stage_date=heute - timedelta(days=1),
            lat=CORSICA_LAT, lon=CORSICA_LON, arrival_start="22:00", arrival_end="02:00",
            extra_stages=[trip_stage(
                "S2", heute, *start_folgeetappe,
                arrival_start="08:00", arrival_end="16:00", wp_prefix="S2WP",
            )],
        )
        frame_source, _ = _radar_lauf(fresh_uid("s3ac2"), trip)

    assert frame_source.calls == pytest.approx([ziel_gestern]), (
        f"S3 AC-2: abgefragt wurde {frame_source.calls!r}, erwartet war das noch "
        f"aktive GESTRIGE Ziel-Segment {ziel_gestern!r}. RED: abgefragt wird der "
        f"Start der Folgeetappe {start_folgeetappe!r} — sie beginnt in 30 min, "
        "der Horizont-Guard greift dort nicht."
    )


def test_schnappschuss_wird_unter_dem_datum_des_gewaehlten_segments_gelesen():
    """S3 AC-3: Stammt das gewaehlte Segment von gestern, muss der
    Briefing-Schnappschuss unter dem SEGMENT-Datum gelesen werden, nicht unter
    ``today`` (``trip_alert.py:1020`` ``load_dated(trip.id, today)``).

    Ein-Etappen-Trip mit Nacht-Wrap (10.8. 22:00->02:00), Pruefzeitpunkt 11.8.
    03:00 UTC -> gewaehlt wird das Ziel-Segment (``segment_id="Ziel"``) vom 10.8.
    Schnappschuss unter dem Segment-Datum -> Alarm unterdrueckt; derselbe
    Schnappschuss nur unter dem heutigen Datum -> er darf NICHT gefunden werden,
    der Alarm feuert. Ohne diese Kopplung waere S3 in genau dem Fall wirkungslos,
    fuer den es gebaut wird.

    RED heute: ``today`` = 11.8. findet die Etappe vom 10.8. nicht -> 0 Alarme in
    BEIDEN Haelften. Die Unterdrueckungs-Haelfte ist damit zufaellig gruen, die
    Gegenprobe ist die rote.
    """
    segment_tag = date_type(2026, 8, 10)
    heute = date_type(2026, 8, 11)

    def _run(*, unter_segmentdatum: bool) -> int:
        uid = fresh_uid("s3ac3-seg" if unter_segmentdatum else "s3ac3-heute")
        trip_id = f"trip-s3ac3-{uuid.uuid4().hex[:8]}"
        with freeze_time("2026-08-11T03:00:00+00:00"):
            trip = _nacht_trip(trip_id, segment_tag)
            onset_hour_naive = (datetime.now(timezone.utc) + timedelta(minutes=10)).replace(
                minute=0, second=0, microsecond=0, tzinfo=None,
            )
            _write_briefing_snapshot(
                uid, trip_id, segment_tag if unter_segmentdatum else heute,
                segment_id="Ziel", onset_hour_naive=onset_hour_naive, precip_mm=1.2,
            )
            _, count = _radar_lauf(uid, trip, mails=[])
        return count

    unterdrueckt = _run(unter_segmentdatum=True)
    assert unterdrueckt == 0, (
        f"S3 AC-3: der Schnappschuss liegt unter dem Datum des gewaehlten "
        f"Segments ({segment_tag}) und kuendigt 1.2 mm Regen an — der Alarm "
        f"haette unterdrueckt werden muessen, war count={unterdrueckt}. "
        "Vermutlich wird weiter unter `today` gesucht."
    )

    feuert = _run(unter_segmentdatum=False)
    assert feuert >= 1, (
        f"S3 AC-3 (Gegenprobe): derselbe Schnappschuss liegt nur unter dem "
        f"heutigen Datum ({heute}), das gewaehlte Segment stammt vom "
        f"{segment_tag} — er darf dort NICHT gefunden werden, der Alarm haette "
        f"feuern muessen, war count={feuert}. RED: die Etappe vom {segment_tag} "
        "wird gar nicht gefunden, es entsteht ueberhaupt kein Alarm."
    )


def test_ein_etappen_trip_bleibt_nach_mitternacht_im_zielfenster_ueberwacht():
    """S3 AC-4 (Kernmotivation): Ein Trip mit genau EINER Etappe, deren Gehzeit
    ueber Mitternacht reicht, wird nach Mitternacht weiter ueberwacht — aber nur
    innerhalb des berechneten Ziel-Segment-Fensters (11.8. 02:00-19:00 UTC).

    - 03:00 UTC (innerhalb): Abruf an der Ziel-Koordinate. RED heute:
      ``convert_trip_to_segments(trip, 11.8.)`` liefert ``[]`` -> ``continue``
      -> 0 Abrufe, bis zu 11 h 50 min ohne jede Ueberwachung.
    - 20:00 UTC (nach ``window_end``): weiterhin 0 Abrufe — heute schon gruen,
      haelt die Rueckwaerts-Suche davon ab, ein abgelaufenes Fenster
      wiederzubeleben. Bewusst der ``window_end``-Fall statt "vor Start": ein
      Zeitpunkt vor 22:00 wuerde den Horizont-Guard messen, nicht das Fenster.
    """
    tag = date_type(2026, 8, 10)

    with freeze_time("2026-08-11T03:00:00+00:00"):
        fs_innen, _ = _radar_lauf(
            fresh_uid("s3ac4-innen"), _nacht_trip(f"trip-s3ac4-i-{uuid.uuid4().hex[:8]}", tag),
        )
    assert fs_innen.calls == pytest.approx([ZIEL_GESTERN]), (
        f"S3 AC-4: um 03:00 UTC laeuft das Ziel-Segment der Etappe vom {tag} "
        f"(02:00-19:00 UTC) — erwartet war genau ein Abruf an {ZIEL_GESTERN!r}, "
        f"war {fs_innen.calls!r}. RED: der heutige Kalendertag traegt keine "
        "Etappe, der Trip wird per `continue` uebersprungen."
    )

    with freeze_time("2026-08-11T20:00:00+00:00"):
        fs_aussen, _ = _radar_lauf(
            fresh_uid("s3ac4-aussen"), _nacht_trip(f"trip-s3ac4-a-{uuid.uuid4().hex[:8]}", tag),
        )
    assert fs_aussen.calls == [], (
        "S3 AC-4 (Zeitfenster-Nachweis): um 20:00 UTC ist auch das Ziel-Segment "
        f"vorbei (Ende 19:00 UTC) — es darf kein Abruf erfolgen, war "
        f"{fs_aussen.calls!r}."
    )


def test_rueckgriff_endet_beim_unmittelbaren_vortag():
    """S3 AC-5: Die Vorrangkette schaut GENAU einen Tag zurueck.

    Gleiche Fixture, nur das Etappendatum verschoben, Pruefzeitpunkt jeweils
    11.8. 03:00 UTC:
    - Etappe am 10.8.: Ziel-Segment laeuft bis 11.8. 19:00 -> Abruf. RED heute
      (0 Abrufe), die diskriminierende Haelfte.
    - Etappe am 9.8.: dazwischen ein vollstaendiger Tag ohne Etappe, das
      Ziel-Segment endete am 10.8. 19:00 -> weiterhin KEIN Abruf. Ohne die erste
      Haelfte erfuellte das auch eine Implementierung, die gar nichts tut.
    """
    with freeze_time("2026-08-11T03:00:00+00:00"):
        fs_gestern, _ = _radar_lauf(
            fresh_uid("s3ac5-gestern"),
            _nacht_trip(f"trip-s3ac5-g-{uuid.uuid4().hex[:8]}", date_type(2026, 8, 10)),
        )
        fs_vorgestern, _ = _radar_lauf(
            fresh_uid("s3ac5-vorgestern"),
            _nacht_trip(f"trip-s3ac5-v-{uuid.uuid4().hex[:8]}", date_type(2026, 8, 9)),
        )

    assert fs_gestern.calls == pytest.approx([ZIEL_GESTERN]), (
        "S3 AC-5 (Grenze innen): die Etappe von GESTERN hat ein noch laufendes "
        f"Ziel-Segment — erwartet war ein Abruf dort, war {fs_gestern.calls!r}. "
        "RED: der Vortags-Rueckgriff existiert noch nicht."
    )
    assert fs_vorgestern.calls == [], (
        "S3 AC-5 (Grenze aussen): die letzte Etappe endete vor ZWEI Tagen — die "
        "Kette darf nicht weiter als einen Tag zurueckschauen, es darf kein "
        f"Abruf erfolgen. War {fs_vorgestern.calls!r}."
    )


class _DatumsSpion(Trip):
    """Echter ``Trip``, der jede Datums-Abfrage mitschreibt und unveraendert
    weiterreicht (Muster ``CountingFrameSource``: echte Aufrufe protokollieren,
    nichts faelschen). ``convert_trip_to_segments`` ruft als ERSTE Anweisung
    ``trip.get_stage_for_date(target_date)`` — das Protokoll ist damit die Liste
    der wirklich abgefragten Kalendertage."""

    abgefragte_daten: list

    def get_stage_for_date(self, d):
        self.abgefragte_daten.append(d)
        return super().get_stage_for_date(d)


def test_rueckgriff_fragt_genau_zwei_kalendertage_ab():
    """S3 AC-5, Tiefe am WIRKORT gemessen (Adversary-F001): abgefragt werden
    genau heute und heute-1, kein dritter Tag.

    ``test_rueckgriff_endet_beim_unmittelbaren_vortag`` misst nur die WIRKUNG
    und blieb gemessen auch bei zwei Tagen Tiefe und bei 29-Tage-Suche gruen —
    durch die Fensterkappung (#1584) ist alles aelter als gestern ohnehin
    abgelaufen. Fixture deshalb ohne Treffer an beiden Tagen (Etappe vor zwei
    Tagen): die Kette laeuft bis zum Ende, jede Zusatzstufe wird sichtbar."""
    heute = date_type(2026, 8, 11)
    vorlage = _nacht_trip("trip-s3ac5-tiefe", heute - timedelta(days=2))
    spion = _DatumsSpion(id=vorlage.id, name=vorlage.name, stages=vorlage.stages)
    spion.abgefragte_daten = []

    ergebnis = resolve_current_segment(
        spion, datetime(2026, 8, 11, 3, 0, tzinfo=timezone.utc), heute
    )

    assert spion.abgefragte_daten == [heute, heute - timedelta(days=1)], (
        f"S3 AC-5 (Tiefe): erlaubt sind genau {heute} und "
        f"{heute - timedelta(days=1)}, abgefragt wurde "
        f"{spion.abgefragte_daten!r} — ein dritter Eintrag heisst: der "
        "Rueckgriff geht tiefer als einen Tag."
    )
    assert ergebnis is None, (
        f"S3 AC-5: kein Tag traegt ein aktives Segment, erwartet None: {ergebnis!r}"
    )

