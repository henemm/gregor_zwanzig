"""#3047 Runde 7, Paket p7 (Trip-Telegram-Fenster): Befund B-L1.

SPEC: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md,
"Nachtrag Runde 7" (AC-22, Kanal-Paritaet ADR-0095) mit ADR-0035 ("ein
Tagesfenster, wirksam auf Anzeige und Bewertung"). Tech-Lead-Entscheidung
Runde 7 (B-L1): die Telegram-Kurzuebersicht bewertet ALLE Groessen im
Tagesfenster wie SMS und Mail; die Scheibenregel #1498 ("nur Gewitter
wechselt aufs Fenster, alle uebrigen bleiben bei der Gehzeit") ist fuer die
Kurzuebersicht abgeloest. Temperatur/gefuehlte Temperatur bleiben bei der
Gehzeit-Spanne -- dieselbe Quelle, aus der SMS (``N``/``D``) und die
Mail-Kachel ("Max 08:00") lesen (#1417).

Echter Weg: Trip-JSON (Persistenzformat) -> ``load_trip`` ->
``NotificationService.send_trip_report`` -> Transport-Mitschrift. Je Fall
zwei frische Nutzer, DE und EN. Die Wetter-Naht liefert eine Etappe 08-12
Uhr (Ortszeit) mit Boeen 80 km/h um 08 Uhr (Gehzeit, aber VOR dem Fenster
10-19) und sonst 45 km/h, Regen 2.0 mm je Stunde; am Ziel nach der Ankunft
(``night_weather``) Boeen 60 km/h um 16 Uhr (im Fenster, nach der Gehzeit) und
90 km/h um 21 Uhr (nach dem Fensterende 19).
"""
from __future__ import annotations

import dataclasses
import json
import re

import pytest

from app.loader import get_data_dir, load_trip
from app.models import NormalizedTimeseries
from services.notification_service import NotificationService, TripReportRequest
from tests.helpers.transport_mitschrift import aufzeichner_installieren
from tests.tdd._einstellung_auslieferung_fixtures import (
    STAGE_NAME, TRANSPORT_ENV, TZ, frisches_profil, golden_dict, night_weather, segment,
)
from utils.timezone import local_hour

#: von Hand: Grundauswahl (Folge != Katalog); Telegram/SMS ohne eigene Liste.
GRUNDAUSWAHL = ["gust", "precipitation", "temperature", "wind", "uv_index", "thunder"]
#: von Hand: Kopf der Kurzuebersicht je Sprache.
KOPF = {"de": "Kurzübersicht", "en": "Summary"}


def _trip(fenster: tuple[int, int] | None) -> dict:
    d = golden_dict("golden_c")
    d["display_config"]["metrics"] = [
        {"metric_id": m, "enabled": True, "bucket": "primary", "order": i,
         "use_friendly_format": True}
        for i, m in enumerate(GRUNDAUSWAHL)
    ]
    d["display_config"]["channel_layouts"] = {}
    d["display_config"]["outlook_metrics"] = []
    d["report_config"]["telegram_style"] = "rich"
    if fenster is not None:
        d["report_config"]["day_window_start_hour"] = fenster[0]
        d["report_config"]["day_window_end_hour"] = fenster[1]
    else:
        d["report_config"].pop("day_window_start_hour", None)
        d["report_config"].pop("day_window_end_hour", None)
    return d


def _etappe():
    """Etappe 08-12: Boeenspitze 80 km/h um 08 Uhr Ortszeit, sonst 45."""
    seg = segment()
    data = [
        dataclasses.replace(dp, gust_kmh=80.0) if local_hour(dp.ts, TZ) == 8 else dp
        for dp in seg.timeseries.data
    ]
    seg.timeseries = NormalizedTimeseries(meta=seg.timeseries.meta, data=data)
    return seg


def _nacht():
    """Ziel-Zeitreihe nach der Ankunft: Boeen 60 km/h um 16, 90 km/h um 21 Uhr."""
    nw = night_weather()
    spitzen = {16: 60.0, 21: 90.0}
    data = [
        dataclasses.replace(dp, gust_kmh=spitzen[local_hour(dp.ts, TZ)])
        if local_hour(dp.ts, TZ) in spitzen and dp.ts.date() == nw.data[0].ts.date() else dp
        for dp in nw.data
    ]
    return NormalizedTimeseries(meta=nw.meta, data=data)


def _senden(monkeypatch, data: dict, lang: str):
    for k, v in TRANSPORT_ENV.items():
        monkeypatch.setenv(k, v)
    mit = aufzeichner_installieren(monkeypatch)
    uid = frisches_profil()
    p = get_data_dir(uid) / "user.json"
    u = json.loads(p.read_text())
    u["language"] = lang
    p.write_text(json.dumps(u))
    trip = load_trip(data, user_id=uid)
    rc = trip.report_config
    req = TripReportRequest(
        trip=trip, report_type="evening", segment_weather=[_etappe()], trip_tz=TZ,
        night_weather=_nacht(), stage_name=STAGE_NAME, report_config=rc,
        display_config=trip.display_config, send_email=rc.send_email, send_sms=rc.send_sms,
        send_telegram=rc.send_telegram, send_premium_sms=rc.send_premium_sms)
    erg = NotificationService(user_id=uid).send_trip_report(req)
    assert erg.sent, erg
    assert set(mit.empfaenger("telegram")) == {f"chat-{uid}"}
    assert mit.empfaenger("email") == [f"{uid}@example.invalid"]
    return uid, mit


def _kurzuebersicht(mit, lang: str) -> str:
    for s in mit.sendungen("telegram"):
        if s["body"].startswith(KOPF[lang]):
            return s["body"]
    raise AssertionError(f"keine Kurzuebersicht: {mit.sendungen('telegram')}")


def _tg(ov: str, kuerzel: str) -> tuple[str, int | None]:
    """Telegram-Zeile ``G 45@10`` bzw. ``G 45@04-80@08`` -> (Spitzenwert, Stunde)."""
    zeile = next(z for z in ov.splitlines() if z.startswith(f"{kuerzel} "))
    m = re.fullmatch(rf"{kuerzel} (?:[\d.]+(?:@\d+)?-)?([\d.]+)(?:@(\d+))?", zeile)
    assert m, zeile
    return m.group(1), (int(m.group(2)) if m.group(2) else None)


def _sms(sms: str, kuerzel: str) -> tuple[str, int]:
    """SMS-Token ``G45@10`` bzw. ``G45@4(80@8)`` -> (Spitzenwert, Stunde)."""
    m = re.search(rf"\b{kuerzel}([\d.]+)@(\d+)(?:\(([\d.]+)@(\d+)\))?", sms)
    assert m, (kuerzel, sms)
    if m.group(3):
        return m.group(3), int(m.group(4))
    return m.group(1), int(m.group(2))


def _stunden(ov: str) -> list[int]:
    """Alle ``@h``-Stunden der Kurzuebersicht."""
    return [int(h) for h in re.findall(r"@(\d+)", ov)]


def _fall(monkeypatch, fenster, lang):
    nutzer = [_senden(monkeypatch, _trip(fenster), lang) for _ in range(2)]
    assert nutzer[0][0] != nutzer[1][0]
    return nutzer


@pytest.mark.parametrize("lang", ["de", "en"])
def test_b_l1_fenster_10_19_kurzuebersicht_wie_sms(monkeypatch, lang):
    """Given Tagesfenster 10-19, Boeenspitze 80 um 08 (vor dem Fenster) /
    When das Briefing ueber den echten Weg verschickt wird / Then nennt die
    Telegram-Kurzuebersicht fuer Boeen und Regen denselben Spitzenwert und
    dieselbe Stunde wie die SMS (60@16 nach der Ankunft, 2.0@10) und keine
    Stunde vor 10."""
    for uid, mit in _fall(monkeypatch, (10, 19), lang):
        ov = _kurzuebersicht(mit, lang)
        sms = mit.sendungen("sms")[0]["body"]
        # von Hand: im Fenster 10-19 liegt die Boeenspitze bei 60 um 16 Uhr
        assert _sms(sms, "G") == ("60", 16), sms
        assert _sms(sms, "R") == ("2.0", 10), sms
        assert _tg(ov, "G") == ("60", 16), f"{uid}: {ov}"
        assert _tg(ov, "R") == ("2.0", 10), f"{uid}: {ov}"
        assert min(_stunden(ov)) >= 10, f"Stunde vor dem Fenster 10-19: {ov}"
        assert "80" not in ov, f"Boeenspitze vor dem Fenster in der Kurzuebersicht: {ov}"
        assert "90" not in ov, f"Boeenspitze nach dem Fensterende in der Kurzuebersicht: {ov}"
        mail = mit.sendungen("email")[0]["plain_text_body"]
        assert "10:00" in mail and "max 60 (16:00)" in mail, mail[:600]


@pytest.mark.parametrize("lang", ["de", "en"])
def test_b_l1_fenster_nie_eingestellt_standard_4_19(monkeypatch, lang):
    """Given kein Tagesfenster gespeichert (Standard 4-19) / When das Briefing
    verschickt wird / Then nennt Telegram fuer Regen die Stunde 04 wie die
    SMS, und die Boeenspitze 80 um 08 (im Fenster) in beiden Kanaelen."""
    for uid, mit in _fall(monkeypatch, None, lang):
        ov = _kurzuebersicht(mit, lang)
        sms = mit.sendungen("sms")[0]["body"]
        assert _sms(sms, "R") == ("2.0", 4), sms
        assert _sms(sms, "G") == ("80", 8), sms
        assert _tg(ov, "R") == ("2.0", 4), f"{uid}: {ov}"
        assert _tg(ov, "G") == ("80", 8), f"{uid}: {ov}"
        assert max(_stunden(ov)) <= 19, f"Stunde nach dem Fensterende: {ov}"
        assert min(_stunden(ov)) == 4, f"Fensterbeginn 04 fehlt: {ov}"


@pytest.mark.parametrize("fenster", [(10, 19), None])
def test_b_l1_temperatur_bleibt_gehzeit_wie_mail(monkeypatch, fenster):
    """Temperatur folgt in allen Kanaelen der Gehzeit-Spanne (#1417): Telegram
    und SMS zeigen dieselbe Spanne (Fixture 15.0 durchgehend)."""
    for uid, mit in _fall(monkeypatch, fenster, "de"):
        ov = _kurzuebersicht(mit, "de")
        sms = mit.sendungen("sms")[0]["body"]
        assert "D15/15" in sms, sms
        assert _tg(ov, "T")[0] == "15.0", ov


@pytest.mark.parametrize("fenster", [(10, 19), None])
def test_stundentabelle_telegram_gleiche_stunden_wie_mail(monkeypatch, fenster):
    """Pruefung "Stundentabelle beachtet das Fenster": Telegram-Etappentabelle
    zeigt dieselben Stunden wie die Etappentabelle der Mail (Kanal-Paritaet)."""
    for uid, mit in _fall(monkeypatch, fenster, "de"):
        tabelle = next(s["body"] for s in mit.sendungen("telegram") if "<pre>" in s["body"])
        tg_std = [z.split()[0] for z in tabelle.split("<pre>")[1].split("</pre>")[0]
                  .strip().splitlines()[1:]]
        mail = mit.sendungen("email")[0]["plain_text_body"]
        etappe = mail.split("━━ Segment 1")[1].split("━━ Nacht")[0]
        mail_std = [z.split()[0] for z in etappe.splitlines()
                    if re.match(r"^\s+\d\d\s", z)]
        assert tg_std == mail_std, (tg_std, mail_std)
