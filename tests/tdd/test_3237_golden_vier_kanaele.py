"""#3237: Golden-Schnappschuss aller vier Kanaele vor/nach dem Altpfad-Rueckbau.

SPEC: docs/specs/modules/feat_3237_altpfad_entfernen.md, AC-5, AC-6.

* AC-5: Abos MIT Tabelle (Trip und Orts-Vergleich, mehrere Formen und
  Haken) werden ueber den echten Versandweg in allen vier Kanaelen (Mail
  HTML + Text, Telegram, SMS, Premium-SMS) erzeugt und gegen den VOR der
  Loeschung aufgenommenen Schnappschuss ``tests/fixtures/golden_3237/``
  zeichengleich verglichen. Er ersetzt das Differenz-Orakel.
* AC-6 (AC-38 aus #3122): dasselbe Abo mit nachtraeglich gesetzten
  Altfeldern liefert je Kanal byte-gleich dieselbe Ausgabe wie ohne.

Aufnahme (nur vor der Loeschung, einmalig): ``GZ_GOLDEN_3237_AUFNEHMEN=1``.

Kern-Schicht: echte Renderer und Versandwege; ersetzt sind allein die
Transporte (Aufzeichner/Sinks) und der Wetterabruf (feste Datensaetze
``segment``/``placements_beispiel``). Kein Mock. Datumsangaben der Etappen
sind fest; Erzeugungsdatum und -uhrzeit werden neutralisiert, damit der
Schnappschuss nicht vom Testtag abhaengt.
"""
from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path

import pytest

GOLDEN = Path(__file__).parents[1] / "fixtures" / "golden_3237"

#: Gestellte Wanduhr (F001, Adversary #3237): Der Schnappschuss wurde am
#: 22.11.2026 um 06:08 UTC (07:08 Ortszeit) aufgenommen. Die Renderer datieren
#: in der Ortszone des Abos (Trip ``Europe/Paris`` aus ``_einstellung_auslieferung_fixtures.TZ``,
#: Orte bei 47.27/11.39 ``Europe/Vienna``; html.py ``local_dt(sent_at, tz)``,
#: compare_html ``_compute_next_send`` -> ``next_compare_briefing`` in der Ortszone).
#: Nach 23:00 UTC ist dort schon der Folgetag, und "Naechster Versand" haengt
#: zusaetzlich an der Tageszeit relativ zum Morgen-Slot. Die Uhr steht deshalb
#: auf einem festen Zeitpunkt NACH dem Morgen-Slot und weit weg von Mitternacht
#: in UTC wie in der Ortszone; ``tick=True``, damit Zeitmessungen weiterlaufen.
GESTELLTE_UHR = "2026-11-22T12:00:00+00:00"
#: Zone, in der die Renderer das Erzeugungsdatum schreiben (s. o.).
RENDER_ZONE = "Europe/Paris"
AUFNEHMEN = os.environ.get("GZ_GOLDEN_3237_AUFNEHMEN") == "1"
ETAPPEN_DATEN = ("2026-07-19", "2026-07-20", "2026-07-21")

TRIP_FOLGE = ["temperature", "wind", "gust", "precipitation", "rain_probability",
              "cloud_total", "uv_index", "thunder"]

#: Trip-Tabellen: Haken je Stelle und Formen (raw/simplified) variieren.
TRIP_TABELLEN = {
    "trip_voll": {"version": 1, "rows": [], "outlook_reports": ["evening"]},
    "trip_gemischt": {"version": 1, "rows": [
        {"metric_id": "gust", "places": {"email": True, "telegram": True, "sms": True, "outlook": True},
         "formats": {"email": "raw", "telegram": "simplified", "outlook": "simplified"}},
        {"metric_id": "wind", "places": {"email": True, "telegram": False, "sms": True, "outlook": False},
         "formats": {"email": "simplified"}},
        {"metric_id": "precipitation", "places": {"email": False, "telegram": True, "sms": True,
                                                  "outlook": True}},
        {"metric_id": "cloud_total", "places": {"email": True, "telegram": True, "sms": False,
                                                "outlook": True},
         "formats": {"email": "raw", "telegram": "raw"}},
    ], "outlook_reports": ["morning", "evening"]},
}

TRIP_ALTFELDER = {
    "channel_layouts": {"email": [{"metric_id": "wind", "enabled": True}],
                        "sms": [{"metric_id": "uv_index", "enabled": True}]},
    "channel_layouts_per_report": {"evening": {"telegram": [{"metric_id": "thunder"}]}},
    "outlook_metrics": [],
    "outlook_metric_formats": {"gust": False},
    "channel_active_metrics": {"email": ["wind"]},
}
TRIP_RC_ALT = {"show_outlook": False}

ORTE_TABELLEN = {
    "orte_voll": {"version": 1, "rows": [], "outlook_reports": ["morning"]},
    "orte_gemischt": {"version": 1, "rows": [
        {"metric_id": "wind", "places": {"email": True, "telegram": True, "sms": True,
                                         "hourly": True, "outlook": True},
         "formats": {"email": "simplified", "hourly": "raw"}},
        {"metric_id": "temperature", "places": {"email": True, "telegram": False, "sms": True,
                                                "hourly": False, "outlook": True}},
        {"metric_id": "precipitation", "places": {"email": False, "telegram": True, "sms": False,
                                                  "hourly": True, "outlook": False}},
    ], "outlook_reports": ["morning"]},
}
ORTE_ALTFELDER = {
    "channel_layouts": {"email": [{"metric_id": "wind_max", "enabled": True}],
                        "sms": [{"metric_id": "temp_max", "enabled": True}]},
    "outlook_metrics": ["wind_max"],
    "outlook_metrics_formats": {"wind_max": True},
    "channel_active_metrics": {"telegram": ["wind_max"]},
    "hourly_metrics": ["wind"],
}

_DATUM = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?(\.\d+)?([+-]\d{2}:\d{2}|Z)?\b")
#: Erzeugungsuhrzeit im Mail-Kopf ("07:03 (CET)", "· 07:04 CET").
_WOCHENTAG = re.compile(r"\b(Mo|Di|Mi|Do|Fr|Sa|So|Mon|Tue|Wed|Thu|Fri|Sat|Sun) · <HEUTE")
#: Kopfzeile "So · 07:06" (Wochentag des Erzeugungstags, Uhrzeit ohne Zone).
_WT_UHRZEIT = re.compile(r"\b(Mo|Di|Mi|Do|Fr|Sa|So|Mon|Tue|Wed|Thu|Fri|Sat|Sun) · \d{2}:\d{2}\b")
_UHRZEIT = re.compile(r"\b\d{2}:\d{2} \(?(CET|CEST|UTC)\)?")


@pytest.fixture(autouse=True)
def _gestellte_uhr():
    """Alle Faelle dieser Datei laufen unter derselben gestellten Uhr (F001)."""
    import pydantic.v1.types  # noqa: F401  (vor dem Einfrieren laden, s. conftest)
    from freezegun import freeze_time

    with freeze_time(GESTELLTE_UHR, tick=True):
        yield


def _normalisiert(text: str) -> str:
    """Nur Zeitstempel des Erzeugungszeitpunkts (ISO mit Uhrzeit, Kopf-Uhrzeit) werden
    neutralisiert; Inhalte, Tagesdaten und Reihenfolgen bleiben."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    text = _UHRZEIT.sub("<UHRZEIT>", _DATUM.sub("<ZEIT>", text))
    # Erzeugungs- und Folgedatum ("Erstellt: 22.11.2026", "So · 22.11.2026")
    # haengen am Testtag; die Wetterdaten der Fixtures liegen fest im Juli 2026.
    # "Heute" aus derselben Zone wie der Renderer (nicht date.today() = Prozesszone).
    heute = datetime.now(ZoneInfo(RENDER_ZONE)).date()
    for versatz in range(-2, 4):
        tag = heute + timedelta(days=versatz)
        for form in (tag.isoformat(), tag.strftime("%d.%m.%Y")):
            text = text.replace(form, f"<HEUTE{versatz:+d}>")
    text = _WT_UHRZEIT.sub("<WT> · <UHRZEIT>", text)
    return _WOCHENTAG.sub(r"<WT> · <HEUTE", text)


def _vergleich(name: str, ausgabe: dict[str, str]) -> None:
    pfad = GOLDEN / f"{name}.json"
    ausgabe = {k: _normalisiert(v) for k, v in ausgabe.items()}
    if AUFNEHMEN:
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(json.dumps(ausgabe, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                        encoding="utf-8")
    assert pfad.exists(), f"Schnappschuss fehlt: {pfad} (vor der Loeschung aufnehmen)"
    soll = json.loads(pfad.read_text(encoding="utf-8"))
    assert sorted(ausgabe) == sorted(soll), (sorted(ausgabe), sorted(soll))
    for kanal in soll:
        assert ausgabe[kanal] == soll[kanal], f"{name}: Kanal {kanal} weicht ab"


# ---------------------------------------------------------------------------
# Trip
# ---------------------------------------------------------------------------

def _trip_daten(tabelle: dict, *, alt: bool) -> dict:
    from tests.tdd._einstellung_gleich_mail_trip_fixtures import trip_json

    rc = {"send_sms": True, "send_telegram": True, "send_premium_sms": True,
          "morning_enabled": True, "evening_enabled": True}
    if alt:
        rc.update(TRIP_RC_ALT)
    daten = trip_json(TRIP_FOLGE, einfach={"wind", "thunder"}, report_config=rc,
                      display={"placements": copy.deepcopy(tabelle),
                               **(copy.deepcopy(TRIP_ALTFELDER) if alt else {})})
    for etappe, tag in zip(daten["stages"], ETAPPEN_DATEN):
        etappe["date"] = tag
    return daten


def _trip_ausgabe(monkeypatch, daten: dict, report_type: str) -> dict[str, str]:
    from tests.tdd._einstellung_gleich_mail_trip_fixtures import render_trip_mit_ausblick

    mit, _trip, _uid = render_trip_mit_ausblick(
        monkeypatch, daten, report_type=report_type, ausblick_nach_zeitplaner=True)
    mail = mit.sendungen("email")
    assert len(mail) == 1, mit
    aus = {"mail_html": mail[0]["body"], "mail_text": mail[0]["plain_text_body"] or ""}
    for kanal in ("telegram", "sms", "premium_sms"):
        sendungen = mit.sendungen(kanal)
        assert sendungen, f"Vorbedingung: {kanal} bedient ({mit!r})"
        aus[kanal] = "\n---\n".join(s["body"] or "" for s in sendungen)
    return aus


@pytest.mark.parametrize("report_type", ["morning", "evening"])
@pytest.mark.parametrize("name", sorted(TRIP_TABELLEN))
def test_ac5_trip_vier_kanaele_gleich_golden(monkeypatch, name, report_type):
    ausgabe = _trip_ausgabe(monkeypatch, _trip_daten(TRIP_TABELLEN[name], alt=False), report_type)
    _vergleich(f"{name}_{report_type}", ausgabe)


@pytest.mark.parametrize("report_type", ["morning", "evening"])
@pytest.mark.parametrize("name", sorted(TRIP_TABELLEN))
def test_ac6_trip_altfelder_aendern_keinen_kanal(monkeypatch, name, report_type):
    sauber = _trip_ausgabe(monkeypatch, _trip_daten(TRIP_TABELLEN[name], alt=False), report_type)
    mit_alt = _trip_ausgabe(monkeypatch, _trip_daten(TRIP_TABELLEN[name], alt=True), report_type)
    for kanal in sauber:
        assert _normalisiert(mit_alt[kanal]) == _normalisiert(sauber[kanal]), kanal


# ---------------------------------------------------------------------------
# Orts-Vergleich
# ---------------------------------------------------------------------------

@pytest.fixture
def orte_env(tmp_path, monkeypatch):
    from app import loader as app_loader
    from tests.tdd.test_compare_premium_sms_versand import _ENV

    data_root = tmp_path / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_loader, "_DATA_ROOT", str(data_root))
    for k, v in _ENV.items():
        monkeypatch.setenv(k, v)
    _beispiel_wetter(monkeypatch)
    return tmp_path


def _beispiel_wetter(monkeypatch) -> None:
    import services.comparison_engine as ce_mod
    import services.scheduler_dispatch_service as sds_mod
    from services import placements_beispiel as pb

    class BeispielEngine(ce_mod.ComparisonEngine):
        @staticmethod
        def run(*args, **kwargs):
            orte = kwargs.get("locations")
            if orte is None and args:
                orte = args[0]
            return pb.orte_ergebnis(list(orte or []))

    monkeypatch.setattr(ce_mod, "ComparisonEngine", BeispielEngine)
    monkeypatch.setattr(sds_mod, "_write_compare_alert_snapshots", lambda *a, **k: None)


def _orte_preset(uid: str, orte, tabelle: dict, *, alt: bool) -> dict:
    dc = {"active_metrics": [
        {"metric_id": "temperature", "aggregation": "max"},
        {"metric_id": "temperature", "aggregation": "min"},
        {"metric_id": "wind", "aggregation": "max"},
        {"metric_id": "gust", "aggregation": "max"},
        {"metric_id": "precipitation", "aggregation": "sum"},
        {"metric_id": "cloud_total", "aggregation": "avg"},
    ], "placements": copy.deepcopy(tabelle)}
    if alt:
        dc.update(copy.deepcopy(ORTE_ALTFELDER))
    return {
        "id": "cp-3237", "name": "Golden", "user_id": uid, "kind": "vergleich",
        "location_ids": [o.id for o in orte], "schedule": "daily", "profil": "ALLGEMEIN",
        "hour_from": 9, "hour_to": 16, "forecast_hours": 48,
        "empfaenger": ["gregor-test@henemm.com"], "created_at": "2026-07-01T00:00:00Z",
        "morning_enabled": True, "evening_enabled": False, "hourly_enabled": True,
        "send_sms": True, "send_premium_sms": True, "send_telegram": True,
        "alert_channels": {"email": True, "telegram": True, "sms": True, "premium_sms": True},
        "display_config": dc,
    }


def _orte_ausgabe(orte_env, tabelle: dict, *, alt: bool) -> dict[str, str]:
    from app.config import Settings
    from app.user import SavedLocation
    from services import placements_beispiel as pb
    from services.scheduler_dispatch_service import send_one_compare_preset
    from tests.tdd.test_compare_premium_sms_versand import _nutzer

    uid = _nutzer("pgold-3237")
    orte = [SavedLocation(id=f"g3237-{i}", name=n, lat=47.27, lon=11.39 + 0.1 * i,
                          elevation_m=600) for i, n in enumerate(("Aabenraa", "Flensburg"))]
    gesehen: dict[str, list] = {"mail": [], "sms": [], "premium_sms": [], "telegram": []}
    send_one_compare_preset(
        _orte_preset(uid, orte, tabelle, alt=alt), Settings(), uid, str(orte_env),
        all_locations_cache=orte, target_date=pb.TAG, tage_ab_ortstag=0,
        mail_sink=lambda **k: gesehen["mail"].append(k),
        sms_sink=gesehen["sms"].append, premium_sms_sink=gesehen["premium_sms"].append,
        telegram_sink=gesehen["telegram"].append, report_type="morning",
    )
    assert len(gesehen["mail"]) == 1, gesehen
    mail = gesehen["mail"][0]
    aus = {"mail_html": mail.get("body") or "", "mail_text": mail.get("plain_body") or ""}
    for kanal in ("telegram", "sms", "premium_sms"):
        assert gesehen[kanal], f"Vorbedingung: {kanal} bedient ({gesehen!r})"
        aus[kanal] = "\n---\n".join(str(t) for t in gesehen[kanal])
    return aus


@pytest.mark.parametrize("name", sorted(ORTE_TABELLEN))
def test_ac5_orte_vier_kanaele_gleich_golden(orte_env, name):
    _vergleich(name, _orte_ausgabe(orte_env, ORTE_TABELLEN[name], alt=False))


@pytest.mark.parametrize("name", sorted(ORTE_TABELLEN))
def test_ac6_orte_altfelder_aendern_keinen_kanal(orte_env, name):
    sauber = _orte_ausgabe(orte_env, ORTE_TABELLEN[name], alt=False)
    mit_alt = _orte_ausgabe(orte_env, ORTE_TABELLEN[name], alt=True)
    for kanal in sauber:
        assert _normalisiert(mit_alt[kanal]) == _normalisiert(sauber[kanal]), kanal
