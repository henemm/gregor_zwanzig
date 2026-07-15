"""conftest.py fuer tests/integration/.

Issue #1250 Scheibe 7a (Cutover): Trip-Persistenz liest/schreibt seitdem
``data/users/<uid>/briefings/`` statt ``data/users/<uid>/trips/`` (ADR-0023).
Die COMMITTETEN Test-Fixtures liegen weiterhin unter
``data/users/<uid>/trips/*.json`` (getrackt); ``briefings/`` ist jetzt
gitignored (host-seitig service-verwaltet, nicht committbar). Auf einem
frischen Checkout fehlt ``briefings/`` deshalb komplett, und Integrationstests,
die committete Fixtures ueber ``load_trip``/``get_briefings_dir`` lesen,
scheitern.

Diese Fixture spiegelt jede committete ``trips/*.json`` additiv nach
``briefings/<stem>.json`` (nur ``kind`` wird ergaenzt, falls es fehlt) -- kein
Netz, kein Mock, keine Aenderung an ``trips/``, kein Ueberschreiben bereits
vorhandener ``briefings/``-Dateien (idempotent).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Gleicher Repo-Root-Bezug wie die bestehenden Integrationstests (die z.B. mit
# ``Path("data/users") / user_id / ...`` relativ zum Prozess-cwd arbeiten,
# welches bei ``uv run pytest`` immer der Repo-Root ist) -- hier zusaetzlich
# ueber ``__file__`` verankert, damit die Spiegelung auch unabhaengig vom
# jeweiligen Aufruf-cwd zuverlaessig denselben Baum trifft.
_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session", autouse=True)
def _mirror_committed_trip_fixtures_to_briefings() -> None:
    """Stellt fuer jede committete ``trips/*.json`` eine ``briefings/``-
    Spiegel-Datei sicher (Issue #1250 Scheibe 7a)."""
    for trips_json in sorted(_REPO_ROOT.glob("data/users/*/trips/*.json")):
        briefings_dir = trips_json.parent.parent / "briefings"
        target = briefings_dir / trips_json.name
        if target.exists():
            continue
        trip = json.loads(trips_json.read_text(encoding="utf-8"))
        trip.setdefault("kind", "route")
        briefings_dir.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(trip, indent=2, ensure_ascii=False), encoding="utf-8"
        )
