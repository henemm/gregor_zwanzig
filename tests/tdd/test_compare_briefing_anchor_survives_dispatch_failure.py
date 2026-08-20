"""TDD RED — Issue #1629, AC-2: der Vergleichs-Anker ueberlebt einen
Versandfehler (Ortsvergleich-Seite).

SPEC: docs/specs/modules/fix_1629_briefing_anker_versandfehler.md, AC-2.
Trip-Pendant: `test_briefing_anchor_survives_dispatch_failure.py`.

Der Ortsvergleich hat dieselbe Bruchstelle wie der Trip:
`scheduler_dispatch_service.py:401` ruft `send_compare_report(...)` ohne
`try/except`, der geteilte Baustein `write_anchor_and_reset_memory(...)` steht
erst bei `:423`. Wirft der E-Mail-Kanal, entsteht fuer KEINEN Ort des Presets
ein Vergleichs-Snapshot.

Test-Politik wie im Trip-Pendant: kein Mock-Theater. Der Versandfehler
entsteht aus einer echten, unzulaessigen Kanal-Konfiguration (unvollstaendige
SMTP-Zugangsdaten) — der echte `EmailOutput`-Guard wirft den echten
`OutputConfigError`, ohne je eine Verbindung aufzubauen. Ersetzt sind nur die
teuren Upstream-Abhaengigkeiten (Vergleichs-Engine, Wetterquelle des
Anker-Schreibers) durch echte Unterklassen bzw. gleichwertige, netzfreie
Implementierungen — Haus-Muster aus
`test_compare_briefing_anchor_and_memory_reset.py`. Der Anker-Schreiber selbst
bleibt ABSICHTLICH scharf: er ist der Pruefgegenstand.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.config import Settings
from app.models import ForecastDataPoint, SegmentWeatherSummary, ThunderLevel
from app.user import SavedLocation

from tests.helpers.compare_briefings import write_compare_briefings

# Pfadregel #1409: Pruefling relativ zur Testdatei aufloesen, nie ueber einen
# festen Hauptrepo-Pfad.
REPO_ROOT = Path(__file__).resolve().parents[2]

TARGET_DATE = date.today()

# `mail_to` MUSS gesetzt sein — sonst bricht `send_one_compare_preset` mit
# ValueError ab, bevor irgendein Versand versucht wird. Der Rest der
# SMTP-Konfiguration fehlt bewusst: `EmailOutput.__init__()` wirft dann den
# echten `OutputConfigError`, ohne Netz. Alle uebrigen Transport-Felder sind
# ausdruecklich leer (#1477 — sonst zieht `Settings()` die Prod-`.env`).
_BROKEN_EMAIL_FIELDS: dict = {
    "smtp_host": "", "smtp_user": "", "smtp_pass": "",
    "mail_to": "tdd-1629@example.invalid",
    "telegram_bot_token": "", "telegram_chat_id": "",
    "telegram_test_bot_token": "", "telegram_test_chat_id": "",
    "sms_gateway_url": "", "seven_api_key": "", "sms_to": "",
}


def _settings_email_broken() -> Settings:
    settings = Settings(**_BROKEN_EMAIL_FIELDS)
    assert settings.can_send_email() is False, (
        "Vorbedingung: der E-Mail-Kanal darf NICHT sendefaehig sein, sonst "
        "wuerde dieser Test einen echten Verbindungsaufbau ausloesen."
    )
    assert settings.can_send_telegram() is False, (
        "Sicherung (#1477): Telegram darf hier nicht sendefaehig sein."
    )
    assert settings.can_send_sms() is False, (
        "Sicherung (#1477): SMS darf hier nicht sendefaehig sein."
    )
    return settings


def _location(loc_id: str, name: str, lat: float, lon: float) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=1000)


def _point(point_id: str, name: str, lat: float, lon: float, precip_sum_mm: float):
    """Echtes `PointWeatherData`-DTO (kein Mock)."""
    from services.point_weather import PointWeatherData

    return PointWeatherData(
        id=point_id, name=name, lat=lat, lon=lon, timeseries=None,
        aggregated=SegmentWeatherSummary(precip_sum_mm=precip_sum_mm),
        fetched_at=datetime.now(timezone.utc), provider="tdd-1629",
    )


class _ScriptedWeatherSource:
    """Echte `LocationWeatherSource`-Implementierung (kein Mock): vollstaendige,
    netzfreie Umsetzung des Protokolls aus `services/point_weather.py`."""

    def __init__(self, values: dict[str, float], names: dict[str, str]) -> None:
        self.values = dict(values)
        self._names = dict(names)
        self.fetch_calls: list[str] = []

    def fetch(self, point_id: str, lat: float, lon: float,
              start_hour: int | None = None, end_hour: int | None = None,
              target_date=None, tage_ab_ortstag=None, elevation_m=None):
        # `target_date`/`tage_ab_ortstag` (Issue #1661 Teil B): der
        # Versandpfad reicht den gebriefeten Tag als VERSATZ gegen den Ortstag
        # bis zum Δ-Anker durch, der Δ-Check spaeter den aufgeloesten absoluten
        # Tag; die Attrappe nimmt beides entgegen, statt an einem TypeError zu
        # scheitern.
        self.fetch_calls.append(point_id)
        return _point(point_id, self._names.get(point_id, point_id), lat, lon,
                      precip_sum_mm=self.values.get(point_id, 0.0))


def _preset(preset_id: str, location_ids: list[str]) -> dict:
    return {
        "id": preset_id, "name": preset_id, "location_ids": list(location_ids),
        "schedule": "daily", "weekday": 4, "profil": "ALLGEMEIN",
        "hour_from": 9, "hour_to": 16,
        "empfaenger": ["tdd-1629@example.invalid"],
        "letzter_versand": None, "top_ort_letzter_versand": None,
        "created_at": "2026-08-09T00:00:00Z", "kind": "vergleich",
    }


def _dp(hour: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(TARGET_DATE.year, TARGET_DATE.month, TARGET_DATE.day, hour, 0),
        t2m_c=22.0, wind_chill_c=21.0, wind10m_kmh=11.0, gust_kmh=19.0,
        precip_1h_mm=0.0, cloud_total_pct=35, uv_index=5.0,
        thunder_level=ThunderLevel.NONE, pop_pct=10, visibility_m=9000,
    )


def _install_comparison_engine_seam(monkeypatch) -> None:
    """Ersetzt NUR die teure Upstream-Abhaengigkeit `ComparisonEngine.run`
    (Live-Wetter fuer die Vergleichs-Mail) durch eine echte Unterklasse mit
    festen Werten — Haus-Muster aus
    `test_compare_briefing_anchor_and_memory_reset.py`."""
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
                created_at=datetime(TARGET_DATE.year, TARGET_DATE.month, TARGET_DATE.day, 4, 0),
            )

    monkeypatch.setattr(ce_mod, "ComparisonEngine", _FixedEngine)


def _install_anchor_weather_seam(monkeypatch, source: _ScriptedWeatherSource) -> None:
    """Der Δ-Anker-Schreiber (`_write_compare_alert_snapshots`) baut sich seine
    Wetterquelle selbst (Netz). Hier wird die KLASSE im Quellmodul durch eine
    gleichwertige, netzfreie Implementierung ersetzt — die Anker-Logik selbst
    (Schleife ueber ALLE Orte, `CompareWeatherSnapshotService.save`) laeuft
    unveraendert echt."""
    import services.compare_location_weather_source as clws_mod

    class _SourceFactory:
        def __new__(cls, *args, **kwargs):
            return source

    monkeypatch.setattr(clws_mod, "CompareLocationWeatherSource", _SourceFactory)


def _anchor_precip(user_id: str, preset_id: str, location_id: str) -> float | None:
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    points = CompareWeatherSnapshotService(user_id=user_id).load(preset_id, location_id)
    if not points:
        return None
    return points[0].aggregated.precip_sum_mm


@pytest.fixture
def compare_env(tmp_path, monkeypatch):
    """Isoliertes Arbeitsverzeichnis (Muster
    `test_compare_briefing_anchor_and_memory_reset.py::compare_env`)."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "users").mkdir(parents=True, exist_ok=True)
    return tmp_path


# ═══════════════════════════════ AC-2 (RED) ══════════════════════════════════


def test_ac2_versandfehler_schreibt_fuer_alle_orte_trotzdem_den_vergleichs_snapshot(
    compare_env, monkeypatch,
):
    """AC-2.

    GIVEN ein Ortsvergleich mit DREI Orten, dessen Versand mit einer Ausnahme
          scheitert (echter Konfigurations-Guard des E-Mail-Kanals).
    WHEN  der Versandlauf abgeschlossen ist.
    THEN  liegt fuer JEDEN Ort des Presets trotzdem der Vergleichs-Snapshot vor
          — dieselbe Zusicherung wie AC-1 auf der Trip-Seite.

    Drei Orte, nicht einer: der geteilte Baustein bekommt ausdruecklich ALLE
    Kennungen des Presets (Risiko R3 aus #1467 S2 AG5). Ein `except`-Zweig,
    der nur den ersten Ort ankert, faellt hier auf.

    RED heute: die Ausnahme ueberspringt `write_anchor_and_reset_memory(...)`
    (`scheduler_dispatch_service.py:423`) — kein Ort hat einen Snapshot.
    """
    from app.loader import get_data_root, save_location
    from output.channels.base import OutputConfigError
    from services.scheduler_dispatch_service import send_one_compare_preset

    uid = f"tdd-1629-ac2-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-1629-ac2-{uuid.uuid4().hex[:6]}"
    locations = [
        _location("loc-1629-a", "Alpenort", 47.0, 11.0),
        _location("loc-1629-b", "Bergort", 47.5, 11.5),
        _location("loc-1629-c", "Talort", 48.0, 12.0),
    ]
    for loc in locations:
        save_location(loc, user_id=uid)
    write_compare_briefings(
        get_data_root() / "users" / uid,
        [_preset(preset_id, [loc.id for loc in locations])],
    )

    settings = _settings_email_broken()
    _install_comparison_engine_seam(monkeypatch)
    source = _ScriptedWeatherSource(
        {loc.id: 12.0 + i for i, loc in enumerate(locations)},
        {loc.id: loc.name for loc in locations},
    )
    _install_anchor_weather_seam(monkeypatch, source)

    with pytest.raises(OutputConfigError) as excinfo:
        send_one_compare_preset(
            _preset(preset_id, [loc.id for loc in locations]),
            settings, uid, str(compare_env / "data"),
            all_locations_cache=list(locations), target_date=TARGET_DATE,
        tage_ab_ortstag=0,
        )
    assert "Incomplete SMTP configuration" in str(excinfo.value), (
        "Vorbedingung: die durchgereichte Ausnahme muss die des ECHTEN "
        f"E-Mail-Kanals sein, erhalten: {excinfo.value!r}"
    )

    fehlend = [
        loc.name for loc in locations
        if _anchor_precip(uid, preset_id, loc.id) is None
    ]
    assert fehlend == [], (
        "Nach einem gescheiterten Versand fehlt der Vergleichs-Snapshot fuer "
        f"{len(fehlend)} von {len(locations)} Orten ({fehlend!r}) — der "
        "Abweichungs-Alarm des Ortsvergleichs hat fuer diese Orte keinen "
        "Vergleichspunkt mehr (AC-2)"
    )
    for i, loc in enumerate(locations):
        assert _anchor_precip(uid, preset_id, loc.id) == pytest.approx(12.0 + i), (
            f"Der Vergleichs-Snapshot von {loc.name!r} traegt nicht den "
            f"Briefing-Stand: {_anchor_precip(uid, preset_id, loc.id)!r}"
        )


# ══════════════════ AC-7/AC-8-Naht, Vergleichs-Seite (F001) ══════════════════


def _dispatch_failure_journal(user_id: str) -> Path:
    """Die Ablage, die der Go-Leser aus AC-8 per Glob einliest
    (`users/<uid>/diagnostics/briefing_dispatch_failures.jsonl`)."""
    from app.loader import get_data_dir

    return get_data_dir(user_id) / "diagnostics" / "briefing_dispatch_failures.jsonl"


def test_versandfehler_des_ortsvergleichs_hinterlaesst_diagnose_spur_als_vergleich(
    compare_env, monkeypatch,
):
    """AC-7/AC-8-Naht, Ortsvergleich-Seite (Adversary-Finding F001).

    GIVEN ein Ortsvergleich, dessen Versand mit einer Ausnahme scheitert.
    WHEN  der Versandlauf abgeschlossen ist.
    THEN  traegt die Diagnose-Spur unter
          `users/<uid>/diagnostics/briefing_dispatch_failures.jsonl` einen
          Eintrag mit `kind == "vergleich"` UND `entity_id == preset_id`.

    Ohne diesen Test bliebe der Diagnose-Schreiber der Vergleichs-Seite
    vollstaendig ungeprueft: fuer einen Nutzer, der nur Ortsvergleiche und
    keine Trips betreibt, waere das Ausfall-Signal bei einem Regress stumm.
    Die Kennung `kind` traegt die Unterscheidung Trip/Vergleich — eine
    Verwechslung mit `"route"` faellt hier auf.
    """
    import json

    from app.loader import get_data_root, save_location
    from output.channels.base import OutputConfigError
    from services.scheduler_dispatch_service import send_one_compare_preset

    uid = f"tdd-1629-diag-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-1629-diag-{uuid.uuid4().hex[:6]}"
    locations = [
        _location("loc-1629-a", "Alpenort", 47.0, 11.0),
        _location("loc-1629-b", "Bergort", 47.5, 11.5),
    ]
    for loc in locations:
        save_location(loc, user_id=uid)
    write_compare_briefings(
        get_data_root() / "users" / uid,
        [_preset(preset_id, [loc.id for loc in locations])],
    )

    settings = _settings_email_broken()
    _install_comparison_engine_seam(monkeypatch)
    _install_anchor_weather_seam(monkeypatch, _ScriptedWeatherSource(
        {loc.id: 12.0 + i for i, loc in enumerate(locations)},
        {loc.id: loc.name for loc in locations},
    ))

    with pytest.raises(OutputConfigError):
        send_one_compare_preset(
            _preset(preset_id, [loc.id for loc in locations]),
            settings, uid, str(compare_env / "data"),
            all_locations_cache=list(locations), target_date=TARGET_DATE,
        tage_ab_ortstag=0,
        )

    journal = _dispatch_failure_journal(uid)
    assert journal.exists(), (
        "Ein gescheiterter Vergleichs-Versand muss dieselbe Diagnose-Spur "
        f"hinterlassen wie der Trip ({journal}) — sonst hat das Ausfall-Signal "
        "am Status-Endpunkt fuer reine Ortsvergleichs-Nutzer keine Quelle"
    )
    eintraege = [
        json.loads(z)
        for z in journal.read_text(encoding="utf-8").splitlines() if z.strip()
    ]
    treffer = [
        e for e in eintraege
        if e.get("kind") == "vergleich" and e.get("entity_id") == preset_id
    ]
    assert treffer, (
        "Die Diagnose-Spur braucht einen Eintrag mit kind='vergleich' und "
        f"entity_id={preset_id!r}; vorgefunden: {eintraege!r}. Ein als 'route' "
        "verbuchter Vergleichs-Ausfall weist den Fehlschlag der falschen "
        "Briefing-Art zu."
    )
