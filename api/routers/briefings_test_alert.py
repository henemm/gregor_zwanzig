"""Test-Alarm ``POST /api/briefings/{entity_id}/test-alert?kind=route|vergleich`` (#3441).

Spec: docs/specs/modules/feat_3441_test_alarm.md

Muster ``briefings_send.py``: ``user_id`` setzt der Go-Proxy aus der Anmeldung,
Eigentum prueft der user-scoped Loader (fremde oder unbekannte ID -> 404),
Fehler kommen ausschliesslich aus ``send_outcomes``. Antwort: ``sent_channels``
sowie ``skipped_channels``/``failed_channels`` als ``[{channel, reason}]`` mit
dem Grund in der Sprache des Nutzers.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Query

from api.routers.briefings_send import _KINDS, _error
from app.loader import InvalidUserIdError
from i18n import resolve_user_lang, t

router = APIRouter(tags=["briefings"])
logger = logging.getLogger("briefings_test_alert")


def _abo(kind: str, entity_id: str, user_id: str):
    """Trip (``app.trip.Trip``) bzw. Vergleich (Rohdict) DIESES Nutzers oder ``None``."""
    if kind == "route":
        from app.loader import load_all_trips

        return next((t for t in load_all_trips(user_id=user_id) if t.id == entity_id), None)
    from services.compare_preset_access import load_compare_alert_presets

    return next((p for p in load_compare_alert_presets(user_id) if p.get("id") == entity_id), None)


def _liste(kanaele: dict[str, str], lang) -> list[dict]:
    return [{"channel": ch, "reason": t(f"versand.test_alarm.grund.{grund}", lang)}
            for ch, grund in kanaele.items()]


def alarm_test_senden(kind: str | None, entity_id: str, user_id: str):
    """Test-Alarm je ``kind``; Fehler als ``{"detail", "code"}`` (4xx/5xx)."""
    from services.alert_test_service import AlertTestService, TestAlarmAbgelehnt

    if kind not in _KINDS:
        return _error("kind_required", user_id)
    try:
        abo = _abo(kind, entity_id, user_id)
        if abo is None:
            return _error("not_found", user_id, entity_id=entity_id)
        ergebnis = AlertTestService(user_id).senden(abo)
    except InvalidUserIdError:
        return _error("not_found", user_id, entity_id=entity_id)
    except TestAlarmAbgelehnt as e:
        return _error(e.code, user_id)
    except Exception:
        logger.exception("Test-Alarm %s/%s (user %s) fehlgeschlagen", kind, entity_id, user_id)  # i18n-log
        return _error("send_failed", user_id)
    lang = resolve_user_lang(user_id)
    return {
        "status": "ok", "kind": kind, "id": entity_id,
        "sent_channels": ergebnis.sent,
        "skipped_channels": _liste(ergebnis.skipped, lang),
        "failed_channels": _liste(ergebnis.failed, lang),
    }


@router.post("/api/briefings/{entity_id}/test-alert")
def test_alert_endpoint(entity_id: str, user_id: str = Query(...), kind: str | None = Query(None)):
    """Beispiel-Alarm mit echten Werten an alle Alarm-Kanaele des Nutzers."""
    return alarm_test_senden(kind, entity_id, user_id)
