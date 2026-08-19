"""TDD RED — Issue #1916, AC-12 (der rollierende Schreibpfad darf das
Melde-Gedaechtnis NICHT zuruecksetzen).

SPEC: docs/specs/modules/trip_alert.md v3.0, AC-12; ADR-0056 "Negativ/Preis".

``write_anchor_and_reset_memory()`` koppelt Anker-Schreiben MIT
Melde-Gedaechtnis-Reset (``alert_briefing_anchor.py:254``). Der neue
rollierende Schreibpfad MUSS einen eigenen, schlankeren Pfad OHNE diesen
Reset nutzen -- sonst wuerden bereits gemeldete Werte nach jedem Alarm/jeder
Ceiling-Ueberschreitung erneut als "neu" gemeldet.

Nachweis: eine Melde-Gedaechtnis-Kennung, die vom AUSGELOESTEN Alarm dieses
Laufs NICHT betroffen ist (anderes Segment), bleibt nach dem Lauf exakt
unveraendert. Ein voller Reset (``AlertStateService.reset()``) wuerde diese
Kennung loeschen -- ein normales Fortschreiben der GETROFFENEN Kennung(en)
laesst sie unberuehrt.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from tests.helpers.alert_log_fixtures import gust_alert_trip, settings_email_only, weather


def test_ac12_rollierender_schreibpfad_setzt_melde_gedaechtnis_nicht_zurueck():
    from services.alert_state import AlertStateService
    from services.trip_alert import TripAlertService
    from services.weather_snapshot import WeatherSnapshotService

    user_id, trip_id = f"tdd-1916-ac12-{uuid.uuid4().hex[:8]}", "trip-ac12"
    state_svc = AlertStateService(user_id=user_id)
    unberuehrter_eintrag = {
        "last_reported_value": 3.0,
        "reported_at": datetime.now(timezone.utc).isoformat(),
    }
    # Kennung eines ANDEREN Segments -- der ausgeloeste Alarm dieses Laufs
    # betrifft Segment "1" (gust:1), nicht Segment "99".
    state_svc.save(trip_id, {"gust:99": unberuehrter_eintrag})

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

    assert ausgeloest, "Fixtur-Schutz: der Alarm muss ausgeloest haben."
    # HEUTE ROT: load_alarm_anchor() existiert nicht -> AttributeError,
    # ein direkter Beleg, dass der neue Schreibpfad (Trigger a) fehlt.
    anker = WeatherSnapshotService(user_id=user_id).load_alarm_anchor(trip_id, "email")
    assert anker, "Fixtur-Schutz: Trigger (a) muss einen rollierenden Anker erzeugt haben."

    nachher = state_svc.load(trip_id)
    assert nachher.get("gust:99") == unberuehrter_eintrag, (
        "AC-12: der rollierende Schreibpfad darf das Melde-Gedaechtnis NICHT "
        f"zuruecksetzen. Vorher: {unberuehrter_eintrag}, nachher: "
        f"{nachher.get('gust:99')} (vollstaendiges Gedaechtnis: {nachher})."
    )
