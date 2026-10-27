"""TDD RED — Issue #2286 AC-9: amtliche Warnungen laufen im `compare-alert-checks`-Job mit.

SPEC: docs/specs/modules/fix_2286_compare_betrieb_health.md (Implementierungsdetail 7, AC-9)

Beim Trip laufen amtliche Warnungen im `alert_checks`-Job mit; beim Vergleich
gab es bisher einen eigenen Job + Endpoint `compare-official-alert-checks`.
Soll: `POST /api/scheduler/compare-alert-checks` fuehrt Abweichungs-Alarme
(`CompareAlertService`) UND amtliche Warnungen (`CompareOfficialAlertService`)
aus, JEDEN in eigenem try-Block; `count`/`failed` werden summiert; wirft
einer, laeuft der andere trotzdem und der Fehler zaehlt als `failed`. Der
Official-Endpoint entfaellt.

Naht: echte Unterklassen beider Services (Muster Engine-Subklasse), die den
Lauf aufzeichnen bzw. einen Fehler einspeisen -- per `monkeypatch.setattr` auf
das Modul-Attribut, das der Router zur Laufzeit importiert. Gepruefter
Gegenstand ist die Router-Orchestrierung (Aufruf, Isolation, Summierung,
Nutzer-Durchreichung), nicht der Service-Inhalt.
"""
from __future__ import annotations

import uuid

import pytest


@pytest.fixture
def services(monkeypatch):
    """Ersetzt beide Services durch aufzeichnende Unterklassen. `plan` steuert
    je Service das Ergebnis: (count, failed) oder eine Ausnahme."""
    import services.compare_alert as ca_mod
    import services.compare_official_alert as coa_mod

    calls: list[tuple[str, str]] = []
    plan: dict[str, object] = {"alert": (2, 1), "official": (3, 0)}

    def _make(base, name):
        class _Recording(base):  # echte Unterklasse, kein Mock
            def __init__(self, *args, user_id: str, **kwargs):
                self._user_id = user_id
                self.last_failed_count = 0
                self.last_checked_count = 0
                self.last_duration_s = 0.0

            def check_all_compare_presets(self) -> int:
                calls.append((name, self._user_id))
                outcome = plan[name]
                if isinstance(outcome, Exception):
                    raise outcome
                count, failed = outcome
                self.last_failed_count = failed
                self.last_checked_count = 1
                self.last_duration_s = 0.01
                return count

        return _Recording

    monkeypatch.setattr(ca_mod, "CompareAlertService", _make(ca_mod.CompareAlertService, "alert"))
    monkeypatch.setattr(
        coa_mod, "CompareOfficialAlertService",
        _make(coa_mod.CompareOfficialAlertService, "official"),
    )
    return calls, plan


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from api.main import app

    return TestClient(app, raise_server_exceptions=False)


def _post(client, uid: str):
    return client.post(f"/api/scheduler/compare-alert-checks?user_id={uid}")


def test_both_services_run_and_counts_are_summed(client, services):
    """Given beide Teile laufen fehlerfrei / When `compare-alert-checks` laeuft
    / Then wurden BEIDE Services fuer genau diesen Nutzer ausgefuehrt, und
    `count`/`failed` sind summiert (2+3, 1+0).

    RED: heute laeuft nur `CompareAlertService`."""
    calls, _ = services
    uid = f"tdd-2286-ac9-{uuid.uuid4().hex[:8]}"

    resp = _post(client, uid)

    assert resp.status_code == 200, resp.text
    assert sorted(calls) == [("alert", uid), ("official", uid)], (
        f"AC-9: beide Teile muessen fuer genau diesen Nutzer laufen, kam {calls!r}"
    )
    body = resp.json()
    assert (body["count"], body["failed"]) == (5, 1), (
        f"AC-9: count/failed muessen summiert werden, kam {body!r}"
    )


@pytest.mark.parametrize("wirft", ["alert", "official"])
def test_one_part_raises_other_still_runs_and_counts_failed(client, services, wirft):
    """AC-9 Fehlerisolation: wirft einer der beiden Teile, wird der andere
    trotzdem ausgefuehrt, die Antwort ist 200 und der Fehler zaehlt als
    `failed` (mindestens +1 gegenueber dem Rest)."""
    calls, plan = services
    plan[wirft] = RuntimeError(f"{wirft} simuliert kaputt")
    anderer = "official" if wirft == "alert" else "alert"
    uid = f"tdd-2286-ac9-{uuid.uuid4().hex[:8]}"

    resp = _post(client, uid)

    assert resp.status_code == 200, (
        f"AC-9: ein werfender Teil darf den Endpoint nicht kippen, kam {resp.status_code}: {resp.text}"
    )
    assert (anderer, uid) in calls, (
        f"AC-9: der andere Teil ({anderer}) muss trotzdem laufen, kam {calls!r}"
    )
    body = resp.json()
    rest_count, rest_failed = plan[anderer]
    assert body["count"] == rest_count, body
    assert body["failed"] >= rest_failed + 1, (
        f"AC-9: der Fehler von {wirft} muss als failed zaehlen, kam {body!r}"
    )


def test_official_endpoint_is_gone():
    """AC-9: der eigene Endpoint `compare-official-alert-checks` existiert
    nicht mehr (Laufzeit-Routentabelle der echten App, kein Quelltext-Check)."""
    from api.main import app

    pfade = {getattr(r, "path", "") for r in app.routes}
    assert "/api/scheduler/compare-alert-checks" in pfade
    assert "/api/scheduler/compare-official-alert-checks" not in pfade, (
        "AC-9: der Official-Endpoint muss entfallen (geht in compare-alert-checks auf)"
    )
