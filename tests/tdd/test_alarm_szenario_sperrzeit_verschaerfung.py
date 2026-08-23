"""Issue #2050 Scheibe S3a — Waechter Sz 4 (A-3): Verschaerfung ueberholt

die Sperrzeit auch im Aenderungs-Zweig (seit #2050 S3c).

SPEC: docs/specs/modules/alarm_szenarien_waechter_4_9_11.md (AC-1, AC-2)
      docs/specs/modules/feat_2050_s3c_abweichung_ueberholt_sperrzeit.md (AC-1)

Der Radar-Zweig-Nachweis fuer dieselbe Anforderung A-3 ist durch
`tests/tdd/test_radar_cooldown_overtake.py` (Issue #2065) erbracht: eine
quantitative Verschaerfung UEBERHOLT dort die Sperrzeit. S3a hielt hier
zunaechst den GEGENSATZ im Aenderungs-Zweig fest; seit S3c gilt dort
dieselbe Anforderung, mit einem ordinalen Rangvergleich
(`alert_urgency.exceeds`) statt einer Faktor-Formel.

Der Nachweis laeuft ueber den Sperrzeit-Zeitstempel in `ThrottleStore` und
nicht ueber das Protokoll: der Aenderungs-Zweig schreibt bei einem
DURCHBRUCH ohnehin einen normalen Zustell-Eintrag, und der Zeitstempel zeigt
unmittelbar, ob die Sperrzeit neu gebucht wurde.

ABLOESUNG (Issue #2050 Scheibe S3c, 2026-08-23): AC-2 sicherte hier zu, dass
eine Verschaerfung innerhalb der Sperrzeit IMMER ohne Alarm bleibt -- als
bewusst festgehaltener IST-Zustand, nicht als Soll. Die Datei kuendigte die
eigene AblOese bereits an. S3c hat die Luecke geschlossen: eine Verschaerfung,
die die gespeicherte Vergleichsdringlichkeit im RANG uebersteigt, ueberholt
die Sperrzeit jetzt auch im Aenderungs-Zweig. AC-2 unten ist deshalb
UMGESCHRIEBEN, nicht geloescht -- dieselbe Flaeche prueft heute das Gegenteil.
Das ist eine bewusste Ablsoese, KEIN entfernter Schutz: die Gegenproben gegen
eine zu weite Loesung stehen in
`docs/specs/modules/feat_2050_s3c_abweichung_ueberholt_sperrzeit.md` (AC-2 bis
AC-5) und in `tests/tdd/test_alarm_pruefstrecke_selbstschutz.py` (AC-1/AC-7,
unveraendert gruen).

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


def test_ac2_verschaerfung_innerhalb_der_sperrzeit_ueberholt_seit_s3c():
    """AC-2: dieselbe Sperrzeit ist noch aktiv (aus Lauf 1 gebucht); Lauf 2
    bietet eine gegenueber Lauf 1 NOCHMALS deutlich verschaerfte Lage --
    und ueberholt die Sperrzeit. Wie im Radar-Zweig
    (`test_radar_cooldown_overtake.py`, Issue #2065) gibt es im
    Aenderungs-Zweig seit S3c eine Eskalations-Ausnahme.

    🔴 ABGELOESTE ZUSICHERUNG: bis Scheibe S3c (#2050, 2026-08-23) hielt
    dieser Test den IST-Zustand fest -- `triggered_count == 0` und ein
    UNVERAENDERTER Sperrzeit-Zeitstempel, weil `check_and_send_alerts()` an
    der Sperrzeit hart abbrach, BEVOR ueberhaupt eine Schwere gebildet wurde.
    Der PO-Entscheid vom 2026-08-22 verlangte auch hier die Ueberholung
    (Anforderung A-3, Szenario 4); S3c hat sie gebaut, und damit kehrt sich
    die Erwartung dieses Tests um. Das ist eine bewusste Ablsoese, kein
    entfernter Schutz -- die Gegenproben gegen eine zu weite Loesung
    (identische Wiederholung, abgeschwaechte Lage, fehlende Vergleichsbasis)
    stehen in `tests/tdd/test_deviation_cooldown_overtake.py` (AC-2 bis AC-5)
    und in `tests/tdd/test_alarm_pruefstrecke_selbstschutz.py` (AC-1/AC-7).
    SPEC der Ablsoese:
    `docs/specs/modules/feat_2050_s3c_abweichung_ueberholt_sperrzeit.md`."""
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
        # jetzt 2.0 -> 45.0). Gemessen ergibt Lauf 1 den Rang MODERATE und
        # Lauf 2 den Rang HIGH -- ein ECHTER Rangsprung, den S3c als
        # Ueberholung wertet.
        at2 = _AT + timedelta(minutes=30)
        lauf2 = strecke.lauf(
            at=at2, zweig="deviation", trip=trip,
            cached_weather=[_weather_data(precip_sum_mm=2.0)],
            fresh_weather=[_weather_data(precip_sum_mm=45.0)],
        )
        assert lauf2.triggered_count == 1, (
            f"AC-2 (seit S3c): der Aenderungs-Zweig kennt eine "
            f"Eskalations-Ausnahme -- die nochmals verschaerfte Lage (Rang "
            f"HIGH gegen die gebuchte Basis MODERATE) muss die laufende "
            f"Sperrzeit ueberholen. War triggered_count={lauf2.triggered_count}."
        )

        gebucht_nach_lauf2 = ThrottleStore(uid).last_sent("trip", trip.id)
        assert (
            gebucht_nach_lauf2 is not None
            and gebucht_nach_lauf2 > gebucht_nach_lauf1
        ), (
            f"AC-2 (seit S3c): der Sperrzeit-Zeitstempel muss durch Lauf 2 NEU "
            f"gebucht sein -- das ist der Nachweis, dass der Durchbruch "
            f"tatsaechlich bis zur Buchung durchlief und nicht bloss ein "
            f"anderer Zaehler ansprang (vorher {gebucht_nach_lauf1!r}, nachher "
            f"{gebucht_nach_lauf2!r})."
        )
    finally:
        _clean_user(uid)
