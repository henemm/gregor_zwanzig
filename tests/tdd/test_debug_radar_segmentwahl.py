"""TDD RED — Issue #2985: Debug-Route waehlt die Etappe ueber den EINEN
Baustein ``resolve_current_segment`` statt ueber eine eigene Kopie.

SPEC: docs/specs/fast/fix-2985-debug-segmentwahl.md (AC-1 … AC-4)
(Die Spec nennt den Arbeitstitel ``test_issue_2985_debug_segmentwahl.py``;
das Testnamen-Gate verlangt Benennung nach Verhalten, daher dieser Name.)

RED-Grund heute: ``api/routers/debug.py`` hat keine Hilfsfunktion
``_pick_debug_segment``; die Route bestimmt das Segment inline mit einer
eigenen "aktiv oder erstes"-Schleife ohne Vortags-Rueckgriff.

Testpolitik: echte ``Trip``-Objekte aus dem geteilten Helfer
(``tests/helpers/nowcast_gate_fixtures.py``), kein Mock/patch. Die Erwartung
fuer AC-1 wird ZUSAETZLICH unabhaengig vom Pruefling aufgebaut (laufendes
Segment der gestrigen Etappe ueber ``convert_trip_to_segments`` +
Zeitfenster), damit der Test nicht nur die Vorrangkette gegen sich selbst
prueft.

Mutations-Gegenprobe (AC-4): Ersetzt man in ``_pick_debug_segment`` den
Aufruf von ``resolve_current_segment`` durch ``None`` (nur noch eigene
Heute-Schleife bzw. Test-Seam-Rueckfall), liefert die Funktion fuer AC-1 das
ERSTE Segment der Etappe (Gehsegment ab 22:00) statt des noch laufenden
Ziel-Segments — ``test_ac1_…`` wird rot.

Ausfuehrung:
    uv run pytest tests/tdd/test_debug_radar_segmentwahl.py -v
"""
from __future__ import annotations

import smtplib
import time
from datetime import date as date_type
from datetime import datetime, timezone

import pytest

from services.trip_segments import convert_trip_to_segments, resolve_current_segment

from tests.helpers.nowcast_gate_fixtures import make_trip, save_trip, trip_stage

# Atlantic/Reykjavik (UTC+0): Ortstag == UTC-Tag, kein Zonenrauschen.
REYKJAVIK_LAT, REYKJAVIK_LON = 64.1466, -21.9426


def _pick():
    from api.routers.debug import _pick_debug_segment

    return _pick_debug_segment


def _key(seg):
    """Identitaet eines Segments ueber fachliche Felder."""
    return (
        str(seg.segment_id),
        seg.start_time,
        seg.end_time,
        round(seg.start_point.lat, 6),
        round(seg.start_point.lon, 6),
        round(seg.end_point.lat, 6),
        round(seg.end_point.lon, 6),
    )


def _nacht_trip(tag: date_type):
    """Etappe 22:00 -> 02:00 Ortszeit: das Ziel-Segment laeuft am Folgetag
    ab 02:00 bis Tagesfenster-Ende (siehe #1667 S3)."""
    return make_trip(
        "trip-2985-nacht", stage_date=tag, lat=REYKJAVIK_LAT, lon=REYKJAVIK_LON,
        arrival_start="22:00", arrival_end="02:00",
    )


def test_ac1_vortags_zielsegment_nach_mitternacht_wie_resolve_current_segment():
    """AC-1: Gestrige Etappe kommt nach Mitternacht an, ihr Ziel-Segment laeuft
    jetzt (11.8. 03:00 UTC) noch, heute keine Etappe. Die Debug-Segmentwahl
    muss genau das Segment liefern, das ``resolve_current_segment`` liefert —
    nicht das erste Segment des Trips."""
    tag = date_type(2026, 8, 10)
    heute = date_type(2026, 8, 11)
    now_utc = datetime(2026, 8, 11, 3, 0, tzinfo=timezone.utc)
    trip = _nacht_trip(tag)

    erwartet = resolve_current_segment(trip, now_utc, heute)
    assert erwartet is not None, "Vorbedingung: Vorrangkette liefert das Vortags-Ziel"
    erwartet_seg, erwartet_datum = erwartet
    assert erwartet_datum == tag, "Vorbedingung: Segment stammt von gestern"

    gestern_segs = convert_trip_to_segments(trip, tag)
    laufend = [s for s in gestern_segs if s.start_time <= now_utc <= s.end_time]
    assert len(laufend) == 1, f"Vorbedingung: genau ein laufendes Segment, war {laufend!r}"
    erstes = gestern_segs[0]
    assert _key(erstes) != _key(laufend[0]), (
        "Vorbedingung: erstes Segment und laufendes Ziel-Segment muessen sich "
        "unterscheiden, sonst diskriminiert der Test nicht"
    )

    gewaehlt = _pick()(trip, now_utc, heute)

    assert gewaehlt is not None, "AC-1: Debug-Segmentwahl lieferte None"
    assert _key(gewaehlt) == _key(erwartet_seg), (
        f"AC-1: erwartet das Segment aus resolve_current_segment "
        f"{_key(erwartet_seg)!r}, war {_key(gewaehlt)!r}"
    )
    assert _key(gewaehlt) == _key(laufend[0])
    assert _key(gewaehlt) != _key(erstes), (
        "AC-1: die Debug-Segmentwahl fiel auf das erste Segment des Trips zurueck "
        "statt das noch laufende Vortags-Ziel zu nehmen"
    )


def test_ac2_heute_aktives_segment_bleibt_unveraendert():
    """AC-2: Ist heute ein Segment aktiv, liefert die Debug-Segmentwahl genau
    dieses Segment (Verhalten wie vor dem Umbau)."""
    heute = date_type(2026, 8, 11)
    now_utc = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
    trip = make_trip(
        "trip-2985-heute", stage_date=heute, lat=REYKJAVIK_LAT, lon=REYKJAVIK_LON,
        arrival_start="08:00", arrival_end="16:00",
    )

    segs = convert_trip_to_segments(trip, heute)
    aktiv = [s for s in segs if s.start_time <= now_utc <= s.end_time]
    assert aktiv, f"Vorbedingung: heute ist ein Segment aktiv, Segmente {segs!r}"

    gewaehlt = _pick()(trip, now_utc, heute)

    assert gewaehlt is not None, "AC-2: Debug-Segmentwahl lieferte None"
    assert _key(gewaehlt) == _key(aktiv[0]), (
        f"AC-2: erwartet das heute aktive Segment {_key(aktiv[0])!r}, "
        f"war {_key(gewaehlt)!r}"
    )


def test_ac3_vergangene_etappen_test_seam_rueckfall_auf_erstes_segment():
    """AC-3: Alle Etappen liegen in der Vergangenheit (Staging-Testdaten) —
    ``resolve_current_segment`` liefert None, die Debug-Segmentwahl faellt auf
    das erste Segment der ersten Etappe zurueck statt None zu liefern."""
    alt = date_type(2026, 8, 1)
    heute = date_type(2026, 8, 11)
    now_utc = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
    trip = make_trip(
        "trip-2985-alt", stage_date=alt, lat=REYKJAVIK_LAT, lon=REYKJAVIK_LON,
        arrival_start="08:00", arrival_end="16:00",
    )
    assert resolve_current_segment(trip, now_utc, heute) is None, (
        "Vorbedingung: keine aktive Etappe, keine Vorschau"
    )
    erwartet = convert_trip_to_segments(trip, alt)[0]

    gewaehlt = _pick()(trip, now_utc, heute)

    assert gewaehlt is not None, "AC-3: Test-Seam-Rueckfall fehlt, lieferte None"
    assert _key(gewaehlt) == _key(erwartet), (
        f"AC-3: erwartet das erste Segment der ersten Etappe {_key(erwartet)!r}, "
        f"war {_key(gewaehlt)!r}"
    )


def test_trip_ohne_etappen_liefert_kein_segment():
    """Rand zu AC-3: ohne Etappen gibt es kein Segment -> None (die Route
    antwortet weiterhin ``no_segment``)."""
    from app.trip import Trip

    heute = date_type(2026, 8, 11)
    now_utc = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
    trip = Trip(id="trip-2985-leer", name="leer", stages=[])

    assert _pick()(trip, now_utc, heute) is None


def test_heute_alle_segmente_vorbei_rueckfall_auf_erstes_segment_von_heute():
    """Test-Seam-Rueckfall Stufe 1 (Fix-Loop F002): heute gibt es eine Etappe,
    aber alle Segmente sind vorbei (21:00 UTC nach 08-16 Uhr + Ziel bis 20:00),
    ``resolve_current_segment`` liefert None. Erwartet: das ERSTE Segment von
    heute — nicht das letzte und nicht das erste Segment der fruehesten
    Trip-Etappe (die liegt bewusst an anderem Ort, damit beides unterscheidbar
    ist)."""
    frueher = date_type(2026, 8, 8)
    heute = date_type(2026, 8, 11)
    now_utc = datetime(2026, 8, 11, 21, 0, tzinfo=timezone.utc)
    trip = make_trip(
        "trip-2985-abend", stage_date=heute, lat=REYKJAVIK_LAT, lon=REYKJAVIK_LON,
        arrival_start="08:00", arrival_end="16:00",
    )
    trip.stages.insert(0, trip_stage(
        "S0", frueher, REYKJAVIK_LAT + 1.0, REYKJAVIK_LON + 1.0,
        arrival_start="08:00", arrival_end="16:00", wp_prefix="A",
    ))
    assert resolve_current_segment(trip, now_utc, heute) is None, (
        "Vorbedingung: heute ist nichts mehr aktiv, keine Vorschau"
    )
    heute_segs = convert_trip_to_segments(trip, heute)
    assert len(heute_segs) >= 2, f"Vorbedingung: mehrere Segmente heute, war {heute_segs!r}"
    erstes_heute = heute_segs[0]
    erstes_trip = convert_trip_to_segments(trip, frueher)[0]
    assert _key(erstes_heute) != _key(heute_segs[-1])
    assert _key(erstes_heute) != _key(erstes_trip), (
        "Vorbedingung: erstes Segment von heute und erstes Segment der "
        "fruehesten Etappe muessen sich unterscheiden"
    )

    gewaehlt = _pick()(trip, now_utc, heute)

    assert gewaehlt is not None, "Heute-Rueckfall lieferte None"
    assert _key(gewaehlt) == _key(erstes_heute), (
        f"erwartet das erste Segment von heute {_key(erstes_heute)!r}, "
        f"war {_key(gewaehlt)!r}"
    )


def test_zwei_vergangene_etappen_rueckfall_auf_erste_etappe():
    """Test-Seam-Rueckfall Stufe 2 (Fix-Loop F003): zwei vergangene Etappen,
    heute nichts. Erwartet: erstes Segment der ERSTEN Etappe (Reihenfolge
    der Etappenliste), nicht der letzten."""
    erste = date_type(2026, 8, 1)
    zweite = date_type(2026, 8, 3)
    heute = date_type(2026, 8, 11)
    now_utc = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
    trip = make_trip(
        "trip-2985-zwei-alt", stage_date=erste, lat=REYKJAVIK_LAT, lon=REYKJAVIK_LON,
        arrival_start="08:00", arrival_end="16:00",
        extra_stages=[trip_stage(
            "S2", zweite, REYKJAVIK_LAT + 1.0, REYKJAVIK_LON + 1.0,
            arrival_start="08:00", arrival_end="16:00", wp_prefix="B",
        )],
    )
    assert resolve_current_segment(trip, now_utc, heute) is None
    erwartet = convert_trip_to_segments(trip, erste)[0]
    andere = convert_trip_to_segments(trip, zweite)[0]
    assert _key(erwartet) != _key(andere), "Vorbedingung: Etappen unterscheidbar"

    gewaehlt = _pick()(trip, now_utc, heute)

    assert gewaehlt is not None
    assert _key(gewaehlt) == _key(erwartet), (
        f"erwartet das erste Segment der ersten Etappe {_key(erwartet)!r}, "
        f"war {_key(gewaehlt)!r}"
    )


# ---------------------------------------------------------------------------
# Route-Test (Fix-Loop F001): die Route verwendet das gewaehlte Segment
# ---------------------------------------------------------------------------

class _FakeSocket:
    def settimeout(self, timeout: float) -> None:
        pass


class _FakeSMTPConnection:
    """Ersetzt die SMTP-Verbindung am Transportrand — kein Netz (Muster aus
    ``tests/tdd/test_mail_fallback_guard.py``)."""

    def __init__(self, calls: list[dict], host: str) -> None:
        self._calls = calls
        self._host = host
        self.sock = _FakeSocket()

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def ehlo(self, *a, **k):
        return (250, b"ok")

    def starttls(self, context=None) -> None:
        return None

    def login(self, user, password) -> None:
        return None

    def sendmail(self, from_addr, to_addrs, msg) -> None:
        self._calls.append({"host": self._host, "to": tuple(to_addrs)})

    def quit(self) -> None:
        return None


class _RecordingSMTP:
    def __init__(self, calls: list[dict]) -> None:
        self.calls = calls

    def __call__(self, host, port, *a, **kw):
        return _FakeSMTPConnection(self.calls, host)


@pytest.fixture
def smtp_sink(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(smtplib, "SMTP", _RecordingSMTP(calls))
    monkeypatch.setattr(time, "sleep", lambda *a, **k: None)
    return calls


def test_route_verwendet_aktives_segment_von_heute(monkeypatch, smtp_sink):
    """F001: Die Route ``POST /api/debug/trigger-radar-alert`` nimmt das von
    ``_pick_debug_segment`` gewaehlte Segment. Gestellte Uhr 11.8. 12:00 UTC,
    fruehere Etappe am 8.8., heutige Etappe 08-10 Uhr -> aktiv ist das
    Ziel-Segment von heute (``segment_id`` "Ziel"). Wuerde die Route ein
    falsches ``today`` weiterreichen, fiele sie auf das erste Segment der
    Etappe vom 8.8. ("Etappe 1"); wuerde sie das Segment verwerfen, kaeme
    ``no_segment``."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from freezegun import freeze_time

    from api.routers import debug as debug_router

    # ``api.main`` bindet den Debug-Router nur ein, wenn GZ_ENV beim IMPORT
    # schon "staging" war — im Testprozess ist das nicht steuerbar. Deshalb
    # der ECHTE Router in einer eigenen App; die Route selbst prueft GZ_ENV
    # zur Anfragezeit (Staging-Guard) und laeuft unveraendert.
    app = FastAPI()
    app.include_router(debug_router.router)

    monkeypatch.setenv("GZ_ENV", "staging")
    user_id = "user-2985-route"
    heute = date_type(2026, 8, 11)
    trip = make_trip(
        "trip-2985-route", stage_date=heute, lat=REYKJAVIK_LAT, lon=REYKJAVIK_LON,
        arrival_start="08:00", arrival_end="10:00",
    )
    trip.stages.insert(0, trip_stage(
        "S0", date_type(2026, 8, 8), REYKJAVIK_LAT + 1.0, REYKJAVIK_LON + 1.0,
        arrival_start="08:00", arrival_end="10:00", wp_prefix="A",
    ))
    save_trip(trip, user_id)

    now_utc = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
    erwartet_seg, _ = resolve_current_segment(trip, now_utc, heute)
    assert str(erwartet_seg.segment_id) == "Ziel", "Vorbedingung: heute aktiv ist das Ziel"
    assert str(convert_trip_to_segments(trip, date_type(2026, 8, 8))[0].segment_id) != "Ziel"

    # Gestellt wird nur die Uhr der Segmentwahl. Das Mail-Modul laeuft auf der
    # echten Uhr: im Worker-Thread des TestClient mischte freezegun sonst echte
    # und gestellte ``time.monotonic``-Werte, das SMTP-Zeitbudget war sofort
    # "erschoepft" und der Ersatzweg sprang ein (nicht Gegenstand dieses Tests).
    with freeze_time(now_utc, ignore=["output.channels.email"]):
        resp = TestClient(app).post(
            "/api/debug/trigger-radar-alert", params={"user_id": user_id},
        )

    assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body.get("status") == "sent", f"erwartet 'sent', war {body!r}"
    assert body.get("trip_id") == "trip-2985-route"
    assert body.get("segment") == "Etappe Ziel", (
        f"Route verwendet nicht das aktive Segment von heute: {body!r}"
    )
    assert smtp_sink, "keine Mail am Transportrand angekommen"
    assert all(c["to"] == ("gregor-test@henemm.com",) for c in smtp_sink), smtp_sink
