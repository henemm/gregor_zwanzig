"""TDD RED — Issue #2050 Scheibe S3b, Szenario 7: eine akute Eskalation
durchbricht das erschoepfte Tagesbudget (AC-15 bis AC-21).

SPEC: docs/specs/modules/feat_2050_s3b_budget_und_unterdrueckungsgrund.md

Heutiger Stand: die Tages-Obergrenze ist ein ausnahmsloser Stop. Eine sich
akut verschaerfende Gewitterlage verhungert damit hinter vier bereits
verschickten Meldungen desselben Tages, egal wie viel dringlicher sie
gegenueber diesen ist.

Der geforderte Mechanismus (existiert noch NICHT):

* `alert_daily_count.json` bekommt je Zonen-Eintrag zwei additive Felder —
  `max_urgency_sent` (hoechste heute in dieser Zone ZUGESTELLTE Stufe) und
  `escalation_breakthroughs` (verbrauchte Durchbrueche, Deckel 1).
* `alert_daily_limit.escalation_breaks_through(...)` verknuepft beide UND.
* Trip- und Ortsvergleich-Radarpfad laufen bei `daily_limit` weiter bis zur
  Dringlichkeits-Ableitung und entscheiden dort — dasselbe Caller-seitige
  Muster, mit dem #2065 die Sperrzeit-Ueberholung geloest hat.

MESSGRUNDLAGE (gemessen 2026-08-23 an diesem Aufbau, nicht angenommen):

* Trip-Zone ist `Europe/Paris` (`anchor_tz`), `_AT` = 10:00 UTC = 12:00
  Ortszeit; Tier `standard` -> Tageslimit 4.
* Radar-Rate -> Dringlichkeit ueber `alert_urgency.urgency_from_radar`:
  0,6 mm/h -> "Leichter Regen" -> LOW; 2,0 mm/h -> "Maessiger Regen" ->
  MODERATE; konvektiv -> "Starker Hagel/Gewitter" -> HIGH (jede Rate).
  Jede benutzte Stufe wird zusaetzlich am ECHTEN Nowcast-Ergebnis GEMESSEN
  (`_gemessene_dringlichkeit`), nicht nur behauptet.

🔴 `max_urgency_sent` wird NIRGENDS als Literal vorbelegt (Ausnahme: AC-19,
dort IST die Altdatei der Pruefgegenstand). Der Wert muss aus echten,
zugestellten Laeufen entstehen — sonst bliebe seine Bildungsstelle
(`record_nowcast_sent(urgency=...)` -> `increment()`) unbewacht.

🔴 SPERRZEIT BEWUSST AUS (`alert_cooldown_minutes = 0`): geprueft wird die
Tages-Obergrenze. Bliebe die Sperrzeit an, koennte die Stille eines
Folgelaufs auch von IHR kommen (#2065-Kette), und der Test bewachte nicht
mehr die Stufe, um die es geht. Die Zusammenarbeit BEIDER Ausnahmen ist in
`test_radar_cooldown_overtake.py` (AC-22) festgenagelt, wo die Sperrzeit
laeuft.

🔴 ZEITFENSTER: `_trip_with_active_segment` spannt das aktive Segment auf
`[jetzt-1 h, jetzt+3 h]` Ortszeit (`test_952_onset_alert_fidelity.py:125`).
Alle Laeufe liegen deshalb innerhalb von `_AT + 90 Min` — spaeter loest
`resolve_current_segment()` nichts mehr auf und der Lauf braeche VOR der
Gate-Kette ab.

Mock-frei: echte Trips/Presets auf Platte, echter `RadarNowcastService` an
seiner DI-Naht `frame_source=`, echte Zustandsdateien unter
`get_data_dir(user_id)`, Unterdrueckungsgrund ueber
`alert_log.read_undelivered()`. Kein `Mock()`/`patch()`/`MagicMock`, kein Netz.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from app.loader import get_data_dir, save_location
from services import alert_daily_limit, alert_log, alert_urgency
from services.radar_cache import reset_shared_radar_cache_for_tests
from services.trip_day import anchor_tz
from services.user_tier import daily_alert_limit

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
from tests.helpers.nowcast_gate_fixtures import (
    LOCATION_ZONE, clean_uid, compare_radar_service, fresh_uid, location,
    radar_preset, reset_radar_cache, settings_email_only, wet_frames,
    write_presets, write_user_tier,
)
from tests.tdd.test_952_onset_alert_fidelity import _clean_user
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (
    _AT, _radar_trip, _settings_all_channels, _write_tier,
)
from tests.tdd.test_alarm_szenario_briefing_ueberholung_zeitreihe import _radar

# Tier mit ENDLICHEM Tagesbudget — Premium hat gar keins (#1070 AC-3) und
# koennte das Szenario strukturell nicht herstellen.
TIER_MIT_BUDGET = "standard"
TAGESLIMIT = 4

RATE_LOW_MM_H = 0.6        # -> "Leichter Regen"  -> LOW
RATE_MODERAT_MM_H = 2.0    # -> "Maessiger Regen" -> MODERATE


def _uid(tag: str) -> str:
    return f"tdd-2050s3b-{tag}-{uuid.uuid4().hex[:6]}"


def _quelle(rate_mm_h: float, *, konvektiv: bool = False):
    """Echte `RadarFrame`-Quelle (kein Mock): ein nasser Frame acht Minuten
    voraus, also innerhalb des Ausloese-Horizonts (55 Min)."""
    def _frames(lat: float, lon: float) -> list:
        return wet_frames(
            onset_minutes=8, is_convective=konvektiv, rate=rate_mm_h,
        )
    return _frames


def _gemessene_dringlichkeit(trip, quelle, at: datetime) -> str:
    """Die Stufe, mit der der Prueflauf spaeter TATSAECHLICH rechnet — aus
    einem echten Nowcast-Abruf ueber dieselbe produktive Ableitung
    (`alert_urgency.urgency_from_radar`), nicht im Testkoerper nachgebaut.

    Der Frame-Cache ist ein PROZESS-Singleton mit Koordinaten-Schluessel
    (TTL 300 s): ohne Reset liefert der naechste Abruf die Frames dieses
    zurueck (#2050 S1, Falle 2 der Pruefstrecke)."""
    lat, lon = trip.stages[0].waypoints[0].lat, trip.stages[0].waypoints[0].lon
    with freeze_time(at):
        reset_shared_radar_cache_for_tests()
        ergebnis = _radar(quelle).get_nowcast(lat, lon)
        reset_shared_radar_cache_for_tests()
    return alert_urgency.urgency_from_radar(
        is_convective=ergebnis.is_convective,
        intensity_label=ergebnis.intensity_label,
    )


def _aufbau(uid: str, tag: str, *, quiet: tuple | None = None, **flags):
    """Nutzer mit endlichem Tagesbudget + Trip mit aktivem Segment.

    Sperrzeit AUS (s. Moduldoku). Die Ruhezeit wird — wie in
    `test_radar_cooldown_overtake.py::test_ac6…` — am Objekt gesetzt und
    ueber den PRODUKTIVEN `app.loader.save_trip()` gespeichert: der Pruefling
    liest die Trips von Platte (`load_all_trips`), ein nur am Objekt gesetzter
    Wert waere still wirkungslos."""
    _clean_user(uid)
    _write_tier(uid, TIER_MIT_BUDGET)
    kanaele = {
        "send_email": True, "send_telegram": True,
        "send_sms": False, "send_premium_sms": False,
    }
    kanaele.update(flags)
    with freeze_time(_AT):
        trip = _radar_trip(uid, f"trip-2050s3b-{tag}", **kanaele)
    trip.alert_cooldown_minutes = 0
    if quiet is not None:
        trip.alert_quiet_from, trip.alert_quiet_to = quiet
    with freeze_time(_AT):
        from app.loader import save_trip
        save_trip(trip, user_id=uid)
    return trip


def _zonen_eintrag(uid: str, zone: ZoneInfo, at: datetime) -> dict:
    """Der Zonen-Eintrag aus `alert_daily_count.json` fuer den Ortstag von
    `at`.

    Direkt aus der Datei gelesen — wie `read_daily_counter()` im Baukasten,
    aus demselben Grund: es gibt keine produktive Leseseite, die die beiden
    neuen Felder herausgibt (`load()` liefert nur den Zaehlerstand). Der Tag
    wird MITGEPRUEFT, sonst laese der Helfer stillschweigend einen Eintrag
    eines anderen Kalendertags."""
    pfad = get_data_dir(uid) / "alert_daily_count.json"
    if not pfad.exists():
        return {}
    eintrag = (json.loads(pfad.read_text()).get("zones") or {}).get(str(zone))
    if not isinstance(eintrag, dict):
        return {}
    tag = at.astimezone(zone).date().isoformat()
    assert eintrag.get("date") == tag, (
        f"Testaufbau: der Zonen-Eintrag von {zone} traegt den Tag "
        f"{eintrag.get('date')!r}, gemessen wird aber gegen {tag!r} — der "
        f"Lauf hat in einen ANDEREN Tageszaehler geschrieben."
    )
    return eintrag


def _budget_ausschoepfen(uid: str, at: datetime, zone: ZoneInfo) -> None:
    """Tageszaehler ueber den PRODUKTIVEN Schreibweg auf das Limit heben —
    dieselbe Zone, die auch das Gate benutzt (eine andere fuellte einen
    anderen Zaehler, #1726). Ohne `urgency=`: dieser Weg darf die hoechste
    zugestellte Stufe NICHT mitschreiben, sonst waere sie hier vorbelegt
    statt aus echten Laeufen entstanden."""
    limit = daily_alert_limit(uid)
    assert limit == TAGESLIMIT, (
        f"Testaufbau: Tier {TIER_MIT_BUDGET!r} muss Tageslimit {TAGESLIMIT} "
        f"haben, hat aber {limit!r}."
    )
    while alert_daily_limit.load(uid, at, zone) < limit:
        alert_daily_limit.increment(uid, at, zone)
    assert not alert_daily_limit.is_allowed(uid, at, zone, reason="nowcast"), (
        "Testaufbau: das Tagesbudget muss erschoepft sein."
    )


def _gruende(uid: str, trip, seit: datetime) -> set:
    """Alle Nicht-Zustellungs-Gruende, die der PRUEFLING selbst protokolliert
    hat (`alert_log.read_undelivered()`) — kein Dateiinhalt-Check."""
    vorfaelle = alert_log.read_undelivered(
        uid, entity_id=trip.id, entity_type="trip", since=seit,
    )
    return {g for v in vorfaelle for g in v.reasons}


def _durchbruchszaehler(uid: str, zone: ZoneInfo, at: datetime) -> int:
    return int(_zonen_eintrag(uid, zone, at).get("escalation_breakthroughs", 0))


# ─────────────────────────────── AC-15 ───────────────────────────────────────


@pytest.mark.timeout(60)
def test_ac15_akute_eskalation_durchbricht_das_erschoepfte_tagesbudget():
    """AC-15. GIVEN das Tagesbudget einer Zone ist erschoepft und die hoechste
    heute dort ZUGESTELLTE Stufe ist MODERATE — entstanden aus einem echten
    Lauf, nicht vorbelegt —, WHEN eine konvektive Lage (HIGH) geprueft wird,
    THEN geht der Alarm trotzdem raus und die Zone hat danach GENAU EINEN
    verbrauchten Durchbruch.

    RED heute an zwei Stellen: (1) `max_urgency_sent` entsteht gar nicht,
    weil `increment()` die Stufe nicht kennt; (2) der Lauf schweigt mit Grund
    `daily_limit`."""
    uid = _uid("ac15")
    try:
        trip = _aufbau(uid, "ac15")
        zone = anchor_tz(trip, _AT)
        moderat, konvektiv = _quelle(RATE_MODERAT_MM_H), _quelle(
            RATE_MODERAT_MM_H, konvektiv=True,
        )
        assert _gemessene_dringlichkeit(trip, moderat, _AT) == "MODERATE", (
            "Testkonstruktion: der erste Lauf muss MODERATE liefern — sonst "
            "ist die spaetere Vergleichsbasis eine andere als gedacht."
        )
        at2 = _AT + timedelta(minutes=30)
        assert _gemessene_dringlichkeit(trip, konvektiv, at2) == "HIGH", (
            "Testkonstruktion: die konvektive Lage muss HIGH liefern, sonst "
            "gibt es gar keine Eskalation zu pruefen."
        )

        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf1 = strecke.lauf(
            at=_AT, zweig="radar", trip=trip, radar_service=_radar(moderat),
        )
        assert lauf1.triggered_count == 1, (
            f"AC-15 Vorbedingung: der MODERATE Lauf muss zustellen und dabei "
            f"die hoechste Stufe des Tages buchen (war {lauf1.triggered_count})."
        )
        assert _zonen_eintrag(uid, zone, _AT).get("max_urgency_sent") == "MODERATE", (
            f"AC-15: eine ZUGESTELLTE MODERATE-Meldung muss die hoechste Stufe "
            f"des Tages in der Zone {zone} fortschreiben — sonst weiss die "
            f"Zone spaeter nicht, dass heute nichts ueber MODERATE hinausging. "
            f"Eintrag: {_zonen_eintrag(uid, zone, _AT)!r}"
        )

        _budget_ausschoepfen(uid, _AT, zone)

        lauf2 = strecke.lauf(
            at=at2, zweig="radar", trip=trip, radar_service=_radar(konvektiv),
        )
        assert lauf2.triggered_count == 1, (
            f"AC-15: eine konvektive HIGH-Lage gegen eine Zone, die heute "
            f"hoechstens MODERATE verschickt hat, muss das erschoepfte "
            f"Tagesbudget durchbrechen. War triggered_count="
            f"{lauf2.triggered_count}, protokollierte Gruende: "
            f"{_gruende(uid, trip, at2)!r}"
        )
        assert lauf2.mail and lauf2.telegram, (
            f"AC-15: der Durchbruch muss die konfigurierten Kanaele erreichen: "
            f"mail={lauf2.mail!r} telegram={lauf2.telegram!r}"
        )
        assert _durchbruchszaehler(uid, zone, at2) == 1, (
            f"AC-15: nach dem Durchbruch muss die Zone GENAU EINEN verbrauchten "
            f"Durchbruch fuehren (Deckel), gefunden "
            f"{_durchbruchszaehler(uid, zone, at2)}. Eintrag: "
            f"{_zonen_eintrag(uid, zone, at2)!r}"
        )
    finally:
        _clean_user(uid)


# ─────────────────────────────── AC-16 ───────────────────────────────────────


@pytest.mark.timeout(60)
def test_ac16_ohne_eskalation_bleibt_das_erschoepfte_budget_ein_hartes_stop():
    """AC-16. GIVEN dieselbe Ausgangslage wie AC-15 (Budget erschoepft,
    hoechste zugestellte Stufe MODERATE), WHEN eine Lage geprueft wird, die
    MODERATE NICHT uebersteigt, THEN bleibt der Alarm aus, das Protokoll weist
    `daily_limit` aus und kein Durchbruch wird verbraucht.

    Die Stille selbst ist heute schon richtig — geprueft wird, dass sie es
    NACH der Aenderung bleibt (gefaehrlichste Fehlerrichtung: aus der
    Tages-Obergrenze wird eine Attrappe).

    POSITIVKONTROLLE im selben Test (PFLICHT): ein zweiter Nutzer mit
    identischem Aufbau, bei dem NUR die Lage konvektiv ist, bricht sehr wohl
    durch. Ohne sie bewiese `triggered_count == 0` nur, dass irgendetwas
    schweigt — nicht, dass die fehlende Eskalation der Grund ist. Diese
    Haelfte ist heute ROT."""
    uid, ctrl = _uid("ac16"), _uid("ac16-ctrl")
    try:
        trip = _aufbau(uid, "ac16")
        zone = anchor_tz(trip, _AT)
        moderat = _quelle(RATE_MODERAT_MM_H)
        at2 = _AT + timedelta(minutes=30)
        assert _gemessene_dringlichkeit(trip, moderat, at2) == "MODERATE", (
            "Testkonstruktion: die zweite Lage muss wieder MODERATE liefern."
        )
        assert not alert_urgency.exceeds("MODERATE", "MODERATE"), (
            "Testkonstruktion: MODERATE darf MODERATE nicht uebersteigen — "
            "sonst pruefte dieser Test eine Eskalation statt ihres Fehlens."
        )

        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf1 = strecke.lauf(
            at=_AT, zweig="radar", trip=trip, radar_service=_radar(moderat),
        )
        assert lauf1.triggered_count == 1, (
            f"AC-16 Vorbedingung: der erste Lauf muss zustellen "
            f"(war {lauf1.triggered_count})."
        )
        _budget_ausschoepfen(uid, _AT, zone)

        lauf2 = strecke.lauf(
            at=at2, zweig="radar", trip=trip, radar_service=_radar(moderat),
        )
        assert lauf2.triggered_count == 0, (
            f"AC-16: ohne echte Eskalation bleibt das erschoepfte Tagesbudget "
            f"ein hartes Stop (war {lauf2.triggered_count})."
        )
        assert alert_log.REASON_DAILY_LIMIT in _gruende(uid, trip, at2), (
            f"AC-16: der Protokollgrund muss "
            f"{alert_log.REASON_DAILY_LIMIT!r} sein. Gefunden: "
            f"{_gruende(uid, trip, at2)!r}"
        )
        assert _durchbruchszaehler(uid, zone, at2) == 0, (
            f"AC-16: eine unterdrueckte Meldung darf keinen Durchbruch "
            f"verbrauchen, gefunden {_durchbruchszaehler(uid, zone, at2)}."
        )

        # Positivkontrolle: identischer Aufbau, NUR die Lage eskaliert.
        ktrip = _aufbau(ctrl, "ac16-ctrl")
        kzone = anchor_tz(ktrip, _AT)
        konvektiv = _quelle(RATE_MODERAT_MM_H, konvektiv=True)
        assert _gemessene_dringlichkeit(ktrip, konvektiv, at2) == "HIGH", (
            "Testkonstruktion der Positivkontrolle: die Lage muss HIGH sein."
        )
        kstrecke = AlarmPruefstrecke(user_id=ctrl, settings=_settings_all_channels())
        klauf1 = kstrecke.lauf(
            at=_AT, zweig="radar", trip=ktrip, radar_service=_radar(moderat),
        )
        assert klauf1.triggered_count == 1, (
            "AC-16 Positivkontrolle: der erste Lauf muss zustellen."
        )
        _budget_ausschoepfen(ctrl, _AT, kzone)
        klauf2 = kstrecke.lauf(
            at=at2, zweig="radar", trip=ktrip, radar_service=_radar(konvektiv),
        )
        assert klauf2.triggered_count == 1, (
            f"AC-16 Positivkontrolle: bei GENAU DERSELBEN Ausgangslage muss "
            f"eine konvektive Lage durchbrechen — sonst sagt die Stille oben "
            f"nichts ueber die fehlende Eskalation aus (war "
            f"{klauf2.triggered_count}, Gruende: {_gruende(ctrl, ktrip, at2)!r})."
        )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


# ─────────────────────────────── AC-17 ───────────────────────────────────────


@pytest.mark.timeout(90)
def test_ac17_die_eskalationsausnahme_gilt_hoechstens_einmal_pro_tag_und_zone():
    """AC-17. GIVEN in einer Zone hat heute bereits ein Durchbruch
    stattgefunden, WHEN eine zweite, noch schwerere Eskalation geprueft wird,
    THEN bleibt der Alarm aus, das Protokoll weist `daily_limit` aus und der
    Durchbruchszaehler bleibt bei 1.

    LEITER LOW -> MODERATE -> HIGH, bewusst so und nicht MODERATE -> HIGH:
    die Skala saettigt bei HIGH (`exceeds("HIGH","HIGH")` ist False, Befund A
    aus #2065). Waere der erste Durchbruch schon HIGH, bliebe der zweite Lauf
    auch OHNE Deckel still — der Test bewachte dann die Saettigung statt der
    Obergrenze und waere gruen aus dem falschen Grund.

    POSITIVKONTROLLE im selben Test (PFLICHT): ein zweiter Nutzer durchlaeuft
    dieselbe Leiter, nur ist bei ihm die MODERATE-Meldung eine NORMALE
    Zustellung (Budget noch frei) — es wird also kein Durchbruch verbraucht.
    Zustand und Lage sind danach deckungsgleich mit dem Hauptfall (Budget
    erschoepft, hoechste Stufe MODERATE), einziger Unterschied ist der
    verbrauchte Durchbruch. Bricht der Kontroll-Lauf durch und der Hauptlauf
    nicht, hat GENAU der Deckel entschieden."""
    uid, ctrl = _uid("ac17"), _uid("ac17-ctrl")
    try:
        leicht = _quelle(RATE_LOW_MM_H)
        moderat = _quelle(RATE_MODERAT_MM_H)
        konvektiv = _quelle(RATE_MODERAT_MM_H, konvektiv=True)
        at2, at3 = _AT + timedelta(minutes=30), _AT + timedelta(minutes=60)

        trip = _aufbau(uid, "ac17")
        zone = anchor_tz(trip, _AT)
        assert _gemessene_dringlichkeit(trip, leicht, _AT) == "LOW", (
            "Testkonstruktion: die erste Stufe der Leiter muss LOW sein."
        )
        assert _gemessene_dringlichkeit(trip, moderat, at2) == "MODERATE", (
            "Testkonstruktion: die zweite Stufe der Leiter muss MODERATE sein."
        )
        assert _gemessene_dringlichkeit(trip, konvektiv, at3) == "HIGH", (
            "Testkonstruktion: die dritte Stufe der Leiter muss HIGH sein — "
            "nur dann ist der dritte Lauf eine ECHTE zweite Eskalation."
        )

        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        assert strecke.lauf(
            at=_AT, zweig="radar", trip=trip, radar_service=_radar(leicht),
        ).triggered_count == 1, "AC-17 Vorbedingung: der LOW-Lauf muss zustellen."
        _budget_ausschoepfen(uid, _AT, zone)

        lauf2 = strecke.lauf(
            at=at2, zweig="radar", trip=trip, radar_service=_radar(moderat),
        )
        assert lauf2.triggered_count == 1, (
            f"AC-17 Vorbedingung: MODERATE gegen eine Zone, die heute nur LOW "
            f"verschickt hat, muss durchbrechen und damit den EINEN Durchbruch "
            f"des Tages verbrauchen (war {lauf2.triggered_count}, Gruende: "
            f"{_gruende(uid, trip, at2)!r})."
        )
        assert _durchbruchszaehler(uid, zone, at2) == 1, (
            f"AC-17 Vorbedingung: der Durchbruch muss gebucht sein, gefunden "
            f"{_durchbruchszaehler(uid, zone, at2)}."
        )

        lauf3 = strecke.lauf(
            at=at3, zweig="radar", trip=trip, radar_service=_radar(konvektiv),
        )
        assert lauf3.triggered_count == 0, (
            f"AC-17: die Eskalationsausnahme gilt hoechstens EINMAL pro Tag und "
            f"Zone — auch eine noch schwerere Lage darf danach nicht mehr "
            f"durchbrechen (war {lauf3.triggered_count})."
        )
        assert alert_log.REASON_DAILY_LIMIT in _gruende(uid, trip, at3), (
            f"AC-17: der Protokollgrund muss {alert_log.REASON_DAILY_LIMIT!r} "
            f"sein. Gefunden: {_gruende(uid, trip, at3)!r}"
        )
        assert _durchbruchszaehler(uid, zone, at3) == 1, (
            f"AC-17: der Durchbruchszaehler darf durch den abgewiesenen Lauf "
            f"nicht weiterwachsen, gefunden "
            f"{_durchbruchszaehler(uid, zone, at3)}."
        )

        # Positivkontrolle: dieselbe Leiter, aber OHNE verbrauchten Durchbruch.
        ktrip = _aufbau(ctrl, "ac17-ctrl")
        kzone = anchor_tz(ktrip, _AT)
        kstrecke = AlarmPruefstrecke(user_id=ctrl, settings=_settings_all_channels())
        assert kstrecke.lauf(
            at=_AT, zweig="radar", trip=ktrip, radar_service=_radar(leicht),
        ).triggered_count == 1, "AC-17 Positivkontrolle: LOW-Lauf muss zustellen."
        assert kstrecke.lauf(
            at=at2, zweig="radar", trip=ktrip, radar_service=_radar(moderat),
        ).triggered_count == 1, (
            "AC-17 Positivkontrolle: der MODERATE-Lauf laeuft bei FREIEM Budget "
            "und ist deshalb eine normale Zustellung, kein Durchbruch."
        )
        assert _durchbruchszaehler(ctrl, kzone, at2) == 0, (
            f"AC-17 Positivkontrolle: eine normale Zustellung darf keinen "
            f"Durchbruch verbrauchen, gefunden "
            f"{_durchbruchszaehler(ctrl, kzone, at2)}."
        )
        _budget_ausschoepfen(ctrl, _AT, kzone)
        klauf3 = kstrecke.lauf(
            at=at3, zweig="radar", trip=ktrip, radar_service=_radar(konvektiv),
        )
        assert klauf3.triggered_count == 1, (
            f"AC-17 Positivkontrolle: bei deckungsgleicher Lage und Zustand, "
            f"nur OHNE verbrauchten Durchbruch, muss derselbe Lauf durchbrechen "
            f"— sonst sagt die Stille oben nichts ueber den Deckel aus (war "
            f"{klauf3.triggered_count}, Gruende: {_gruende(ctrl, ktrip, at3)!r})."
        )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


# ─────────────────────────────── AC-18 ───────────────────────────────────────


@pytest.mark.timeout(60)
def test_ac18_ohne_erreichbaren_kanal_wird_der_durchbruch_nicht_gebucht():
    """AC-18. GIVEN eine Durchbruchslage wie AC-15, aber ohne erreichbaren
    Zustellkanal, WHEN der Lauf abgeschlossen ist, THEN bleiben hoechste
    zugestellte Stufe UND Durchbruchszaehler unveraendert (F001-Symmetrie:
    geprueft wird immer, gebucht nur nach Zustellung).

    Der Trip fuehrt NUR E-Mail; der stumme Lauf benutzt Settings ohne
    SMTP-Zugang (`can_send_email()` False), der Kanal bleibt also
    konfiguriert (das effektive Kanal-Set ist nicht leer, der Lauf bricht
    nicht vorher ab), ist aber nicht erreichbar.

    🔴 Die `test_smtp_*`-Felder MUESSEN mitgeleert werden: `AlarmPruefstrecke`
    ruft `Settings.with_user_profile(uid)` (`config.py:355`), und weil `tdd-…`
    eine Test-Kennung ist, laeuft das ueber `Settings.for_testing()` — das
    befuellt `smtp_host/-user/-pass` aus `test_smtp_*` WIEDER. Die
    Konstruktionspruefung haengt deshalb am Objekt, mit dem der Lauf
    TATSAECHLICH faehrt (NACH `with_user_profile`).

    POSITIVKONTROLLE im selben Test (PFLICHT): derselbe Lauf danach mit
    erreichbarem Kanal bricht durch und bucht. Ohne sie bewiese die
    unveraenderte Buchung nur, dass ueberhaupt nichts passiert ist — nicht,
    dass der Zustand noch durchbrechbar war."""
    uid = _uid("ac18")
    try:
        trip = _aufbau(uid, "ac18", send_telegram=False)
        zone = anchor_tz(trip, _AT)
        moderat = _quelle(RATE_MODERAT_MM_H)
        konvektiv = _quelle(RATE_MODERAT_MM_H, konvektiv=True)
        at2, at3 = _AT + timedelta(minutes=30), _AT + timedelta(minutes=60)

        laut = _settings_all_channels()
        stumm = laut.model_copy(update={
            "smtp_host": "", "smtp_user": "", "smtp_pass": "",
            "test_smtp_user": "", "test_smtp_pass": "",
        })
        assert laut.with_user_profile(uid).can_send_email(), (
            "AC-18 Testkonstruktion: der LAUTE Lauf braucht einen erreichbaren "
            "E-Mail-Kanal — geprueft am Objekt, mit dem die Pruefstrecke faehrt."
        )
        assert not stumm.with_user_profile(uid).can_send_email(), (
            "AC-18 Testkonstruktion: der stumme Lauf braucht einen "
            "konfigurierten, aber NICHT erreichbaren E-Mail-Kanal — geprueft "
            "NACH `with_user_profile()`, weil erst dort `for_testing()` die "
            "Zugangsdaten wieder einsetzen wuerde."
        )

        strecke_laut = AlarmPruefstrecke(user_id=uid, settings=laut)
        strecke_stumm = AlarmPruefstrecke(user_id=uid, settings=stumm)

        assert strecke_laut.lauf(
            at=_AT, zweig="radar", trip=trip, radar_service=_radar(moderat),
        ).triggered_count == 1, "AC-18 Vorbedingung: der erste Lauf muss zustellen."
        _budget_ausschoepfen(uid, _AT, zone)
        vorher = dict(_zonen_eintrag(uid, zone, _AT))
        assert vorher.get("max_urgency_sent") == "MODERATE", (
            f"AC-18 Vorbedingung: die hoechste zugestellte Stufe des Tages muss "
            f"aus dem echten ersten Lauf MODERATE sein. Eintrag: {vorher!r}"
        )

        lauf2 = strecke_stumm.lauf(
            at=at2, zweig="radar", trip=trip, radar_service=_radar(konvektiv),
        )
        assert lauf2.triggered_count == 0, (
            f"AC-18 Vorbedingung: ohne erreichbaren Kanal darf nichts als "
            f"zugestellt gelten (war {lauf2.triggered_count})."
        )
        nachher = _zonen_eintrag(uid, zone, at2)
        assert nachher.get("max_urgency_sent") == "MODERATE", (
            f"AC-18: eine GESCHEITERTE Zustellung darf die hoechste Stufe des "
            f"Tages nicht auf HIGH heben — sonst waere die naechste, echte "
            f"Eskalation danach nicht mehr moeglich. Eintrag: {nachher!r}"
        )
        assert _durchbruchszaehler(uid, zone, at2) == 0, (
            f"AC-18: eine gescheiterte Zustellung darf den einen Durchbruch des "
            f"Tages nicht verbrauchen, gefunden "
            f"{_durchbruchszaehler(uid, zone, at2)}."
        )
        assert alert_daily_limit.load(uid, at2, zone) == TAGESLIMIT, (
            f"AC-18: auch der Tageszaehler bleibt unberuehrt, steht auf "
            f"{alert_daily_limit.load(uid, at2, zone)}."
        )

        # Positivkontrolle: derselbe Lauf mit erreichbarem Kanal.
        lauf3 = strecke_laut.lauf(
            at=at3, zweig="radar", trip=trip, radar_service=_radar(konvektiv),
        )
        assert lauf3.triggered_count == 1, (
            f"AC-18 Positivkontrolle: derselbe Zustand muss mit erreichbarem "
            f"Kanal sehr wohl durchbrechen — sonst bewiese die unveraenderte "
            f"Buchung oben nur, dass nichts passiert ist (war "
            f"{lauf3.triggered_count}, Gruende: {_gruende(uid, trip, at3)!r})."
        )
        assert _durchbruchszaehler(uid, zone, at3) == 1, (
            f"AC-18 Positivkontrolle: erst die erfolgreiche Zustellung bucht "
            f"den Durchbruch, gefunden {_durchbruchszaehler(uid, zone, at3)}."
        )
        assert _zonen_eintrag(uid, zone, at3).get("max_urgency_sent") == "HIGH", (
            f"AC-18 Positivkontrolle: erst die erfolgreiche Zustellung hebt die "
            f"hoechste Stufe des Tages auf HIGH. Eintrag: "
            f"{_zonen_eintrag(uid, zone, at3)!r}"
        )
    finally:
        _clean_user(uid)


# ─────────────────────────────── AC-19 ───────────────────────────────────────


@pytest.mark.timeout(60)
def test_ac19_altbestand_ohne_die_neuen_felder_bleibt_lesbar_und_unangetastet():
    """AC-19. GIVEN eine `alert_daily_count.json` im HEUTIGEN Schema (Zonen,
    aber ohne die zwei neuen Felder) mit einem Eintrag einer ZWEITEN Zone,
    WHEN ein Lauf dagegen prueft und schreibt — sowohl per normalem Increment
    als auch per Eskalations-Durchbruch —, THEN bleibt die Datei lesbar, der
    Eintrag der anderen Zone bleibt Feld fuer Feld unangetastet, und die zwei
    neuen Felder entstehen additiv NUR im betroffenen Zonen-Eintrag
    (Read-Modify-Write, kein Replace).

    Hier IST die Datei der Pruefgegenstand — deshalb als einziger Test dieser
    Datei ein direkter Blick in ihren Inhalt und eine literal vorbelegte
    Ausgangslage (Risiko 2 der Spec: ein Read-Modify-Write-Fehler korrumpiert
    den Tageszaehler mandantenweit)."""
    uid = _uid("ac19")
    fremde_zone = "Pacific/Auckland"
    try:
        trip = _aufbau(uid, "ac19")
        zone = anchor_tz(trip, _AT)
        tag = _AT.astimezone(zone).date().isoformat()
        fremd_vorher = {"date": tag, "count": 3, "letzter_grund": "unberuehrt"}
        pfad = get_data_dir(uid) / "alert_daily_count.json"
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(json.dumps({"zones": {
            str(zone): {"date": tag, "count": 1},
            fremde_zone: dict(fremd_vorher),
        }}))

        def _fremd() -> dict:
            return (json.loads(pfad.read_text()).get("zones") or {}).get(fremde_zone)

        moderat = _quelle(RATE_MODERAT_MM_H)
        konvektiv = _quelle(RATE_MODERAT_MM_H, konvektiv=True)
        at2 = _AT + timedelta(minutes=30)
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())

        # Weg 1: normales Increment einer zugestellten Meldung.
        assert strecke.lauf(
            at=_AT, zweig="radar", trip=trip, radar_service=_radar(moderat),
        ).triggered_count == 1, (
            "AC-19 Vorbedingung: der erste Lauf muss gegen die Altdatei "
            "zustellen — sonst wird gar nichts geschrieben."
        )
        assert alert_daily_limit.load(uid, _AT, zone) == 2, (
            f"AC-19 (normales Increment): der vorhandene Zaehlerstand 1 muss um "
            f"genau 1 wachsen, steht auf {alert_daily_limit.load(uid, _AT, zone)} "
            f"— ein Replace haette ihn auf 1 zurueckgesetzt."
        )
        eintrag = _zonen_eintrag(uid, zone, _AT)
        assert eintrag.get("max_urgency_sent") == "MODERATE", (
            f"AC-19 (normales Increment): das neue Feld muss additiv im "
            f"betroffenen Zonen-Eintrag entstehen. Eintrag: {eintrag!r}"
        )
        assert int(eintrag.get("escalation_breakthroughs", 0)) == 0, (
            f"AC-19: ohne Durchbruch bleibt der Durchbruchszaehler bei 0. "
            f"Eintrag: {eintrag!r}"
        )
        assert _fremd() == fremd_vorher, (
            f"AC-19: der Eintrag der Zone {fremde_zone} muss Feld fuer Feld "
            f"unangetastet bleiben (auch das unbekannte Feld). Erwartet "
            f"{fremd_vorher!r}, gefunden {_fremd()!r}"
        )

        # Weg 2: Eskalations-Durchbruch gegen dieselbe Datei.
        _budget_ausschoepfen(uid, _AT, zone)
        assert strecke.lauf(
            at=at2, zweig="radar", trip=trip, radar_service=_radar(konvektiv),
        ).triggered_count == 1, (
            "AC-19 Vorbedingung: der Durchbruch muss stattfinden, sonst prueft "
            "dieser Test den zweiten Schreibweg gar nicht."
        )
        eintrag = _zonen_eintrag(uid, zone, at2)
        assert int(eintrag.get("escalation_breakthroughs", 0)) == 1, (
            f"AC-19 (Durchbruch): das zweite neue Feld muss additiv entstehen. "
            f"Eintrag: {eintrag!r}"
        )
        assert eintrag.get("max_urgency_sent") == "HIGH", (
            f"AC-19 (Durchbruch): die hoechste zugestellte Stufe wandert auf "
            f"HIGH. Eintrag: {eintrag!r}"
        )
        assert alert_daily_limit.load(uid, at2, zone) == TAGESLIMIT + 1, (
            f"AC-19 (Durchbruch): auch der Durchbruch verbraucht einen Platz, "
            f"Zaehler steht auf {alert_daily_limit.load(uid, at2, zone)}."
        )
        assert _fremd() == fremd_vorher, (
            f"AC-19: auch der Durchbruchs-Schreibweg darf die Zone "
            f"{fremde_zone} nicht anfassen. Erwartet {fremd_vorher!r}, gefunden "
            f"{_fremd()!r}"
        )
    finally:
        _clean_user(uid)


# ─────────────────────────────── AC-20 ───────────────────────────────────────


@pytest.mark.timeout(60)
def test_ac20_der_durchbruch_wirkt_auch_im_ortsvergleich():
    """AC-20. GIVEN dieselbe Eskalationslage wie AC-15, aber im
    Ortsvergleich-Radarpfad, WHEN der Lauf geprueft wird, THEN bricht der
    Alarm ebenso durch — derselbe Mechanismus wirkt in BEIDEN Flaechen.

    Eigener Aufbau statt Prueflauf-Harness: `AlarmPruefstrecke` kennt keinen
    Compare-Zweig (bewusst, s. dortige Moduldoku). Die Zone ist hier
    `Europe/Vienna` (Ortskoordinaten des Baukastens), NICHT die Trip-Zone —
    eine falsche Zone fuellte einen anderen Zaehler (#1726).

    Sperrzeit des Presets bewusst auf 0 (s. Moduldoku); der Compare-Pfad
    faehrt auf der Wanduhr, zwei Laeufe liegen also Sekunden auseinander.

    POSITIVKONTROLLE im selben Test: ohne erschoepftes Budget stellt derselbe
    konvektive Lauf ebenfalls zu — die Zustellung oben beweist damit den
    Durchbruch und nicht bloss, dass der Pfad ueberhaupt funktioniert."""
    uid, ctrl = fresh_uid("2050s3b-ac20"), fresh_uid("2050s3b-ac20-ctrl")
    preset_id, ctrl_preset_id = "cp-2050s3b-ac20", "cp-2050s3b-ac20-ctrl"

    def _compare_aufbau(user: str, pid: str) -> None:
        clean_uid(user)
        write_user_tier(user, TIER_MIT_BUDGET)
        save_location(location("loc-eskalation", "Eskalationsdorf"), user_id=user)
        write_presets(user, [
            radar_preset(pid, ["loc-eskalation"], user_id=user, cooldown_minutes=0),
        ])

    def _compare_lauf(user: str, quelle, mails: list) -> int:
        reset_radar_cache()
        return compare_radar_service(
            user, settings_email_only(), quelle,
            lambda subject, body: mails.append((subject, body)),
        ).check_all_compare_presets()

    try:
        _compare_aufbau(uid, preset_id)
        moderat = _quelle(RATE_MODERAT_MM_H)
        konvektiv = _quelle(RATE_MODERAT_MM_H, konvektiv=True)
        mails: list = []

        assert _compare_lauf(uid, moderat, mails) == 1, (
            "AC-20 Vorbedingung: der MODERATE Vergleichs-Lauf muss zustellen "
            "und dabei die hoechste Stufe des Tages buchen."
        )
        jetzt = datetime.now(timezone.utc)
        assert _zonen_eintrag(uid, LOCATION_ZONE, jetzt).get(
            "max_urgency_sent"
        ) == "MODERATE", (
            f"AC-20: auch der Ortsvergleich muss die hoechste zugestellte Stufe "
            f"fortschreiben. Eintrag: "
            f"{_zonen_eintrag(uid, LOCATION_ZONE, jetzt)!r}"
        )

        _budget_ausschoepfen(uid, jetzt, LOCATION_ZONE)
        gesendet = _compare_lauf(uid, konvektiv, mails)
        assert gesendet == 1, (
            f"AC-20: die konvektive HIGH-Lage muss das erschoepfte Tagesbudget "
            f"auch im Ortsvergleich durchbrechen (war {gesendet})."
        )
        assert _durchbruchszaehler(uid, LOCATION_ZONE, jetzt) == 1, (
            f"AC-20: der Durchbruch wird auch im Ortsvergleich gebucht, "
            f"gefunden {_durchbruchszaehler(uid, LOCATION_ZONE, jetzt)}."
        )

        # Positivkontrolle: derselbe konvektive Lauf bei FREIEM Budget.
        _compare_aufbau(ctrl, ctrl_preset_id)
        kmails: list = []
        assert _compare_lauf(ctrl, moderat, kmails) == 1, (
            "AC-20 Positivkontrolle: der MODERATE Lauf muss zustellen."
        )
        assert _compare_lauf(ctrl, konvektiv, kmails) == 1, (
            "AC-20 Positivkontrolle: bei freiem Budget stellt derselbe "
            "konvektive Lauf zu — die Zustellung oben ist also der Durchbruch "
            "und nicht bloss ein funktionierender Pfad."
        )
    finally:
        clean_uid(uid)
        clean_uid(ctrl)


# ─────────────────────────────── AC-21 ───────────────────────────────────────


@pytest.mark.timeout(60)
def test_ac21_die_ruhezeit_bleibt_auch_fuer_die_eskalationsausnahme_unbrechbar():
    """AC-21. GIVEN eine aktive Ruhezeit UND eine extreme Eskalation, WHEN der
    Radar-Alarm geprueft wird, THEN bleibt der Alarm dennoch aus und das
    Protokoll weist `quiet_hours` aus.

    PO-Ablehnung #1955: die Ruhezeit ist unbrechbar. Die Reihenfolge
    Ruhezeit -> Sperrzeit -> Tages-Obergrenze bleibt; die neue Ausnahme haengt
    ausschliesslich an der letzten Stufe.

    Das Ruhefenster (12:15-13:00 Ortszeit, Europe/Paris) liegt so, dass der
    erste Lauf um 12:00 Ortszeit noch AUSSERHALB liegt und zustellen kann —
    sonst gaebe es weder eine hoechste zugestellte Stufe noch ein erschoepftes
    Budget, und der Test bewachte eine leere Lage.

    POSITIVKONTROLLE im selben Test (PFLICHT): ein zweiter Nutzer mit
    identischem Aufbau, dessen Ruhefenster woanders liegt, bricht durch.
    Diese Haelfte ist heute ROT."""
    uid, ctrl = _uid("ac21"), _uid("ac21-ctrl")
    try:
        moderat = _quelle(RATE_MODERAT_MM_H)
        konvektiv = _quelle(RATE_MODERAT_MM_H, konvektiv=True)
        at2 = _AT + timedelta(minutes=30)  # 12:30 Ortszeit — mitten im Fenster

        trip = _aufbau(uid, "ac21", quiet=("12:15", "13:00"))
        zone = anchor_tz(trip, _AT)
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        assert strecke.lauf(
            at=_AT, zweig="radar", trip=trip, radar_service=_radar(moderat),
        ).triggered_count == 1, (
            "AC-21 Vorbedingung: der Lauf um 12:00 Ortszeit liegt VOR dem "
            "Ruhefenster und muss zustellen."
        )
        _budget_ausschoepfen(uid, _AT, zone)

        lauf2 = strecke.lauf(
            at=at2, zweig="radar", trip=trip, radar_service=_radar(konvektiv),
        )
        assert lauf2.triggered_count == 0, (
            f"AC-21: die Ruhezeit ist unbrechbar — auch die neue "
            f"Eskalationsausnahme darf sie nicht aufreissen (war "
            f"{lauf2.triggered_count})."
        )
        gruende = _gruende(uid, trip, at2)
        assert alert_log.REASON_QUIET_HOURS in gruende, (
            f"AC-21: der Protokollgrund muss {alert_log.REASON_QUIET_HOURS!r} "
            f"sein (nicht {alert_log.REASON_DAILY_LIMIT!r}) — die Ruhezeit "
            f"entscheidet zuerst. Gefunden: {gruende!r}"
        )
        assert _durchbruchszaehler(uid, zone, at2) == 0, (
            f"AC-21: eine an der Ruhezeit unterdrueckte Meldung darf keinen "
            f"Durchbruch verbrauchen, gefunden "
            f"{_durchbruchszaehler(uid, zone, at2)}."
        )

        # Positivkontrolle: identische Lage, Ruhefenster liegt woanders.
        ktrip = _aufbau(ctrl, "ac21-ctrl", quiet=("20:00", "21:00"))
        kzone = anchor_tz(ktrip, _AT)
        kstrecke = AlarmPruefstrecke(user_id=ctrl, settings=_settings_all_channels())
        assert kstrecke.lauf(
            at=_AT, zweig="radar", trip=ktrip, radar_service=_radar(moderat),
        ).triggered_count == 1, (
            "AC-21 Positivkontrolle: der erste Lauf muss zustellen."
        )
        _budget_ausschoepfen(ctrl, _AT, kzone)
        klauf2 = kstrecke.lauf(
            at=at2, zweig="radar", trip=ktrip, radar_service=_radar(konvektiv),
        )
        assert klauf2.triggered_count == 1, (
            f"AC-21 Positivkontrolle: dieselbe Lage OHNE Ruhezeit muss "
            f"durchbrechen — sonst sagt die Stille oben nichts ueber die "
            f"Ruhezeit aus (war {klauf2.triggered_count}, Gruende: "
            f"{_gruende(ctrl, ktrip, at2)!r})."
        )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)
