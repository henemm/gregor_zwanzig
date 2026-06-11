"""
Issue #456 — Compare Auto-Briefings: Manueller Versand-Trigger + Top-Ort-Anzeige.

Spec: docs/specs/modules/issue_456_compare_auto_briefings.md

Verhaltenstests (Python-Backend):
- AC-4: CompareSubscription hat top_ort_letzter_versand-Feld mit None-Default
- AC-4: load_compare_subscriptions() liest top_ort_letzter_versand aus JSON
- AC-4: _save_subscription() schreibt top_ort_letzter_versand in JSON
- AC-3: run_comparison_for_subscription() gibt 4-Tupel zurück (4. = Winner-Name)
- AC-3: POST /api/scheduler/subscriptions/{id}/send-Endpoint existiert

Sweep #754: Frontend-Quelltext-Checks (AutoReportCard.svelte, types.ts) entfernt.
AC-2-Frontend-Coverage: orts-vergleich-c1.spec.ts / issue-301b-auto-reports-overview.spec.ts.

Keine Mocks — alle Tests prüfen echte Klassen und reale Dateioperationen.
"""
import json
import os

import pytest


# ---------------------------------------------------------------------------
# AC-4: CompareSubscription Dataclass hat top_ort_letzter_versand
# ---------------------------------------------------------------------------

class TestCompareSubscriptionTopOrtField:
    """CompareSubscription muss top_ort_letzter_versand als optionales Feld haben."""

    def setup_method(self):
        from app.user import CompareSubscription
        self.CompareSubscription = CompareSubscription

    def test_has_top_ort_field_with_none_default(self):
        """
        GIVEN: CompareSubscription wird ohne top_ort_letzter_versand instanziiert
        WHEN: Attribut abgefragt
        THEN: Feld existiert mit Default None
        """
        sub = self.CompareSubscription(id="test", name="Test")
        assert hasattr(sub, "top_ort_letzter_versand"), (
            "CompareSubscription fehlt 'top_ort_letzter_versand'-Feld"
        )
        assert sub.top_ort_letzter_versand is None, (
            f"Default soll None, got {sub.top_ort_letzter_versand!r}"
        )

    def test_top_ort_can_be_set_via_constructor(self):
        """
        GIVEN: CompareSubscription mit gesetztem top_ort_letzter_versand
        WHEN: Attribut abgefragt
        THEN: Wert wird korrekt gespeichert
        """
        sub = self.CompareSubscription(
            id="test", name="Test", top_ort_letzter_versand="Ischgl"
        )
        assert sub.top_ort_letzter_versand == "Ischgl"

    def test_top_ort_accepts_none_explicitly(self):
        """
        GIVEN: CompareSubscription mit top_ort_letzter_versand=None
        WHEN: Attribut abgefragt
        THEN: Wert ist None (kein Fehler)
        """
        sub = self.CompareSubscription(
            id="test", name="Test", top_ort_letzter_versand=None
        )
        assert sub.top_ort_letzter_versand is None


# ---------------------------------------------------------------------------
# AC-4: load_compare_subscriptions() liest top_ort_letzter_versand aus JSON
# ---------------------------------------------------------------------------

class TestLoadCompareSubscriptionsTopOrtField:
    """load_compare_subscriptions() muss top_ort_letzter_versand einlesen."""

    def _write_fixture(self, tmp_path, data):
        users_dir = os.path.join(str(tmp_path), "users", "testuser")
        os.makedirs(users_dir, exist_ok=True)
        with open(os.path.join(users_dir, "compare_subscriptions.json"), "w") as f:
            json.dump(data, f)

    def _load_with_tmp_root(self, tmp_path):
        import app.loader as loader_module
        original = getattr(loader_module, "_DATA_ROOT", None)
        loader_module._DATA_ROOT = str(tmp_path)
        try:
            from app.loader import load_compare_subscriptions
            return load_compare_subscriptions(user_id="testuser")
        finally:
            if original is not None:
                loader_module._DATA_ROOT = original
            elif hasattr(loader_module, "_DATA_ROOT"):
                del loader_module._DATA_ROOT

    def test_loads_top_ort_from_json(self, tmp_path):
        """
        GIVEN: compare_subscriptions.json enthält top_ort_letzter_versand
        WHEN: load_compare_subscriptions() aufgerufen
        THEN: CompareSubscription.top_ort_letzter_versand == gespeicherter Wert
        """
        self._write_fixture(tmp_path, {
            "subscriptions": [{
                "id": "sub-1",
                "name": "Ski-Vergleich",
                "schedule": "daily_morning",
                "forecast_hours": 48,
                "time_window_start": 9,
                "time_window_end": 16,
                "top_n": 3,
                "top_ort_letzter_versand": "Stubai",
            }]
        })
        subs = self._load_with_tmp_root(tmp_path)
        assert len(subs) == 1
        assert subs[0].top_ort_letzter_versand == "Stubai", (
            f"top_ort_letzter_versand wurde nicht geladen: {subs[0].top_ort_letzter_versand!r}"
        )

    def test_backward_compat_json_without_top_ort_field(self, tmp_path):
        """
        GIVEN: compare_subscriptions.json hat KEIN top_ort_letzter_versand (alt)
        WHEN: load_compare_subscriptions() aufgerufen
        THEN: CompareSubscription.top_ort_letzter_versand == None (kein Fehler)
        """
        self._write_fixture(tmp_path, {
            "subscriptions": [{
                "id": "sub-old",
                "name": "Alt-Sub",
                "schedule": "weekly",
                "forecast_hours": 48,
                "time_window_start": 9,
                "time_window_end": 16,
                "top_n": 3,
            }]
        })
        subs = self._load_with_tmp_root(tmp_path)
        assert len(subs) == 1
        assert subs[0].top_ort_letzter_versand is None, (
            "Bestandsdaten ohne top_ort_letzter_versand sollen None ergeben"
        )


# ---------------------------------------------------------------------------
# AC-4: _save_subscription() schreibt top_ort_letzter_versand in JSON
# ---------------------------------------------------------------------------

class TestSaveSubscriptionTopOrtField:
    """_save_subscription() muss top_ort_letzter_versand in die JSON schreiben."""

    def test_save_subscription_writes_top_ort(self, tmp_path):
        """
        GIVEN: compare_subscriptions.json enthält eine Subscription
        WHEN: _save_subscription() mit top_ort_letzter_versand='Ischgl' aufgerufen
        THEN: JSON enthält danach top_ort_letzter_versand == 'Ischgl'
        """
        import api.routers.scheduler as sched_module
        users_dir = os.path.join(str(tmp_path), "users", "testuser")
        os.makedirs(users_dir, exist_ok=True)
        json_path = os.path.join(users_dir, "compare_subscriptions.json")
        with open(json_path, "w") as f:
            json.dump({"subscriptions": [{"id": "sub-top", "name": "T"}]}, f)

        from app.user import CompareSubscription
        sub = CompareSubscription(
            id="sub-top",
            name="T",
            last_run="2026-05-30T06:00:00Z",
            last_status="ok",
            top_ort_letzter_versand="Ischgl",
        )
        sched_module._save_subscription("testuser", sub, data_root=str(tmp_path))

        with open(json_path) as f:
            updated = json.load(f)
        entry = updated["subscriptions"][0]
        assert "top_ort_letzter_versand" in entry, (
            f"top_ort_letzter_versand fehlt in gespeicherter JSON: {entry}"
        )
        assert entry["top_ort_letzter_versand"] == "Ischgl", (
            f"Falscher Wert: {entry['top_ort_letzter_versand']!r}"
        )

    def test_save_subscription_preserves_existing_top_ort_when_none(self, tmp_path):
        """
        GIVEN: JSON enthält bereits top_ort_letzter_versand='Stubai'
        WHEN: _save_subscription() mit top_ort_letzter_versand=None aufgerufen
        THEN: Vorhandener Wert 'Stubai' bleibt erhalten (None überschreibt nicht)
        """
        import api.routers.scheduler as sched_module
        users_dir = os.path.join(str(tmp_path), "users", "testuser")
        os.makedirs(users_dir, exist_ok=True)
        json_path = os.path.join(users_dir, "compare_subscriptions.json")
        with open(json_path, "w") as f:
            json.dump({
                "subscriptions": [{
                    "id": "sub-keep",
                    "name": "K",
                    "top_ort_letzter_versand": "Stubai",
                }]
            }, f)

        from app.user import CompareSubscription
        sub = CompareSubscription(
            id="sub-keep",
            name="K",
            last_status="error",
            top_ort_letzter_versand=None,
        )
        sched_module._save_subscription("testuser", sub, data_root=str(tmp_path))

        with open(json_path) as f:
            updated = json.load(f)
        entry = updated["subscriptions"][0]
        assert entry.get("top_ort_letzter_versand") == "Stubai", (
            "None soll den vorherigen Wert nicht überschreiben"
        )


# ---------------------------------------------------------------------------
# AC-3: run_comparison_for_subscription() gibt 4-Tupel zurück
# ---------------------------------------------------------------------------

def _make_test_locations():
    """Erstellt Fixture-Standorte für run_comparison-Tests (kein load_all_locations nötig)."""
    from app.user import SavedLocation
    return [
        SavedLocation(id="loc-456-a", name="Innsbruck", lat=47.27, lon=11.40, elevation_m=574),
        SavedLocation(id="loc-456-b", name="Chamonix", lat=45.92, lon=6.87, elevation_m=1035),
    ]


class TestRunComparisonReturnsWinnerName:
    """run_comparison_for_subscription() muss 4-Tupel (subject, html, text, winner) zurückgeben."""

    def test_returns_4_tuple(self):
        """
        GIVEN: Gültige CompareSubscription mit 2 Fixture-Standorten
        WHEN: run_comparison_for_subscription(sub, locations) aufgerufen
        THEN: Rückgabe ist 4-Tupel; 4. Element ist str oder None.

        Fixture-Standorte werden direkt übergeben (kein load_all_locations).
        Verhindert Fehlschlag wegen leerer Nutzerdaten in der Test-Umgebung.
        """
        from services.compare_subscription import run_comparison_for_subscription
        from app.user import CompareSubscription, Schedule

        locations = _make_test_locations()
        sub = CompareSubscription(
            id="test-456-tdd",
            name="TDD Issue 456",
            locations=[loc.id for loc in locations],
            schedule=Schedule.DAILY_MORNING,
            enabled=True,
        )
        result = run_comparison_for_subscription(sub, locations)

        assert isinstance(result, tuple), f"Kein Tupel: {type(result)}"
        assert len(result) == 4, (
            f"Erwartet 4-Tupel (subject, html, text, winner), got {len(result)}-Tupel"
        )
        subject, html_body, text_body, winner_name = result
        assert isinstance(subject, str), f"subject kein str: {type(subject)}"
        assert isinstance(html_body, str), f"html_body kein str: {type(html_body)}"
        assert isinstance(text_body, str), f"text_body kein str: {type(text_body)}"
        assert winner_name is None or isinstance(winner_name, str), (
            f"winner_name muss str oder None sein, got {type(winner_name)}"
        )

    def test_winner_name_matches_location_name(self):
        """
        GIVEN: Subscription mit 2 Fixture-Standorten
        WHEN: run_comparison_for_subscription(sub, locations) aufgerufen
        THEN: 4. Element (winner_name) ist str (bekannter Ortsname) oder None.
        """
        from services.compare_subscription import run_comparison_for_subscription
        from app.user import CompareSubscription, Schedule

        locations = _make_test_locations()
        sub = CompareSubscription(
            id="test-456-tdd-winner",
            name="TDD Winner Test",
            locations=[loc.id for loc in locations],
            schedule=Schedule.DAILY_MORNING,
            enabled=True,
        )
        result = run_comparison_for_subscription(sub, locations)
        _, _, _, winner_name = result

        known_names = {loc.name for loc in locations}
        if winner_name is not None:
            assert winner_name in known_names, (
                f"winner_name '{winner_name}' ist kein bekannter Ortsname: {known_names}"
            )


# ---------------------------------------------------------------------------
# AC-3: POST /api/scheduler/subscriptions/{id}/send-Endpoint existiert
# ---------------------------------------------------------------------------

class TestManualSendEndpoint:
    """POST /api/scheduler/subscriptions/{id}/send muss existieren."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from api.main import app
        return TestClient(app)

    def test_manual_send_endpoint_returns_subscription_not_found(self, client):
        """
        GIVEN: Unbekannte subscription_id
        WHEN: POST /api/scheduler/subscriptions/nonexistent-id/send?user_id=default
        THEN: HTTP 404 mit detail='Subscription not found' (nicht generisches FastAPI-404)
        """
        resp = client.post(
            "/api/scheduler/subscriptions/nonexistent-id-xyz/send",
            params={"user_id": "default"},
        )
        assert resp.status_code == 404, (
            f"Erwartet 404, got {resp.status_code}"
        )
        data = resp.json()
        # FastAPI-generisches 404 hat detail='Not Found'
        # Unser Endpoint soll 'Subscription not found' zurückgeben
        detail = data.get("detail", "")
        assert "subscription" in detail.lower() or "not found" in detail.lower(), (
            f"detail soll 'Subscription not found' lauten, got: {detail!r}"
        )
        assert detail != "Not Found", (
            "Generisches FastAPI-404 — Route existiert noch nicht. "
            f"Erwartet Subscription-spezifischen 404-Text, got: {detail!r}"
        )

    def test_manual_send_endpoint_is_post_method(self, client):
        """
        GIVEN: Endpoint-Pfad /api/scheduler/subscriptions/{id}/send
        WHEN: GET-Anfrage (falsche Methode)
        THEN: HTTP 405 Method Not Allowed (beweist: Route ist registriert, nur POST erlaubt)
        """
        resp = client.get(
            "/api/scheduler/subscriptions/any-id/send",
            params={"user_id": "default"},
        )
        assert resp.status_code == 405, (
            f"GET soll 405 zurückgeben (Route existiert, falsche Methode), got {resp.status_code}"
        )


# AC-2 Frontend-Quelltext-Checks (AutoReportCard.svelte, types.ts) wurden in #754
# entfernt — Verhaltens-Coverage durch E2E:
# - orts-vergleich-c1.spec.ts (Vergleichs-Karten mit top_ort_letzter_versand)
# - issue-301b-auto-reports-overview.spec.ts (Auto-Report-Übersicht)
