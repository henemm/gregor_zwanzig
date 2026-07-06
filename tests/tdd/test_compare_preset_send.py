"""TDD RED — Issue #627: Compare-Preset Einzel-Sofortversand (Python-Core).

Spec: docs/specs/modules/issue_627_631_compare_send_rhythm.md (AC-4)

Echte Aufrufe — KEINE Mocks:
  - FastAPI TestClient ist ein echter ASGI-Call (kein Mock).
  - _send_compare_preset arbeitet gegen ein echtes temporäres compare_presets.json.

SOLL-Verhalten nach Fix:
  - api.routers.scheduler._send_compare_preset(user_id, preset_id, data_root=...)
    existiert und sendet das Vergleichs-Briefing sofort (ignoriert schedule).
  - Ohne Empfänger UND ohne mail_to-Fallback → Fehler (Exception oder
    Rückgabe mit Fehlerstatus), NICHT still "ok".
  - POST /api/scheduler/compare-presets/{id}/send?user_id=... existiert;
    unbekannte ID → HTTP 404.

RED-Erwartung (vor Fix):
  - ImportError: _send_compare_preset existiert nicht.
  - Endpoint fehlt → POST liefert kein 404 vom SOLL-Endpoint (Route fehlt).
"""
import json

import pytest
from fastapi.testclient import TestClient

from api.main import app


class TestComparePresetSend:
    """Issue #627 — Einzel-Sofortversand für ein Compare-Preset."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def _write_preset(self, data_root, user_id, preset):
        """Lege ein Test-Preset in einem temporären data_root an."""
        user_dir = data_root / "users" / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / "compare_presets.json").write_text(
            json.dumps([preset], ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ── AC-4: Preset ohne Empfänger + ohne mail_to-Fallback → Fehler ──────────

    def test_send_without_recipients_signals_error(self, tmp_path):
        """Preset OHNE empfaenger und ohne mail_to-Fallback darf NICHT still 'ok'.

        RED: api.routers.scheduler._send_compare_preset existiert noch nicht
        → ImportError beim Import.
        """
        from services.scheduler_dispatch_service import send_compare_preset as _send_compare_preset

        user_id = "u1"
        preset = {
            "id": "cp-no-recipients",
            "name": "Ohne Empfänger",
            "user_id": user_id,
            "location_ids": ["loc-a"],
            "schedule": "manual",
            "profil": "SUMMER_TREKKING",
            "hour_from": 9,
            "hour_to": 16,
            "empfaenger": [],  # bewusst leer
            "created_at": "2026-01-01T00:00:00Z",
        }
        self._write_preset(tmp_path, user_id, preset)

        error_signalled = False
        try:
            result = _send_compare_preset(
                user_id, "cp-no-recipients", data_root=str(tmp_path)
            )
            status = (result or {}).get("status")
            error_signalled = status not in ("ok", None) or "error" in (result or {})
        except Exception:
            error_signalled = True

        assert error_signalled, (
            "Preset ohne Empfänger und ohne mail_to-Fallback muss einen Fehler "
            "signalisieren (Exception oder Fehlerstatus) — kein stiller 'ok'-Erfolg."
        )

    # ── Endpoint: unbekannte Preset-ID → HTTP 404 ─────────────────────────────

    def test_send_endpoint_unknown_id_returns_404(self, client, tmp_path):
        """POST /api/scheduler/compare-presets/{unbekannt}/send → fachliches 404.

        WICHTIG: FastAPI liefert für eine FEHLENDE Route ebenfalls ein generisches
        404 ({"detail":"Not Found"}). Damit dieser Test ein echtes RED ist und
        NICHT durch die abwesende Route grün scheint, muss er einen vorhandenen
        Endpoint mit einem FACHLICHEN Not-Found unterscheiden:
          - Der SOLL-Endpoint liefert bei unbekannter Preset-ID eine Detail-/Error-
            Meldung, die das Preset benennt (z.B. "preset"/"not found"/"nicht
            gefunden"), nicht das nackte Routing-"Not Found".

        RED (vor Fix): Route fehlt → FastAPI-Routing-404 mit detail=="Not Found"
        → die fachliche Assertion schlägt fehl.
        """
        # Existierenden, aber leeren User anlegen, damit der Endpoint einen echten
        # Lookup macht statt am Routing zu scheitern.
        user_dir = tmp_path / "users" / "u1"
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / "compare_presets.json").write_text("[]", encoding="utf-8")

        resp = client.post(
            "/api/scheduler/compare-presets/cp-does-not-exist/send",
            params={"user_id": "u1"},
        )
        assert resp.status_code == 404, (
            f"Erwartet 404 für unbekanntes Preset, bekam {resp.status_code} "
            f"(body={resp.text!r})."
        )
        detail = ""
        try:
            body = resp.json()
            detail = str(body.get("detail") or body.get("error") or "").lower()
        except Exception:
            detail = resp.text.lower()
        assert detail and detail != "not found", (
            f"Erwartet ein FACHLICHES Not-Found (Preset benannt), bekam generisches "
            f"Routing-404 {detail!r} — Endpoint /compare-presets/{{id}}/send fehlt (RED)."
        )
