"""#3047 Runde 7, Paket p8: Orte-SMS/Premium-SMS kuerzen zuerst die Zellen
ALLER Orte, erst dann ganze Orte (AC-23, ADR-0095).

#3172 (ADR-0125): die Orte-SMS schreibt die Token-Zeile der Trip-SMS; alle
gezeigten Orte tragen gleich viele Listenzeilen, der Zaehler ``+N`` entfaellt.

SPEC: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md,
"Nachtrag Runde 7" (AC-23; Tech-Lead-Entscheidung p8: ein Vergleich braucht
mehrere Orte -- jeder Kanal beantwortet jede Frage, ADR-0095).

Echter Weg: rohes Preset-JSON im Nutzerordner -> ``load_compare_presets`` ->
``send_one_compare_preset`` -> ``NotificationService`` -> Transport-Mitschrift.
Einzige Naehte: Wetter (``ComparisonEngine.run``, echte Subklasse) und
Transport. Jeder Fall mit zwei frischen Nutzern; Erwartungen von Hand.
"""
from __future__ import annotations

import copy
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.loader import get_data_dir, save_location
from app.user import SavedLocation
from tests.helpers.transport_mitschrift import aufzeichner_installieren
from tests.tdd._compare_kette_fixtures import (
    TARGET_DATE, _dp, briefing_senden, fixture_dict, nutzer_anlegen,
    preset_ablegen, settings_fuer, transport_einrichten,
)

#: Orte (Kennung -> Name). Reihenfolge = ``location_ids``.
ORTE = [("loc-ibk", "Innsbruck"), ("loc-bz", "Bozen"), ("loc-kuf", "Kufstein"),
        ("loc-lz", "Lienz"), ("loc-sz", "Salzburg"), ("loc-vil", "Villach"),
        ("loc-gr", "Graz"), ("loc-li", "Linz"), ("loc-br", "Bregenz"),
        ("loc-kl", "Klagenfurt"), ("loc-sp", "St. Poelten"), ("loc-ei", "Eisenstadt"),
        # #3172: die Orte-SMS ist kuerzer (keine Namen, 160 Zeichen) -- fuer den
        # Orts-Ueberlauf braucht es mehr Orte.
        ("loc-we", "Wels"), ("loc-st", "Steyr"), ("loc-do", "Dornbirn"),
        ("loc-fe", "Feldkirch"), ("loc-le", "Leoben"), ("loc-ki", "Kitzbuehel"),
        ("loc-ze", "Zell am See"), ("loc-ha", "Hallein")]
ORTE += [(f"loc-x{i}", f"Ort {i}") for i in range(21, 31)]
#: Orte fuer den Orts-Ueberlauf; die beiden letzten tragen im Warnungs-Fall die Warnung.
VIELE = 30

#: Mail-Tabellenfolge bei "nie eingestellt" (CV2), als SMS-Kuerzel von Hand.
#: #3172: der Tagestiefstwert ``L`` steht im Bereich ``D10/20`` der ersten Zeile.
MAIL_KUERZEL = ["D", "W", "R", "PR", "TH", "SU", "CT", "UV", "VS", "SD", "NS", "G", "WD"]

#: Ausdrueckliche lange Liste, Folge bewusst != Katalogfolge, Kuerzel von Hand.
LANGE_LISTE = [("gust", "G"), ("uv_index", "UV"), ("temperature", "D"),
               ("precipitation", "R"), ("wind", "W"), ("cloud_total", "CT"),
               ("rain_probability", "PR"), ("sunshine", "SU"), ("thunder", "TH"),
               ("wind_direction", "WD")]

#: Aggregation je Zeile, wo sie nicht "max" ist.
AGG = {"precipitation": "sum", "cloud_total": "avg", "sunshine": "sum",
       "wind_direction": "avg"}

ALLE_KUERZEL = sorted({k for _, k in LANGE_LISTE} | set(MAIL_KUERZEL), key=len, reverse=True)


#: Orte mit amtlicher Warnung je Test (Kennungen).
WARN: dict = {"orte": set()}


def _warnung():
    from services.official_alerts.models import OfficialAlert

    wien = ZoneInfo("Europe/Vienna")
    return OfficialAlert(
        source="meteoalarm", hazard="thunderstorm", level=3, label="Gewitter",
        region_label="Tirol", valid_from=datetime(2026, 7, 8, 10, 0, tzinfo=wien),
        valid_to=datetime(2026, 7, 8, 20, 0, tzinfo=wien))


def _ergebnis(locations, kwargs):
    from app.models import ThunderLevel
    from app.user import ComparisonResult, LocationResult

    res = []
    for i, loc in enumerate(list(locations)):
        w = dict(temp_max=20.0 + i, temp_min=10.0 + i, wind_max=11.0 + i, gust_max=19.0 + i,
                 cloud_avg=30 + i, sunny_hours=5.0 + i, snow_depth_cm=0.0, snow_new_cm=0.0,
                 precip_1h=1.5, pop=10 + i)
        res.append(LocationResult(
            location=loc, score=90 - i, temp_max=w["temp_max"], temp_min=w["temp_min"],
            wind_max=w["wind_max"], gust_max=w["gust_max"], cloud_avg=w["cloud_avg"],
            sunny_hours=w["sunny_hours"], snow_depth_cm=w["snow_depth_cm"],
            snow_new_cm=w["snow_new_cm"], wind_direction_avg=250, precip_sum_mm=3.5 + i,
            pop_max_pct=40 + i, uv_index_max=6.0, thunder_level_max=ThunderLevel.MED,
            visibility_min_m=8000,
            official_alerts=[_warnung()] if loc.id in WARN["orte"] else [],
            hourly_data=[_dp(9, w), _dp(12, w), _dp(15, w)],
        ))
    return ComparisonResult(locations=res, time_window=kwargs.get("time_window", (9, 16)),
                            target_date=kwargs.get("target_date", TARGET_DATE),
                            created_at=datetime(2026, 7, 8, 4, 0))


@pytest.fixture
def mit(monkeypatch):
    import services.comparison_engine as ce_mod
    import services.scheduler_dispatch_service as sds_mod

    original = ce_mod.ComparisonEngine

    class Engine(original):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            locations = kwargs.get("locations") or (args[0] if args else [])
            return _ergebnis(locations, kwargs)

    transport_einrichten(monkeypatch)
    monkeypatch.setattr(ce_mod, "ComparisonEngine", Engine)
    monkeypatch.setattr(sds_mod, "_write_compare_alert_snapshots", lambda *a, **k: None)
    WARN["orte"] = set()
    return aufzeichner_installieren(monkeypatch)


def preset(anzahl: int, liste: list[str] | None) -> dict:
    p = fixture_dict("basis")
    p["location_ids"] = [lid for lid, _ in ORTE[:anzahl]]
    if liste is None:
        p["display_config"].pop("active_metrics")  # nie eingestellt
    else:
        p["display_config"]["active_metrics"] = [
            {"metric_id": m, "aggregation": AGG.get(m, "max")} for m in liste]
    p["send_telegram"] = p["send_sms"] = p["send_premium_sms"] = True
    p["alert_channels"] = {"email": True, "telegram": False, "sms": False, "premium_sms": False}
    return p


def zwei_nutzer(mit, p) -> list:
    laeufe = []
    for _ in range(2):
        uid = nutzer_anlegen("premium")
        pf = get_data_dir(uid) / "user.json"
        u = json.loads(pf.read_text())
        u["language"] = "de"
        pf.write_text(json.dumps(u))
        for lid, name in ORTE:
            save_location(SavedLocation(id=lid, name=name, lat=47.27, lon=11.39,
                                        elevation_m=1000), user_id=uid)
        preset_ablegen(uid, copy.deepcopy(p))
        mit.leeren()
        briefing_senden(uid, p["id"], settings_fuer(uid))
        snap = copy.deepcopy(mit)
        mit.leeren()
        assert snap.sendungen("sms") and snap.sendungen("premium_sms"), uid
        laeufe.append((uid, snap))
    assert laeufe[0][0] != laeufe[1][0]
    return laeufe


def _teile(sms: str) -> list[str]:
    from tests.helpers.orte_sms import orte_teile

    return orte_teile(sms)


def _name(ortsteil: str) -> str:
    """#3172 (PO 2026-11-19): keine Namen in der SMS -- die Ortsnummer ``O{n}``
    (Stelle in ``location_ids``) wird auf den Namen zurueckgefuehrt."""
    return ORTE[int(ortsteil.split(" ", 1)[0][1:]) - 1][1]


def _kuerzel(ortsteil: str) -> list[str]:
    """Kuerzel der Token eines Ortsteils (#3172: ``D10/20``, ``TH:M@12``,
    ``NS24+0`` -> ``D``, ``TH``, ``NS``), bis zum Warnblock ``!``."""
    from tests.helpers.orte_sms import orte_kuerzel

    return [k for k in orte_kuerzel(ortsteil) if k in ALLE_KUERZEL]


def _pruefe(snap, namen: list[str], soll: list[str], *, alle_orte: bool) -> list[str]:
    sms = snap.sendungen("sms")[-1]["body"]
    from tests.helpers.orte_sms import assert_premium_folgt_sms

    assert len(sms) <= 160, (len(sms), sms)
    assert_premium_folgt_sms(sms, snap.sendungen("premium_sms")[-1]["body"])
    teile = _teile(sms)
    gezeigt = [_name(t) for t in teile]
    if alle_orte:
        assert " Orte" not in sms, f"Ort faellt weg, obwohl Zellen kuerzbar sind: {sms}"
        assert gezeigt == namen, sms
    for teil in teile:
        ist = _kuerzel(teil)
        assert ist and ist[0] == soll[0], f"erste Listenzeile fehlt: {teil!r} in {sms}"
        assert ist == soll[:len(ist)], f"nicht vom Listenende gekuerzt: {ist} vs {soll}"
    # #3172 (ADR-0125 Nr. 4): alle gezeigten Orte tragen gleich viele Zeilen,
    # kein Zaehler ``+N`` mehr im Ortsteil.
    assert len({len(_kuerzel(t)) for t in teile}) == 1, f"ungleiche Zeilenzahl: {sms}"
    assert not any(re.search(r" [+?]\d+(?: |$)", t) for t in teile), sms
    return teile


@pytest.mark.parametrize("anzahl", [2, 3])
def test_nie_eingestellt_alle_orte_sichtbar(mit, anzahl):
    namen = [n for _, n in ORTE[:anzahl]]
    for uid, snap in zwei_nutzer(mit, preset(anzahl, None)):
        teile = _pruefe(snap, namen, MAIL_KUERZEL, alle_orte=True)
        # #3172: gleiche Zeilenzahl je Ort (in ``_pruefe``), mehr als eine Zeile.
        assert len(_kuerzel(teile[0])) > 1, teile


def test_lange_ausdrueckliche_liste_drei_orte(mit):
    namen = [n for _, n in ORTE[:3]]
    soll = [k for _, k in LANGE_LISTE]
    for uid, snap in zwei_nutzer(mit, preset(3, [m for m, _ in LANGE_LISTE])):
        _pruefe(snap, namen, soll, alle_orte=True)


def test_viele_orte_fallen_erst_nach_der_ersten_zeile_weg(mit):
    """30 Orte: selbst mit nur der ersten Listenzeile passen nicht alle -- dann
    erst fallen Orte vom Ende als ``+k Orte`` weg, jeder gezeigte Ort behaelt
    seine erste Zeile, die Zahl der gezeigten plus k ergibt alle Orte."""
    soll = [k for _, k in LANGE_LISTE]
    for uid, snap in zwei_nutzer(mit, preset(VIELE, [m for m, _ in LANGE_LISTE])):
        sms = snap.sendungen("sms")[-1]["body"]
        treffer = re.search(r" \+(\d+) Orte$", sms)
        assert treffer, sms
        teile = _pruefe(snap, [], soll, alle_orte=False)
        assert len(teile) + int(treffer.group(1)) == VIELE, sms
        assert len(teile) >= 3, f"zu frueh Orte verworfen: {sms}"
        assert all(len(_kuerzel(t)) == 1 for t in teile), f"Orte vor der ersten Zeile weg: {sms}"
        gezeigt = [_name(t) for t in teile]
        assert gezeigt == [n for _, n in ORTE[:len(teile)]], sms


def test_viele_orte_warnung_eines_hinteren_ortes_faellt_zuletzt_weg(mit):
    """30 Orte, nur der letzte (Ort 30) und der vorletzte (Ort 29)
    tragen eine Gewitterwarnung: beide bleiben mit ``!TS`` sichtbar, statt
    ihrer entfallen Orte ohne Warnung vom Ende; jeder gezeigte Ort behaelt
    seine erste Listenzeile und seine Nummer (``O29``, ``O30``)."""
    WARN["orte"] = {"loc-x29", "loc-x30"}
    soll = [k for _, k in LANGE_LISTE]
    for uid, snap in zwei_nutzer(mit, preset(VIELE, [m for m, _ in LANGE_LISTE])):
        sms = snap.sendungen("sms")[-1]["body"]
        treffer = re.search(r" \+(\d+) Orte$", sms)
        assert treffer, sms
        teile = _pruefe(snap, [], soll, alle_orte=False)
        gezeigt = [_name(t) for t in teile]
        assert gezeigt[-2:] == ["Ort 29", "Ort 30"], sms
        assert [t.split(" ", 1)[0] for t in teile[-2:]] == ["O29", "O30"], sms
        for teil in teile[-2:]:
            assert "!TS" in teil, f"Warnung fehlt: {sms}"
        ohne = [n for _, n in ORTE[:28]]
        assert gezeigt[:-2] == ohne[:len(gezeigt) - 2], sms
        assert len(teile) + int(treffer.group(1)) == VIELE, sms
