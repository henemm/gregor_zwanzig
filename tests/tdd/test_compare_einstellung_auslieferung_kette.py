"""Kette Ortsvergleich: Preset-JSON bis zum gesendeten Text je Kanal
(Issue #2422, Scheibe S5, Bloecke A, B, C, E-Python, F, G).

SPEC: docs/specs/modules/fix_2422_s5_ortsvergleich_kette.md (AC-1..AC-13,
AC-24, AC-27..AC-30). Block D (Alarme) steht in
``test_compare_alarm_einstellung_auslieferung_kette.py``, der Go-Teil
(AC-23/25/26) in ``internal/handler/compare_preset_kette_test.go``.

Einstieg wie im Betrieb: das Preset liegt als ROHES JSON der Fixture-Datei
(``tests/fixtures/compare_kette/*.json``, Persistenzformat des Editors) im
Nutzerverzeichnis, wird vom ECHTEN ``load_compare_presets`` gelesen und ueber
``send_one_compare_preset`` versendet. Messpunkt: die Kanal-Ausgaenge, ersetzt
durch den geteilten Aufzeichner (``tests/helpers/transport_mitschrift.py``,
zusaetzlich auf ``output.channels.email.EmailOutput``, weil ``send_compare_
report`` die Mail-Klasse erst beim Aufruf importiert). Kein ``Mock()``/
``patch()``, keine ``*_sink``-Parameter (ein Sink umgeht den Aufzeichner).

Erwartungen kommen aus dem rohen JSON der Datei auf der Platte und dem
statischen Register im Orakel (``tests/helpers/einstellung_auslieferung_
orakel.py``), NIE aus ``resolve_channel_enabled_metrics``/``effective_compare_
briefing_channels`` (Spiegel-Test). Jeder datenbewegende Test laeuft mit ZWEI
Nutzern (eigene Kennung, eigenes Verzeichnis, eigene Empfaenger); jeder Test
ruft die Vorbedingung VOR seinen Zusicherungen (null Sendungen sind nie gruen).

RED heute: AC-28 (Telegram-Kurzstil erreicht das Briefing nicht), AC-27
(api_contract.md behauptet noch KL-7). Alles uebrige sichert den Ist-Stand.
"""
from __future__ import annotations

import copy
import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.loader import load_compare_presets, save_location
from app.user import SavedLocation
from services.compare_slot_scheduler import presets_due_for_hour
from tests.helpers.einstellung_auslieferung_orakel import (
    COMPARE_KANAELE,
    compare_erreichbare_kanaele,
    compare_erwartete_metriken,
    compare_parse_email_plain,
    compare_parse_sms,
    compare_parse_telegram,
    compare_telegram_erwartung,
    compare_vorbedingung_pruefen,
)
from tests.helpers.transport_mitschrift import Kanalmitschrift, aufzeichner_installieren
from tests.tdd._compare_kette_fixtures import (
    ORTSNAMEN,
    alle_orte,
    briefing_senden,
    engine_naht,
    fixture_dict,
    nutzer_anlegen,
    orte_anlegen,
    preset_ablegen,
    preset_laden,
    settings_fuer,
    sms_tageslimit_erschoepfen,
    transport_einrichten,
)

WIEN = ZoneInfo("Europe/Vienna")
ALLE_MIT_TEXT = ("email", "telegram", "sms", "premium_sms")


# ---------------------------------------------------------------------------
# Aufbau
# ---------------------------------------------------------------------------


@pytest.fixture
def mit(monkeypatch) -> Kanalmitschrift:
    """Aufzeichner an allen Ausgaengen (inkl. Laufzeit-Import der Vergleichs-
    Mail) + Wetter-Naht; Transportfelder unbrauchbar aber vollstaendig belegt."""
    transport_einrichten(monkeypatch)
    engine_naht(monkeypatch)
    return aufzeichner_installieren(monkeypatch)


@dataclass
class Lauf:
    uid: str
    roh: dict          # JSON, wie es auf der Platte liegt (json.load der Datei)
    snap: Kanalmitschrift
    ergebnis: tuple


def _optins(p: dict) -> dict:
    """Alle drei Kanal-Schalter an; ``alert_channels`` vorhanden (sonst gilt
    Premium-SMS als Alarm-Absicht des Altbestands, AC-9)."""
    p["send_telegram"] = p["send_sms"] = p["send_premium_sms"] = True
    p.setdefault("alert_channels", {"email": True, "telegram": False, "sms": False, "premium_sms": False})
    return p


def _lauf(mit, vorlage: dict, tier: str = "premium", *, optins: bool = True,
          telegram: bool = True, sms: bool = True, vorher=None) -> Lauf:
    """EIN Nutzer, EIN Briefing-Lauf ueber den echten Einstieg. ``vorher(uid)``
    darf den Nutzer praeparieren (z.B. Tageszaehler)."""
    uid = nutzer_anlegen(tier)
    orte_anlegen(uid)
    p = _optins(copy.deepcopy(vorlage)) if optins else copy.deepcopy(vorlage)
    pfad = preset_ablegen(uid, p)
    if vorher:
        vorher(uid)
    mit.leeren()
    ergebnis = briefing_senden(uid, p["id"], settings_fuer(uid, telegram=telegram, sms=sms))
    snap = copy.deepcopy(mit)
    mit.leeren()
    return Lauf(uid, json.loads(pfad.read_text(encoding="utf-8")), snap, ergebnis)


def _text(snap: Kanalmitschrift, kanal: str) -> str:
    s = snap.sendungen(kanal)[-1]
    return (s.get("plain_text_body") or s.get("body")) if kanal == "email" else s["body"]


def _ist(snap: Kanalmitschrift, kanal: str) -> dict[str, list[str]]:
    """Geparste Zellen je Ort fuer einen Kanal (Telegram ohne Hinweis)."""
    if kanal == "email":
        return compare_parse_email_plain(_text(snap, "email"), ORTSNAMEN)
    if kanal == "telegram":
        return compare_parse_telegram(_text(snap, "telegram"), ORTSNAMEN)[0]
    return compare_parse_sms(_text(snap, kanal), ORTSNAMEN)


def _inhalt_pruefen(lauf: Lauf, kanaele=ALLE_MIT_TEXT, *, email: bool = True) -> None:
    """Vorbedingung, dann je Kanal: erwartete Metrik-Menge (und ausser E-Mail die
    Reihenfolge) je Ort aus rohem JSON + Register."""
    compare_vorbedingung_pruefen(lauf.snap, tuple(kanaele))
    for kanal in kanaele:
        if kanal == "email" and not email:
            continue
        erwartet = compare_erwartete_metriken(lauf.roh, kanal)
        ist = _ist(lauf.snap, kanal)
        for ort in ORTSNAMEN:
            if erwartet is None:
                assert ist.get(ort), f"{kanal}/{ort}: ohne Filter muss der Standardsatz Werte zeigen"
                continue
            if kanal == "telegram":
                soll = compare_telegram_erwartung(erwartet)[0]
            else:
                soll = erwartet
            if kanal == "email":
                assert sorted(ist.get(ort, [])) == sorted(soll), (
                    f"E-Mail/{ort}: erwartet {sorted(soll)}, gesendet {ist.get(ort)} "
                    f"(Nutzer {lauf.uid}, Preset {lauf.roh['id']})"
                )
            else:
                assert ist.get(ort) == soll, (
                    f"{kanal}/{ort}: erwartet {soll} (Reihenfolge der Kanal-Liste), gesendet "
                    f"{ist.get(ort)} (Nutzer {lauf.uid}, Preset {lauf.roh['id']})\n{_text(lauf.snap, kanal)}"
                )


def _zwei_nutzer(mit, vorlage: dict, **kw) -> tuple[Lauf, Lauf]:
    """Derselbe Preset-Inhalt bei zwei Nutzern verschiedener Tarife/Kennungen:
    jeder bekommt seinen eigenen Versand an seine eigenen Empfaenger."""
    a = _lauf(mit, vorlage, "premium", **kw)
    b = _lauf(mit, vorlage, "premium", **kw)
    assert a.uid != b.uid
    for lauf in (a, b):
        assert lauf.snap.empfaenger("email") == [f"{lauf.uid}@example.invalid"]
        assert lauf.snap.empfaenger("telegram") == [f"chat-{lauf.uid}"]
    return a, b


# ---------------------------------------------------------------------------
# Block A -- channel_active_metrics je Kanal
# ---------------------------------------------------------------------------


def test_kanal_darf_grundauswahl_nur_abwaehlen(mit):
    """AC-1: SMS = Schnitt aus Grundauswahl und SMS-Eintrag (ohne Wind), Telegram
    zeigt die fremde Groesse (Schneehoehe) nicht, E-Mail zeigt die volle Grundauswahl."""
    for lauf in _zwei_nutzer(mit, fixture_dict("kanal_auswahl")):
        compare_vorbedingung_pruefen(lauf.snap, ALLE_MIT_TEXT)
        assert compare_erwartete_metriken(lauf.roh, "sms") == [
            "temp_max_c", "gust_max_kmh", "cloud_avg_pct", "sunny_hours_h"]
        assert compare_erwartete_metriken(lauf.roh, "telegram") == ["temp_max_c", "wind_max_kmh"]
        _inhalt_pruefen(lauf)
        assert "snow_depth_cm" not in _ist(lauf.snap, "telegram")["Innsbruck"]
        assert "wind_max_kmh" not in _ist(lauf.snap, "sms")["Innsbruck"]
        assert sorted(_ist(lauf.snap, "email")["Innsbruck"]) == sorted(
            ["temp_max_c", "wind_max_kmh", "gust_max_kmh", "cloud_avg_pct", "sunny_hours_h"])


def test_fehlender_kanal_eintrag_folgt_der_grundauswahl(mit):
    """AC-2: ohne channel_active_metrics / ohne Schluessel ``sms`` zeigt der Kanal die
    Grundauswahl, identisch zu einem expliziten Eintrag mit derselben Grundauswahl;
    fehlt active_metrics ganz, wird nicht geschnitten."""
    basis = fixture_dict("basis")
    explizit = copy.deepcopy(basis)
    explizit["display_config"]["channel_active_metrics"] = {
        k: copy.deepcopy(basis["display_config"]["active_metrics"]) for k in ("email", "telegram", "sms")
    }
    ohne_sms = fixture_dict("kanal_auswahl")
    ohne_sms["display_config"]["channel_active_metrics"].pop("sms")
    ohne_sms["display_config"]["channel_active_metrics"]["telegram"] = copy.deepcopy(
        ohne_sms["display_config"]["active_metrics"])

    for a, b in zip(_zwei_nutzer(mit, basis), _zwei_nutzer(mit, explizit)):
        _inhalt_pruefen(a)
        _inhalt_pruefen(b)
        for kanal in ("telegram", "sms", "premium_sms"):
            assert _text(a.snap, kanal) == _text(b.snap, kanal), f"{kanal}: fehlender Eintrag != expliziter Eintrag"
        assert _ist(a.snap, "email") == _ist(b.snap, "email")

    for lauf in _zwei_nutzer(mit, ohne_sms):
        _inhalt_pruefen(lauf)
        assert _ist(lauf.snap, "sms")["Innsbruck"] == [
            "temp_max_c", "wind_max_kmh", "gust_max_kmh", "cloud_avg_pct", "sunny_hours_h"]

    ohne_grundauswahl = fixture_dict("basis")
    ohne_grundauswahl["display_config"].pop("active_metrics")
    ohne_grundauswahl["display_config"]["channel_active_metrics"] = {
        "sms": [{"metric_id": "wind", "aggregation": "max"}]}
    for lauf in _zwei_nutzer(mit, ohne_grundauswahl):
        assert lauf.ergebnis[0] is not None
        _inhalt_pruefen(lauf)  # SMS: genau Wind (kein Maximum -> nicht geschnitten); E-Mail/Telegram: Standardsatz


def test_leere_auswahl_bleibt_leer_und_faellt_nicht_auf_grundauswahl_zurueck(mit):
    """AC-3: (a) ``sms = []`` -> keine SMS-Zelle, E-Mail/Telegram die Grundauswahl;
    (b) ``active_metrics = []`` -> alle drei Kanaele ohne Zelle. Die Sendung kommt zustande."""
    a = fixture_dict("basis")
    a["display_config"]["channel_active_metrics"] = {"sms": []}
    for lauf in _zwei_nutzer(mit, a):
        _inhalt_pruefen(lauf)
        assert _ist(lauf.snap, "sms").get("Innsbruck") == []
        assert _ist(lauf.snap, "telegram")["Innsbruck"], "Telegram muss die Grundauswahl zeigen"
        assert _ist(lauf.snap, "email")["Innsbruck"], "E-Mail muss die Grundauswahl zeigen"

    b = fixture_dict("basis")
    b["display_config"]["active_metrics"] = []
    b["display_config"]["channel_active_metrics"] = {
        "email": copy.deepcopy(a["display_config"]["active_metrics"]),
        "telegram": copy.deepcopy(a["display_config"]["active_metrics"]),
        "sms": copy.deepcopy(a["display_config"]["active_metrics"]),
    }
    for lauf in _zwei_nutzer(mit, b):
        compare_vorbedingung_pruefen(lauf.snap, ALLE_MIT_TEXT)
        for kanal in ("email", "telegram", "sms"):
            assert not any(_ist(lauf.snap, kanal).values()), (
                f"{kanal}: leere Grundauswahl darf keine Zelle zeigen, war {_ist(lauf.snap, kanal)}")


def test_reihenfolge_der_kanal_liste_bestimmt_zellen_und_kappung(mit):
    """AC-4: Zellen in der Reihenfolge der Kanal-Liste (nicht der Grundauswahl); bei
    Ueberschreitung der Telegram-Grenze (7 je Ort) entfallen die HINTEREN Groessen und
    der Hinweis nennt die Zahl der Verdraengten."""
    for lauf in _zwei_nutzer(mit, fixture_dict("kanal_reihenfolge")):
        _inhalt_pruefen(lauf)
        assert _ist(lauf.snap, "telegram")["Innsbruck"] == [
            "sunny_hours_h", "cloud_avg_pct", "gust_max_kmh", "wind_max_kmh", "temp_max_c"]
        assert _ist(lauf.snap, "sms")["Innsbruck"] == ["gust_max_kmh", "temp_max_c", "sunny_hours_h"]

    for lauf in _zwei_nutzer(mit, fixture_dict("kanal_ueberlauf")):
        _inhalt_pruefen(lauf, ("telegram",))
        zellen, verdraengt = compare_telegram_erwartung(compare_erwartete_metriken(lauf.roh, "telegram"))
        assert len(zellen) == 7 and verdraengt == 3
        ist, hinweis = compare_parse_telegram(_text(lauf.snap, "telegram"), ORTSNAMEN)
        for ort in ORTSNAMEN:
            assert ist[ort] == zellen, f"Telegram/{ort}: die vorderen sieben der Kanal-Liste muessen bleiben"
        assert hinweis == verdraengt, f"Telegram muss die {verdraengt} verdraengten Groessen ausweisen"
        compare_vorbedingung_pruefen(lauf.snap, ("email", "sms"))
        assert set(_ist(lauf.snap, "sms").get("Innsbruck", [])), "SMS zeigt die Grundauswahl (kein Kanal-Eintrag)"


def test_kanalauswahl_aendert_den_stundenverlauf_nicht(mit):
    """AC-5: E-Mail-Auswahl ohne Wind -> Wind fehlt in der Uebersicht, steht aber im
    Stundenverlauf (folgt allein ``hourly_metrics``)."""
    for lauf in _zwei_nutzer(mit, fixture_dict("stundenverlauf")):
        _inhalt_pruefen(lauf, ("email",))
        assert "wind_max_kmh" not in _ist(lauf.snap, "email")["Innsbruck"]
        text = _text(lauf.snap, "email")
        assert "STUNDENVERLAUF" in text, "Stundenverlauf muss vorhanden sein (hourly_enabled an)"
        stunden = text.split("STUNDENVERLAUF", 1)[1]
        zeilen = [z for z in stunden.splitlines() if re.match(r"^\s+\d\d:00\s", z)]
        assert zeilen and all(re.search(r"Wind \d+", z) and re.search(r"Temp \d+", z) for z in zeilen), stunden[:400]
        assert not any("Gust" in z for z in zeilen), "Boeen stehen nicht in hourly_metrics"
        assert lauf.snap.sendungen("email")[-1]["compare_hourly_enabled"] is True


def test_premium_sms_text_ist_der_sms_text_und_ein_premium_eintrag_wirkt_nicht(mit):
    """AC-6: Premium-SMS-Text byte-identisch zum SMS-Text; ein Eintrag
    ``channel_active_metrics["premium_sms"]`` aendert weder Premium- noch SMS-Text."""
    ohne = fixture_dict("kanal_auswahl")
    mit_eintrag = copy.deepcopy(ohne)
    mit_eintrag["display_config"]["channel_active_metrics"]["premium_sms"] = [
        {"metric_id": "wind", "aggregation": "max"}]
    l_ohne = _zwei_nutzer(mit, ohne)
    l_mit = _zwei_nutzer(mit, mit_eintrag)
    for lauf in (*l_ohne, *l_mit):
        compare_vorbedingung_pruefen(lauf.snap, ("sms", "premium_sms"))
        assert _text(lauf.snap, "premium_sms") == _text(lauf.snap, "sms")
        assert lauf.snap.empfaenger("premium_sms") == ["+490000000008"]
    for a, b in zip(l_ohne, l_mit):
        assert _text(a.snap, "sms") == _text(b.snap, "sms")
        assert _text(a.snap, "premium_sms") == _text(b.snap, "premium_sms")
        assert "wind_max_kmh" not in _ist(b.snap, "premium_sms")["Innsbruck"]


# ---------------------------------------------------------------------------
# Block B -- Kanal an/aus x Tarif
# ---------------------------------------------------------------------------

_OPTINS = [(tg, sm, pr) for tg in (False, True) for sm in (False, True) for pr in (False, True)]


@pytest.mark.parametrize("tier", ["free", "standard", "premium"])
@pytest.mark.parametrize("kann_tg,kann_sms", [(True, True), (False, True), (True, False), (False, False)])
@pytest.mark.parametrize("tg,sm,pr", _OPTINS)
def test_kanalmatrix_briefing_nach_optin_faehigkeit_und_tarif(mit, tier, kann_tg, kann_sms, tg, sm, pr):
    """AC-7: genau die Kanalmenge, die das Orakel aus rohem JSON, Tarif und
    Sendefaehigkeit ableitet. Ein zweiter Nutzer (Premium, alles an) bleibt unberuehrt."""
    vorlage = fixture_dict("basis")
    vorlage.update(send_telegram=tg, send_sms=sm, send_premium_sms=pr)
    if pr:
        vorlage["alert_channels"] = {"email": True, "telegram": False, "sms": False, "premium_sms": False}
    lauf = _lauf(mit, vorlage, tier, optins=False, telegram=kann_tg, sms=kann_sms)
    kontrolle = _lauf(mit, fixture_dict("basis"), "premium")  # mit allen Opt-ins
    erwartet = compare_erreichbare_kanaele(lauf.roh, tier, kann_telegram=kann_tg, kann_sms=kann_sms)
    compare_vorbedingung_pruefen(lauf.snap, erwartet)
    bedient = tuple(k for k in COMPARE_KANAELE if lauf.snap.sendungen(k))
    assert sorted(bedient) == sorted(erwartet), (
        f"Tarif {tier}, Telegram-faehig={kann_tg}, SMS-faehig={kann_sms}, Opt-ins tg/sms/pr={tg}/{sm}/{pr}: "
        f"erwartet {sorted(erwartet)}, bedient {sorted(bedient)}")
    compare_vorbedingung_pruefen(kontrolle.snap, ("email", "telegram", "sms", "premium_sms"))
    assert lauf.snap.empfaenger("email") == [f"{lauf.uid}@example.invalid"]
    assert kontrolle.snap.empfaenger("email") == [f"{kontrolle.uid}@example.invalid"]


def test_email_ist_immer_aktiv_auch_bei_allen_schaltern_aus(mit):
    """AC-8: alle ``send_*`` fehlen/falsch, Rohschluessel ``send_email: false`` -> E-Mail
    geht hinaus und ist der einzige Kanal."""
    fehlen = fixture_dict("basis")
    for k in ("send_telegram", "send_sms", "send_premium_sms"):
        fehlen.pop(k)
    falsch = fixture_dict("basis")
    falsch["send_email"] = False
    for vorlage in (fehlen, falsch):
        for tier in ("premium", "standard"):
            lauf = _lauf(mit, vorlage, tier, optins=False)
            compare_vorbedingung_pruefen(lauf.snap, ("email",))
            assert lauf.snap.kanaele == ["email"], f"nur E-Mail erwartet, bedient: {lauf.snap.kanaele}"
            assert lauf.snap.empfaenger("email") == [f"{lauf.uid}@example.invalid"]
    assert "send_email" not in fehlen


def test_premium_sms_ohne_alert_channels_ist_kein_briefing_kanal(mit):
    """AC-9: ``send_premium_sms`` ohne ``alert_channels`` (Altbestand = Alarm-Absicht) ->
    aus; mit ``alert_channels`` -> bedient (Premium-Tarif)."""
    ohne = fixture_dict("basis")
    ohne.update(send_premium_sms=True)
    assert "alert_channels" not in ohne
    mit_ac = copy.deepcopy(ohne)
    mit_ac["alert_channels"] = {"email": True, "telegram": False, "sms": False, "premium_sms": False}
    for vorlage, soll in ((ohne, False), (mit_ac, True)):
        for _ in range(2):
            lauf = _lauf(mit, vorlage, "premium", optins=False)
            compare_vorbedingung_pruefen(lauf.snap, ("email",) + (("premium_sms",) if soll else ()))
            assert bool(lauf.snap.sendungen("premium_sms")) is soll


def test_sms_tageslimit_sperrt_nur_den_betroffenen_nutzer_und_kanal(mit, caplog):
    """AC-10: Nutzer A hat das Tageslimit erschoepft -> keine SMS/Premium-SMS (Sperrgrund
    im Protokoll), E-Mail und Telegram gehen hinaus; Nutzer B wird auf allen Kanaelen bedient."""
    vorlage = fixture_dict("basis")
    with caplog.at_level(logging.WARNING):
        a = _lauf(mit, vorlage, "premium", vorher=sms_tageslimit_erschoepfen)
        b = _lauf(mit, vorlage, "premium")
    compare_vorbedingung_pruefen(a.snap, ("email", "telegram"))
    compare_vorbedingung_pruefen(b.snap, ALLE_MIT_TEXT)
    assert a.snap.sendungen("sms") == [] and a.snap.sendungen("premium_sms") == []
    assert a.snap.empfaenger("telegram") == [f"chat-{a.uid}"]
    gesperrt = [r.getMessage() for r in caplog.records if "sms_daily_limit_exceeded" in r.getMessage()]
    assert any("Kanal sms" in m for m in gesperrt) and any("Kanal premium_sms" in m for m in gesperrt), gesperrt


# ---------------------------------------------------------------------------
# Block C -- Slots morgen/abend
# ---------------------------------------------------------------------------


def _wien(tag: date, stunde: int) -> datetime:
    """Weltzeit-Zeitpunkt, an dem die Ortszeit in Wien ``stunde`` ist."""
    return datetime(tag.year, tag.month, tag.day, stunde, 0, tzinfo=WIEN).astimezone(timezone.utc)


def _faellig(uid: str, preset: dict, moment: datetime) -> list:
    orte = {o.id: o for o in alle_orte(uid)}
    return presets_due_for_hour([preset_laden(uid, preset["id"])], orte, moment)


def _nutzer_mit_preset(vorlage: dict, tier: str = "premium"):
    uid = nutzer_anlegen(tier)
    orte_anlegen(uid)
    pfad = preset_ablegen(uid, vorlage)
    return uid, json.loads(pfad.read_text(encoding="utf-8"))


def test_slots_morgen_abend_faelligkeit_zieltag_und_betreff_datum(mit):
    """AC-11: Morgen-Slot Versatz 0/Zieltag heute, Abend-Slot Versatz 1/Zieltag morgen;
    Betreff-Datum der Mail = Zieltag; abgeschaltete Slots liefern nichts."""
    heute = date(2026, 7, 8)
    uid_a, roh_a = _nutzer_mit_preset(fixture_dict("slots_morgen_abend"))
    aus = fixture_dict("slots_morgen_abend")
    aus.update(morning_enabled=False, evening_enabled=False)
    uid_b, roh_b = _nutzer_mit_preset(aus)
    assert roh_a["morning_time"] == "07:00:00" and roh_a["evening_time"] == "19:00:00"

    morgen_faellig = _faellig(uid_a, roh_a, _wien(heute, 7))
    abend_faellig = _faellig(uid_a, roh_a, _wien(heute, 19))
    assert [(d.tage_ab_ortstag, d.target_date) for d in morgen_faellig] == [(0, heute)]
    assert [(d.tage_ab_ortstag, d.target_date) for d in abend_faellig] == [(1, heute + timedelta(days=1))]
    assert _faellig(uid_a, roh_a, _wien(heute, 12)) == []
    # Nutzer B: beide Slots aus -> nie faellig, egal welche Stunde; A bleibt davon unberuehrt.
    assert all(_faellig(uid_b, roh_b, _wien(heute, h)) == [] for h in range(24))

    from services.scheduler_dispatch_service import send_one_compare_preset  # noqa: F401
    from app.loader import get_data_root
    for uid, faellig, erwartet_tag in (
        (uid_a, morgen_faellig[0], heute), (uid_a, abend_faellig[0], heute + timedelta(days=1)),
    ):
        mit.leeren()
        send_one_compare_preset(
            faellig.preset, settings_fuer(uid), uid, str(get_data_root()),
            all_locations_cache=alle_orte(uid),
            target_date=faellig.target_date, tage_ab_ortstag=faellig.tage_ab_ortstag,
        )
        compare_vorbedingung_pruefen(mit, ("email",))
        assert f"({erwartet_tag.strftime('%d.%m.%Y')})" in mit.sendungen("email")[-1]["subject"]
        assert mit.empfaenger("email") == [f"{uid}@example.invalid"]


def test_altbestand_ohne_slot_zeiten_faellt_auf_schedule_zurueck(mit):
    """AC-12: ohne ``morning_time``: ``schedule=daily_evening`` -> nur Abend (18:00),
    ``schedule=daily`` -> nur Morgen (06:00)."""
    heute = date(2026, 7, 8)
    abend = fixture_dict("altbestand_ohne_slot_zeiten")
    abend["schedule"] = "daily_evening"
    morgen = fixture_dict("altbestand_ohne_slot_zeiten")
    morgen["schedule"] = "daily"
    for vorlage in (abend, morgen):
        assert "morning_time" not in vorlage
    uid_a, roh_a = _nutzer_mit_preset(abend)
    uid_b, roh_b = _nutzer_mit_preset(morgen)
    assert "morning_time" not in roh_a and "morning_time" not in roh_b

    assert [(d.tage_ab_ortstag) for d in _faellig(uid_a, roh_a, _wien(heute, 18))] == [1]
    assert _faellig(uid_a, roh_a, _wien(heute, 6)) == []
    assert [(d.tage_ab_ortstag) for d in _faellig(uid_b, roh_b, _wien(heute, 6))] == [0]
    assert _faellig(uid_b, roh_b, _wien(heute, 18)) == []


def _preset_in_zone(uid: str, ort_id: str, lat: float, lon: float, morgens: str) -> dict:
    save_location(SavedLocation(id=ort_id, name=ort_id, lat=lat, lon=lon, elevation_m=10), user_id=uid)
    p = fixture_dict("slots_morgen_abend")
    p.update(location_ids=[ort_id], morning_time=morgens, evening_enabled=False)
    return json.loads(preset_ablegen(uid, p).read_text(encoding="utf-8"))


def test_slot_stunde_gilt_in_der_ortszeit_des_presets_je_nutzer():
    """AC-13: zwei Nutzer, Orte in verschiedenen Zeitzonen, derselbe Weltzeit-Zeitpunkt ->
    jedes Preset wird gegen die Ortszeit seines ersten Orts geprueft; keins beeinflusst das andere."""
    moment = datetime(2026, 7, 8, 5, 0, tzinfo=timezone.utc)   # Wien 07:00, Auckland 17:00
    uid_a, uid_b = nutzer_anlegen("premium"), nutzer_anlegen("premium")
    roh_a = _preset_in_zone(uid_a, "ort-wien", 48.21, 16.37, "07:00:00")
    roh_b = _preset_in_zone(uid_b, "ort-auckland", -36.85, 174.76, "17:00:00")
    roh_b_falsch = dict(roh_b, id="kette-slots-b2", morning_time="07:00:00")
    preset_ablegen(uid_b, roh_b_falsch)

    def faellig(uid, roh_id, ort_id):
        orte = {o.id: o for o in alle_orte_nur(uid)}
        return presets_due_for_hour([preset_laden(uid, roh_id)], orte, moment)

    def alle_orte_nur(uid):
        from app.loader import load_all_locations
        return load_all_locations(user_id=uid)

    assert len(faellig(uid_a, roh_a["id"], "ort-wien")) == 1, "Wien 07:00 = 05:00 UTC -> faellig"
    assert len(faellig(uid_b, roh_b["id"], "ort-auckland")) == 1, "Auckland 17:00 = 05:00 UTC -> faellig"
    assert faellig(uid_b, "kette-slots-b2", "ort-auckland") == [], "Auckland 07:00 ist um 05:00 UTC NICHT faellig"
    spaeter = datetime(2026, 7, 8, 6, 0, tzinfo=timezone.utc)
    orte_a = {o.id: o for o in alle_orte_nur(uid_a)}
    assert presets_due_for_hour([preset_laden(uid_a, roh_a["id"])], orte_a, spaeter) == []


# ---------------------------------------------------------------------------
# Block E (Python) -- end_date
# ---------------------------------------------------------------------------


def test_fehlendes_end_date_heisst_unbegrenzt_und_grenztag_ist_faellig():
    """AC-24: die von Go geschriebene Datei OHNE ``end_date`` -> geladener Wert ``None``
    (``is None``), Preset faellig; ``end_date`` von gestern (Ortstag) -> nicht faellig,
    von heute -> faellig. Zwei Nutzer.

    "Heute" ist der ECHTE Ortstag (Wien), nicht ein fester Kalendertag: die Stilllegungs-
    Regel aus AC-21 (``is_silenced``) kennt keinen Zeitparameter und misst gegen die
    Wanduhr -- ein fest verdrahteter Tag wuerde nach dem Fix rot."""
    heute = datetime.now(timezone.utc).astimezone(WIEN).date()
    moment = _wien(heute, 7)
    unbegrenzt = fixture_dict("slots_morgen_abend")
    assert "end_date" not in unbegrenzt
    gestern = dict(fixture_dict("slots_morgen_abend"), end_date=(heute - timedelta(days=1)).isoformat())
    grenztag = dict(fixture_dict("slots_morgen_abend"), end_date=heute.isoformat())

    for vorlage, soll in ((unbegrenzt, True), (gestern, False), (grenztag, True)):
        uids = []
        for _ in range(2):
            uid, roh = _nutzer_mit_preset(vorlage)
            geladen = [p for p in load_compare_presets(uid) if p.id == roh["id"]][0]
            if vorlage is unbegrenzt:
                assert geladen.end_date is None and "end_date" not in roh
            assert bool(_faellig(uid, roh, moment)) is soll, f"end_date={roh.get('end_date')!r}"
            uids.append(uid)
        assert uids[0] != uids[1]


def test_api_contract_beschreibt_end_date_sentinel():
    """AC-27: ``docs/reference/api_contract.md`` beschreibt den Loesch-Sentinel und behauptet
    KL-7 nicht mehr."""  # doc-compliance-test
    text = (Path(__file__).resolve().parents[2] / "docs" / "reference" / "api_contract.md").read_text(encoding="utf-8")
    zeilen = [z for z in text.splitlines() if '`json:"end_date,omitempty"`' in z and "unbegrenzte Laufzeit" in z]
    assert len(zeilen) == 1, "Vorbedingung: die ComparePreset-Zeile zu end_date muss auffindbar sein"
    assert "kann per PUT nicht auf nil zurückgesetzt werden" not in text
    assert "KL-7" not in zeilen[0]
    assert '""' in zeilen[0] and "400" in zeilen[0], (
        "die end_date-Zeile muss den Sentinel (`\"\"` loescht) und das 400 bei ungueltigem Datum nennen")
    assert '`end_date: ""` löscht das Enddatum' in zeilen[0], "Sentinel-Aussage: leerer String loescht"
    assert "compare_preset.go" in zeilen[0], "Verweis auf den Handler fehlt"
    assert "ungültiges Datum ergibt 400" in zeilen[0], "400 bei ungueltigem Datum fehlt"
    assert "fehlendes Feld erhält den gespeicherten Wert" in zeilen[0]


# ---------------------------------------------------------------------------
# Block F -- Telegram-Kurzstil im Briefing
# ---------------------------------------------------------------------------


def _stil_vorlage(stil) -> dict:
    p = fixture_dict("basis")
    if stil is not _FEHLT:
        p["display_config"]["telegram_style"] = stil
    return p


_FEHLT = object()


def test_telegram_kurzstil_erreicht_das_vergleichs_briefing_je_nutzer(mit):
    """AC-28: Nutzer A ``kurzform`` -> Telegram-Text byte-identisch zum SMS-Text (parse_mode=None);
    Nutzer B ``rich`` -> ausfuehrlicher Vergleichstext mit Ortsbloecken; fehlender Schluessel,
    leerer und unbekannter Wert verhalten sich wie ``rich``."""
    a = _lauf(mit, _stil_vorlage("kurzform"), "premium")
    b = _lauf(mit, _stil_vorlage("rich"), "premium")
    compare_vorbedingung_pruefen(a.snap, ALLE_MIT_TEXT)
    compare_vorbedingung_pruefen(b.snap, ALLE_MIT_TEXT)
    assert _text(a.snap, "telegram") == _text(a.snap, "sms"), (
        "Kurzstil: der Telegram-Text muss der SMS-Text sein (wie im Trip-Briefing)")
    assert a.snap.sendungen("telegram")[-1]["parse_mode"] is None
    assert a.snap.empfaenger("telegram") == [f"chat-{a.uid}"]
    assert _text(b.snap, "telegram") != _text(b.snap, "sms")
    assert "Innsbruck\n   " in _text(b.snap, "telegram") and "Bozen\n   " in _text(b.snap, "telegram")
    assert b.snap.empfaenger("telegram") == [f"chat-{b.uid}"]
    for wert in (_FEHLT, "", "unbekannt-xyz"):
        lauf = _lauf(mit, _stil_vorlage(wert), "premium")
        compare_vorbedingung_pruefen(lauf.snap, ALLE_MIT_TEXT)
        assert _text(lauf.snap, "telegram") == _text(b.snap, "telegram"), f"telegram_style={wert!r} muss wie rich wirken"
    # Der Kurzstil ist eine Darstellung, kein Kanalschalter: die Kanalmenge bleibt gleich.
    assert a.snap.kanaele == b.snap.kanaele


# ---------------------------------------------------------------------------
# Block G -- Mail-Kennung und Beobachtbarkeit
# ---------------------------------------------------------------------------


def test_vergleichs_mail_traegt_kennung_compare_klartext_und_stundenkennzeichen(mit):
    """AC-29: aufgezeichnete Mail hat ``mail_type == "compare"``, nicht-leeren Klartext und
    ``compare_hourly_enabled`` passend zum Preset; HTML enthaelt die Matrix mit den Orten."""
    an = fixture_dict("stundenverlauf")
    aus = fixture_dict("stundenverlauf")
    aus["hourly_enabled"] = False
    for vorlage, soll in ((an, True), (aus, False)):
        for lauf in _zwei_nutzer(mit, vorlage):
            compare_vorbedingung_pruefen(lauf.snap, ("email",))
            mail = lauf.snap.sendungen("email")[-1]
            assert mail["mail_type"] == "compare"
            assert mail["plain_text_body"] and mail["plain_text_body"].strip()
            assert mail["compare_hourly_enabled"] is soll
            for ort in ORTSNAMEN:
                assert re.search(rf"<th[^>]*>{ort}</th>", mail["body"]), f"Matrix-Kopf ohne {ort}"


def test_vorbedingung_schlaegt_bei_null_sendungen_an(mit):
    """AC-30: liefe die Mail an der Aufzeichnung vorbei (hier: ein ``mail_sink`` umgeht die
    Ausgangsklasse), waere die Sendungsliste leer -- die Vorbedingung muss dann FEHLSCHLAGEN."""
    uid = nutzer_anlegen("premium")
    orte_anlegen(uid)
    p = fixture_dict("basis")
    preset_ablegen(uid, p)
    mit.leeren()
    gesehen: list = []
    briefing_senden(uid, p["id"], settings_fuer(uid), mail_sink=lambda subject, body: gesehen.append(subject))
    assert gesehen, "Sink wurde bedient (der Versand lief, nur an der Aufzeichnung vorbei)"
    assert mit.sendungen("email") == []
    with pytest.raises(AssertionError, match="Vorbedingung verletzt"):
        compare_vorbedingung_pruefen(mit, ("email",))
    with pytest.raises(AssertionError, match="Vorbedingung verletzt"):
        compare_vorbedingung_pruefen(Kanalmitschrift(), ("email",))
