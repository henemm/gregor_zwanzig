"""TDD RED — Issue #1948 (Scheibe S1): Feldnamen/-typen des Zweig-a-
Datensatzes decken ``ChangePayload`` (``api/routers/validator.py``)
verlustfrei ab -- Schema-/Attributvergleich, kein Dateiinhalt-Stringcheck.

SPEC: docs/specs/modules/alarm_eingangsprotokoll.md (AC-9)

RED-Grund: ``services.alert_input_capture`` existiert nicht -- kein
Eingangs-Datensatz zum Vergleichen.

Der Typ-Nachweis laeuft ueber eine ECHTE Pydantic-Konstruktion von
``ChangePayload`` aus den geschriebenen Feldern (kein reiner
Namensabgleich) -- genau das, was Scheibe S2 ("ohne Transformation
einspeisen") tatsaechlich braucht.
"""
from __future__ import annotations

import json

from api.routers.validator import ChangePayload

from tests.helpers.alert_log_fixtures import (
    fresh_user, gust_alert_trip, settings_email_only, weather,
)


def _service(user_id: str, sink: list):
    from services.trip_alert import TripAlertService

    return TripAlertService(
        settings=settings_email_only(), user_id=user_id, throttle_hours=0,
        mail_sink=lambda subject, body: sink.append((subject, body)),
    )


def test_ac9_zweig_a_change_felder_decken_changepayload_verlustfrei_ab():
    """AC-9: GIVEN ein Eingangs-Datensatz fuer Zweig a wurde geschrieben,
    WHEN seine ``changes``-Eintraege mit ``ChangePayload`` verglichen
    werden, THEN deckt jeder Eintrag ALLE Pflichtfelder von
    ``ChangePayload`` ab, mit kompatiblem Typ -- Scheibe S2 kann ihn ohne
    Transformation in ``alert-preview`` einspeisen."""
    from app.loader import get_data_dir

    uid = fresh_user("ac9-schema")
    trip = gust_alert_trip("trip-ac9-schema")
    mails: list = []

    sent = _service(uid, mails).check_and_send_alerts(
        trip, [weather(1, gust_max_kmh=20.0)],
        fresh_weather=[weather(1, gust_max_kmh=60.0)],
    )
    assert sent is True and mails

    files = sorted((get_data_dir(uid) / "alert_input").glob("*.json"))
    assert files, (
        "Kein Eingangs-Datensatz geschrieben -- Voraussetzung fuer den "
        "Schema-Vergleich fehlt."
    )
    record = json.loads(files[-1].read_text())
    changes = record.get("payload", {}).get("changes")
    assert changes, f"Der Datensatz enthaelt keine 'changes': {record!r}"

    required_fields = set(ChangePayload.model_fields)
    for change in changes:
        missing = required_fields - set(change)
        assert not missing, (
            f"Aenderungs-Eintrag deckt ChangePayload nicht verlustfrei ab "
            f"-- fehlende Felder: {missing!r}, Eintrag: {change!r}"
        )
        # Echte Pydantic-Validierung statt reinem Namensabgleich: beweist
        # Typ-Kompatibilitaet, nicht nur gleiche Schluesselnamen.
        ChangePayload(**{k: change[k] for k in required_fields})
