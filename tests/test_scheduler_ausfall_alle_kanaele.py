"""Ausfall, Nachlieferung und eigene Scheduler-Texte in der Nutzersprache
(Issue #2672, AC-3, AC-4 und Restposten aus P9a).

SPEC: docs/specs/modules/i18n_p9b_scheduler_orchestrierung_2672.md

Echter Weg ``TripReportSchedulerService`` -> ``NotificationService`` -> Draht
(``KanalRig``); Wetter ueber den offline ``FixtureProvider`` (leeres Verzeichnis
= echter Totalausfall). Uhr eingefroren auf 2026-10-29T04:00Z. Erwartungen aus
dem Katalog. PO-Korrektur 2026-10-31 (ADR-0104 Praezisierung): SMS bleibt in
jeder Sprache byte-gleich zur deutschen Fassung.
"""
from __future__ import annotations

import re

import pytest
from freezegun import freeze_time

from i18n import t
from i18n.format import fmt_date_numeric, fmt_weekday
from tests.helpers import scheduler_sprache_fixture as fx
from tests.helpers.versand_fixture import rig_starten


@pytest.fixture
def rig(monkeypatch):
    r = rig_starten(monkeypatch)
    yield r
    r.stoppen()


def _ausfall(rig, monkeypatch, tmp_path, lang: str) -> dict:
    with freeze_time(fx.JETZT):
        fx.nutzer_anlegen(f"golden-{lang}", lang)
        return fx.ausfall(rig, monkeypatch, tmp_path, f"golden-{lang}")


def test_ac3_totalausfall_englisch_auf_allen_kanaelen(rig, monkeypatch, tmp_path):
    """AC-3: Mail und Telegram englisch, SMS byte-gleich zur deutschen
    Ausfall-SMS (PO-Korrektur 2026-10-31); Kopf ``X-GZ-Lang: en``."""
    en = _ausfall(rig, monkeypatch, tmp_path, "en")
    de = _ausfall(rig, monkeypatch, tmp_path, "de")
    hinweis = t("versand.hinweis.wetterdienst_ausfall", "en")
    assert en["ausgang"] == "no_weather"
    assert en["mail"]["betreff"] == t("versand.betreff.wetterdaten_fehlen", "en", trip="GR20")
    assert en["mail"]["lang"] == "en"
    assert en["mail"]["plain"].strip() == hinweis
    assert en["telegram"] and en["telegram"][0].endswith(hinweis)
    assert en["sms"] and en["sms"] == de["sms"]
    assert de["mail"]["lang"] == "de"


@pytest.mark.parametrize("fall,schluessel,werte", [
    ("komplett", "versand.scheduler.nachgeliefert", {"stunde": 6}),
    ("vollstaendig", "versand.scheduler.aktualisiert_vollstaendig", {}),
    ("unvollstaendig", "versand.scheduler.aktualisiert_unvollstaendig", {}),
    ("versandfehler", "versand.scheduler.zustellung_fehlgeschlagen", {"stunde": "06:00"}),
])
def test_ac4_nachlieferung_praefix_in_nutzersprache(rig, monkeypatch, tmp_path, fall,
                                                    schluessel, werte):
    """AC-4: die drei Nachlieferungs-Faelle und der Versandfehler-Nachholer
    tragen den Praefix in der Sprache des Nutzers, auf Mail und Telegram;
    die SMS ist in beiden Sprachen gleich."""
    ergebnisse = {}
    for lang in ("en", "de"):
        with freeze_time(fx.JETZT):
            uid = f"golden-{lang}-{fall}"
            fx.nutzer_anlegen(uid, lang)
            ergebnisse[lang] = fx.nachlieferung(rig, monkeypatch, tmp_path, uid, fall)
    for lang, k in ergebnisse.items():
        praefix = t(schluessel, lang, **werte)
        assert k["ergebnis"] == (1, 0)
        assert k["mail"]["lang"] == lang
        assert k["mail"]["plain"].startswith(praefix + "\n\n")
        assert k["telegram"][0].startswith(praefix + "\n\n")
    assert ergebnisse["en"]["sms"] == ergebnisse["de"]["sms"]
    if fall == "unvollstaendig":
        ziel = t("versand.scheduler.abschnitt", "en", id=t("alarm.segment.ziel", "en"))
        assert t("versand.scheduler.teilausfall", "en", abschnitte=ziel) in \
            ergebnisse["en"]["mail"]["plain"]


def test_servicefehler_mail_rumpf_betreff_und_kopf_in_einer_sprache(rig, monkeypatch, tmp_path):
    """Restposten P9a: SMS-only-Trip mit Teilausfall -- die Service-Mail ist
    in Rumpf, Betreff und ``X-GZ-Lang`` englisch (Kopf = Inhaltssprache)."""
    with freeze_time(fx.JETZT):
        fx.nutzer_anlegen("golden-en", "en")
        s = fx.servicefehler(rig, monkeypatch, tmp_path, "golden-en")
    service = [m for m in s["mails"] if "Weather data unavailable" in m["betreff"]]
    assert len(service) == 1, [m["betreff"] for m in s["mails"]]
    assert service[0]["lang"] == "en"
    roh = next(r for r in s["roh"] if "Weather data unavailable" in r)
    for key in ("titel", "problem", "segmente", "grund", "fusszeile"):
        assert t(f"versand.servicefehler.{key}", "en") in _html_text(roh)
    assert "Wetterdaten" not in _html_text(roh)
    # F001: das ausgefallene Ziel-Segment heisst wie im Teilausfall-Hinweis.
    ziel = t("versand.scheduler.abschnitt", "en", id=t("alarm.segment.ziel", "en"))
    assert f"  - {ziel}: " in _html_text(roh)
    assert "Segment Ziel" not in _html_text(roh)


def test_servicefehler_mail_ziel_segment_deutsch_unveraendert(rig, monkeypatch, tmp_path):
    """Gegenprobe zu F001: deutsch bleibt die Zeile ``  - Segment Ziel: …``."""
    with freeze_time(fx.JETZT):
        fx.nutzer_anlegen("golden-de", "de")
        s = fx.servicefehler(rig, monkeypatch, tmp_path, "golden-de")
    roh = next(r for r in s["roh"] if "Wetterdaten nicht verfuegbar" in r)
    assert "  - Segment Ziel: " in _html_text(roh)


def _html_text(roh: str) -> str:
    import email

    msg = email.message_from_string(roh)
    for teil in msg.walk():
        if teil.get_content_type() == "text/html":
            return teil.get_payload(decode=True).decode(teil.get_content_charset() or "utf-8")
    return ""


def test_ausblick_wochentag_trend_notiz_und_gewitter_vorschau(rig, monkeypatch, tmp_path):
    """Eigene Bausteine der Etappen-Vorschau: Wochentag und Trend-Notiz der
    Ausblick-Zeile sowie Gewitter-Vorschau (Trend-Weg UND Abruf-Weg) in der
    Sprache des Dienstobjekts."""
    from utils.timezone import tz_for_coords

    tz = tz_for_coords(*fx.INNSBRUCK)
    texte = {}
    with freeze_time(fx.JETZT):
        fx.wetter(monkeypatch, tmp_path, "sturm")
        for lang in ("de", "en"):
            uid = f"golden-{lang}-ausblick"
            fx.nutzer_anlegen(uid, lang)
            trip = fx.trip_mehrtaegig(uid)
            svc = fx.scheduler(rig, uid)
            zeilen = svc._build_stage_trend(trip, fx.TAG, now_utc=fx.JETZT).rows
            trend = svc._build_thunder_forecast_from_trend_or_fetch(
                trip, fx.TAG, fx.JETZT, tz, multi_day_trend=zeilen)
            abruf = svc._build_thunder_forecast_from_trend_or_fetch(trip, fx.TAG, fx.JETZT, tz)
            texte[lang] = (zeilen, trend, abruf)
    for lang, (zeilen, trend, abruf) in texte.items():
        assert [z["weekday"] for z in zeilen] == [fmt_weekday(z["date"], lang) for z in zeilen]
        notiz = zeilen[0]["note"]
        assert notiz.startswith(t("versand.scheduler.trend_gewitter", lang) + " · ")
        assert t("versand.scheduler.trend_boeen", lang, kmh=50) in notiz
        assert re.search(re.escape(t("versand.scheduler.trend_regen", lang, mm="X"))
                         .replace("X", r"\d+"), notiz)
        for vorschau in (trend, abruf):
            eintrag = vorschau["+1"]
            assert eintrag["date"] == fmt_date_numeric(zeilen[0]["date"], lang)
            satz = "Thunderstorm possible from " if lang == "en" else "Gewitter möglich ab "
            assert eintrag["text"].startswith(satz), eintrag["text"]


def test_ungueltiger_ortsvergleich_grund_in_nutzersprache(monkeypatch):
    """Restposten P9a (d): ``invalid_preset`` nennt den Grund (geloeschte Orte)
    in der Sprache des Nutzers -- kein deutscher Satz im englischen Text."""
    from fastapi.testclient import TestClient

    from api.main import app
    from tests.helpers.compare_briefings import write_compare_briefings
    from app.loader import get_data_dir

    antworten = {}
    for lang in ("en", "de"):
        uid = f"golden-{lang}-ungueltig"
        fx.nutzer_anlegen(uid, lang)
        write_compare_briefings(get_data_dir(uid), [{
            "id": "cp-weg", "name": "Weg", "kind": "vergleich", "schedule": "daily",
            "location_ids": ["geloescht-1"], "created_at": "2026-10-01T00:00:00Z",
        }])
        r = TestClient(app).post(f"/api/briefings/cp-weg/send?kind=vergleich&user_id={uid}")
        antworten[lang] = (r.status_code, r.json())
    for lang, (status, body) in antworten.items():
        grund = t("versand.grund.orte_geloescht", lang, preset_id="cp-weg",
                  orte="['geloescht-1']")
        assert status == 422 and body["code"] == "invalid_preset"
        assert body["detail"] == t("versand.ergebnis.invalid_preset", lang, reason=grund)
