"""Issue #2050 Scheibe S3a — Waechter Sz 4 (A-3): Verschaerfung ueberholt

Sperrzeit NICHT im Aenderungs-Zweig (Kontrast zum Radar-Zweig).

SPEC: docs/specs/modules/alarm_szenarien_waechter_4_9_11.md (AC-1, AC-2)

Der Radar-Zweig-Nachweis fuer dieselbe Anforderung A-3 ist bereits
vollstaendig durch `tests/tdd/test_radar_cooldown_overtake.py` (Issue #2065)
erbracht: eine quantitative Verschaerfung UEBERHOLT dort die Sperrzeit. Dieser
Waechter belegt den GEGENSATZ im Aenderungs-Zweig: `_is_throttled_with_cooldown`
(`trip_alert.py:306-308`) gibt bedingungslos `False` zurueck, BEVOR ueberhaupt
eine Verschaerfung geprueft wuerde -- eine noch so deutliche Zuspitzung
gegenueber Lauf 1 aendert daran nichts.

Der Aenderungs-Zweig schreibt bei dieser Unterdrueckung KEINEN `alert_log`-
Eintrag (kein `append_suppressed_entry`-Aufruf an dieser Stelle, anders als
der Radar-Zweig via `_protokolliere_radar_unterdrueckung`) -- der Nachweis
laeuft deshalb ueber den UNVERAENDERTEN Sperrzeit-Zeitstempel in
`ThrottleStore`, nicht ueber das Protokoll.

WICHTIG -- dieser Waechter haelt den IST-ZUSTAND fest, nicht das Soll:
Anforderung A-3 ("eine Verschaerfung ueberholt jede Sperre") gilt laut
PO-Entscheid vom 2026-08-22 (Issue #2050) AUCH im Aenderungs-Zweig, nicht nur
im Radar-Zweig. Heute gibt es die Ausnahme dort nicht (`trip_alert.py:306-308`,
harter `return False` ohne jede Schweregrad-Pruefung). Geschlossen wird die
Luecke durch Scheibe S3c (#2050); mit ihr KEHRT SICH AC-2 UM und muss dann
mit-umgeschrieben werden -- ein rot werdendes AC-2 ist nach S3c also der
erwartete Befund, keine Regression.

Beide Laeufe ueber `AlarmPruefstrecke` (#2050 S1) gegen die ECHTE
Ausloeseentscheidung `TripAlertService.check_and_send_alerts()`. Kein
Mock()/patch()/MagicMock.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from services.throttle_store import ThrottleStore

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
from tests.tdd.test_952_onset_alert_fidelity import _clean_user
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (
    _settings_all_channels, _write_tier,
)
from tests.tdd.test_issue_1070_daily_alert_limit import _deviation_trip, _weather_data

_AT = datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc)


def _uid(tag: str) -> str:
    return f"tdd-2050-s3a-sz4-{tag}-{uuid.uuid4().hex[:6]}"


def test_ac1_deutliche_verschaerfung_ohne_vorbelegte_sperrzeit_loest_aus_und_bucht():
    """AC-1: Trip ohne vorbelegte Sperrzeit, alarmwuerdiges Delta im
    Aenderungs-Zweig -> genau ein Alarm, Sperrzeit wird gebucht.

    Positivkontrolle fuer AC-2: ohne diesen Nachweis waere unklar, ob die
    Verschaerfung selbst ueberhaupt ausloesefaehig ist."""
    uid = _uid("ac1")
    _clean_user(uid)
    try:
        _write_tier(uid, "premium")
        trip = _deviation_trip("trip-s3a-sz4-ac1")
        trip.alert_cooldown_minutes = 120
        cached = [_weather_data(precip_sum_mm=2.0)]
        fresh = [_weather_data(precip_sum_mm=18.0)]
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())

        lauf = strecke.lauf(
            at=_AT, zweig="deviation", trip=trip,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert lauf.triggered_count == 1, (
            f"AC-1: die alarmwuerdige Verschaerfung muss ueber die echte "
            f"Ausloeseentscheidung GENAU EINEN Alarm ergeben. War "
            f"triggered_count={lauf.triggered_count}."
        )

        gebucht = ThrottleStore(uid).last_sent("trip", trip.id)
        assert gebucht is not None, (
            "AC-1: nach dem Alarm muss die Sperrzeit fuer den Trip gebucht "
            "sein (ThrottleStore.last_sent lieferte None)."
        )
    finally:
        _clean_user(uid)


def test_ac2_verschaerfung_innerhalb_der_sperrzeit_bleibt_ohne_alarm():
    """AC-2: dieselbe Sperrzeit ist noch aktiv (aus Lauf 1 gebucht); Lauf 2
    bietet eine gegenueber Lauf 1 NOCHMALS deutlich verschaerfte Lage --
    trotzdem bleibt der Lauf ohne Alarm. Anders als im Radar-Zweig
    (`test_radar_cooldown_overtake.py`, Issue #2065) gibt es im
    Aenderungs-Zweig keine Eskalations-Ausnahme.

    Festgehalten wird damit der IST-Zustand, NICHT das Soll aus Anforderung
    A-3: nach dem PO-Entscheid vom 2026-08-22 (#2050) soll die Verschaerfung
    auch hier die Sperre ueberholen. Scheibe S3c (#2050) dreht das um und
    kehrt die Erwartung dieses Tests um (dann: `triggered_count == 1` und ein
    NEU gebuchter Sperrzeit-Zeitstempel)."""
    uid = _uid("ac2")
    _clean_user(uid)
    try:
        _write_tier(uid, "premium")
        trip = _deviation_trip("trip-s3a-sz4-ac2")
        trip.alert_cooldown_minutes = 120
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())

        lauf1 = strecke.lauf(
            at=_AT, zweig="deviation", trip=trip,
            cached_weather=[_weather_data(precip_sum_mm=2.0)],
            fresh_weather=[_weather_data(precip_sum_mm=18.0)],
        )
        assert lauf1.triggered_count == 1, (
            f"AC-2 Vorbedingung: Lauf 1 muss ausloesen und die Sperrzeit "
            f"buchen (war {lauf1.triggered_count})."
        )
        gebucht_nach_lauf1 = ThrottleStore(uid).last_sent("trip", trip.id)
        assert gebucht_nach_lauf1 is not None, (
            "AC-2 Vorbedingung: die Sperrzeit muss nach Lauf 1 gebucht sein."
        )

        # Lauf 2: innerhalb des Sperrfensters aus Lauf 1, mit einer GEGENUEBER
        # Lauf 1 nochmals deutlich verschaerften Lage (2.0 -> 18.0 in Lauf 1,
        # jetzt 2.0 -> 45.0 -- mehr als das Doppelte des Deltas aus Lauf 1).
        at2 = _AT + timedelta(minutes=30)
        lauf2 = strecke.lauf(
            at=at2, zweig="deviation", trip=trip,
            cached_weather=[_weather_data(precip_sum_mm=2.0)],
            fresh_weather=[_weather_data(precip_sum_mm=45.0)],
        )
        assert lauf2.triggered_count == 0, (
            f"AC-2: der Aenderungs-Zweig kennt keine Eskalations-Ausnahme -- "
            f"trotz der nochmals verschaerften Lage muss der Lauf innerhalb "
            f"der Sperrzeit still bleiben. War triggered_count={lauf2.triggered_count}."
        )

        gebucht_nach_lauf2 = ThrottleStore(uid).last_sent("trip", trip.id)
        assert gebucht_nach_lauf2 == gebucht_nach_lauf1, (
            f"AC-2: der Sperrzeit-Zeitstempel darf sich durch Lauf 2 nicht "
            f"veraendert haben -- das ist der Nachweis, dass der Cooldown-Gate "
            f"frueh griff, nicht dass zufaellig ein anderer Gate zuschlug "
            f"(vorher {gebucht_nach_lauf1!r}, nachher {gebucht_nach_lauf2!r})."
        )
    finally:
        _clean_user(uid)
