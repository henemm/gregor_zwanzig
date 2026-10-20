"""Gemeinsamer Aufbau fuer den Handversand-Endpoint (#2280, Epic #2345 P4).

Kein Test-Modul (fuehrender Unterstrich). Geteilt von
``test_briefings_send_endpoint.py`` (AC-1..3, AC-9, AC-10, AC-13) und
``test_compare_preset_send.py`` (AC-4..8).

Naehte -- ausschliesslich zum Netz bzw. zur Konfigurationslage, nie zur
Entscheidung, die geprueft wird:

* Trip-Wetter: Provider-Double auf echte, aufgezeichnete Innsbruck-Fixturdaten
  (Muster ``tests/unit/test_trip_send_endpoint_no_channels.py``).
* Trip-E-Mail: ``NotificationService._send_email`` schreibt mit statt zu senden.
* Ortsvergleich-Wetter: ``engine_naht`` (echte Engine-Subklasse) aus
  ``_compare_kette_fixtures``; Ausfall-Variante wirft fuer JEDEN Ort.
* Ortsvergleich-Transport: geteilter Aufzeichner ``transport_mitschrift``;
  Ausfall-Variante: Telegram-Ausgang wirft beim Senden (fail-soft-Pfad).
* Ortsvergleich-Kanallage: ausschliesslich ECHTE Daten -- Preset-Opt-ins
  ``send_telegram``/``send_sms`` und das Konto-Profil (mit/ohne ``mail_to``).
  Der Kanal-Aufloeser bleibt unangetastet. Mechanik laut Tech-Lead-Entscheid
  (#2280): ohne ``mail_to`` faellt E-Mail am Versandort aus der wirksamen
  Menge; bleibt nichts uebrig -> ``no_channels``.
* Anker: ``_write_compare_alert_snapshots`` zaehlt mit (statt Nowcast-Abruf).
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.loader import get_briefings_dir, get_data_dir

REPO_ROOT = Path(__file__).resolve().parents[2]

DISPATCH = "services.scheduler_dispatch_service"
NEU = "/api/briefings/{id}/send"
ALT_TRIP = "/api/scheduler/trips/{id}/send"
ALT_VERGLEICH = "/api/scheduler/compare-presets/{id}/send"

#: Vokabular laut Spec (send_outcomes.py) -> erwarteter HTTP-Status.
ERWARTETE_CODES = {
    "no_stage": 422,
    "no_weather": 422,
    "no_channels": 422,
    "channels_unreachable": 422,
    "already_in_progress": 409,
    "not_found": 404,
    "invalid_report_type": 422,
    "smtp_not_configured": 422,
}


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def client():
    """Echter ASGI-Aufruf gegen die komplette App. Serverfehler werden als
    500 sichtbar (nicht als Ausnahme im Test), damit "500 statt 422" ein
    beobachtbarer Befund ist."""
    from fastapi.testclient import TestClient

    from api.main import app

    return TestClient(app, raise_server_exceptions=False)


def neu_senden(c, entity_id: str, uid: str, kind: str | None, **extra):
    params = {"user_id": uid, **extra}
    if kind is not None:
        params["kind"] = kind
    return c.post(NEU.format(id=entity_id), params=params)


def alt_senden(c, kind: str, entity_id: str, uid: str, **extra):
    pfad = ALT_TRIP if kind == "route" else ALT_VERGLEICH
    return c.post(pfad.format(id=entity_id), params={"user_id": uid, **extra})


def body(resp) -> dict:
    try:
        b = resp.json()
    except ValueError:
        return {"_roh": resp.text}
    return b if isinstance(b, dict) else {"_roh": b}


# ---------------------------------------------------------------------------
# Trip
# ---------------------------------------------------------------------------


def trip_anlegen(uid: str, trip_id: str, *, email: bool = True, telegram: bool = False,
                 sms: bool = False, stages: bool = True) -> Path:
    """Echte Trip-Datei im Nutzerverzeichnis (``kind="route"``), Etappe heute."""
    ordner = get_briefings_dir(uid)
    ordner.mkdir(parents=True, exist_ok=True)
    pfad = ordner / f"{trip_id}.json"
    pfad.write_text(json.dumps({
        "id": trip_id,
        "name": f"Handversand {trip_id}",
        "kind": "route",
        "stages": [{
            "id": "st-heute",
            "name": "Etappe heute",
            "date": date.today().isoformat(),
            "waypoints": [
                {"id": "wp1", "name": "Innsbruck", "lat": 47.2692, "lon": 11.4041,
                 "elevation_m": 574},
                {"id": "wp2", "name": "Hafelekar", "lat": 47.3103, "lon": 11.3844,
                 "elevation_m": 2269},
            ],
        }] if stages else [],
        # strukturell kein MeteoAlarm-Abruf (netzfrei)
        "official_alerts_enabled": False,
        "report_config": {"send_email": email, "send_telegram": telegram, "send_sms": sms},
        "alert_rules": [],
    }))
    return pfad


class _TripWetterDouble:
    """Echte, aufgezeichnete Innsbruck-Daten (FixtureProvider)."""

    name = "openmeteo"

    def __init__(self) -> None:
        from providers.fixture import FixtureProvider

        self._fixture = FixtureProvider(str(REPO_ROOT / "fixtures" / "openmeteo"))

    def fetch_forecast(self, location, start=None, end=None,
                       enrich_ensemble=True, enrich_snow=True):
        return self._fixture.fetch_forecast(
            location, start=start, end=end,
            enrich_ensemble=enrich_ensemble, enrich_snow=enrich_snow,
        )


def trip_naehte(monkeypatch) -> list:
    """Wetter-Double + E-Mail-Mitschrift fuer den Trip. Liefert die Liste der
    tatsaechlich hinausgegangenen Trip-Mails (je Eintrag der Betreff)."""
    double = _TripWetterDouble()
    monkeypatch.setattr("providers.base.get_provider", lambda name: double)
    gesendet: list = []

    def _mitschreiben(self, report) -> None:
        gesendet.append(getattr(report, "email_subject", "?"))

    monkeypatch.setattr(
        "services.notification_service.NotificationService._send_email", _mitschreiben,
    )
    return gesendet


def telegram_trip_unerreichbar(monkeypatch) -> None:
    """Telegram konfiguriert, Zustellfaehigkeit meldet 'nicht erreichbar'
    (Muster #1403 AC-4) -- ohne Netz."""
    monkeypatch.setattr("app.config.Settings.can_send_telegram", lambda self: False)


# ---------------------------------------------------------------------------
# Ortsvergleich
# ---------------------------------------------------------------------------


def telegram_vergleich_scheitert(monkeypatch) -> list:
    """Telegram-Ausgang wirft beim Senden (Transportausfall, fail-soft-Pfad).
    Liefert die Liste der Zustellversuche."""
    from services import notification_service as ns

    versuche: list = []

    class _AusfallTelegram:
        def __init__(self, settings, recipient=None) -> None:
            pass

        def send(self, subject, body, reply_markup=None, *, parse_mode=None,
                 suppress_subject_line=False):
            versuche.append(subject)
            raise RuntimeError("Telegram-Gateway nicht erreichbar (simulierter Ausfall)")

    monkeypatch.setattr(ns, "TelegramOutput", _AusfallTelegram)
    return versuche


def wetter_faellt_ueberall_aus(monkeypatch) -> None:
    """Jeder Engine-Lauf (einer je Ort) wirft -- ``run_comparison_parallel``
    erkennt den Ausfall ALLER Orte selbst und reicht die Ausnahme weiter."""
    import services.comparison_engine as ce_mod

    original = ce_mod.ComparisonEngine

    class _AusfallEngine(original):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            raise RuntimeError("Wetterdienst nicht erreichbar (simulierter Ausfall)")

    monkeypatch.setattr(ce_mod, "ComparisonEngine", _AusfallEngine)


def wetter_fehlt_je_ort(monkeypatch) -> None:
    """Realistischer Ausfall: ``ComparisonEngine.run`` faengt einen
    Provider-Fehler je Ort selbst ab und liefert ``LocationResult(error=...)``
    (comparison_engine.py, s. Docstring ``_run_one_location``) — KEINE
    Ausnahme. Hier fuer JEDEN Ort."""
    from datetime import datetime

    import services.comparison_engine as ce_mod
    from app.user import ComparisonResult, LocationResult

    original = ce_mod.ComparisonEngine

    class _OhneDatenEngine(original):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            locations = kwargs.get("locations")
            if locations is None and args:
                locations = args[0]
            return ComparisonResult(
                locations=[
                    LocationResult(location=loc, error="Open-Meteo: HTTP 503 (keine Daten)")
                    for loc in list(locations or [])
                ],
                time_window=kwargs.get("time_window", (9, 16)),
                target_date=kwargs.get("target_date"),
                created_at=datetime(2026, 7, 8, 4, 0),
            )

    monkeypatch.setattr(ce_mod, "ComparisonEngine", _OhneDatenEngine)


def anker_zaehler(monkeypatch) -> list:
    """Zaehlt jeden Δ-Anker-Schreibvorgang des Vergleichs (statt Nowcast-Netz)."""
    import services.scheduler_dispatch_service as sds

    aufrufe: list = []

    def _zaehlen(preset_id, locations, user_id, preset, tage_ab_ortstag):
        aufrufe.append((user_id, preset_id))

    monkeypatch.setattr(sds, "_write_compare_alert_snapshots", _zaehlen)
    return aufrufe


def profil_ohne_mail_to(uid: str) -> None:
    """``mail_to`` aus dem echten ``user.json`` entfernen (Telegram/SMS bleiben)."""
    pfad = get_data_dir(uid) / "user.json"
    daten = json.loads(pfad.read_text())
    daten.pop("mail_to", None)
    pfad.write_text(json.dumps(daten))


def letzter_versand(uid: str, preset_id: str):
    """Gespeicherter Erfolgs-Status des Presets (echter Dateizustand)."""
    pfad = get_data_dir(uid) / "briefings" / f"{preset_id}.json"
    return json.loads(pfad.read_text()).get("letzter_versand")
