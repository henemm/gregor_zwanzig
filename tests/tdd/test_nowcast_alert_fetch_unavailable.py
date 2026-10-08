"""TDD RED -- ein Nowcast-Ausfall im Trip-Radar-Alarm bucht ``alert_fetch``
(Eintrag C5-02c, Issue #2218 Scheibe C, Epic #2505).

SPEC: docs/specs/modules/fix_2218_scheibe_c_observability.md (AC-28)

Heute faengt der Radar-Zweig eine Ausnahme des ERSTEN Nowcast-Abrufs mit einem
``logger.error`` ab und buecht nichts ins Health-Journal -- der Ausfall ist nur
im Log sichtbar (Scheibe B hat denselben Pfad fuer den Delta-Zweig geschlossen).
Gefordert: ``alert_fetch``/``unavailable`` mit ``unit = <user>/<trip>``; ein
erfolgreicher Abruf bucht ``alert_fetch``/``ok`` mit derselben ``unit`` (loest
den Ausfall ab); ``RadarDeadlineExceeded`` bucht KEIN ``unavailable`` (Zeitgrenze
ist weder Ausfall noch Entwarnung). Rueckgabe und Alarmentscheidung unveraendert.

Geprueft wird die ECHTE Journaldatei. Fake nur an der Systemgrenze: eine echte
``RadarNowcastService``-Unterklasse, die beim ersten Abruf wirft. Zwei Nutzer
mit gleicher Trip-ID pruefen die Mandantentrennung der ``unit``.
"""
from __future__ import annotations

import json
import time
import uuid

import pytest
from freezegun import freeze_time

from app.loader import get_data_root
from services.radar_service import RadarDeadlineExceeded

from tests.tdd.test_radar_alarmlauf_fairness import (
    _ScriptedRadar,
    _make_trips,
    _trip_idx,
    _trip_service,
)

PFAD = "alert_fetch"


@pytest.fixture(autouse=True)
def _gestellte_uhr():
    # Muster test_radar_alarmlauf_fairness.py: Mittag UTC, monotonic echt.
    echte_monotonic = time.monotonic
    with freeze_time("2026-10-01T10:00:00+00:00", tick=True):
        time.monotonic = echte_monotonic
        yield


def _uid(tag: str) -> str:
    return f"tdd-2218c-{tag}-{uuid.uuid4().hex[:6]}"


def _journal(unit: str) -> list[dict]:
    jp = get_data_root() / "diagnostics" / "enrichment_calls.jsonl"
    if not jp.is_file():
        return []
    zeilen = [json.loads(z) for z in jp.read_text().splitlines() if z.strip()]
    return [z for z in zeilen if z.get("path") == PFAD and z.get("unit") == unit]


def _lauf(uid: str, trip_id: str, **radar_kw):
    mails: list = []
    radar = _ScriptedRadar(_trip_idx, **radar_kw)
    ergebnis = _trip_service(uid, radar, mails).check_radar_alerts_run()
    return ergebnis, mails, radar


def test_ac28_ausnahme_im_ersten_nowcast_abruf_bucht_unavailable_ohne_alarm():
    """AC-28: der erste Nowcast-Abruf wirft -> ``alert_fetch``/``unavailable``
    mit ``unit = <user>/<trip>``; kein Alarm, keine Nutzermeldung, der Lauf
    selbst bleibt unveraendert (Trip gilt als geprueft)."""
    uid = _uid("ausfall")
    _make_trips(uid, ["t-ausfall"])

    ergebnis, mails, radar = _lauf(uid, "t-ausfall", raise_on=(0, 1, RuntimeError("Nowcast down")))

    assert radar.calls_per_unit.get(0, 0) >= 1, "Testaufbau: der Abruf lief wirklich"
    assert ergebnis.alerts_sent == 0 and mails == [], "kein Alarm bei Quellenausfall"
    assert ergebnis.checked == 1
    zeilen = _journal(f"{uid}/t-ausfall")
    assert zeilen, f"AC-28: kein alert_fetch-Eintrag fuer {uid}/t-ausfall im Journal"
    assert zeilen[0]["outcome"] == "unavailable", zeilen


def test_ac28_erfolgreicher_abruf_bucht_ok_mit_derselben_unit():
    """AC-28: erfolgreicher Nowcast-Abruf -> ``alert_fetch``/``ok`` mit
    ``unit = <user>/<trip>``."""
    uid = _uid("ok")
    _make_trips(uid, ["t-ok"])

    ergebnis, _mails, radar = _lauf(uid, "t-ok")

    assert radar.calls_per_unit.get(0, 0) >= 1, "Testaufbau: der Abruf lief wirklich"
    zeilen = _journal(f"{uid}/t-ok")
    assert zeilen, f"AC-28: kein alert_fetch/ok-Eintrag fuer {uid}/t-ok im Journal"
    assert {z["outcome"] for z in zeilen} == {"ok"}, zeilen


def test_ac28_spaeterer_erfolg_loest_den_ausfall_derselben_unit_ab():
    """AC-28: erst Ausfall, dann Erfolg derselben Einheit -> die LETZTE Zeile
    der ``unit`` ist ``ok`` (der Ausfall wird abgeloest, nicht ewig gemeldet)."""
    uid = _uid("abloesung")
    _make_trips(uid, ["t-abl"])

    _lauf(uid, "t-abl", raise_on=(0, 1, RuntimeError("Nowcast down")))
    _lauf(uid, "t-abl")

    zeilen = _journal(f"{uid}/t-abl")
    assert [z["outcome"] for z in zeilen][:1] == ["unavailable"], zeilen
    assert zeilen[-1]["outcome"] == "ok", zeilen


def test_ac28_zeitgrenze_bucht_keinen_ausfall():
    """AC-28: ``RadarDeadlineExceeded`` ist weder Ausfall noch Entwarnung ->
    KEIN ``unavailable`` im Journal. Kontrolle: derselbe Aufbau mit einer
    gewoehnlichen Ausnahme bucht sehr wohl einen (anderer Nutzer)."""
    uid_grenze, uid_ausfall = _uid("grenze"), _uid("kontrolle")
    _make_trips(uid_grenze, ["t-grenze"])
    _make_trips(uid_ausfall, ["t-grenze"])

    _lauf(uid_grenze, "t-grenze", raise_on=(0, 1, RadarDeadlineExceeded("Zeitgrenze")))
    _lauf(uid_ausfall, "t-grenze", raise_on=(0, 1, RuntimeError("Nowcast down")))

    assert [z for z in _journal(f"{uid_grenze}/t-grenze") if z["outcome"] == "unavailable"] == [], (
        "RadarDeadlineExceeded darf nicht als Ausfall gebucht werden"
    )
    assert [z["outcome"] for z in _journal(f"{uid_ausfall}/t-grenze")][:1] == ["unavailable"], (
        "Positivkontrolle gescheitert: auch die gewoehnliche Ausnahme bucht nichts"
    )


def test_ac28_zwei_nutzer_mit_gleicher_trip_id_tragen_ihre_eigene_unit():
    """AC-28 (Mandantentrennung): gleiche Trip-ID bei zwei Nutzern -> zwei
    getrennte Einheiten; der Erfolg von B ueberschreibt nicht den Ausfall von A."""
    a, b = _uid("mandant-a"), _uid("mandant-b")
    _make_trips(a, ["t-gleich"])
    _make_trips(b, ["t-gleich"])

    _lauf(a, "t-gleich", raise_on=(0, 1, RuntimeError("Nowcast down")))
    _lauf(b, "t-gleich")

    za, zb = _journal(f"{a}/t-gleich"), _journal(f"{b}/t-gleich")
    assert za and za[0]["outcome"] == "unavailable", za
    assert zb and {z["outcome"] for z in zb} == {"ok"}, zb
