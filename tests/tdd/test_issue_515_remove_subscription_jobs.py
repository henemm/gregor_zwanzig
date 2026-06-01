"""
TDD RED: Tests für Issue #515 — Entfernung obsoleter Subscription-Jobs.

SPEC: docs/specs/modules/issue_515_remove_subscription_jobs.md

Jeder Test prüft, dass zu löschender Code NICHT mehr vorhanden ist.
Schlägt jetzt FEHL (RED), weil der Code noch existiert.
Nach der Implementierung müssen alle Tests GRÜN sein.

KEINE MOCKS — Projektkonvention (CLAUDE.md).
"""
from __future__ import annotations

from pathlib import Path

import pytest


SCHEDULER_PY = Path(__file__).parent.parent.parent / "api" / "routers" / "scheduler.py"
GO_SCHEDULER = Path(__file__).parent.parent.parent / "internal" / "scheduler" / "scheduler.go"
GO_CONFIG = Path(__file__).parent.parent.parent / "internal" / "config" / "config.go"
TEST_509 = Path(__file__).parent / "test_issue_509_preset_migration.py"


# ---------------------------------------------------------------------------
# AC-2: Python-Funktionen entfernt
# ---------------------------------------------------------------------------

class TestPythonFunctionsRemoved:
    """_run_subscriptions_by_schedule und _run_weekly_subscriptions dürfen nicht existieren."""

    def test_run_subscriptions_by_schedule_not_importable(self):
        """
        GIVEN: api.routers.scheduler nach dem Cleanup
        WHEN: _run_subscriptions_by_schedule importiert wird
        THEN: ImportError — Funktion existiert nicht mehr

        Schlägt FEHL weil Funktion noch vorhanden.
        """
        with pytest.raises(ImportError):
            from api.routers.scheduler import _run_subscriptions_by_schedule  # noqa: F401

    def test_run_weekly_subscriptions_not_importable(self):
        """
        GIVEN: api.routers.scheduler nach dem Cleanup
        WHEN: _run_weekly_subscriptions importiert wird
        THEN: ImportError — Funktion existiert nicht mehr

        Schlägt FEHL weil Funktion noch vorhanden.
        """
        with pytest.raises(ImportError):
            from api.routers.scheduler import _run_weekly_subscriptions  # noqa: F401


# ---------------------------------------------------------------------------
# AC-2: Python-Endpoints entfernt
# ---------------------------------------------------------------------------

class TestPythonEndpointsRemoved:
    """Die FastAPI-Endpoints /morning-subscriptions und /evening-subscriptions dürfen nicht registriert sein."""

    def test_morning_subscriptions_endpoint_absent(self):
        """
        GIVEN: scheduler.py Quelltext nach dem Cleanup
        WHEN: Datei auf morning-subscriptions-Route geprüft
        THEN: Kein Treffer — Endpoint ist entfernt

        Schlägt FEHL weil Endpoint noch vorhanden.
        """
        source = SCHEDULER_PY.read_text(encoding="utf-8")
        assert "/morning-subscriptions" not in source, (
            "Endpoint /morning-subscriptions noch in scheduler.py vorhanden"
        )

    def test_evening_subscriptions_endpoint_absent(self):
        """
        GIVEN: scheduler.py Quelltext nach dem Cleanup
        WHEN: Datei auf evening-subscriptions-Route geprüft
        THEN: Kein Treffer — Endpoint ist entfernt

        Schlägt FEHL weil Endpoint noch vorhanden.
        """
        source = SCHEDULER_PY.read_text(encoding="utf-8")
        assert "/evening-subscriptions" not in source, (
            "Endpoint /evening-subscriptions noch in scheduler.py vorhanden"
        )


# ---------------------------------------------------------------------------
# AC-3: Doppelversand-Guard entfernt
# ---------------------------------------------------------------------------

class TestGuardRemoved:
    """Der data_root-Parameter und der Doppelversand-Guard dürfen nicht mehr existieren."""

    def test_no_double_dispatch_guard_comment(self):
        """
        GIVEN: scheduler.py Quelltext nach dem Cleanup
        WHEN: Datei auf Guard-Kommentar geprüft
        THEN: Kein Treffer — Guard-Code ist entfernt

        Schlägt FEHL weil Guard-Code noch vorhanden.
        """
        source = SCHEDULER_PY.read_text(encoding="utf-8")
        assert "Doppelversand-Guard" not in source, (
            "Doppelversand-Guard-Code noch in scheduler.py vorhanden"
        )

    def test_no_preset_path_check_in_scheduler(self):
        """
        GIVEN: scheduler.py Quelltext nach dem Cleanup
        WHEN: Datei auf presets.json-Existenz-Check (aus Guard) geprüft
        THEN: Kein Treffer mehr für _preset_path

        Schlägt FEHL weil Guard-Variable _preset_path noch vorhanden.
        """
        source = SCHEDULER_PY.read_text(encoding="utf-8")
        assert "_preset_path" not in source, (
            "_preset_path (Guard-Variable) noch in scheduler.py vorhanden"
        )


# ---------------------------------------------------------------------------
# AC-1: Go-Scheduler-Jobs entfernt
# ---------------------------------------------------------------------------

class TestGoSchedulerJobsRemoved:
    """morning_subscriptions und evening_subscriptions dürfen im Go-Scheduler nicht mehr vorkommen."""

    def test_morning_subscriptions_absent_in_go_scheduler(self):
        """
        GIVEN: internal/scheduler/scheduler.go nach dem Cleanup
        WHEN: Datei auf morningSubscriptions geprüft
        THEN: Kein Treffer — Methode ist entfernt

        Schlägt FEHL weil Methode noch vorhanden.
        """
        source = GO_SCHEDULER.read_text(encoding="utf-8")
        assert "morningSubscriptions" not in source, (
            "morningSubscriptions noch in scheduler.go vorhanden"
        )

    def test_evening_subscriptions_absent_in_go_scheduler(self):
        """
        GIVEN: internal/scheduler/scheduler.go nach dem Cleanup
        WHEN: Datei auf eveningSubscriptions geprüft
        THEN: Kein Treffer — Methode ist entfernt

        Schlägt FEHL weil Methode noch vorhanden.
        """
        source = GO_SCHEDULER.read_text(encoding="utf-8")
        assert "eveningSubscriptions" not in source, (
            "eveningSubscriptions noch in scheduler.go vorhanden"
        )

    def test_heartbeat_morning_absent_in_go_config(self):
        """
        GIVEN: internal/config/config.go nach dem Cleanup
        WHEN: Datei auf HeartbeatMorning geprüft
        THEN: Kein Treffer — Feld ist entfernt

        Schlägt FEHL weil Feld noch vorhanden.
        """
        source = GO_CONFIG.read_text(encoding="utf-8")
        assert "HeartbeatMorning" not in source, (
            "HeartbeatMorning noch in config.go vorhanden"
        )

    def test_heartbeat_evening_absent_in_go_config(self):
        """
        GIVEN: internal/config/config.go nach dem Cleanup
        WHEN: Datei auf HeartbeatEvening geprüft
        THEN: Kein Treffer — Feld ist entfernt

        Schlägt FEHL weil Feld noch vorhanden.
        """
        source = GO_CONFIG.read_text(encoding="utf-8")
        assert "HeartbeatEvening" not in source, (
            "HeartbeatEvening noch in config.go vorhanden"
        )


# ---------------------------------------------------------------------------
# AC-5: TestDoubleDispatchGuard-Klasse entfernt
# ---------------------------------------------------------------------------

class TestGuardTestsRemoved:
    """Die TestDoubleDispatchGuard-Klasse darf in der Testdatei nicht mehr vorhanden sein."""

    def test_double_dispatch_guard_class_absent(self):
        """
        GIVEN: tests/tdd/test_issue_509_preset_migration.py nach dem Cleanup
        WHEN: Datei auf TestDoubleDispatchGuard geprüft
        THEN: Kein Treffer — Klasse ist entfernt

        Schlägt FEHL weil Klasse noch vorhanden.
        """
        source = TEST_509.read_text(encoding="utf-8")
        assert "TestDoubleDispatchGuard" not in source, (
            "TestDoubleDispatchGuard noch in test_issue_509_preset_migration.py vorhanden"
        )
