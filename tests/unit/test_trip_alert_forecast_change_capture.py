"""TDD RED — Issue #1948 (Scheibe S1): Zweig-a-Mount schreibt vor dem
Alarmversand einen rohen Eingangs-Datensatz.

SPEC: docs/specs/modules/alarm_eingangsprotokoll.md (AC-1)
Kontext: docs/context/feat-1948-eingangsprotokoll.md

RED-Grund: ``src/services/alert_input_capture.py`` existiert noch nicht --
``check_and_send_alerts()`` in ``trip_alert.py`` ruft an ihrem Delta-Alarm-
Mount-Punkt (vor ``_send_alert``, trip_alert.py ~Z. 333-352) noch keinen
Capture-Aufruf auf. Der Import innerhalb der Testfunktion (nicht auf
Modulebene) schlaegt daher mit ``ModuleNotFoundError`` fehl -- Collection
der Datei bleibt trotzdem intakt.

Mock-frei: echter ``TripAlertService``-Lauf (Vorbild
``tests/tdd/test_alert_log_metrics.py``), echte Persistenz ueber die
pytest-isolierte ``get_data_dir()``-Basis (#1133), Transport ueber den
bestehenden ``mail_sink``-DI-Seam.
"""
from __future__ import annotations

import json

from tests.helpers.alert_log_fixtures import (
    fresh_user, gust_alert_trip, settings_email_only, weather,
)


def _service(user_id: str, sink: list):
    from services.trip_alert import TripAlertService

    return TripAlertService(
        settings=settings_email_only(), user_id=user_id, throttle_hours=0,
        mail_sink=lambda subject, body: sink.append((subject, body)),
    )


def _capture_files(user_id: str) -> list:
    from app.loader import get_data_dir

    d = get_data_dir(user_id) / "alert_input"
    if not d.exists():
        return []
    return sorted(d.glob("forecast_change_*.json"))


def test_ac1_delta_alarm_schreibt_rohen_eingangsdatensatz_vor_versand():
    """AC-1: GIVEN ein Trip loest einen Boeen-Delta-Alarm (20 -> 60 km/h)
    aus, WHEN ``check_and_send_alerts`` die Aenderungsliste gebildet hat und
    den Alarm verschickt, THEN liegt unter
    ``data/users/<uid>/alert_input/`` ein Eingangs-Datensatz mit den rohen
    Aenderungswerten (Metrik, alter/neuer Wert, Delta, Schwelle)."""
    uid = fresh_user("ac1-capture")
    trip = gust_alert_trip("trip-ac1-capture")
    mails: list = []

    sent = _service(uid, mails).check_and_send_alerts(
        trip, [weather(1, gust_max_kmh=20.0)],
        fresh_weather=[weather(1, gust_max_kmh=60.0)],
    )

    assert sent is True and mails, (
        "Voraussetzung: der Alarm muss tatsaechlich verschickt werden."
    )
    files = _capture_files(uid)
    assert files, (
        f"Kein Eingangs-Datensatz unter data/users/{uid}/alert_input/ "
        "gefunden -- alert_input_capture.capture_user_scoped() wurde am "
        "Delta-Alarm-Mount-Punkt (trip_alert.py) nicht aufgerufen."
    )
    record = json.loads(files[-1].read_text())
    assert record.get("entity_type") == "trip", (
        f"Falscher/fehlender entity_type: {record.get('entity_type')!r}"
    )
    assert record.get("entity_id") == "trip-ac1-capture", (
        f"Falsche/fehlende entity_id: {record.get('entity_id')!r}"
    )
    assert record.get("capture_id"), "capture_id fehlt im Eingangs-Datensatz."

    changes = record.get("payload", {}).get("changes")
    assert changes, f"Der Datensatz enthaelt keine rohen Aenderungswerte: {record!r}"
    # Rohes WeatherChange.metric-Feld (Rohdaten-Vokabular, z.B.
    # "gust_max_kmh"), NICHT das Register-Paar ("gust","max") aus
    # alert_log.register_pairs_from_changes() -- das ist eine spaetere
    # Projektion, kein roher Eingangswert (AC-1 verlangt genau die rohen
    # Aenderungswerte).
    gust = next((c for c in changes if c.get("metric") == "gust_max_kmh"), None)
    assert gust is not None, f"Erwartete Metrik 'gust_max_kmh' fehlt: {changes!r}"
    assert gust["old_value"] == 20.0
    assert gust["new_value"] == 60.0
    assert gust["delta"] == 40.0
    assert "threshold" in gust and "severity" in gust and "direction" in gust, (
        f"Aenderungs-Eintrag ist unvollstaendig: {gust!r}"
    )
