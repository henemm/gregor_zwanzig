"""TDD RED — Alarm-Abruffehler sind im Health-Journal sichtbar
(Issue #2218 Scheibe B, Epic #2505; Einträge B1-09, B2-70, C5-32).

SPEC: docs/specs/modules/fix_2218_alarm_ausfaelle.md (AC-1 bis AC-4, AC-7 bis AC-9,
AC-11; die Go-Seite AC-5/6/8/10 steht in
internal/scheduler/enrichment_health_test.go).

Geprüft wird die ECHTE Journaldatei ``<Datenwurzel>/diagnostics/
enrichment_calls.jsonl`` nach echten Alarmläufen. Ersetzt wird nur die
Systemgrenze zum Wetteranbieter (``SegmentWeatherService.fetch_segment_weather``
bzw. die Ort-Auswertung des Vergleichs); die Trennlogik "leer vs. gescheitert"
und das Journalschreiben laufen echt.

Das Journal ist append-only und liegt in der von ``_isolate_data_root``
isolierten Datenwurzel — jeder Test liest nur Zeilen seiner eigenen ``unit``.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.loader import get_data_root  # noqa: E402

from tests.helpers.alert_log_fixtures import weather  # noqa: E402
from tests.helpers.briefing_imminent_fixtures import (  # noqa: E402
    LOCATION_ZONE,
    TRIP_ZONE,
    clean_uid,
    compare_preset,
    fresh_uid,
    load_trip_obj,
    settings_email_only,
    stunde_versetzt,
    write_location,
    write_presets,
    write_trip,
)

PFAD = "alert_fetch"


# ───────────────────────────── Hilfen ──────────────────────────────────────


def _journal_zeilen() -> list[dict]:
    jp = get_data_root() / "diagnostics" / "enrichment_calls.jsonl"
    if not jp.is_file():
        return []
    return [json.loads(z) for z in jp.read_text().splitlines() if z.strip()]


def _alert_fetch(unit_teil: str) -> list[dict]:
    """Journalzeilen des Pfads ``alert_fetch`` deren ``unit`` ``unit_teil`` enthält."""
    return [
        z for z in _journal_zeilen()
        if z.get("path") == PFAD and unit_teil in (z.get("unit") or "")
    ]


@pytest.fixture
def nutzer():
    angelegt: list[str] = []

    def _neu(prefix: str) -> str:
        uid = fresh_uid(prefix)
        angelegt.append(uid)
        return uid

    yield _neu
    for uid in angelegt:
        clean_uid(uid)


def _trip(user_id: str, trip_id: str):
    # Slots weit weg von "jetzt": weder Vorlauf-Sperre noch Ruhezeit greifen.
    write_trip(
        user_id, trip_id,
        morgen_stunde=stunde_versetzt(8, zone=TRIP_ZONE),
        abend_stunde=stunde_versetzt(14, zone=TRIP_ZONE),
    )
    return load_trip_obj(user_id, trip_id)


def _vergangene_etappe(segment_id: int):
    w = weather(segment_id)
    jetzt = datetime.now(timezone.utc)
    seg = dataclasses.replace(
        w.segment,
        start_time=jetzt - timedelta(hours=9), end_time=jetzt - timedelta(hours=5),
    )
    return dataclasses.replace(w, segment=seg)


def _morgige_etappe(segment_id: int):
    w = weather(segment_id)
    jetzt = datetime.now(timezone.utc)
    seg = dataclasses.replace(
        w.segment,
        start_time=jetzt + timedelta(days=1, hours=1),
        end_time=jetzt + timedelta(days=1, hours=5),
    )
    return dataclasses.replace(w, segment=seg)


class _AbrufNaht:
    """Systemgrenze zum Anbieter: wirft für ``scheitern``, liefert sonst."""

    def __init__(self, monkeypatch, scheitern: set):
        import providers.base as base
        from services.segment_weather import SegmentWeatherService

        self.aufrufe: list = []
        naht = self

        def _fetch(service, segment, **kwargs):
            naht.aufrufe.append(segment.segment_id)
            if segment.segment_id in scheitern:
                raise RuntimeError("Anbieter nicht erreichbar")
            return weather(segment.segment_id)

        monkeypatch.setattr(base, "get_provider", lambda *_a, **_k: object())
        monkeypatch.setattr(SegmentWeatherService, "fetch_segment_weather", _fetch)


def _trip_lauf(user_id: str, trip, cached: list) -> tuple[bool, list]:
    from services.trip_alert import TripAlertService

    zugestellt: list = []
    dienst = TripAlertService(
        settings=settings_email_only(), throttle_hours=2, user_id=user_id,
        mail_sink=lambda *a, **kw: zugestellt.append((a, kw)),
    )
    return dienst.check_and_send_alerts(trip, cached_weather=cached), zugestellt


# ───────────────────────────── Trip (B1-09) ────────────────────────────────


def test_ac1_absolvierte_und_morgige_etappen_sind_kein_ausfall(
    nutzer, monkeypatch, caplog,
):
    """AC-1: leer wegen "alles legitim übersprungen" ⇒ weder `unavailable` noch
    die Dauer-Warnung. Gegenprobe zur Fehlbuchung "leer + 0 Versuche = Ausfall"."""
    uid = nutzer("ac1")
    trip = _trip(uid, "t-ac1")
    naht = _AbrufNaht(monkeypatch, scheitern=set())

    with caplog.at_level(logging.DEBUG):
        ergebnis, zugestellt = _trip_lauf(
            uid, trip, [_vergangene_etappe(1), _morgige_etappe(2)],
        )

    assert naht.aufrufe == [], "Kontrolle: übersprungene Etappen dürfen keinen Abruf auslösen"
    assert ergebnis is False and zugestellt == []
    assert _alert_fetch(f"{uid}/t-ac1") == [], "Normalfall ist kein Journal-Ereignis"
    assert not [
        r for r in caplog.records
        if r.levelno >= logging.WARNING and "No fresh weather data" in r.getMessage()
    ]


def test_ac2_gescheiterter_abruf_wird_als_ausfall_gebucht_ohne_alarm(
    nutzer, monkeypatch,
):
    """AC-2: Abruf wirft ⇒ `alert_fetch`/`unavailable` mit unit `<user>/<trip>`;
    der Check bleibt fail-closed (False, nichts gesendet) — AC-7 am Fehlerfall."""
    uid = nutzer("ac2")
    trip = _trip(uid, "t-ac2")
    naht = _AbrufNaht(monkeypatch, scheitern={1})

    ergebnis, zugestellt = _trip_lauf(uid, trip, [weather(1)])

    assert naht.aufrufe == [1], "Kontrolle: der Abruf lief wirklich"
    assert ergebnis is False and zugestellt == []
    zeilen = _alert_fetch(f"{uid}/t-ac2")
    assert [z["outcome"] for z in zeilen] == ["unavailable"]
    assert zeilen[0]["unit"] == f"{uid}/t-ac2"


def test_ac3_erfolgreicher_abruf_loest_den_ausfall_derselben_unit_ab(
    nutzer, monkeypatch,
):
    """AC-3: erst Ausfall, dann Erfolg ⇒ gleiche `unit`, letzte Zeile `ok`."""
    uid = nutzer("ac3")
    trip = _trip(uid, "t-ac3")

    _AbrufNaht(monkeypatch, scheitern={1})
    _trip_lauf(uid, trip, [weather(1)])
    _AbrufNaht(monkeypatch, scheitern=set())
    _trip_lauf(uid, trip, [weather(1)])

    zeilen = _alert_fetch(f"{uid}/t-ac3")
    assert [z["outcome"] for z in zeilen] == ["unavailable", "ok"]
    assert {z["unit"] for z in zeilen} == {f"{uid}/t-ac3"}


def test_ac11_teilausfall_zaehlt_als_ausfall_und_liefert_kein_ok(
    nutzer, monkeypatch,
):
    """AC-11: Segment 1 wirft, Segment 2 liefert ⇒ genau EIN `unavailable`,
    KEIN `ok`; die gelieferten Daten laufen weiter (Aufruf für beide Segmente)."""
    uid = nutzer("ac11")
    trip = _trip(uid, "t-ac11")
    naht = _AbrufNaht(monkeypatch, scheitern={1})

    _trip_lauf(uid, trip, [weather(1), weather(2)])

    assert naht.aufrufe == [1, 2]
    zeilen = _alert_fetch(f"{uid}/t-ac11")
    assert [z["outcome"] for z in zeilen] == ["unavailable"]


def test_ac8_zwei_nutzer_tragen_ihre_eigene_id_in_der_unit(nutzer, monkeypatch):
    """AC-8 (Schreibseite): gleiche Trip-ID bei zwei Nutzern ⇒ zwei getrennte
    Einheiten; der Erfolg von B überschreibt nicht die Unit von A."""
    a, b = nutzer("ac8a"), nutzer("ac8b")
    trip_a, trip_b = _trip(a, "t-gleich"), _trip(b, "t-gleich")

    _AbrufNaht(monkeypatch, scheitern={1})
    _trip_lauf(a, trip_a, [weather(1)])
    _AbrufNaht(monkeypatch, scheitern=set())
    _trip_lauf(b, trip_b, [weather(1)])

    za, zb = _alert_fetch(f"{a}/t-gleich"), _alert_fetch(f"{b}/t-gleich")
    assert [z["outcome"] for z in za] == ["unavailable"]
    assert [z["outcome"] for z in zb] == ["ok"]
    assert za[0]["unit"] == f"{a}/t-gleich" and zb[0]["unit"] == f"{b}/t-gleich"


def test_ac9_trip_journal_nicht_beschreibbar_aendert_den_lauf_nicht(
    nutzer, monkeypatch,
):
    """AC-9: Journalpfad ist ein Verzeichnis ⇒ keine Ausnahme, Rückgabe wie sonst.
    Kontrolle: der Fehlerpfad (Abruf wirft) wurde wirklich durchlaufen."""
    uid = nutzer("ac9t")
    trip = _trip(uid, "t-ac9")
    naht = _AbrufNaht(monkeypatch, scheitern={1})
    (get_data_root() / "diagnostics" / "enrichment_calls.jsonl").mkdir(
        parents=True, exist_ok=True,
    )
    try:
        ergebnis, zugestellt = _trip_lauf(uid, trip, [weather(1)])
    finally:
        (get_data_root() / "diagnostics" / "enrichment_calls.jsonl").rmdir()

    assert naht.aufrufe == [1]
    assert ergebnis is False and zugestellt == []


# ───────────────────────────── Ortsvergleich (B2-70) ───────────────────────


def _compare_lauf(monkeypatch, user_id: str, kaputter_ort: str | None):
    from services.compare_alert import CompareAlertService

    class _Dienst(CompareAlertService):
        def _evaluate_one_location(self, preset_id, location_id, *a, **kw):
            if location_id == kaputter_ort:
                raise RuntimeError("Ortsabruf gescheitert")
            return None

    dienst = _Dienst(settings=settings_email_only(), user_id=user_id)
    sent = dienst.check_all_compare_presets()
    return sent, dienst.last_failed_count


def _compare_aufbau(user_id: str) -> None:
    for lid in ("loc-a", "loc-b", "loc-c"):
        write_location(user_id, lid)
    preset = compare_preset(
        "p-2218",
        morgen_stunde=stunde_versetzt(8, zone=LOCATION_ZONE),
        abend_stunde=stunde_versetzt(14, zone=LOCATION_ZONE),
        location_ids=["loc-a", "loc-b", "loc-c"],
    )
    write_presets(user_id, [preset])


def test_ac4_ortsfehler_wird_je_ort_gebucht_andere_orte_laufen_weiter(
    nutzer, monkeypatch,
):
    """AC-4: mittlerer Ort wirft ⇒ `unavailable` für genau diese unit, die
    anderen beiden `ok`, Preset NICHT als gescheitert gezählt."""
    uid = nutzer("ac4")
    _compare_aufbau(uid)

    sent, failed = _compare_lauf(monkeypatch, uid, kaputter_ort="loc-b")

    assert failed == 0, "Presets werden bei einem Ortsfehler nicht als gescheitert gewertet"
    assert sent == 0
    assert [z["outcome"] for z in _alert_fetch(f"{uid}/p-2218/loc-b")] == ["unavailable"]
    assert [z["outcome"] for z in _alert_fetch(f"{uid}/p-2218/loc-a")] == ["ok"]
    assert [z["outcome"] for z in _alert_fetch(f"{uid}/p-2218/loc-c")] == ["ok"]
    assert _alert_fetch(f"{uid}/p-2218/loc-b")[0]["unit"] == f"{uid}/p-2218/loc-b"


def test_ac9_compare_journal_nicht_beschreibbar_aendert_den_lauf_nicht(
    nutzer, monkeypatch,
):
    """AC-9 (Ortsvergleich): Journal-Verzeichnis-Falle ⇒ gleiches Ergebnis wie
    ohne Journalfehler, die Schleife läuft durch."""
    uid = nutzer("ac9c")
    _compare_aufbau(uid)
    jp = get_data_root() / "diagnostics" / "enrichment_calls.jsonl"
    jp.mkdir(parents=True, exist_ok=True)
    try:
        sent, failed = _compare_lauf(monkeypatch, uid, kaputter_ort="loc-b")
    finally:
        jp.rmdir()

    assert (sent, failed) == (0, 0)
