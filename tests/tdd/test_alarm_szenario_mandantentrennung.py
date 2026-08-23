"""Issue #2050 Scheibe S3a — Waechter Sz 11 (D-1/D-2): Mandantentrennung der

vier Alarm-Zustandsspeicher zwischen zwei Nutzern.

SPEC: docs/specs/modules/alarm_szenarien_waechter_4_9_11.md (AC-6..AC-9)

Kanonische Sequenz (sequenziell -- `radar_cache.py:73-84` ist ein
prozessweiter Cache OHNE `user_id`-Schluessel, echte Nebenlaeufigkeit ist
NICHT Ziel dieser Scheibe):

  1. Lauf A1 (zweig="deviation"): loest aus, bucht Sperrzeit, Tageszaehler
     und Melde-Gedaechtnis unter `get_data_dir(uid_a)`.
  2. Lauf B1 (zweig="deviation", uid_b): loest ebenso aus, bucht seine
     EIGENEN Speicher unter `get_data_dir(uid_b)`.
  3. Lauf B-Radar-1 (zweig="radar", uid_b): loest aus und bucht B's EIGENE
     Radar-Sperrzeit (Scope "radar" -- ein eigener Scope neben "trip", den
     Lauf B1 bucht, `throttle_store.py:36-55`).
  4. Lauf B2 (zweig="radar", uid_b, innerhalb der in Schritt 3 gebuchten
     Radar-Sperrzeit, UNVERAENDERTE Menge): wird unterdrueckt -- ohne
     Verschaerfung greift #2065s Ueberholungsregel nicht -- und schreibt
     einen `alert_log`-Unterdrueckungs-Eintrag fuer `uid_b`
     (`_protokolliere_radar_unterdrueckung`, `trip_alert.py:1181-1196`).

Nur der RADAR-Zweig protokolliert eine Cooldown-Unterdrueckung im
`alert_log` (Known Limitation der Spec: der Aenderungs-Zweig tut das nicht,
s. `test_alarm_szenario_sperrzeit_verschaerfung.py`) -- AC-9 (das
Unterdrueckungs-Protokoll) braucht deshalb zwingend den Radar-Zweig, und
"B's Sperrfenster" ist damit B's EIGENE radar-Sperrzeit aus Schritt 3, nicht
die des Aenderungs-Zweigs aus Schritt 2 (getrennter Scope).

Nach jedem B-Lauf wird A's Zustand in allen vier Speichern erneut gelesen
und mit dem Stand nach A1 verglichen -- muss unveraendert sein.

Zusaetzlich wird jeder von B gebuchte Schluessel EIN ZWEITES MAL gelesen,
diesmal unter A's Kennung (AC-7 die radar-Sperrzeit, AC-9 der
Unterdrueckungs-Vorfall zu B's radar-Trip). Erst diese Gegenlesung macht
AC-7/AC-9 eigenstaendig: bei einem faelschlich GETEILTEN `get_data_dir()`
bleiben A's eigene Werte naemlich unauffaellig -- B's Aenderungs-Lauf wird
dann von A's Sperrzeit gedrosselt und ueberschreibt gar nichts (dieses
Muster faengt AC-6/AC-8), waehrend B's radar-Buchung unter einem anderen
Schluessel liegt und A's Vergleich damit unberuehrt laesst.

Kein Mock()/patch()/MagicMock: beide Zweige ueber `AlarmPruefstrecke`
(#2050 S1) gegen die ECHTE Ausloeseentscheidung, echte Zustandsdateien unter
`get_data_dir(user_id)`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from services import alert_log
from services.alert_daily_limit import load as daily_limit_load
from services.alert_state import AlertStateService
from services.throttle_store import ThrottleStore
from services.trip_day import anchor_tz

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
from tests.tdd.test_952_onset_alert_fidelity import _clean_user
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (
    _radar_trip, _settings_all_channels, _write_tier,
)
from tests.tdd.test_alarm_szenario_briefing_ueberholung_zeitreihe import (
    _dauerregen, _radar,
)
from tests.tdd.test_issue_1070_daily_alert_limit import _deviation_trip, _weather_data

_AT = datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc)


def _uid(tag: str) -> str:
    return f"tdd-2050-s3a-sz11-{tag}-{uuid.uuid4().hex[:6]}"


def _cached_fresh():
    return [_weather_data(precip_sum_mm=2.0)], [_weather_data(precip_sum_mm=18.0)]


def _deviation_ausloeser(uid: str, trip_id: str = "trip-s3a-sz11"):
    """Ein deviation-Lauf, der garantiert ausloest und Sperrzeit,
    Tageszaehler und Melde-Gedaechtnis unter `get_data_dir(uid)` bucht."""
    _write_tier(uid, "premium")
    trip = _deviation_trip(trip_id)
    trip.alert_cooldown_minutes = 120
    cached, fresh = _cached_fresh()
    strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
    lauf = strecke.lauf(
        at=_AT, zweig="deviation", trip=trip,
        cached_weather=cached, fresh_weather=fresh,
    )
    return trip, lauf


def _b_radar_setup(uid: str):
    """B's erster radar-Lauf: loest aus und bucht B's EIGENE radar-Sperrzeit
    -- Vorbedingung fuer den unterdrueckten zweiten Lauf (`_b2`).

    Bewusst EINE Sekunde nach `_AT` (statt exakt `_AT`, dem Zeitpunkt von
    A1): sonst waeren A's und B's gebuchte Zeitstempel LITERAL identisch und
    die Positivkontrolle in AC-7 ("B's Zeitstempel unterscheidet sich von
    A's") koennte nie etwas pruefen."""
    _write_tier(uid, "premium")
    trip = _radar_trip(uid, "trip-s3a-sz11-radar", send_email=True, send_telegram=True)
    strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
    lauf = strecke.lauf(
        at=_AT + timedelta(seconds=1), zweig="radar", trip=trip,
        radar_service=_radar(_dauerregen(11.0)),
    )
    return trip, strecke, lauf


def _b2(uid: str, trip, strecke):
    """B's zweiter radar-Lauf, kurz danach, UNVERAENDERTE Menge (#2065: ohne
    Verschaerfung ueberholt nichts die Sperrzeit) -> wird unterdrueckt."""
    at2 = _AT + timedelta(minutes=5)
    return strecke.lauf(
        at=at2, zweig="radar", trip=trip, radar_service=_radar(_dauerregen(11.0)),
    )


def _sequenz(uid_a: str, uid_b: str) -> dict:
    """Faehrt die kanonische Vier-Lauf-Sequenz genau einmal und haelt A's
    Zustand in allen vier Speichern nach A1 UND nach der vollstaendigen
    B-Sequenz fest -- jeder AC-Test liest daraus, ohne die Sequenz erneut zu
    fahren."""
    trip_a, lauf_a1 = _deviation_ausloeser(uid_a)
    zone_a = anchor_tz(trip_a, _AT)
    snap_a_nach_a1 = dict(
        zaehler=daily_limit_load(uid_a, _AT, zone_a),
        sperrzeit=ThrottleStore(uid_a).last_sent("trip", trip_a.id),
        melde_gedaechtnis=AlertStateService(uid_a).load(trip_a.id),
    )

    trip_b1, lauf_b1 = _deviation_ausloeser(uid_b)
    radar_trip_b, strecke_b, lauf_radar1 = _b_radar_setup(uid_b)
    lauf_radar2 = _b2(uid_b, radar_trip_b, strecke_b)

    snap_a_danach = dict(
        zaehler=daily_limit_load(uid_a, _AT, zone_a),
        sperrzeit=ThrottleStore(uid_a).last_sent("trip", trip_a.id),
        melde_gedaechtnis=AlertStateService(uid_a).load(trip_a.id),
    )

    return dict(
        trip_a=trip_a, lauf_a1=lauf_a1,
        snap_a_nach_a1=snap_a_nach_a1, snap_a_danach=snap_a_danach,
        trip_b1=trip_b1, lauf_b1=lauf_b1,
        radar_trip_b=radar_trip_b, lauf_radar1=lauf_radar1, lauf_radar2=lauf_radar2,
    )


def test_ac6_tageszaehler_bleibt_je_nutzer_getrennt():
    """AC-6: A loest einmal aus, danach loest B ebenfalls aus (sequenziell,
    A dann B) -> A's Tageszaehler bleibt bei dem Stand, den A's eigener Lauf
    gesetzt hat."""
    uid_a, uid_b = _uid("ac6-a"), _uid("ac6-b")
    _clean_user(uid_a)
    _clean_user(uid_b)
    try:
        seq = _sequenz(uid_a, uid_b)
        assert seq["lauf_a1"].triggered_count == 1, "AC-6 Vorbedingung: A muss ausloesen"
        assert seq["snap_a_nach_a1"]["zaehler"] >= 1, (
            "AC-6 Vorbedingung: A's Tageszaehler muss nach A1 gestiegen sein "
            f"(war {seq['snap_a_nach_a1']['zaehler']})."
        )
        assert seq["lauf_b1"].triggered_count == 1, (
            "AC-6 Positivkontrolle Vorbedingung: B muss ebenfalls ausloesen "
            f"(war {seq['lauf_b1'].triggered_count})."
        )
        assert seq["snap_a_danach"]["zaehler"] == seq["snap_a_nach_a1"]["zaehler"], (
            f"AC-6: B's Ausloesungen duerfen A's Tageszaehler nicht "
            f"veraendern (vorher {seq['snap_a_nach_a1']['zaehler']}, "
            f"nachher {seq['snap_a_danach']['zaehler']})."
        )
        zone_b = anchor_tz(seq["trip_b1"], _AT)
        zaehler_b = daily_limit_load(uid_b, _AT, zone_b)
        assert zaehler_b >= 1, (
            "AC-6 Positivkontrolle: B's eigener Zaehler muss B's Buchung "
            f"zeigen (war {zaehler_b})."
        )
    finally:
        _clean_user(uid_a)
        _clean_user(uid_b)


def test_ac7_sperrzeit_bleibt_je_nutzer_getrennt():
    """AC-7: nach A's erstem Lauf (Sperrzeit gebucht) loest B aus und danach
    laeuft ein zweiter, unterdrueckter Lauf von B im selben Sperrfenster ->
    A's gebuchte Sperrzeit bleibt unveraendert."""
    uid_a, uid_b = _uid("ac7-a"), _uid("ac7-b")
    _clean_user(uid_a)
    _clean_user(uid_b)
    try:
        seq = _sequenz(uid_a, uid_b)
        assert seq["snap_a_nach_a1"]["sperrzeit"] is not None, (
            "AC-7 Vorbedingung: A muss die Sperrzeit gebucht haben."
        )
        assert seq["lauf_radar1"].triggered_count == 1, (
            "AC-7 Vorbedingung: B's erster radar-Lauf muss ausloesen und "
            f"seine EIGENE Sperrzeit buchen (war {seq['lauf_radar1'].triggered_count})."
        )
        ts_b = ThrottleStore(uid_b).last_sent("radar", seq["radar_trip_b"].id)
        assert ts_b is not None and ts_b != seq["snap_a_nach_a1"]["sperrzeit"], (
            f"AC-7 Positivkontrolle: B's Sperrzeit muss eigenstaendig "
            f"gebucht sein und sich von A's unterscheiden (B={ts_b!r}, "
            f"A={seq['snap_a_nach_a1']['sperrzeit']!r})."
        )
        # Eigenstaendiger Fang einer `get_data_dir`-Regression (F001): faenden
        # A und B EIN Verzeichnis vor, laege B's radar-Buchung in A's
        # `throttle_state.json` und waere unter demselben (scope, key) auch
        # ueber `uid_a` lesbar. Die Zeile darueber ist die Positivkontrolle --
        # unter `uid_b` liefert genau dieser Schluessel `ts_b`; dass er unter
        # `uid_a` LEER ist, prueft also die Trennung, nicht die Abwesenheit
        # eines Eintrags ueberhaupt. Ohne diese Zeile haengt AC-7 daran, dass
        # ein geteiltes Verzeichnis B's Aenderungs-Lauf zufaellig drosselt --
        # das faengt AC-6/AC-8, nicht dieser Test.
        ts_b_unter_a = ThrottleStore(uid_a).last_sent("radar", seq["radar_trip_b"].id)
        assert ts_b_unter_a is None, (
            f"AC-7: A's Sperrzeit-Speicher darf B's radar-Buchung nicht "
            f"kennen -- unter `uid_a` gelesen kam {ts_b_unter_a!r} "
            f"(B's eigener Wert: {ts_b!r})."
        )
        assert seq["lauf_radar2"].triggered_count == 0, (
            "AC-7 Vorbedingung: B's zweiter radar-Lauf muss innerhalb der "
            f"eigenen Sperrzeit unterdrueckt sein (war "
            f"{seq['lauf_radar2'].triggered_count})."
        )
        assert seq["snap_a_danach"]["sperrzeit"] == seq["snap_a_nach_a1"]["sperrzeit"], (
            f"AC-7: A's gebuchte Sperrzeit darf sich durch B's Laeufe nicht "
            f"veraendert haben (vorher {seq['snap_a_nach_a1']['sperrzeit']!r}, "
            f"nachher {seq['snap_a_danach']['sperrzeit']!r})."
        )
    finally:
        _clean_user(uid_a)
        _clean_user(uid_b)


def test_ac8_melde_gedaechtnis_bleibt_je_nutzer_getrennt():
    """AC-8: A und B loesen je einen Alarm mit identischem Trip-Aufbau
    (derselbe `trip_id`-String, getrennte `user_id`-Ablagen) aus -> A's
    Melde-Gedaechtnis enthaelt weiterhin ausschliesslich den von A's eigenem
    Lauf gemeldeten Wert."""
    uid_a, uid_b = _uid("ac8-a"), _uid("ac8-b")
    _clean_user(uid_a)
    _clean_user(uid_b)
    try:
        seq = _sequenz(uid_a, uid_b)
        assert seq["snap_a_nach_a1"]["melde_gedaechtnis"], (
            "AC-8 Vorbedingung: A's Melde-Gedaechtnis muss nach A1 einen "
            "Eintrag tragen."
        )
        assert seq["lauf_b1"].triggered_count == 1, (
            "AC-8 Positivkontrolle Vorbedingung: B muss ebenfalls ausloesen "
            f"(war {seq['lauf_b1'].triggered_count})."
        )
        assert seq["snap_a_danach"]["melde_gedaechtnis"] == seq["snap_a_nach_a1"]["melde_gedaechtnis"], (
            f"AC-8: A's Melde-Gedaechtnis darf durch B's Lauf nicht "
            f"veraendert werden (vorher {seq['snap_a_nach_a1']['melde_gedaechtnis']!r}, "
            f"nachher {seq['snap_a_danach']['melde_gedaechtnis']!r})."
        )
        state_b = AlertStateService(uid_b).load(seq["trip_b1"].id)
        assert state_b, (
            "AC-8 Positivkontrolle: B's eigenes Melde-Gedaechtnis muss "
            "beschrieben sein."
        )
    finally:
        _clean_user(uid_a)
        _clean_user(uid_b)


def test_ac9_unterdrueckungs_protokoll_bleibt_je_nutzer_getrennt():
    """AC-9: A's erster Lauf hat ausgeloest, B's zwei radar-Laeufe (einer
    ausgeloest, einer durch Sperrzeit unterdrueckt und protokolliert) sind
    danach gefahren -> A's Unterdrueckungs-Protokoll enthaelt keinen von B's
    Vorfaellen."""
    uid_a, uid_b = _uid("ac9-a"), _uid("ac9-b")
    _clean_user(uid_a)
    _clean_user(uid_b)
    try:
        seq = _sequenz(uid_a, uid_b)
        assert seq["lauf_a1"].triggered_count == 1, "AC-9 Vorbedingung: A muss ausloesen"
        assert seq["lauf_radar1"].triggered_count == 1, (
            "AC-9 Vorbedingung: B's erster radar-Lauf muss ausloesen."
        )
        assert seq["lauf_radar2"].triggered_count == 0, (
            "AC-9 Vorbedingung: B's zweiter radar-Lauf muss unterdrueckt sein "
            f"(war {seq['lauf_radar2'].triggered_count})."
        )

        seit = _AT - timedelta(minutes=1)
        vorfaelle_a = alert_log.read_undelivered(
            uid_a, entity_id=seq["trip_a"].id, entity_type="trip", since=seit,
        )
        assert vorfaelle_a == [], (
            f"AC-9: A's Protokoll darf keinen von B's Unterdrueckungs-"
            f"Vorfaellen enthalten (war {vorfaelle_a!r})."
        )

        vorfaelle_b = alert_log.read_undelivered(
            uid_b, entity_id=seq["radar_trip_b"].id, entity_type="trip", since=seit,
        )
        assert vorfaelle_b, (
            "AC-9 Positivkontrolle: B's eigenes Protokoll muss den "
            "Unterdrueckungs-Vorfall zeigen -- sonst prueft die Stille bei "
            "A nichts."
        )
        # Eigenstaendiger Fang einer `get_data_dir`-Regression (F001): die
        # Stille oben ist nach `entity_id` gefiltert (`alert_log.py:573`) und
        # bliebe auch bei EINEM geteilten `alert_log.json` still, weil B's
        # radar-Trip eine andere Kennung traegt. Deshalb hier derselbe Lesevor-
        # gang, der bei B den Vorfall FINDET (Zeile darueber = Positivkontrolle),
        # nur unter `uid_a`: laege beides im selben Verzeichnis, kaeme B's
        # Vorfall hier zurueck.
        b_vorfaelle_unter_a = alert_log.read_undelivered(
            uid_a, entity_id=seq["radar_trip_b"].id, entity_type="trip", since=seit,
        )
        assert b_vorfaelle_unter_a == [], (
            f"AC-9: A's Protokoll darf B's radar-Trip gar nicht kennen -- "
            f"unter `uid_a` gelesen kam {b_vorfaelle_unter_a!r} (B's eigener "
            f"Stand: {vorfaelle_b!r})."
        )
    finally:
        _clean_user(uid_a)
        _clean_user(uid_b)
