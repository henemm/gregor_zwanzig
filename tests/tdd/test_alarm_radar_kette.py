"""TDD RED — Issue #2422 Scheibe S4, Bein Radar-Alarm: Kanal-Auflösung +
Schwelle über alle vier Kanäle (AC-2) und der Negativ-Test zu
`alert_metric_channels` bei Radar UND amtlich (AC-8).

SPEC: docs/specs/modules/fix_2422_s4_alarm_familie_kette.md (AC-2, AC-8).

Radar teilt sich `_dispatch_alert_message`/`_effective_alert_channels` mit dem
Abweichungsalarm (`test_alarm_abweichung_kette.py`) — kein Kanal darf bei
Radar anders behandelt werden. `check_radar_alerts()` liest seine Trips
SELBST von der Platte (`load_all_trips`, kein `trip`-Parameter) — die
Golden-Fixture muss deshalb VOR dem Lauf über `app.loader.save_trip()`
geschrieben sein (dasselbe Muster wie
`test_alarm_szenario_ein_ereignis_ein_alarm.py::_trip_delta_und_radar`).

Beide ACs sind heute bereits GRÜN (Charakterisierung bzw. Negativ-Test) —
AC-8 schützt explizit dagegen, eine fehlende Metrik-Kanal-Trennung bei
Radar/amtlich künftig fälschlich als Defekt zu melden.
"""
from __future__ import annotations

import uuid
from datetime import timedelta

from freezegun import freeze_time

from app.loader import save_trip
from app.models import TripReportConfig

from tests.tdd._alarm_amtlich_fixtures import (
    amtliche_warnung, segmentgeometrie, stelle_amtliche_quelle,
    stelle_cache_fuer_amtliche_kette,
)
from tests.tdd.test_952_onset_alert_fidelity import _clean_user, _trip_with_active_segment
from tests.tdd.test_alarm_abweichung_kette import _AT, _kanaele, _strecke
from tests.tdd.test_alarm_amtliche_warnungen_kette import _lauf_amtliche_kette
from tests.tdd.test_alarm_szenario_briefing_ueberholung_zeitreihe import _radar
from tests.tdd.test_daily_budget_escalation import RATE_MODERAT_MM_H, _quelle


def _uid(tag: str) -> str:
    return f"tdd-2422s4-{tag}-{uuid.uuid4().hex[:6]}"


def _radar_trip(uid: str, trip_id: str, **overrides):
    """Trip mit garantiert aktivem Segment JETZT (Vorbild
    `test_alarm_szenario_ein_ereignis_ein_alarm.py::_trip_delta_und_radar`) —
    über `app.loader.save_trip()` geschrieben, weil `check_radar_alerts()`
    seine Trips selbst per `load_all_trips()` von der Platte liest."""
    config = TripReportConfig(
        trip_id=trip_id, alert_on_changes=True, send_email=True, send_telegram=True,
    )
    with freeze_time(_AT):
        trip = _trip_with_active_segment(trip_id, config)
    for feld, wert in overrides.items():
        setattr(trip, feld, wert)
    with freeze_time(_AT):
        save_trip(trip, user_id=uid)
    return trip


# ═══════════════════════════ AC-2 ════════════════════════════════════════════


def test_radar_kanalmatrix_und_schwelle_konsistent():
    """AC-2 (Charakterisierung, heute GRÜN). GIVEN ein geladener Trip mit
    `alert_channels` (drei von vier Kanälen: E-Mail, Telegram, SMS) und einer
    `alert_channel_thresholds`-Schwelle auf Telegram (HIGH), die den
    nicht-konvektiven Radar-Auslöser (MODERATE) knapp unterschreitet, sowie
    eine Gegenprobe mit KONVEKTIVEM Radar (HIGH), die sie knapp überschreitet
    / WHEN der Radar-Alarm über dieselbe Prüfstrecke ausgelöst wird / THEN
    bleibt Telegram im ersten Fall aus (E-Mail/SMS bedient), im zweiten Fall
    bedient der Aufzeichner alle drei eingeschalteten Kanäle — kein Kanal
    wird bei Radar anders behandelt als bei Abweichung (dieselbe
    `_effective_alert_channels`/`split_by_threshold`-Kette).
    """
    uid_niedrig, uid_hoch = _uid("ac2-niedrig"), _uid("ac2-hoch")
    try:
        kanaele = {"email": True, "telegram": True, "sms": True}
        schwelle = {"telegram": "HIGH"}

        strecke_niedrig = _strecke(uid_niedrig)
        trip_niedrig = _radar_trip(
            uid_niedrig, "trip-ac2-niedrig",
            alert_channels=kanaele, alert_channel_thresholds=schwelle,
        )
        niedrig = strecke_niedrig.lauf(
            at=_AT, zweig="radar", trip=trip_niedrig,
            radar_service=_radar(_quelle(RATE_MODERAT_MM_H, konvektiv=False)),
        )
        assert niedrig.triggered_count == 1, (
            f"AC-2 Vorbedingung: der nicht-konvektive Radar-Alarm muss "
            f"trotz der Telegram-Schwelle ausliefern (E-Mail/SMS bleiben "
            f"erlaubt), war {niedrig.triggered_count}."
        )
        assert _kanaele(niedrig) == {"mail": 1, "telegram": 0, "sms": 1, "premium_sms": 0}, (
            f"AC-2: MODERATE unterschreitet die Telegram-Schwelle HIGH — "
            f"Telegram muss aussen vor bleiben: {_kanaele(niedrig)!r}"
        )

        strecke_hoch = _strecke(uid_hoch)
        trip_hoch = _radar_trip(
            uid_hoch, "trip-ac2-hoch",
            alert_channels=kanaele, alert_channel_thresholds=schwelle,
        )
        hoch = strecke_hoch.lauf(
            at=_AT, zweig="radar", trip=trip_hoch,
            radar_service=_radar(_quelle(RATE_MODERAT_MM_H, konvektiv=True)),
        )
        assert _kanaele(hoch) == {"mail": 1, "telegram": 1, "sms": 1, "premium_sms": 0}, (
            f"AC-2 Gegenprobe: HIGH (konvektiv) überschreitet dieselbe "
            f"Telegram-Schwelle — alle drei eingeschalteten Kanäle müssen "
            f"jetzt bedient werden: {_kanaele(hoch)!r}"
        )
    finally:
        _clean_user(uid_niedrig)
        _clean_user(uid_hoch)


# ═══════════════════════════ AC-8 ════════════════════════════════════════════


def test_alert_metric_channels_wirkt_nicht_bei_radar_und_amtlich(monkeypatch):
    """AC-8 (Negativ-Test, heute GRÜN). GIVEN ein geladener Trip mit
    `alert_metric_channels` gesetzt / WHEN ein Radar-Alarm UND eine amtliche
    Warnung ausgelöst werden / THEN wird `alert_metric_channels` bei BEIDEN
    NICHT ausgewertet — Gegenprobe mit identischem `alert_metric_channels`-
    Wert, aber unverändertem Ergebnis gegenüber einem Lauf ohne dieses Feld
    (`_effective_alert_channels(trip)` ohne `metrics=`-Kwarg an beiden
    Aufrufstellen, trip_alert.py:1671 bzw. :2732). Schützt gegen den
    Fehlschluss, dass fehlende Metrik-Kanal-Trennung bei Radar/amtlich ein
    Defekt wäre.
    """
    metrik_override = {"precipitation_sum": {"telegram": True, "premium_sms": True}}
    kanaele = {"email": True, "sms": True}

    # --- Radar-Hälfte ---
    uid_ohne, uid_mit = _uid("ac8-radar-ohne"), _uid("ac8-radar-mit")
    try:
        strecke_ohne = _strecke(uid_ohne)
        trip_ohne = _radar_trip(uid_ohne, "trip-ac8-radar-ohne", alert_channels=kanaele)
        ohne = strecke_ohne.lauf(
            at=_AT, zweig="radar", trip=trip_ohne,
            radar_service=_radar(_quelle(RATE_MODERAT_MM_H)),
        )

        strecke_mit = _strecke(uid_mit)
        trip_mit = _radar_trip(
            uid_mit, "trip-ac8-radar-mit",
            alert_channels=kanaele, alert_metric_channels=metrik_override,
        )
        mit = strecke_mit.lauf(
            at=_AT, zweig="radar", trip=trip_mit,
            radar_service=_radar(_quelle(RATE_MODERAT_MM_H)),
        )

        assert _kanaele(ohne) == _kanaele(mit), (
            f"AC-8 (Radar): alert_metric_channels darf das Ergebnis NICHT "
            f"verändern: ohne={_kanaele(ohne)!r} mit={_kanaele(mit)!r}"
        )
        assert _kanaele(mit) == {"mail": 1, "telegram": 0, "sms": 1, "premium_sms": 0}, (
            f"AC-8 (Radar) Vorbedingung: ohne Metrik-Wirkung bleibt es beim "
            f"regulären Kanal-Set {kanaele!r}: {_kanaele(mit)!r}"
        )
    finally:
        _clean_user(uid_ohne)
        _clean_user(uid_mit)

    # --- Amtlich-Hälfte ---
    uid_o, uid_m = _uid("ac8-amtlich-ohne"), _uid("ac8-amtlich-mit")
    try:
        alert = amtliche_warnung(3, von=_AT - timedelta(hours=1), bis=_AT + timedelta(hours=6))
        stelle_amtliche_quelle(monkeypatch, [alert])
        stelle_cache_fuer_amtliche_kette(monkeypatch, route_geometrie=segmentgeometrie(_AT))

        notices_o, geliefert_o, mit_o = _lauf_amtliche_kette(
            monkeypatch, uid_o, "golden_amtlich_fall1", at=_AT, alert_channels=kanaele,
        )
        notices_m, geliefert_m, mit_m = _lauf_amtliche_kette(
            monkeypatch, uid_m, "golden_amtlich_fall1", at=_AT, alert_channels=kanaele,
            alert_metric_channels=metrik_override,
        )

        assert notices_o and notices_m, (
            f"AC-8 (amtlich) Vorbedingung: beide Läufe müssen die injizierte "
            f"Warnung finden: ohne={notices_o!r} mit={notices_m!r}"
        )
        assert geliefert_o and geliefert_m, (
            f"AC-8 (amtlich) Vorbedingung: beide Läufe müssen ausliefern: "
            f"ohne={geliefert_o!r} mit={geliefert_m!r}"
        )
        assert _kanaele(mit_o) == _kanaele(mit_m), (
            f"AC-8 (amtlich): alert_metric_channels darf das Ergebnis NICHT "
            f"verändern: ohne={_kanaele(mit_o)!r} mit={_kanaele(mit_m)!r}"
        )
    finally:
        _clean_user(uid_o)
        _clean_user(uid_m)
