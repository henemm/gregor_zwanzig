"""Pruefkatalog #3047 Runde 7: Einstellungen, die der Katalog bisher umging.

SPEC: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md
(Nachtrag Runde 7; AC-14 Mutations-Gegenprobe). Befunde B-TM3, B-TM4
(Trip) und B-OM-6 (Orte).

Die bisherigen Katalog-Ketten setzen genau an den Stellen Naehte, an denen
diese Einstellungen wirken (Trip: ``render_trip_mit_ausblick`` baut den
Ausblick immer und ruft den Zeitplaner nicht; Orte: ``ComparisonEngine`` ist
vollstaendig ersetzt, ``created_at == target_date``). Hier laufen sie ueber
den ECHTEN Weg bis zur zugestellten Mail:

* Trip, Zeitplaner-Weg: rohes JSON -> ``load_trip`` ->
  ``TripReportSchedulerService._send_trip_report_outcome`` -> Transport-
  Mitschrift. Naehte nur am Wetterabruf (``_fetch_weather``, Offline-Fixture)
  und am Netzabruf der amtlichen Warnungen (``_lade_amtliche_warnungen``
  haengt eine echte ``OfficialAlert`` an -- wird er NICHT gerufen, bleibt die
  Mail warnungsfrei).
* Trip, Versandweg: ``load_trip`` -> ``NotificationService.send_trip_report``
  (Tagesfenster, ``report_config.day_window_*``).
* Orte: echte ``ComparisonEngine`` mit Offline-Fixture-Provider (aus
  ``tests/conftest.py``) -> ``send_one_compare_preset``; Naht nur am Netzabruf
  der Warnungen (``fetch_location_official_alerts``) und am Delta-Anker.

Kein ``Mock()``/``patch()``/``MagicMock``. Echte ``user_id`` je Profil, nie
``"default"``; zwei Nutzer bei den datenbewegenden Schaltern.
"""
from __future__ import annotations

import copy
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import pytest

from app.loader import load_trip
from tests.helpers.ortstag import ortstag
from tests.helpers.transport_mitschrift import Kanalmitschrift, aufzeichner_installieren
from tests.tdd._einstellung_auslieferung_fixtures import TRANSPORT_ENV, frisches_profil
from tests.tdd._einstellung_gleich_mail_trip_fixtures import (
    mail_teile, render_trip_mit_ausblick, sprache_setzen, trip_json,
)

# ===========================================================================
# Trip -- Zeitplaner-Weg
# ===========================================================================

#: Korsika: ausserhalb des DWD-Gebiets (kein Gewittersignal-Netzabruf).
LAT, LON = 42.0, 9.0

#: Nutzer-sichtbare Kennzeichen (feste Zeichenketten, kein Produkt-Resolver).
WARN_TEXT = ("Amtliche Warnung", "Official warning")
AUSBLICK_KOMPAKT = ("3-Tages-Ausblick", "3-day outlook")


def _alarm():
    from services.official_alerts.models import OfficialAlert
    jetzt = datetime.now(timezone.utc)
    return OfficialAlert(
        source="meteofrance_vigilance", hazard="thunderstorm", level=3,
        label="Gewitter", region_label="Pruefregion Runde7",
        valid_from=jetzt - timedelta(hours=2), valid_to=jetzt + timedelta(days=3),
    )


def _scheduler_klasse(abrufe: list):
    from tests.tdd.test_trip_outlook_dispatch_mail import _fixture_scheduler_klasse

    class _S(_fixture_scheduler_klasse()):
        def _lade_amtliche_warnungen(self, segment_weather, segments):
            # Netz-Naht: der Warndienst liefert eine echte Warnung.
            abrufe.append(len(segment_weather))
            for sw in segment_weather:
                sw.official_alerts = [_alarm()]
                sw.official_alerts_unavailable = False
            return []
    return _S


def _trip_roh(*, rc: Optional[dict] = None, official: bool = True) -> dict:
    heute = ortstag(LAT, LON)
    tid = f"runde7-{uuid.uuid4().hex[:8]}"
    stages = [{
        "id": f"S{i}", "name": f"Tag {i}",
        "date": (heute + timedelta(days=i)).isoformat(),
        "waypoints": [
            {"id": f"W{i}a", "name": "Start", "lat": LAT, "lon": LON,
             "elevation_m": 1400, "arrival_calculated": "08:00"},
            {"id": f"W{i}b", "name": "Ziel", "lat": LAT + 0.05, "lon": LON + 0.1,
             "elevation_m": 2100, "arrival_calculated": "12:00"}],
    } for i in range(5)]
    # Folge ungleich der Katalogfolge.
    metrics = [{"metric_id": m, "enabled": True, "bucket": "primary", "order": i}
               for i, m in enumerate(["gust", "precipitation", "temperature", "wind"])]
    r = {"trip_id": tid, "enabled": True, "send_email": True, "send_sms": False,
         "send_telegram": False, "send_premium_sms": False, "email_format": "full",
         "morning_time": "07:00:00", "evening_time": "18:00:00"}
    r.update(rc or {})
    return {"id": tid, "name": "Runde7 Zeitplaner", "stages": stages,
            # #3047 E4: der Editor-Schalter schreibt Briefing- UND Alarm-Feld
            # (Briefing ODER Alarm an -> beides an, PO 2026-11-16).
            "official_alerts_enabled": official, "official_warnings": {"enabled": official},
            "display_config": {"trip_id": tid, "metrics": metrics,
                               "show_night_block": False},
            "report_config": r}


def _zeitplaner_senden(monkeypatch, data: dict, report_type: str, *,
                       mitschrift: Optional[Kanalmitschrift] = None,
                       language: Optional[str] = None,
                       abrufe: Optional[list] = None) -> tuple[dict, str]:
    from tests.helpers.trip_outlook_channels import _settings
    from tests.helpers.trip_outlook_selection import utc_process_tz

    for k, v in TRANSPORT_ENV.items():
        monkeypatch.setenv(k, v)
    mitschrift = mitschrift or aufzeichner_installieren(monkeypatch)
    vorher = len(mitschrift.sendungen("email"))
    uid = frisches_profil()
    if language:
        sprache_setzen(uid, language)
    trip = load_trip(copy.deepcopy(data), user_id=uid)
    with utc_process_tz():
        sched = _scheduler_klasse(abrufe if abrufe is not None else [])(
            settings=_settings(uid), user_id=uid)
        erg = sched._send_trip_report_outcome(trip, report_type, on_demand=True)
    assert erg == "sent", erg
    s = mitschrift.sendungen("email")
    assert len(s) == vorher + 1
    return s[-1], uid


def _texte(s: dict) -> dict[str, str]:
    """Nutzer-sichtbare Teile der Sendung je Format."""
    if s["mail_format"] == "compact":
        return {"kompakt": s["body"]}
    from tests.helpers.einstellung_gleich_mail_trip import html_text
    return {"html": html_text(s["body"]), "klartext": s["plain_text_body"]}


def _hat_ausblick(s: dict) -> dict[str, bool]:
    if s["mail_format"] == "compact":
        return {"kompakt": any(t in s["body"] for t in AUSBLICK_KOMPAKT)}
    from tests.helpers.einstellung_gleich_mail_trip import html_ausblick
    plain = s["plain_text_body"]
    return {"html": html_ausblick(s["body"]) is not None,
            "klartext": "3-Tages-Ausblick" in plain or "3-day outlook" in plain}


# --- B-TM3: Schalter amtliche Warnungen (W20) ------------------------------

@pytest.mark.parametrize("fmt", ["full", "compact"])
@pytest.mark.parametrize("report_type", ["morning", "evening"])
@pytest.mark.parametrize("an", [True, False])
def test_trip_w20_amtliche_warnungen_schalter_wirkt_in_der_mail(
        monkeypatch, an, report_type, fmt):
    abrufe: list = []
    s, _uid = _zeitplaner_senden(monkeypatch, _trip_roh(rc={"email_format": fmt},
                                                         official=an),
                                 report_type, abrufe=abrufe)
    assert bool(abrufe) is an, f"official_alerts_enabled={an}: Abruf {abrufe}"
    for teil, text in _texte(s).items():
        drin = any(w in text for w in WARN_TEXT)
        assert drin is an, (f"{fmt}/{report_type} {teil}: Warnung "
                            f"{'fehlt' if an else 'erscheint trotz Schalter aus'}")


def test_trip_w20_zwei_nutzer(monkeypatch):
    mitschrift = aufzeichner_installieren(monkeypatch)
    sa, ua = _zeitplaner_senden(monkeypatch, _trip_roh(official=True), "evening",
                                mitschrift=mitschrift)
    sb, ub = _zeitplaner_senden(monkeypatch, _trip_roh(official=False), "evening",
                                mitschrift=mitschrift, language="en")
    assert ua != ub and sa["empfaenger"] != sb["empfaenger"]
    assert "Amtliche Warnung" in sa["plain_text_body"]
    assert not any(w in sb["plain_text_body"] for w in WARN_TEXT)


# --- B-TM4: Ausblick „Erscheint im" (multi_day_trend_reports) -------------

@pytest.mark.parametrize("fmt", ["full", "compact"])
@pytest.mark.parametrize("reports", [[], ["morning"], ["evening"],
                                     ["morning", "evening"], None])
@pytest.mark.parametrize("report_type", ["morning", "evening"])
def test_trip_ausblick_erscheint_im(monkeypatch, fmt, reports, report_type):
    rc: dict = {"email_format": fmt}
    if reports is not None:
        rc["multi_day_trend_reports"] = reports
    s, _uid = _zeitplaner_senden(monkeypatch, _trip_roh(rc=rc, official=False),
                                 report_type)
    # Nie eingestellt: Ausblick nur im Abend-Bericht (Vorgabe).
    erwartet = report_type in (reports if reports is not None else ["evening"])
    for teil, wert in _hat_ausblick(s).items():
        assert wert is erwartet, (
            f"{fmt} reports={reports} {report_type} {teil}: Ausblick {wert}, soll {erwartet}")


# --- show_outlook im echten Versand ---------------------------------------
# Ausfuehrlich: der Schalter wirkt. Kompakt: PO-Entscheidung #722, der Editor
# sperrt den Schalter, der Ausblick steht immer drin (kein Fehler, B-P2).

@pytest.mark.parametrize("fmt", ["full", "compact"])
@pytest.mark.parametrize("an", [True, False])
def test_trip_show_outlook_zeitplaner(monkeypatch, fmt, an):
    rc = {"email_format": fmt, "show_outlook": an,
          "multi_day_trend_reports": ["morning", "evening"]}
    s, _uid = _zeitplaner_senden(monkeypatch, _trip_roh(rc=rc, official=False), "evening")
    soll = True if fmt == "compact" else an
    for teil, wert in _hat_ausblick(s).items():
        assert wert is soll, f"{fmt} show_outlook={an} {teil}: Ausblick {wert}, soll {soll}"


# ===========================================================================
# Trip -- Tagesfenster (Versandweg)
# ===========================================================================

def _ueberblick(text: str, fmt: str) -> str:
    """Block „Metriken-Ueberblick" (Kopf bis Leerzeile) je Format."""
    if fmt == "html":
        from tests.helpers.einstellung_gleich_mail_trip import html_text
        text = html_text(text)
    for kopf in ("Metriken-Ueberblick", "Metriken-Überblick"):
        i = text.find(kopf)
        if i >= 0:
            ende = text.find("\n\n", i)
            return text[i:ende if ende > 0 else i + 800]
    raise AssertionError(f"{fmt}: kein Metriken-Ueberblick")


def _stunden(block: str) -> set[int]:
    """Beginn-Uhrzeiten der Schwellen-Pillen („ab HH:00")."""
    return {int(h) for h in re.findall(r"\bab (\d\d):00\b", block)}


@pytest.mark.parametrize("fmt", ["html", "klartext", "kompakt"])
def test_trip_tagesfenster_begrenzt_den_ueberblick(monkeypatch, fmt):
    """Fixture: Boeen ueber der Schwelle ab 04 Uhr. Ohne Einstellung (Vorgabe
    04-19) beginnt die Boeen-Pille „ab 04:00"; mit Tagesfenster 10-14 liegt
    jeder Pillen-Beginn im Fenster."""
    def _mail(rc: dict) -> str:
        if fmt == "kompakt":
            rc = {**rc, "email_format": "compact"}
        data = trip_json(["wind_chill", "gust", "temperature"], report_config=rc)
        m, _t, _u = render_trip_mit_ausblick(monkeypatch, data)
        html, text = mail_teile(m)
        return _ueberblick(html if fmt == "html" else text, fmt)

    vorgabe = _stunden(_mail({}))
    eng = _stunden(_mail({"day_window_start_hour": 10, "day_window_end_hour": 14}))
    assert vorgabe and min(vorgabe) < 10, f"Vorbedingung Vorgabe-Fenster: {vorgabe}"
    assert eng and all(10 <= h <= 14 for h in eng), f"{fmt}: Fenster 10-14, Ueberblick {eng}"


# ===========================================================================
# Orte -- echte ComparisonEngine
# ===========================================================================

ORTE_JETZT = "2026-10-29T04:00:00+00:00"
ORTE_HEUTE = date(2026, 10, 29)


def _orte_versand(roh: dict, monkeypatch, *, language: Optional[str] = None,
                  abend: bool = False) -> tuple[str, list, tuple[str, str, str]]:
    from freezegun import freeze_time

    import services.comparison_engine as ce_mod
    import services.scheduler_dispatch_service as sds_mod
    from app.config import Settings
    from app.loader import get_data_root, load_all_locations
    from services.scheduler_dispatch_service import send_one_compare_preset
    from tests.helpers.amtliche_warnungen_fixture import hitze
    from tests.helpers.einstellung_gleich_mail_orte import (
        orte_anlegen, profil_anlegen, transport_umgebung,
    )
    from tests.tdd._compare_kette_fixtures import preset_ablegen, preset_laden

    abrufe: list = []

    def warn_abruf(lat, lon):  # Netz-Naht: Warndienst
        abrufe.append((lat, lon))
        return [hitze()], False, None

    monkeypatch.setattr(ce_mod, "fetch_location_official_alerts", warn_abruf)
    monkeypatch.setattr(sds_mod, "_write_compare_alert_snapshots", lambda *a, **k: None)
    uid = profil_anlegen(None, language=language)
    orte_anlegen(uid)
    preset_ablegen(uid, roh)
    gesendet: list = []

    def sink(*, subject, body, plain_body):
        gesendet.append((subject, body, plain_body))

    ziel = ORTE_HEUTE + timedelta(days=1 if abend else 0)
    with transport_umgebung(), freeze_time(ORTE_JETZT):
        settings = Settings().with_user_profile(uid)
        preset = preset_laden(uid, roh["id"])
        send_one_compare_preset(
            preset, settings, uid, str(get_data_root()),
            all_locations_cache=load_all_locations(user_id=uid),
            target_date=ziel, tage_ab_ortstag=1 if abend else 0, mail_sink=sink)
    assert len(gesendet) == 1
    return uid, abrufe, gesendet[0]


def _orte_roh(**top) -> dict:
    from tests.helpers.einstellung_gleich_mail_orte import preset_dict
    p = preset_dict("basis")
    p["id"] = "runde7"
    p["name"] = "Runde7 Orte"
    p.update(top)
    return p


def _orte_stunden_html(html: str) -> list[str]:
    """Stundenwerte der ersten Stunden-Tabelle (Kopf „Zeit"/„Time")."""
    from tests.helpers.einstellung_gleich_mail_orte import _tabellen
    for _p, zeilen in _tabellen(html):
        if zeilen and zeilen[0] and zeilen[0][0] in ("Zeit", "Time"):
            return [z[0].zfill(2) + ":00" if re.fullmatch(r"\d\d?", z[0]) else z[0]
                    for z in zeilen[1:]]
    return []


def _orte_stunden_klartext(plain: str) -> list[str]:
    return re.findall(r"^\s{3}(\d\d:\d\d)\s", plain, re.M)


def _ohne_tags(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


# --- Tagesfenster ----------------------------------------------------------

@pytest.mark.parametrize("fenster,erwartet", [
    ((11, 14), ["11:00", "12:00", "13:00", "14:00"]),
    ((22, 2), ["22:00", "23:00", "00:00", "01:00", "02:00"]),  # ueber Mitternacht
])
def test_orte_tagesfenster_wirkt_in_html_und_klartext(monkeypatch, fenster, erwartet):
    roh = _orte_roh(day_window_start_hour=fenster[0], day_window_end_hour=fenster[1])
    _u, _a, (_s, html, plain) = _orte_versand(roh, monkeypatch)
    assert _orte_stunden_html(html) == erwartet
    k = _orte_stunden_klartext(plain)
    assert k[:len(erwartet)] == erwartet and set(k) == set(erwartet), k


def test_orte_tagesfenster_nie_eingestellt_vorgabe(monkeypatch):
    roh = _orte_roh()
    roh.pop("day_window_start_hour", None)
    roh.pop("day_window_end_hour", None)
    _u, _a, (_s, html, _p) = _orte_versand(roh, monkeypatch)
    h = _orte_stunden_html(html)
    assert h[0] == "04:00" and h[-1] == "19:00", h


# --- Schalter amtliche Warnungen, EN-Wortlaut -----------------------------

#: Klartext-Warnzeile je Sprache (fester Wortlaut aus Nutzersicht).
WARN_ZEILE = {"de": "⚠️ Amtliche Warnung: Extreme Hitze",
              "en": "⚠️ Official warning: Heat"}


@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("an", [True, False])
def test_orte_warnschalter_und_wortlaut(monkeypatch, an, lang):
    roh = _orte_roh(official_alerts_enabled=an, official_warnings={"enabled": an})
    _u, abrufe, (_s, html, plain) = _orte_versand(roh, monkeypatch, language=lang)
    html_t = _ohne_tags(html)
    if not an:
        assert abrufe == [], "Schalter aus: kein Abruf beim Warndienst"
        assert "⚠" not in plain
        # Warn-Kuerzel-Legende nennt „Hitze" immer; die Warnung selbst traegt
        # Quelle und Ereignis.
        assert "Météo-France" not in html_t and "Extreme Hitze" not in html_t
        return
    assert len(abrufe) == 3
    zeilen = [z.strip() for z in plain.splitlines() if "⚠" in z]
    assert len(zeilen) == 3, zeilen
    assert all(z.startswith(WARN_ZEILE[lang]) for z in zeilen), (lang, zeilen)
    anders = WARN_ZEILE["en" if lang == "de" else "de"].split(":")[0]
    assert anders not in plain, f"{lang}: Warnzeile in falscher Sprache"


def test_orte_warnschalter_zwei_nutzer(monkeypatch):
    u1, a1, m1 = _orte_versand(_orte_roh(official_alerts_enabled=True, official_warnings={"enabled": True}), monkeypatch)
    u2, a2, m2 = _orte_versand(_orte_roh(official_alerts_enabled=False, official_warnings={"enabled": False}), monkeypatch,
                               language="en")
    assert u1 != u2 and "default" not in (u1, u2)
    assert len(a1) == 3 and a2 == []
    assert "⚠" in m1[2] and "⚠" not in m2[2]


# --- Zieltag im Abend-Briefing --------------------------------------------

@pytest.mark.parametrize("abend", [False, True])
def test_orte_kopfdatum_ist_zieltag(monkeypatch, abend):
    roh = _orte_roh(evening_enabled=True)
    _u, _a, (subj, html, plain) = _orte_versand(roh, monkeypatch, abend=abend)
    ziel = ORTE_HEUTE + timedelta(days=1 if abend else 0)
    erstellt = ORTE_HEUTE
    tage_kurz = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    tage_lang = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag",
                 "Samstag", "Sonntag"]
    datum = ziel.strftime("%d.%m.%Y")
    assert datum in subj
    # Klartext-Kopf: „Datum: <Wochentag>, <Zieltag>"
    kopf = [z for z in plain.splitlines() if z.startswith("Datum")]
    assert kopf == [f"Datum: {tage_lang[ziel.weekday()]}, {datum}"], kopf
    # HTML-Kopf: „<Wt>, <Zieltag>"
    html_t = _ohne_tags(html)
    assert f"{tage_kurz[ziel.weekday()]}, {datum}" in html_t
    if abend:
        falsch = f"{tage_kurz[erstellt.weekday()]}, {erstellt.strftime('%d.%m.%Y')}"
        assert falsch not in html_t, "HTML-Kopf zeigt Erstellungstag statt Zieltag"
