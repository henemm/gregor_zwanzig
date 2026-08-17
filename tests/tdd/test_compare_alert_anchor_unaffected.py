"""TDD — Issue #1916, AC-13 (Compare-Pfad bleibt von der rollierenden
Trip-Basis unberuehrt).

SPEC: docs/specs/modules/trip_alert.md v3.0, AC-13.

``compare_alert.py``/``CompareWeatherSnapshotService`` nutzen eine eigene,
undatierte Snapshot-Mechanik ohne #823-Tagesgrenze. AC-Gruppe B (dritter
Anker-Typ, Hybrid-Trigger, 4h-Ceiling) ist bewusst auf den TRIP-Pfad
beschraenkt (Spec "Known Limitations").

Issue #765 (Backend-Hygiene-Gate, Fix-Loop 2): die urspruengliche Fassung
dieser Datei bewachte die Zusicherung per ``ast.parse(pfad.read_text(...))``
auf ``compare_alert.py``/``compare_location_weather_source.py`` -- das Gate
``test_765_backend_hygiene_compliance.py`` verbietet JEDES ``read_text()``
auf Produkt-Quelltext aus Testdateien, unabhaengig vom Zweck danach. Diese
Fassung ersetzt den Quellcode-Scan durch ECHTES Verhalten: ein realer
Compare-Check-Lauf (``CompareAlertService.check_all_compare_presets()``,
Vorbild ``test_alert_reference_timestamp.py::
test_ac4_compare_wiring_ueber_echten_aufrufpfad_liefert_referenz_zeitpunkt``)
wird ausgefuehrt und (a) per zaehlendem Wrapper (kein ``Mock()``, die echte
Methode bleibt aufrufbar) beobachtet, ob die Trip-eigenen rollierenden
Anker-Funktionen aufgerufen werden, und (b) per Dateisystem-Assertion
geprueft, dass NUR Compare-eigene Snapshot-Dateien entstehen.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.loader import get_data_dir, get_snapshots_dir, save_location
from app.models import SegmentWeatherSummary
from app.user import SavedLocation
from services.compare_alert import CompareAlertService
from services.compare_weather_snapshot import CompareWeatherSnapshotService
from services.point_weather import PointWeatherData
from services.weather_snapshot import WeatherSnapshotService
from tests.helpers.alert_log_fixtures import settings_email_only
from tests.helpers.compare_briefings import write_compare_briefings


class _FixedWeatherSource:
    """Deterministischer `LocationWeatherSource`-Impl (kein Mock) — liefert
    einen festen Frischwert, Vorbild `_ScriptedWeatherSource` aus
    `test_issue_1169_compare_alert_consumer.py`."""

    def __init__(self, precip_sum_mm: float) -> None:
        self._val = precip_sum_mm

    def fetch(self, point_id, lat, lon, start_hour=None, end_hour=None):
        return PointWeatherData(
            id=point_id, name=point_id, lat=lat, lon=lon, timeseries=None,
            aggregated=SegmentWeatherSummary(precip_sum_mm=self._val),
            fetched_at=datetime.now(timezone.utc), provider="test",
        )


def _run_compare_check(uid: str, preset_id: str, location_id: str):
    """Ein realer, ausloesender Compare-Check-Lauf — echtes Preset, echter
    Ort, echter `CompareWeatherSnapshotService`-Anker, `mail_sink`-Capture
    statt SMTP. Delta 18 mm >= Standard-Schwelle 10 mm loest aus."""
    loc = SavedLocation(id=location_id, name="Vergleichsort", lat=47.0, lon=11.0, elevation_m=1000)
    save_location(loc, user_id=uid)
    preset = {
        "id": preset_id, "name": preset_id, "user_id": "default",
        "location_ids": [location_id], "schedule": "daily", "weekday": 4,
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "empfaenger": ["dummy@example.com"], "letzter_versand": None,
        "top_ort_letzter_versand": None, "created_at": "2026-07-09T00:00:00Z",
        "cooldown_minutes": 0,
    }
    write_compare_briefings(get_data_dir(uid), [preset])

    CompareWeatherSnapshotService(user_id=uid).save(
        preset_id, location_id,
        PointWeatherData(
            id=location_id, name=loc.name, lat=loc.lat, lon=loc.lon, timeseries=None,
            aggregated=SegmentWeatherSummary(precip_sum_mm=2.0),
            fetched_at=datetime.now(timezone.utc) - timedelta(hours=1), provider="test",
        ),
    )

    mails: list[tuple[str, str]] = []
    service = CompareAlertService(
        settings=settings_email_only(), user_id=uid,
        weather_source=_FixedWeatherSource(20.0),
        mail_sink=lambda subject, body: mails.append((subject, body)),
    )
    sent = service.check_all_compare_presets()
    return sent, mails


def test_ac13_kein_compare_lauf_ruft_den_rollierenden_trip_anker_auf(monkeypatch):
    """AC-13: ein realer Compare-Check-Lauf darf `WeatherSnapshotService.
    save_alarm_anchor()`/`.load_alarm_anchor()` (Trip-eigener rollierender
    Anker, Issue #1916 Slice 2) NIE aufrufen.

    Zaehlender Wrapper statt Mock (CLAUDE.md: kein `Mock()`, der nur die
    eigene Annahme zurueckspiegelt) — die echten Methoden bleiben
    aufrufbar, nur der Aufruf wird mitgezaehlt.
    """
    calls = {"save": 0, "load": 0}
    orig_save = WeatherSnapshotService.save_alarm_anchor
    orig_load = WeatherSnapshotService.load_alarm_anchor

    def _counting_save(self, *args, **kwargs):
        calls["save"] += 1
        return orig_save(self, *args, **kwargs)

    def _counting_load(self, *args, **kwargs):
        calls["load"] += 1
        return orig_load(self, *args, **kwargs)

    monkeypatch.setattr(WeatherSnapshotService, "save_alarm_anchor", _counting_save)
    monkeypatch.setattr(WeatherSnapshotService, "load_alarm_anchor", _counting_load)

    uid = f"tdd-1916-ac13-{uuid.uuid4().hex[:8]}"
    sent, mails = _run_compare_check(uid, "cp-1916-ac13", "loc-ac13")

    assert sent == 1, "Fixtur-Schutz: das Delta (18 mm) muss ausloesen."
    assert mails, "Fixtur-Schutz: es muss eine Mail geben."
    assert calls == {"save": 0, "load": 0}, (
        f"AC-13: der Compare-Pfad hat die Trip-eigenen rollierenden "
        f"Anker-Funktionen aufgerufen ({calls}) — Slice 2 (dritter "
        f"Anker-Typ, Hybrid-Trigger, 4h-Ceiling) muss auf den Trip-Pfad "
        f"beschraenkt bleiben (Spec 'Known Limitations')."
    )


def test_ac13_regression_compare_snapshot_bleibt_eigenstaendig():
    """Regression: ein realer Compare-Check-Lauf erzeugt/aktualisiert NUR
    Compare-eigene Snapshot-Dateien (`{preset_id}__{location_id}.json`),
    NIE Trip-Snapshot-Dateien (`WeatherSnapshotService`-Ablage) fuer
    dieselben Kennungen — Dateisystem-Assertion statt Quellcode-Scan."""
    uid = f"tdd-1916-ac13reg-{uuid.uuid4().hex[:8]}"
    preset_id, location_id = "cp-1916-ac13reg", "loc-ac13reg"
    sent, mails = _run_compare_check(uid, preset_id, location_id)

    assert sent == 1, "Fixtur-Schutz: das Delta (18 mm) muss ausloesen."
    assert mails, "Fixtur-Schutz: es muss eine Mail geben."

    compare_file = get_data_dir(uid) / "compare_weather_snapshots" / f"{preset_id}__{location_id}.json"
    assert compare_file.exists(), (
        "Fixtur-Schutz: der Compare-eigene Snapshot muss existieren."
    )

    trip_snapshots_dir = get_snapshots_dir(uid)
    for verbotener_name in (
        f"{preset_id}.json",
        f"{location_id}.json",
        f"{preset_id}_alarm_anchor.json",
        f"{location_id}_alarm_anchor.json",
    ):
        assert not (trip_snapshots_dir / verbotener_name).exists(), (
            f"AC-13: Trip-Snapshot-Datei {verbotener_name!r} existiert unter "
            f"{trip_snapshots_dir} — der Compare-Pfad darf die Trip-eigene "
            f"WeatherSnapshotService-Ablage nie beschreiben."
        )
