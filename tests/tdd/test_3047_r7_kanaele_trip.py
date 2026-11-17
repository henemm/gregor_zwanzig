"""#3047 Runde 7, Paket p1_kanaele_trip: Trip-Telegram und Trip-SMS aus Nutzersicht.

Spec: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md, Nachtrag Runde 7
(AC-22 Telegram/SMS-Liste inkl. Windrichtung Roh #3063 und Nutzersprache, AC-23 SMS-Kuerzung
vom Listenende, amtliche Warnungen zuletzt).

Echter Weg: Trip-JSON (Persistenzformat des Editors) -> ``load_trip`` ->
``NotificationService.send_trip_report`` -> Transport-Mitschrift
(``tests/helpers/transport_mitschrift.py``). Je Fall zwei frische Nutzer; die Mitschrift
belegt, dass jede Sendung beim eigenen Empfaenger ankommt. Kein Mock, keine Dateiinhalt-Pruefung.
"""
from __future__ import annotations

import json
import re
from datetime import datetime

import pytest

from app.loader import get_data_dir, load_trip
from services.notification_service import NotificationService, TripReportRequest
from tests.helpers.transport_mitschrift import aufzeichner_installieren
from tests.tdd._einstellung_auslieferung_fixtures import (
    STAGE_NAME, TRANSPORT_ENV, TZ, frisches_profil, golden_dict, night_weather, segment,
)

GRUNDAUSWAHL = ["gust", "temperature", "rain_probability", "wind", "wind_direction", "thunder",
                "cloud_total", "precipitation", "uv_index", "humidity"]


def _mc(mid: str, order: int, fmt: str | None = None, enabled: bool = True) -> dict:
    """Ein Listeneintrag im Speicherformat des Editors (Roh = ``format_mode: raw``)."""
    d = {"metric_id": mid, "enabled": enabled, "bucket": "primary", "order": order,
         "use_friendly_format": fmt != "raw"}
    if fmt is not None:
        d["format_mode"] = fmt
    return d


def _trip(telegram: list[dict] | None = None, sms: list[dict] | None = None,
          extra: list[str] = ()) -> dict:
    d = golden_dict("golden_c")
    d["display_config"]["metrics"] = [
        _mc(m, i) for i, m in enumerate(GRUNDAUSWAHL + list(extra))]
    layouts = {}
    if telegram is not None:
        layouts["telegram"] = telegram
    if sms is not None:
        layouts["sms"] = sms
    d["display_config"]["channel_layouts"] = layouts
    d["display_config"]["outlook_metrics"] = []
    d["report_config"]["telegram_style"] = "rich"
    return d


def _warnung():
    from services.official_alerts.models import OfficialAlert
    return OfficialAlert(source="meteoalarm", hazard="thunderstorm", level=3,
                         label="Gewitter", region_label="Tirol",
                         valid_from=datetime(2026, 7, 20, 10, 0, tzinfo=TZ),
                         valid_to=datetime(2026, 7, 20, 20, 0, tzinfo=TZ))


def _senden(monkeypatch, data: dict, *, lang: str | None = None, warn: bool = False):
    for k, v in TRANSPORT_ENV.items():
        monkeypatch.setenv(k, v)
    mit = aufzeichner_installieren(monkeypatch)
    uid = frisches_profil()
    if lang:
        pfad = get_data_dir(uid) / "user.json"
        profil = json.loads(pfad.read_text())
        profil["language"] = lang
        pfad.write_text(json.dumps(profil))
    trip = load_trip(data, user_id=uid)
    seg = segment()
    if warn:
        seg.official_alerts = [_warnung()]
    rc = trip.report_config
    req = TripReportRequest(
        trip=trip, report_type="evening", segment_weather=[seg], trip_tz=TZ,
        night_weather=night_weather(), stage_name=STAGE_NAME, report_config=rc,
        display_config=trip.display_config, send_email=rc.send_email, send_sms=rc.send_sms,
        send_telegram=rc.send_telegram, send_premium_sms=rc.send_premium_sms)
    assert NotificationService(user_id=uid).send_trip_report(req).sent
    return uid, mit


def _zwei_nutzer(monkeypatch, data: dict, **kw):
    """Zwei frische Nutzer senden dieselbe Konfiguration; jede Sendung geht an den eigenen."""
    laeufe = [_senden(monkeypatch, data, **kw) for _ in range(2)]
    assert laeufe[0][0] != laeufe[1][0]
    for uid, mit in laeufe:
        assert mit.empfaenger("telegram") and all(
            e == f"chat-{uid}" for e in mit.empfaenger("telegram"))
        assert mit.empfaenger("email") == [f"{uid}@example.invalid"]
    return laeufe


def _kurzuebersicht(mit) -> list[str]:
    for s in mit.sendungen("telegram"):
        kopf = s["body"].splitlines()[0]
        if kopf in ("Kurzübersicht", "Summary"):
            return s["body"].splitlines()
    raise AssertionError(f"keine Kurzuebersicht: {mit}")


def _tabelle(mit) -> tuple[list[str], list[list[str]]]:
    for s in mit.sendungen("telegram"):
        if "<pre>" in s["body"]:
            zeilen = s["body"].split("<pre>")[1].split("</pre>")[0].strip().splitlines()
            return zeilen[0].split(), [z.split() for z in zeilen[1:]]
    raise AssertionError(f"keine Telegram-Tabelle: {mit}")


def _zeile(uebersicht: list[str], kuerzel: str) -> str:
    treffer = [z for z in uebersicht if z.startswith(f"{kuerzel} ")]
    assert treffer, (kuerzel, uebersicht)
    return treffer[0]


# --------------------------------------------------------------------------- B-K1 (#3063 P2)

def _tg_liste(wd_fmt: str, ct_fmt: str) -> list[dict]:
    # Folge bewusst ungleich Katalogfolge; Windrichtung vorn (eigene Spalte, nicht in W verschmolzen).
    return [_mc("wind_direction", 0, wd_fmt), _mc("precipitation", 1), _mc("cloud_total", 2, ct_fmt),
            _mc("gust", 3), _mc("temperature", 4), _mc("thunder", 5)]


@pytest.mark.parametrize("lang", ["de", "en"])
def test_ac22_telegram_windrichtung_roh_zeigt_grad_wie_mail(monkeypatch, lang):
    """Windrichtung Roh in der Telegram-Liste: Kurzuebersicht und Tabelle zeigen Grad (250°)
    wie die Mail mit Windrichtung Roh, nicht den Kompasswert."""
    for _uid, mit in _zwei_nutzer(monkeypatch, _trip(telegram=_tg_liste("raw", "raw")), lang=lang):
        uebersicht = _kurzuebersicht(mit)
        assert _zeile(uebersicht, "WD") == "WD 250°", uebersicht
        kopf, zeilen = _tabelle(mit)
        assert kopf[1] == "WD", kopf
        assert {z[1] for z in zeilen} == {"250°"}, zeilen
        # Bewoelkung Roh: Prozentzahl statt Symbol (dieselbe Regel, andere Metrik).
        assert re.fullmatch(r"CT 70", _zeile(uebersicht, "CT")), uebersicht
        assert {z[kopf.index("CT")] for z in zeilen} == {"70"}, zeilen


def test_ac22_telegram_windrichtung_einfach_bleibt_kompass(monkeypatch):
    """Gegenprobe: Windrichtung/Bewoelkung Einfach -> Kompass W und Wolkensymbol."""
    for _uid, mit in _zwei_nutzer(monkeypatch, _trip(telegram=_tg_liste("scale", "symbol"))):
        uebersicht = _kurzuebersicht(mit)
        assert _zeile(uebersicht, "WD") == "WD W", uebersicht
        kopf, zeilen = _tabelle(mit)
        assert {z[1] for z in zeilen} == {"W"}, zeilen
        assert not re.search(r"CT \d", _zeile(uebersicht, "CT")), uebersicht
        assert {z[kopf.index("CT")] for z in zeilen} != {"70"}, zeilen


def test_ac22_telegram_roh_gleich_mail_roh(monkeypatch):
    """Dieselbe Roh-Wahl in Mail- und Telegram-Liste ergibt denselben Windrichtungswert."""
    data = _trip(telegram=_tg_liste("raw", "raw"))
    data["display_config"]["channel_layouts"]["email"] = _tg_liste("raw", "raw")
    for _uid, mit in _zwei_nutzer(monkeypatch, data):
        mail = mit.sendungen("email")[0]["plain_text_body"]
        assert "250°" in mail
        assert "WD 250°" in _kurzuebersicht(mit)


# --------------------------------------------------------------------------- B-K2

def _acht_zeilen() -> list[dict]:
    ids = ["wind_direction", "precipitation", "gust", "temperature", "wind", "thunder",
           "humidity", "uv_index", "cloud_total"]
    return [_mc(m, i) for i, m in enumerate(ids)]


@pytest.mark.parametrize("lang,soll,nicht", [
    ("en", "Telegram limit", "Wettergrößen"),
    ("de", "Telegram-Limit", "Telegram limit"),
])
def test_ac22_telegram_kappungshinweis_in_nutzersprache(monkeypatch, lang, soll, nicht):
    """Mehr als 7 Telegram-Zeilen: der Hinweis auf die nur als Tageswert gezeigten Groessen
    steht in der Sprache des Nutzers."""
    for _uid, mit in _zwei_nutzer(monkeypatch, _trip(telegram=_acht_zeilen()), lang=lang):
        text = " ".join(_kurzuebersicht(mit))  # Telegram-Prosa wird bei 56 Zeichen umbrochen
        assert soll in text and nicht not in text, text


# --------------------------------------------------------------------------- B-K4 (AC-23)

# Nur Groessen, die mit der Wetter-Fixture ein Kuerzel erzeugen (Schnee/CAPE bleiben dort stumm),
# damit "lueckenloser Listenanfang" eindeutig pruefbar ist.
_LANGE_LISTE = ["humidity", "dewpoint", "pressure", "temperature", "wind", "gust", "visibility",
                "cloud_total", "cloud_low", "cloud_mid", "cloud_high", "freezing_level",
                "uv_index", "wind_direction", "wind_chill", "sunshine", "precip_type",
                "precipitation", "rain_probability", "thunder"]
_EXTRA = [m for m in _LANGE_LISTE if m not in GRUNDAUSWAHL]

# Kuerzel je Listeneintrag (Token-Symbol ohne Doppelpunkt) fuer die Folge-Pruefung.
_KUERZEL = {"humidity": {"HU"}, "dewpoint": {"DP"}, "pressure": {"HP"},
            "temperature": {"N", "L", "D"}, "wind": {"W"}, "gust": {"G"}, "visibility": {"VS"},
            "cloud_total": {"CT"}, "cloud_low": {"CL"}, "cloud_mid": {"CM"}, "cloud_high": {"CH"},
            "freezing_level": {"FZ"}, "snowfall_limit": {"SL"}, "cape": {"CP"}, "uv_index": {"UV"},
            "wind_direction": {"WD"}, "wind_chill": {"FN", "FL", "FD", "TF"}, "sunshine": {"SU"},
            "precip_type": {"PT"}, "snow_depth": {"SD"}, "fresh_snow": {"NS"},
            "precipitation": {"R"}, "rain_probability": {"PR"}, "thunder": {"TH", "TH+"}}


def _symbole(sms: str) -> list[str]:
    body = sms.split(": ", 1)[1]
    return [re.match(r"([A-Z]+\+?)", tok).group(1) for tok in body.split() if re.match(r"[A-Z]", tok)]


def _listenplaetze(sms: str, liste: list[str]) -> list[int]:
    plaetze = []
    for sym in _symbole(sms):
        platz = next((i for i, m in enumerate(liste) if sym in _KUERZEL[m]), None)
        if platz is not None:
            plaetze.append(platz)
    return plaetze


def test_ac23_sms_kuerzt_vom_listenende_warnung_bleibt(monkeypatch):
    """SMS ueber 160 Zeichen: die vorderen Zeilen der SMS-Liste bleiben (Feuchte, Taupunkt an
    Platz 1/2), die hinteren fallen zuerst; die amtliche Warnung bleibt. Premium-SMS = SMS-Text."""
    data = _trip(sms=[_mc(m, i) for i, m in enumerate(_LANGE_LISTE)], extra=_EXTRA)
    data["official_alerts_enabled"] = True
    for _uid, mit in _zwei_nutzer(monkeypatch, data, warn=True):
        sms = mit.sendungen("sms")[0]["body"]
        assert len(sms) <= 160, sms
        assert re.search(r" !TS:", sms), f"amtliche Warnung muss bleiben: {sms}"
        plaetze = _listenplaetze(sms, _LANGE_LISTE)
        assert plaetze[:2] == [0, 1], f"HU/DP (Platz 1/2) fielen weg: {sms}"
        # Was bleibt, ist ein lueckenloser Anfang der Liste (Schnittlinie).
        erhalten = sorted(set(plaetze))
        assert erhalten == list(range(len(erhalten))), f"Luecke in der Liste: {sms}"
        assert len(erhalten) < len(_LANGE_LISTE)
        assert "TH" not in _symbole(sms), f"Gewitter (letzter Platz) faellt zuerst: {sms}"
        assert mit.sendungen("premium_sms")[0]["body"] == sms


def test_ac23_sms_umgekehrte_liste_kuerzt_andere_seite(monkeypatch):
    """Dieselben Groessen in umgekehrter Folge: jetzt bleiben Gewitter/Regen und HU faellt."""
    liste = list(reversed(_LANGE_LISTE))
    data = _trip(sms=[_mc(m, i) for i, m in enumerate(liste)], extra=_EXTRA)
    data["official_alerts_enabled"] = True
    for _uid, mit in _zwei_nutzer(monkeypatch, data, warn=True):
        sms = mit.sendungen("sms")[0]["body"]
        assert len(sms) <= 160, sms
        assert sms.endswith(" !TS:M@10"), f"amtliche Warnung muss bleiben: {sms}"
        syms = _symbole(sms)
        assert syms[:2] == ["TH", "TH+"] and "PR" in syms and "R" in syms, sms
        assert "HU" not in syms and "DP" not in syms, sms
        erhalten = sorted(set(_listenplaetze(sms, liste)))
        assert erhalten == list(range(len(erhalten))), f"Luecke in der Liste: {sms}"


def test_ac23_zeile_faellt_als_ganzes():
    """Eine Listenzeile mit mehreren Kuerzeln (Temperatur N/D, Gewitter TH:/TH+:) faellt beim
    Kuerzen gemeinsam -- bei keinem Budget bleibt eine halbe Zeile stehen. Echter Builder und
    Renderer, Listenplaetze wie vom Versandpfad gesetzt (``MetricSpec.position``)."""
    from output.tokens.builder import build_token_line
    from output.tokens.dto import DailyForecast, HourlyValue, MetricSpec, NormalizedForecast
    from output.tokens.render import render_line
    from tests.helpers.ampel_allgemein import AMPEL_ALLGEMEIN

    tag = DailyForecast(
        temp_min_c=4.0, temp_max_c=21.0, night_temp_min_c=3.0,
        rain_hourly=(HourlyValue(9, 2.0),), pop_hourly=(HourlyValue(9, 70.0),),
        wind_hourly=(HourlyValue(10, 35.0),), gust_hourly=(HourlyValue(10, 55.0),),
        thunder_hourly=(HourlyValue(15, 2),),
    )
    morgen = DailyForecast(thunder_hourly=(HourlyValue(14, 3),))
    specs = [MetricSpec(symbol=s, enabled=True, position=p) for s, p in (
        ("TH:", 0), ("TH+:", 0), ("R", 1), ("PR", 2), ("W", 3), ("G", 4), ("N", 5), ("D", 5))]

    def zeile(mx: int) -> set[str]:
        line = build_token_line(NormalizedForecast(days=(tag, morgen)), specs,
                                report_type="evening", stage_name="E1", ampel=AMPEL_ALLGEMEIN)
        return set(_symbole(render_line(line, mx)))

    voll = zeile(10_000)
    assert {"N", "D", "TH", "TH+"} <= voll, voll
    wechsel = 0
    for mx in range(12, 80):
        syms = zeile(mx)
        assert ("N" in syms) == ("D" in syms), (mx, syms)
        assert ("TH" in syms) == ("TH+" in syms), (mx, syms)
        wechsel += ("N" in syms) != ("N" in zeile(mx + 1))
    assert wechsel, "Sweep muss den Wegfall der Temperaturzeile ueberstreichen"
