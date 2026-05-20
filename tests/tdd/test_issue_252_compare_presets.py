"""
TDD RED: Issue #252 — Compare Presets: recipients, last_run/last_status,
CompareSubscriptionsPanel.

Spec: docs/specs/modules/issue_252_compare_presets.md

Testet:
- AC-5: EmailOutput.send() mit to-Parameter
- AC-6: CompareSubscription hat recipients/last_run/last_status mit Defaults
- AC-6: load_compare_subscriptions() liest neue Felder aus JSON
- AC-1: Scheduler schreibt last_run/last_status nach Lauf in JSON zurück

Keine Mocks — alle Tests prüfen echte Klassen und reale Dateioperationen.
"""
import inspect
import json
import os

import pytest


# ---------------------------------------------------------------------------
# AC-6: CompareSubscription Dataclass hat neue Felder mit korrekten Defaults
# ---------------------------------------------------------------------------

class TestCompareSubscriptionNewFields:
    """CompareSubscription muss recipients, last_run, last_status haben."""

    def setup_method(self):
        from app.user import CompareSubscription
        self.CompareSubscription = CompareSubscription

    def test_has_recipients_field_with_empty_list_default(self):
        sub = self.CompareSubscription(id="test", name="Test")
        assert hasattr(sub, "recipients"), "CompareSubscription fehlt 'recipients'-Feld"
        assert sub.recipients == [], f"Default soll [], got {sub.recipients!r}"

    def test_has_last_run_field_with_none_default(self):
        sub = self.CompareSubscription(id="test", name="Test")
        assert hasattr(sub, "last_run"), "CompareSubscription fehlt 'last_run'-Feld"
        assert sub.last_run is None, f"Default soll None, got {sub.last_run!r}"

    def test_has_last_status_field_with_none_default(self):
        sub = self.CompareSubscription(id="test", name="Test")
        assert hasattr(sub, "last_status"), "CompareSubscription fehlt 'last_status'-Feld"
        assert sub.last_status is None, f"Default soll None, got {sub.last_status!r}"

    def test_recipients_can_be_set_via_constructor(self):
        sub = self.CompareSubscription(id="test", name="Test", recipients=["a@test.com"])
        assert sub.recipients == ["a@test.com"]

    def test_last_status_can_be_set_as_string(self):
        sub = self.CompareSubscription(id="test", name="Test", last_status="ok")
        assert sub.last_status == "ok"


# ---------------------------------------------------------------------------
# AC-6: load_compare_subscriptions() liest neue Felder aus JSON
# ---------------------------------------------------------------------------

class TestLoadCompareSubscriptionsNewFields:
    """load_compare_subscriptions() muss recipients/last_run/last_status einlesen."""

    def _write_fixture(self, tmp_dir: str, data: dict) -> None:
        users_dir = os.path.join(tmp_dir, "users", "testuser")
        os.makedirs(users_dir, exist_ok=True)
        with open(os.path.join(users_dir, "compare_subscriptions.json"), "w") as f:
            json.dump(data, f)

    def _with_tmp_root(self, tmp_path, fn):
        import app.loader as loader_module
        original = getattr(loader_module, "_DATA_ROOT", None)
        loader_module._DATA_ROOT = str(tmp_path)
        try:
            return fn()
        finally:
            if original is not None:
                loader_module._DATA_ROOT = original
            elif hasattr(loader_module, "_DATA_ROOT"):
                del loader_module._DATA_ROOT

    def test_loads_recipients_from_json(self, tmp_path):
        self._write_fixture(
            str(tmp_path),
            {"subscriptions": [{"id": "s1", "name": "T", "recipients": ["a@x.com"]}]},
        )
        from app.loader import load_compare_subscriptions
        subs = self._with_tmp_root(tmp_path, lambda: load_compare_subscriptions(user_id="testuser"))
        assert subs[0].recipients == ["a@x.com"]

    def test_backward_compat_json_without_new_fields(self, tmp_path):
        self._write_fixture(
            str(tmp_path),
            {"subscriptions": [{"id": "old", "name": "Old"}]},
        )
        from app.loader import load_compare_subscriptions
        subs = self._with_tmp_root(tmp_path, lambda: load_compare_subscriptions(user_id="testuser"))
        assert subs[0].recipients == []
        assert subs[0].last_run is None
        assert subs[0].last_status is None

    def test_loads_last_run_and_last_status_from_json(self, tmp_path):
        ts = "2026-05-20T06:00:00Z"
        self._write_fixture(
            str(tmp_path),
            {"subscriptions": [{"id": "d", "name": "D", "last_run": ts, "last_status": "ok"}]},
        )
        from app.loader import load_compare_subscriptions
        subs = self._with_tmp_root(tmp_path, lambda: load_compare_subscriptions(user_id="testuser"))
        assert subs[0].last_run == ts
        assert subs[0].last_status == "ok"


# ---------------------------------------------------------------------------
# AC-5: EmailOutput.send() akzeptiert optionalen to-Parameter
# ---------------------------------------------------------------------------

class TestEmailOutputToParameter:
    """EmailOutput.send() muss optionalen 'to: list[str] | None'-Parameter haben."""

    def test_send_signature_has_to_parameter(self):
        from outputs.email import EmailOutput
        sig = inspect.signature(EmailOutput.send)
        assert "to" in sig.parameters, (
            f"EmailOutput.send() fehlt 'to'-Parameter. Aktuell: {list(sig.parameters.keys())}"
        )

    def test_send_to_parameter_has_none_default(self):
        from outputs.email import EmailOutput
        sig = inspect.signature(EmailOutput.send)
        to_param = sig.parameters.get("to")
        assert to_param is not None
        assert to_param.default is not inspect.Parameter.empty, "'to' muss Default haben"
        assert to_param.default is None, f"Default soll None, got {to_param.default!r}"


# ---------------------------------------------------------------------------
# AC-1: Scheduler schreibt last_run/last_status nach Lauf in JSON zurück
# ---------------------------------------------------------------------------

class TestSchedulerWritesRunStatus:
    """Scheduler muss _save_subscription() haben und Status korrekt schreiben."""

    def test_save_subscription_function_exists(self):
        import api.routers.scheduler as sched_module
        assert hasattr(sched_module, "_save_subscription"), (
            "api/routers/scheduler.py fehlt _save_subscription()-Funktion"
        )

    def test_save_subscription_writes_last_run_to_json(self, tmp_path):
        import api.routers.scheduler as sched_module
        users_dir = os.path.join(str(tmp_path), "users", "testuser")
        os.makedirs(users_dir, exist_ok=True)
        json_path = os.path.join(users_dir, "compare_subscriptions.json")
        ts = "2026-05-20T14:00:00Z"
        with open(json_path, "w") as f:
            json.dump({"subscriptions": [{"id": "sub-abc", "name": "T"}]}, f)

        from app.user import CompareSubscription
        sub = CompareSubscription(id="sub-abc", name="T", last_run=ts, last_status="ok")
        sched_module._save_subscription("testuser", sub, data_root=str(tmp_path))

        with open(json_path) as f:
            updated = json.load(f)
        entry = updated["subscriptions"][0]
        assert entry["last_run"] == ts, f"last_run nicht in JSON: {entry}"
        assert entry["last_status"] == "ok"

    def test_save_subscription_preserves_other_fields(self, tmp_path):
        import api.routers.scheduler as sched_module
        users_dir = os.path.join(str(tmp_path), "users", "testuser")
        os.makedirs(users_dir, exist_ok=True)
        json_path = os.path.join(users_dir, "compare_subscriptions.json")
        with open(json_path, "w") as f:
            json.dump(
                {"subscriptions": [{"id": "abc", "name": "Keep", "locations": ["l1"], "recipients": ["r@x.com"]}]},
                f,
            )
        from app.user import CompareSubscription
        sub = CompareSubscription(id="abc", name="Keep", last_status="error")
        sched_module._save_subscription("testuser", sub, data_root=str(tmp_path))

        with open(json_path) as f:
            updated = json.load(f)
        entry = updated["subscriptions"][0]
        assert entry["locations"] == ["l1"]
        assert entry.get("recipients") == ["r@x.com"]
        assert entry["last_status"] == "error"
