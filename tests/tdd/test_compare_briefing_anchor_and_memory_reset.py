"""TDD RED — Issue #1467 Scheibe S2, Arbeitsgang AG5: Vergleichs-Bezugspunkt
(Δ-Anker) und Melde-Gedaechtnis als EIN geteilter Baustein, Ortsvergleich-Seite.

SPEC: docs/specs/modules/rework_1467_s2_aenderungsalarm.md, Abschnitt
"AG5 — Vergleichs-Bezugspunkt und Melde-Gedaechtnis als EIN geteilter
Baustein", AC-14 bis AC-19.

Ist-Stand (gemessen am Code dieses Worktrees):

* `scheduler_dispatch_service.py::send_one_compare_preset` schreibt den
  Δ-Anker **bedingungslos** (`_write_compare_alert_snapshots(...)`) — auch
  beim Handversand ueber `send_compare_preset()`, der `send_one_compare_preset`
  ohne jede Unterscheidung aufruft. Einen Parameter `on_demand` gibt es dort
  heute nicht.
* Das Melde-Gedaechtnis (`AlertStateService`) wird auf dem Compare-Pfad
  **gar nicht** zurueckgesetzt: repo-weit existiert genau ein
  `AlertStateService.reset()`-Aufruf, der des Trips
  (`trip_report_scheduler.py::_reset_alert_state_after_briefing`).

Der gefaehrlichste Fehler ist der ausbleibende Alarm: `_filter_against_alert_state`
(`deviation_alert_engine.py:228-242`) vergleicht gegen den ABSOLUTEN
`last_reported_value` des Gedaechtnisses. Ein frischer Anker OHNE
Gedaechtnis-Reset laesst deshalb Aenderungen gegenueber dem — jetzt
ueberschriebenen — Vergleichspunkt dauerhaft verschwinden. Genau das weisen
AC-15 und AC-19 als ZUSTELLUNG nach (nicht nur als "kein Absturz").

Der neue geteilte Baustein, den diese Tests festlegen:

    from services.alert_briefing_anchor import write_anchor_and_reset_memory

    write_anchor_and_reset_memory(
        user_id=<echte user_id, nie "default">,
        entity_ids=[...],          # Trip: [trip.id]; Compare: [f"{preset_id}:{loc.id}", ...]
        write_anchor=<callable>,   # schreibt den Δ-Anker
        on_demand=<bool>,          # True => es passiert NICHTS (weder Anker noch Reset)
    )

Testpolitik: kein Mock-Theater. Alle Naehte sind entweder echte, kleine
Implementierungen desselben Protokolls (Wetterquelle, Vergleichs-Engine,
E-Mail-Transport) oder delegierende Beobachter, die die echte Implementierung
weiterhin ausfuehren. Zustands-, Anker- und Preset-Dateien sind echte Dateien
auf Platte; gelesen wird ueber die echten Services.

Versand-Sicherheit (#1477): `Settings(...)` faellt bei fehlenden Feldern still
auf die Prod-`.env` im Worktree zurueck. Jede hier gebaute `Settings`-Instanz
setzt deshalb ALLE Transport-Felder ausdruecklich auf unbrauchbare Werte, und
jeder Test, der einen Versandweg anfasst, prueft ueber
`can_send_telegram()`/`can_send_sms()` == False, dass kein echter Kanal
scharf ist. `send_compare_preset()` baut seine Settings selbst — dort greift
zusaetzlich die `_NoTransportSettings`-Naht (s.u.).
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.config import Settings
from app.loader import get_data_root
from app.models import ForecastDataPoint, SegmentWeatherSummary, ThunderLevel
from app.user import SavedLocation

from tests.helpers.compare_briefings import write_compare_briefings

# Pfadregel #1409: Pruefling relativ zur Testdatei aufloesen, nie ueber einen
# festen Hauptrepo-Pfad — sonst pruefte dieser Test aus dem Worktree die
# unveraenderte Hauptrepo-Kopie und meldete falsches Gruen.
REPO_ROOT = Path(__file__).resolve().parents[2]

TARGET_DATE = date(2026, 8, 4)

# Schwelle "standard" fuer PRECIPITATION_SUM = 10 mm, fuer
# PRECIPITATION_CHANGE = 7 mm (`services/alert_preset.py:41,52`). Alle
# Zahlenwerte unten sind gegen BEIDE Schwellen gewaehlt.
PRECIP_THRESHOLD_MM = 10.0


# ───────────────────────────── Settings-Naht ────────────────────────────────


_NO_TRANSPORT_FIELDS: dict = {
    # E-Mail: `mail_to` muss gesetzt sein (sonst bricht send_one_compare_preset
    # mit ValueError ab, bevor irgendein Anker geschrieben wird) — die Adresse
    # ist bewusst eine nicht existierende .invalid-Domain.
    "smtp_host": "dummy.invalid",
    "smtp_user": "dummy",
    "smtp_pass": "dummy",
    "mail_to": "ag5-dummy@example.invalid",
    "test_smtp_host": "dummy.invalid",
    "test_smtp_user": "dummy",
    "test_smtp_pass": "dummy",
    "test_mail_from": "ag5-dummy@example.invalid",
    # Telegram/SMS ausdruecklich AUS — sonst zieht Settings() die echten
    # Prod-Zugangsdaten aus der .env des Worktrees (#1477).
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "telegram_test_bot_token": "",
    "telegram_test_chat_id": "",
    "sms_gateway_url": "",
    "seven_api_key": "",
    "sms_to": "",
}


def _settings_email_only() -> Settings:
    """Echte `Settings` mit ausdruecklich unbrauchbaren Transport-Feldern."""
    return Settings(**_NO_TRANSPORT_FIELDS)


class _NoTransportSettings(Settings):
    """Echte `Settings`-Unterklasse (kein Mock) fuer den Handversand-Pfad.

    `send_compare_preset()` baut seine Settings SELBST
    (`Settings().with_user_profile(user_id)`) und bietet keine Sink-Naht. Ohne
    diese Unterklasse liefe der Test mit den Prod-Zugangsdaten und der
    Prod-Empfaengeradresse aus der `.env` des Worktrees (#1477). Erzwungen
    werden dieselben unbrauchbaren Werte wie oben; `with_user_profile` gibt
    die Instanz unveraendert zurueck, damit weder das Test-Konto noch eine
    `.env`-Adresse nachtraeglich eingespielt wird. Verhalten des Prueflings
    bleibt unberuehrt: es werden nur Konfigurationswerte gesetzt.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**{**_NO_TRANSPORT_FIELDS, **kwargs})

    def with_user_profile(self, user_id: str) -> "Settings":
        return self


class _RecordingEmailOutput:
    """Echter Transport-Ersatz fuer den Handversand-Pfad (kein Mock).

    `NotificationService.send_compare_report()` loest `EmailOutput` zur
    Laufzeit ueber `output.channels.email` auf. Fuer `send_compare_preset()`
    gibt es keinen `mail_sink`-Parameter — diese Klasse ist die Entsprechung:
    sie haelt Betreff und Empfaengerliste fest, statt SMTP zu waehlen. Damit
    ist zusaetzlich pruefbar, dass KEINE Adresse aus der `.env` durchschlaegt.
    """

    calls: list[dict] = []

    def __init__(self, settings) -> None:
        self._settings = settings

    def send(self, subject, html_body, plain_text_body=None, to=None, **kwargs) -> None:
        _RecordingEmailOutput.calls.append(
            {"subject": subject, "to": list(to or []), "body": html_body}
        )


# ───────────────────────────── Daten-Helfer ─────────────────────────────────


def _location(loc_id: str, name: str, lat: float, lon: float) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=1000)


def _point(point_id: str, name: str, lat: float, lon: float, precip_sum_mm: float):
    """Echtes `PointWeatherData`-DTO (kein Mock)."""
    from services.point_weather import PointWeatherData

    return PointWeatherData(
        id=point_id, name=name, lat=lat, lon=lon, timeseries=None,
        aggregated=SegmentWeatherSummary(precip_sum_mm=precip_sum_mm),
        fetched_at=datetime.now(timezone.utc), provider="tdd-ag5",
    )


class _ScriptedWeatherSource:
    """Echte `LocationWeatherSource`-Implementierung mit umschaltbaren Werten.

    Kein `Mock()`: eine kleine, vollstaendige Implementierung des Protokolls
    (`services/point_weather.py`), die echte `PointWeatherData` ohne Netz
    liefert. `values` ist absichtlich veraenderbar — damit laesst sich
    zwischen "Wetterlage zum Briefing" und "Wetterlage beim spaeteren
    Alarm-Check" umschalten, ohne die Naht zu tauschen.
    """

    def __init__(self, values: dict[str, float], names: dict[str, str] | None = None) -> None:
        self.values = dict(values)
        self._names = dict(names or {})
        self.fetch_calls: list[str] = []

    def fetch(
        self, point_id: str, lat: float, lon: float,
        start_hour: int | None = None, end_hour: int | None = None,
        target_date=None, tage_ab_ortstag=None,
    ):
        # `target_date`/`tage_ab_ortstag` (Issue #1661 Teil B): der
        # Versandpfad reicht den gebriefeten Tag als VERSATZ gegen den Ortstag
        # bis zum Δ-Anker durch, der Δ-Check spaeter den aufgeloesten absoluten
        # Tag; die Attrappe nimmt beides entgegen, statt an einem TypeError zu
        # scheitern.
        self.fetch_calls.append(point_id)
        return _point(
            point_id, self._names.get(point_id, point_id), lat, lon,
            precip_sum_mm=self.values.get(point_id, 0.0),
        )


def _preset(preset_id: str, location_ids: list[str], **extra) -> dict:
    preset = {
        "id": preset_id,
        "name": preset_id,
        "location_ids": list(location_ids),
        "schedule": "daily",
        "weekday": 4,
        "profil": "ALLGEMEIN",
        "hour_from": 9,
        "hour_to": 16,
        "empfaenger": ["ag5-dummy@example.invalid"],
        "letzter_versand": None,
        "top_ort_letzter_versand": None,
        "created_at": "2026-08-01T00:00:00Z",
        "kind": "vergleich",
    }
    preset.update(extra)
    return preset


def _dp(hour: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(TARGET_DATE.year, TARGET_DATE.month, TARGET_DATE.day, hour, 0),
        t2m_c=22.0, wind_chill_c=21.0, wind10m_kmh=11.0, gust_kmh=19.0,
        precip_1h_mm=0.0, cloud_total_pct=35, uv_index=5.0,
        thunder_level=ThunderLevel.NONE, pop_pct=10, visibility_m=9000,
    )


# ────────────────────────────── Naht-Installation ───────────────────────────


def _install_comparison_engine_seam(monkeypatch) -> None:
    """Ersetzt NUR die teure Upstream-Abhaengigkeit `ComparisonEngine.run`
    (Live-Wetter fuer die Vergleichs-Mail) durch eine echte Unterklasse mit
    festen Werten — Haus-Muster aus
    `tests/tdd/test_compare_dispatch_channel_fanout.py`. Der Δ-Anker-Schreiber
    bleibt ABSICHTLICH scharf: er ist der Pruefgegenstand dieser Scheibe."""
    import services.comparison_engine as ce_mod
    from app.user import ComparisonResult, LocationResult

    original = ce_mod.ComparisonEngine

    class _FixedEngine(original):  # echte Unterklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            locations = kwargs.get("locations")
            if locations is None and args:
                locations = args[0]
            return ComparisonResult(
                locations=[
                    LocationResult(
                        location=loc, score=90 - 5 * i, temp_max=22.0 + i, temp_min=12.0,
                        wind_max=11.0, gust_max=19.0, cloud_avg=35, sunny_hours=6,
                        official_alerts=[], hourly_data=[_dp(9), _dp(12), _dp(15)],
                    )
                    for i, loc in enumerate(list(locations or []))
                ],
                time_window=kwargs.get("time_window", (9, 16)),
                target_date=kwargs.get("target_date", TARGET_DATE),
                created_at=datetime(2026, 8, 4, 4, 0),
            )

    monkeypatch.setattr(ce_mod, "ComparisonEngine", _FixedEngine)


def _install_anchor_weather_seam(monkeypatch, source: _ScriptedWeatherSource) -> None:
    """Der Δ-Anker-Schreiber (`_write_compare_alert_snapshots`) baut sich seine
    Wetterquelle selbst (`CompareLocationWeatherSource()`, Netz). Hier wird die
    KLASSE im Quellmodul durch eine gleichwertige, netzfreie Implementierung
    ersetzt — die Anker-Logik selbst (Schleife ueber alle Orte,
    `CompareWeatherSnapshotService.save`) laeuft unveraendert echt."""
    import services.compare_location_weather_source as clws_mod

    class _SourceFactory:
        def __new__(cls, *args, **kwargs):
            return source

    monkeypatch.setattr(clws_mod, "CompareLocationWeatherSource", _SourceFactory)


def _install_email_transport_seam(monkeypatch) -> None:
    """Ersetzt den SMTP-Transport fuer Pfade OHNE `mail_sink`-Parameter
    (`send_compare_preset`). Zeichnet Betreff und Empfaenger auf."""
    import output.channels.email as email_mod

    _RecordingEmailOutput.calls = []
    monkeypatch.setattr(email_mod, "EmailOutput", _RecordingEmailOutput)


def _install_shared_anchor_spy(monkeypatch) -> list[dict]:
    """Delegierender Beobachter auf dem geteilten Baustein (kein Mock-Theater:
    die echte Funktion wird weiterhin ausgefuehrt, es wird nur mitgeschrieben,
    MIT WELCHEN Argumenten der Ortsvergleich delegiert).

    Gepatcht wird sowohl das Quellmodul als auch — falls der Name dort schon
    gebunden ist — das verbrauchende Modul, damit der Beobachter unabhaengig
    von der gewaehlten Importform greift (Haus-Muster, vgl. Kommentar in
    `scheduler_dispatch_service.py:280-282`)."""
    import services.alert_briefing_anchor as anchor_mod
    import services.scheduler_dispatch_service as sds_mod

    calls: list[dict] = []
    original = anchor_mod.write_anchor_and_reset_memory

    def _spy(*args, **kwargs):
        calls.append(dict(kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(anchor_mod, "write_anchor_and_reset_memory", _spy)
    if hasattr(sds_mod, "write_anchor_and_reset_memory"):
        monkeypatch.setattr(sds_mod, "write_anchor_and_reset_memory", _spy)
    return calls


@pytest.fixture
def compare_env(tmp_path, monkeypatch):
    """Isoliertes Arbeitsverzeichnis.

    Issue #1595: `load_compare_presets()` loest seinen `data_root` NICHT mehr
    relativ zum Arbeitsverzeichnis auf, sondern ueber `get_data_root()` — das
    `chdir` allein wuerde die Presets also nicht mehr dorthin legen, wo der
    Pruefling sie liest. Geschrieben wird deshalb unter der aufgeloesten
    Wurzel (s. `_write_presets`); das `chdir` bleibt als zweite Sicherung, damit
    ein versehentlich relativer Schreibzugriff nicht im echten Repo-Baum
    landet (#1265)."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "users").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _write_presets(tmp_path: Path, user_id: str, presets: list[dict]) -> None:
    from app.loader import get_data_root

    write_compare_briefings(get_data_root() / "users" / user_id, presets)


def _memory_keys(user_id: str, entity_id: str) -> list[str]:
    from services.alert_state import AlertStateService

    return sorted(AlertStateService(user_id=user_id).load(entity_id))


def _anchor_precip(user_id: str, preset_id: str, location_id: str) -> float | None:
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    points = CompareWeatherSnapshotService(user_id=user_id).load(preset_id, location_id)
    if not points:
        return None
    return points[0].aggregated.precip_sum_mm


def _assert_no_live_channel(settings: Settings) -> None:
    assert settings.can_send_telegram() is False, (
        "Sicherung (#1477): Telegram darf in diesem Test unter keinen Umstaenden "
        "sendefaehig sein — sonst ginge eine echte Nachricht an den Prod-Chat."
    )
    assert settings.can_send_sms() is False, (
        "Sicherung (#1477): SMS darf in diesem Test nicht sendefaehig sein."
    )


# ══════════════════════════════════ AC-14 ════════════════════════════════════


def test_ac14_unveraenderter_wert_meldet_nach_dem_briefing_nicht(compare_env, monkeypatch):
    """AC-14.

    GIVEN ein Ortsvergleich mit EINEM Ort, dessen Δ-Anker vor dem Briefing auf
          2 mm steht und dessen Melde-Gedaechtnis einen Aenderungs-Eintrag
          (2 mm) traegt — dieser Eintrag wuerde eine Meldung ueber 30 mm NICHT
          unterdruecken (|30-2| = 28 >= 10).
    WHEN  das geplante Briefing mit 30 mm laeuft und danach der Alarm-Check
          denselben, unveraenderten Wert von 30 mm sieht.
    THEN  geht KEIN Alarm raus — der Briefing-Stand ist der neue
          Vergleichspunkt.

    Warum dieser Test etwas bewacht, obwohl er heute schon gruen ist: er
    schlaegt fehl, sobald der neue Baustein das Gedaechtnis zuruecksetzt, OHNE
    vorher den Anker zu schreiben (dann bliebe der alte Anker 2 mm stehen,
    Δ = 28 mm, und die geleerte Erinnerung liesse die Meldung durch). Er ist
    damit die Gegenprobe zu AC-15: der Umbau darf nicht ins Gegenteil kippen
    und alles feuern lassen.
    """
    from app.loader import save_location
    from services.alert_state import AlertStateService
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from services.scheduler_dispatch_service import send_one_compare_preset

    uid = f"tdd-ag5-ac14-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-ag5-ac14-{uuid.uuid4().hex[:6]}"
    loc = _location("loc-ac14", "Ruhigort", 47.0, 11.0)
    save_location(loc, user_id=uid)
    _write_presets(compare_env, uid, [_preset(preset_id, [loc.id])])

    # Ausgangslage: Anker 2 mm, Gedaechtnis-Eintrag 2 mm.
    CompareWeatherSnapshotService(user_id=uid).save(
        preset_id, loc.id, _point(loc.id, loc.name, loc.lat, loc.lon, 2.0)
    )
    AlertStateService(user_id=uid).save(f"{preset_id}:{loc.id}", {
        f"precip_sum_mm:{loc.id}": {
            "last_reported_value": 2.0, "reported_at": "2026-08-03T06:00:00+00:00",
        }
    })

    settings = _settings_email_only()
    _assert_no_live_channel(settings)
    _install_comparison_engine_seam(monkeypatch)
    source = _ScriptedWeatherSource({loc.id: 30.0}, {loc.id: loc.name})
    _install_anchor_weather_seam(monkeypatch, source)

    mail_calls: list[str] = []
    send_one_compare_preset(
        _preset(preset_id, [loc.id]), settings, uid, str(compare_env / "data"),
        all_locations_cache=[loc], target_date=TARGET_DATE,
        tage_ab_ortstag=0,
        mail_sink=lambda subject, body: mail_calls.append(subject),
    )

    assert _anchor_precip(uid, preset_id, loc.id) == pytest.approx(30.0), (
        "Vorbedingung/AC-14: das geplante Briefing MUSS den Δ-Anker auf den "
        f"Briefing-Stand (30 mm) setzen, gefunden: "
        f"{_anchor_precip(uid, preset_id, loc.id)!r}"
    )

    # Der Alarm-Check sieht denselben, unveraenderten Wert.
    alert_mails: list[str] = []
    sent = CompareAlertService(
        settings=settings, user_id=uid,
        weather_source=_ScriptedWeatherSource({loc.id: 30.0}, {loc.id: loc.name}),
        mail_sink=lambda subject, body: alert_mails.append(subject),
    ).check_all_compare_presets()

    assert sent == 0, (
        f"Ein seit dem Briefing unveraenderter Wert darf keinen Alarm ausloesen, "
        f"erhalten: {sent} Zustellung(en) (AC-14)"
    )
    assert alert_mails == [], f"Unerwartete Zustellung: {alert_mails!r} (AC-14)"


# ══════════════════════════════════ AC-15 ════════════════════════════════════


def test_ac15_starker_ausschlag_nach_dem_briefing_wird_zugestellt(compare_env, monkeypatch):
    """AC-15 (RED heute — der verschluckte Alarm).

    GIVEN ein Ortsvergleich mit EINEM Ort, fuer den 60 mm bereits gemeldet
          wurden (Gedaechtnis-Eintrag 60 mm, Δ-Anker 60 mm).
    WHEN  das geplante Briefing mit einer ruhigeren Lage (30 mm) laeuft und
          der Wert danach wieder stark auf 55 mm steigt (Δ zum frischen Anker
          = 25 mm, weit ueber der Schwelle von 10 mm).
    THEN  wird der Alarm ausgeloest UND zugestellt.

    RED-Grund (heute): der Ortsvergleich schreibt beim Briefing zwar den
    frischen Anker (30 mm), leert das Melde-Gedaechtnis aber NICHT. Der Eintrag
    steht weiter auf 60 mm, und `_filter_against_alert_state`
    (`deviation_alert_engine.py:228-242`) vergleicht ABSOLUT gegen diesen Wert:
    |55 - 60| = 5 mm < 10 mm ⇒ die Meldung wird verschluckt, `sent == 0`. Genau
    die Kombination "frischer Anker + altes Gedaechtnis", vor der die Spec
    warnt. Nach dem Umbau ist das Gedaechtnis beim Briefing geleert, der Δ von
    25 mm zum Anker schlaegt durch und die Mail geht raus.
    """
    from app.loader import save_location
    from services.alert_state import AlertStateService
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from services.scheduler_dispatch_service import send_one_compare_preset

    uid = f"tdd-ag5-ac15-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-ag5-ac15-{uuid.uuid4().hex[:6]}"
    loc = _location("loc-ac15", "Sturmort", 47.1, 11.1)
    save_location(loc, user_id=uid)
    _write_presets(compare_env, uid, [_preset(preset_id, [loc.id])])

    CompareWeatherSnapshotService(user_id=uid).save(
        preset_id, loc.id, _point(loc.id, loc.name, loc.lat, loc.lon, 60.0)
    )
    AlertStateService(user_id=uid).save(f"{preset_id}:{loc.id}", {
        f"precip_sum_mm:{loc.id}": {
            "last_reported_value": 60.0, "reported_at": "2026-08-03T06:00:00+00:00",
        }
    })

    settings = _settings_email_only()
    _assert_no_live_channel(settings)
    _install_comparison_engine_seam(monkeypatch)
    _install_anchor_weather_seam(
        monkeypatch, _ScriptedWeatherSource({loc.id: 30.0}, {loc.id: loc.name})
    )

    send_one_compare_preset(
        _preset(preset_id, [loc.id]), settings, uid, str(compare_env / "data"),
        all_locations_cache=[loc], target_date=TARGET_DATE,
        tage_ab_ortstag=0,
        mail_sink=lambda subject, body: None,
    )

    alert_mails: list[tuple[str, str]] = []
    sent = CompareAlertService(
        settings=settings, user_id=uid,
        weather_source=_ScriptedWeatherSource({loc.id: 55.0}, {loc.id: loc.name}),
        mail_sink=lambda subject, body: alert_mails.append((subject, body)),
    ).check_all_compare_presets()

    assert sent == 1, (
        "Ein starker Ausschlag nach dem Briefing (30 mm ⇒ 55 mm, Δ = 25 mm bei "
        "einer Schwelle von 10 mm) MUSS gemeldet werden. Erhalten: "
        f"{sent} Zustellung(en) — das alte Melde-Gedaechtnis (60 mm) hat den "
        "Alarm verschluckt (AC-15)."
    )
    assert len(alert_mails) == 1, f"Erwartet genau eine Zustellung, erhalten: {len(alert_mails)}"
    assert loc.name in alert_mails[0][1], (
        f"Die zugestellte Meldung nennt den betroffenen Ort nicht: "
        f"{alert_mails[0][1][:300]!r}"
    )


# ══════════════════════════════════ AC-16 ════════════════════════════════════


def test_ac16_briefing_setzt_das_gedaechtnis_aller_drei_orte_zurueck(compare_env, monkeypatch):
    """AC-16 (RED heute) — Risiko R3: ein still uebersprungener Ort meldet nie
    wieder.

    GIVEN ein Ortsvergleich mit DREI Orten, die sich in allem unterscheiden:
          Anker und Gedaechtnis-Eintrag stehen bei 60 / 45 / 30 mm, dazu
          traegt jeder Ort einen eigenen, wiedererkennbaren Namen.
    WHEN  das geplante Briefing laeuft (Briefing-Werte ebenfalls verschieden:
          10 / 12 / 14 mm).
    THEN  ist der Aenderungs-Schluessel in den Zustandsdateien ALLER drei Orte
          (`f"{preset_id}:{location_id}"`) zurueckgesetzt — und der
          anschliessende Alarm-Check meldet GENAU den einen Ort, der danach
          stark ausschlaegt, nicht die beiden anderen.

    RED-Grund (heute): auf dem Compare-Pfad existiert ueberhaupt kein
    `AlertStateService.reset()`-Aufruf — alle drei Eintraege stehen nach dem
    Briefing unveraendert da.

    Die drei Orte sind bewusst NICHT austauschbar (verschiedene Werte,
    verschiedene Namen, nur einer loest spaeter aus): gleiche Werte machten
    das Ergebnis beliebig zuordenbar und den Test blind (Lehre aus AG3b).
    """
    from app.loader import save_location
    from services.alert_state import AlertStateService
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from services.scheduler_dispatch_service import send_one_compare_preset

    uid = f"tdd-ag5-ac16-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-ag5-ac16-{uuid.uuid4().hex[:6]}"
    locs = [
        _location("loc-ac16-a", "Alpenblick", 47.2, 11.2),
        _location("loc-ac16-b", "Bergsattel", 47.3, 11.3),
        _location("loc-ac16-c", "Chalethang", 47.4, 11.4),
    ]
    for loc in locs:
        save_location(loc, user_id=uid)
    location_ids = [loc.id for loc in locs]
    _write_presets(compare_env, uid, [_preset(preset_id, location_ids)])

    vorher = {"loc-ac16-a": 60.0, "loc-ac16-b": 45.0, "loc-ac16-c": 30.0}
    briefing = {"loc-ac16-a": 10.0, "loc-ac16-b": 12.0, "loc-ac16-c": 14.0}
    snap = CompareWeatherSnapshotService(user_id=uid)
    state = AlertStateService(user_id=uid)
    for loc in locs:
        snap.save(preset_id, loc.id, _point(loc.id, loc.name, loc.lat, loc.lon, vorher[loc.id]))
        state.save(f"{preset_id}:{loc.id}", {
            f"precip_sum_mm:{loc.id}": {
                "last_reported_value": vorher[loc.id],
                "reported_at": "2026-08-03T06:00:00+00:00",
            }
        })

    settings = _settings_email_only()
    _assert_no_live_channel(settings)
    _install_comparison_engine_seam(monkeypatch)
    names = {loc.id: loc.name for loc in locs}
    _install_anchor_weather_seam(monkeypatch, _ScriptedWeatherSource(briefing, names))

    send_one_compare_preset(
        _preset(preset_id, location_ids), settings, uid, str(compare_env / "data"),
        all_locations_cache=locs, target_date=TARGET_DATE,
        tage_ab_ortstag=0,
        mail_sink=lambda subject, body: None,
    )

    for loc in locs:
        assert _memory_keys(uid, f"{preset_id}:{loc.id}") == [], (
            f"Der Aenderungs-Schluessel von Ort {loc.name} ({loc.id}) haette beim "
            f"Briefing zurueckgesetzt werden muessen, gefunden: "
            f"{_memory_keys(uid, f'{preset_id}:{loc.id}')!r} (AC-16, R3)"
        )
        assert _anchor_precip(uid, preset_id, loc.id) == pytest.approx(briefing[loc.id]), (
            f"Der Δ-Anker von Ort {loc.name} muss auf dem Briefing-Stand stehen"
        )

    # Nur EIN Ort schlaegt danach aus — der Reset darf nicht alles feuern lassen.
    danach = {"loc-ac16-a": 10.0, "loc-ac16-b": 40.0, "loc-ac16-c": 14.0}
    alert_mails: list[tuple[str, str]] = []
    sent = CompareAlertService(
        settings=settings, user_id=uid,
        weather_source=_ScriptedWeatherSource(danach, names),
        mail_sink=lambda subject, body: alert_mails.append((subject, body)),
    ).check_all_compare_presets()

    assert sent == 1, f"Erwartet genau einen gebuendelten Versand, erhalten: {sent}"
    body = alert_mails[0][1]
    assert "Bergsattel" in body, (
        f"Der ausschlagende Ort 'Bergsattel' fehlt in der Meldung: {body[:400]!r}"
    )
    assert "Alpenblick" not in body and "Chalethang" not in body, (
        "Nur der tatsaechlich ausschlagende Ort darf gemeldet werden — die "
        f"unveraenderten Orte stehen faelschlich mit drin: {body[:400]!r}"
    )


# ══════════════════════════════════ AC-17 ════════════════════════════════════


def test_ac17_amtlicher_eintrag_ueberlebt_den_briefing_reset(compare_env, monkeypatch):
    """AC-17 (RED heute) — Vorbild `test_alert_state_briefing_reset.py:151`
    (AC-20-Muster), auf den Ortsvergleich uebertragen.

    GIVEN eine Zustandsdatei eines Vergleichs-Ortes mit BEIDEN Schluesselarten:
          einem amtlichen Eintrag (`official_alert:...`) und einem
          Aenderungs-Eintrag.
    WHEN  das geplante Briefing fuer diesen Ortsvergleich laeuft.
    THEN  bleibt der amtliche Eintrag wertgleich erhalten und nur der
          Aenderungs-Eintrag verschwindet.

    RED-Grund (heute): der Compare-Pfad setzt gar nichts zurueck — der
    Aenderungs-Eintrag steht danach unveraendert da. `AlertStateService.reset()`
    schont `official_alert:`-Schluessel bereits seit #1460 P2
    (`alert_state.py:90-97`); dieser Test nagelt fest, dass der neue,
    geteilte Baustein genau diesen Reset benutzt und keinen eigenen,
    grobschlaechtigeren.
    """
    from app.loader import save_location
    from services.alert_state import AlertStateService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from services.scheduler_dispatch_service import send_one_compare_preset

    uid = f"tdd-ag5-ac17-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-ag5-ac17-{uuid.uuid4().hex[:6]}"
    loc = _location("loc-ac17", "Amtsort", 47.5, 11.5)
    save_location(loc, user_id=uid)
    _write_presets(compare_env, uid, [_preset(preset_id, [loc.id])])

    official_key = (
        "official_alert:region:Gailtal:thunderstorm:"
        "2026-08-04T06:00:00+00:00:2026-08-04T18:00:00+00:00"
    )
    official_value = {"last_reported_value": 3.0, "reported_at": "2026-08-04T07:00:00+00:00"}
    entity_id = f"{preset_id}:{loc.id}"
    AlertStateService(user_id=uid).save(entity_id, {
        official_key: dict(official_value),
        f"precip_sum_mm:{loc.id}": {
            "last_reported_value": 42.0, "reported_at": "2026-08-04T07:00:00+00:00",
        },
    })
    CompareWeatherSnapshotService(user_id=uid).save(
        preset_id, loc.id, _point(loc.id, loc.name, loc.lat, loc.lon, 42.0)
    )

    settings = _settings_email_only()
    _assert_no_live_channel(settings)
    _install_comparison_engine_seam(monkeypatch)
    _install_anchor_weather_seam(
        monkeypatch, _ScriptedWeatherSource({loc.id: 8.0}, {loc.id: loc.name})
    )

    send_one_compare_preset(
        _preset(preset_id, [loc.id]), settings, uid, str(compare_env / "data"),
        all_locations_cache=[loc], target_date=TARGET_DATE,
        tage_ab_ortstag=0,
        mail_sink=lambda subject, body: None,
    )

    after = AlertStateService(user_id=uid).load(entity_id)
    assert official_key in after, (
        f"Der amtliche Eintrag muss den Briefing-Reset ueberleben, vorhanden: "
        f"{sorted(after)!r} (AC-17)"
    )
    assert after[official_key] == official_value, (
        f"Der amtliche Eintrag darf sich nicht veraendern: {after[official_key]!r}"
    )
    assert f"precip_sum_mm:{loc.id}" not in after, (
        f"Der Aenderungs-Eintrag muss beim Briefing verschwinden, vorhanden: "
        f"{sorted(after)!r} (AC-17)"
    )


# ══════════════════════════════════ AC-18 ════════════════════════════════════


def test_ac18_briefing_von_nutzer_a_laesst_nutzer_b_unberuehrt(compare_env, monkeypatch):
    """AC-18 (RED heute, Mandantentrennung).

    GIVEN zwei verschiedene Nutzer mit einem gleichnamigen Ortsvergleich
          (IDENTISCHE `preset_id`, identische Orts-Kennung) und je einem
          eigenen Gedaechtnis-Eintrag — Nutzer A mit 60 mm, Nutzer B mit
          33 mm (verschieden, damit eine Verwechslung auffliegt).
    WHEN  ausschliesslich Nutzer A sein geplantes Briefing versendet.
    THEN  ist NUR das Gedaechtnis von Nutzer A geleert; das von Nutzer B
          steht unveraendert da — Wert und Zeitstempel.

    RED-Grund (heute): das Gedaechtnis von Nutzer A wird gar nicht geleert
    (kein Reset auf dem Compare-Pfad). Die B-Haelfte ist der Waechter gegen
    einen Baustein, der die `user_id` verliert oder auf `"default"`
    zurueckfaellt.
    """
    from app.loader import save_location
    from services.alert_state import AlertStateService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from services.scheduler_dispatch_service import send_one_compare_preset

    suffix = uuid.uuid4().hex[:6]
    uid_a = f"tdd-ag5-ac18-a-{suffix}"
    uid_b = f"tdd-ag5-ac18-b-{suffix}"
    preset_id = f"cp-ag5-ac18-{suffix}"  # bewusst fuer BEIDE Nutzer identisch
    loc = _location("loc-ac18", "Zwillingsort", 47.6, 11.6)
    entity_id = f"{preset_id}:{loc.id}"

    b_state = {
        f"precip_sum_mm:{loc.id}": {
            "last_reported_value": 33.0, "reported_at": "2026-08-02T05:00:00+00:00",
        }
    }
    for uid, value in ((uid_a, 60.0), (uid_b, 33.0)):
        save_location(loc, user_id=uid)
        _write_presets(compare_env, uid, [_preset(preset_id, [loc.id])])
        CompareWeatherSnapshotService(user_id=uid).save(
            preset_id, loc.id, _point(loc.id, loc.name, loc.lat, loc.lon, value)
        )
    AlertStateService(user_id=uid_a).save(entity_id, {
        f"precip_sum_mm:{loc.id}": {
            "last_reported_value": 60.0, "reported_at": "2026-08-03T06:00:00+00:00",
        }
    })
    AlertStateService(user_id=uid_b).save(entity_id, json.loads(json.dumps(b_state)))

    settings = _settings_email_only()
    _assert_no_live_channel(settings)
    _install_comparison_engine_seam(monkeypatch)
    _install_anchor_weather_seam(
        monkeypatch, _ScriptedWeatherSource({loc.id: 5.0}, {loc.id: loc.name})
    )

    send_one_compare_preset(
        _preset(preset_id, [loc.id]), settings, uid_a, str(compare_env / "data"),
        all_locations_cache=[loc], target_date=TARGET_DATE,
        tage_ab_ortstag=0,
        mail_sink=lambda subject, body: None,
    )

    assert _memory_keys(uid_a, entity_id) == [], (
        f"Nutzer A hat ein Briefing versendet — sein Gedaechtnis muss geleert "
        f"sein, gefunden: {_memory_keys(uid_a, entity_id)!r} (AC-18)"
    )
    assert AlertStateService(user_id=uid_b).load(entity_id) == b_state, (
        "Das Gedaechtnis des gleichnamigen Ortsvergleichs von Nutzer B muss "
        "unveraendert bleiben (Mandantentrennung), gefunden: "
        f"{AlertStateService(user_id=uid_b).load(entity_id)!r} (AC-18)"
    )
    assert _anchor_precip(uid_b, preset_id, loc.id) == pytest.approx(33.0), (
        "Auch der Δ-Anker von Nutzer B darf durch das Briefing von Nutzer A "
        f"nicht angefasst werden, gefunden: {_anchor_precip(uid_b, preset_id, loc.id)!r}"
    )


# ══════════════════════════════════ AC-19 ════════════════════════════════════


def test_ac19_handversand_laesst_anker_und_gedaechtnis_unberuehrt(compare_env, monkeypatch):
    """AC-19 (RED heute) — der Handversand darf den Vergleichspunkt nicht
    verschieben, sonst verschwindet der naechste echte Ausschlag.

    GIVEN ein Ortsvergleich mit Δ-Anker 5 mm und einem Gedaechtnis-Eintrag,
          und eine aktuelle Lage von 50 mm.
    WHEN  der Nutzer den Einzelversand ausloest
          (`send_compare_preset()`, Endpunkt POST
          /api/scheduler/compare-presets/{id}/send).
    THEN  bleiben Δ-Anker (5 mm) UND Gedaechtnis unveraendert — UND der
          anschliessende regulaere Alarm-Check meldet die 50 mm tatsaechlich
          (Δ = 45 mm gegen den erhaltenen Anker) und stellt zu.

    RED-Grund (heute): `send_compare_preset()` reicht an
    `send_one_compare_preset()` durch, das den Δ-Anker BEDINGUNGSLOS schreibt
    — der Anker steht danach auf 50 mm. Der spaetere Check vergleicht dann
    50 gegen 50, findet keine Aenderung und meldet NICHTS. Der Ausschlag ist
    still verloren. Nach dem Umbau (`on_demand=True` ⇒ weder Anker noch
    Reset) bleibt der Anker bei 5 mm und die Meldung geht raus.

    Versand-Sicherheit: `send_compare_preset()` baut seine Settings selbst und
    bietet keine Sink-Naht — deshalb `_NoTransportSettings` (alle Kanaele
    unbrauchbar, keine `.env`-Adresse) plus `_RecordingEmailOutput` statt
    SMTP. Der Test prueft ausdruecklich, an WELCHE Adresse zugestellt wurde.
    """
    from app.loader import save_location
    from services.alert_state import AlertStateService
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    import services.scheduler_dispatch_service as sds_mod

    uid = f"tdd-ag5-ac19-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-ag5-ac19-{uuid.uuid4().hex[:6]}"
    loc = _location("loc-ac19", "Handort", 47.7, 11.7)
    save_location(loc, user_id=uid)
    _write_presets(compare_env, uid, [_preset(preset_id, [loc.id])])

    entity_id = f"{preset_id}:{loc.id}"
    gedaechtnis_vorher = {
        f"precip_sum_mm:{loc.id}": {
            "last_reported_value": 5.0, "reported_at": "2026-08-03T06:00:00+00:00",
        }
    }
    AlertStateService(user_id=uid).save(entity_id, json.loads(json.dumps(gedaechtnis_vorher)))
    CompareWeatherSnapshotService(user_id=uid).save(
        preset_id, loc.id, _point(loc.id, loc.name, loc.lat, loc.lon, 5.0)
    )

    _install_comparison_engine_seam(monkeypatch)
    _install_anchor_weather_seam(
        monkeypatch, _ScriptedWeatherSource({loc.id: 50.0}, {loc.id: loc.name})
    )
    _install_email_transport_seam(monkeypatch)
    monkeypatch.setattr(sds_mod, "Settings", _NoTransportSettings)
    _assert_no_live_channel(_NoTransportSettings())

    result = sds_mod.send_compare_preset(uid, preset_id, str(get_data_root()))
    assert result.get("status") == "ok", f"Der Handversand ist nicht durchgelaufen: {result!r}"
    assert len(_RecordingEmailOutput.calls) == 1, (
        f"Der Handversand muss genau eine Mail zustellen, erhalten: "
        f"{len(_RecordingEmailOutput.calls)}"
    )
    assert _RecordingEmailOutput.calls[0]["to"] == ["ag5-dummy@example.invalid"], (
        "Sicherung (#1477): die Zustellung ging an eine andere als die im Test "
        f"gesetzte Adresse: {_RecordingEmailOutput.calls[0]['to']!r}"
    )

    assert _anchor_precip(uid, preset_id, loc.id) == pytest.approx(5.0), (
        "Der Handversand darf den Δ-Anker NICHT neu setzen — gefunden: "
        f"{_anchor_precip(uid, preset_id, loc.id)!r} mm statt 5.0 mm (AC-19)"
    )
    assert AlertStateService(user_id=uid).load(entity_id) == gedaechtnis_vorher, (
        "Der Handversand darf das Melde-Gedaechtnis nicht leeren — gefunden: "
        f"{AlertStateService(user_id=uid).load(entity_id)!r} (AC-19)"
    )

    # Und der Ausschlag muss danach tatsaechlich zugestellt werden.
    settings = _settings_email_only()
    _assert_no_live_channel(settings)
    alert_mails: list[tuple[str, str]] = []
    sent = CompareAlertService(
        settings=settings, user_id=uid,
        weather_source=_ScriptedWeatherSource({loc.id: 50.0}, {loc.id: loc.name}),
        mail_sink=lambda subject, body: alert_mails.append((subject, body)),
    ).check_all_compare_presets()

    assert sent == 1, (
        "Nach dem Handversand muss der starke Ausschlag (5 mm ⇒ 50 mm) beim "
        f"naechsten regulaeren Check gemeldet werden, erhalten: {sent} "
        "Zustellung(en) — der Handversand hat den Vergleichspunkt verschoben "
        "und den Alarm verschluckt (AC-19)"
    )
    assert len(alert_mails) == 1 and loc.name in alert_mails[0][1], (
        f"Die Meldung nennt den betroffenen Ort nicht: {alert_mails!r}"
    )


# ═══════════════════ Delegation an den geteilten Baustein ═══════════════════


def test_ortsvergleich_delegiert_an_den_geteilten_baustein(compare_env, monkeypatch):
    """AG5-Kern (RED heute): der Ortsvergleich behandelt Anker und Gedaechtnis
    NICHT selbst, sondern ueber den EINEN geteilten Baustein — mit ALLEN Orten
    des Presets, nicht nur den getriggerten (Risiko R3), und mit der echten
    `user_id`.

    GIVEN ein Ortsvergleich mit drei Orten.
    WHEN  das geplante Briefing laeuft.
    THEN  wurde `services.alert_briefing_anchor.write_anchor_and_reset_memory`
          genau einmal aufgerufen, mit `on_demand=False`, mit der echten
          `user_id` (nie `"default"`) und mit den Kennungen ALLER drei Orte in
          der konfigurierten Reihenfolge.

    RED-Grund (heute): das Modul `services/alert_briefing_anchor.py` existiert
    nicht (ImportError) — der Ortsvergleich schreibt seinen Anker inline und
    kennt gar kein Melde-Gedaechtnis.
    """
    from app.loader import save_location
    from services.scheduler_dispatch_service import send_one_compare_preset

    uid = f"tdd-ag5-deleg-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-ag5-deleg-{uuid.uuid4().hex[:6]}"
    locs = [
        _location("loc-d1", "Erstort", 46.1, 10.1),
        _location("loc-d2", "Zweitort", 46.2, 10.2),
        _location("loc-d3", "Drittort", 46.3, 10.3),
    ]
    for loc in locs:
        save_location(loc, user_id=uid)
    location_ids = [loc.id for loc in locs]
    _write_presets(compare_env, uid, [_preset(preset_id, location_ids)])

    settings = _settings_email_only()
    _assert_no_live_channel(settings)
    _install_comparison_engine_seam(monkeypatch)
    _install_anchor_weather_seam(
        monkeypatch,
        _ScriptedWeatherSource({loc.id: 3.0 for loc in locs}, {loc.id: loc.name for loc in locs}),
    )
    calls = _install_shared_anchor_spy(monkeypatch)

    send_one_compare_preset(
        _preset(preset_id, location_ids), settings, uid, str(compare_env / "data"),
        all_locations_cache=locs, target_date=TARGET_DATE,
        tage_ab_ortstag=0,
        mail_sink=lambda subject, body: None,
    )

    assert len(calls) == 1, (
        f"Der geteilte Baustein muss genau einmal je Briefing laufen, erhalten: "
        f"{len(calls)} Aufruf(e)"
    )
    call = calls[0]
    assert call.get("on_demand") is False, (
        f"Das geplante Briefing muss mit on_demand=False delegieren: {call!r}"
    )
    assert call.get("user_id") == uid, (
        f"Die echte user_id muss durchgereicht werden (nie 'default'): {call!r}"
    )
    assert list(call.get("entity_ids") or []) == [f"{preset_id}:{loc.id}" for loc in locs], (
        "Der Reset muss ALLE Orte des Presets in der konfigurierten Reihenfolge "
        f"abdecken (R3), erhalten: {call.get('entity_ids')!r}"
    )


def test_fehlschlagender_reset_stoppt_die_uebrigen_kennungen_nicht(
    compare_env, monkeypatch, caplog
):
    """Risiko R3, Adversary-Fund F002: die fail-soft-Zusicherung des geteilten
    Bausteins war bislang unbewacht — das Entfernen des `try/except` liess alle
    22 Tests gruen.

    GIVEN drei Kennungen mit je einem Aenderungs-Eintrag, bei denen der Reset
          der MITTLEREN Kennung fehlschlaegt.
    WHEN  der geteilte Baustein mit `on_demand=False` ueber alle drei laeuft.
    THEN  sind die Nachbarn VOR und HINTER der Fehlstelle trotzdem
          zurueckgesetzt (am echten Dateizustand gemessen, nicht am
          Aufrufzaehler), die gescheiterte Kennung steht unveraendert da, und
          die Warnung nennt Kennung UND Ausnahmetyp.

    Ohne den Nachbarn HINTER der Fehlstelle waere der Test blind: genau dessen
    Gedaechtnis bliebe bei einer abbrechenden Schleife stehen, und er wuerde
    nach dem naechsten Briefing nie wieder melden (R3).

    Warum diese Naht und keine kaputte Zustandsdatei: nachgemessen (04.08.)
    schluckt `AlertStateService.reset()` JEDEN realen Dateisystem-Fehler selbst
    — Verzeichnis statt Datei, schreibgeschuetztes Verzeichnis, kaputter
    JSON-Inhalt und Null-Byte-Kennung laufen alle ohne Wurf durch (OSError wird
    intern gefangen, ValueError von `Path.exists()` verschluckt). Ein echter
    Wurf ist ueber den Dateizustand heute NICHT herstellbar. Deshalb eine echte
    Unterklasse des Prueflings (kein `Mock(side_effect=...)`): sie fuehrt fuer
    alle anderen Kennungen den ECHTEN Reset aus und faellt nur fuer eine
    einzige aus — dasselbe Naht-Muster wie `_FixedEngine`/`_NoTransportSettings`
    weiter oben. Gemessen wird die Wirkung auf Platte, nicht der Aufruf.
    """
    import services.alert_state as alert_state_mod
    from services.alert_briefing_anchor import write_anchor_and_reset_memory

    uid = f"tdd-ag5-failsoft-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-ag5-failsoft-{uuid.uuid4().hex[:6]}"
    entity_ids = [f"{preset_id}:loc-{suffix}" for suffix in ("a", "b", "c")]
    kaputte_kennung = entity_ids[1]

    state = alert_state_mod.AlertStateService(user_id=uid)
    vorher = {}
    for entity_id, wert in zip(entity_ids, (60.0, 45.0, 30.0)):
        payload = {
            f"precip_sum_mm:{entity_id.rsplit(':', 1)[1]}": {
                "last_reported_value": wert, "reported_at": "2026-08-03T06:00:00+00:00",
            }
        }
        vorher[entity_id] = json.loads(json.dumps(payload))
        state.save(entity_id, payload)

    class _ResetFailsForOneEntity(alert_state_mod.AlertStateService):
        """Echte Unterklasse des Prueflings: fuer alle Kennungen ausser einer
        laeuft der unveraenderte, echte Reset."""

        def reset(self, entity_id: str) -> None:
            if entity_id == kaputte_kennung:
                raise RuntimeError(f"Reset fuer {entity_id} fehlgeschlagen")
            return super().reset(entity_id)

    monkeypatch.setattr(alert_state_mod, "AlertStateService", _ResetFailsForOneEntity)

    with caplog.at_level(logging.WARNING, logger="alert_briefing_anchor"):
        write_anchor_and_reset_memory(
            user_id=uid, entity_ids=entity_ids, write_anchor=lambda: None, on_demand=False,
        )

    assert _memory_keys(uid, entity_ids[0]) == [], (
        "Die Kennung VOR der Fehlstelle muss zurueckgesetzt sein, gefunden: "
        f"{_memory_keys(uid, entity_ids[0])!r}"
    )
    assert _memory_keys(uid, entity_ids[2]) == [], (
        "Die Kennung HINTER der Fehlstelle muss ebenfalls zurueckgesetzt sein — "
        "ein Fehler bei einer Kennung darf die Schleife nicht abbrechen (R3), "
        f"gefunden: {_memory_keys(uid, entity_ids[2])!r}"
    )
    assert alert_state_mod.AlertStateService(user_id=uid).load(kaputte_kennung) == vorher[
        kaputte_kennung
    ], "Die gescheiterte Kennung darf nicht halb aufgeraeumt zurueckbleiben"

    protokoll = " | ".join(record.getMessage() for record in caplog.records)
    assert kaputte_kennung in protokoll, (
        f"Die Warnung muss die betroffene Kennung nennen: {protokoll!r}"
    )
    assert "RuntimeError" in protokoll, (
        f"Die Warnung muss den Ausnahmetyp nennen, damit ein echter "
        f"Programmfehler auffindbar bleibt: {protokoll!r}"
    )


def test_handversand_delegiert_mit_on_demand_kennzeichen(compare_env, monkeypatch):
    """AC-19 (Struktur-Haelfte, RED heute): der Handversand delegiert an
    denselben Baustein, aber mit `on_demand=True` — dort entscheidet EINE
    Stelle, dass weder Anker noch Gedaechtnis angefasst werden.

    RED-Grund (heute): `services/alert_briefing_anchor.py` existiert nicht,
    und `send_one_compare_preset()` kennt keinen Parameter `on_demand`.
    """
    from app.loader import save_location

    import services.scheduler_dispatch_service as sds_mod

    uid = f"tdd-ag5-deleg-od-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-ag5-deleg-od-{uuid.uuid4().hex[:6]}"
    loc = _location("loc-od", "Handdelegat", 46.4, 10.4)
    save_location(loc, user_id=uid)
    _write_presets(compare_env, uid, [_preset(preset_id, [loc.id])])

    _install_comparison_engine_seam(monkeypatch)
    _install_anchor_weather_seam(
        monkeypatch, _ScriptedWeatherSource({loc.id: 3.0}, {loc.id: loc.name})
    )
    _install_email_transport_seam(monkeypatch)
    monkeypatch.setattr(sds_mod, "Settings", _NoTransportSettings)
    calls = _install_shared_anchor_spy(monkeypatch)

    sds_mod.send_compare_preset(uid, preset_id, str(get_data_root()))

    assert len(calls) == 1, (
        f"Auch der Handversand laeuft ueber den geteilten Baustein — erwartet "
        f"genau einen Aufruf, erhalten: {len(calls)}"
    )
    assert calls[0].get("on_demand") is True, (
        f"Der Handversand muss mit on_demand=True delegieren: {calls[0]!r}"
    )
