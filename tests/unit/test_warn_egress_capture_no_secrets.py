"""TDD RED — Issue #1948 (Scheibe S1): der Zweig-b-Eingangs-Datensatz
enthaelt keine Request-Header/Auth-Parameter, weil sie der Capture-Funktion
strukturell nicht uebergeben werden.

SPEC: docs/specs/modules/alarm_eingangsprotokoll.md (AC-7)

RED-Grund: ``alert_input_capture.py`` existiert nicht; ``cached_fetch()``
schreibt an ihrer ``on_response``-Stelle noch keinen Eingangs-Datensatz.
"""
from __future__ import annotations

import inspect
import json

import httpx


def _capture_dir():
    from app.loader import get_data_root

    return get_data_root() / "debug" / "alert_input" / "official_alert"


def _fixed_clock(value: float):
    return lambda: value


def test_ac7_response_header_landet_nicht_in_der_capture_datei(monkeypatch, tmp_path):
    """AC-7: GIVEN eine echte Response traegt einen Header mit einem
    (testweise eingebauten) Geheimnis, WHEN ``cached_fetch`` sie an der
    ``on_response``-Stelle mitschneidet, THEN taucht das Geheimnis in
    KEINER geschriebenen Datei auf -- die Schreibstelle nimmt nur den
    geparsten Body plus Service/Host/Status entgegen."""
    from services.official_alerts import warn_egress

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "warn_service_calls.jsonl"
    )
    secret = "tdd-1948-geheimes-token-9f8e7d"

    warn_egress.cached_fetch(
        cache={}, cache_key="AT-1948-no-secret", service="meteoalarm",
        host="api.meteoalarm.org",
        request_fn=lambda: httpx.Response(
            200, json={"features": []},
            headers={"Authorization": f"Bearer {secret}", "X-Api-Key": secret},
        ),
        parse_fn=lambda r: r.json(),
        clock=_fixed_clock(3000.0),
    )

    files = list(_capture_dir().glob("*.json"))
    assert files, (
        "Kein Eingangs-Datensatz geschrieben -- Voraussetzung fuer die "
        "Geheimnis-Pruefung fehlt."
    )
    for f in files:
        raw_text = f.read_text()
        assert secret not in raw_text, (
            f"Geheimnis aus dem Response-Header wurde mitgeschrieben: {f}"
        )
        record = json.loads(raw_text)
        assert "headers" not in record.get("payload", {}), (
            f"Die Capture-Datei enthaelt ein 'headers'-Feld: {record!r}"
        )


def test_ac7_capture_system_nimmt_keine_header_oder_request_parameter_entgegen():
    """AC-7 (Signatur-Zusicherung): ``capture_system()`` besitzt
    strukturell KEINEN Parameter fuer Header/Request/Auth -- ein Geheimnis
    kann also gar nicht erst hereingereicht werden, unabhaengig vom
    Aufrufer-Verhalten (kein nachtraeglicher Filter noetig)."""
    from services import alert_input_capture

    sig = inspect.signature(alert_input_capture.capture_system)
    forbidden = {"headers", "request", "auth", "response", "resp"}
    leaked = forbidden & set(sig.parameters)
    assert not leaked, (
        f"capture_system() nimmt einen Header-/Request-nahen Parameter "
        f"entgegen: {leaked!r} -- Geheimnisse koennten so hereingereicht "
        "werden."
    )
