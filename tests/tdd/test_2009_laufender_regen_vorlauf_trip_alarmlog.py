"""TDD RED — Issue #2009 (Nachmessung): laufender Regen im Trip-Alarmlog.

SPEC: docs/specs/modules/fix_2009_laufender_regen_vorlauf.md
      (Waechter 1 = AC-1, Zwei-Nutzer-Lauf = AC-8, Waechter 5 = AC-5)

Laeuft der Regen zum Zeitpunkt des Laufs bereits (das laufende Frame ist
nass, `already_running`), protokolliert der Trip-Radar-Zweig heute als
Vorlauf `onset_minutes` -- die Minuten bis zum NAECHSTEN nassen Frame (im
5-Min-Takt `3-58/5` gegen das 15-Min-Raster 2, 7 oder 12) -- und als Beginn
den naechsten Viertelstundenpunkt. Richtig ist: Vorlauf 0, Beginn = Zeitpunkt
des Laufs.

Echter Pfad, kein Mock()/patch()/MagicMock: `check_radar_alerts()` ueber die
`AlarmPruefstrecke` (#2050 S1), Frames ueber die DI-Naht `frame_source=` eines
echten `RadarNowcastService`, gelesen wird der echte Alarmlog
(`alert_log.json`) unter der Datenwurzel des jeweiligen Nutzers. Die Uhr ist
gestellt (`freeze_time` in der Pruefstrecke), kein Netz.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from freezegun import freeze_time

from services.radar_service import RadarNowcastService

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
from tests.helpers.nowcast_gate_fixtures import read_log
from tests.tdd.test_952_onset_alert_fidelity import _clean_user
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (
    _AT, _radar_trip, _settings_all_channels, _write_premium_profile,
)

# Laufender Rasterslot (INCA-Raster :00/:15/:30/:45) und ein Laufzeitpunkt IM
# Takt `3-58/5` (internal/scheduler/scheduler.go): 10:08 UTC = 12:08 Ortszeit
# Korsika. Literal, nicht aus dem Pruefling gelesen.
_SLOT = _AT                                  # 10:00 UTC
_LAUF = _SLOT + timedelta(minutes=8)         # 10:08 UTC, Taktminute :08
_NAECHSTER_VIERTELSTUNDENPUNKT = _SLOT + timedelta(minutes=15)   # 10:15 UTC

_ANGELEGT: list[str] = []


@pytest.fixture(autouse=True)
def _aufraeumen():
    _ANGELEGT.clear()
    yield
    for uid in _ANGELEGT:
        _clean_user(uid)


def _uid(tag: str) -> str:
    uid = f"tdd-2009-laufend-{tag}-{uuid.uuid4().hex[:6]}"
    _ANGELEGT.append(uid)
    return uid


def _quelle(*, anker: datetime, nass, gesamt: int = 13, rate: float = 2.0):
    """Echte `RadarFrame`-Reihe im 15-Min-Abstand ab `anker`; `nass(k)`
    entscheidet, welche Frames ueber der Trockenschwelle (0,1 mm/h) liegen."""
    def _frames(lat: float, lon: float) -> list:
        from providers.brightsky import RadarFrame
        return [
            RadarFrame(
                timestamp=anker + timedelta(minutes=15 * k),
                precip_mm_h=rate if nass(k) else 0.0,
            )
            for k in range(gesamt)
        ]
    return _frames


def _laeuft_bereits():
    """Laufendes Frame (10:00) UND naechstes Frame (10:15) nass, Ende 10:45.

    Damit ist `onset_minutes` NICHT `None` (das naechste nasse Frame liegt
    7 Min nach dem Lauf) -- genau der Fall, in dem heute 7 statt 0 im Log
    steht. (Der Fall "endet im laufenden Slot", `onset_minutes is None`, ist
    seit #2050 S2b schon richtig und wird hier bewusst nicht benutzt.)"""
    return _quelle(anker=_SLOT, nass=lambda k: k < 3)


def _aufbau(uid: str, trip_id: str):
    """Nutzer mit Premium-Profil (alle vier Kanaele) + Trip mit aktivem
    Segment, aufgebaut unter der gestellten Uhr (Compute-on-Save, #802)."""
    _clean_user(uid)
    _write_premium_profile(uid, _AT)
    with freeze_time(_AT):
        return _radar_trip(
            uid, trip_id, send_email=True, send_telegram=True,
            send_sms=True, send_premium_sms=True,
        )


def _lauf(uid: str, trip, quelle, *, at: datetime = _LAUF):
    strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
    return strecke.lauf(
        at=at, zweig="radar", trip=trip,
        radar_service=RadarNowcastService(frame_source=quelle),
    )


def _versand_eintraege(uid: str, trip_id: str) -> list[dict]:
    """Die Alarmlog-Eintraege eines ZUGESTELLTEN Radar-Alarms dieses Trips."""
    return [
        e for e in read_log(uid)["entries"]
        if e.get("entity_id") == trip_id and e.get("reason") == "nowcast"
    ]


def _zeit(raw) -> datetime | None:
    if raw is None:
        return None
    ts = datetime.fromisoformat(str(raw))
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def _einziger_eintrag(uid: str, trip_id: str, lauf, waechter: str) -> dict:
    assert lauf.triggered_count == 1, (
        f"{waechter} Vorbedingung: der Lauf muss ausloesen, sonst prueft der "
        f"Alarmlog nichts (triggered_count={lauf.triggered_count})."
    )
    eintraege = _versand_eintraege(uid, trip_id)
    assert len(eintraege) == 1, (
        f"{waechter} Vorbedingung: genau EIN Versand-Eintrag im Alarmlog von "
        f"{uid} erwartet, gefunden {len(eintraege)}: {eintraege!r}"
    )
    return eintraege[0]


# ═══════════════════════════ Waechter 1 (AC-1) ═════════════════════════════


def test_waechter1_laufender_regen_trip_alarmlog_vorlauf_null_beginn_jetzt():
    """AC-1: laufendes und naechstes Frame nass, Lauf im 5-Min-Takt (10:08)
    -> Alarmlog: `lead_time_minutes == 0`, `event_at` == Lauf-Zeitpunkt
    (10:08), NICHT der naechste Viertelstundenpunkt (10:15)."""
    uid = _uid("w1")
    trip_id = "trip-2009-w1"
    trip = _aufbau(uid, trip_id)
    lauf = _lauf(uid, trip, _laeuft_bereits())
    eintrag = _einziger_eintrag(uid, trip_id, lauf, "Waechter 1")

    assert eintrag.get("lead_time_minutes") == 0, (
        f"AC-1: bei bereits laufendem Regen muss der Vorlauf 0 sein, "
        f"protokolliert ist lead_time_minutes={eintrag.get('lead_time_minutes')!r} "
        f"(= Minuten bis zum naechsten Frame, Mess-Artefakt)."
    )
    beginn = _zeit(eintrag.get("event_at"))
    assert beginn != _NAECHSTER_VIERTELSTUNDENPUNKT, (
        f"AC-1: der Beginn ist der naechste Viertelstundenpunkt "
        f"({_NAECHSTER_VIERTELSTUNDENPUNKT.isoformat()}) -- der wandert mit "
        f"jedem Lauf und ist nicht der Beginn eines laufenden Regens."
    )
    assert beginn == _LAUF, (
        f"AC-1: Beginn muss der Lauf-Zeitpunkt {_LAUF.isoformat()} sein, "
        f"protokolliert ist event_at={eintrag.get('event_at')!r}."
    )


# ═══════════════════════════ AC-8 (Zwei Nutzer) ════════════════════════════


def test_ac8_zwei_nutzer_je_eigener_alarmlog_keine_fremde_entdopplung():
    """AC-8: zwei verschiedene Nutzer, je ein Trip mit DERSELBEN Trip-Kennung
    und derselben laufenden Lage, nacheinander zum selben Zeitpunkt.

    Dieselbe Trip-Kennung ist Absicht: wirkten Alarmlog oder Entdopplung
    nutzeruebergreifend (Schluessel nur ueber die Entitaet), unterdrueckte
    der erste Nutzer den zweiten oder schriebe in dessen Log. Jeder Nutzer
    muss seinen Alarm bekommen, und jeder Log traegt genau seinen Eintrag mit
    Vorlauf 0 und Beginn = Lauf-Zeitpunkt."""
    trip_id = "trip-2009-ac8"
    nutzer_a, nutzer_b = _uid("ac8-a"), _uid("ac8-b")
    assert nutzer_a != nutzer_b and "default" not in (nutzer_a, nutzer_b)
    trip_a = _aufbau(nutzer_a, trip_id)
    trip_b = _aufbau(nutzer_b, trip_id)

    lauf_a = _lauf(nutzer_a, trip_a, _laeuft_bereits())
    lauf_b = _lauf(nutzer_b, trip_b, _laeuft_bereits())
    assert lauf_b.triggered_count == 1, (
        f"AC-8: die Entdopplung von Nutzer A darf den Alarm von Nutzer B nicht "
        f"unterdruecken (B: triggered_count={lauf_b.triggered_count})."
    )

    for uid, lauf in ((nutzer_a, lauf_a), (nutzer_b, lauf_b)):
        eintrag = _einziger_eintrag(uid, trip_id, lauf, f"AC-8 ({uid})")
        assert eintrag.get("lead_time_minutes") == 0, (
            f"AC-8 ({uid}): Vorlauf im eigenen Alarmlog muss 0 sein, ist "
            f"{eintrag.get('lead_time_minutes')!r}."
        )
        assert _zeit(eintrag.get("event_at")) == _LAUF, (
            f"AC-8 ({uid}): Beginn im eigenen Alarmlog muss {_LAUF.isoformat()} "
            f"sein, ist {eintrag.get('event_at')!r}."
        )


# ═══════════════════════════ Waechter 5 (AC-5) ═════════════════════════════


def test_waechter5_gegenprobe_trockenes_vorframe_vorlauf_bleibt_acht():
    """AC-5 (Gegenprobe, BEWUSST schon heute gruen): das Frame, das den Lauf
    abdeckt, ist TROCKEN, der Regen beginnt in 8 Minuten -> der Vorlauf
    bleibt 8 und der Beginn ist der Frame-Zeitpunkt. Schuetzt davor, dass die
    Korrektur jeden Vorlauf auf 0 setzt.

    Das Raster ist hier um 1 Min versetzt (:01/:16/...), damit ein Vorlauf
    von genau 8 Min im Takt `3-58/5` erreichbar ist -- gegen das INCA-Raster
    :00/:15 sind nur 2/7/12 moeglich (Waechter 6)."""
    anker = _SLOT + timedelta(minutes=1)                 # 10:01 UTC, trocken
    regenbeginn = anker + timedelta(minutes=15)          # 10:16 UTC, nass
    uid = _uid("w5")
    trip_id = "trip-2009-w5"
    trip = _aufbau(uid, trip_id)
    lauf = _lauf(uid, trip, _quelle(anker=anker, nass=lambda k: 1 <= k <= 3))
    eintrag = _einziger_eintrag(uid, trip_id, lauf, "Waechter 5")

    assert eintrag.get("lead_time_minutes") == 8, (
        f"AC-5: trockenes Vorframe, Regen in 8 Min -> Vorlauf 8, protokolliert "
        f"ist {eintrag.get('lead_time_minutes')!r}."
    )
    assert _zeit(eintrag.get("event_at")) == regenbeginn, (
        f"AC-5: Beginn muss der Frame-Zeitpunkt {regenbeginn.isoformat()} sein, "
        f"ist {eintrag.get('event_at')!r}."
    )
