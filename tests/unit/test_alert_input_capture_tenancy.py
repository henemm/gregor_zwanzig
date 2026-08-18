"""TDD RED — Issue #1948 (Scheibe S1): zwei Nutzer bekommen getrennte
Ablageverzeichnisse; ``user_id`` ist Pflichtparameter OHNE Default (kein
stiller ``"default"``-Fallback).

SPEC: docs/specs/modules/alarm_eingangsprotokoll.md (AC-6)

RED-Grund: ``services.alert_input_capture`` existiert nicht.
"""
from __future__ import annotations

import inspect
import json
import uuid


def _uid(prefix: str) -> str:
    return f"tdd-1948-tenancy-{prefix}-{uuid.uuid4().hex[:6]}"


def _payload() -> dict:
    return {"changes": [{
        "metric": "gust", "old_value": 1.0, "new_value": 2.0, "delta": 1.0,
        "threshold": 0.5, "severity": "minor", "direction": "increase",
        "segment_id": "1",
    }]}


def test_ac6_zwei_nutzer_erzeugen_getrennte_verzeichnisse():
    """AC-6: GIVEN zwei verschiedene Nutzer A und B loesen unabhaengig je
    einen Delta-Alarm aus, WHEN beide Eingangs-Datensaetze geschrieben
    werden, THEN liegt der Datensatz von A ausschliesslich unter
    ``data/users/<uid_A>/alert_input/`` und der von B ausschliesslich
    unter ``data/users/<uid_B>/alert_input/``."""
    from app.loader import get_data_dir
    from services import alert_input_capture

    uid_a, uid_b = _uid("a"), _uid("b")

    alert_input_capture.capture_user_scoped(
        uid_a, entity_type="trip", entity_id="trip-a", payload=_payload(),
    )
    alert_input_capture.capture_user_scoped(
        uid_b, entity_type="trip", entity_id="trip-b", payload=_payload(),
    )

    files_a = list((get_data_dir(uid_a) / "alert_input").glob("*.json"))
    files_b = list((get_data_dir(uid_b) / "alert_input").glob("*.json"))
    assert files_a and files_b, "Beide Nutzer muessen je einen Datensatz bekommen."

    entities_a = {json.loads(f.read_text()).get("entity_id") for f in files_a}
    entities_b = {json.loads(f.read_text()).get("entity_id") for f in files_b}
    assert "trip-b" not in entities_a, (
        f"Nutzer A hat Daten von Nutzer B in seinem Verzeichnis: {entities_a!r}"
    )
    assert "trip-a" not in entities_b, (
        f"Nutzer B hat Daten von Nutzer A in seinem Verzeichnis: {entities_b!r}"
    )


def test_ac6_user_id_ist_pflichtparameter_ohne_default():
    """AC-6: ``capture_user_scoped`` darf ``user_id`` KEINEN Default-Wert
    geben -- eine vergessene ``user_id`` an der Aufrufstelle soll knallen
    statt still auf ``"default"`` zurueckzufallen (Mandantentrennungs-
    Regel, CLAUDE.md)."""
    from services import alert_input_capture

    sig = inspect.signature(alert_input_capture.capture_user_scoped)
    user_id_param = sig.parameters.get("user_id")
    assert user_id_param is not None, (
        "capture_user_scoped hat keinen user_id-Parameter."
    )
    assert user_id_param.default is inspect.Parameter.empty, (
        f"user_id hat einen Default-Wert ({user_id_param.default!r}) -- das "
        "ermoeglicht einen stillen 'default'-Fallback und verstoesst gegen "
        "die Mandantentrennungs-Regel."
    )
