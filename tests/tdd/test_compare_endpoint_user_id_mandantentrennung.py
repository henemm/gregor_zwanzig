"""TDD RED — Issue #1891: `GET /api/compare` missachtet die Mandantentrennung.

Spec: docs/specs/modules/compare_endpoint_user_id.md

`run_comparison()` (api/routers/compare.py) ruft `load_all_locations()` OHNE
`user_id`-Argument auf. Da FastAPI nicht deklarierte Query-Parameter still
verwirft, hat ein mitgeschicktes `&user_id=...` heute KEINE Wirkung: jeder
eingeloggte Nutzer bekommt die Orte des Pseudo-Nutzers `"default"` statt seiner
eigenen (Cross-User-Datenleck).

RED-Ursachen (heute):
- AC-1: der Loader-Stub wertet `user_id` echt aus; weil der Router den Parameter
  nicht durchreicht, kommt `user_id=None` an -> beide Nutzer bekommen dieselbe
  (leere) Ortsliste, also `{"error": "no_locations_found"}` statt der jeweils
  eigenen Orte. Der Stub ist korrekt -- der Router reicht nicht durch.
- AC-2: ein Aufruf ohne `user_id` liefert heute HTTP 200 statt HTTP 422, weil
  `user_id` in der Signatur von `run_comparison()` gar nicht existiert.

Kein Mock-Theater: `monkeypatch.setattr` ersetzt die Datenquellen durch echte,
lokal konstruierte DTOs. Der Loader-Stub verhaelt sich wie die echte
Persistenz (unterschiedliche Ortsliste je Nutzer), der Engine-Stub leitet sein
Ergebnis aus den TATSAECHLICH uebergebenen Orten ab -- er kann die Trennung
also nicht faelschlich bestaetigen.

Kern-Schicht: bewusst OHNE `live`/`real_data_root`-Marker, damit die
Daten-Isolation aus tests/conftest.py greift (kein Zugriff auf `data/users/`).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

TARGET_DATE = "2026-08-20"


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from api.main import app
    return TestClient(app)


@pytest.fixture
def zwei_nutzer_orte(monkeypatch):
    """Zwei Nutzer mit je eigenen Orten -- der Loader-Stub wertet `user_id` aus.

    Der Engine-Stub baut sein Ergebnis aus den ihm uebergebenen Orten; er kann
    die Mandantentrennung damit nicht selbst herbeifuehren.
    """
    import app.loader as loader_mod
    from app.user import ComparisonResult, LocationResult, SavedLocation
    from services.comparison_engine import ComparisonEngine

    orte = {
        "alice": [SavedLocation(id="alice-huette", name="Alice-Huette",
                                lat=46.6, lon=12.9, elevation_m=1900,
                                timezone="Europe/Vienna")],
        "bob": [SavedLocation(id="bob-pass", name="Bob-Pass",
                              lat=42.3, lon=9.0, elevation_m=1500,
                              timezone="Europe/Paris")],
    }

    monkeypatch.setattr(
        loader_mod, "load_all_locations",
        lambda user_id=None, **kw: orte.get(user_id, []),
    )

    def _engine_run(locations, time_window, target_date, **kwargs):
        return ComparisonResult(
            locations=[LocationResult(location=loc, score=1) for loc in locations],
            time_window=time_window,
            target_date=target_date,
        )

    monkeypatch.setattr(ComparisonEngine, "run", staticmethod(_engine_run))
    return orte


# =============================================================================
# AC-1 — jeder Nutzer sieht ausschliesslich seine eigenen Orte
# =============================================================================

def test_ac1_compare_liefert_je_nutzer_nur_dessen_eigene_orte(client, zwei_nutzer_orte):
    antworten = {}
    for nutzer in ("alice", "bob"):
        resp = client.get(
            f"/api/compare?location_ids=*&user_id={nutzer}&target_date={TARGET_DATE}"
        )
        assert resp.status_code == 200, (
            f"Compare-Aufruf fuer {nutzer!r} scheiterte: "
            f"{resp.status_code} {resp.text}"
        )
        antworten[nutzer] = [o["id"] for o in (resp.json().get("locations") or [])]

    assert antworten["alice"] == ["alice-huette"], (
        "GET /api/compare?user_id=alice liefert nicht genau die Orte von alice, "
        f"sondern {antworten['alice']!r} -- der Router reicht `user_id` nicht an "
        "load_all_locations() durch (Issue #1891)"
    )
    assert antworten["bob"] == ["bob-pass"], (
        "GET /api/compare?user_id=bob liefert nicht genau die Orte von bob, "
        f"sondern {antworten['bob']!r} -- der Router reicht `user_id` nicht an "
        "load_all_locations() durch (Issue #1891)"
    )
    assert "bob-pass" not in antworten["alice"], (
        "Cross-User-Datenleck: alice sieht den Ort von bob"
    )
    assert "alice-huette" not in antworten["bob"], (
        "Cross-User-Datenleck: bob sieht den Ort von alice"
    )


# =============================================================================
# AC-2 — ohne `user_id` gibt es keine Antwort, sondern HTTP 422
# =============================================================================

def test_ac2_compare_ohne_user_id_antwortet_mit_422(client, zwei_nutzer_orte):
    resp = client.get(f"/api/compare?location_ids=alice-huette&target_date={TARGET_DATE}")

    assert resp.status_code == 422, (
        "GET /api/compare ohne `user_id` muss HTTP 422 liefern (Pflichtparameter, "
        f"kein stiller Fallback auf 'default'), bekam aber {resp.status_code}: "
        f"{resp.text[:300]}"
    )
