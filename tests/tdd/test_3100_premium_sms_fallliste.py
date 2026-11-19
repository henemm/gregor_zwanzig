"""#3100 (Phase 3e von #3047, Epic #3058): Premium-SMS-Fallliste im Pruefkatalog.

SPEC: docs/specs/modules/feat_3100_premium_sms_fallliste.md (AC-1 bis AC-8)

Die Premium-SMS folgt vorerst der SMS (ADR-0124 Nr. 8): eine abweichende
``channel_layouts.premium_sms`` wird NICHT gelesen (eigene Auswahl erst #2801).
Hier wird das ueber den ECHTEN Empfangsweg belegt: Garmin-Nachricht ins
seven.io-Journal -> ``InboundSmsReader.poll_and_process`` -> Kommandoverarbeiter
-> Briefing per Premium-SMS. Verglichen wird der an der Premium-SMS-Ausgabe
gebuchte Text mit dem SMS-Text desselben Ziels (echter Versand,
``restrict_to_channel="sms"``).

Aussengrenzen (keine ``Mock()``/``patch()``): Journal-GET und Lern-POST
(``test_premium_sms_kommandopfad._poll``), die vier Kanal-Ausgaenge
(``tests/helpers/transport_mitschrift.py`` ueber die Fixture ``mit``), das
Vergleichs-Wetter (echte Engine-Subklasse der Runde 7) und -- nur in AC-4 --
der Abruf amtlicher Warnungen.

ROT vor der Umsetzung:
* ``test_ac5_*``/``test_ac6_*``/``test_ac7_*`` -- ``fallliste_premium_sms.json``
  ist im Waechter nicht registriert (``TEILDATEIEN``, ``PY_TEST_GLOBS``).

Die Empfangsweg-Faelle (AC-1 bis AC-4, AC-8) sind Nachweis des heutigen
Verhaltens (keine Produktionsaenderung vorgesehen) und bewachen es gegen die
Mutationen der Spec (Premium liest eigene Ebene, Grenze 153 -> 160, Kuerzung
entfernt Warnung, Antwort an fremden Nutzer).
"""
from __future__ import annotations

import copy
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import pytest

from app.loader import (
    compare_preset_to_dict, load_all_locations, load_all_trips, load_compare_presets,
    load_trip, save_trip,
)
from app.models import TripReportConfig
from app.trip import Stage, Trip, Waypoint
from services.trip_report_scheduler import TripReportSchedulerService
from tests.tdd._compare_kette_fixtures import nutzer_anlegen, orte_anlegen, preset_ablegen
from tests.tdd._einstellung_auslieferung_fixtures import (
    frisches_profil, golden_dict, premium_rueckadresse,
)
from tests.tdd.test_3047_r7_kanaele_trip import _LANGE_LISTE, GRUNDAUSWAHL, _mc

# ruff: noqa: F811  (mit = geteilte Fixture als Testparameter)
from tests.tdd.test_3047_runde7_orte_kanaele import mit, preset  # noqa: F401  (Fixture)
from tests.tdd.test_premium_sms_kommandopfad import (
    INNSBRUCK, _garmin, _Journal, _LernEndpunkt, _poll,
)
from utils.timezone import tz_for_coords

REPO_ROOT = Path(__file__).resolve().parents[2]
FALLLISTEN_DIR = REPO_ROOT / "tests" / "fixtures" / "einstellung_gleich_mail"
PREMIUM_DATEI = "fallliste_premium_sms.json"
PREMIUM_GRENZE = 153

NUMMERN = ("4917000003101", "4917000003102")

#: Befehl -> Report-Typ des On-Demand-Briefings (``trip_command_processor``).
BEFEHLE = {"heute": "morning", "morgen": "evening"}


def _liste(ids: list[str], fmt: str | None = None) -> list[dict]:
    return [_mc(m, i, fmt if m == "cloud_total" else None) for i, m in enumerate(ids)]


SMS_LISTE = ["precipitation", "gust", "cloud_total"]
#: Bewusst disjunkt zur SMS-Liste: wird sie gelesen, aendert sich der Text sichtbar.
PREMIUM_ABWEICHEND = ["humidity", "uv_index", "temperature"]


# ---------------------------------------------------------------------------
# Trip-Aufbau: echte Dateien, Etappen gestern/heute/morgen am Fixture-Standort
# ---------------------------------------------------------------------------

def _trip_anlegen(uid: str, *, sms: list[dict] | None, premium: list[dict] | None,
                  grund: list[str] = GRUNDAUSWAHL, warnungen: bool = False) -> Trip:
    """``premium is None`` = Kanal-Ebene nie gesetzt, ``[]`` = leer."""
    d = golden_dict("golden_c")
    d["display_config"]["metrics"] = [_mc(m, i) for i, m in enumerate(grund)]
    layouts: dict = {}
    if sms is not None:
        layouts["sms"] = sms
    if premium is not None:
        layouts["premium_sms"] = premium
    d["display_config"]["channel_layouts"] = layouts
    d["display_config"]["outlook_metrics"] = []
    dc = load_trip(copy.deepcopy(d), user_id=uid).display_config

    zone = tz_for_coords(*INNSBRUCK)
    heute = datetime.now(timezone.utc).astimezone(zone).date()
    trip_id = f"psms-{uid[-6:]}"
    stages = [
        Stage(id=f"T{i}", name=f"Etappe {i}", date=heute + timedelta(days=i - 1),
              waypoints=[
                  Waypoint(id=f"G{i}a", name="Start", lat=INNSBRUCK[0], lon=INNSBRUCK[1],
                           elevation_m=600),
                  Waypoint(id=f"G{i}b", name="Ziel", lat=INNSBRUCK[0] + 0.02,
                           lon=INNSBRUCK[1] + 0.02, elevation_m=900)])
        for i in range(3)
    ]
    trip = Trip(
        id=trip_id, name=f"Premium {uid[-6:]}", stages=stages, display_config=dc,
        official_alerts_enabled=warnungen,
        report_config=TripReportConfig(trip_id=trip_id, send_email=True, send_sms=True,
                                       send_premium_sms=True, send_telegram=True),
    )
    save_trip(trip, uid)
    return next(t for t in load_all_trips(uid) if t.id == trip_id)


def _eingang(monkeypatch, auftraege: list[tuple[str, str, str]]) -> None:
    """Ein Journal-Poll mit je einer Garmin-Nachricht ``(uid, nummer, befehl)``."""
    msgs = [_garmin(3100 + i, nummer, befehl) for i, (_u, nummer, befehl) in enumerate(auftraege)]
    _poll(monkeypatch, journal=_Journal([msgs]),
          lernen=_LernEndpunkt(nummer_zu_user={n: u for u, n, _b in auftraege}))


def _premium_fuer(mit, uid: str) -> list[str]:
    ziel = premium_rueckadresse(uid)
    return [s["body"] for s in mit.sendungen("premium_sms") if s["empfaenger"] == ziel]


def _trip_sms(mit, uid: str, trip: Trip, report_type: str) -> str:
    """SMS-Text desselben Trips ueber den echten Versandweg."""
    mit.leeren()
    erg = TripReportSchedulerService(user_id=uid).send_on_demand_report(
        trip, report_type, restrict_to_channel="sms")
    assert erg.outcome == "sent", f"Vorbedingung SMS-Versand: {erg.outcome!r}"
    sendungen = mit.sendungen("sms")
    assert len(sendungen) == 1, mit
    return sendungen[0]["body"]


def _trip_premium_ueber_eingang(monkeypatch, mit, uid: str, befehl: str) -> str:
    mit.leeren()
    _eingang(monkeypatch, [(uid, NUMMERN[0], befehl)])
    assert mit.kanaele == ["premium_sms"], f"Antwort nur per Premium-SMS erwartet: {mit!r}"
    texte = _premium_fuer(mit, uid)
    assert len(texte) == 1, mit
    return texte[0]


# ---------------------------------------------------------------------------
# AC-1 / AC-8: Trip, abweichende Premium-Ebene, morning und evening
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("befehl", list(BEFEHLE))
@pytest.mark.parametrize("premium_ebene", ["abweichend", "leer", "nie"])
def test_ac1_trip_eingang_premium_gleich_sms(monkeypatch, mit, befehl, premium_ebene):
    """AC-1/AC-8: Garmin-Befehl ueber den echten Reader -> Premium-Antwort ist der
    SMS-Text desselben Trips; die Premium-Ebene (abweichend/leer/nie) wird nicht gelesen."""
    uid = frisches_profil()
    premium = {"abweichend": _liste(PREMIUM_ABWEICHEND), "leer": [], "nie": None}[premium_ebene]
    trip = _trip_anlegen(uid, sms=_liste(SMS_LISTE), premium=premium)

    premium_text = _trip_premium_ueber_eingang(monkeypatch, mit, uid, befehl)
    sms_text = _trip_sms(mit, uid, trip, BEFEHLE[befehl])

    assert " R" in sms_text and " G" in sms_text and " CT" in sms_text, sms_text
    assert premium_text == sms_text, (premium_text, sms_text)
    assert len(premium_text) <= PREMIUM_GRENZE, premium_text


# ---------------------------------------------------------------------------
# AC-2: Orts-Vergleich, Roh und Einfach
# ---------------------------------------------------------------------------

def _orte_sms(cloud_fmt: str) -> list[dict]:
    from tests.tdd.test_3099_sms_resolver import _orte_sms as sms_liste

    return sms_liste(cloud_fmt)


def _orte_sms_text(mit, uid: str, preset_id: str) -> str:
    """SMS-Text desselben Vergleichs ueber denselben Handversand wie die Befehlsantwort."""
    from services.compare_slot_scheduler import preset_ortstag
    from services.scheduler_dispatch_service import send_compare_preset

    p = next(p for p in load_compare_presets(uid) if p.id == preset_id)
    orte = {o.id: o for o in load_all_locations(user_id=uid)}
    zieltag = preset_ortstag(compare_preset_to_dict(p), orte, datetime.now(timezone.utc))
    mit.leeren()
    erg = send_compare_preset(uid, preset_id, restrict_to_channel="sms", target_date=zieltag,
                              tage_ab_ortstag=0)
    assert erg["status"] == "ok", erg
    sendungen = mit.sendungen("sms")
    assert len(sendungen) == 1, mit
    return sendungen[0]["body"]


@pytest.mark.parametrize("cloud_fmt", ["raw", "simplified"], ids=["roh", "einfach"])
def test_ac2_orte_eingang_premium_gleich_sms(monkeypatch, mit, cloud_fmt):
    """AC-2: Garmin-'heute' an einen Orts-Vergleich mit abweichender Premium-Ebene ->
    Premium-Antwort == SMS-Text desselben Vergleichs, Roh und Einfach."""
    abweichend = [{"metric_id": "humidity", "enabled": True},
                  {"metric_id": "uv_index", "enabled": True}]
    p = preset({"sms": _orte_sms(cloud_fmt), "premium_sms": abweichend})
    uid = nutzer_anlegen("premium")
    orte_anlegen(uid)
    preset_ablegen(uid, copy.deepcopy(p))

    mit.leeren()
    _eingang(monkeypatch, [(uid, NUMMERN[0], "heute")])
    texte = _premium_fuer(mit, uid)
    assert mit.kanaele == ["premium_sms"] and len(texte) == 1, mit
    sms_text = _orte_sms_text(mit, uid, p["id"])

    assert " CT " in sms_text, sms_text
    assert texte[0] == sms_text, (texte[0], sms_text)
    assert len(texte[0]) <= PREMIUM_GRENZE, texte[0]


# ---------------------------------------------------------------------------
# AC-3: zwei Nutzer, beide Aufrufreihenfolgen in EINEM Poll
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("reihenfolge", ["ab", "ba"])
def test_ac3_zwei_nutzer_je_eigene_premium_antwort(monkeypatch, mit, reihenfolge):
    """AC-3: zwei Nutzer mit unterschiedlicher SMS-Auswahl schicken je einen
    Garmin-Befehl; jede Premium-Antwort geht an den eigenen Nutzer und ist dessen
    SMS-Text -- nie Auswahl oder Daten des anderen."""
    a, b = frisches_profil(), frisches_profil()
    trips = {
        a: _trip_anlegen(a, sms=_liste(["gust", "cloud_total"], "raw"),
                         premium=_liste(PREMIUM_ABWEICHEND)),
        b: _trip_anlegen(b, sms=_liste(["cloud_total", "precipitation"]),
                         premium=_liste(["gust"])),
    }
    auftraege = [(a, NUMMERN[0], "heute"), (b, NUMMERN[1], "heute")]
    if reihenfolge == "ba":
        auftraege.reverse()

    mit.leeren()
    _eingang(monkeypatch, auftraege)
    premium = {uid: _premium_fuer(mit, uid) for uid in (a, b)}
    assert len(mit.sendungen("premium_sms")) == 2, mit
    sms = {uid: _trip_sms(mit, uid, trips[uid], "morning") for uid in (a, b)}

    assert sms[a] != sms[b], sms
    assert premium == {a: [sms[a]], b: [sms[b]]}, (premium, sms)


# ---------------------------------------------------------------------------
# AC-4: Ueberlaenge + amtliche Warnung
# ---------------------------------------------------------------------------

#: Ueber ``_LANGE_LISTE`` hinaus: die uebrigen Katalog-Metriken, damit der SMS-Text
#: mit den (duennen) Fixture-Werten sicher ueber 153 Zeichen kommt.
LANGE_LISTE = list(_LANGE_LISTE) + ["snowfall_limit", "cape", "snow_depth", "fresh_snow",
                                    "temperature_cold", "wind_chill_night"]


def _warnungen_heute() -> list:
    from services.official_alerts.models import OfficialAlert

    zone = tz_for_coords(*INNSBRUCK)
    jetzt = datetime.now(timezone.utc).astimezone(zone)
    # #3168: fester Beginn gestern 22:00 Ortszeit statt "jetzt - 12 h". Die
    # Warntokens tragen die lokale Beginnstunde (`!TS:M@22`); eine einstellige
    # Stunde (Lauf zwischen 12 und 22 Uhr Ortszeit) machte den SMS-Text vier
    # Zeichen kuerzer und liess die Vorbedingung `> 153` je nach Uhrzeit scheitern.
    beginn = datetime.combine(jetzt.date() - timedelta(days=1), time(22, 0), tzinfo=zone)
    return [OfficialAlert(source="meteoalarm", hazard=hazard, level=3, label=label,
                          region_label="Tirol", valid_from=beginn,
                          valid_to=jetzt + timedelta(days=2))
            for hazard, label in (("thunderstorm", "Gewitter"), ("rain", "Starkregen"),
                                  ("wind_gust", "Sturm"), ("snow", "Schnee"))]


def _teile(text: str) -> tuple[list[str], str]:
    """(Metrik-Tokens, Warnblock) -- der Warnblock reicht vom ersten ``!``-Token
    bis zum Textende (nur sein erstes Token traegt das ``!``)."""
    kopf, _, rest = text.partition(": ")
    tokens = rest.split()
    start = next((i for i, t in enumerate(tokens) if t.startswith("!")), len(tokens))
    return [kopf, *tokens[:start]], " ".join(tokens[start:])


def test_ac4_ueberlaenge_premium_kuerzt_vom_listenende_warnung_bleibt(monkeypatch, mit):
    """AC-4: SMS-Text > 153 Zeichen mit amtlicher Warnung -> Premium-Antwort
    hoechstens 153 Zeichen, Metrik-Tokens sind ein Anfangsstueck der SMS-Tokens
    (Kuerzung vom Listenende), die Warnung steht weiter hinten."""
    import services.official_alerts as oa

    warnungen = _warnungen_heute()
    monkeypatch.setattr(oa, "get_official_alerts_with_status",
                        lambda *a, **k: (list(warnungen), False))
    uid = frisches_profil()
    trip = _trip_anlegen(uid, sms=_liste(LANGE_LISTE), premium=_liste(["gust"]),
                         grund=GRUNDAUSWAHL + [m for m in LANGE_LISTE if m not in GRUNDAUSWAHL],
                         warnungen=True)

    premium_text = _trip_premium_ueber_eingang(monkeypatch, mit, uid, "heute")
    sms_text = _trip_sms(mit, uid, trip, "morning")

    assert PREMIUM_GRENZE < len(sms_text) <= 160, (
        f"Vorbedingung: SMS-Text muss die Premium-Grenze ueberschreiten: {sms_text!r}")
    assert len(premium_text) <= PREMIUM_GRENZE, premium_text
    p_tokens, p_warn = _teile(premium_text)
    s_tokens, s_warn = _teile(sms_text)
    assert s_warn and p_warn == s_warn, (premium_text, sms_text)
    assert premium_text.endswith(p_warn), premium_text
    assert len(p_tokens) < len(s_tokens), (premium_text, sms_text)
    assert p_tokens == s_tokens[:len(p_tokens)], (premium_text, sms_text)


# ---------------------------------------------------------------------------
# AC-5 / AC-6 / AC-7: Fallliste und Waechter
# ---------------------------------------------------------------------------

#: Verstreute Premium-Faelle, die in ihren Dateien BLEIBEN (Spec Nr. 5).
VERSTREUT = {
    "R7-KAT-trip-premium-matrix": "fallliste_trip.json",
    "R7-KAT-trip-premium-gleich-sms-kuerzung": "fallliste_trip.json",
    "T-R8PY-T3-PREMIUM-FOLGT-SMS": "fallliste_trip.json",
    "R7-KAT-orte-premium-gleich-sms": "fallliste_orte.json",
    "O-R7-PSMS-NIE-EINGESTELLT": "fallliste_orte.json",
    "O-R7-PSMS-UNAVAILABLE": "fallliste_orte.json",
    "sms-premium-gleich-sms-text": "fallliste_sms.json",
    "sms-orte-versand-roh": "fallliste_sms.json",
    "sms-orte-versand-einfach": "fallliste_sms.json",
}


def _waechter():
    from tests.tdd import test_einstellung_gleich_mail_fallliste as w

    return w


def _premium_liste() -> dict:
    """Die Premium-Fallliste, wie der Waechter sie laedt (registriert)."""
    w = _waechter()
    geladen = w.lade_falllisten(w.FALLLISTEN_DIR)
    assert PREMIUM_DATEI in geladen, (
        f"{PREMIUM_DATEI} ist nicht im Waechter registriert (TEILDATEIEN={w.TEILDATEIEN})")
    return geladen[PREMIUM_DATEI]


def test_ac6_waechter_registriert_premium_fallliste():
    """AC-6: Teildatei und Testmuster sind registriert, die Datei wird mitgezaehlt."""
    w = _waechter()
    assert "premium_sms" in w.TEILDATEIEN, w.TEILDATEIEN
    assert "tests/tdd/test_3100_*.py" in w.PY_TEST_GLOBS, w.PY_TEST_GLOBS
    faelle = _premium_liste()["faelle"]
    assert faelle and w.zaehle_status({PREMIUM_DATEI: {"faelle": faelle}})["gruen"] == len(faelle)


def test_ac6_fehlende_premium_teildatei_scheitert_klar(tmp_path):
    """AC-6 Selbsttest: alle Teildateien da, nur die Premium-Liste fehlt -> klarer Fehler."""
    w = _waechter()
    for teil in w.TEILDATEIEN:
        if teil != "premium_sms":
            (tmp_path / f"fallliste_{teil}.json").write_text('{"faelle": []}', encoding="utf-8")
    with pytest.raises(w.FalllisteFehler, match=r"Teildatei fehlt: .*fallliste_premium_sms\.json"):
        w.lade_falllisten(tmp_path)


def test_ac6_premium_liste_schema_ids_und_verstreute_faelle():
    """AC-6: Pflichtfelder, Praefix ``psms-``, IDs global eindeutig, die verstreuten
    Premium-Faelle bleiben in ihren Dateien und sind im ``hinweis`` genannt; die
    Kanal-Abdeckung premium_sms ist vollstaendig."""
    w = _waechter()
    daten = _premium_liste()
    alle = w.lade_falllisten(w.FALLLISTEN_DIR)
    assert w.pruefe_schema(alle) == [], w.pruefe_schema(alle)
    ids = [f["id"] for f in daten["faelle"]]
    assert all(i.startswith("psms-") for i in ids), ids
    hinweis = daten.get("dimensionen", {}).get("hinweis", "")
    for fid, datei in VERSTREUT.items():
        assert fid in hinweis, f"hinweis nennt {fid} nicht"
        assert fid in {f["id"] for f in alle[datei]["faelle"]}, f"{fid} fehlt in {datei}"
    assert not [z for z in w.pruefe_kanal_abdeckung(alle) if "premium_sms" in z]


#: Achsen der Spec (Implementation Details Nr. 1) -> geforderte Werte.
ACHSEN = {
    "weg": {"eingang", "versand", "alarm_verweis"},
    "report_type": {"morning", "evening"},
    "premium_ebene": {"nie", "leer", "abweichend"},
    "darstellung": {"roh", "einfach"},
    "kuerzung": {"153"},
    "nutzer": {"zwei"},
}


def test_ac5_premium_liste_belegt_alle_achsen_mit_ausfuehrendem_test():
    """AC-5: jede Achse ist mit mindestens einem ``psms-``-Fall belegt (Werte mit
    ``+`` zaehlen einzeln), beide Kontexte; jeder Fall nennt einen auffindbaren Test."""
    w = _waechter()
    daten = _premium_liste()
    faelle = daten["faelle"]
    assert {f["kontext"] for f in faelle} >= {"trip", "orte"}
    gesehen: dict[str, set] = {}
    for f in faelle:
        for k, v in (f.get("merkmale") or {}).items():
            gesehen.setdefault(k, set()).update(str(v).split("+"))
    for achse, soll in ACHSEN.items():
        assert gesehen.get(achse, set()) >= soll, (achse, gesehen.get(achse))
    assert w.pruefe_testverweise({PREMIUM_DATEI: daten}, REPO_ROOT) == []
    eingang = [f for f in faelle if "eingang" in str((f.get("merkmale") or {}).get("weg"))]
    assert eingang and all("test_3100_premium_sms_fallliste.py::" in f["test"] for f in eingang)


def test_ac5_fall_ohne_test_scheitert_klar(tmp_path):
    """AC-5 Selbsttest: ein Premium-Fall mit unbekanntem Test wird benannt."""
    w = _waechter()
    fall = {"id": "psms-ohne-test", "liste": "trip_premium_sms", "kontext": "trip",
            "format": "premium_sms", "pruefung": "auswahl",
            "test": "tests/tdd/test_3100_premium_sms_fallliste.py::test_gibt_es_nicht",
            "ac": "AC-5", "befund": "", "status": "gruen"}
    fehler = w.pruefe_testverweise({PREMIUM_DATEI: {"faelle": [fall]}}, REPO_ROOT)
    assert fehler and "psms-ohne-test" in fehler[0], fehler


def test_ac7_alarm_verweis_faelle():
    """AC-7: Alarme stehen als Verweis auf die Kanalparitaets-Tests (keine neue
    Metrikauswahl-Pruefung); beide Verweistests existieren."""
    faelle = _premium_liste()["faelle"]
    verweise = [f for f in faelle if (f.get("merkmale") or {}).get("weg") == "alarm_verweis"]
    tests = " ".join(f["test"] for f in verweise)
    assert "test_compare_alert_channel_equivalence.py::" in tests, verweise
    assert "test_onset_ende_kanalparitaet.py::" in tests, verweise
    assert all("alarm" in f["format"].split("+") for f in verweise), verweise
    assert all("#1701" in f["befund"] for f in verweise), verweise


def test_ac9_ausgabe_matrix_premium_zeile():  # doc-compliance-test
    """AC-9: Die Premium-SMS-Zeile der Ausgabe-Matrix nennt die Fallliste, ADR-0124
    (Premium folgt vorerst der SMS) und #2801 (eigene Auswahl)."""
    doku = (REPO_ROOT / "docs" / "reference" / "metric_output_matrix.md").read_text(encoding="utf-8")
    zeilen = [z for z in doku.splitlines() if z.startswith("| Premium-SMS")]
    assert len(zeilen) == 1, zeilen
    for pflicht in (PREMIUM_DATEI, "ADR-0124", "#2801"):
        assert pflicht in zeilen[0], pflicht
