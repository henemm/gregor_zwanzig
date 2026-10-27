"""Issue #2050 Scheibe S6 — `unique_or_none()` selbst (AC-14) und
Fail-soft bei fehlerhaft geformten Eingaben an `append_entry()` (AC-15).

SPEC: docs/specs/modules/alarm_protokoll_vorwarnzeit.md (AC-14, AC-15)

RED-Grund: `services.alert_log.unique_or_none` existiert noch nicht
(ImportError); `append_entry()` kennt die sechs neuen kwargs noch nicht
(TypeError) -- beides der korrekte, ehrliche Rot-Grund fuer diese Scheibe.
"""
from __future__ import annotations

import logging
import uuid

from app.loader import get_data_dir


_ANGELEGT: list[str] = []


def _uid(tag: str) -> str:
    uid = f"tdd-2050-s6-{tag}-{uuid.uuid4().hex[:6]}"
    _ANGELEGT.append(uid)
    return uid


def _aufraeumen() -> None:
    import shutil
    for uid in _ANGELEGT:
        d = get_data_dir(uid)
        if d.exists():
            shutil.rmtree(d)
    _ANGELEGT.clear()


def test_ac14_unique_or_none_liefert_den_einen_wert_oder_none_bei_mehrdeutigkeit():
    """AC-14 (PFLICHT mit Gegenprobe): vier Fallgruppen in einem Test --
    eindeutig direkt, eindeutig mit `None`-Rauschen, mehrdeutig (zwei
    verschiedene Werte), leere Liste."""
    from services.alert_log import unique_or_none

    assert unique_or_none(["seg-1", "seg-1"]) == "seg-1", (
        "AC-14: zwei gleiche Nicht-None-Werte muessen den einen Wert liefern"
    )
    assert unique_or_none(["seg-1", None]) == "seg-1", (
        "AC-14: ein Wert plus None-Rauschen muss den einen Wert liefern"
    )
    assert unique_or_none(["seg-1", "seg-2"]) is None, (
        "AC-14: ZWEI VERSCHIEDENE Nicht-None-Werte muessen None liefern "
        "(Mehrdeutigkeit) -- sonst waere das eine willkuerliche Wahl"
    )
    assert unique_or_none([]) is None, (
        "AC-14: eine leere Liste muss None liefern"
    )


def test_ac15_fehlerhaft_geformter_wert_verhindert_den_alarm_nicht_und_wird_laut_verworfen(caplog):
    """AC-15 (PFLICHT): `measurement_point` als String statt dict --
    `append_entry()` darf KEINE Ausnahme werfen (der Alarm darf nie
    verhindert werden), der fehlerhafte Schluessel entsteht nicht (mit oder
    ohne korrekten Wert je nach Absicherung), aber es erscheint eine
    `logger.warning`-Zeile mit dem betroffenen Schluessel und der
    `entity_id`. Gegenprobe: derselbe Aufruf mit korrekt geformtem Wert
    erzeugt KEINE Warnung -- der Unterschied beweist, dass die Warnung den
    Fehlerfall anzeigt, nicht immer erscheint."""
    from services import alert_log

    uid = _uid("ac15")
    try:
        with caplog.at_level(logging.WARNING, logger="services.alert_log"):
            caplog.clear()
            alert_log.append_entry(
                uid, entity_id="trip-2050-s6-ac15-defekt", entity_type="trip",
                changes_count=1, severity="MODERATE",
                reason=alert_log.REASON_NOWCAST,
                effective_channels={"email"}, sent_channels=["email"],
                measurement_point="das-ist-KEIN-dict",  # absichtlich falsch geformt
            )
        assert any(
            "trip-2050-s6-ac15-defekt" in r.message and "measurement_point" in r.message
            for r in caplog.records
        ), (
            f"AC-15: erwarte eine Warnung mit Schluessel UND entity_id, "
            f"nicht stilles Verschlucken. Log: {[r.message for r in caplog.records]!r}"
        )

        # Gegenprobe: derselbe Aufruf mit korrekt geformtem Wert -- KEINE Warnung.
        with caplog.at_level(logging.WARNING, logger="services.alert_log"):
            caplog.clear()
            alert_log.append_entry(
                uid, entity_id="trip-2050-s6-ac15-korrekt", entity_type="trip",
                changes_count=1, severity="MODERATE",
                reason=alert_log.REASON_NOWCAST,
                effective_channels={"email"}, sent_channels=["email"],
                measurement_point={"segment_id": "1", "km_from": 0.0, "km_to": 3.0},
            )
        assert not caplog.records, (
            f"AC-15 Gegenprobe: ein KORREKT geformter Wert darf KEINE Warnung "
            f"ausloesen -- sonst zeigt die Warnung oben nicht den Fehlerfall, "
            f"sondern erscheint immer. Log: {[r.message for r in caplog.records]!r}"
        )
    finally:
        _aufraeumen()


def test_ac15_defekte_e1_ableitung_stoppt_weder_den_alarm_noch_die_folgenden_trips(
    monkeypatch, caplog,
):
    """AC-15 an der Stelle, an der die Zusicherung WIRKT: die E-1-Ableitung
    des Radar-Zweigs (`trip_alert._radar_e1_fields()`) steht VOR dem Versand
    und laeuft INNERHALB der Schleife ueber alle Trips des Nutzers. Ein
    Fehler dort duerfte deshalb weder den Alarm dieses Trips verhindern noch
    die uebrigen Trips mitreissen (Muster `fix_1479`).

    Fehler-Injektion ueber die ECHTE geteilte Naht
    `alert_log.nowcast_event_end_at()`, die die Ableitung benutzt -- kein
    Mock(): gemessen wird nicht die Injektion selbst, sondern das Verhalten
    dahinter (Zustellung, Protokoll-Eintrag, Warnung). Ohne diese Injektion
    ist der Zweig heute nicht auf Fehler zu bringen; genau deshalb ist die
    Absicherung strukturell und braucht einen eigenen Waechter.

    Positivkontrolle im selben Test: derselbe Aufbau OHNE Defekt traegt die
    Groessen sehr wohl -- sonst waere die Absenz oben nur ein durchgehend
    leerer Pfad statt der Wirkung des Defekts."""
    import logging as _logging

    from services import alert_log as alert_log_mod

    from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
    from tests.tdd.test_952_onset_alert_fidelity import _clean_user
    from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (
        _AT, _radar_trip, _settings_all_channels,
    )
    from tests.tdd.test_alert_log_mandanten_und_altbestand import (
        _FixedRadar, _entry_for,
    )

    _SECHS = (
        "lead_time_minutes", "event_at", "event_end_at",
        "measurement_point", "reference_at", "source",
    )
    uid_defekt, uid_ok = _uid("ac15-defekt"), _uid("ac15-ok")
    try:
        # --- Lauf MIT Defekt: zwei Trips desselben Nutzers ---------------
        trip_a = _radar_trip(uid_defekt, "trip-2050-s6-ac15-a", send_email=True)
        trip_b = _radar_trip(uid_defekt, "trip-2050-s6-ac15-b", send_email=True)

        def _wirft(*_args, **_kwargs):
            raise RuntimeError("defekte E-1-Ableitung (Fehler-Injektion AC-15)")

        monkeypatch.setattr(alert_log_mod, "nowcast_event_end_at", _wirft)
        strecke = AlarmPruefstrecke(user_id=uid_defekt, settings=_settings_all_channels())
        with caplog.at_level(_logging.WARNING, logger="services.trip_alert"):
            caplog.clear()
            lauf = strecke.lauf(
                at=_AT, zweig="radar", trip=trip_a,
                radar_service=_FixedRadar(onset_minutes=12, event_end_minutes=45),
            )
        assert lauf.triggered_count == 2, (
            f"AC-15: BEIDE Trips muessen trotz der defekten Ableitung alarmieren "
            f"-- ein Protokollfehler darf weder den eigenen Alarm verhindern noch "
            f"die restlichen Trips des Nutzers mitreissen (war {lauf.triggered_count})."
        )
        for trip in (trip_a, trip_b):
            entry = _entry_for(uid_defekt, trip.id)
            assert entry.get("channels_sent"), (
                f"AC-15: der Alarm fuer {trip.id} muss zugestellt und vollstaendig "
                f"protokolliert werden: {entry!r}"
            )
            for schluessel in _SECHS:
                assert schluessel not in entry, (
                    f"AC-15: nach dem Defekt darf {schluessel!r} nicht im Eintrag "
                    f"stehen (fail-soft zu Absenz, nicht zu einem Ratewert): {entry!r}"
                )
        gemeldet = " ".join(r.getMessage() for r in caplog.records)
        for trip in (trip_a, trip_b):
            assert trip.id in gemeldet, (
                f"AC-15: der Defekt muss LAUT verworfen werden -- eine Warnung mit "
                f"{trip.id!r} fehlt. Sonst behauptete das Protokoll 'diese Groessen "
                f"gab es hier nicht', wo ein Defekt vorlag. Log: {gemeldet!r}"
            )

        # --- Positivkontrolle: derselbe Aufbau OHNE Defekt ---------------
        monkeypatch.undo()
        trip_c = _radar_trip(uid_ok, "trip-2050-s6-ac15-c", send_email=True)
        strecke_ok = AlarmPruefstrecke(user_id=uid_ok, settings=_settings_all_channels())
        with caplog.at_level(_logging.WARNING, logger="services.trip_alert"):
            caplog.clear()
            lauf_ok = strecke_ok.lauf(
                at=_AT, zweig="radar", trip=trip_c,
                radar_service=_FixedRadar(onset_minutes=12, event_end_minutes=45),
            )
        assert lauf_ok.triggered_count == 1
        ohne_defekt = [r.getMessage() for r in caplog.records
                       if "nicht ableitbar" in r.getMessage()]
        assert not ohne_defekt, (
            f"AC-15 Gegenprobe: ein fehlerfreier Lauf darf KEINE "
            f"'nicht ableitbar'-Warnung erzeugen -- sonst zeigt die Warnung oben "
            f"nicht den Fehlerfall an, sondern erscheint immer und ginge im "
            f"Betrieb im Rauschen unter. Log: {ohne_defekt!r}"
        )
        entry_ok = _entry_for(uid_ok, trip_c.id)
        assert entry_ok.get("lead_time_minutes") == 12 and "event_end_at" in entry_ok, (
            f"AC-15 Positivkontrolle: ohne Defekt MUESSEN die Groessen entstehen -- "
            f"sonst zeigt ihre Absenz oben nur einen leeren Pfad: {entry_ok!r}"
        )
    finally:
        for uid in (uid_defekt, uid_ok):
            _clean_user(uid)
        _aufraeumen()
