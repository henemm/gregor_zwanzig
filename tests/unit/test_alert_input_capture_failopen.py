"""TDD RED — Issue #1948 (Scheibe S1): ein fehlschlagender Capture-
Schreibvorgang verhindert den Alarmversand NICHT (fail-open, gleiches
Muster wie ``alert_log._append()``/``weather_snapshot.save_dated()``).

SPEC: docs/specs/modules/alarm_eingangsprotokoll.md (AC-8)

RED-Grund: ``services.alert_input_capture`` existiert nicht; der
Delta-Alarm-Mount-Punkt in ``trip_alert.py`` ruft noch keinen
Capture-Aufruf auf, kann also auch keinen Fehlschlag abfangen.

Der Schreibfehler wird ueber einen echten Dateisystem-Konflikt erzwungen
(eine reguläre Datei liegt dort, wo das Ablageverzeichnis entstehen
muesste) -- kein Mock, kein Rechte-Trickser (portabel).
"""
from __future__ import annotations

import logging

from tests.helpers.alert_log_fixtures import (
    fresh_user, gust_alert_trip, settings_email_only, weather,
)


def _service(user_id: str, sink: list):
    from services.trip_alert import TripAlertService

    return TripAlertService(
        settings=settings_email_only(), user_id=user_id, throttle_hours=0,
        mail_sink=lambda subject, body: sink.append((subject, body)),
    )


def test_ac8_kaputtes_capture_verzeichnis_verhindert_alarmversand_nicht(caplog):
    """AC-8: GIVEN das Ablageverzeichnis fuer den Eingangs-Datensatz ist
    strukturell blockiert (eine Datei liegt dort, wo ein Verzeichnis
    entstehen muesste), WHEN der Delta-Alarm-Zweig weiterlaeuft, THEN wird
    der Alarm trotzdem verschickt, und der Fehlschlag erscheint
    ausschliesslich als Log-Warnung, nie als Exception nach oben."""
    from app.loader import get_data_dir

    uid = fresh_user("ac8-failopen")
    data_dir = get_data_dir(uid)
    data_dir.mkdir(parents=True, exist_ok=True)
    # Blockiert: "alert_input" existiert bereits als DATEI, nicht als
    # Verzeichnis -- ein echter, deterministischer Fehlschlag.
    (data_dir / "alert_input").write_text("blockiert absichtlich (AC-8)")

    trip = gust_alert_trip("trip-ac8-failopen")
    mails: list = []

    with caplog.at_level(logging.WARNING):
        sent = _service(uid, mails).check_and_send_alerts(
            trip, [weather(1, gust_max_kmh=20.0)],
            fresh_weather=[weather(1, gust_max_kmh=60.0)],
        )

    assert sent is True and mails, (
        "Der Alarm haette trotz kaputtem Capture-Verzeichnis versendet "
        "werden muessen (fail-open) -- stattdessen wurde der Versand "
        "verhindert."
    )
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings, (
        "Der fehlgeschlagene Capture-Schreibvorgang haette als Log-Warnung "
        "erscheinen muessen."
    )


def test_ac8_capture_user_scoped_selbst_wirft_bei_schreibfehler_nicht(caplog):
    """AC-8 (direkter Unit-Nachweis): ``capture_user_scoped()`` selbst
    faengt einen Schreibfehler ab, gibt ``None`` zurueck (statt zu werfen)
    und loggt eine Warnung."""
    from app.loader import get_data_dir
    from services import alert_input_capture

    uid = fresh_user("ac8-direct")
    data_dir = get_data_dir(uid)
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "alert_input").write_text("blockiert absichtlich (AC-8, direkt)")

    with caplog.at_level(logging.WARNING):
        result = alert_input_capture.capture_user_scoped(
            uid, entity_type="trip", entity_id="direct-failopen",
            payload={"changes": []},
        )

    assert result is None, (
        f"Bei einem Schreibfehler muss None zurueckkommen (fail-open), "
        f"erhalten: {result!r}"
    )
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings, "Kein Log-Warning bei fehlgeschlagenem Schreibvorgang."
