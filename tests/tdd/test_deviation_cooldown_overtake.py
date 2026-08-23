"""TDD RED — Issue #2050 Scheibe S3c: eine Verschaerfung ueberholt die
Sperrzeit im ABWEICHUNGS-Zweig (AC-1 bis AC-16).

SPEC: docs/specs/modules/feat_2050_s3c_abweichung_ueberholt_sperrzeit.md

Heutiger Stand: `check_and_send_alerts()` bricht an der Sperrzeit hart ab
(`trip_alert.py:393-400`), BEVOR ueberhaupt Wetter abgerufen und eine Schwere
gebildet wird. Eine Lage, die sich von „maessig" auf „schwer" verschaerft,
wird damit genauso geschluckt wie eine reine Wiederholung. #2065 hat dieselbe
Anforderung (A-3) fuer den Radar-Zweig geloest, S3b den Budget-Durchbruch
ergaenzt — diese Scheibe traegt beide Bausteine in den Abweichungs-Zweig.

Der geforderte Mechanismus (existiert noch NICHT):

* `ThrottleStore.record(..., urgency=...)` speichert die Dringlichkeit, mit
  der die laufende Sperrzeit gebucht wurde; `last_sent_with_urgency()` liest
  sie als Schwester zu `last_sent_with_precip()`.
* `alert_gate.deviation_overtakes_cooldown(basis_urgency=…, urgency=…)`
  vergleicht ORDINAL (`alert_urgency.exceeds`) statt ueber einen Faktor —
  der Abweichungs-Zweig traegt heterogene Metriken (°C, km/h, mm).
* Die Gate-Kette merkt sich die offene Sperrzeit, laeuft bis zur
  Dringlichkeits-Ableitung weiter und holt die Tages-Obergrenze danach REAL
  nach (Lehre `trip_alert.py:1633-1654`).

MESSGRUNDLAGE (Sonde 2026-08-23 gegen die ECHTE Kette, nicht angenommen —
`_deviation_trip`, Metrik `precipitation_sum`, Stufe `standard`):

* Delta unter 11 mm loest gar nicht aus; 11-14 mm -> LOW, 15-19 mm ->
  MODERATE, ab 20 mm -> HIGH. Daraus die vier benutzten Lagen unten.
* Trip-Zone ist `Europe/Paris` (Wegpunkt 42.20/9.10, Korsika) — DIESELBE
  Zone wie die Radar-Trips aus `test_alarm_pruefstrecke_selbstschutz.py`.
  Nur deshalb koennen sich beide Zweige in AC-8..AC-11 einen Zaehler und
  einen Durchbruch teilen.
* Das Melde-Gedaechtnis ist deltabasiert (`deviation_alert_engine.py:246`):
  eine WIEDERHOLUNG desselben Werts faellt bereits dort heraus, ohne die
  Sperrzeit zu bemuehen. Folgelagen liegen deshalb immer mindestens
  11 mm vom zuletzt gemeldeten Wert entfernt — sonst maesse der Test den
  Dedup statt der Sperrzeit.

🔴 Kein Literal fuer abgeleitete Groessen: die erwartete Dringlichkeit eines
Laufs wird ueber `_dringlichkeit_des_laufs()` aus der ECHTEN Engine mit dem
Melde-Gedaechtnis von Platte und der produktiven Ableitung
`alert_urgency.urgency_from_changes()` gebildet (AC-6). Ein hartkodierter
String liesse die Bildungsstelle unbewacht.

🔴 `max_urgency_sent` und `escalation_breakthroughs` entstehen ausschliesslich
aus ECHTEN Zustellungen; der reine Zaehlerstand wird ueber den produktiven
`alert_daily_limit.increment()` gehoben (nie durch Hineinschreiben in die
JSON-Datei).

Mock-frei: echte Trips, echter `RadarNowcastService` an seiner DI-Naht
`frame_source=`, echte Zustandsdateien unter `get_data_dir(user_id)`,
Unterdrueckungsgrund ueber `alert_log.read_undelivered()`. Kein
`Mock()`/`patch()`/`MagicMock`, kein Netz. `monkeypatch.setattr` auf einer
ECHTEN Modulfunktion (AC-13) folgt dem Muster aus
`test_alarm_pruefstrecke_selbstschutz.py::test_ac4_…`.
"""
from __future__ import annotations

import inspect
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from freezegun import freeze_time

from app.loader import get_data_dir
from services import alert_daily_limit, alert_log, alert_urgency
from services.alert_state import AlertStateService
from services.deviation_alert_engine import DeviationAlertEngine
from services.point_weather import AlertEvaluationConfig, TripSegmentWeatherAdapter
from services.throttle_store import ThrottleStore
from services.trip_day import anchor_tz

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
from tests.tdd.test_952_onset_alert_fidelity import _clean_user
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (
    _AT, _radar_trip, _settings_all_channels, _write_tier,
)
from tests.tdd.test_alarm_szenario_briefing_ueberholung_zeitreihe import _radar
# Geliehen statt nachgebaut (S3b): dieselbe Stufen-Messung, derselbe
# produktive Weg zum erschoepften Budget, dieselbe Leseseite des
# Zonen-Eintrags — zwei Fassungen derselben Messgrundlage liefen auseinander.
from tests.tdd.test_daily_budget_escalation import (
    RATE_LOW_MM_H, RATE_MODERAT_MM_H, TAGESLIMIT, TIER_MIT_BUDGET,
    _budget_ausschoepfen, _durchbruchszaehler,
    _gemessene_dringlichkeit as _radar_dringlichkeit,
    _gruende, _quelle, _zonen_eintrag,
)
from tests.tdd.test_issue_1070_daily_alert_limit import _deviation_trip, _weather_data

COOLDOWN_MIN = 120

# Gemessene Leiter (s. Moduldoku): (cached_mm, fresh_mm) -> Rang.
LAGE_LOW = (2.0, 15.0)          # Delta 13 -> LOW
LAGE_MODERATE = (2.0, 18.0)     # Delta 16 -> MODERATE
LAGE_MODERATE_FERN = (30.0, 47.0)  # Delta 17 -> MODERATE, 29 mm weg von 18,0
LAGE_HIGH = (2.0, 45.0)         # Delta 43 -> HIGH


def _uid(tag: str) -> str:
    return f"tdd-2050s3c-{tag}-{uuid.uuid4().hex[:6]}"


def _lage(paar: tuple[float, float]) -> tuple[list, list]:
    von, nach = paar
    return [_weather_data(precip_sum_mm=von)], [_weather_data(precip_sum_mm=nach)]


def _aufbau(
    uid: str, tag: str, *, tier: str = "premium",
    cooldown: int = COOLDOWN_MIN, quiet: tuple | None = None,
):
    """Nutzer + Abweichungs-Trip. Der Trip bleibt bewusst NUR im Speicher:
    `check_and_send_alerts()` bekommt ihn direkt, waehrend `check_radar_alerts()`
    seine Trips von Platte liest — so kann derselbe Nutzer einen Radar-Trip
    auf Platte fuehren, ohne dass der Abweichungs-Trip dort mitgezogen wird."""
    _clean_user(uid)
    _write_tier(uid, tier)
    trip = _deviation_trip(f"trip-2050s3c-{tag}")
    trip.alert_cooldown_minutes = cooldown
    if quiet is not None:
        trip.alert_quiet_from, trip.alert_quiet_to = quiet
    return trip


def _dringlichkeit_des_laufs(uid: str, trip, paar: tuple[float, float], at: datetime) -> str:
    """Die Stufe, mit der ein Prueflauf zu `at` TATSAECHLICH rechnen wird.

    Gebildet aus der ECHTEN `DeviationAlertEngine` mit dem Melde-Gedaechtnis,
    das der Lauf auf Platte vorfindet, und der produktiven Ableitung
    `alert_urgency.urgency_from_changes()` — kein im Testkoerper nachgebauter
    Rang und kein Literal (AC-6). Die Ruhezeit wird hier bewusst NICHT
    mitgegeben: gemessen wird die Schwere der LAGE, nicht die Entscheidung des
    Ruhezeit-Gates (AC-12 prueft die getrennt)."""
    cached, fresh = _lage(paar)
    config = AlertEvaluationConfig(
        cooldown_minutes=trip.alert_cooldown_minutes,
        metric_alert_levels=(
            getattr(trip.display_config, "metric_alert_levels", None)
            if trip.display_config else None
        ),
        display_config=trip.display_config,
        zone=anchor_tz(trip, at),
    )
    with freeze_time(at):
        ergebnis = DeviationAlertEngine().evaluate(
            cached=TripSegmentWeatherAdapter.to_points(cached),
            fresh=TripSegmentWeatherAdapter.to_points(fresh),
            config=config,
            alert_state=AlertStateService(user_id=uid).load(trip.id),
        )
    return alert_urgency.urgency_from_changes(ergebnis.changes)


def _sperrzeit(uid: str, trip) -> datetime | None:
    return ThrottleStore(uid).last_sent("trip", trip.id)


def _sperrzeit_dringlichkeit(uid: str, trip) -> str | None:
    """Die Vergleichsbasis, die der Sperrtopf zu diesem Trip fuehrt — der neue
    Lesepfad aus dieser Scheibe (heute nicht vorhanden: RED)."""
    _, urgency = ThrottleStore(uid).last_sent_with_urgency("trip", trip.id)
    return urgency


def _sperrtopf_roh(uid: str) -> dict:
    pfad = get_data_dir(uid) / "throttle_state.json"
    return json.loads(pfad.read_text()) if pfad.exists() else {}


def _zustellungen(uid: str) -> list:
    pfad = get_data_dir(uid) / "alert_log.json"
    if not pfad.exists():
        return []
    return json.loads(pfad.read_text()).get("entries") or []


def _radar_trip_ohne_sperrzeit(uid: str, tag: str):
    """Radar-Trip mit abgeschalteter Sperrzeit, auf Platte gespeichert.

    `check_radar_alerts()` liest seine Trips von Platte — ein nur am Objekt
    gesetzter Wert waere still wirkungslos. Ohne `alert_cooldown_minutes = 0`
    sperrte der erste Radar-Lauf den zweiten (Scope `radar`), und AC-11 maesse
    die Radar-Sperrzeit statt des geteilten Durchbruch-Deckels."""
    from app.loader import save_trip

    rtrip = _radar_trip(uid, f"radar-2050s3c-{tag}", send_email=True, send_telegram=True)
    rtrip.alert_cooldown_minutes = 0
    with freeze_time(_AT):
        save_trip(rtrip, user_id=uid)
    return rtrip


def _zone_vorbelegen(uid: str, tag: str, radar_quelle, *, erschoepfen: bool = True):
    """Zone ueber einen ECHTEN Radar-Lauf mit einer hoechsten ZUGESTELLTEN
    Stufe versehen und danach das Tagesbudget ueber den produktiven
    Zaehlerweg erschoepfen.

    Der Radar-Zweig ist der einzige Weg, `max_urgency_sent` aus einer
    tatsaechlichen Zustellung entstehen zu lassen, ohne sie als abgeleitetes
    Feld in die Datei zu schreiben (S3b hat ihn dafuer gebaut). Er laeuft in
    DERSELBEN Zone wie der Abweichungs-Trip — genau darum geht es in
    AC-8..AC-11."""
    rtrip = _radar_trip_ohne_sperrzeit(uid, tag)
    zone = anchor_tz(rtrip, _AT)
    stufe = _radar_dringlichkeit(rtrip, radar_quelle, _AT)
    strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
    lauf = strecke.lauf(at=_AT, zweig="radar", trip=rtrip, radar_service=_radar(radar_quelle))
    assert lauf.triggered_count == 1, (
        f"Testaufbau: der Radar-Lauf muss zustellen und dabei die hoechste "
        f"Stufe des Tages buchen (war {lauf.triggered_count})."
    )
    assert _zonen_eintrag(uid, zone, _AT).get("max_urgency_sent") == stufe, (
        f"Testaufbau: die Zone {zone} muss nach dem Radar-Lauf die gemessene "
        f"Stufe {stufe!r} als hoechste zugestellte fuehren. Eintrag: "
        f"{_zonen_eintrag(uid, zone, _AT)!r}"
    )
    if erschoepfen:
        _budget_ausschoepfen(uid, _AT, zone)
        assert not alert_daily_limit.is_allowed(
            uid, _AT, zone, reason="forecast_change",
        ), "Testaufbau: die Tages-Obergrenze muss fuer forecast_change gesperrt sein."
    return zone, stufe


def _basis_buchen(uid: str, trip, urgency: str, at: datetime = _AT) -> None:
    """Sperrzeit mit einer benannten Vergleichsbasis vorbelegen — der
    produktive Schreibweg, den auch der Abweichungs-Zweig nach dieser Scheibe
    benutzt. Heute existiert der Parameter nicht: RED."""
    ThrottleStore(uid).record("trip", trip.id, at, urgency=urgency)


# ─────────────────────────────── AC-1 ────────────────────────────────────────


@pytest.mark.timeout(60)
def test_ac1_verschaerfung_ueberholt_die_laufende_sperrzeit():
    """AC-1. GIVEN Lauf 1 (MODERATE) hat die Sperrzeit gebucht, WHEN Lauf 2
    30 Minuten spaeter INNERHALB desselben Sperrfensters eine im Rang hoehere
    Lage (HIGH) meldet, THEN geht der Alarm raus und die Sperrzeit ist NEU
    gebucht.

    Die Umkehrung des bisherigen Ist-Zustands (`test_alarm_szenario_
    sperrzeit_verschaerfung.py::test_ac2_…`, S3a). Der Test prueft ein
    EINTRETEN, nicht ein Ausbleiben — die Zustellung ist selbst der Nachweis,
    eine zusaetzliche Positivkontrolle waere gegenstandslos."""
    uid = _uid("ac1")
    try:
        trip = _aufbau(uid, "ac1")
        at2 = _AT + timedelta(minutes=30)
        basis = _dringlichkeit_des_laufs(uid, trip, LAGE_MODERATE, _AT)
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())

        cached, fresh = _lage(LAGE_MODERATE)
        lauf1 = strecke.lauf(
            at=_AT, zweig="deviation", trip=trip,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert lauf1.triggered_count == 1, (
            f"AC-1 Vorbedingung: Lauf 1 muss ausloesen und die Sperrzeit "
            f"buchen (war {lauf1.triggered_count})."
        )
        gebucht1 = _sperrzeit(uid, trip)
        assert gebucht1 is not None, "AC-1 Vorbedingung: Sperrzeit nach Lauf 1."

        verschaerft = _dringlichkeit_des_laufs(uid, trip, LAGE_HIGH, at2)
        assert alert_urgency.exceeds(verschaerft, basis), (
            f"Testkonstruktion: Lauf 2 ({verschaerft!r}) muss die Basis aus "
            f"Lauf 1 ({basis!r}) im Rang ECHT uebersteigen — sonst gaebe es "
            f"gar keine Ueberholung zu pruefen."
        )

        cached2, fresh2 = _lage(LAGE_HIGH)
        lauf2 = strecke.lauf(
            at=at2, zweig="deviation", trip=trip,
            cached_weather=cached2, fresh_weather=fresh2,
        )
        assert lauf2.triggered_count == 1, (
            f"AC-1: eine im Rang hoehere Lage muss die laufende Sperrzeit "
            f"ueberholen (war {lauf2.triggered_count}, protokollierte Gruende: "
            f"{_gruende(uid, trip, at2)!r})."
        )
        assert lauf2.telegram, (
            f"AC-1: der Durchbruch muss den konfigurierten Kanal erreichen: "
            f"telegram={lauf2.telegram!r}"
        )
        gebucht2 = _sperrzeit(uid, trip)
        assert gebucht2 is not None and gebucht2 > gebucht1, (
            f"AC-1: die Sperrzeit muss durch Lauf 2 NEU gebucht sein "
            f"(vorher {gebucht1!r}, nachher {gebucht2!r})."
        )
    finally:
        _clean_user(uid)


# ─────────────────────────────── AC-2 ────────────────────────────────────────


@pytest.mark.timeout(60)
def test_ac2_identische_wiederholung_bleibt_still_und_bucht_nicht_neu():
    """AC-2 (erste Haelfte). GIVEN dieselbe laufende Sperrzeit wie AC-1, WHEN
    Lauf 2 mit IDENTISCHEN Eingangswerten geprueft wird, THEN bleibt er still
    und der Sperrzeit-Zeitstempel bleibt unveraendert.

    Gegenprobe gegen eine zu weite Loesung: wird „jeder Folgelauf bricht
    durch" gebaut statt „nur ein Rangsprung bricht durch", muss dieser Test
    rot werden. Er deckt zugleich den bestehenden, unveraendert gruen
    bleibenden Waechter `test_alarm_pruefstrecke_selbstschutz.py::test_ac1_…`
    ab.

    Der Protokollgrund wird hier BEWUSST NICHT geprueft: bei identischen
    Werten faellt der Lauf nach der Umstellung bereits am deltabasierten
    Melde-Gedaechtnis (`deviation_alert_engine.py:246`) heraus, das VOR der
    Sperrzeit-Entscheidung liegt und keinen Protokolleintrag schreibt (D-2,
    Sammel-Issue #1199). Die zweite Haelfte (`test_ac2b_…`) prueft den
    benannten Grund an einer Lage, die den Dedup passiert.

    POSITIVKONTROLLE im selben Test (PFLICHT): ein zweiter Nutzer prueft
    dieselben Werte zum selben Zeitpunkt OHNE Lauf 1 und loest aus."""
    uid, ctrl = _uid("ac2"), _uid("ac2-ctrl")
    try:
        trip = _aufbau(uid, "ac2")
        at2 = _AT + timedelta(minutes=30)
        cached, fresh = _lage(LAGE_MODERATE)
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())

        lauf1 = strecke.lauf(
            at=_AT, zweig="deviation", trip=trip,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert lauf1.triggered_count == 1, (
            f"AC-2 Vorbedingung: Lauf 1 muss ausloesen (war "
            f"{lauf1.triggered_count})."
        )
        gebucht1 = _sperrzeit(uid, trip)

        lauf2 = strecke.lauf(
            at=at2, zweig="deviation", trip=trip,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert lauf2.triggered_count == 0, (
            f"AC-2: eine identische Wiederholung darf die Sperrzeit NICHT "
            f"ueberholen (war {lauf2.triggered_count})."
        )
        assert _sperrzeit(uid, trip) == gebucht1, (
            f"AC-2: der Sperrzeit-Zeitstempel darf sich durch die unterdrueckte "
            f"Wiederholung nicht veraendern (vorher {gebucht1!r}, nachher "
            f"{_sperrzeit(uid, trip)!r})."
        )

        # Positivkontrolle: dieselben Werte, derselbe Zeitpunkt, OHNE Lauf 1.
        ktrip = _aufbau(ctrl, "ac2-ctrl")
        kstrecke = AlarmPruefstrecke(user_id=ctrl, settings=_settings_all_channels())
        klauf = kstrecke.lauf(
            at=at2, zweig="deviation", trip=ktrip,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert klauf.triggered_count == 1, (
            f"AC-2 Positivkontrolle: dieselben Eingangsdaten zum selben "
            f"Zeitpunkt OHNE vorangegangenen Lauf muessen ausloesen — sonst "
            f"sagt die Stille oben nichts ueber den gebuchten Zustand aus "
            f"(war {klauf.triggered_count})."
        )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


@pytest.mark.timeout(60)
def test_ac2b_gleicher_rang_bleibt_mit_benanntem_grund_an_der_sperrzeit():
    """AC-2 (zweite Haelfte). GIVEN eine laufende Sperrzeit, gebucht mit
    MODERATE, WHEN eine Folgelage geprueft wird, die den Dedup passiert, aber
    im Rang ebenfalls nur MODERATE ist, THEN bleibt der Lauf still, das
    Protokoll weist `cooldown` aus und der Zeitstempel bleibt unveraendert.

    Diese Haelfte ist der eigentliche Waechter der VERGLEICHSFORMEL: die Lage
    ist neu (30,0 -> 47,0 mm, 29 mm vom zuletzt gemeldeten Wert entfernt) und
    faellt daher NICHT am Melde-Gedaechtnis heraus — allein der fehlende
    Rangsprung darf sie stoppen.

    POSITIVKONTROLLE im selben Test (PFLICHT): ein zweiter Nutzer mit
    identischem Aufbau, bei dem NUR der Rang der Folgelage hoeher ist (HIGH),
    bricht durch. Diese Haelfte ist heute ROT."""
    uid, ctrl = _uid("ac2b"), _uid("ac2b-ctrl")
    try:
        trip = _aufbau(uid, "ac2b")
        at2 = _AT + timedelta(minutes=30)
        cached, fresh = _lage(LAGE_MODERATE)
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())

        basis = _dringlichkeit_des_laufs(uid, trip, LAGE_MODERATE, _AT)
        assert strecke.lauf(
            at=_AT, zweig="deviation", trip=trip,
            cached_weather=cached, fresh_weather=fresh,
        ).triggered_count == 1, "AC-2b Vorbedingung: Lauf 1 muss ausloesen."
        gebucht1 = _sperrzeit(uid, trip)

        gleichrangig = _dringlichkeit_des_laufs(uid, trip, LAGE_MODERATE_FERN, at2)
        assert gleichrangig == basis and not alert_urgency.exceeds(gleichrangig, basis), (
            f"Testkonstruktion: die Folgelage muss denselben Rang tragen wie "
            f"die Basis (Basis {basis!r}, Folgelage {gleichrangig!r}) — sonst "
            f"pruefte dieser Test eine Eskalation statt ihres Fehlens."
        )

        cached2, fresh2 = _lage(LAGE_MODERATE_FERN)
        lauf2 = strecke.lauf(
            at=at2, zweig="deviation", trip=trip,
            cached_weather=cached2, fresh_weather=fresh2,
        )
        assert lauf2.triggered_count == 0, (
            f"AC-2b: ohne Rangsprung bleibt die Sperrzeit ein hartes Stop "
            f"(war {lauf2.triggered_count})."
        )
        assert alert_log.REASON_COOLDOWN in _gruende(uid, trip, at2), (
            f"AC-2b: der Protokollgrund muss {alert_log.REASON_COOLDOWN!r} "
            f"sein. Gefunden: {_gruende(uid, trip, at2)!r}"
        )
        assert _sperrzeit(uid, trip) == gebucht1, (
            f"AC-2b: der Sperrzeit-Zeitstempel bleibt unveraendert (vorher "
            f"{gebucht1!r}, nachher {_sperrzeit(uid, trip)!r})."
        )

        # Positivkontrolle: identischer Aufbau, NUR der Rang der Folgelage steigt.
        ktrip = _aufbau(ctrl, "ac2b-ctrl")
        kstrecke = AlarmPruefstrecke(user_id=ctrl, settings=_settings_all_channels())
        assert kstrecke.lauf(
            at=_AT, zweig="deviation", trip=ktrip,
            cached_weather=cached, fresh_weather=fresh,
        ).triggered_count == 1, "AC-2b Positivkontrolle: Lauf 1 muss ausloesen."
        khoeher = _dringlichkeit_des_laufs(ctrl, ktrip, LAGE_HIGH, at2)
        assert alert_urgency.exceeds(khoeher, basis), (
            f"Testkonstruktion der Positivkontrolle: {khoeher!r} muss "
            f"{basis!r} uebersteigen."
        )
        kcached, kfresh = _lage(LAGE_HIGH)
        klauf2 = kstrecke.lauf(
            at=at2, zweig="deviation", trip=ktrip,
            cached_weather=kcached, fresh_weather=kfresh,
        )
        assert klauf2.triggered_count == 1, (
            f"AC-2b Positivkontrolle: bei GENAU DERSELBEN Ausgangslage muss "
            f"ein echter Rangsprung durchbrechen — sonst sagt die Stille oben "
            f"nichts ueber den fehlenden Rangsprung aus (war "
            f"{klauf2.triggered_count}, Gruende: {_gruende(ctrl, ktrip, at2)!r})."
        )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


# ─────────────────────────────── AC-3 ────────────────────────────────────────


@pytest.mark.timeout(60)
def test_ac3_abgeschwaechte_lage_ueberholt_die_sperrzeit_nicht():
    """AC-3. GIVEN eine mit HIGH gebuchte Sperrzeit, WHEN ein Folgelauf
    innerhalb des Sperrfensters eine ABGESCHWAECHTE (MODERATE) Lage meldet,
    THEN bleibt er still, das Protokoll weist `cooldown` aus und der
    Zeitstempel bleibt unveraendert.

    Die gefaehrlichste Fehlerrichtung dieser Scheibe waere ein Vergleich, der
    jede Rangaenderung als Eskalation liest.

    POSITIVKONTROLLE im selben Test (PFLICHT): dieselbe abgeschwaechte Lage
    ist bei einem Nutzer OHNE laufende Sperrzeit sehr wohl alarmfaehig — die
    Stille oben kommt also vom fehlenden Rangsprung, nicht davon, dass die
    Lage an sich nichts hergibt."""
    uid, ctrl = _uid("ac3"), _uid("ac3-ctrl")
    try:
        trip = _aufbau(uid, "ac3")
        at2 = _AT + timedelta(minutes=30)
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())

        basis = _dringlichkeit_des_laufs(uid, trip, LAGE_HIGH, _AT)
        cached, fresh = _lage(LAGE_HIGH)
        assert strecke.lauf(
            at=_AT, zweig="deviation", trip=trip,
            cached_weather=cached, fresh_weather=fresh,
        ).triggered_count == 1, "AC-3 Vorbedingung: der hohe Lauf muss ausloesen."
        gebucht1 = _sperrzeit(uid, trip)

        schwaecher = _dringlichkeit_des_laufs(uid, trip, LAGE_MODERATE, at2)
        assert not alert_urgency.exceeds(schwaecher, basis), (
            f"Testkonstruktion: die Folgelage ({schwaecher!r}) darf die Basis "
            f"({basis!r}) NICHT uebersteigen."
        )

        cached2, fresh2 = _lage(LAGE_MODERATE)
        lauf2 = strecke.lauf(
            at=at2, zweig="deviation", trip=trip,
            cached_weather=cached2, fresh_weather=fresh2,
        )
        assert lauf2.triggered_count == 0, (
            f"AC-3: eine abgeschwaechte Lage darf die Sperrzeit nicht "
            f"ueberholen (war {lauf2.triggered_count})."
        )
        assert alert_log.REASON_COOLDOWN in _gruende(uid, trip, at2), (
            f"AC-3: der Protokollgrund muss {alert_log.REASON_COOLDOWN!r} sein. "
            f"Gefunden: {_gruende(uid, trip, at2)!r}"
        )
        assert _sperrzeit(uid, trip) == gebucht1, (
            f"AC-3: der Sperrzeit-Zeitstempel bleibt unveraendert (vorher "
            f"{gebucht1!r}, nachher {_sperrzeit(uid, trip)!r})."
        )

        # Positivkontrolle: dieselbe abgeschwaechte Lage OHNE Sperrzeit.
        ktrip = _aufbau(ctrl, "ac3-ctrl")
        kstrecke = AlarmPruefstrecke(user_id=ctrl, settings=_settings_all_channels())
        klauf = kstrecke.lauf(
            at=at2, zweig="deviation", trip=ktrip,
            cached_weather=cached2, fresh_weather=fresh2,
        )
        assert klauf.triggered_count == 1, (
            f"AC-3 Positivkontrolle: dieselbe abgeschwaechte Lage muss ohne "
            f"laufende Sperrzeit ausloesen — sonst bewiese die Stille oben "
            f"nur, dass die Lage nichts hergibt (war {klauf.triggered_count})."
        )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


# ─────────────────────────────── AC-4 ────────────────────────────────────────


@pytest.mark.timeout(60)
def test_ac4_sperrzeit_im_altformat_bricht_konservativ_nicht_durch():
    """AC-4. GIVEN ein Sperrzeit-Eintrag im ALTEN Format (reiner ISO-String
    ohne `urgency`, Bestandsdaten), WHEN eine beliebig starke Verschaerfung im
    Sperrfenster geprueft wird, THEN bleibt der Lauf still und das Protokoll
    weist `cooldown` aus — fehlende Basis heisst konservativ kein Durchbruch.

    POSITIVKONTROLLE im selben Test (PFLICHT): dieselbe Lage gegen eine im
    NEUEN Format mit niedriger Dringlichkeit gebuchte Sperrzeit bricht durch.
    Ohne sie bewiese die Stille nur, dass irgendetwas sperrt — nicht, dass es
    das Altformat ist."""
    uid, ctrl = _uid("ac4"), _uid("ac4-ctrl")
    try:
        trip = _aufbau(uid, "ac4")
        gebucht_am = (_AT - timedelta(minutes=10)).isoformat()
        pfad = get_data_dir(uid) / "throttle_state.json"
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(json.dumps({"trip": {trip.id: gebucht_am}}))
        assert _sperrzeit_dringlichkeit(uid, trip) is None, (
            "AC-4 Vorbedingung: ein Alt-Eintrag darf KEINE Vergleichsbasis "
            "hergeben."
        )

        cached, fresh = _lage(LAGE_HIGH)
        lauf = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels()).lauf(
            at=_AT, zweig="deviation", trip=trip,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert lauf.triggered_count == 0, (
            f"AC-4: ohne gespeicherte Vergleichsbasis darf nichts durchbrechen "
            f"(war {lauf.triggered_count})."
        )
        assert alert_log.REASON_COOLDOWN in _gruende(uid, trip, _AT), (
            f"AC-4: der Protokollgrund muss {alert_log.REASON_COOLDOWN!r} sein. "
            f"Gefunden: {_gruende(uid, trip, _AT)!r}"
        )
        assert _sperrzeit(uid, trip) is not None, (
            "AC-4: der Alt-Eintrag muss weiterhin lesbar sein (die Sperrzeit "
            "selbst darf durch die neue Lesemethode nicht verschwinden)."
        )

        # Positivkontrolle: dieselbe Lage gegen eine NEU gebuchte, niedrige Basis.
        ktrip = _aufbau(ctrl, "ac4-ctrl")
        _basis_buchen(ctrl, ktrip, "LOW", _AT - timedelta(minutes=10))
        klauf = AlarmPruefstrecke(user_id=ctrl, settings=_settings_all_channels()).lauf(
            at=_AT, zweig="deviation", trip=ktrip,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert klauf.triggered_count == 1, (
            f"AC-4 Positivkontrolle: gegen eine im NEUEN Format gebuchte "
            f"niedrige Basis muss dieselbe Lage durchbrechen — sonst sagt die "
            f"Stille oben nichts ueber das Altformat aus (war "
            f"{klauf.triggered_count}, Gruende: {_gruende(ctrl, ktrip, _AT)!r})."
        )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


# ─────────────────────────────── AC-5 ────────────────────────────────────────


@pytest.mark.timeout(60)
def test_ac5_vom_amtlichen_zweig_gebuchte_sperre_bricht_nicht_durch():
    """AC-5. GIVEN die Sperrzeit wurde OHNE Dringlichkeit gebucht — so wie es
    der amtliche Zweig (`trip_alert.py:2480`) unveraendert tut —, WHEN eine
    beliebig starke Abweichungs-Verschaerfung im selben Sperrfenster geprueft
    wird, THEN bleibt der Lauf still mit Grund `cooldown`. Direktes
    Gegenstueck zu AC-8 aus #2065.

    Beide Zweige teilen denselben Sperrschluessel (`scope="trip"`,
    `key=trip.id`, gemessen als M5 der Analyse) — ein amtlicher Alarm stellt
    die Uhr, hinterlaesst aber keine Abweichungs-Schwere.

    POSITIVKONTROLLE im selben Test (PFLICHT): dieselbe Lage gegen eine vom
    Abweichungs-Zweig selbst gesetzte, niedrigere Basis bricht durch.

    Spiegelt zugleich den unveraendert gruen bleibenden Waechter
    `test_alarm_pruefstrecke_selbstschutz.py::test_ac7_…`."""
    uid, ctrl = _uid("ac5"), _uid("ac5-ctrl")
    try:
        trip = _aufbau(uid, "ac5")
        ThrottleStore(uid).record("trip", trip.id, _AT - timedelta(minutes=10))
        assert _sperrzeit_dringlichkeit(uid, trip) is None, (
            "AC-5 Vorbedingung: ein ohne Dringlichkeit gebuchter Eintrag darf "
            "keine Vergleichsbasis hergeben."
        )

        cached, fresh = _lage(LAGE_HIGH)
        lauf = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels()).lauf(
            at=_AT, zweig="deviation", trip=trip,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert lauf.triggered_count == 0, (
            f"AC-5: nach einem amtlichen Alarm fehlt die Vergleichsbasis — der "
            f"Abweichungs-Zweig darf konservativ nicht durchbrechen (war "
            f"{lauf.triggered_count})."
        )
        assert alert_log.REASON_COOLDOWN in _gruende(uid, trip, _AT), (
            f"AC-5: der Protokollgrund muss {alert_log.REASON_COOLDOWN!r} sein. "
            f"Gefunden: {_gruende(uid, trip, _AT)!r}"
        )

        # Positivkontrolle: identische Lage, Basis vom Abweichungs-Zweig gesetzt.
        ktrip = _aufbau(ctrl, "ac5-ctrl")
        _basis_buchen(ctrl, ktrip, "LOW", _AT - timedelta(minutes=10))
        klauf = AlarmPruefstrecke(user_id=ctrl, settings=_settings_all_channels()).lauf(
            at=_AT, zweig="deviation", trip=ktrip,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert klauf.triggered_count == 1, (
            f"AC-5 Positivkontrolle: mit gesetzter niedriger Basis muss "
            f"dieselbe Lage durchbrechen (war {klauf.triggered_count}, "
            f"Gruende: {_gruende(ctrl, ktrip, _AT)!r})."
        )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


# ─────────────────────────────── AC-6 ────────────────────────────────────────


@pytest.mark.timeout(60)
def test_ac6_der_sperrtopf_traegt_die_dringlichkeit_des_tatsaechlichen_laufs():
    """AC-6. GIVEN ein durchbrechender Lauf wie AC-1, WHEN der Sperrtopf-
    Eintrag danach gelesen wird, THEN traegt sein `urgency`-Feld EXAKT den
    Wert, den `alert_urgency.urgency_from_changes()` fuer die TATSAECHLICH
    gemeldeten Aenderungen dieses Laufs liefert — und derselbe Wert steht als
    `severity` im `alert_log`-Eintrag desselben Laufs.

    🔴 Der erwartete Wert wird im Test ABGELEITET (ueber die echte Engine mit
    dem Melde-Gedaechtnis von Platte), nicht als Literal gesetzt: sonst bliebe
    die Bildungsstelle unbewacht und ein falscher, aber plausibler Wert fiele
    nicht auf. Zusaetzlich wird geprueft, dass sich der erwartete Wert vom
    Wert des ERSTEN Laufs unterscheidet — sonst waere die Zusicherung schon
    dadurch erfuellt, dass ueberhaupt nichts fortgeschrieben wurde."""
    uid = _uid("ac6")
    try:
        trip = _aufbau(uid, "ac6")
        at2 = _AT + timedelta(minutes=30)
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())

        basis = _dringlichkeit_des_laufs(uid, trip, LAGE_MODERATE, _AT)
        cached, fresh = _lage(LAGE_MODERATE)
        assert strecke.lauf(
            at=_AT, zweig="deviation", trip=trip,
            cached_weather=cached, fresh_weather=fresh,
        ).triggered_count == 1, "AC-6 Vorbedingung: Lauf 1 muss ausloesen."
        assert _sperrzeit_dringlichkeit(uid, trip) == basis, (
            f"AC-6: schon Lauf 1 muss seine eigene Dringlichkeit im Sperrtopf "
            f"hinterlassen (erwartet {basis!r}, gefunden "
            f"{_sperrzeit_dringlichkeit(uid, trip)!r})."
        )

        erwartet = _dringlichkeit_des_laufs(uid, trip, LAGE_HIGH, at2)
        assert erwartet != basis, (
            f"Testkonstruktion: Lauf 2 muss eine ANDERE Dringlichkeit tragen "
            f"als Lauf 1 ({basis!r}) — sonst waere die Fortschreibung schon "
            f"durch Nichtstun erfuellt."
        )

        cached2, fresh2 = _lage(LAGE_HIGH)
        lauf2 = strecke.lauf(
            at=at2, zweig="deviation", trip=trip,
            cached_weather=cached2, fresh_weather=fresh2,
        )
        assert lauf2.triggered_count == 1, (
            f"AC-6 Vorbedingung: der durchbrechende Lauf muss zustellen (war "
            f"{lauf2.triggered_count}, Gruende: {_gruende(uid, trip, at2)!r})."
        )
        assert _sperrzeit_dringlichkeit(uid, trip) == erwartet, (
            f"AC-6: der Sperrtopf muss die aus den TATSAECHLICHEN Aenderungen "
            f"abgeleitete Dringlichkeit {erwartet!r} fuehren, gefunden "
            f"{_sperrzeit_dringlichkeit(uid, trip)!r}."
        )
        letzte = _zustellungen(uid)[-1]
        assert letzte.get("severity") == erwartet, (
            f"AC-6: derselbe Wert muss im `alert_log`-Eintrag desselben Laufs "
            f"stehen — zwei Berechnungspfade duerfen nicht auseinanderlaufen. "
            f"Erwartet {erwartet!r}, Eintrag: {letzte!r}"
        )
    finally:
        _clean_user(uid)


# ─────────────────────────────── AC-7 ────────────────────────────────────────


@pytest.mark.timeout(60)
def test_ac7_fremde_sperreintraege_ueberleben_den_schreibvorgang():
    """AC-7. GIVEN ein `throttle_state.json` mit mehreren Bestandseintraegen
    verschiedener `scope`/`key` (teils im Altformat, einer mit einem
    unbekannten Zusatzfeld), WHEN ein Lauf dagegen prueft und schreibt —
    unterdrueckend WIE durchbrechend —, THEN bleibt die Datei lesbar, alle
    fremden Eintraege bleiben Feld fuer Feld unangetastet, und NUR der
    betroffene Schluessel traegt danach das neue, vollstaendige Format.

    Hier IST die Datei der Pruefgegenstand — deshalb als einziger Test dieser
    Datei ein direkter Blick in ihren Inhalt (Risiko: ein Replace statt eines
    Read-Modify-Write raeumt Bestandssperren aller Alarmarten ab)."""
    uid = _uid("ac7")
    try:
        trip = _aufbau(uid, "ac7")
        at2 = _AT + timedelta(minutes=30)
        alt_iso = (_AT - timedelta(minutes=10)).isoformat()
        fremd_radar = {"trip-fremd": (_AT - timedelta(hours=1)).isoformat()}
        fremd_compare = {
            "cp-fremd": {"at": (_AT - timedelta(hours=2)).isoformat(), "precip_mm": 3.5},
        }
        fremd_trip = {
            "at": (_AT - timedelta(hours=3)).isoformat(),
            "precip_mm": None, "unbekanntes_feld": "bleibt",
        }
        pfad = get_data_dir(uid) / "throttle_state.json"
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(json.dumps({
            "trip": {trip.id: alt_iso, "trip-nachbar": dict(fremd_trip)},
            "radar": dict(fremd_radar),
            "compare_preset": {k: dict(v) for k, v in fremd_compare.items()},
        }))

        def _fremd_unveraendert(phase: str) -> None:
            data = _sperrtopf_roh(uid)
            assert data.get("radar") == fremd_radar, (
                f"AC-7 ({phase}): der `radar`-Bestand muss unangetastet "
                f"bleiben. Erwartet {fremd_radar!r}, gefunden "
                f"{data.get('radar')!r}"
            )
            assert data.get("compare_preset") == fremd_compare, (
                f"AC-7 ({phase}): der `compare_preset`-Bestand muss "
                f"unangetastet bleiben. Erwartet {fremd_compare!r}, gefunden "
                f"{data.get('compare_preset')!r}"
            )
            assert (data.get("trip") or {}).get("trip-nachbar") == fremd_trip, (
                f"AC-7 ({phase}): der Nachbar-Trip muss Feld fuer Feld "
                f"unangetastet bleiben (auch das unbekannte Feld). Erwartet "
                f"{fremd_trip!r}, gefunden "
                f"{(data.get('trip') or {}).get('trip-nachbar')!r}"
            )

        cached, fresh = _lage(LAGE_HIGH)
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())

        # Weg 1: unterdrueckender Lauf gegen den Alt-Eintrag.
        assert strecke.lauf(
            at=_AT, zweig="deviation", trip=trip,
            cached_weather=cached, fresh_weather=fresh,
        ).triggered_count == 0, (
            "AC-7 Vorbedingung: gegen den Alt-Eintrag darf nichts durchbrechen "
            "(AC-4)."
        )
        _fremd_unveraendert("unterdrueckender Lauf")
        assert (_sperrtopf_roh(uid).get("trip") or {}).get(trip.id) == alt_iso, (
            "AC-7: ein unterdrueckter Lauf darf den eigenen Eintrag nicht "
            "anfassen."
        )

        # Weg 2: durchbrechender Lauf gegen dieselbe Datei.
        _basis_buchen(uid, trip, "LOW", _AT)
        _fremd_unveraendert("Basis-Buchung")
        erwartet = _dringlichkeit_des_laufs(uid, trip, LAGE_HIGH, at2)
        lauf2 = strecke.lauf(
            at=at2, zweig="deviation", trip=trip,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert lauf2.triggered_count == 1, (
            f"AC-7 Vorbedingung: der Durchbruch muss stattfinden, sonst prueft "
            f"dieser Test den zweiten Schreibweg gar nicht (war "
            f"{lauf2.triggered_count}, Gruende: {_gruende(uid, trip, at2)!r})."
        )
        _fremd_unveraendert("durchbrechender Lauf")
        eigener = (_sperrtopf_roh(uid).get("trip") or {}).get(trip.id)
        assert isinstance(eigener, dict) and set(eigener) == {"at", "precip_mm", "urgency"}, (
            f"AC-7: der betroffene Schluessel muss danach das neue, "
            f"vollstaendige Format tragen. Gefunden: {eigener!r}"
        )
        assert eigener.get("urgency") == erwartet, (
            f"AC-7: das `urgency`-Feld muss die aus dem Lauf abgeleitete "
            f"Dringlichkeit {erwartet!r} tragen. Gefunden: {eigener!r}"
        )
    finally:
        _clean_user(uid)


# ─────────────────────────────── AC-8 ────────────────────────────────────────


@pytest.mark.timeout(90)
def test_ac8_erschoepftes_budget_stoppt_die_ueberholung_ohne_tageseskalation():
    """AC-8. GIVEN eine Sperrzeit wird durch einen Rangsprung ueberholt, das
    Tagesbudget ist erschoepft UND die Dringlichkeit uebersteigt die heute in
    dieser Zone bereits ZUGESTELLTE Hoechststufe NICHT, WHEN der Lauf geprueft
    wird, THEN bleibt der Alarm aus, der Grund wechselt von `cooldown` auf
    `daily_limit` und die Sperrzeit bleibt unveraendert.

    Das Tagesbudget ist die in der Analyse GEMESSENE zweite Wand (M2): ein Fix,
    der nur die Sperrzeit oeffnet, wechselt bloss den Unterdrueckungsgrund.
    Genau das haelt dieser Test fest.

    Die Hoechststufe des Tages (MODERATE) entsteht aus einem ECHTEN Radar-Lauf
    derselben Zone — der einzige Weg, sie ohne direktes Hineinschreiben
    abgeleiteter Felder herzustellen.

    POSITIVKONTROLLE im selben Test (PFLICHT): deckungsgleicher Aufbau, nur
    mit FREIEM Tageszaehler — derselbe Lauf geht durch. Ohne sie bewiese die
    Stille nur, dass irgendetwas sperrt."""
    uid, ctrl = _uid("ac8"), _uid("ac8-ctrl")
    try:
        at2 = _AT + timedelta(minutes=30)
        trip = _aufbau(uid, "ac8", tier=TIER_MIT_BUDGET)
        zone, hoechste = _zone_vorbelegen(uid, "ac8", _quelle(RATE_MODERAT_MM_H))
        _basis_buchen(uid, trip, "LOW")

        stufe = _dringlichkeit_des_laufs(uid, trip, LAGE_MODERATE, at2)
        assert alert_urgency.exceeds(stufe, "LOW"), (
            f"Testkonstruktion: der Lauf ({stufe!r}) muss die Sperrzeit-Basis "
            f"LOW ueberholen — sonst pruefte dieser Test die Sperrzeit statt "
            f"des Budgets."
        )
        assert not alert_urgency.exceeds(stufe, hoechste), (
            f"Testkonstruktion: der Lauf ({stufe!r}) darf die heute bereits "
            f"zugestellte Hoechststufe ({hoechste!r}) NICHT uebersteigen — "
            f"sonst waere es eine echte Tages-Eskalation (AC-9)."
        )

        cached, fresh = _lage(LAGE_MODERATE)
        lauf = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels()).lauf(
            at=at2, zweig="deviation", trip=trip,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert lauf.triggered_count == 0, (
            f"AC-8: die Sperrzeit-Ueberholung allein genuegt nicht — das "
            f"erschoepfte Tagesbudget bleibt die zweite Wand (war "
            f"{lauf.triggered_count})."
        )
        assert alert_log.REASON_DAILY_LIMIT in _gruende(uid, trip, at2), (
            f"AC-8: der Protokollgrund muss {alert_log.REASON_DAILY_LIMIT!r} "
            f"sein (nicht {alert_log.REASON_COOLDOWN!r}) — die Sperrzeit wurde "
            f"ueberholt, das Budget nicht. Gefunden: {_gruende(uid, trip, at2)!r}"
        )
        assert _durchbruchszaehler(uid, zone, at2) == 0, (
            f"AC-8: ein abgewiesener Lauf darf keinen Durchbruch verbrauchen, "
            f"gefunden {_durchbruchszaehler(uid, zone, at2)}."
        )
        assert _sperrzeit(uid, trip) == _AT, (
            f"AC-8: der Sperrzeit-Zeitstempel bleibt unveraendert (erwartet "
            f"{_AT!r}, gefunden {_sperrzeit(uid, trip)!r})."
        )

        # Positivkontrolle: identischer Aufbau, nur der Tageszaehler ist frei.
        ktrip = _aufbau(ctrl, "ac8-ctrl", tier=TIER_MIT_BUDGET)
        _zone_vorbelegen(ctrl, "ac8-ctrl", _quelle(RATE_MODERAT_MM_H), erschoepfen=False)
        _basis_buchen(ctrl, ktrip, "LOW")
        klauf = AlarmPruefstrecke(user_id=ctrl, settings=_settings_all_channels()).lauf(
            at=at2, zweig="deviation", trip=ktrip,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert klauf.triggered_count == 1, (
            f"AC-8 Positivkontrolle: bei deckungsgleichem Aufbau mit FREIEM "
            f"Tageszaehler muss derselbe Lauf durchgehen — sonst sagt die "
            f"Stille oben nichts ueber das Budget aus (war "
            f"{klauf.triggered_count}, Gruende: {_gruende(ctrl, ktrip, at2)!r})."
        )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


# ─────────────────────────────── AC-9 ────────────────────────────────────────


@pytest.mark.timeout(90)
def test_ac9_echte_tageseskalation_bricht_das_erschoepfte_budget():
    """AC-9. GIVEN eine ueberholte Sperrzeit, ein erschoepftes Tagesbudget UND
    eine Dringlichkeit, die die heute in dieser Zone bereits ZUGESTELLTE
    Hoechststufe ECHT uebersteigt, bei noch freiem Durchbruch, WHEN der Lauf
    geprueft wird, THEN wird der Alarm dennoch zugestellt und
    `escalation_breakthroughs` der Zone steht danach auf 1.

    Die Hoechststufe (LOW) entsteht aus einem ECHTEN Radar-Lauf derselben
    Zone, nicht aus einem vorbelegten Feld. Der Test prueft ein EINTRETEN —
    die Zustellung ist selbst der Nachweis."""
    uid = _uid("ac9")
    try:
        at2 = _AT + timedelta(minutes=30)
        trip = _aufbau(uid, "ac9", tier=TIER_MIT_BUDGET)
        zone, hoechste = _zone_vorbelegen(uid, "ac9", _quelle(RATE_LOW_MM_H))
        _basis_buchen(uid, trip, "LOW")

        stufe = _dringlichkeit_des_laufs(uid, trip, LAGE_HIGH, at2)
        assert alert_urgency.exceeds(stufe, hoechste), (
            f"Testkonstruktion: der Lauf ({stufe!r}) muss die heute bereits "
            f"zugestellte Hoechststufe ({hoechste!r}) ECHT uebersteigen."
        )
        assert _durchbruchszaehler(uid, zone, _AT) == 0, (
            "Testkonstruktion: der eine Durchbruch des Tages muss noch frei sein."
        )

        cached, fresh = _lage(LAGE_HIGH)
        lauf = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels()).lauf(
            at=at2, zweig="deviation", trip=trip,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert lauf.triggered_count == 1, (
            f"AC-9: eine echte Tages-Eskalation muss das erschoepfte Budget im "
            f"Abweichungs-Zweig durchbrechen (war {lauf.triggered_count}, "
            f"Gruende: {_gruende(uid, trip, at2)!r})."
        )
        assert lauf.telegram, (
            f"AC-9: der Durchbruch muss den konfigurierten Kanal erreichen: "
            f"telegram={lauf.telegram!r}"
        )
        assert _durchbruchszaehler(uid, zone, at2) == 1, (
            f"AC-9: nach dem Durchbruch muss die Zone GENAU EINEN verbrauchten "
            f"Durchbruch fuehren, gefunden {_durchbruchszaehler(uid, zone, at2)}. "
            f"Eintrag: {_zonen_eintrag(uid, zone, at2)!r}"
        )
    finally:
        _clean_user(uid)


# ─────────────────────────────── AC-10 ───────────────────────────────────────


@pytest.mark.timeout(120)
def test_ac10_der_durchbruch_gilt_hoechstens_einmal_pro_tag_und_zone():
    """AC-10. GIVEN in einer Zone hat heute bereits ein Durchbruch
    stattgefunden, WHEN ein zweiter, noch schwererer Lauf derselben Zone
    geprueft wird, THEN bleibt der Alarm aus, das Protokoll weist
    `daily_limit` aus und der Durchbruchszaehler bleibt bei 1.

    LEITER LOW -> MODERATE -> HIGH, bewusst so und nicht MODERATE -> HIGH: die
    Rang-Skala saettigt bei HIGH. Waere der erste Durchbruch schon HIGH,
    bliebe der zweite Lauf auch OHNE Deckel still, und der Test bewachte die
    Saettigung statt der Obergrenze.

    Der zweite Lauf laeuft auf einem ZWEITEN Trip derselben Zone: die
    Sperrzeit haengt am Trip-Schluessel, der Durchbruchszaehler an der Zone.
    Auf demselben Trip haette der erste Durchbruch die Sperrzeit-Basis auf
    HIGH gehoben und die Stille kaeme von der Saettigung, nicht vom Deckel.

    POSITIVKONTROLLE im selben Test (PFLICHT): derselbe zweite Trip bei einem
    Nutzer, bei dem der Durchbruch des Tages NOCH FREI ist, bricht durch."""
    uid, ctrl = _uid("ac10"), _uid("ac10-ctrl")
    try:
        at2, at3 = _AT + timedelta(minutes=30), _AT + timedelta(minutes=60)
        trip_a = _aufbau(uid, "ac10-a", tier=TIER_MIT_BUDGET)
        trip_b = _deviation_trip("trip-2050s3c-ac10-b")
        trip_b.alert_cooldown_minutes = COOLDOWN_MIN
        zone, hoechste = _zone_vorbelegen(uid, "ac10", _quelle(RATE_LOW_MM_H))
        _basis_buchen(uid, trip_a, "LOW")
        _basis_buchen(uid, trip_b, "LOW")

        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        cached_m, fresh_m = _lage(LAGE_MODERATE)
        stufe_a = _dringlichkeit_des_laufs(uid, trip_a, LAGE_MODERATE, at2)
        assert alert_urgency.exceeds(stufe_a, hoechste), (
            f"Testkonstruktion: der erste Durchbruch ({stufe_a!r}) muss die "
            f"Hoechststufe ({hoechste!r}) uebersteigen."
        )
        assert strecke.lauf(
            at=at2, zweig="deviation", trip=trip_a,
            cached_weather=cached_m, fresh_weather=fresh_m,
        ).triggered_count == 1, (
            f"AC-10 Vorbedingung: der erste Lauf muss durchbrechen und damit "
            f"den EINEN Durchbruch des Tages verbrauchen (Gruende: "
            f"{_gruende(uid, trip_a, at2)!r})."
        )
        assert _durchbruchszaehler(uid, zone, at2) == 1, (
            f"AC-10 Vorbedingung: der Durchbruch muss gebucht sein, gefunden "
            f"{_durchbruchszaehler(uid, zone, at2)}."
        )

        cached_h, fresh_h = _lage(LAGE_HIGH)
        stufe_b = _dringlichkeit_des_laufs(uid, trip_b, LAGE_HIGH, at3)
        assert alert_urgency.exceeds(stufe_b, stufe_a), (
            f"Testkonstruktion: der zweite Lauf ({stufe_b!r}) muss noch "
            f"schwerer sein als der erste ({stufe_a!r}) — sonst bewachte der "
            f"Test die Saettigung statt des Deckels."
        )
        lauf_b = strecke.lauf(
            at=at3, zweig="deviation", trip=trip_b,
            cached_weather=cached_h, fresh_weather=fresh_h,
        )
        assert lauf_b.triggered_count == 0, (
            f"AC-10: die Ausnahme gilt hoechstens EINMAL pro Tag und Zone — "
            f"auch eine noch schwerere Lage darf danach nicht mehr "
            f"durchbrechen (war {lauf_b.triggered_count})."
        )
        assert alert_log.REASON_DAILY_LIMIT in _gruende(uid, trip_b, at3), (
            f"AC-10: der Protokollgrund muss {alert_log.REASON_DAILY_LIMIT!r} "
            f"sein. Gefunden: {_gruende(uid, trip_b, at3)!r}"
        )
        assert _durchbruchszaehler(uid, zone, at3) == 1, (
            f"AC-10: der Durchbruchszaehler darf durch den abgewiesenen Lauf "
            f"nicht weiterwachsen, gefunden "
            f"{_durchbruchszaehler(uid, zone, at3)}."
        )

        # Positivkontrolle: derselbe zweite Trip, aber OHNE verbrauchten Durchbruch.
        _aufbau(ctrl, "ac10-ctrl", tier=TIER_MIT_BUDGET)
        kzone, _ = _zone_vorbelegen(ctrl, "ac10-ctrl", _quelle(RATE_LOW_MM_H))
        _basis_buchen(ctrl, trip_b, "LOW")
        assert _durchbruchszaehler(ctrl, kzone, _AT) == 0, (
            "AC-10 Positivkontrolle: der Durchbruch des Tages muss hier noch "
            "frei sein."
        )
        klauf = AlarmPruefstrecke(user_id=ctrl, settings=_settings_all_channels()).lauf(
            at=at3, zweig="deviation", trip=trip_b,
            cached_weather=cached_h, fresh_weather=fresh_h,
        )
        assert klauf.triggered_count == 1, (
            f"AC-10 Positivkontrolle: bei deckungsgleicher Lage, nur OHNE "
            f"verbrauchten Durchbruch, muss derselbe Lauf durchbrechen — sonst "
            f"sagt die Stille oben nichts ueber den Deckel aus (war "
            f"{klauf.triggered_count}, Gruende: {_gruende(ctrl, trip_b, at3)!r})."
        )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


# ─────────────────────────────── AC-11 ───────────────────────────────────────


@pytest.mark.timeout(120)
def test_ac11_radar_und_abweichung_teilen_denselben_durchbruch_deckel():
    """AC-11. GIVEN der eine Durchbruch einer Zone wurde heute bereits im
    RADAR-Zweig verbraucht, WHEN danach eine ebenso eskalierende Lage im
    ABWEICHUNGS-Zweig derselben Zone geprueft wird, THEN bleibt dieser Alarm
    aus mit Grund `daily_limit` — der Deckel gilt gemeinsam ueber beide
    Zweige, er wird nicht getrennt gezaehlt.

    Ohne diese Teilung koennte eine Lage, die abwechselnd im Radar- und im
    Abweichungs-Zweig eskaliert, das Tagesbudget zweimal aufreissen.

    POSITIVKONTROLLE im selben Test (PFLICHT): derselbe Zaehlerstand, dieselbe
    Zone, dieselbe Lage — nur OHNE den im Radar-Zweig verbrauchten Durchbruch
    — bricht durch.

    🔴 Der Radar-Lauf laeuft bewusst ueber den REGULAeREN Pfad mit
    vollstaendigen Nowcast-Daten (echter `RadarNowcastService` an seiner
    DI-Naht `frame_source=`, ein vorhandener nasser `RadarFrame`). Er darf
    KEINEN der beiden Ausfall-Zweige in `check_radar_alerts` (`:1521-1560`,
    Positionsbestimmung bzw. Nowcast-Abruf) beruehren — die enden beide auf
    `continue` und stellen nichts zu, und #2050 S4a (Szenario 6) erweitert sie
    gerade um einen Ausfall-Protokolleintrag. Ein AC-11, der ueber einen
    Ausfallpfad liefe, wuerde davon mitgerissen. Die beiden Zusicherungen
    unten (Zustellung auf einem echten Kanal + gebuchter Durchbruch) sind auf
    einem Ausfallpfad strukturell unerreichbar und halten das fest."""
    uid, ctrl = _uid("ac11"), _uid("ac11-ctrl")
    try:
        at2, at3 = _AT + timedelta(minutes=30), _AT + timedelta(minutes=60)
        trip = _aufbau(uid, "ac11", tier=TIER_MIT_BUDGET)
        zone, hoechste = _zone_vorbelegen(uid, "ac11", _quelle(RATE_LOW_MM_H))

        # Der Radar-Zweig verbraucht den einen Durchbruch des Tages.
        rtrip = _radar_trip_ohne_sperrzeit(uid, "ac11")
        konvektiv = _quelle(RATE_MODERAT_MM_H, konvektiv=True)
        radar_stufe = _radar_dringlichkeit(rtrip, konvektiv, at2)
        assert alert_urgency.exceeds(radar_stufe, hoechste), (
            f"Testkonstruktion: der Radar-Lauf ({radar_stufe!r}) muss die "
            f"Hoechststufe ({hoechste!r}) uebersteigen."
        )
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        radar_lauf = strecke.lauf(
            at=at2, zweig="radar", trip=rtrip, radar_service=_radar(konvektiv),
        )
        assert radar_lauf.triggered_count == 1, (
            f"AC-11 Vorbedingung: der Radar-Lauf muss das erschoepfte Budget "
            f"durchbrechen (S3b). War {radar_lauf.triggered_count}."
        )
        assert radar_lauf.mail and radar_lauf.telegram, (
            f"AC-11 Vorbedingung: der Radar-Lauf muss auf echten Kanaelen "
            f"zugestellt haben — ein Ausfall-Zweig (`:1521-1560`) endet auf "
            f"`continue` und liefert nichts, der Test liefe dann am "
            f"regulaeren Pfad vorbei. mail={radar_lauf.mail!r} "
            f"telegram={radar_lauf.telegram!r}"
        )
        assert _durchbruchszaehler(uid, zone, at2) == 1, (
            f"AC-11 Vorbedingung: der Radar-Durchbruch muss gebucht sein, "
            f"gefunden {_durchbruchszaehler(uid, zone, at2)}."
        )

        _basis_buchen(uid, trip, "LOW", at2)
        cached, fresh = _lage(LAGE_HIGH)
        lauf = strecke.lauf(
            at=at3, zweig="deviation", trip=trip,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert lauf.triggered_count == 0, (
            f"AC-11: der eine Durchbruch des Tages ist im Radar-Zweig bereits "
            f"verbraucht — der Abweichungs-Zweig bekommt keinen zweiten (war "
            f"{lauf.triggered_count})."
        )
        assert alert_log.REASON_DAILY_LIMIT in _gruende(uid, trip, at3), (
            f"AC-11: der Protokollgrund muss {alert_log.REASON_DAILY_LIMIT!r} "
            f"sein. Gefunden: {_gruende(uid, trip, at3)!r}"
        )
        assert _durchbruchszaehler(uid, zone, at3) == 1, (
            f"AC-11: der Zaehler darf nicht weiterwachsen, gefunden "
            f"{_durchbruchszaehler(uid, zone, at3)}."
        )

        # Positivkontrolle: gleicher Zaehlerstand, aber Durchbruch noch frei.
        ktrip = _aufbau(ctrl, "ac11-ctrl", tier=TIER_MIT_BUDGET)
        kzone, _ = _zone_vorbelegen(ctrl, "ac11-ctrl", _quelle(RATE_LOW_MM_H))
        with freeze_time(at2):
            alert_daily_limit.increment(ctrl, at2, kzone)
        assert alert_daily_limit.load(ctrl, at2, kzone) == TAGESLIMIT + 1, (
            f"AC-11 Positivkontrolle: der Zaehlerstand muss dem des Hauptfalls "
            f"entsprechen (Radar-Durchbruch = ein weiterer Platz), steht auf "
            f"{alert_daily_limit.load(ctrl, at2, kzone)}."
        )
        assert _durchbruchszaehler(ctrl, kzone, at2) == 0, (
            "AC-11 Positivkontrolle: hier ist der Durchbruch noch frei."
        )
        _basis_buchen(ctrl, ktrip, "LOW", at2)
        klauf = AlarmPruefstrecke(user_id=ctrl, settings=_settings_all_channels()).lauf(
            at=at3, zweig="deviation", trip=ktrip,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert klauf.triggered_count == 1, (
            f"AC-11 Positivkontrolle: bei gleichem Zaehlerstand, aber freiem "
            f"Durchbruch, muss derselbe Lauf durchbrechen — sonst sagt die "
            f"Stille oben nichts ueber den geteilten Deckel aus (war "
            f"{klauf.triggered_count}, Gruende: {_gruende(ctrl, ktrip, at3)!r})."
        )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


# ─────────────────────────────── AC-12 ───────────────────────────────────────


@pytest.mark.timeout(90)
def test_ac12_die_ruhezeit_bleibt_auch_fuer_die_ueberholung_unbrechbar():
    """AC-12. GIVEN eine aktive Ruhezeit UND eine extreme Verschaerfung, die
    sowohl die Sperrzeit als auch ein erschoepftes Tagesbudget ueberholen
    wuerde, WHEN der Lauf geprueft wird, THEN bleibt der Alarm dennoch aus und
    das Protokoll weist `quiet_hours` aus.

    PO-Ablehnung #1955: die Ruhezeit ist unbrechbar. Die Reihenfolge
    Ruhezeit -> Sperrzeit -> Tages-Obergrenze bleibt; die neuen Ausnahmen
    haengen ausschliesslich an den beiden hinteren Stufen.

    Das Ruhefenster (12:15-13:00 Ortszeit, Europe/Paris) liegt so, dass der
    vorbereitende Radar-Lauf um 12:00 Ortszeit noch AUSSERHALB liegt.

    POSITIVKONTROLLE im selben Test (PFLICHT): identischer Aufbau, Ruhefenster
    woanders — derselbe Lauf bricht durch."""
    uid, ctrl = _uid("ac12"), _uid("ac12-ctrl")
    try:
        at2 = _AT + timedelta(minutes=30)  # 12:30 Ortszeit — mitten im Fenster
        trip = _aufbau(uid, "ac12", tier=TIER_MIT_BUDGET, quiet=("12:15", "13:00"))
        zone, hoechste = _zone_vorbelegen(uid, "ac12", _quelle(RATE_LOW_MM_H))
        _basis_buchen(uid, trip, "LOW")

        stufe = _dringlichkeit_des_laufs(uid, trip, LAGE_HIGH, at2)
        assert alert_urgency.exceeds(stufe, "LOW") and alert_urgency.exceeds(
            stufe, hoechste,
        ), (
            f"Testkonstruktion: die Lage ({stufe!r}) muss BEIDE hinteren "
            f"Stufen ueberholen — Sperrzeit-Basis LOW und Hoechststufe "
            f"{hoechste!r}. Sonst bewiese die Stille nichts ueber die Ruhezeit."
        )

        cached, fresh = _lage(LAGE_HIGH)
        lauf = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels()).lauf(
            at=at2, zweig="deviation", trip=trip,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert lauf.triggered_count == 0, (
            f"AC-12: die Ruhezeit ist unbrechbar — auch die neuen Ausnahmen "
            f"duerfen sie nicht aufreissen (war {lauf.triggered_count})."
        )
        gruende = _gruende(uid, trip, at2)
        assert alert_log.REASON_QUIET_HOURS in gruende, (
            f"AC-12: der Protokollgrund muss "
            f"{alert_log.REASON_QUIET_HOURS!r} sein (nicht "
            f"{alert_log.REASON_COOLDOWN!r} oder "
            f"{alert_log.REASON_DAILY_LIMIT!r}) — die Ruhezeit entscheidet "
            f"zuerst. Gefunden: {gruende!r}"
        )
        assert _durchbruchszaehler(uid, zone, at2) == 0, (
            f"AC-12: eine an der Ruhezeit unterdrueckte Meldung darf keinen "
            f"Durchbruch verbrauchen, gefunden "
            f"{_durchbruchszaehler(uid, zone, at2)}."
        )
        assert _sperrzeit(uid, trip) == _AT, (
            f"AC-12: der Sperrzeit-Zeitstempel bleibt unveraendert (gefunden "
            f"{_sperrzeit(uid, trip)!r})."
        )

        # Positivkontrolle: identischer Aufbau, Ruhefenster liegt woanders.
        ktrip = _aufbau(ctrl, "ac12-ctrl", tier=TIER_MIT_BUDGET, quiet=("20:00", "21:00"))
        _zone_vorbelegen(ctrl, "ac12-ctrl", _quelle(RATE_LOW_MM_H))
        _basis_buchen(ctrl, ktrip, "LOW")
        klauf = AlarmPruefstrecke(user_id=ctrl, settings=_settings_all_channels()).lauf(
            at=at2, zweig="deviation", trip=ktrip,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert klauf.triggered_count == 1, (
            f"AC-12 Positivkontrolle: dieselbe Lage OHNE Ruhezeit muss "
            f"durchbrechen — sonst sagt die Stille oben nichts ueber die "
            f"Ruhezeit aus (war {klauf.triggered_count}, Gruende: "
            f"{_gruende(ctrl, ktrip, at2)!r})."
        )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


# ─────────────────────────────── AC-13 ───────────────────────────────────────


@pytest.mark.timeout(60)
def test_ac13_der_briefing_vorlauf_bleibt_von_der_ueberholung_unberuehrt(monkeypatch):
    """AC-13. GIVEN ein geplantes Briefing steht unmittelbar bevor UND eine
    extreme Verschaerfung liegt vor, WHEN der Lauf geprueft wird, THEN bleibt
    der Alarm aus (Bestandsschutz #1594 — die Meldung kommt Minuten spaeter
    vollstaendig im Briefing an).

    `check_briefing_imminent` wird ueber `monkeypatch.setattr` auf der ECHTEN
    Modulfunktion gestellt, nicht ueber einen Mock: `trip_alert.py` importiert
    sie LOKAL PRO AUFRUF (`:1095`), ein Patch auf `services.alert_gate` wirkt
    dort also — dasselbe Muster wie
    `test_alarm_pruefstrecke_selbstschutz.py::test_ac4_…`.

    POSITIVKONTROLLE im selben Test (PFLICHT): ohne den Briefing-Vorlauf, bei
    sonst identischem Aufbau, geht derselbe Alarm durch."""
    import services.alert_gate as alert_gate_mod

    uid, ctrl = _uid("ac13"), _uid("ac13-ctrl")
    try:
        trip = _aufbau(uid, "ac13")
        _basis_buchen(uid, trip, "LOW")
        cached, fresh = _lage(LAGE_HIGH)
        at2 = _AT + timedelta(minutes=30)

        monkeypatch.setattr(alert_gate_mod, "check_briefing_imminent", lambda **kw: True)
        lauf = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels()).lauf(
            at=at2, zweig="deviation", trip=trip,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert lauf.triggered_count == 0, (
            f"AC-13: bei unmittelbar bevorstehendem Briefing darf auch eine "
            f"extreme Verschaerfung keinen Alarm ausloesen (war "
            f"{lauf.triggered_count})."
        )
        assert not (lauf.mail or lauf.telegram or lauf.sms or lauf.premium_sms), (
            f"AC-13: kein Kanal darf etwas bekommen: mail={lauf.mail!r} "
            f"telegram={lauf.telegram!r} sms={lauf.sms!r} "
            f"premium_sms={lauf.premium_sms!r}"
        )
        assert _sperrzeit(uid, trip) == _AT, (
            f"AC-13: der Sperrzeit-Zeitstempel bleibt unveraendert (gefunden "
            f"{_sperrzeit(uid, trip)!r})."
        )

        # Positivkontrolle: identischer Aufbau, nur ohne Briefing-Vorlauf.
        monkeypatch.undo()
        ktrip = _aufbau(ctrl, "ac13-ctrl")
        _basis_buchen(ctrl, ktrip, "LOW")
        klauf = AlarmPruefstrecke(user_id=ctrl, settings=_settings_all_channels()).lauf(
            at=at2, zweig="deviation", trip=ktrip,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert klauf.triggered_count == 1, (
            f"AC-13 Positivkontrolle: ohne Briefing-Vorlauf muss derselbe Lauf "
            f"durchbrechen — sonst unterscheidet die gepruefte Bedingung gar "
            f"nichts (war {klauf.triggered_count}, Gruende: "
            f"{_gruende(ctrl, ktrip, at2)!r})."
        )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


# ─────────────────────────────── AC-14 ───────────────────────────────────────


@pytest.mark.timeout(60)
def test_ac14_die_geteilte_engine_bleibt_in_signatur_und_verhalten_unveraendert():
    """AC-14. GIVEN `DeviationAlertEngine` ist mit dem PO-zurueckgestellten
    Ortsvergleich geteilt (`compare_alert.py:509`), WHEN diese Scheibe
    abgeschlossen ist, THEN hat `evaluate()` keinen neuen Pflichtparameter und
    liefert fuer dieselbe eskalierende Eingangslage dasselbe Ergebnis wie
    zuvor — der Ortsvergleich erbt die Ausnahme NICHT.

    Zwei Zusicherungen: (1) die Pflichtparameter sind unveraendert genau
    `cached`/`fresh`/`config`/`alert_state`, jeder weitere hat einen
    Vorgabewert; (2) die Engine ist SPERRTOPF-BLIND — ein vorbelegter,
    laufender Sperrzeit-Eintrag desselben Nutzers/Schluessels aendert ihr
    Ergebnis nicht, und eine laufende Sperrzeit in der Konfiguration
    unterdrueckt nichts. Genau diese Blindheit ist der Grund, warum die
    Ausnahme im Trip-Aufrufer leben muss."""
    uid = _uid("ac14")
    try:
        trip = _aufbau(uid, "ac14")
        sig = inspect.signature(DeviationAlertEngine.evaluate)
        pflicht = {
            name for name, p in sig.parameters.items()
            if name != "self" and p.default is inspect.Parameter.empty
            and p.kind is not inspect.Parameter.VAR_KEYWORD
        }
        assert pflicht == {"cached", "fresh", "config", "alert_state"}, (
            f"AC-14: `DeviationAlertEngine.evaluate()` darf keinen neuen "
            f"Pflichtparameter bekommen — der geteilte Baustein bliebe sonst "
            f"nicht signaturgleich. Gefunden: {sorted(pflicht)!r} (voller "
            f"Parametersatz: {sorted(sig.parameters)!r})"
        )

        cached, fresh = _lage(LAGE_HIGH)
        config = AlertEvaluationConfig(
            cooldown_minutes=COOLDOWN_MIN,
            metric_alert_levels=trip.display_config.metric_alert_levels,
            display_config=trip.display_config,
            zone=anchor_tz(trip, _AT),
        )

        def _auswerten() -> tuple:
            with freeze_time(_AT):
                r = DeviationAlertEngine().evaluate(
                    cached=TripSegmentWeatherAdapter.to_points(cached),
                    fresh=TripSegmentWeatherAdapter.to_points(fresh),
                    config=config, alert_state={},
                )
            return r.triggered, r.severity, r.suppressed_reason, len(r.changes)

        ohne_sperre = _auswerten()
        assert ohne_sperre[0] is True and ohne_sperre[1] == "HIGH", (
            f"AC-14 Vorbedingung: die eskalierende Lage muss in der Engine "
            f"anschlagen (Ergebnis {ohne_sperre!r})."
        )

        ThrottleStore(uid).record("trip", trip.id, _AT)
        mit_sperre = _auswerten()
        assert mit_sperre == ohne_sperre, (
            f"AC-14: eine laufende Sperrzeit darf das Ergebnis der geteilten "
            f"Engine nicht veraendern — sie kennt den Sperrtopf strukturell "
            f"nicht, und genau deshalb darf die Ueberholung nicht in ihr "
            f"leben. Ohne Sperre {ohne_sperre!r}, mit Sperre {mit_sperre!r}."
        )
    finally:
        _clean_user(uid)


# ─────────────────────────────── AC-15 ───────────────────────────────────────


@pytest.mark.timeout(120)
def test_ac15_der_durchbruch_eines_nutzers_sperrt_den_anderen_nicht():
    """AC-15. GIVEN Nutzer A hat den einen Durchbruch SEINER Zone heute
    bereits verbraucht, WHEN Nutzer B eine ebenso eskalierende Lage in
    DERSELBEN Zone prueft, THEN bricht B's Alarm trotzdem durch — jeder Nutzer
    fuehrt seinen eigenen Zaehler unter `data/users/<user_id>/`.

    Der Zonen-Schluessel (`Europe/Paris`) ist bei beiden identisch; nur die
    Mandantentrennung verhindert, dass A's verbrauchter Durchbruch B sperrt.
    Kein Cross-User-Datenleck ueber den geteilten Zonen-Schluessel.

    Der Test prueft ein EINTRETEN (B bricht durch) — die Zustellung ist selbst
    der Nachweis; zusaetzlich wird belegt, dass A's Zaehler dabei unberuehrt
    bleibt."""
    uid_a, uid_b = _uid("ac15-a"), _uid("ac15-b")
    try:
        at2 = _AT + timedelta(minutes=30)
        trip_a = _aufbau(uid_a, "ac15-a", tier=TIER_MIT_BUDGET)
        trip_b = _aufbau(uid_b, "ac15-b", tier=TIER_MIT_BUDGET)
        zone_a, _ = _zone_vorbelegen(uid_a, "ac15-a", _quelle(RATE_LOW_MM_H))
        zone_b, _ = _zone_vorbelegen(uid_b, "ac15-b", _quelle(RATE_LOW_MM_H))
        assert zone_a == zone_b, (
            f"Testkonstruktion: beide Nutzer muessen dieselbe Zone benutzen "
            f"({zone_a} vs. {zone_b}) — sonst pruefte der Test die "
            f"Zonen-Trennung statt der Mandantentrennung."
        )
        _basis_buchen(uid_a, trip_a, "LOW")
        _basis_buchen(uid_b, trip_b, "LOW")

        cached, fresh = _lage(LAGE_HIGH)
        assert AlarmPruefstrecke(user_id=uid_a, settings=_settings_all_channels()).lauf(
            at=at2, zweig="deviation", trip=trip_a,
            cached_weather=cached, fresh_weather=fresh,
        ).triggered_count == 1, (
            f"AC-15 Vorbedingung: A muss durchbrechen und damit SEINEN einen "
            f"Durchbruch verbrauchen (Gruende: {_gruende(uid_a, trip_a, at2)!r})."
        )
        assert _durchbruchszaehler(uid_a, zone_a, at2) == 1, (
            f"AC-15 Vorbedingung: A's Durchbruch muss gebucht sein, gefunden "
            f"{_durchbruchszaehler(uid_a, zone_a, at2)}."
        )
        assert _durchbruchszaehler(uid_b, zone_b, at2) == 0, (
            f"AC-15: B's Zaehler darf durch A's Durchbruch nicht wandern, "
            f"gefunden {_durchbruchszaehler(uid_b, zone_b, at2)}."
        )

        lauf_b = AlarmPruefstrecke(user_id=uid_b, settings=_settings_all_channels()).lauf(
            at=at2, zweig="deviation", trip=trip_b,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert lauf_b.triggered_count == 1, (
            f"AC-15: B muss trotz A's verbrauchtem Durchbruch durchbrechen — "
            f"der Deckel gilt je Nutzer, nicht je Zone ueber alle Nutzer (war "
            f"{lauf_b.triggered_count}, Gruende: {_gruende(uid_b, trip_b, at2)!r})."
        )
        assert _durchbruchszaehler(uid_b, zone_b, at2) == 1, (
            f"AC-15: B bucht seinen eigenen Durchbruch, gefunden "
            f"{_durchbruchszaehler(uid_b, zone_b, at2)}."
        )
        assert _durchbruchszaehler(uid_a, zone_a, at2) == 1, (
            f"AC-15: A's Zaehler bleibt durch B's Lauf unberuehrt, gefunden "
            f"{_durchbruchszaehler(uid_a, zone_a, at2)}."
        )
    finally:
        _clean_user(uid_a)
        _clean_user(uid_b)


# ─────────────────────────────── AC-16 ───────────────────────────────────────


def test_ac16_adr_0021_traegt_einen_datierten_s3c_nachtrag():
    """AC-16. ``# doc-compliance-test`` (Ausnahme von der Dateiinhalt-Regel,
    CLAUDE.md — Vorbild `test_alert_gate.py::test_ac21_…`). GIVEN die
    bestehenden ADR-0021-Nachtraege zu #2065 und #2050 S3b, WHEN diese
    Scheibe abgeschlossen ist, THEN traegt ADR-0021 einen DRITTEN, datierten
    Nachtrag mit Bezug auf `#2050 S3c`, einsortiert NACH dem S3b-Nachtrag,
    der Reichweite, Rangvergleich, geteilten Deckel, Saettigungsgrenze und die
    unberuehrten Stufen benennt.

    RED heute: der Nachtrag fehlt."""
    # doc-compliance-test
    adr_pfad = (
        Path(__file__).resolve().parents[2]
        / "docs" / "adr" / "0021-shared-deviation-alert-engine.md"
    )
    text = adr_pfad.read_text(encoding="utf-8")

    s3b_pos = text.find("Issue #2050 S3b")
    s3c_pos = text.find("Issue #2050 S3c")
    assert s3b_pos != -1, (
        f"Der bestehende S3b-Nachtrag darf nicht verschwinden: {adr_pfad}"
    )
    assert s3c_pos != -1 and s3c_pos > s3b_pos, (
        f"ADR-0021 muss einen Nachtrag mit Bezug auf 'Issue #2050 S3c' NACH "
        f"dem S3b-Nachtrag tragen (s3b_pos={s3b_pos}, s3c_pos={s3c_pos}): "
        f"{adr_pfad}"
    )
    nachtrag = text[s3c_pos:]
    for begriff, zweck in (
        ("Abweichungs", "die Reichweite (Abweichungs-Zweig)"),
        ("Rang", "der Rangvergleich statt der Faktor-Formel"),
        ("HIGH", "die Saettigungs-Grenze bei HIGH"),
        ("Ruhezeit", "die unberuehrte Ruhezeit"),
        ("Briefing", "das unberuehrte Briefing-Vorlauf-Gate"),
    ):
        assert begriff in nachtrag, (
            f"Der S3c-Nachtrag muss {zweck} benennen (Stichwort {begriff!r} "
            f"fehlt): {adr_pfad}"
        )
    assert "2026-08-23" in nachtrag, (
        f"Der S3c-Nachtrag muss datiert sein: {adr_pfad}"
    )
