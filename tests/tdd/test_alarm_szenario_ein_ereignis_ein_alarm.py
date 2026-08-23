"""TDD RED — Issue #2050 Scheibe S4c: ein Ereignis, ein Alarm (Szenario 5,
Anforderung C-2) — der ABWEICHUNGS-Zweig am quellenuebergreifenden
Ereignis-Identitaets-Register.

SPEC: docs/specs/modules/feat_2050_s4c_ein_ereignis_ein_alarm.md
(AC-1, AC-3, AC-4, AC-5, AC-9, AC-10, AC-13, AC-15, AC-18)

Heutiger Stand (gemessen 2026-08-23 gegen die echte Kette): der Δ-Zweig
`check_and_send_alerts()` ruft die Ereignis-Identitaet WEDER zum Pruefen NOCH
zum Registrieren (`trip_alert.py:310-657`, kein Aufruf im ganzen Block). Eine
amtliche Warnung um 10:00 und ein inhaltsgleicher Abweichungs-Alarm um 10:20
gehen deshalb als ZWEI volle Nachrichten raus, und das Register kennt den
Δ-Alarm hinterher nicht (Sonde: `register danach` unveraendert).

Die Paarung „Δ meldete, Radar zieht nach" bewacht heute allein der
Doppel-Alarm-Waechter (`trip_alert.py:1955-1984`) — halb tot (`precip:` ist
kein Metrik-Schluessel, der reale heisst `precip_sum_mm`) und ohne
Eskalations-Ausnahme. Gemessen: Regen-Δ -> Radar geht ungebremst raus
(AC-3 rot), Gewitter-Δ -> konvektiver Radar wird mit Grund
`double_alert_guard` GESCHLUCKT, obwohl er eine echte Verschaerfung ist
(AC-15 rot).

MESSGRUNDLAGE (Sonde 2026-08-23 gegen die ECHTE Engine, nicht angenommen):

* `precip_sum_mm` 2->18 mm = MODERATE, 2->45 mm = HIGH; `gust_max_kmh`
  10->90 km/h = HIGH; `thunder_level` auf Stufe „sensibel" NONE->MED =
  MODERATE (auf „standard" loest MED gar nicht aus).
* `alert_urgency.urgency_from_official_level`: Stufe 3 = MODERATE, Stufe 4 =
  HIGH. Daraus die Registereintraege unten.
* Radar: nicht-konvektiv bei 2,0 mm/h = MODERATE, konvektiv = HIGH.
* Die Segment-Kennung ist auf BEIDEN Seiten `"1"` — der Radar-Zweig
  normalisiert `active.segment_id`, der Δ-Zweig traegt `change.segment_id`.
  Nur deshalb koennen sich beide Zweige einen Registereintrag teilen.
* Das Melde-Gedaechtnis ist deltabasiert: eine WIEDERHOLUNG desselben Werts
  faellt schon dort heraus. Zweitlaeufe desselben Nutzers liegen deshalb
  immer weit vom zuletzt gemeldeten Wert entfernt.

🔴 Jede AC dieser Datei, die ein AUSBLEIBEN prueft, traegt eine
Positivkontrolle: derselbe Aufbau OHNE die gepruefte Bedingung (zweiter
Nutzer, eigener Datenpfad) muss zustellen. Ohne sie bewiese ein stiller Lauf
nichts — er koennte auch an der Sperrzeit, am Budget oder am Melde-
Gedaechtnis haengen.

Mock-frei: echte Trips, echte Zustandsdateien unter `get_data_dir(user_id)`,
echte `RadarNowcastService`-Instanz an ihrer DI-Naht `frame_source=`, alle
vier Kanaele ueber die Prüfstrecke (`tests/helpers/alarm_pruefstrecke.py`,
#2050 S1) an lokalen Loopback-Stubs. Kein `Mock()`/`patch()`/`MagicMock`,
kein Netz.
"""
from __future__ import annotations

import uuid
from datetime import date as date_type, datetime, timedelta, timezone

import pytest
from freezegun import freeze_time

from app.loader import save_trip
from app.models import (
    ForecastMeta,
    GPXPoint,
    MetricConfig,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripReportConfig,
    TripSegment,
    UnifiedWeatherDisplayConfig,
)
from app.trip import Stage, Trip, Waypoint
from services import alert_log, alert_urgency
from services.alert_state import AlertStateService
from services.deviation_alert_engine import DeviationAlertEngine
from services.official_alerts.models import OfficialAlert
from services.point_weather import AlertEvaluationConfig, TripSegmentWeatherAdapter
from services.trip_day import anchor_tz

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
from tests.tdd.test_952_onset_alert_fidelity import (
    _clean_user, _trip_with_active_segment,
)
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (
    _AT, _settings_all_channels, _write_tier,
)
from tests.tdd.test_alarm_szenario_briefing_ueberholung_zeitreihe import _radar
from tests.tdd.test_daily_budget_escalation import RATE_MODERAT_MM_H, _quelle
from tests.tdd.test_issue_1070_daily_alert_limit import LAT, LON

# Segmentfenster der synthetischen Wetterdaten (UTC) — es umschliesst `_AT`
# (10:00) und liefert damit den Zeitbezug, den der Δ-Zweig kuenftig statt des
# meist fehlenden `occurred_at` uebergibt (Befund B der Kontext-Kartierung).
_SEG_START = datetime(2026, 4, 5, 8, 0, tzinfo=timezone.utc)
_SEG_END = datetime(2026, 4, 5, 12, 0, tzinfo=timezone.utc)


def _uid(tag: str) -> str:
    return f"tdd-2050s4c-{tag}-{uuid.uuid4().hex[:6]}"


def _wd(
    segment_id: int | str = 1, *,
    start: datetime | None = _SEG_START, end: datetime | None = _SEG_END,
    **summary,
) -> SegmentWeatherData:
    """Wetterdaten EINES Segments mit frei setzbarem Zeitfenster.

    `start`/`end` sind hier bewusst steuerbar (anders als im Bestandsfixture
    `test_issue_1070_daily_alert_limit._weather_data`): der Δ-Zweig bildet
    seinen Zeitbezug kuenftig aus genau diesen beiden Werten, und AC-9/AC-10
    haengen daran."""
    segment = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(
            lat=LAT, lon=LON, elevation_m=1000, distance_from_start_km=12.0,
        ),
        end_point=GPXPoint(
            lat=LAT + 0.1, lon=LON + 0.1, elevation_m=1500,
            distance_from_start_km=18.0,
        ),
        start_time=start, end_time=end, duration_hours=4.0, distance_km=6.0,
        ascent_m=500, descent_m=0,
    )
    return SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(**summary),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


_ALARM_METRIKEN = {
    "precipitation_sum": "standard",
    # „sensibel", damit eine MITTLERE Gewitterstufe ueberhaupt meldefaehig
    # ist (gemessen: auf „standard" loest NONE->MED nicht aus). AC-15 braucht
    # einen Δ-Gewitteralarm, der UNTER der konvektiven Radar-Stufe liegt.
    "thunder_level": "sensibel",
    "wind_gust": "standard",
}
_ANZEIGE_METRIKEN = ("precipitation", "thunder", "gust")


def _trip_delta(
    trip_id: str, *, cooldown: int = 0, levels: dict | None = None,
    metrics: tuple = _ANZEIGE_METRIKEN, kanaele: bool = True,
) -> Trip:
    """Reiner Abweichungs-Trip (nur im Speicher, wie `_deviation_trip` aus
    #1070): `check_and_send_alerts()` bekommt ihn direkt uebergeben.

    `levels`/`metrics` sind steuerbar, weil AC-7 (Schnee) eine Metrik ausserhalb
    des Standardsatzes braucht; `kanaele=False` erzeugt einen Trip ohne jeden
    Versandkanal (AC-17)."""
    stage = Stage(
        id="T1", name="Tag 1", date=date_type(2026, 4, 5),
        waypoints=[Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0)],
    )
    trip = Trip(
        id=trip_id, name="S4c Abweichungs-Trip", stages=[stage],
        display_config=UnifiedWeatherDisplayConfig(
            trip_id=trip_id,
            metrics=[MetricConfig(metric_id=m, enabled=True) for m in metrics],
            metric_alert_levels=dict(levels if levels is not None else _ALARM_METRIKEN),
        ),
    )
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=False, send_telegram=kanaele,
        alert_on_changes=True,
    )
    trip.alert_cooldown_minutes = cooldown
    return trip


def _trip_delta_und_radar(uid: str, trip_id: str, *, cooldown: int = 120) -> Trip:
    """Trip, der BEIDE Zweige traegt: aktives Segment fuer `check_radar_alerts()`
    (das seine Trips von PLATTE liest) und Alarm-Metriken fuer den Δ-Zweig.

    Ohne diesen gemeinsamen Trip liefen Δ und Radar auf verschiedenen
    `entity_id` — das Register ist pro Trip gefuehrt, und die Paarung waere
    strukturell gar nicht herstellbar."""
    config = TripReportConfig(
        trip_id=trip_id, alert_on_changes=True, send_email=True, send_telegram=True,
    )
    with freeze_time(_AT):
        trip = _trip_with_active_segment(trip_id, config)
    trip.display_config = UnifiedWeatherDisplayConfig(
        trip_id=trip_id,
        metrics=[MetricConfig(metric_id=m, enabled=True) for m in _ANZEIGE_METRIKEN],
        metric_alert_levels=dict(_ALARM_METRIKEN),
    )
    trip.alert_cooldown_minutes = cooldown
    with freeze_time(_AT):
        save_trip(trip, user_id=uid)
    return trip


def _strecke(uid: str) -> AlarmPruefstrecke:
    _write_tier(uid, "premium")
    return AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())


def _amtlich(level: int, *, von: datetime, bis: datetime) -> OfficialAlert:
    return OfficialAlert(
        source="tdd-2050-s4c", hazard="thunderstorm", level=level,
        label="Gewitterwarnung", valid_from=von, valid_to=bis,
    )


def _amtlicher_vorlauf(
    strecke: AlarmPruefstrecke, uid: str, trip: Trip, *, level: int = 3,
    von: datetime | None = None, bis: datetime | None = None, at: datetime = _AT,
) -> dict:
    """ECHTER amtlicher Alarm-Lauf — er legt den Registereintrag ueber den
    produktiven Weg an (`_send_official_alert_only` -> `record_event_identity`),
    nicht per Hand. Liefert den entstandenen Eintrag zurueck."""
    alert = _amtlich(
        level,
        von=von if von is not None else at - timedelta(hours=1),
        bis=bis if bis is not None else at + timedelta(hours=6),
    )
    lauf = strecke.lauf(
        at=at, zweig="official", trip=trip, official_notices=[(alert, ["1"])],
    )
    assert lauf.triggered_count == 1, (
        f"Testaufbau: der amtliche Vorlauf muss zustellen und registrieren "
        f"(war {lauf.triggered_count})."
    )
    eintraege = _register(uid, trip.id)
    assert len(eintraege) == 1, (
        f"Testaufbau: genau EIN Registereintrag nach dem amtlichen Lauf, "
        f"gefunden: {eintraege!r}"
    )
    return next(iter(eintraege.values()))


def _register(uid: str, trip_id: str) -> dict:
    state = AlertStateService(user_id=uid).load(trip_id)
    return {k: v for k, v in state.items() if k.startswith("event_identity:")}


def _gruende(uid: str, trip_id: str, seit: datetime) -> set:
    """Nicht-Zustellungs-Gruende, die der PRUEFLING selbst protokolliert hat —
    kein Dateiinhalt-Check."""
    vorfaelle = alert_log.read_undelivered(
        uid, entity_id=trip_id, entity_type="trip", since=seit,
    )
    return {g for v in vorfaelle for g in v.reasons}


def _dringlichkeit(uid: str, trip: Trip, cached: list, fresh: list, at: datetime) -> str:
    """Die Stufe, mit der ein Prueflauf zu `at` TATSAECHLICH rechnet — aus der
    ECHTEN Engine mit dem Melde-Gedaechtnis von Platte und der produktiven
    Ableitung `alert_urgency.urgency_from_changes()`. Kein Literal, sonst
    bliebe die Bildungsstelle unbewacht."""
    config = AlertEvaluationConfig(
        cooldown_minutes=trip.alert_cooldown_minutes,
        metric_alert_levels=(
            getattr(trip.display_config, "metric_alert_levels", None)
            if trip.display_config else None
        ),
        display_config=trip.display_config, zone=anchor_tz(trip, at),
    )
    with freeze_time(at):
        ergebnis = DeviationAlertEngine().evaluate(
            cached=TripSegmentWeatherAdapter.to_points(cached),
            fresh=TripSegmentWeatherAdapter.to_points(fresh),
            config=config,
            alert_state=AlertStateService(user_id=uid).load(trip.id),
        )
    return alert_urgency.urgency_from_changes(list(ergebnis.changes))


def _kanaele(lauf) -> dict:
    return {
        "mail": len(lauf.mail), "telegram": len(lauf.telegram),
        "sms": len(lauf.sms), "premium_sms": len(lauf.premium_sms),
    }


# Die drei gemessenen Lagen (s. Moduldoku).
def _regen(von: float, nach: float, **kw) -> tuple[list, list]:
    return [_wd(1, precip_sum_mm=von, **kw)], [_wd(1, precip_sum_mm=nach, **kw)]


# ─────────────────────────────── AC-1 ────────────────────────────────────────


@pytest.mark.timeout(120)
def test_ac1_amtlicher_alarm_entdoppelt_den_nachfolgenden_abweichungsalarm():
    """AC-1. GIVEN eine amtliche Warnung (Klasse `wet`, Segment 1,
    ueberlappendes Zeitfenster, MODERATE) wurde zugestellt und registriert,
    WHEN 20 Minuten spaeter ein Abweichungs-Alarm mit AUSSCHLIESSLICH nassen
    Aenderungen fuer dasselbe Segment und ohne hoehere Dringlichkeit geprueft
    wird, THEN bleibt er still — auf KEINEM der vier Kanaele, und im Protokoll
    steht `event_duplicate`.

    Positivkontrolle (Pflicht, es wird ein AUSBLEIBEN geprueft): ein zweiter
    Nutzer mit identischem Δ-Lauf, aber OHNE amtlichen Vorlauf, stellt zu.
    Ohne sie koennte die Stille auch von Sperrzeit, Budget oder Melde-
    Gedaechtnis stammen.

    RED heute: der Δ-Zweig fragt das Register gar nicht — der Alarm geht raus
    (gemessen: `triggered_count == 1`, Telegram bedient)."""
    uid, ctrl = _uid("ac1"), _uid("ac1-ctrl")
    try:
        trip = _trip_delta("trip-s4c-ac1")
        strecke = _strecke(uid)
        eintrag = _amtlicher_vorlauf(strecke, uid, trip, level=3)

        at2 = _AT + timedelta(minutes=20)
        cached, fresh = _regen(2.0, 18.0)
        stufe = _dringlichkeit(uid, trip, cached, fresh, at2)
        assert not alert_urgency.exceeds(stufe, eintrag["severity"]), (
            f"Testkonstruktion: der Δ-Lauf ({stufe!r}) darf den Registereintrag "
            f"({eintrag['severity']!r}) NICHT im Rang uebersteigen — sonst "
            f"maesse der Test die Eskalations-Ausnahme statt der Entdopplung."
        )

        lauf = strecke.lauf(
            at=at2, zweig="deviation", trip=trip,
            cached_weather=cached, fresh_weather=fresh,
        )

        assert lauf.triggered_count == 0, (
            f"AC-1: der Abweichungs-Alarm muss als Duplikat der amtlichen "
            f"Warnung still bleiben (war {lauf.triggered_count})."
        )
        assert _kanaele(lauf) == {
            "mail": 0, "telegram": 0, "sms": 0, "premium_sms": 0,
        }, f"AC-1: kein Kanal darf bedient werden: {_kanaele(lauf)!r}"
        assert alert_log.REASON_EVENT_DUPLICATE in _gruende(
            uid, trip.id, _AT - timedelta(hours=1),
        ), (
            f"AC-1: der Vorfall muss mit gate_reason="
            f"{alert_log.REASON_EVENT_DUPLICATE!r} protokolliert sein, "
            f"gefunden: {_gruende(uid, trip.id, _AT - timedelta(hours=1))!r}"
        )

        # Positivkontrolle: derselbe Δ-Lauf ohne amtlichen Vorlauf.
        kontrolle = _strecke(ctrl).lauf(
            at=at2, zweig="deviation", trip=_trip_delta("trip-s4c-ac1"),
            cached_weather=cached, fresh_weather=fresh,
        )
        assert kontrolle.triggered_count == 1, (
            f"AC-1 Positivkontrolle: ohne den amtlichen Registereintrag MUSS "
            f"derselbe Lauf zustellen (war {kontrolle.triggered_count}) — "
            f"sonst prueft der Test die Entdopplung gar nicht."
        )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


# ─────────────────────────────── AC-3 ────────────────────────────────────────


@pytest.mark.timeout(120)
def test_ac3_radar_nach_registriertem_abweichungsalarm_wird_keine_zweite_vollnachricht():
    """AC-3. GIVEN ein Abweichungs-Alarm mit Nass-Anteil wurde zugestellt und
    registriert, WHEN danach ein Radar-Alarm derselben Zelle OHNE hoehere
    Dringlichkeit geprueft wird, THEN geht er nicht als zweite VOLLE Nachricht
    raus.

    Positivkontrolle: derselbe Radar-Lauf bei einem zweiten Nutzer ohne
    Δ-Vorlauf stellt zu.

    RED heute: der Δ-Alarm registriert nichts, und der Doppel-Alarm-Waechter
    liest den toten Schluessel `precip:<segment>` (der reale Name lautet
    `precip_sum_mm`) — der Radar-Alarm geht ungebremst als zweite volle
    Nachricht raus (gemessen: `triggered_count == 1`)."""
    uid, ctrl = _uid("ac3"), _uid("ac3-ctrl")
    try:
        strecke = _strecke(uid)
        trip = _trip_delta_und_radar(uid, "trip-s4c-ac3")
        cached, fresh = _regen(2.0, 18.0)
        delta = strecke.lauf(
            at=_AT, zweig="deviation", trip=trip,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert delta.triggered_count == 1, (
            f"AC-3 Vorbedingung: der Δ-Lauf muss zustellen (war "
            f"{delta.triggered_count})."
        )

        at2 = _AT + timedelta(minutes=30)
        radar = strecke.lauf(
            at=at2, zweig="radar", trip=trip,
            radar_service=_radar(_quelle(RATE_MODERAT_MM_H)),
        )
        assert radar.triggered_count == 0, (
            f"AC-3: der Radar-Alarm derselben Zelle darf keine zweite volle "
            f"Nachricht sein (war {radar.triggered_count}, Kanaele "
            f"{_kanaele(radar)!r})."
        )
        assert _kanaele(radar) == {
            "mail": 0, "telegram": 0, "sms": 0, "premium_sms": 0,
        }, f"AC-3: kein Kanal-Zuwachs erlaubt: {_kanaele(radar)!r}"

        # Positivkontrolle: gleicher Radar-Lauf ohne Δ-Vorlauf.
        kstrecke = _strecke(ctrl)
        _trip_delta_und_radar(ctrl, "trip-s4c-ac3")
        kontrolle = kstrecke.lauf(
            at=at2, zweig="radar", trip=trip,
            radar_service=_radar(_quelle(RATE_MODERAT_MM_H)),
        )
        assert kontrolle.triggered_count == 1, (
            f"AC-3 Positivkontrolle: ohne den Δ-Vorlauf MUSS derselbe "
            f"Radar-Lauf zustellen (war {kontrolle.triggered_count})."
        )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


# ─────────────────────────────── AC-4 ────────────────────────────────────────


@pytest.mark.timeout(120)
def test_ac4_echte_verschaerfung_bricht_durch_die_ereignis_identitaet():
    """AC-4. GIVEN ein Registereintrag mit MODERATE existiert fuer
    Segment/Zeitfenster, WHEN ein Abweichungs-Alarm mit ECHT hoeherer
    Dringlichkeit (HIGH) fuer dasselbe Segment geprueft wird, THEN wird er
    IMMER zugestellt.

    Positivkontrolle: derselbe Aufbau mit einem GLEICHRANGIGEN Δ-Lauf bleibt
    still — nur so ist belegt, dass die Zustellung an der Verschaerfung haengt
    und nicht daran, dass die Entdopplung ueberhaupt nicht greift.

    RED heute: die Positivkontrolle stellt zu (kein Gate im Δ-Zweig)."""
    uid, ctrl = _uid("ac4"), _uid("ac4-ctrl")
    try:
        trip = _trip_delta("trip-s4c-ac4")
        strecke = _strecke(uid)
        eintrag = _amtlicher_vorlauf(strecke, uid, trip, level=3)

        at2 = _AT + timedelta(minutes=20)
        cached, fresh = _regen(2.0, 45.0)
        stufe = _dringlichkeit(uid, trip, cached, fresh, at2)
        assert alert_urgency.exceeds(stufe, eintrag["severity"]), (
            f"Testkonstruktion: der Δ-Lauf ({stufe!r}) MUSS den Registereintrag "
            f"({eintrag['severity']!r}) im Rang echt uebersteigen."
        )

        lauf = strecke.lauf(
            at=at2, zweig="deviation", trip=trip,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert lauf.triggered_count == 1, (
            f"AC-4: eine echte Verschaerfung muss IMMER zugestellt werden "
            f"(war {lauf.triggered_count}, Gruende "
            f"{_gruende(uid, trip.id, _AT - timedelta(hours=1))!r})."
        )
        assert lauf.telegram, (
            f"AC-4: der Durchbruch muss den konfigurierten Kanal erreichen: "
            f"{_kanaele(lauf)!r}"
        )

        # Positivkontrolle: gleichrangiger Lauf im selben Aufbau bleibt still.
        ktrip = _trip_delta("trip-s4c-ac4")
        kstrecke = _strecke(ctrl)
        keintrag = _amtlicher_vorlauf(kstrecke, ctrl, ktrip, level=3)
        kcached, kfresh = _regen(2.0, 18.0)
        kstufe = _dringlichkeit(ctrl, ktrip, kcached, kfresh, at2)
        assert not alert_urgency.exceeds(kstufe, keintrag["severity"]), (
            f"Testkonstruktion der Positivkontrolle: {kstufe!r} darf "
            f"{keintrag['severity']!r} nicht uebersteigen."
        )
        kontrolle = kstrecke.lauf(
            at=at2, zweig="deviation", trip=ktrip,
            cached_weather=kcached, fresh_weather=kfresh,
        )
        assert kontrolle.triggered_count == 0, (
            f"AC-4 Positivkontrolle: ein GLEICHRANGIGER Δ-Lauf muss im selben "
            f"Aufbau still bleiben (war {kontrolle.triggered_count}) — sonst "
            f"belegt der Durchbruch oben nichts."
        )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


# ─────────────────────────────── AC-5 ────────────────────────────────────────


@pytest.mark.timeout(120)
def test_ac5_gemischtes_buendel_wird_nie_unterdrueckt():
    """AC-5. GIVEN ein passender Registereintrag (HIGH) existiert, WHEN ein
    Abweichungs-Alarm neben der nassen Aenderung auch eine NICHT-nasse
    (`gust_max_kmh`) buendelt, THEN wird er NIE unterdrueckt — die
    Gefahrenklasse des Laufs ist `None`.

    Positivkontrolle: derselbe Aufbau mit rein nassem Buendel derselben
    Dringlichkeit bleibt still. Allein die Beimischung entscheidet — die
    Dringlichkeit ist in beiden Faellen HIGH und damit als Erklaerung
    ausgeschlossen (Registereintrag ebenfalls HIGH, `exceeds` also False).

    RED heute: die Positivkontrolle stellt zu (kein Gate im Δ-Zweig)."""
    uid, ctrl = _uid("ac5"), _uid("ac5-ctrl")
    try:
        trip = _trip_delta("trip-s4c-ac5")
        strecke = _strecke(uid)
        eintrag = _amtlicher_vorlauf(strecke, uid, trip, level=4)

        at2 = _AT + timedelta(minutes=20)
        cached = [_wd(1, precip_sum_mm=2.0, gust_max_kmh=10.0)]
        fresh = [_wd(1, precip_sum_mm=45.0, gust_max_kmh=90.0)]
        stufe = _dringlichkeit(uid, trip, cached, fresh, at2)
        assert not alert_urgency.exceeds(stufe, eintrag["severity"]), (
            f"Testkonstruktion: das gemischte Buendel ({stufe!r}) darf den "
            f"Registereintrag ({eintrag['severity']!r}) NICHT uebersteigen — "
            f"sonst kaeme es schon ueber die Eskalation durch und der Test "
            f"maesse die Beimischung nicht."
        )

        lauf = strecke.lauf(
            at=at2, zweig="deviation", trip=trip,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert lauf.triggered_count == 1, (
            f"AC-5: ein Buendel mit nicht-nassem Anteil darf NIE entdoppelt "
            f"werden (war {lauf.triggered_count}, Gruende "
            f"{_gruende(uid, trip.id, _AT - timedelta(hours=1))!r})."
        )

        # Positivkontrolle: rein nasses Buendel derselben Stufe bleibt still.
        ktrip = _trip_delta("trip-s4c-ac5")
        kstrecke = _strecke(ctrl)
        keintrag = _amtlicher_vorlauf(kstrecke, ctrl, ktrip, level=4)
        kcached, kfresh = _regen(2.0, 45.0)
        kstufe = _dringlichkeit(ctrl, ktrip, kcached, kfresh, at2)
        assert kstufe == stufe and not alert_urgency.exceeds(
            kstufe, keintrag["severity"],
        ), (
            f"Testkonstruktion der Positivkontrolle: dieselbe Stufe wie oben "
            f"({kstufe!r} vs. {stufe!r}), kein Rang-Durchbruch."
        )
        kontrolle = kstrecke.lauf(
            at=at2, zweig="deviation", trip=ktrip,
            cached_weather=kcached, fresh_weather=kfresh,
        )
        assert kontrolle.triggered_count == 0, (
            f"AC-5 Positivkontrolle: das rein nasse Buendel muss still bleiben "
            f"(war {kontrolle.triggered_count}) — sonst belegt der Durchlass "
            f"oben nicht, dass die Beimischung entschieden hat."
        )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


# ─────────────────────────────── AC-9 ────────────────────────────────────────


@pytest.mark.timeout(120)
def test_ac9_ohne_bildbares_zeitfenster_entsteht_kein_match():
    """AC-9. GIVEN die nasse Aenderung haengt an einem Segment, fuer das KEIN
    Start-/Endzeitpunkt auffindbar ist, WHEN ein Abweichungs-Alarm dafuer
    geprueft wird, THEN entsteht kein Zeitintervall, die Ereignis-Identitaet
    erzeugt fail-soft KEIN Match, und die Meldung geht durch.

    Positivkontrolle: dasselbe Segment MIT Zeitfenster wird im identischen
    Aufbau unterdrueckt — der Registereintrag haette also gematcht.

    RED heute: die Positivkontrolle stellt zu (kein Gate im Δ-Zweig)."""
    uid, ctrl = _uid("ac9"), _uid("ac9-ctrl")
    try:
        trip = _trip_delta("trip-s4c-ac9")
        strecke = _strecke(uid)
        _amtlicher_vorlauf(strecke, uid, trip, level=3)

        at2 = _AT + timedelta(minutes=20)
        ohne_zeiten_cached = [_wd(1, start=None, end=None, precip_sum_mm=2.0)]
        ohne_zeiten_fresh = [_wd(1, start=None, end=None, precip_sum_mm=18.0)]
        lauf = strecke.lauf(
            at=at2, zweig="deviation", trip=trip,
            cached_weather=ohne_zeiten_cached, fresh_weather=ohne_zeiten_fresh,
        )
        assert lauf.triggered_count == 1, (
            f"AC-9: ohne bildbares Zeitfenster darf NICHTS unterdrueckt werden "
            f"(war {lauf.triggered_count}, Gruende "
            f"{_gruende(uid, trip.id, _AT - timedelta(hours=1))!r})."
        )

        # Positivkontrolle: identischer Aufbau, aber MIT Segmentzeiten.
        ktrip = _trip_delta("trip-s4c-ac9")
        kstrecke = _strecke(ctrl)
        _amtlicher_vorlauf(kstrecke, ctrl, ktrip, level=3)
        kcached, kfresh = _regen(2.0, 18.0)
        kontrolle = kstrecke.lauf(
            at=at2, zweig="deviation", trip=ktrip,
            cached_weather=kcached, fresh_weather=kfresh,
        )
        assert kontrolle.triggered_count == 0, (
            f"AC-9 Positivkontrolle: MIT Segmentzeiten muss derselbe Lauf "
            f"unterdrueckt werden (war {kontrolle.triggered_count}) — sonst "
            f"beweist der Durchlass oben nichts ueber den fehlenden Zeitbezug."
        )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


# ─────────────────────────────── AC-10 ───────────────────────────────────────


@pytest.mark.timeout(120)
def test_ac10_wesentlich_weiter_reichendes_segmentfenster_kommt_durch():
    """AC-10 (V1-Ausnahme, unveraendert vererbt). GIVEN ein Registereintrag
    deckt nur eine kurze Zeitspanne ab, WHEN ein gleichrangiger
    Abweichungs-Alarm ein Segmentfenster meldet, das WESENTLICH weiter reicht,
    THEN kommt er durch.

    Positivkontrolle: derselbe Δ-Lauf gegen einen Registereintrag, der bis
    ueber das Segmentende hinaus abdeckt, bleibt still.

    RED heute: die Positivkontrolle stellt zu (kein Gate im Δ-Zweig)."""
    uid, ctrl = _uid("ac10"), _uid("ac10-ctrl")
    try:
        # Weit reichendes Segmentfenster (bis _AT + 10 h) gegen einen
        # Registereintrag, der nur bis _AT + 10 min abdeckt.
        weit_start, weit_ende = _AT - timedelta(hours=2), _AT + timedelta(hours=10)
        cached = [_wd(1, start=weit_start, end=weit_ende, precip_sum_mm=2.0)]
        fresh = [_wd(1, start=weit_start, end=weit_ende, precip_sum_mm=18.0)]

        trip = _trip_delta("trip-s4c-ac10")
        strecke = _strecke(uid)
        eintrag = _amtlicher_vorlauf(
            strecke, uid, trip, level=3,
            von=_AT - timedelta(hours=1), bis=_AT + timedelta(minutes=10),
        )
        at2 = _AT + timedelta(minutes=20)
        stufe = _dringlichkeit(uid, trip, cached, fresh, at2)
        assert not alert_urgency.exceeds(stufe, eintrag["severity"]), (
            f"Testkonstruktion: {stufe!r} darf {eintrag['severity']!r} nicht "
            f"uebersteigen — sonst maesse der Test die Eskalation statt V1."
        )

        lauf = strecke.lauf(
            at=at2, zweig="deviation", trip=trip,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert lauf.triggered_count == 1, (
            f"AC-10: ein wesentlich weiter reichendes Segmentfenster ist neue "
            f"Information und muss durchkommen (war {lauf.triggered_count})."
        )

        # Positivkontrolle: Registereintrag deckt ueber das Segmentende hinaus.
        ktrip = _trip_delta("trip-s4c-ac10")
        kstrecke = _strecke(ctrl)
        _amtlicher_vorlauf(
            kstrecke, ctrl, ktrip, level=3,
            von=_AT - timedelta(hours=1), bis=weit_ende + timedelta(hours=2),
        )
        kontrolle = kstrecke.lauf(
            at=at2, zweig="deviation", trip=ktrip,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert kontrolle.triggered_count == 0, (
            f"AC-10 Positivkontrolle: deckt der Registereintrag das ganze "
            f"Segmentfenster ab, muss der Lauf still bleiben (war "
            f"{kontrolle.triggered_count})."
        )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


# ─────────────────────────────── AC-13 ───────────────────────────────────────


@pytest.mark.timeout(120)
def test_ac13_radar_nachtrag_nennt_die_wetterabweichung_statt_einer_amtlichen_warnung():
    """AC-13. GIVEN ein Abweichungs-Alarm wurde registriert (Quelle
    `deviation`), WHEN danach ein Radar-Alarm derselben Zelle mit ECHTER
    Verschaerfung geprueft wird, THEN geht er in NACHTRAGSFORM heraus — mit
    einer Bezeichnung fuer die Vorhersage-Abweichung, NICHT als „Ergaenzung
    zur amtlichen Warnung" (es lag keine amtliche Warnung vor, B-2).

    Positivkontrolle: nach einer echten AMTLICHEN Warnung traegt derselbe
    Radar-Lauf weiterhin den amtlichen Nachtragsbezug — sie belegt, dass der
    Nachtrags-Mechanismus im Aufbau ueberhaupt greift und der Test nicht nur
    einen abwesenden Text feiert.

    RED heute: der Radar-Alarm nach einem Δ-Alarm ist ueberhaupt kein Nachtrag
    (kein Bezugstext im Kanalinhalt), weil der Δ-Zweig nichts registriert."""
    uid, ctrl = _uid("ac13"), _uid("ac13-ctrl")
    try:
        strecke = _strecke(uid)
        trip = _trip_delta_und_radar(uid, "trip-s4c-ac13")
        cached, fresh = _regen(2.0, 18.0)
        delta = strecke.lauf(
            at=_AT, zweig="deviation", trip=trip,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert delta.triggered_count == 1, (
            f"AC-13 Vorbedingung: der Δ-Lauf muss zustellen (war "
            f"{delta.triggered_count})."
        )

        at2 = _AT + timedelta(minutes=30)
        radar = strecke.lauf(
            at=at2, zweig="radar", trip=trip,
            radar_service=_radar(_quelle(RATE_MODERAT_MM_H, konvektiv=True)),
        )
        assert radar.triggered_count == 1, (
            f"AC-13: die Verschaerfung muss zugestellt werden (war "
            f"{radar.triggered_count})."
        )
        text = "\n".join(radar.telegram + [b for _s, b in radar.mail])
        assert "Ergänzung" in text, (
            f"AC-13: der Radar-Alarm muss als NACHTRAG mit Bezug auf die "
            f"vorherige Meldung herausgehen: {text!r}"
        )
        assert "amtlich" not in text.lower(), (
            f"AC-13: der Bezug darf keine amtliche Warnung behaupten — es lag "
            f"keine vor: {text!r}"
        )

        # Positivkontrolle: nach einer ECHTEN amtlichen Warnung bleibt der
        # amtliche Nachtragsbezug erhalten.
        kstrecke = _strecke(ctrl)
        ktrip = _trip_delta_und_radar(ctrl, "trip-s4c-ac13")
        _amtlicher_vorlauf(kstrecke, ctrl, ktrip, level=3)
        kradar = kstrecke.lauf(
            at=at2, zweig="radar", trip=ktrip,
            radar_service=_radar(_quelle(RATE_MODERAT_MM_H, konvektiv=True)),
        )
        ktext = "\n".join(kradar.telegram + [b for _s, b in kradar.mail])
        assert kradar.triggered_count == 1 and "amtlich" in ktext.lower(), (
            f"AC-13 Positivkontrolle: nach einer amtlichen Warnung muss der "
            f"Nachtrag sie weiterhin nennen (count={kradar.triggered_count}): "
            f"{ktext!r}"
        )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


# ─────────────────────────────── AC-15 ───────────────────────────────────────


@pytest.mark.timeout(120)
def test_ac15_gewitter_verschaerfung_kommt_nach_der_abloesung_durch():
    """AC-15. GIVEN ein Abweichungs-Alarm hat eine mittlere Gewitterstufe
    gemeldet (MODERATE) und damit genau den Schluessel geschrieben, auf den
    der alte Doppel-Alarm-Waechter anspringt
    (`thunder_level_max:<segment_id>`), WHEN innerhalb desselben
    Sperrzeit-Fensters ein KONVEKTIVER Radar-Alarm (HIGH) geprueft wird,
    THEN kommt die Verschaerfung DURCH — der abgeloeste Waechter kannte keine
    Eskalations-Ausnahme und haette sie geschluckt (Anforderung A-3).

    Der Test prueft ein EINTRETEN; die Zustellung ist selbst der Nachweis.
    Die Vorbedingung („der alte Waechter waere hier scharf gewesen") wird
    ausdruecklich gemessen: der Schluessel steht im Zustand, und die Sperrzeit
    des Trips ist laenger als der Abstand der beiden Laeufe.

    RED heute (gemessen): `triggered_count == 0`, protokollierter Grund
    `double_alert_guard`."""
    uid = _uid("ac15")
    try:
        strecke = _strecke(uid)
        trip = _trip_delta_und_radar(uid, "trip-s4c-ac15", cooldown=120)
        cached = [_wd(1, thunder_level_max=ThunderLevel.NONE)]
        fresh = [_wd(1, thunder_level_max=ThunderLevel.MED)]
        at2 = _AT + timedelta(minutes=30)

        delta_stufe = _dringlichkeit(uid, trip, cached, fresh, _AT)
        delta = strecke.lauf(
            at=_AT, zweig="deviation", trip=trip,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert delta.triggered_count == 1, (
            f"AC-15 Vorbedingung: der Gewitter-Δ muss zustellen (war "
            f"{delta.triggered_count})."
        )
        zustand = AlertStateService(user_id=uid).load(trip.id)
        assert "thunder_level_max:1" in zustand, (
            f"AC-15 Vorbedingung: der Δ-Lauf muss genau den Schluessel "
            f"schreiben, auf den der alte Doppel-Alarm-Waechter anspringt — "
            f"sonst waere er im Aufbau gar nicht scharf: {sorted(zustand)!r}"
        )
        assert (at2 - _AT) < timedelta(minutes=trip.alert_cooldown_minutes), (
            "AC-15 Vorbedingung: der zweite Lauf muss INNERHALB des alten "
            "Waechter-Fensters liegen."
        )

        radar = strecke.lauf(
            at=at2, zweig="radar", trip=trip,
            radar_service=_radar(_quelle(RATE_MODERAT_MM_H, konvektiv=True)),
        )
        assert radar.triggered_count == 1, (
            f"AC-15: die Gewitter-Verschaerfung gegenueber {delta_stufe!r} "
            f"muss durchkommen (war {radar.triggered_count}, Gruende "
            f"{_gruende(uid, trip.id, _AT - timedelta(hours=1))!r})."
        )
        assert alert_log.REASON_DOUBLE_ALERT_GUARD not in _gruende(
            uid, trip.id, _AT - timedelta(hours=1),
        ), (
            "AC-15: der abgeloeste Doppel-Alarm-Waechter darf fuer diese "
            "Paarung keinen Grund mehr erzeugen."
        )
    finally:
        _clean_user(uid)


# ─────────────────────────────── AC-18 ───────────────────────────────────────


@pytest.mark.timeout(120)
def test_ac18_registereintrag_von_nutzer_a_wirkt_nicht_auf_nutzer_b():
    """AC-18. GIVEN Nutzer A hat einen Ereignis-Identitaets-Registereintrag
    aus einem eigenen Abweichungs-Alarm hinterlassen, WHEN Nutzer B einen
    inhaltsgleichen Abweichungs-Alarm fuer sein eigenes, gleich benanntes
    Segment prueft, THEN bleibt B's Alarm unbeeinflusst — getrennte
    Registerpfade unter `data/users/<user_id>/`.

    Positivkontrolle: A's EIGENER Folgelauf derselben Stufe bleibt still.
    Ohne sie waere „B stellt zu" auch dann wahr, wenn die Entdopplung gar
    nicht existiert (heute genau der Fall — daher RED)."""
    a, b = _uid("ac18-a"), _uid("ac18-b")
    try:
        trip_a = _trip_delta("trip-s4c-ac18")
        strecke_a = _strecke(a)
        cached, fresh = _regen(2.0, 18.0)
        # VOR dem Lauf gemessen: danach steht der gemeldete Wert im
        # deltabasierten Melde-Gedaechtnis und dieselbe Lage ergaebe eine
        # andere Stufe.
        erst_stufe = _dringlichkeit(a, trip_a, cached, fresh, _AT)
        lauf_a1 = strecke_a.lauf(
            at=_AT, zweig="deviation", trip=trip_a,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert lauf_a1.triggered_count == 1, (
            f"AC-18 Vorbedingung: A's erster Lauf muss zustellen und "
            f"registrieren (war {lauf_a1.triggered_count})."
        )

        at2 = _AT + timedelta(minutes=20)
        # B: gleich benannter Trip, gleich benanntes Segment, gleiche Lage.
        trip_b = _trip_delta("trip-s4c-ac18")
        lauf_b = _strecke(b).lauf(
            at=at2, zweig="deviation", trip=trip_b,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert lauf_b.triggered_count == 1, (
            f"AC-18: B's Alarm darf von A's Registereintrag nicht beruehrt "
            f"werden (war {lauf_b.triggered_count})."
        )
        assert not _register(b, trip_b.id) or all(
            e.get("segment_ids") for e in _register(b, trip_b.id).values()
        ), "AC-18: B's Register darf nur B's eigene Eintraege fuehren."

        # Positivkontrolle: A's eigener Folgelauf derselben Stufe (weit genug
        # vom zuletzt gemeldeten Wert entfernt, damit nicht schon das
        # deltabasierte Melde-Gedaechtnis greift) bleibt still.
        a_cached, a_fresh = _regen(30.0, 47.0)
        a_stufe = _dringlichkeit(a, trip_a, a_cached, a_fresh, at2)
        assert a_stufe == erst_stufe, (
            f"Testkonstruktion: A's Folgelage muss dieselbe Stufe tragen wie "
            f"sein Ersteintrag ({a_stufe!r} vs. {erst_stufe!r}) — sonst maesse "
            f"die Kontrolle einen Rang-Unterschied statt der Entdopplung."
        )
        lauf_a2 = strecke_a.lauf(
            at=at2, zweig="deviation", trip=trip_a,
            cached_weather=a_cached, fresh_weather=a_fresh,
        )
        assert lauf_a2.triggered_count == 0, (
            f"AC-18 Positivkontrolle: A's eigener, gleichrangiger Folgelauf "
            f"muss an A's eigenem Registereintrag scheitern (war "
            f"{lauf_a2.triggered_count}) — sonst belegt B's Zustellung keine "
            f"Mandantentrennung."
        )
    finally:
        _clean_user(a)
        _clean_user(b)
