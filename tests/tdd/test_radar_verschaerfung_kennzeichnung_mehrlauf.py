"""TDD RED — Issue #2848: Radar-Verschaerfung desselben Ereignisses kennzeichnen.

SPEC: docs/specs/modules/fix_2848_radar_verschaerfung_kennzeichnen.md
(AC-1, AC-2, AC-3, AC-4, AC-8, AC-9, AC-10 — AC-5/AC-6 liegen in
`test_radar_verschaerfung_kennzeichnung_renderer.py`, AC-7 ist Live-E2E).

Nachbau des Prod-Ablaufs vom 24.08.2026 (Trip 5f534011): derselbe Regen,
gleicher Beginn, vier Radar-Laeufe im 15-Minuten-Abstand mit den gemessenen
Mengen 1,0 -> 3,1 -> 5,2 -> 7,3 mm. Lauf 2 (Faktor 3,1) und Lauf 4 (Faktor
2,35 gegen die Basis 3,1) brechen nach #2065 durch Sperrzeit und Entdopplung,
Lauf 3 (Faktor 1,68) bleibt still. Heute sehen alle drei Alarme gleich aus;
kuenftig sagen Lauf 2 und Lauf 4 in JEDEM Kanal „dasselbe Ereignis, jetzt
staerker: X statt Y mm" (SMS/Premium-SMS: `UP Y>X`).

Wachter (heute GRUEN, muessen gruen bleiben): AC-1 (Durchbruch-Verhalten),
AC-3 (Erstalarm ohne Hinweis), AC-8 (Ortsvergleich ohne Hinweis), die
Negativ-Haelften von AC-4 und die B-Seite von AC-9.
RED (heute ROT, Nutzersicht „Hinweis fehlt"): AC-2, AC-4-Positivkontrollen,
AC-9 (A bekommt „7,3 statt 3,1"), AC-10 (Alarmlog-Felder).

MENGEN-HERLEITUNG (`window_precip_mm`, `radar_service._accumulate_precip_mm`):
Das Ereignis beginnt fest um `_BEGINN` (= `_AT` + 53 Min, wie 13:15 vs.
12:22 am 24.08.) und traegt Frames im 15-Minuten-Raster bis 105 Minuten nach
Beginn (Ende wie 15:00). Das Vergleichsfenster reicht 60 Minuten ab jetzt;
ein Lauf zur Zeit `t` erfasst also `(t + 60) - _BEGINN` Minuten Regen (7, 22,
37, 52 Min). Die Rate je Lauf ist so gewaehlt, dass genau die Zielmenge
entsteht — und jede Menge wird am ECHTEN Nowcast-Ergebnis nachgemessen
(`_gemessene_menge`), nicht nur gerechnet.

Mock-frei: echter `RadarNowcastService` an seiner DI-Naht `frame_source=`,
echte Zustandsdateien unter `get_data_dir(user_id)`, alle vier Kanaele ueber
`AlarmPruefstrecke` (Loopback-Stubs fuer Telegram und seven.io, `mail_sink`
fuer E-Mail). Kein `Mock()`/`patch()`/`MagicMock`, kein Netz.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from freezegun import freeze_time

from app.loader import get_data_dir, save_location
from providers.brightsky import RadarFrame
from services import alert_log
from services.alert_gate import last_nowcast_precip_mm
from services.alert_state import AlertStateService
from services.official_alerts.models import OfficialAlert
from services.radar_service import RadarNowcastService

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
from tests.helpers.nowcast_gate_fixtures import (
    clean_uid, compare_radar_service, location, radar_preset,
    settings_email_only, write_presets, write_user_tier,
)
from tests.tdd.test_952_onset_alert_fidelity import _clean_user
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (
    _AT, _radar_trip, _settings_all_channels, _write_premium_profile,
)
from tests.tdd.test_radar_cooldown_overtake import _gemessene_menge

# Fester Ereignisbeginn (Nachbau 24.08.: Lauf 12:22, Beginn 13:15 -> 53 Min).
_BEGINN = _AT + timedelta(minutes=53)
_ENDE_NACH_MIN = 105                 # Ende 15:00 = Beginn + 105 Min
_FENSTER_MIN = 60                    # _OVERTAKE_COMPARE_WINDOW_MIN
_RADAR_SCOPE = "radar"               # trip_alert._RADAR_THROTTLE_SCOPE

# Die vier Laeufe des 24.08. (Abstand 15 Min) mit ihren gemessenen Mengen.
_LAEUFE = (
    (_AT, 1.0),
    (_AT + timedelta(minutes=15), 3.1),
    (_AT + timedelta(minutes=30), 5.2),
    (_AT + timedelta(minutes=45), 7.3),
)

# Erkennungsmerkmale des Hinweises in jeder Form (fuer die Abwesenheits-
# Pruefungen). Bewusst breit: auch eine falsch formatierte Fassung waere
# beim Erstalarm ein Defekt.
_HINWEIS_RE = re.compile(r"Dasselbe Ereignis|Same event|\bUP \d")


def _uid(tag: str) -> str:
    return f"tdd-2848-{tag}-{uuid.uuid4().hex[:6]}"


def _satz_de(basis: float, menge: float) -> str:
    """Nutzertext laut Spec (DE, Komma, eine Nachkommastelle)."""
    return (
        f"Dasselbe Ereignis, jetzt stärker: {menge:.1f} statt {basis:.1f} mm"
    ).replace(".", ",")


def _token(basis: float, menge: float) -> str:
    """Kurzform laut Spec — ASCII/GSM-7, nie uebersetzt."""
    return f"UP {basis:.1f}>{menge:.1f}"


def _ereignis(mm: float, *, beginn: datetime = _BEGINN):
    """Echte `RadarFrame`-Quelle (kein Mock): Regen ab `beginn` im
    15-Minuten-Raster bis `beginn + 105 Min`, Rate so gewaehlt, dass der
    Lauf zur gestellten Uhr genau `mm` im 60-Min-Vergleichsfenster erfasst.

    Die Uhr wird BEIM ABRUF gelesen (`datetime.now` unter `freeze_time`), wie
    bei `_dauerregen` — so gilt dieselbe Quelle fuer Pruefling und Messung."""
    def _quelle(lat: float, lon: float) -> list:
        jetzt = datetime.now(timezone.utc)
        fensterende = jetzt + timedelta(minutes=_FENSTER_MIN)
        ende = beginn + timedelta(minutes=_ENDE_NACH_MIN)
        abgedeckt = (min(fensterende, ende) - beginn).total_seconds() / 60.0
        assert abgedeckt > 0, "Testaufbau: Beginn liegt hinter dem Vergleichsfenster"
        rate = mm * 60.0 / abgedeckt
        return [
            RadarFrame(timestamp=beginn + timedelta(minutes=m), precip_mm_h=rate)
            for m in range(0, _ENDE_NACH_MIN, 15)
        ]
    return _quelle


def _radar(quelle) -> RadarNowcastService:
    return RadarNowcastService(frame_source=quelle)


def _aufbau(uid: str, tag: str):
    """Premium-Nutzer (kein Tageslimit, frische Garmin-Rueckadresse) und ein
    Trip mit aktivem Segment und ALLEN vier Kanaelen. Kein Briefing-Anker
    (Briefing-Ueberholung faellt als Entscheidungsgrund aus, Vorbild #2065)."""
    _clean_user(uid)
    _write_premium_profile(uid, _AT)
    with freeze_time(_AT):
        trip = _radar_trip(
            uid, f"trip-2848-{tag}", send_email=True, send_telegram=True,
            send_sms=True, send_premium_sms=True,
        )
    return trip


def _strecke(uid: str) -> AlarmPruefstrecke:
    return AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())


def _basis(uid: str, trip) -> float | None:
    """Vergleichsbasis der naechsten Runde — ueber den PRODUKTIVEN Lesepfad,
    den auch `check_radar_alerts()` benutzt."""
    return last_nowcast_precip_mm(
        user_id=uid, throttle_scope=_RADAR_SCOPE, throttle_key=trip.id,
    )


def _texte(lauf) -> dict[str, list[str]]:
    return {
        "mail": [body for _subject, body in lauf.mail],
        "telegram": list(lauf.telegram),
        "sms": list(lauf.sms),
        "premium_sms": list(lauf.premium_sms),
    }


def _kanaele(lauf) -> dict[str, int]:
    return {k: len(v) for k, v in _texte(lauf).items()}


def _nowcast_eintraege(uid: str, trip_id: str) -> list[dict]:
    """Zugestellte Nowcast-Eintraege des Alarmlogs — die Datei, die die
    Go-API dem Nutzer zeigt (Ort der Wirkung von AC-10)."""
    pfad = get_data_dir(uid) / "alert_log.json"
    if not pfad.exists():
        return []
    daten = json.loads(pfad.read_text())
    return [
        e for e in daten.get("entries", [])
        if e.get("entity_id") == trip_id and e.get("reason") == alert_log.REASON_NOWCAST
    ]


def _alle_eintraege(uid: str) -> list[dict]:
    pfad = get_data_dir(uid) / "alert_log.json"
    return json.loads(pfad.read_text()).get("entries", []) if pfad.exists() else []


def _pruefe_hinweis_in_allen_kanaelen(lauf, basis: float, menge: float, wo: str) -> None:
    """AC-2-Kern: Aussage UND beide Zahlen, in der richtigen Reihenfolge, je
    Kanal dort gemessen, wo der Nutzer sie liest."""
    texte = _texte(lauf)
    satz = _satz_de(basis, menge)
    token = _token(basis, menge)
    assert texte["mail"], f"{wo}: keine E-Mail zugestellt: {_kanaele(lauf)!r}"
    assert any(satz in b for b in texte["mail"]), (
        f"{wo}: die E-Mail muss den Hinweis {satz!r} tragen — der Alarm sieht "
        f"sonst aus wie der erste. E-Mail-Text: {texte['mail']!r}"
    )
    assert texte["telegram"], f"{wo}: kein Telegram zugestellt: {_kanaele(lauf)!r}"
    assert any(satz in t for t in texte["telegram"]), (
        f"{wo}: Telegram muss den Hinweis {satz!r} tragen. Telegram-Text: "
        f"{texte['telegram']!r}"
    )
    for kanal in ("sms", "premium_sms"):
        assert texte[kanal], f"{wo}: kein {kanal} zugestellt: {_kanaele(lauf)!r}"
        for text in texte[kanal]:
            assert re.search(r": " + re.escape(token) + r" (?:R|TH)", text), (
                f"{wo}: {kanal} muss das Token {token!r} direkt nach dem Ortskopf "
                f"und vor dem Radar-Token tragen. Text: {text!r}"
            )


def _pruefe_kein_hinweis(lauf, wo: str) -> None:
    for kanal, liste in _texte(lauf).items():
        for text in liste:
            assert not _HINWEIS_RE.search(text), (
                f"{wo}: {kanal} darf KEINEN Verschaerfungs-Hinweis tragen: {text!r}"
            )


# ───────────────────────── Gemeinsamer Nachbau 24.08. ───────────────────────


@pytest.fixture(scope="module")
def nachbau():
    """Faehrt die vier Laeufe EINMAL fuer alle Tests dieser Gruppe (AC-1, AC-2,
    AC-3, AC-10) — der Nachbau ist teuer, das Ergebnis deterministisch.

    Vor Lauf 1 steht ein Alt-Eintrag (Vortag, Abweichungsalarm) im Alarmlog,
    angelegt ueber den PRODUKTIVEN Schreibweg `alert_log.append_entry()` —
    AC-10 prueft, dass er unveraendert erhalten bleibt."""
    uid = _uid("nachbau")
    trip = _aufbau(uid, "nachbau")
    with freeze_time(_AT - timedelta(days=1)):
        alert_log.append_entry(
            uid, entity_id=trip.id, entity_type="trip", changes_count=1,
            severity="MODERATE", reason=alert_log.REASON_FORECAST_CHANGE,
            effective_channels=["email"], sent_channels=["email"],
        )
    altbestand = [dict(e) for e in _alle_eintraege(uid)]

    gemessen = [
        _gemessene_menge(trip, _ereignis(mm), at) for at, mm in _LAEUFE
    ]
    strecke = _strecke(uid)
    laeufe, basen = [], []
    for at, mm in _LAEUFE:
        laeufe.append(strecke.lauf(
            at=at, zweig="radar", trip=trip, radar_service=_radar(_ereignis(mm)),
        ))
        basen.append(_basis(uid, trip))
    ergebnis = {
        "uid": uid, "trip": trip, "laeufe": laeufe, "basen": basen,
        "gemessen": gemessen, "altbestand": altbestand,
        "eintraege": _nowcast_eintraege(uid, trip.id),
        "alle": _alle_eintraege(uid),
    }
    yield ergebnis
    _clean_user(uid)


# ─────────────────────────────── AC-1 ────────────────────────────────────────


def test_ac1_nachbau_24_08_drei_alarme_lauf_drei_still(nachbau):
    """AC-1 (WAECHTER, heute gruen). GIVEN vier Laeufe mit gleichem Beginn
    und 1,0 -> 3,1 -> 5,2 -> 7,3 mm im 15-Min-Abstand, WHEN alle durchlaufen,
    THEN genau drei Alarme (Lauf 1, 2, 4), Lauf 3 still; Vergleichsbasis nach
    Lauf 2 ist 3,1 mm. Belegt: kein Deckel, keine verschaerfte Entdopplung
    (Fehlerrichtung „Alarm bleibt aus" verboten)."""
    for (at, soll), ist in zip(_LAEUFE, nachbau["gemessen"]):
        assert abs(ist - soll) < 0.01, (
            f"Testaufbau: der Nowcast zur Uhr {at:%H:%M} muss {soll} mm messen, "
            f"gemessen {ist!r}"
        )
    zaehler = [lauf.triggered_count for lauf in nachbau["laeufe"]]
    assert zaehler == [1, 1, 0, 1], (
        f"AC-1: erwartet Alarm/Alarm/still/Alarm wie am 24.08., war {zaehler!r}"
    )
    for nr in (0, 1, 3):
        k = _kanaele(nachbau["laeufe"][nr])
        assert all(n >= 1 for n in k.values()), (
            f"AC-1: Lauf {nr + 1} muss alle vier Kanaele erreichen: {k!r}"
        )
    assert _kanaele(nachbau["laeufe"][2]) == {
        "mail": 0, "telegram": 0, "sms": 0, "premium_sms": 0,
    }, f"AC-1: Lauf 3 (5,2 mm, Faktor 1,68) muss still bleiben: {_kanaele(nachbau['laeufe'][2])!r}"
    basen = nachbau["basen"]
    assert basen[1] is not None and abs(basen[1] - 3.1) < 0.01, (
        f"AC-1: Vergleichsbasis nach Lauf 2 muss 3,1 mm sein, war {basen[1]!r}"
    )
    assert basen[2] is not None and abs(basen[2] - 3.1) < 0.01, (
        f"AC-1: der stille Lauf 3 darf die Basis nicht verschieben, war {basen[2]!r}"
    )


# ─────────────────────────────── AC-2 ────────────────────────────────────────


def test_ac2_lauf_zwei_traegt_den_hinweis_in_allen_vier_kanaelen(nachbau):
    """AC-2 (RED). Lauf 2 (1,0 -> 3,1 mm): „Dasselbe Ereignis, jetzt
    staerker: 3,1 statt 1,0 mm" in E-Mail und Telegram, `UP 1.0>3.1` in SMS
    und Premium-SMS. RED heute: der Alarm traegt keinen Hinweis."""
    _pruefe_hinweis_in_allen_kanaelen(nachbau["laeufe"][1], 1.0, 3.1, "AC-2 Lauf 2")


def test_ac2_lauf_vier_traegt_den_hinweis_in_allen_vier_kanaelen(nachbau):
    """AC-2 (RED). Lauf 4 (3,1 -> 7,3 mm): Zahlen gegen die zuletzt GEMELDETE
    Menge (3,1), nicht gegen den stillen Lauf 3 (5,2) und nicht gegen den
    Erstalarm (1,0)."""
    lauf = nachbau["laeufe"][3]
    _pruefe_hinweis_in_allen_kanaelen(lauf, 3.1, 7.3, "AC-2 Lauf 4")
    alles = "\n".join(t for v in _texte(lauf).values() for t in v)
    for falsch in ("7,3 statt 5,2", "7,3 statt 1,0", "UP 5.2>7.3", "UP 1.0>7.3"):
        assert falsch not in alles, (
            f"AC-2: Lauf 4 nennt eine falsche Vergleichsbasis ({falsch!r})"
        )


# ─────────────────────────────── AC-3 ────────────────────────────────────────


def test_ac3_erstalarm_traegt_keinen_hinweis(nachbau):
    """AC-3 (WAECHTER, heute gruen). Lauf 1 ist der erste Alarm des
    Ereignisses — kein Hinweis in keinem der vier Kanaele. Die Byte-Gleichheit
    des Renderers fuer Alarme ohne Kennzeichen bewacht
    `test_radar_verschaerfung_kennzeichnung_renderer.py` gegen die Golden-
    Dateien des Bestands."""
    lauf = nachbau["laeufe"][0]
    assert lauf.triggered_count == 1
    _pruefe_kein_hinweis(lauf, "AC-3 Lauf 1")


def test_ac3_erstalarm_gleicht_dem_einzellauf_ohne_vorgeschichte():
    """AC-3 (WAECHTER). Der Erstalarm im Nachbau ist textgleich zu einem
    Einzellauf desselben Aufbaus bei einem Nutzer ohne jede Vorgeschichte —
    in allen vier Kanaelen. Bewacht, dass die neue Logik keinen Zustand aus
    einem leeren Register / fehlender Basis „erfindet"."""
    a, b = _uid("ac3-a"), _uid("ac3-b")
    try:
        trip_a = _aufbau(a, "ac3")
        trip_b = _aufbau(b, "ac3")
        at, mm = _LAEUFE[0]
        lauf_a = _strecke(a).lauf(at=at, zweig="radar", trip=trip_a,
                                  radar_service=_radar(_ereignis(mm)))
        lauf_b = _strecke(b).lauf(at=at, zweig="radar", trip=trip_b,
                                  radar_service=_radar(_ereignis(mm)))
        assert lauf_a.triggered_count == lauf_b.triggered_count == 1
        assert _texte(lauf_a) == _texte(lauf_b), (
            "AC-3: zwei Erstalarme desselben Aufbaus muessen byte-gleich sein"
        )
        _pruefe_kein_hinweis(lauf_a, "AC-3 Einzellauf")
    finally:
        _clean_user(a)
        _clean_user(b)


# ─────────────────────────────── AC-4 ────────────────────────────────────────


@pytest.mark.timeout(120)
def test_ac4a_ohne_radar_vorgaenger_im_register_kein_hinweis():
    """AC-4 (a). GIVEN die Sperrzeit wird mengenmaessig ueberholt (Basis 1,0,
    Menge 3,1), aber im Ereignis-Register steht KEIN frueherer Alarm — das
    Register wurde dazwischen ueber den produktiven Briefing-Reset
    (`AlertStateService.reset`) geleert, die Vergleichsbasis in der
    Sperrzeit-Buchhaltung bleibt —, WHEN der Alarm zugestellt wird, THEN
    erscheint KEIN „dasselbe Ereignis"-Hinweis (die Behauptung waere falsch).

    Positivkontrolle (RED heute): derselbe Aufbau OHNE Reset — der
    Radar-Vorgaenger steht im Register — traegt den Hinweis. Ohne sie haenge
    das Ausbleiben oben womoeglich an einer Nebenbedingung."""
    uid, ctrl = _uid("ac4a"), _uid("ac4a-ctrl")
    try:
        for wer in (uid, ctrl):
            trip = _aufbau(wer, "ac4a")
            strecke = _strecke(wer)
            l1 = strecke.lauf(at=_LAEUFE[0][0], zweig="radar", trip=trip,
                              radar_service=_radar(_ereignis(1.0)))
            assert l1.triggered_count == 1, f"Vorbedingung Lauf 1 ({wer})"
            if wer == uid:
                AlertStateService(user_id=uid).reset(trip.id)
                assert not [
                    k for k in AlertStateService(user_id=uid).load(trip.id)
                    if k.startswith("event_identity:")
                ], "Testaufbau: das Register muss nach dem Reset leer sein"
            assert abs((_basis(wer, trip) or 0) - 1.0) < 0.01, (
                f"Testaufbau: die Vergleichsbasis 1,0 mm muss stehen bleiben ({wer})"
            )
            l2 = strecke.lauf(at=_LAEUFE[1][0], zweig="radar", trip=trip,
                              radar_service=_radar(_ereignis(3.1)))
            assert l2.triggered_count == 1, (
                f"AC-4a: der Mengen-Durchbruch muss in BEIDEN Aufbauten zustellen "
                f"({wer}, war {l2.triggered_count})"
            )
            if wer == uid:
                _pruefe_kein_hinweis(l2, "AC-4a (Register leer)")
            else:
                _pruefe_hinweis_in_allen_kanaelen(
                    l2, 1.0, 3.1, "AC-4a Positivkontrolle (Radar-Vorgaenger im Register)",
                )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


def _amtliche_warnung(at: datetime, wer: str, trip, strecke) -> None:
    """ECHTER amtlicher Alarm-Lauf (Stufe 4 = HIGH, gleichrangig zum Radar),
    registriert ueber den produktiven Weg `_send_official_alert_only` ->
    `record_event_identity`. Als JUENGSTER gleichrangiger Kandidat wird er der
    Vorgaenger, den `check_event_identity_gate` waehlt.

    Die Gueltigkeit reicht bewusst 8 Stunden: der Radar-Eintrag aus Lauf 1
    deckt `Beginn + NOWCAST_HORIZON_MIN` (180) ab; nur eine Warnung, die
    WESENTLICH weiter reicht (V1-Ausnahme, > weitere 180 Min), kommt neben
    dem gleichrangigen Radar-Eintrag ueberhaupt durch — sonst waere sie selbst
    ein `event_duplicate`."""
    alarm = OfficialAlert(
        source="tdd-2848", hazard="rain", level=4, label="Starkregenwarnung",
        valid_from=at - timedelta(hours=1), valid_to=at + timedelta(hours=8),
    )
    lauf = strecke.lauf(at=at, zweig="official", trip=trip,
                        official_notices=[(alarm, ["1"])])
    assert lauf.triggered_count == 1, (
        f"Testaufbau: die amtliche Warnung muss zustellen ({wer}, war "
        f"{lauf.triggered_count})"
    )
    quellen = [
        v.get("source") for k, v in AlertStateService(user_id=wer).load(trip.id).items()
        if k.startswith("event_identity:") and isinstance(v, dict)
    ]
    assert "official" in quellen, (
        f"Testaufbau: die amtliche Warnung muss registriert sein: {quellen!r}"
    )


@pytest.mark.timeout(120)
def test_ac4b_vorgaenger_amtlich_nachtragstext_bleibt_kein_hinweis():
    """AC-4 (b). GIVEN Radar-Alarm 1,0 mm, danach eine amtliche Warnung
    desselben Ereignisses (juengster gleichrangiger Registereintrag), WHEN der
    Radar-Lauf mit 3,1 mm die Sperrzeit mengenmaessig ueberholt, THEN geht er
    als NACHTRAG raus („Ergänzung zur amtlichen Warnung" unveraendert) und
    traegt KEINEN „dasselbe Ereignis"-Hinweis (Nachtrags-Zweig #2018 bleibt).

    Positivkontrolle (RED heute): derselbe Ablauf ohne die amtliche Warnung
    traegt den Hinweis."""
    uid, ctrl = _uid("ac4b"), _uid("ac4b-ctrl")
    try:
        for wer in (uid, ctrl):
            trip = _aufbau(wer, "ac4b")
            strecke = _strecke(wer)
            l1 = strecke.lauf(at=_LAEUFE[0][0], zweig="radar", trip=trip,
                              radar_service=_radar(_ereignis(1.0)))
            assert l1.triggered_count == 1, f"Vorbedingung Lauf 1 ({wer})"
            if wer == uid:
                _amtliche_warnung(_AT + timedelta(minutes=5), wer, trip, strecke)
            l2 = strecke.lauf(at=_LAEUFE[1][0], zweig="radar", trip=trip,
                              radar_service=_radar(_ereignis(3.1)))
            assert l2.triggered_count == 1, (
                f"AC-4b: der Mengen-Durchbruch muss zustellen ({wer}, war "
                f"{l2.triggered_count})"
            )
            if wer == uid:
                text = "\n".join(l2.telegram + [b for _s, b in l2.mail])
                assert "Ergänzung zur amtlichen Warnung" in text, (
                    f"AC-4b: der bestehende Nachtragstext muss unveraendert "
                    f"stehen: {text!r}"
                )
                _pruefe_kein_hinweis(l2, "AC-4b (Vorgaenger amtlich)")
            else:
                _pruefe_hinweis_in_allen_kanaelen(
                    l2, 1.0, 3.1, "AC-4b Positivkontrolle (Vorgaenger Radar)",
                )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


# ─────────────────────────────── AC-8 ────────────────────────────────────────


def _vergleichs_quelle(rate_mm_h: float):
    """Nasser Frame acht Minuten voraus (Ortsvergleich-Radar)."""
    def _quelle(lat: float, lon: float) -> list:
        jetzt = datetime.now(timezone.utc)
        return [
            RadarFrame(timestamp=jetzt + timedelta(minutes=m), precip_mm_h=rate_mm_h)
            for m in (8, 23, 38, 53)
        ]
    return _quelle


@pytest.mark.timeout(120)
def test_ac8_ortsvergleich_radar_nach_mengenverdopplung_ohne_hinweis():
    """AC-8 (WAECHTER, heute gruen). GIVEN ein Ortsvergleich mit Radar-Alarm,
    dessen Menge sich zwischen zwei Laeufen mehr als verdoppelt (2 -> 6 mm/h,
    MODERATE -> HIGH, ohne Sperrzeit, damit der zweite Lauf ueberhaupt
    zugestellt wird), WHEN die Radar-Alarme des Ortsvergleichs zugestellt
    werden, THEN traegt keiner einen Verschaerfungs-Hinweis — #2065 wirkt im
    Ortsvergleich bewusst nicht. Byte-Gleichheit des geteilten Renderers fuer
    den Ortsvergleich bewacht die Renderer-Datei (Golden `regen_buendel`)."""
    uid, preset_id = _uid("ac8"), "cp-2848-ac8"
    clean_uid(uid)
    try:
        write_user_tier(uid, "premium")
        save_location(location("loc-2848", "Verschaerfungsdorf"), user_id=uid)
        write_presets(uid, [radar_preset(preset_id, ["loc-2848"], user_id=uid,
                                         cooldown_minutes=0)])
        mails: list = []
        gesendet = []
        for at, rate in ((_AT, 2.0), (_AT + timedelta(minutes=15), 6.0)):
            with freeze_time(at):
                gesendet.append(compare_radar_service(
                    uid, settings_email_only(), _vergleichs_quelle(rate),
                    lambda subject, body: mails.append((subject, body)),
                ).check_all_compare_presets())
        assert gesendet == [1, 1], (
            f"AC-8 Vorbedingung: beide Laeufe muessen zustellen — sonst sieht der "
            f"Test den Alarm nach der Verdopplung gar nicht ({gesendet!r})"
        )
        assert len(mails) == 2, f"AC-8: zwei Ortsvergleich-Mails erwartet: {mails!r}"
        for subject, body in mails:
            assert not _HINWEIS_RE.search(subject + "\n" + body), (
                f"AC-8: der Ortsvergleich darf nie einen Verschaerfungs-Hinweis "
                f"tragen: {subject!r} / {body!r}"
            )
    finally:
        clean_uid(uid)


# ─────────────────────────────── AC-9 ────────────────────────────────────────


@pytest.mark.timeout(120)
def test_ac9_mandantentrennung_zahlenpaar_nur_aus_eigenen_daten():
    """AC-9. GIVEN Nutzer A (Vorgaenger 3,1 mm) und Nutzer B (Vorgaenger
    9,0 mm), je eigener Trip und eigenes Datenverzeichnis, WHEN fuer beide
    derselbe Lauf mit 7,3 mm durchlaeuft, THEN bekommt nur A einen
    Verschaerfungs-Alarm „7,3 statt 3,1 mm" (RED heute: Hinweis fehlt); B
    (7,3 gegen 9,0) bleibt still (Waechter); kein Zahlenpaar stammt aus den
    Daten des anderen Nutzers, und B's Alarmlog traegt keine Eskalations-
    Felder."""
    a, b = _uid("ac9-a"), _uid("ac9-b")
    try:
        trip_a = _aufbau(a, "ac9")
        trip_b = _aufbau(b, "ac9")
        assert get_data_dir(a) != get_data_dir(b), "Testaufbau: getrennte Verzeichnisse"
        strecke_a, strecke_b = _strecke(a), _strecke(b)
        at1, at2 = _LAEUFE[0][0], _LAEUFE[1][0]
        assert strecke_a.lauf(at=at1, zweig="radar", trip=trip_a,
                              radar_service=_radar(_ereignis(3.1))).triggered_count == 1
        assert strecke_b.lauf(at=at1, zweig="radar", trip=trip_b,
                              radar_service=_radar(_ereignis(9.0))).triggered_count == 1
        assert abs((_basis(a, trip_a) or 0) - 3.1) < 0.01
        assert abs((_basis(b, trip_b) or 0) - 9.0) < 0.01

        lauf_b = strecke_b.lauf(at=at2, zweig="radar", trip=trip_b,
                                radar_service=_radar(_ereignis(7.3)))
        lauf_a = strecke_a.lauf(at=at2, zweig="radar", trip=trip_a,
                                radar_service=_radar(_ereignis(7.3)))

        assert lauf_b.triggered_count == 0, (
            f"AC-9: B (7,3 gegen 9,0 mm) ist keine Verschaerfung — kein "
            f"Durchbruch (war {lauf_b.triggered_count}, {_kanaele(lauf_b)!r})"
        )
        assert all(
            "escalation_from_mm" not in e and "escalation_to_mm" not in e
            for e in _alle_eintraege(b)
        ), f"AC-9: B's Alarmlog darf keine Eskalations-Felder tragen: {_alle_eintraege(b)!r}"

        assert lauf_a.triggered_count == 1, (
            f"AC-9: A (7,3 gegen 3,1 mm) muss durchbrechen (war {lauf_a.triggered_count})"
        )
        alles_a = "\n".join(t for v in _texte(lauf_a).values() for t in v)
        assert "9,0" not in alles_a and "9.0" not in alles_a, (
            f"AC-9: A's Alarm darf keine Zahl aus B's Daten tragen: {alles_a!r}"
        )
        _pruefe_hinweis_in_allen_kanaelen(lauf_a, 3.1, 7.3, "AC-9 Nutzer A")
        eintraege_a = _nowcast_eintraege(a, trip_a.id)
        assert abs(eintraege_a[-1].get("escalation_from_mm", -1) - 3.1) < 0.05, (
            f"AC-9: A's Alarmlog muss die eigene Basis 3,1 tragen: {eintraege_a[-1]!r}"
        )
    finally:
        _clean_user(a)
        _clean_user(b)


# ─────────────────────────────── AC-10 ───────────────────────────────────────


def test_ac10_nur_der_verschaerfungs_eintrag_traegt_die_felder(nachbau):
    """AC-10 (RED). Nach dem Nachbau stehen drei zugestellte Nowcast-Eintraege
    im Alarmlog. Genau die beiden Verschaerfungs-Alarme (Lauf 2, Lauf 4)
    tragen `escalation_from_mm`/`escalation_to_mm` mit den Werten aus dem
    Alarm (1,0/3,1 und 3,1/7,3); der Erstalarm traegt die Felder NICHT."""
    eintraege = nachbau["eintraege"]
    assert len(eintraege) == 3, (
        f"Testaufbau: drei zugestellte Nowcast-Eintraege erwartet, gefunden "
        f"{len(eintraege)}: {eintraege!r}"
    )
    erst, zweit, viert = eintraege
    assert "escalation_from_mm" not in erst and "escalation_to_mm" not in erst, (
        f"AC-10: der Erstalarm darf die Felder nicht tragen: {erst!r}"
    )
    for eintrag, (von, nach), wo in (
        (zweit, (1.0, 3.1), "Lauf 2"), (viert, (3.1, 7.3), "Lauf 4"),
    ):
        assert "escalation_from_mm" in eintrag and "escalation_to_mm" in eintrag, (
            f"AC-10: der Verschaerfungs-Eintrag {wo} muss beide Felder tragen: "
            f"{eintrag!r}"
        )
        assert abs(eintrag["escalation_from_mm"] - von) < 0.05, (
            f"AC-10 {wo}: escalation_from_mm muss {von} sein: {eintrag!r}"
        )
        assert abs(eintrag["escalation_to_mm"] - nach) < 0.05, (
            f"AC-10 {wo}: escalation_to_mm muss {nach} sein: {eintrag!r}"
        )


def test_ac10_altbestand_bleibt_unveraendert_erhalten(nachbau):
    """AC-10 (WAECHTER). Der vor dem Nachbau angelegte Alt-Eintrag steht nach
    allen Laeufen unveraendert am Anfang des Logs und hat keine neuen Felder
    bekommen (Read-Modify-Write mit Merge, kein Replace)."""
    alt = nachbau["altbestand"]
    alle = nachbau["alle"]
    assert len(alt) == 1, f"Testaufbau: genau ein Alt-Eintrag: {alt!r}"
    assert alle[: len(alt)] == alt, (
        f"AC-10: der Altbestand muss unveraendert erhalten bleiben. Vorher "
        f"{alt!r}, nachher {alle[: len(alt)]!r}"
    )
    assert "escalation_from_mm" not in alle[0] and "escalation_to_mm" not in alle[0]
