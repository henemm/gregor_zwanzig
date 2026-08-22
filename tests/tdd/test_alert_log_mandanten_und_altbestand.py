"""Issue #2050 Scheibe S6 — Mandantentrennung (AC-11) und Alt-Bestand bleibt
unangetastet (AC-12) fuer die sechs neuen E-1-Groessen.

SPEC: docs/specs/modules/alarm_protokoll_vorwarnzeit.md (AC-11, AC-12)
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from app.loader import get_data_dir
from services.radar_service import NowcastResult, RadarNowcastService

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
from tests.tdd.test_952_onset_alert_fidelity import _clean_user
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (
    _AT, _radar_trip, _settings_all_channels,
)

_ANGELEGT: list[str] = []


def _uid(tag: str) -> str:
    uid = f"tdd-2050-s6-{tag}-{uuid.uuid4().hex[:6]}"
    _ANGELEGT.append(uid)
    return uid


def _aufraeumen() -> None:
    for uid in _ANGELEGT:
        _clean_user(uid)
    _ANGELEGT.clear()


class _FixedRadar(RadarNowcastService):
    def __init__(self, **kwargs) -> None:
        super().__init__()
        kwargs.setdefault("intensity_label", "leichter Regen")
        kwargs.setdefault("source", "radar")
        self._fixed = NowcastResult(**kwargs)

    def get_nowcast(self, lat, lon, elevation_m=None, priority="user_briefing"):
        return self._fixed


def _entry_for(uid: str, entity_id: str) -> dict:
    path = get_data_dir(uid) / "alert_log.json"
    data = json.loads(path.read_text())
    treffer = [e for e in data.get("entries", []) if e.get("entity_id") == entity_id]
    assert treffer, f"kein entries-Eintrag fuer {entity_id!r} in {path}: {data!r}"
    return treffer[-1]


def test_ac11_zwei_nutzer_mit_eigenen_alarmen_vermischen_ihre_werte_nicht():
    """AC-11 (Mandantentrennung, PFLICHT): zwei Nutzer, je ein Nowcast-Alarm
    mit UNTERSCHIEDLICHER Vorwarnzeit im selben Testlauf -- Nutzer As Wert
    darf in Nutzer Bs Datei nicht auftauchen und umgekehrt."""
    uid_a, uid_b = _uid("ac11-a"), _uid("ac11-b")
    try:
        trip_a = _radar_trip(uid_a, "trip-2050-s6-ac11-a", send_email=True)
        trip_b = _radar_trip(uid_b, "trip-2050-s6-ac11-b", send_email=True)

        strecke_a = AlarmPruefstrecke(user_id=uid_a, settings=_settings_all_channels())
        strecke_b = AlarmPruefstrecke(user_id=uid_b, settings=_settings_all_channels())
        lauf_a = strecke_a.lauf(at=_AT, zweig="radar", trip=trip_a, radar_service=_FixedRadar(onset_minutes=7))
        lauf_b = strecke_b.lauf(at=_AT, zweig="radar", trip=trip_b, radar_service=_FixedRadar(onset_minutes=33))
        assert lauf_a.triggered_count == 1 and lauf_b.triggered_count == 1, (
            f"AC-11 Vorbedingung: beide Nutzer muessen ausloesen "
            f"(a={lauf_a.triggered_count}, b={lauf_b.triggered_count})."
        )

        entry_a = _entry_for(uid_a, trip_a.id)
        entry_b = _entry_for(uid_b, trip_b.id)

        assert entry_a.get("lead_time_minutes") == 7, (
            f"AC-11: Nutzer As eigener Wert (7) fehlt in seiner Datei: {entry_a!r}"
        )
        assert entry_b.get("lead_time_minutes") == 33, (
            f"AC-11: Nutzer Bs eigener Wert (33) fehlt in seiner Datei: {entry_b!r}"
        )

        data_a = json.loads((get_data_dir(uid_a) / "alert_log.json").read_text())
        data_b = json.loads((get_data_dir(uid_b) / "alert_log.json").read_text())
        assert not any(e.get("lead_time_minutes") == 33 for e in data_a.get("entries", [])), (
            f"AC-11: Nutzer Bs Wert (33) ist in Nutzer As Datei aufgetaucht: {data_a!r}"
        )
        assert not any(e.get("lead_time_minutes") == 7 for e in data_b.get("entries", [])), (
            f"AC-11: Nutzer As Wert (7) ist in Nutzer Bs Datei aufgetaucht: {data_b!r}"
        )
    finally:
        _aufraeumen()


def test_ac12_alter_eintrag_bleibt_byte_identisch_waehrend_neuer_eintrag_die_sechs_groessen_traegt():
    """AC-12 (Alt-Eintraege unangetastet, PFLICHT mit Gegenprobe): eine
    bestehende `alert_log.json` mit einem Eintrag aus VOR dieser Scheibe --
    ein neuer Alarm fuer denselben Nutzer darf den alten NICHT nachtraeglich
    um die sechs neuen Schluessel ergaenzen, waehrend der NEUE Eintrag in
    DERSELBEN Datei sie traegt, wo bestimmbar. Der Kontrast zwischen den
    beiden Eintraegen IST die Positivkontrolle."""
    from services import alert_log

    uid = _uid("ac12")
    try:
        data_dir = get_data_dir(uid)
        data_dir.mkdir(parents=True, exist_ok=True)
        alt_eintrag = {
            "entity_id": "trip-2050-s6-ac12-alt", "entity_type": "trip",
            "sent_at": "2026-01-01T09:00:00+00:00",
            "changes_count": 1, "severity": "MODERATE",
            "metrics": [{"metric_id": "precipitation", "aggregation": "sum"}],
            "hazards": [], "reason": "forecast_change",
            "channels_sent": ["email"], "channels_not_sent": [],
        }
        (data_dir / "alert_log.json").write_text(
            json.dumps({"entries": [alt_eintrag], "not_delivered": []}, indent=2)
        )

        alert_log.append_entry(
            uid, entity_id="trip-2050-s6-ac12-neu", entity_type="trip",
            changes_count=1, severity="MODERATE",
            reason=alert_log.REASON_NOWCAST,
            effective_channels={"email"}, sent_channels=["email"],
            lead_time_minutes=9, event_at=datetime(2026, 4, 5, 10, 12, tzinfo=timezone.utc).isoformat(),
            measurement_point={"segment_id": "1", "km_from": 0.0, "km_to": 3.0},
            source="radar",  # roher Schluessel, nicht die Beschriftung (O1)
        )

        data = json.loads((data_dir / "alert_log.json").read_text())
        entries = data.get("entries", [])
        assert len(entries) == 2, (
            f"AC-12 Vorbedingung: Read-Modify-Write muss den alten Eintrag "
            f"BEHALTEN und den neuen ANHAENGEN: {entries!r}"
        )
        alter_wiedergelesen = next(
            e for e in entries if e.get("entity_id") == "trip-2050-s6-ac12-alt"
        )
        assert alter_wiedergelesen == alt_eintrag, (
            f"AC-12: der ALTE Eintrag muss byte-identisch (dict-gleich) bleiben "
            f"-- keiner der sechs neuen Schluessel darf nachtraeglich ergaenzt "
            f"werden: {alter_wiedergelesen!r}"
        )
        neuer_eintrag = next(
            e for e in entries if e.get("entity_id") == "trip-2050-s6-ac12-neu"
        )
        assert any(
            k in neuer_eintrag for k in (
                "lead_time_minutes", "event_at", "measurement_point", "source",
            )
        ), (
            f"AC-12 Gegenprobe: der NEUE Eintrag muss mindestens einen der "
            f"sechs Schluessel tragen -- sonst zeigt der Kontrast oben nichts, "
            f"weil schlicht NIE geschrieben wird: {neuer_eintrag!r}"
        )
    finally:
        _aufraeumen()
