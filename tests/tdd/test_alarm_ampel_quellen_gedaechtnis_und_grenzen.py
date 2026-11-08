"""Ampel-Alarm: alle Quellen, Melde-Gedaechtnis, Grenzwerte (Issue #2793 S2b,
Fix-Loop 2 nach Adversary F101-F105).

SPEC: docs/specs/modules/feat_2793_s2_alarm_stufenwechsel.md (v1.2, §1-§4)
ACs: AC-1 bis AC-5 je Metrik (§1-Tabelle), AC-2 (Grenze), AC-9 (Mischfall),
AC-12 (D4 im SMS-Token), AC-18 (Farbpaar in der Mail), AC-20 (Trip UND
Orts-Vergleich, Entwarnung).

Jede Zusicherung wird dort gemessen, wo sie fuer den Nutzer WIRKT: am echten
Trip- bzw. Vergleichs-Einstieg, an der zugestellten Mail (Klartext und HTML
am SMTP-Draht), am SMS-Draht der Gegenstelle, am Alarm-Protokoll und am rohen
Eingangs-Datensatz (``data/users/<uid>/alert_input``). Ausnahme mit Grund:
``suppressed_reason`` (F105/E1) erreicht keinen Kanal und kein Protokoll, er
ist allein Rueckgabe der geteilten ``DeviationAlertEngine`` (Trip und
Vergleich, ADR-0021) und wird dort gemessen.

Kein ``Mock()``/``patch()``/``MagicMock``; Persistenz unter der
pytest-isolierten Datenwurzel (#1133). Jede Kennung ist ein frischer Nutzer.
Baubloecke (Trip, Lauf, Quelle) teilt diese Datei mit
``test_alarm_ampel_randpfade.py``.
"""
from __future__ import annotations

import email as email_mod
import json
import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.loader import get_data_dir, save_location
from app.models import ThunderLevel
from app.user import SavedLocation

from tests.helpers.alert_log_fixtures import (
    LAT, LON, clean_compare_user, compare_data_root, read_log, reason_for_channel,
    settings_email_only,
)
from tests.helpers.compare_briefings import write_compare_briefings
from tests.helpers.kanal_fake_transporte import KanalRig, kanal_auswahl, premium_profil_schreiben
from tests.tdd.test_alarm_ampel_randpfade import (
    _FARBPAAR, _Quelle, _alarm_eintraege, _ampel, _eingangs_datensaetze, _profil, _trip,
    _trip_lauf,
)


def _uid(tag: str) -> str:
    return f"tdd-2793-qg-{tag}-{uuid.uuid4().hex[:6]}"


@pytest.fixture
def rig(monkeypatch):
    r = KanalRig(monkeypatch)
    yield r
    r.stoppen()


def _rig_lauf(rig: KanalRig, uid: str, trip, alt: dict, neu: dict) -> dict[str, str]:
    """Alarm-Lauf gegen die echten Kanal-Ausgaenge; Text je Kanal."""
    from services.trip_alert import TripAlertService
    from tests.helpers.alert_log_fixtures import weather

    jetzt = datetime.now(timezone.utc)
    premium_profil_schreiben(uid, reply_at=jetzt - timedelta(minutes=5))
    _profil(uid, "de")
    TripAlertService(
        settings=rig.settings(premium_reply_at=jetzt - timedelta(minutes=5)),
        user_id=uid, throttle_hours=0,
    ).check_and_send_alerts(trip, [weather(1, **alt)], fresh_weather=[weather(1, **neu)])
    texte: dict[str, str] = {}
    if rig.angenommen["sms"]:
        texte["sms"] = rig.angenommen["sms"][-1]["text"]
    if rig.angenommen["email"]:
        nachricht = email_mod.message_from_string(rig.angenommen["email"][-1]["roh"])
        for teil in nachricht.walk():
            if teil.get_content_type() == "text/plain":
                texte["email"] = teil.get_payload(decode=True).decode()
            elif teil.get_content_type() == "text/html":
                texte["html"] = teil.get_payload(decode=True).decode()
    return texte


def _change(uid: str, feld: str) -> dict:
    """Ereignis ``feld`` im rohen Eingangs-Datensatz des letzten Alarms."""
    datensaetze = _eingangs_datensaetze(uid)
    assert datensaetze, "kein Eingangs-Datensatz zum Alarm geschrieben"
    treffer = [c for c in datensaetze[-1]["payload"]["changes"] if c["metric"] == feld]
    assert treffer, datensaetze[-1]["payload"]["changes"]
    return treffer[0]


# ═══════ F101 — die vier uebrigen Ampel-Quellen alarmieren nach der Farbe ═════
#
# Vorlage „Allgemein": Wind gelb 30 / orange 50 / rot 70 km/h, Neuschnee
# gelb 10 / orange 20 / rot 30 cm, Sicht (Seite „unten") gelb < 2000 /
# orange < 1000 / rot < 500 m, UV gelb 3 / orange 6 / rot 8. Jede Metrik
# „Alarm ab Orange" (UV ausdruecklich, die Vorlage sagt dort „Nie").

_QUELLEN = [
    # catalog_id, Feld, Ankerwert, Neuwert, Farbe Anker, Farbe neu, Richtung
    ("wind", "wind_max_kmh", 40.0, 55.0, "gelb", "orange", "increase"),
    ("fresh_snow", "snow_new_sum_cm", 15.0, 25.0, "gelb", "orange", "increase"),
    ("visibility", "visibility_min_m", 3000.0, 800.0, "grün", "orange", "decrease"),
    ("uv_index", "uv_index_max", 2.0, 7.0, "grün", "orange", "increase"),
]


@pytest.mark.parametrize("cid,feld,alt,neu,von,bis,richtung", _QUELLEN,
                         ids=[q[0] for q in _QUELLEN])
def test_f101_verschaerfung_je_ampel_quelle_ueber_den_trip(cid, feld, alt, neu, von, bis, richtung):
    """AC-1 je Metrik: GIVEN „Alarm ab Orange" und ein Anker unter Orange /
    WHEN die Prognose die Farbe Orange erreicht (bei Sicht: der Wert FAELLT
    unter 1000 m) / THEN ein Alarm „von {von} auf {bis} gestiegen", Protokoll
    MODERATE, Eingangs-Datensatz mit der Richtung des Werts."""
    uid = _uid(f"v-{cid}")
    trip = _trip(f"trip-v-{cid}", alarm_ab={cid: "orange"}, metrics=(cid,))
    mails = _trip_lauf(uid, trip, {feld: alt}, {feld: neu})
    assert mails, f"{cid}: {von} -> {bis} bei Alarm ab Orange muss alarmieren."
    assert f"von {von} auf {bis} gestiegen" in mails[-1][1], mails[-1][1]
    assert _alarm_eintraege(uid)[-1]["severity"] == "MODERATE", _alarm_eintraege(uid)
    assert _change(uid, feld)["direction"] == richtung


@pytest.mark.parametrize("cid,feld,alt,neu,von,bis,richtung", _QUELLEN,
                         ids=[q[0] for q in _QUELLEN])
def test_f101_entwarnung_je_ampel_quelle_ueber_den_trip(cid, feld, alt, neu, von, bis, richtung):
    """AC-3 je Metrik: GIVEN derselbe Aufbau, Anker orange / WHEN die Prognose
    zurueck unter Orange geht (bei Sicht: der Wert STEIGT ueber 1000 m) /
    THEN eine Entwarnung „von {bis} auf {von} zurückgegangen", Dringlichkeit
    aus der verlassenen Farbe Orange (MODERATE), Richtung gegenlaeufig."""
    uid = _uid(f"e-{cid}")
    trip = _trip(f"trip-e-{cid}", alarm_ab={cid: "orange"}, metrics=(cid,))
    mails = _trip_lauf(uid, trip, {feld: neu}, {feld: alt})
    assert mails, f"{cid}: {bis} -> {von} muss entwarnen."
    text = mails[-1][1]
    assert "Entwarnung" in text and f"von {bis} auf {von} zurückgegangen" in text, text
    assert _alarm_eintraege(uid)[-1]["severity"] == "MODERATE", _alarm_eintraege(uid)
    gegen = "decrease" if richtung == "increase" else "increase"
    assert _change(uid, feld)["direction"] == gegen


def test_f101_sicht_steigt_ist_nie_eine_verschaerfung():
    """Sicht-Seite „unten": GIVEN Sicht „Alarm ab Orange" / WHEN die Sicht von
    800 m (orange) auf 400 m faellt / THEN Alarm „von orange auf rot"; und
    eine STEIGENDE Sicht innerhalb Gruen (3000 -> 20000 m) meldet nichts."""
    uid = _uid("sicht-rot")
    trip = _trip("trip-sicht-rot", alarm_ab={"visibility": "orange"}, metrics=("visibility",))
    mails = _trip_lauf(uid, trip, {"visibility_min_m": 800.0}, {"visibility_min_m": 400.0})
    assert mails and "von orange auf rot gestiegen" in mails[-1][1], mails
    assert _alarm_eintraege(uid)[-1]["severity"] == "HIGH"

    uid2 = _uid("sicht-gut")
    trip2 = _trip("trip-sicht-gut", alarm_ab={"visibility": "orange"}, metrics=("visibility",))
    assert _trip_lauf(uid2, trip2, {"visibility_min_m": 3000.0},
                      {"visibility_min_m": 20000.0}) == []
    assert _alarm_eintraege(uid2) == []


# ═══════ F102 — Melde-Gedaechtnis im Orts-Vergleich und fuer Entwarnungen ════

class _Vergleich:
    """Ein Orts-Vergleich mit fest gespeichertem Anker; jeder ``lauf`` ist ein
    echter Alarm-Lauf ueber ``check_all_compare_presets`` (State bleibt
    zwischen den Laeufen erhalten, wie im Betrieb)."""

    PRESET = "cp-2793-qg"

    def __init__(self, uid: str, alarm_ab: dict[str, str], anker: dict) -> None:
        from services.compare_weather_snapshot import CompareWeatherSnapshotService

        self.uid = uid
        clean_compare_user(uid)
        save_location(
            SavedLocation(id="loc-a", name="Vergleichsort", lat=LAT, lon=LON, elevation_m=1000),
            user_id=uid,
        )
        write_compare_briefings(compare_data_root() / uid, [{
            "id": self.PRESET, "name": "Vergleich Gedaechtnis", "user_id": uid,
            "location_ids": ["loc-a"], "schedule": "daily", "weekday": 4,
            "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
            "empfaenger": ["dummy@example.com"], "created_at": "2026-08-01T00:00:00Z",
            "alert_cooldown_minutes": 0,
            "display_config": {"active_metrics": list(anker), "ampel": _ampel(alarm_ab)},
        }])
        _profil(uid)
        CompareWeatherSnapshotService(user_id=uid).save(
            self.PRESET, "loc-a", _Quelle(**anker).fetch("loc-a", LAT, LON),
        )

    def lauf(self, neu: dict) -> list[tuple[str, str]]:
        from services.compare_alert import CompareAlertService

        mails: list[tuple[str, str]] = []
        CompareAlertService(
            settings=settings_email_only(), user_id=self.uid, weather_source=_Quelle(**neu),
            mail_sink=lambda subject, body, **_kw: mails.append((subject, body)),
        ).check_all_compare_presets()
        return mails


def test_f102_vergleich_drei_laeufe_wiederholung_stumm_neue_stufe_meldet():
    """AC-20 im Orts-Vergleich: GIVEN Boeen „Alarm ab Orange", Anker 40 (gelb),
    Lauf 1 mit 55 meldet „von gelb auf orange" / WHEN Lauf 2 wieder 55 und
    Lauf 3 57 liefert / THEN stumm; Lauf 4 mit 78 (rot) meldet „von orange
    auf rot gestiegen" (Bezug = zuletzt gemeldet, nicht der Anker)."""
    uid = _uid("cmp-ac20")
    try:
        v = _Vergleich(uid, {"gust": "orange"}, {"gust_max_kmh": 40.0})
        erst = v.lauf({"gust_max_kmh": 55.0})
        assert erst and "von gelb auf orange gestiegen" in erst[-1][1], erst
        assert v.lauf({"gust_max_kmh": 55.0}) == [], "Vergleich: Wiederholung gemeldet."
        assert v.lauf({"gust_max_kmh": 57.0}) == [], "Vergleich: Sprung 2 gemeldet."
        dritt = v.lauf({"gust_max_kmh": 78.0})
        assert dritt, "Vergleich: orange -> rot ist ein neuer Stufenwechsel."
        assert "von orange auf rot gestiegen" in dritt[-1][1], dritt[-1][1]
    finally:
        clean_compare_user(uid)


def test_f102_vergleich_dieselbe_entwarnung_kommt_nicht_erneut():
    """§2 Dedup, Entwarnung im Orts-Vergleich: GIVEN Anker 55 (orange), Lauf 1
    mit 35 entwarnt / WHEN Lauf 2 wieder 35 liefert / THEN keine zweite
    Entwarnung."""
    uid = _uid("cmp-ew")
    try:
        v = _Vergleich(uid, {"gust": "orange"}, {"gust_max_kmh": 55.0})
        erst = v.lauf({"gust_max_kmh": 35.0})
        assert erst and "von orange auf gelb zurückgegangen" in erst[-1][1], erst
        assert v.lauf({"gust_max_kmh": 35.0}) == [], "Vergleich: Entwarnung wiederholt."
    finally:
        clean_compare_user(uid)


def test_f102_trip_dieselbe_entwarnung_kommt_nicht_erneut():
    """§2 Dedup, Entwarnung im Trip: GIVEN Anker 55 (orange), Lauf 1 mit 35
    entwarnt / WHEN Lauf 2 wieder 35 liefert / THEN keine zweite Entwarnung,
    genau ein Alarm-Eintrag im Protokoll."""
    uid = _uid("trip-ew")
    trip = _trip("trip-ew", alarm_ab={"gust": "orange"}, metrics=("gust",))
    anker = {"gust_max_kmh": 55.0}
    erst = _trip_lauf(uid, trip, anker, {"gust_max_kmh": 35.0})
    assert erst and "von orange auf gelb zurückgegangen" in erst[-1][1], erst
    assert _trip_lauf(uid, trip, anker, {"gust_max_kmh": 35.0}) == []
    assert len(_alarm_eintraege(uid)) == 1, _alarm_eintraege(uid)


# ═══════ F103 — Sprung genau an der Schwelle, zuletzt gemeldet 0,0 °C ════════

def test_f103_sprung_genau_gleich_der_schwelle_alarmiert():
    """§2 Sprung ``>=``: GIVEN Boeen „Alarm ab Orange", Anker 65 (rot) / WHEN
    die Prognose 85 liefert (Sprung genau 20 = Schwelle) / THEN Alarm „weiter
    rot, großer Sprung"."""
    uid = _uid("sprung-20")
    trip = _trip("trip-s20", alarm_ab={"gust": "orange"}, metrics=("gust",))
    mails = _trip_lauf(uid, trip, {"gust_max_kmh": 65.0}, {"gust_max_kmh": 85.0})
    assert mails, "Sprung genau gleich der Sprung-Schwelle muss alarmieren."
    assert "Böen weiter rot, großer Sprung" in mails[-1][1], mails[-1][1]


def test_f103_zuletzt_gemeldet_null_grad_ist_der_bezug():
    """§2 Bezug: GIVEN Temperatur „Alarm ab Orange", Tagestief-Anker -7 °C
    (orange), Lauf 1 mit 0,0 °C (gruen) entwarnt und merkt 0,0 / WHEN Lauf 2
    wieder 0,0 °C liefert / THEN keine zweite Entwarnung -- 0,0 ist ein
    gemeldeter Wert, kein „fehlt" (sonst gaelte wieder der Anker -7)."""
    uid = _uid("null-grad")
    trip = _trip("trip-0c", alarm_ab={"temperature": "orange"}, metrics=("temperature",))
    anker = {"temp_min_c": -7.0}
    erst = _trip_lauf(uid, trip, anker, {"temp_min_c": 0.0})
    assert erst and "von orange auf grün zurückgegangen" in erst[-1][1], erst
    assert _trip_lauf(uid, trip, anker, {"temp_min_c": 0.0}) == []
    assert len(_alarm_eintraege(uid)) == 1, _alarm_eintraege(uid)


# ═══════ F104 — Farbpaar-Zelle der Mail, D4 ohne Farbpaar in der SMS ═════════

def _zelle(html: str, inhalt: str) -> bool:
    """Steht ``inhalt`` als eigener Zelleninhalt (``>inhalt<``) im HTML?"""
    return re.search(r">\s*" + re.escape(inhalt) + r"\s*<", html) is not None


def test_f104_einzelereignis_mailtabelle_traegt_farbpaar_alt_nach_neu(rig):
    """AC-18: GIVEN Boeen gelb -> orange (40 -> 55) / WHEN die Mail zugestellt
    wird / THEN steht in der Tabelle die Zelle „gelb → orange" (alt -> neu),
    in Klartext UND HTML, und nirgends die vertauschte „orange → gelb"."""
    uid = _uid("mail-1")
    trip = _trip("trip-m1", alarm_ab={"gust": "orange"}, metrics=("gust",))
    trip.alert_channels = kanal_auswahl("email")
    texte = _rig_lauf(rig, uid, trip, {"gust_max_kmh": 40.0}, {"gust_max_kmh": 55.0})
    assert "email" in texte and "html" in texte, f"Mail nicht zugestellt: {rig!r}"
    assert "gelb → orange" in texte["email"], texte["email"]
    assert "orange → gelb" not in texte["email"], texte["email"]
    assert _zelle(texte["html"], "gelb → orange"), texte["html"]
    assert "orange → gelb" not in texte["html"], texte["html"]


def test_f104_gebuendelte_mailtabelle_traegt_farbpaare_alt_nach_neu(rig):
    """AC-18 gebuendelt: GIVEN Boeen gelb -> orange und Niederschlag gruen ->
    rot in EINER Mail / THEN Zellen „gelb → orange" und „grün → rot" in
    Klartext und HTML, keine vertauschten Paare."""
    uid = _uid("mail-2")
    trip = _trip("trip-m2", alarm_ab={"gust": "orange", "precipitation": "orange"},
                 metrics=("gust", "precipitation"))
    trip.alert_channels = kanal_auswahl("email")
    texte = _rig_lauf(rig, uid, trip, {"gust_max_kmh": 40.0, "precip_sum_mm": 0.0},
                      {"gust_max_kmh": 55.0, "precip_sum_mm": 12.0})
    assert "email" in texte and "html" in texte, f"Mail nicht zugestellt: {rig!r}"
    for richtig, falsch in (("gelb → orange", "orange → gelb"), ("grün → rot", "rot → grün")):
        assert richtig in texte["email"], texte["email"]
        assert falsch not in texte["email"], texte["email"]
        assert _zelle(texte["html"], richtig), texte["html"]
        assert falsch not in texte["html"], texte["html"]


def test_f104_nullgradgrenze_sms_traegt_kein_farbpaar(rig):
    """AC-12 / §4: GIVEN Nullgradgrenze „standard" (Δ 400 m) / WHEN sie von
    3000 auf 2550 m faellt / THEN geht eine SMS hinaus, und sie traegt KEIN
    Farbpaar ``:X>Y`` (D4 bleibt wie vor S2)."""
    uid = _uid("d4-sms")
    trip = _trip("trip-d4s", metrics=("freezing_level",), levels={"freezing_level": "standard"})
    trip.alert_channels = kanal_auswahl("sms")
    texte = _rig_lauf(rig, uid, trip, {"freezing_level_m": 3000}, {"freezing_level_m": 2550})
    assert "sms" in texte, f"Nullgradgrenzen-SMS nicht zugestellt: {rig!r}"
    assert "FZ3000->2550" in texte["sms"], texte["sms"]
    assert not _FARBPAAR.search(texte["sms"]), f"D4-SMS mit Farbpaar: {texte['sms']!r}"


# ═══════ F105 — gemischte Meldung: hoechste Dringlichkeit, Kanal-Schwelle ════

def test_f105_gelb_und_orange_gemischt_zaehlt_orange_fuer_die_kanaele(rig):
    """§3 / AC-9 Mischfall: GIVEN Boeen „Alarm ab Gelb" 20 -> 35 (gruen ->
    gelb, gering) und Niederschlag „Alarm ab Orange" 2 -> 6 (gelb -> orange,
    mittel), Kanal-Schwelle E-Mail „mittel", SMS „hoch" / WHEN beide in einem
    Lauf ausloesen / THEN Dringlichkeit MODERATE (die hoechste), die E-Mail
    traegt beide Ereignisse, die SMS wird nicht versucht und steht mit
    ``below_channel_threshold`` im Protokoll."""
    uid = _uid("misch")
    trip = _trip("trip-misch", alarm_ab={"gust": "yellow", "precipitation": "orange"},
                 metrics=("gust", "precipitation"))
    trip.alert_channels = kanal_auswahl("email", "sms")
    trip.alert_channel_thresholds = {"email": "MODERATE", "sms": "HIGH"}
    texte = _rig_lauf(rig, uid, trip, {"gust_max_kmh": 20.0, "precip_sum_mm": 2.0},
                      {"gust_max_kmh": 35.0, "precip_sum_mm": 6.0})
    assert rig.anzahl_angenommen("email") == 1, rig
    assert rig.anzahl_versuche("sms") == 0, rig
    assert "von grün auf gelb gestiegen" in texte["email"], texte["email"]
    assert "von gelb auf orange gestiegen" in texte["email"], texte["email"]
    eintrag = _alarm_eintraege(uid)[-1]
    assert eintrag["severity"] == "MODERATE", eintrag
    assert reason_for_channel(eintrag, "sms") == "below_channel_threshold", eintrag
    assert reason_for_channel(eintrag, "email") is None, eintrag


# ═══════ F201 — Sicht, UV, Gewitter haben KEINEN Sprung-Zweig (§1-Tabelle) ════
#
# Je Quelle: gleiche Farbe im Alarmbereich, der Wert verschlechtert sich
# stark -> kein Alarm. Daneben je eine Kontrolle mit demselben Aufbau, die
# alarmiert (Farbwechsel in den Alarmbereich) -- sonst bewiese der stumme
# Lauf nur einen Aufbaufehler. Werte Vorlage „Allgemein": Sicht rot < 500 m,
# UV rot ab 8; Vorlage „Wassersport": Gewitter mittel = rot, hoch = rot.

_OHNE_SPRUNG = [
    # catalog_id, Vorlage, alarm_ab, Feld, Anker, Neuwert (gleiche Farbe, viel
    # schlechter), Kontroll-Anker (Farbe darunter)
    ("visibility", "allgemein", "orange", "visibility_min_m", 400.0, 150.0, 800.0),
    ("uv_index", "allgemein", "orange", "uv_index_max", 8.5, 11.0, 7.0),
    ("thunder", "wassersport", "red", "thunder_level_max",
     ThunderLevel.MED, ThunderLevel.HIGH, ThunderLevel.NONE),
]

# Gewitter ist eine Stufen-Groesse (Seite „stufe"): ein Sprung-Zweig rechnete
# dort „schlechter" als Anker minus Neuwert, er schlaege also beim RUECKGANG
# hoch -> mittel an (beides rot in Wassersport, Stufen-Abstand 1). Die Spec
# verlangt dort Stille (kein Sprung-Zweig, D2: Rueckgang im Alarmbereich).
_GEWITTER_RUECKGANG = ("thunder", "wassersport", "red", "thunder_level_max",
                       ThunderLevel.HIGH, ThunderLevel.MED, ThunderLevel.NONE)


def _trip_vorlage(trip_id: str, cid: str, vorlage: str, alarm_ab: str):
    trip = _trip(trip_id, alarm_ab={cid: alarm_ab}, metrics=(cid,))
    trip.display_config.ampel = _ampel({cid: alarm_ab}, template=vorlage)
    return trip


@pytest.mark.parametrize("cid,vorlage,ab,feld,anker,neu,kontrolle", _OHNE_SPRUNG,
                         ids=[q[0] for q in _OHNE_SPRUNG])
def test_f201_gleiche_farbe_starke_verschlechterung_ohne_sprung_zweig_stumm(
        cid, vorlage, ab, feld, anker, neu, kontrolle):
    """§1-Tabelle „kein Sprung-Zweig": GIVEN {cid} „Alarm ab {ab}" in Vorlage
    {vorlage}, Anker rot / WHEN der Wert innerhalb Rot stark schlechter wird
    (Sicht 400 -> 150 m, UV 8,5 -> 11, Gewitter mittel -> hoch) / THEN kein
    Alarm und kein Protokoll-Eintrag. Kontrolle: derselbe Aufbau mit Anker
    unter Rot meldet „auf rot gestiegen"."""
    uid = _uid(f"ns-{cid}")
    trip = _trip_vorlage(f"trip-ns-{cid}", cid, vorlage, ab)
    mails = _trip_lauf(uid, trip, {feld: anker}, {feld: neu})
    assert mails == [], f"{cid}: ohne Sprung-Zweig darf rot -> rot nie melden: {mails}"
    assert _alarm_eintraege(uid) == [], _alarm_eintraege(uid)

    uid_k = _uid(f"ns-k-{cid}")
    trip_k = _trip_vorlage(f"trip-ns-k-{cid}", cid, vorlage, ab)
    kontroll = _trip_lauf(uid_k, trip_k, {feld: kontrolle}, {feld: neu})
    assert kontroll and "auf rot gestiegen" in kontroll[-1][1], (cid, kontroll)


def test_f201_gewitter_hoch_auf_mittel_in_wassersport_bleibt_stumm():
    """§1 „kein Sprung-Zweig" + §2 D2 fuer Gewitter: GIVEN Gewitter „Alarm ab
    Rot" in Vorlage Wassersport (mittel = rot, hoch = rot) / WHEN die Stufe
    von „hoch" auf „mittel" zurueckgeht (weiter rot, eine Stufe) / THEN
    weder Alarm („weiter rot, großer Sprung") noch Entwarnung. Kontrolle:
    „keins" -> „mittel" meldet „von grün auf rot gestiegen"."""
    cid, vorlage, ab, feld, anker, neu, kontrolle = _GEWITTER_RUECKGANG
    uid = _uid("ns-th-zurueck")
    trip = _trip_vorlage("trip-ns-th-zurueck", cid, vorlage, ab)
    mails = _trip_lauf(uid, trip, {feld: anker}, {feld: neu})
    assert mails == [], f"Gewitter hoch -> mittel (rot -> rot) darf nie melden: {mails}"
    assert _alarm_eintraege(uid) == [], _alarm_eintraege(uid)

    uid_k = _uid("ns-th-zurueck-k")
    trip_k = _trip_vorlage("trip-ns-th-zurueck-k", cid, vorlage, ab)
    kontroll = _trip_lauf(uid_k, trip_k, {feld: kontrolle}, {feld: neu})
    assert kontroll and "von grün auf rot gestiegen" in kontroll[-1][1], kontroll


# ═══════ F204 — Reihenfolge gleichzeitiger Entwarnungen (verlassene Farbe) ════
#
# Spec §3 legt die Dringlichkeit einer Entwarnung auf die VERLASSENE Farbe;
# eine Regel fuer die Reihenfolge mehrerer Entwarnungen nennt die Spec nicht.
# Gesichert wird das bestehende Verhalten (``model.severity``: Entwarnung nach
# ``stufe_von``, absteigend): die gewichtigere Entwarnung steht zuerst.
# Die Kopfzeile kuerzt den Niederschlag heute auf „Niedersch" (bestehendes
# Kurzlabel der Mail, nicht S2).

@pytest.mark.parametrize("alt,neu,zuerst,danach", [
    # Niederschlag rot -> gruen, Boeen orange -> gelb: Niederschlag zuerst
    # (gegen die Feld-Reihenfolge, Boeen werden zuerst geprueft).
    ({"gust_max_kmh": 50.0, "precip_sum_mm": 12.0}, {"gust_max_kmh": 35.0, "precip_sum_mm": 0.0},
     "Entwarnung Niedersch: von rot auf grün", "Entwarnung Böen: von orange auf gelb"),
    # Boeen rot -> gruen, Niederschlag orange -> gelb: Boeen zuerst.
    ({"gust_max_kmh": 65.0, "precip_sum_mm": 6.0}, {"gust_max_kmh": 20.0, "precip_sum_mm": 2.0},
     "Entwarnung Böen: von rot auf grün", "Entwarnung Niedersch: von orange auf gelb"),
], ids=["niederschlag-rot-zuerst", "boeen-rot-zuerst"])
def test_f204_entwarnungen_geordnet_nach_verlassener_farbe(alt, neu, zuerst, danach):
    """§3/D3: GIVEN Boeen und Niederschlag „Alarm ab Orange" / WHEN beide in
    EINEM Lauf entwarnen, eine von Rot, eine von Orange / THEN steht in der
    zugestellten Mail die Entwarnung von Rot vor der von Orange -- geordnet
    nach der verlassenen Farbe, nicht nach der neuen (gruen < gelb)."""
    uid = _uid("ew-ord")
    trip = _trip("trip-ew-ord", alarm_ab={"gust": "orange", "precipitation": "orange"},
                 metrics=("gust", "precipitation"))
    mails = _trip_lauf(uid, trip, alt, neu)
    assert len(mails) == 1, mails
    text = mails[-1][1]
    a, b = text.find(zuerst), text.find(danach)
    assert a >= 0 and b >= 0, text
    assert a < b, f"Reihenfolge falsch ({zuerst!r} zuerst erwartet): {text!r}"


def _engine_lauf(trip, alt: float, neu: float, alert_state: dict):
    """Ein Lauf der geteilten Engine mit der Konfiguration, die der Trip-
    Einstieg baut (Abo-Ampel ueber ``resolve_ampel``)."""
    from app.ampel import resolve_ampel
    from app.models import SegmentWeatherSummary
    from services.deviation_alert_engine import DeviationAlertEngine
    from services.point_weather import AlertEvaluationConfig, PointWeatherData

    def punkt(wert: float) -> PointWeatherData:
        return PointWeatherData(
            id="1", name="Etappe", lat=LAT, lon=LON, timeseries=None,
            aggregated=SegmentWeatherSummary(gust_max_kmh=wert),
            fetched_at=datetime.now(timezone.utc), provider="tdd-2793-qg",
        )

    config = AlertEvaluationConfig(
        channels={"email"}, display_config=trip.display_config, ampel=resolve_ampel(trip),
    )
    return DeviationAlertEngine().evaluate(
        cached=[punkt(alt)], fresh=[punkt(neu)], config=config, alert_state=alert_state,
    )


def test_f105_unterdrueckungsgrund_gedaechtnis_gegen_keine_aenderung():
    """§2 Dedup / Protokollgrund: GIVEN Boeen „Alarm ab Orange", Anker 40 /
    WHEN 55 schon gemeldet ist (Gedaechtnis 55) und wieder 55 kommt / THEN
    unterdrueckt die Engine mit ``alert_state_dedup``; ohne jede Aenderung
    gegen den Anker (40 -> 40) mit ``no_significant_changes``."""
    trip = _trip("trip-grund", alarm_ab={"gust": "orange"}, metrics=("gust",))
    gemerkt = {"gust_max_kmh:1": {"last_reported_value": 55.0}}
    dedup = _engine_lauf(trip, 40.0, 55.0, gemerkt)
    assert not dedup.triggered and dedup.suppressed_reason == "alert_state_dedup", dedup
    still = _engine_lauf(trip, 40.0, 40.0, {})
    assert not still.triggered and still.suppressed_reason == "no_significant_changes", still
    kontrolle = _engine_lauf(trip, 40.0, 55.0, {})
    assert kontrolle.triggered and kontrolle.severity == "MODERATE", kontrolle
