"""TDD RED — Issue #1916, AC-11 (Radar-Alert-Unterdrueckung #818/#1667 bleibt
vom rollierenden Anker unberuehrt).

SPEC: docs/specs/modules/trip_alert.md v3.0, AC-11; ADR-0056.

Die Radar-Unterdrueckung liest ausschliesslich den Briefing-Anker
(``{trip_id}_{date}.json`` via ``load_dated()``, ``trip_alert.py:1068``) als
eingefrorene Prognose. Der neue rollierende Anker-Schreibpfad liegt in einem
EIGENEN Speicherort (kein ``save_dated()``-Umwidmen, s. ADR-0056) -- diese
Datei prueft, dass ein rollierender Schreibvorgang die Briefing-Anker-Datei
weder inhaltlich noch zeitlich (mtime) anfasst.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.loader import get_snapshots_dir

from tests.helpers.alert_log_fixtures import gust_alert_trip, settings_email_only, weather


def test_ac11_briefing_anker_datei_bleibt_unberuehrt_von_rollierenden_schreibvorgaengen():
    """HEUTE ROT: ``load_alarm_anchor()`` existiert nicht -> AttributeError.
    Nach der Implementierung: ein Trigger-(a)-Schreibvorgang (echter Alarm)
    darf ``{trip_id}_{date}.json`` nicht veraendern.
    """
    from services.trip_alert import TripAlertService
    from services.weather_snapshot import WeatherSnapshotService

    user_id, trip_id = f"tdd-1916-ac11-{uuid.uuid4().hex[:8]}", "trip-ac11"
    heute = datetime.now(timezone.utc).date()
    snap_svc = WeatherSnapshotService(user_id=user_id)
    snap_svc.save_dated(trip_id, heute, [weather(1, gust_max_kmh=5.0)])
    briefing_pfad = get_snapshots_dir(user_id) / f"{trip_id}_{heute.isoformat()}.json"
    vor_inhalt = briefing_pfad.read_bytes()
    vor_mtime = briefing_pfad.stat().st_mtime_ns

    trip = gust_alert_trip(trip_id)
    # Issue #1987 (S1): der rollierende Anker rueckt seither NUR fuer
    # tatsaechlich ZUGESTELLTE Kanaele vor. Ohne die `mail_sink`-Naht
    # scheitert der E-Mail-Versand am Egress-Waechter, `delivered_channels`
    # bliebe leer und der Fixtur-Schutz unten haette nichts zu finden --
    # kein Mock, dieselbe Transportnaht wie in `test_alert_anchor_day_guard`.
    svc = TripAlertService(
        settings=settings_email_only(), user_id=user_id,
        mail_sink=lambda subject, body: None,
    )
    ausgeloest = svc.check_and_send_alerts(
        trip, [weather(1, gust_max_kmh=10.0)],
        fresh_weather=[weather(1, gust_max_kmh=150.0)],
    )

    assert ausgeloest, "Fixtur-Schutz: der Alarm (Trigger a) muss ausgeloest haben."
    anker = snap_svc.load_alarm_anchor(trip_id, "email")
    assert anker, "Fixtur-Schutz: der rollierende Anker muss geschrieben worden sein."
    assert briefing_pfad.read_bytes() == vor_inhalt, (
        "AC-11: die Briefing-Anker-Datei darf durch den rollierenden "
        "Schreibpfad NICHT inhaltlich veraendert werden -- sie ist die "
        "eingefrorene Prognose der Radar-Unterdrueckung (#818/#1667)."
    )
    assert briefing_pfad.stat().st_mtime_ns == vor_mtime, (
        "AC-11: die mtime der Briefing-Anker-Datei hat sich veraendert -- "
        "ein rollierender Schreibpfad darf diese Datei nicht anfassen."
    )
