"""TDD RED — Issue #2065: eine Verschaerfung ueberholt die Radar-Sperrzeit.

SPEC: docs/specs/modules/fix_2065_verschaerfung_ueberholt_sperre.md
(AC-1 bis AC-10 und AC-13; AC-11 liegt in `test_throttle_store.py`,
AC-12/AC-14 in `test_alert_gate.py`.)

Gemessener Ausgangsbefund (Analyse 2026-08-22): Lauf 1 mit 11 mm/h (~10,08 mm
im 60-Min-Vergleichsfenster) loest aus und bucht 120 Min Sperrzeit; 90 Minuten
spaeter schweigt eine auf 30 mm/h (~27,5 mm) verdreifachte Lage mit
Protokollgrund `cooldown`. Hinter der Sperrzeit steht eine ZWEITE Wand: die
Entdopplung vergleicht auf der dreistufigen Skala LOW/MODERATE/HIGH, die bei
4 mm/h saettigt — `exceeds("HIGH","HIGH")` ist False (AC-5).

Alle Zeitreihen laufen ueber `AlarmPruefstrecke` (#2050 S1) gegen die ECHTE
Ausloeseentscheidung `TripAlertService.check_radar_alerts()`. Kein
Mock()/patch()/MagicMock: echter `RadarNowcastService` an seiner DI-Naht
`frame_source=`, echte Zustandsdateien unter `get_data_dir(user_id)`,
Unterdrueckungsgrund ueber `alert_log.read_undelivered()`.

BEWUSST OHNE BRIEFING-ANKER: ohne `save_dated()`-Schnappschuss ist
`_briefing_announced` False (`trip_alert.py:1400`) und die Briefing-
Ueberholung faellt als Entscheidungsgrund komplett aus. Waere ein Anker
gesetzt, koennte die Stille in AC-3/AC-4 auch von IHR kommen — die geprueften
Bedingungen waeren dann nie die wirksamen.

Keine Wanduhr: alle Zeitpunkte haengen an `_AT` (gestellte Uhr).

MENGEN-HERLEITUNG (`window_precip_mm`, `radar_service.py:765-805`):
`_accumulate_precip_mm` gibt jedem Frame die Dauer bis zum naechsten Frame,
gedeckelt auf `_MAX_FRAME_COVERAGE` (15 Min) und nie ueber das Fensterende
(`now + _OVERTAKE_COMPARE_WINDOW_MIN`, 60 Min) hinaus.

* `_dauerregen(r)`  — Frames bei +5/+20/+35/+50 -> 15+15+15+10 = 55 Min
  Deckung -> `r * 55/60` mm. 11 mm/h -> 10,083 mm; 30 mm/h -> 27,5 mm.
* `_kurze_spitze(r)` — Frames bei +5 (r) und +15 (0,0) -> 10 Min Deckung
  -> `r * 10/60` mm.

Jede benutzte Menge wird zusaetzlich am ECHTEN Nowcast-Ergebnis GEMESSEN
(`_gemessene_menge`), nicht nur gerechnet.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta

from freezegun import freeze_time

from services import alert_log
from services.radar_cache import reset_shared_radar_cache_for_tests

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
from tests.tdd.test_952_onset_alert_fidelity import _clean_user
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (
    _AT, _radar_trip, _settings_all_channels, _write_premium_profile, _write_tier,
)
from tests.tdd.test_alarm_szenario_briefing_ueberholung_zeitreihe import (
    _dauerregen, _kurze_spitze, _radar,
)

# Die beiden Werte des gemessenen #2065-Falls.
BASIS_RATE_MM_H = 11.0          # -> ~10,08 mm Vergleichsbasis
VERSCHAERFT_RATE_MM_H = 30.0    # -> ~27,5 mm, Faktor 2,73 gegen die Basis
BASIS_MM = 11.0 * 55 / 60
VERSCHAERFT_MM = 30.0 * 55 / 60


def _uid(tag: str) -> str:
    return f"tdd-2065-{tag}-{uuid.uuid4().hex[:6]}"


def _rate_dauerregen(mm: float) -> float:
    """Rate, die als Dauerregen genau `mm` im Vergleichsfenster ergibt."""
    return mm * 60.0 / 55.0


def _rate_spitze(mm: float) -> float:
    """Rate, die als 10-Minuten-Spitze genau `mm` im Vergleichsfenster ergibt."""
    return mm * 60.0 / 10.0


def _aufbau(uid: str, tag: str, *, tier: str = "premium", **flags):
    """Nutzer + Trip mit allen vier Kanaelen (sofern nicht anders verlangt).
    Kein Briefing-Anker (s. Moduldoku)."""
    _clean_user(uid)
    if tier == "premium":
        _write_premium_profile(uid, _AT)
    else:
        _write_tier(uid, tier)
    kanaele = {
        "send_email": True, "send_telegram": True,
        "send_sms": True, "send_premium_sms": True,
    }
    kanaele.update(flags)
    with freeze_time(_AT):
        trip = _radar_trip(uid, f"trip-2065-{tag}", **kanaele)
    return trip


def _gemessene_menge(trip, quelle, at: datetime) -> float:
    """`window_precip_mm` aus einem ECHTEN Nowcast-Abruf — die Zahl, mit der
    der Prueflauf spaeter rechnet, nicht eine im Test nachgerechnete.

    Der Frame-Cache ist ein PROZESS-Singleton mit Koordinaten-Schluessel
    (TTL 300 s): ohne Reset liefert der naechste Abruf die Frames dieses
    zurueck (#2050 S1, Falle 2 der Pruefstrecke). Die Koordinaten duerfen von
    denen des Prueflings abweichen — die Frame-Quelle ignoriert sie."""
    lat, lon = trip.stages[0].waypoints[0].lat, trip.stages[0].waypoints[0].lon
    with freeze_time(at):
        reset_shared_radar_cache_for_tests()
        ergebnis = _radar(quelle).get_nowcast(lat, lon)
        reset_shared_radar_cache_for_tests()
    return ergebnis.window_precip_mm


def _gruende(uid: str, trip, seit: datetime) -> set:
    """Alle Nicht-Zustellungs-Gruende, die der PRUEFLING selbst protokolliert
    hat (`alert_log.read_undelivered()`) — kein Dateiinhalt-Check, kein
    zweiter Lesepfad im Testkoerper."""
    vorfaelle = alert_log.read_undelivered(
        uid, entity_id=trip.id, entity_type="trip", since=seit,
    )
    return {g for v in vorfaelle for g in v.reasons}


def _zahlen(text: str) -> list:
    return [float(z) for z in re.findall(r"\d+[.,]\d+", text.replace(",", "."))]


def _entscheidungszeile(caplog, basis: float, menge: float, tol: float = 0.06):
    """Die Protokollzeile der Ueberholungsentscheidung: EINE Zeile aus
    `trip_alert`, die BEIDE Groessen traegt — gelesene Vergleichsbasis UND
    aktuell gemessene Menge (AC-13).

    Geprueft wird auf ZAHLEN mit Nachkommastelle, nicht auf Wortlaut: die
    Formulierung ist Sache der Implementierung, die beiden Werte sind es
    nicht. `tol=0.06` laesst Rundung auf eine Nachkommastelle zu (10,083 ->
    "10.1"), nicht aber auf ganze Zahlen — eine ganzzahlige Angabe verloere
    genau die Nachvollziehbarkeit, um die es hier geht."""
    for rec in caplog.records:
        if rec.name != "trip_alert":
            continue
        text = rec.getMessage()
        gefunden = _zahlen(text)
        if any(abs(z - basis) <= tol for z in gefunden) and any(
            abs(z - menge) <= tol for z in gefunden
        ):
            return text
    return None


# ───────────────────────────── AC-1 / AC-5 ───────────────────────────────────


def test_ac1_verschaerfung_ueberholt_die_laufende_sperrzeit_auf_allen_kanaelen():
    """AC-1. GIVEN eine laufende Sperrzeit aus einem Alarm ueber ~10 mm
    (11 mm/h), WHEN 90 Minuten spaeter im selben Sperrfenster eine Lage mit
    ~27,5 mm (30 mm/h) geprueft wird, THEN geht ein Alarm ueber ALLE vier
    konfigurierten Kanaele raus.

    RED heute: `check_nowcast_gate` prueft die Sperrzeit unbedingt vor jeder
    Verschaerfungsbewertung und kennt keine Ausnahme -> `triggered_count == 0`,
    Protokollgrund `cooldown`."""
    uid = _uid("ac1")
    try:
        trip = _aufbau(uid, "ac1")
        assert abs(_gemessene_menge(trip, _dauerregen(BASIS_RATE_MM_H), _AT)
                   - BASIS_MM) < 0.01
        assert abs(_gemessene_menge(trip, _dauerregen(VERSCHAERFT_RATE_MM_H), _AT)
                   - VERSCHAERFT_MM) < 0.01

        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf1 = strecke.lauf(
            at=_AT, zweig="radar", trip=trip,
            radar_service=_radar(_dauerregen(BASIS_RATE_MM_H)),
        )
        assert lauf1.triggered_count == 1, (
            f"AC-1 Vorbedingung: Lauf 1 (~{BASIS_MM:.2f} mm) muss ausloesen und "
            f"dabei Sperrzeit UND Vergleichsbasis buchen "
            f"(war {lauf1.triggered_count})."
        )

        at3 = _AT + timedelta(minutes=90)
        lauf3 = strecke.lauf(
            at=at3, zweig="radar", trip=trip,
            radar_service=_radar(_dauerregen(VERSCHAERFT_RATE_MM_H)),
        )
        assert lauf3.triggered_count == 1, (
            f"AC-1: ~{VERSCHAERFT_MM:.2f} mm gegen eine Vergleichsbasis von "
            f"~{BASIS_MM:.2f} mm (Faktor {VERSCHAERFT_MM / BASIS_MM:.2f}) muessen "
            f"die laufende Sperrzeit ueberholen. War "
            f"triggered_count={lauf3.triggered_count}, protokollierte Gruende: "
            f"{_gruende(uid, trip, at3)!r}"
        )
        assert lauf3.mail and lauf3.telegram and lauf3.sms and lauf3.premium_sms, (
            f"AC-1: alle vier Kanaele muessen Inhalt tragen: mail={lauf3.mail!r} "
            f"telegram={lauf3.telegram!r} sms={lauf3.sms!r} "
            f"premium_sms={lauf3.premium_sms!r}"
        )
    finally:
        _clean_user(uid)


def test_ac5_der_durchbruch_wirkt_auch_an_der_entdopplung():
    """AC-5. GIVEN dieselbe Verschaerfung wie in AC-1, WHEN der Alarm geprueft
    wird, THEN wirkt der Durchbruch AUCH an der Entdopplung — der Alarm kommt
    an und wurde NICHT mit `event_duplicate` unterdrueckt.

    Die Vorbedingung wird POSITIV nachgewiesen: nach Lauf 1 traegt das
    Ereignis-Register einen Eintrag mit `severity == "HIGH"`. Weil die Skala
    bei 4 mm/h saettigt (`HEAVY_RAIN_THRESHOLD_MM_H`), ist auch die
    verdreifachte Lage wieder `HIGH` — `alert_urgency.exceeds("HIGH","HIGH")`
    ist False, die bestehende Eskalationspruefung kann die Verschaerfung also
    strukturell nicht sehen. Ohne diesen Nachweis koennte ein gruener Test
    nicht zwischen 'die Entdopplung wurde ueberholt' und 'die Entdopplung war
    gar nicht geladen' unterscheiden (Befund A der Analyse).

    RED heute: der Lauf schweigt schon an der Sperrzeit."""
    uid = _uid("ac5")
    try:
        trip = _aufbau(uid, "ac5")
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf1 = strecke.lauf(
            at=_AT, zweig="radar", trip=trip,
            radar_service=_radar(_dauerregen(BASIS_RATE_MM_H)),
        )
        assert lauf1.triggered_count == 1, "AC-5 Vorbedingung: Lauf 1 muss ausloesen"

        from services.alert_state import AlertStateService
        register = AlertStateService(uid).load(trip.id)
        stufen = [
            eintrag.get("severity") for schluessel, eintrag in register.items()
            if schluessel.startswith("event_identity:") and isinstance(eintrag, dict)
        ]
        assert stufen == ["HIGH"], (
            f"AC-5 Vorbedingung: Lauf 1 muss GENAU EINEN Ereignis-Eintrag mit "
            f"Stufe HIGH registriert haben — sonst kann die Entdopplung den "
            f"zweiten Lauf gar nicht blockieren und der Test bewacht nichts. "
            f"Registriert: {stufen!r}"
        )

        at3 = _AT + timedelta(minutes=90)
        lauf3 = strecke.lauf(
            at=at3, zweig="radar", trip=trip,
            radar_service=_radar(_dauerregen(VERSCHAERFT_RATE_MM_H)),
        )
        gruende = _gruende(uid, trip, at3)
        assert alert_log.REASON_EVENT_DUPLICATE not in gruende, (
            f"AC-5: die Verschaerfung darf nicht an der ENTDOPPLUNG haengen "
            f"bleiben (Stufenvergleich HIGH gegen HIGH). Gruende: {gruende!r}"
        )
        assert lauf3.triggered_count == 1, (
            f"AC-5: der Alarm muss tatsaechlich ankommen, nicht nur einen "
            f"anderen Unterdrueckungsgrund bekommen. War "
            f"triggered_count={lauf3.triggered_count}, Gruende: {gruende!r}"
        )
    finally:
        _clean_user(uid)


# ─────────────────────────────── AC-2 ────────────────────────────────────────


def test_ac2_unveraenderte_lage_bleibt_mit_grund_sperrzeit_unterdrueckt():
    """AC-2 (Regressionswaechter, HEUTE SCHON GRUEN). GIVEN eine laufende
    Sperrzeit, WHEN die Lage gegenueber der letzten Meldung unveraendert
    bleibt, THEN bleibt die Unterdrueckung bestehen und das Protokoll weist
    `cooldown` aus.

    Bewacht die gefaehrlichste Fehlerrichtung dieser Aenderung: aus der
    Sperrzeit darf keine Attrappe werden."""
    uid = _uid("ac2")
    try:
        trip = _aufbau(uid, "ac2")
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf1 = strecke.lauf(
            at=_AT, zweig="radar", trip=trip,
            radar_service=_radar(_dauerregen(BASIS_RATE_MM_H)),
        )
        assert lauf1.triggered_count == 1, "AC-2 Vorbedingung: Lauf 1 muss ausloesen"

        at2 = _AT + timedelta(minutes=30)
        lauf2 = strecke.lauf(
            at=at2, zweig="radar", trip=trip,
            radar_service=_radar(_dauerregen(BASIS_RATE_MM_H)),
        )
        assert lauf2.triggered_count == 0, (
            f"AC-2: unveraenderte Lage darf die Sperre NICHT durchbrechen "
            f"(war {lauf2.triggered_count})."
        )
        gruende = _gruende(uid, trip, at2)
        assert alert_log.REASON_COOLDOWN in gruende, (
            f"AC-2: der Protokollgrund muss die SPERRZEIT "
            f"({alert_log.REASON_COOLDOWN!r}) bleiben. Gefunden: {gruende!r}"
        )
    finally:
        _clean_user(uid)


# ──────────────────────────── AC-3 / AC-4 ────────────────────────────────────


def test_ac3_faktor_erreicht_aber_unter_der_absoluten_untergrenze(caplog):
    """AC-3. GIVEN eine Verschaerfung, die den Faktor 2,0 erreicht, deren
    Gesamtmenge aber unter der absoluten Untergrenze von 2,0 mm bleibt, WHEN
    der Vergleich laeuft, THEN bricht die Sperre NICHT durch.

    Konstruktion so gewaehlt, dass GENAU EINE Bedingung entscheidet: Basis
    0,8 mm (4,8 mm/h als 10-Min-Spitze — dieselbe Intensitaetsstufe wie der
    Ausloesefall, aber winzige Menge), neue Menge 1,9 mm. Faktor:
    1,9 / 0,8 = 2,375 — LOCKER erfuellt. Absolute Untergrenze: 1,9 < 2,0 —
    allein sie verhindert den Durchbruch. Entfiele die Untergrenze, muss
    dieser Test rot werden.

    RED heute: der Lauf schweigt zwar auch, fuehrt die Ueberholungspruefung
    aber gar nicht erst aus — deshalb wird zusaetzlich die
    Entscheidungs-Protokollzeile (AC-13) verlangt, die heute fehlt."""
    uid = _uid("ac3")
    basis_mm, neue_mm = 0.8, 1.9
    try:
        trip = _aufbau(uid, "ac3")
        gemessen_basis = _gemessene_menge(
            trip, _kurze_spitze(_rate_spitze(basis_mm)), _AT,
        )
        gemessen_neu = _gemessene_menge(
            trip, _kurze_spitze(_rate_spitze(neue_mm)), _AT,
        )
        assert abs(gemessen_basis - basis_mm) < 0.01, (
            f"AC-3 Testkonstruktion: Basis erwartet {basis_mm} mm, gemessen "
            f"{gemessen_basis} mm."
        )
        assert abs(gemessen_neu - neue_mm) < 0.01, (
            f"AC-3 Testkonstruktion: neue Menge erwartet {neue_mm} mm, gemessen "
            f"{gemessen_neu} mm."
        )
        assert gemessen_neu >= gemessen_basis * 2.0, (
            f"AC-3 Testkonstruktion: die FAKTOR-Bedingung muss erfuellt sein, "
            f"sonst entscheidet wieder sie statt der absoluten Untergrenze "
            f"({gemessen_neu} < {gemessen_basis * 2.0})."
        )
        assert gemessen_neu < 2.0, (
            f"AC-3 Testkonstruktion: die Menge muss UNTER der absoluten "
            f"Untergrenze liegen ({gemessen_neu})."
        )

        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf1 = strecke.lauf(
            at=_AT, zweig="radar", trip=trip,
            radar_service=_radar(_kurze_spitze(_rate_spitze(basis_mm))),
        )
        assert lauf1.triggered_count == 1, (
            f"AC-3 Vorbedingung: Lauf 1 muss ausloesen und {basis_mm} mm als "
            f"Vergleichsbasis buchen (war {lauf1.triggered_count})."
        )

        at2 = _AT + timedelta(minutes=30)
        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger="trip_alert"):
            lauf2 = strecke.lauf(
                at=at2, zweig="radar", trip=trip,
                radar_service=_radar(_kurze_spitze(_rate_spitze(neue_mm))),
            )
        assert lauf2.triggered_count == 0, (
            f"AC-3: {neue_mm} mm erfuellen zwar den Faktor gegen {basis_mm} mm, "
            f"bleiben aber unter der absoluten Untergrenze von 2,0 mm — kein "
            f"Durchbruch erlaubt. War triggered_count={lauf2.triggered_count}."
        )
        assert alert_log.REASON_COOLDOWN in _gruende(uid, trip, at2), (
            f"AC-3: die Stille muss die SPERRZEIT als Grund behalten. Gefunden: "
            f"{_gruende(uid, trip, at2)!r}"
        )
        assert _entscheidungszeile(caplog, basis_mm, neue_mm) is not None, (
            f"AC-3: die Ueberholungspruefung muss nachweislich GELAUFEN sein — "
            f"ohne die Entscheidungszeile mit Basis {basis_mm} und Menge "
            f"{neue_mm} (AC-13) bewiese die Stille nur, dass die Kette wie "
            f"bisher vor dem Vergleich kurzschliesst."
        )
    finally:
        _clean_user(uid)


def test_ac4_menge_ueber_der_untergrenze_aber_ohne_faktor(caplog):
    """AC-4. GIVEN eine Menge deutlich ueber der absoluten Untergrenze, aber
    ohne den geforderten Faktor 2,0 gegenueber der Vergleichsbasis, WHEN der
    Vergleich laeuft, THEN bricht die Sperre NICHT durch.

    Spiegelbild zu AC-3: hier entscheidet ALLEIN der Faktor. Basis ~10,08 mm
    (11 mm/h), neue Menge 15,0 mm — 15,0 liegt siebeneinhalbfach ueber der
    absoluten Untergrenze (2,0 mm), aber unter dem Doppelten der Basis
    (20,17 mm). Entfiele der Faktor, muss dieser Test rot werden."""
    uid = _uid("ac4")
    neue_mm = 15.0
    try:
        trip = _aufbau(uid, "ac4")
        gemessen_neu = _gemessene_menge(
            trip, _dauerregen(_rate_dauerregen(neue_mm)), _AT,
        )
        assert abs(gemessen_neu - neue_mm) < 0.01, (
            f"AC-4 Testkonstruktion: erwartet {neue_mm} mm, gemessen {gemessen_neu}."
        )
        assert gemessen_neu >= 2.0, (
            "AC-4 Testkonstruktion: die absolute Untergrenze muss LOCKER "
            "erfuellt sein, sonst entscheidet wieder sie statt des Faktors."
        )
        assert gemessen_neu < BASIS_MM * 2.0, (
            f"AC-4 Testkonstruktion: die FAKTOR-Bedingung muss verfehlt sein "
            f"({gemessen_neu} >= {BASIS_MM * 2.0})."
        )

        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf1 = strecke.lauf(
            at=_AT, zweig="radar", trip=trip,
            radar_service=_radar(_dauerregen(BASIS_RATE_MM_H)),
        )
        assert lauf1.triggered_count == 1, "AC-4 Vorbedingung: Lauf 1 muss ausloesen"

        at2 = _AT + timedelta(minutes=30)
        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger="trip_alert"):
            lauf2 = strecke.lauf(
                at=at2, zweig="radar", trip=trip,
                radar_service=_radar(_dauerregen(_rate_dauerregen(neue_mm))),
            )
        assert lauf2.triggered_count == 0, (
            f"AC-4: {neue_mm} mm gegen eine Basis von ~{BASIS_MM:.2f} mm "
            f"erreichen den Faktor 2,0 NICHT — kein Durchbruch erlaubt. War "
            f"triggered_count={lauf2.triggered_count}."
        )
        assert alert_log.REASON_COOLDOWN in _gruende(uid, trip, at2), (
            f"AC-4: die Stille muss die SPERRZEIT als Grund behalten. Gefunden: "
            f"{_gruende(uid, trip, at2)!r}"
        )
        assert _entscheidungszeile(caplog, BASIS_MM, neue_mm) is not None, (
            f"AC-4: die Ueberholungspruefung muss nachweislich gelaufen sein "
            f"(Entscheidungszeile mit Basis ~{BASIS_MM:.2f} und Menge "
            f"{neue_mm}, AC-13)."
        )
    finally:
        _clean_user(uid)


# ──────────────────────────── AC-6 / AC-7 ────────────────────────────────────


def test_ac6_ruhezeit_bleibt_auch_fuer_extreme_verschaerfung_unbrechbar():
    """AC-6 (Regressionswaechter, HEUTE SCHON GRUEN). GIVEN die Ruhezeit ist
    aktiv, WHEN selbst eine extreme Verschaerfung geprueft wird, THEN bleibt
    der Alarm aus und das Protokoll weist `quiet_hours` aus.

    PO-Ablehnung #1955: die Ruhezeit bleibt unbrechbar. Das Ruhefenster
    (13:00–14:00 Ortszeit, Europe/Paris) liegt so, dass Lauf 1 um 12:00
    Ortszeit noch AUSSERHALB liegt und ausloesen kann — sonst gaebe es weder
    Sperrzeit noch Vergleichsbasis und der Test bewachte eine leere Lage."""
    uid = _uid("ac6")
    try:
        trip = _aufbau(uid, "ac6")
        trip.alert_quiet_from = "13:00"
        trip.alert_quiet_to = "14:00"
        with freeze_time(_AT):
            from app.loader import save_trip
            save_trip(trip, user_id=uid)

        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf1 = strecke.lauf(
            at=_AT, zweig="radar", trip=trip,
            radar_service=_radar(_dauerregen(BASIS_RATE_MM_H)),
        )
        assert lauf1.triggered_count == 1, (
            f"AC-6 Vorbedingung: Lauf 1 um 12:00 Ortszeit liegt VOR dem "
            f"Ruhefenster und muss ausloesen (war {lauf1.triggered_count})."
        )

        at3 = _AT + timedelta(minutes=90)  # 13:30 Ortszeit — mitten in der Ruhezeit
        lauf3 = strecke.lauf(
            at=at3, zweig="radar", trip=trip,
            radar_service=_radar(_dauerregen(VERSCHAERFT_RATE_MM_H)),
        )
        assert lauf3.triggered_count == 0, (
            f"AC-6: die Ruhezeit ist unbrechbar — auch eine Verdreifachung "
            f"darf sie nicht durchbrechen (war {lauf3.triggered_count})."
        )
        gruende = _gruende(uid, trip, at3)
        assert alert_log.REASON_QUIET_HOURS in gruende, (
            f"AC-6: der Protokollgrund muss {alert_log.REASON_QUIET_HOURS!r} "
            f"sein. Gefunden: {gruende!r}"
        )
    finally:
        _clean_user(uid)


def test_ac7_erschoepftes_tagesbudget_stoppt_den_durchbruch():
    """AC-7. GIVEN ein Nutzer mit endlichem Tagesbudget (Tier `standard`,
    Limit 4), dessen Budget erschoepft ist, WHEN eine Verschaerfung vorliegt,
    die Faktor UND Untergrenze erfuellt, THEN bleibt der Alarm aus und das
    Protokoll weist `daily_limit` aus.

    Begruendung: die Kette schliesst heute bei Sperrzeit kurz, das Tageslimit
    wurde fuer den Ueberholungsfall also NIE geprueft. Der Durchbruch darf es
    nicht stillschweigend mit-ueberspringen.

    Kein Premium-Profil (dort gilt gar kein Limit) und deshalb ohne
    Premium-SMS-Kanal — geprueft wird die Stille, nicht die Kanalparitaet.

    RED heute: der Lauf schweigt mit Grund `cooldown` statt `daily_limit`."""
    uid = _uid("ac7")
    try:
        trip = _aufbau(
            uid, "ac7", tier="standard",
            send_sms=False, send_premium_sms=False,
        )
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf1 = strecke.lauf(
            at=_AT, zweig="radar", trip=trip,
            radar_service=_radar(_dauerregen(BASIS_RATE_MM_H)),
        )
        assert lauf1.triggered_count == 1, (
            f"AC-7 Vorbedingung: Lauf 1 muss ausloesen (war {lauf1.triggered_count})."
        )

        # Tageszaehler ueber den PRODUKTIVEN Schreibweg auf das Limit heben
        # (Lauf 1 hat bereits einmal gezaehlt): dieselbe Zone, die auch das
        # Gate benutzt — eine andere fuellte einen anderen Zaehler (#1726).
        from services import alert_daily_limit
        from services.trip_day import anchor_tz
        from services.user_tier import daily_alert_limit

        at3 = _AT + timedelta(minutes=90)
        zone = anchor_tz(trip, at3)
        limit = daily_alert_limit(uid)
        assert limit == 4, f"AC-7 Vorbedingung: Tier `standard` muss Limit 4 haben ({limit})"
        while alert_daily_limit.load(uid, at3, zone) < limit:
            alert_daily_limit.increment(uid, at3, zone)
        assert not alert_daily_limit.is_allowed(uid, at3, zone, reason="nowcast"), (
            "AC-7 Vorbedingung: das Tagesbudget muss erschoepft sein."
        )

        lauf3 = strecke.lauf(
            at=at3, zweig="radar", trip=trip,
            radar_service=_radar(_dauerregen(VERSCHAERFT_RATE_MM_H)),
        )
        assert lauf3.triggered_count == 0, (
            f"AC-7: das erschoepfte Tagesbudget bleibt hartes Stop, auch fuer "
            f"eine Verschaerfung (war {lauf3.triggered_count})."
        )
        gruende = _gruende(uid, trip, at3)
        assert alert_log.REASON_DAILY_LIMIT in gruende, (
            f"AC-7: der Protokollgrund muss {alert_log.REASON_DAILY_LIMIT!r} "
            f"sein — der Durchbruch der Sperrzeit muss das Tageslimit ERNEUT "
            f"pruefen, statt es mit zu ueberspringen. Gefunden: {gruende!r}"
        )
    finally:
        _clean_user(uid)


# ──────────────────────────── AC-8 / AC-9 / AC-10 ────────────────────────────


def test_ac8_ohne_vergleichsbasis_bleibt_die_sperre_bestehen():
    """AC-8 (Regressionswaechter, HEUTE SCHON GRUEN — wird nach der
    Implementierung mutations-empfindlich). GIVEN die Sperre wurde vom ZWEITEN
    Schreiber ohne Mengenangabe gebucht (Kurzfristhinweis im Briefing,
    `trip_report_scheduler.py:1574`), sodass keine Vergleichsbasis existiert,
    WHEN eine beliebig starke Lage geprueft wird, THEN bricht die Sperre NICHT
    durch und das Protokoll weist `cooldown` aus.

    Konservative Fehlerrichtung: ein Durchbruch ohne Vergleichsbasis waere ein
    Durchbruch ohne Nachweis. Liefert der Vergleichs-Helfer bei fehlender
    Basis faelschlich `True`, wird dieser Test rot.

    Positivkontrolle im selben Test: DIESELBE Lage auf einem Trip OHNE
    gebuchte Sperre loest aus — ohne sie bewiese `triggered_count == 0` nur,
    dass die Lage ueberhaupt nicht alarmwuerdig ist."""
    uid, ctrl = _uid("ac8"), _uid("ac8-ctrl")
    try:
        trip = _aufbau(uid, "ac8")
        # Exakt der Aufruf des zweiten Schreibers: Zeitstempel, keine Menge.
        from services.throttle_store import ThrottleStore
        ThrottleStore(uid).record("radar", trip.id, _AT)

        at2 = _AT + timedelta(minutes=30)
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf = strecke.lauf(
            at=at2, zweig="radar", trip=trip,
            radar_service=_radar(_dauerregen(VERSCHAERFT_RATE_MM_H)),
        )
        assert lauf.triggered_count == 0, (
            f"AC-8: ohne gespeicherte Vergleichsbasis darf auch eine sehr starke "
            f"Lage (~{VERSCHAERFT_MM:.2f} mm) die Sperre NICHT durchbrechen "
            f"(war {lauf.triggered_count})."
        )
        gruende = _gruende(uid, trip, at2)
        assert alert_log.REASON_COOLDOWN in gruende, (
            f"AC-8: der Protokollgrund muss {alert_log.REASON_COOLDOWN!r} "
            f"bleiben. Gefunden: {gruende!r}"
        )

        kontroll_trip = _aufbau(ctrl, "ac8-ctrl")
        kontroll_strecke = AlarmPruefstrecke(
            user_id=ctrl, settings=_settings_all_channels(),
        )
        kontrolle = kontroll_strecke.lauf(
            at=at2, zweig="radar", trip=kontroll_trip,
            radar_service=_radar(_dauerregen(VERSCHAERFT_RATE_MM_H)),
        )
        assert kontrolle.triggered_count == 1, (
            f"AC-8 Positivkontrolle: dieselbe Lage OHNE gebuchte Sperre muss "
            f"ausloesen — sonst sagt die Stille oben nichts ueber die Sperre "
            f"aus (war {kontrolle.triggered_count})."
        )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


def test_ac9_fortgeschriebene_vergleichsbasis_bremst_den_zweiten_durchbruch():
    """AC-9. GIVEN ein Alarm ist im selben Sperrfenster bereits einmal
    durchgebrochen und hat die Vergleichsbasis auf die hoehere Menge
    fortgeschrieben, WHEN dieselbe (nicht weiter verschaerfte) Menge erneut
    geprueft wird, THEN bricht der Alarm NICHT ein zweites Mal durch.

    Selbstbremsung gegen die Wiederholungs-Kettenreaktion: nach dem
    27,5-mm-Durchbruch braucht die naechste Verschaerfung den vollen Faktor
    gegen 27,5 mm, nicht mehr gegen die alten 10,08 mm.

    RED heute an Lauf 2: der Durchbruch findet gar nicht erst statt."""
    uid = _uid("ac9")
    try:
        trip = _aufbau(uid, "ac9")
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf1 = strecke.lauf(
            at=_AT, zweig="radar", trip=trip,
            radar_service=_radar(_dauerregen(BASIS_RATE_MM_H)),
        )
        assert lauf1.triggered_count == 1, "AC-9 Vorbedingung: Lauf 1 muss ausloesen"

        at2 = _AT + timedelta(minutes=45)
        lauf2 = strecke.lauf(
            at=at2, zweig="radar", trip=trip,
            radar_service=_radar(_dauerregen(VERSCHAERFT_RATE_MM_H)),
        )
        assert lauf2.triggered_count == 1, (
            f"AC-9 Vorbedingung: Lauf 2 (~{VERSCHAERFT_MM:.2f} mm) muss die "
            f"Sperre durchbrechen und die Vergleichsbasis fortschreiben "
            f"(war {lauf2.triggered_count}, Gruende: {_gruende(uid, trip, at2)!r})."
        )

        at3 = at2 + timedelta(minutes=45)  # immer noch im Sperrfenster von Lauf 2
        lauf3 = strecke.lauf(
            at=at3, zweig="radar", trip=trip,
            radar_service=_radar(_dauerregen(VERSCHAERFT_RATE_MM_H)),
        )
        assert lauf3.triggered_count == 0, (
            f"AC-9: unveraenderte ~{VERSCHAERFT_MM:.2f} mm gegen eine bereits "
            f"auf diesen Wert fortgeschriebene Vergleichsbasis duerfen NICHT "
            f"erneut durchbrechen (war {lauf3.triggered_count})."
        )
        assert alert_log.REASON_COOLDOWN in _gruende(uid, trip, at3), (
            f"AC-9: der Protokollgrund muss {alert_log.REASON_COOLDOWN!r} sein. "
            f"Gefunden: {_gruende(uid, trip, at3)!r}"
        )
    finally:
        _clean_user(uid)


def test_ac10_gescheiterte_zustellung_schreibt_die_vergleichsbasis_nicht_fort():
    """AC-10. GIVEN ein Durchbruchsfall, bei dem die Zustellung scheitert
    (kein erreichbarer Kanal), WHEN der Lauf abgeschlossen ist, THEN wird die
    Vergleichsbasis NICHT fortgeschrieben (F001-Symmetrie).

    Nachgewiesen VERHALTENSSEITIG statt ueber einen Blick in die
    Zustandsdatei: Lauf 3 faehrt dieselben ~27,5 mm noch einmal, diesmal mit
    erreichbarem Kanal. Er darf nur dann durchbrechen, wenn die Basis noch bei
    ~10,08 mm steht (27,5 >= 20,17). Waere sie durch den gescheiterten Lauf 2
    auf 27,5 mm fortgeschrieben worden, laege die Schwelle bei 55 mm und
    Lauf 3 bliebe stumm.

    Der Trip fuehrt NUR E-Mail; der stumme Lauf benutzt Settings ohne
    SMTP-Zugang (`can_send_email()` False), der Kanal bleibt also konfiguriert
    (das effektive Kanal-Set ist nicht leer, der Lauf bricht nicht vorher ab),
    ist aber nicht erreichbar.

    🔴 Die `test_smtp_*`-Felder MUESSEN mitgeleert werden: `AlarmPruefstrecke`
    ruft `Settings.with_user_profile(uid)` (`config.py:355`), und weil
    `tdd-…` eine Test-Kennung ist, laeuft das ueber `Settings.for_testing()`
    (`config.py:318`) — das befuellt `smtp_host/-user/-pass` aus
    `test_smtp_*` WIEDER. Ein nur auf `smtp_*` geleertes Objekt waere im Lauf
    also erneut sendefaehig. Die Konstruktionspruefung haengt deshalb am
    Objekt, mit dem der Lauf TATSAECHLICH faehrt (nach `with_user_profile`),
    nicht am Rohobjekt davor — sonst bliebe ein kuenftiger Eingriff in
    `for_testing()` hier unbemerkt.

    RED heute: schon Lauf 3 loest nicht aus."""
    uid = _uid("ac10")
    try:
        trip = _aufbau(
            uid, "ac10", send_telegram=False, send_sms=False, send_premium_sms=False,
        )
        laut = _settings_all_channels()
        stumm = laut.model_copy(update={
            "smtp_host": "", "smtp_user": "", "smtp_pass": "",
            "test_smtp_user": "", "test_smtp_pass": "",
        })
        assert laut.with_user_profile(uid).can_send_email(), (
            "AC-10 Testkonstruktion: der LAUTE Lauf braucht einen erreichbaren "
            "E-Mail-Kanal — geprueft am Objekt, mit dem die Pruefstrecke faehrt."
        )
        assert not stumm.with_user_profile(uid).can_send_email(), (
            "AC-10 Testkonstruktion: der stumme Lauf braucht einen konfigurierten, "
            "aber NICHT erreichbaren E-Mail-Kanal — geprueft NACH "
            "`with_user_profile()`, weil erst dort `for_testing()` die "
            "Zugangsdaten wieder einsetzen wuerde."
        )

        strecke_laut = AlarmPruefstrecke(user_id=uid, settings=laut)
        strecke_stumm = AlarmPruefstrecke(user_id=uid, settings=stumm)

        lauf1 = strecke_laut.lauf(
            at=_AT, zweig="radar", trip=trip,
            radar_service=_radar(_dauerregen(BASIS_RATE_MM_H)),
        )
        assert lauf1.triggered_count == 1, "AC-10 Vorbedingung: Lauf 1 muss ausloesen"

        at2 = _AT + timedelta(minutes=30)
        lauf2 = strecke_stumm.lauf(
            at=at2, zweig="radar", trip=trip,
            radar_service=_radar(_dauerregen(VERSCHAERFT_RATE_MM_H)),
        )
        assert lauf2.triggered_count == 0, (
            f"AC-10 Vorbedingung: ohne erreichbaren Kanal darf nichts als "
            f"zugestellt gelten (war {lauf2.triggered_count})."
        )

        at3 = _AT + timedelta(minutes=60)
        lauf3 = strecke_laut.lauf(
            at=at3, zweig="radar", trip=trip,
            radar_service=_radar(_dauerregen(VERSCHAERFT_RATE_MM_H)),
        )
        assert lauf3.triggered_count == 1, (
            f"AC-10: die Vergleichsbasis darf nach der GESCHEITERTEN Zustellung "
            f"noch bei ~{BASIS_MM:.2f} mm stehen — sonst kommt der Nutzer nach "
            f"einem Zustellfehler an die Verschaerfung nicht mehr heran "
            f"(war triggered_count={lauf3.triggered_count}, Gruende: "
            f"{_gruende(uid, trip, at3)!r})."
        )
    finally:
        _clean_user(uid)


# ─────────────────────────────── AC-13 ───────────────────────────────────────


def test_ac13_die_ueberholungsentscheidung_protokolliert_basis_und_menge(caplog):
    """AC-13. GIVEN ein Lauf mit laufender Sperrzeit, WHEN die
    Ueberholungsentscheidung getroffen wird (Durchbruch ODER Unterdrueckung),
    THEN protokolliert der Lauf sowohl die gelesene Vergleichsbasis als auch
    die aktuell gemessene Menge.

    Abweichung von der Spec-Formulierung, bewusst: der Unterdrueckungsfall
    faehrt NICHT die unveraenderte Lage aus AC-2, sondern die 15,0 mm aus
    AC-4. Bei unveraenderter Lage waeren Basis und Menge dieselbe Zahl — der
    Nachweis 'beide Werte stehen im Protokoll' waere dann schon mit EINER
    Zahl erfuellt und bewachte nichts.

    Geprueft wird auf die beiden ZAHLEN in einer `trip_alert`-Protokollzeile,
    nicht auf einen Wortlaut (s. `_entscheidungszeile`).

    RED heute: es gibt keine Ueberholungsentscheidung und damit auch keine
    Protokollzeile — der gesperrte Lauf holt heute gar keine Daten."""
    uid = _uid("ac13")
    neue_mm = 15.0
    try:
        trip = _aufbau(uid, "ac13")
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf1 = strecke.lauf(
            at=_AT, zweig="radar", trip=trip,
            radar_service=_radar(_dauerregen(BASIS_RATE_MM_H)),
        )
        assert lauf1.triggered_count == 1, "AC-13 Vorbedingung: Lauf 1 muss ausloesen"

        # Unterdrueckungsfall: 15,0 mm gegen ~10,08 mm -> Faktor verfehlt.
        at2 = _AT + timedelta(minutes=30)
        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger="trip_alert"):
            strecke.lauf(
                at=at2, zweig="radar", trip=trip,
                radar_service=_radar(_dauerregen(_rate_dauerregen(neue_mm))),
            )
        zeile_stille = _entscheidungszeile(caplog, BASIS_MM, neue_mm)
        assert zeile_stille is not None, (
            f"AC-13 (Unterdrueckung): das Protokoll muss die gelesene Basis "
            f"(~{BASIS_MM:.2f} mm) UND die gemessene Menge ({neue_mm} mm) "
            f"tragen. `trip_alert`-Zeilen waren: "
            f"{[r.getMessage() for r in caplog.records if r.name == 'trip_alert']!r}"
        )

        # Durchbruchsfall: ~27,5 mm gegen ~10,08 mm.
        at3 = _AT + timedelta(minutes=60)
        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger="trip_alert"):
            lauf3 = strecke.lauf(
                at=at3, zweig="radar", trip=trip,
                radar_service=_radar(_dauerregen(VERSCHAERFT_RATE_MM_H)),
            )
        assert lauf3.triggered_count == 1, (
            f"AC-13 Vorbedingung: der Durchbruchsfall muss durchbrechen "
            f"(war {lauf3.triggered_count})."
        )
        zeile_durchbruch = _entscheidungszeile(caplog, BASIS_MM, VERSCHAERFT_MM)
        assert zeile_durchbruch is not None, (
            f"AC-13 (Durchbruch): das Protokoll muss die gelesene Basis "
            f"(~{BASIS_MM:.2f} mm) UND die gemessene Menge "
            f"(~{VERSCHAERFT_MM:.2f} mm) tragen. `trip_alert`-Zeilen waren: "
            f"{[r.getMessage() for r in caplog.records if r.name == 'trip_alert']!r}"
        )
    finally:
        _clean_user(uid)


# ───────────────── F001 (Adversary #2065): Durchbruch ohne Ausloeser ─────────
#
# Nach einem erfolgreichen Durchbruch ist der Durchgang NICHT MEHR gesperrt —
# er verhaelt sich ab da wie ein freier Lauf. Scheitert er anschliessend am
# Ausloese-Guard (`radar_alert_due`, Onset jenseits
# `RADAR_ONSET_THRESHOLD_MIN`), bleibt er genauso still wie ein freier Lauf in
# derselben Lage: kein Alarm UND kein `alert_log`-Eintrag. „Nicht
# alarmwuerdig" ist in diesem System kein Unterdrueckungs-Ereignis
# (`trip_alert.py`, Ausloese- und Doppel-Alarm-Guard schreiben auch im freien
# Lauf nichts). Ein `cooldown`-Eintrag waere hier FALSCH — die Sperrzeit hat
# diesen Lauf ja gerade nicht unterdrueckt.


def _spaeter_regen(rate_mm_h: float, minute: int = 56):
    """EIN Frame jenseits des Ausloese-Horizonts: Onset `minute` Minuten
    (> `RADAR_ONSET_THRESHOLD_MIN` = 55) -> `radar_alert_due` ist False. Im
    60-Minuten-Vergleichsfenster traegt er trotzdem `60 - minute` Minuten
    Deckung, liefert also eine echte Menge fuer die Ueberholungspruefung."""
    def _quelle(lat: float, lon: float) -> list:
        from providers.brightsky import RadarFrame
        from datetime import timezone as _tz
        jetzt = datetime.now(_tz.utc)
        return [
            RadarFrame(timestamp=jetzt + timedelta(minutes=minute),
                       precip_mm_h=rate_mm_h),
        ]
    return _quelle


def _gemessenes_ergebnis(trip, quelle, at: datetime):
    """Wie `_gemessene_menge`, aber das ganze `NowcastResult` — hier wird
    zusaetzlich der Onset gebraucht."""
    lat, lon = trip.stages[0].waypoints[0].lat, trip.stages[0].waypoints[0].lon
    with freeze_time(at):
        reset_shared_radar_cache_for_tests()
        ergebnis = _radar(quelle).get_nowcast(lat, lon)
        reset_shared_radar_cache_for_tests()
    return ergebnis


def test_f001_durchbruch_ohne_ausloeser_verhaelt_sich_wie_ein_freier_lauf(caplog):
    """F001. GIVEN eine laufende Sperrzeit und eine Lage, die die
    Ueberholungsbedingungen erfuellt, deren Regen aber erst JENSEITS des
    Ausloese-Horizonts beginnt, WHEN der Lauf laeuft, THEN bricht er die
    Sperrzeit durch (Protokollzeile „Durchbruch") und bleibt danach genauso
    still wie ein freier Lauf in derselben Lage — kein Alarm, KEIN
    `alert_log`-Eintrag, insbesondere keiner mit Grund `cooldown`.

    Positivkontrolle im selben Test (PFLICHT): derselbe Lauf auf einem Trip
    OHNE gebuchte Sperre. Ohne sie bewiese die Stille oben nur, dass die Lage
    nicht alarmwuerdig ist — nicht, dass sich der durchgebrochene Lauf
    IDENTISCH zum freien verhaelt. Genau diese Gleichheit ist die Zusicherung.
    """
    from services import radar_service as radar_service_mod

    uid, frei = _uid("f001"), _uid("f001-frei")
    basis_mm = 1.0
    try:
        trip = _aufbau(uid, "f001")
        ergebnis = _gemessenes_ergebnis(trip, _spaeter_regen(60.0), _AT)
        assert ergebnis.onset_minutes is not None, "Testkonstruktion: Onset fehlt"
        assert ergebnis.onset_minutes > radar_service_mod.RADAR_ONSET_THRESHOLD_MIN, (
            f"F001 Testkonstruktion: der Regen muss JENSEITS des "
            f"Ausloese-Horizonts ({radar_service_mod.RADAR_ONSET_THRESHOLD_MIN} "
            f"Min) beginnen, sonst scheitert der Lauf gar nicht am "
            f"Ausloese-Guard (Onset {ergebnis.onset_minutes})."
        )
        menge = ergebnis.window_precip_mm
        assert menge >= 2.0 and menge >= basis_mm * 2.0, (
            f"F001 Testkonstruktion: die Lage muss die Ueberholung LOCKER "
            f"erfuellen (Menge {menge} gegen Basis {basis_mm}) — sonst kaeme "
            f"die Stille von der Ueberholungspruefung statt vom Ausloese-Guard."
        )

        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf1 = strecke.lauf(
            at=_AT, zweig="radar", trip=trip,
            radar_service=_radar(_kurze_spitze(_rate_spitze(basis_mm))),
        )
        assert lauf1.triggered_count == 1, (
            f"F001 Vorbedingung: Lauf 1 muss ausloesen und {basis_mm} mm als "
            f"Vergleichsbasis buchen (war {lauf1.triggered_count})."
        )

        at2 = _AT + timedelta(minutes=30)
        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger="trip_alert"):
            lauf2 = strecke.lauf(
                at=at2, zweig="radar", trip=trip,
                radar_service=_radar(_spaeter_regen(60.0)),
            )
        zeile = _entscheidungszeile(caplog, basis_mm, menge)
        assert zeile is not None and "Durchbruch" in zeile, (
            f"F001: der Lauf MUSS die Sperrzeit durchbrochen haben — sonst "
            f"prueft dieser Test den Ausloese-Guard hinter einer Sperre, die "
            f"gar nicht gefallen ist. Protokollzeile: {zeile!r}"
        )
        assert lauf2.triggered_count == 0, (
            f"F001: jenseits des Ausloese-Horizonts darf kein Alarm rausgehen "
            f"(war {lauf2.triggered_count})."
        )
        assert _gruende(uid, trip, at2) == set(), (
            f"F001: ein durchgebrochener Lauf ist NICHT MEHR gesperrt — er darf "
            f"am Ausloese-Guard keinen Unterdrueckungs-Eintrag hinterlassen, "
            f"schon gar nicht mit Grund {alert_log.REASON_COOLDOWN!r}. "
            f"Protokolliert wurde: {_gruende(uid, trip, at2)!r}"
        )

        # Positivkontrolle: derselbe Lauf ohne jede Sperre.
        frei_trip = _aufbau(frei, "f001-frei")
        frei_strecke = AlarmPruefstrecke(
            user_id=frei, settings=_settings_all_channels(),
        )
        frei_lauf = frei_strecke.lauf(
            at=at2, zweig="radar", trip=frei_trip,
            radar_service=_radar(_spaeter_regen(60.0)),
        )
        assert frei_lauf.triggered_count == lauf2.triggered_count == 0, (
            f"F001 Positivkontrolle: der freie Lauf muss sich genauso verhalten "
            f"(frei={frei_lauf.triggered_count}, durchgebrochen="
            f"{lauf2.triggered_count})."
        )
        assert _gruende(frei, frei_trip, at2) == _gruende(uid, trip, at2) == set(), (
            f"F001 Positivkontrolle: auch der freie Lauf schreibt hier keinen "
            f"Eintrag — die Gleichheit ist die Zusicherung. frei="
            f"{_gruende(frei, frei_trip, at2)!r}, durchgebrochen="
            f"{_gruende(uid, trip, at2)!r}"
        )
    finally:
        _clean_user(uid)
        _clean_user(frei)
