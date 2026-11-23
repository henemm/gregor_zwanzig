"""Issue #448 -- Validator-Endpoint metrics-for-channel (Stand #3237).

Spec: docs/specs/_archive/modules/issue_448_validator_metrics_for_channel.md
(Nachtrag #3237), docs/specs/modules/feat_3237_altpfad_entfernen.md AC-7.

Endpoint: GET /api/_validator/metrics-for-channel
Parameters: trip=<id>, channel=<ch>, report=<morning|evening>, user_id=<id>
Response:   {"source": "placements|grundauswahl", "metric_ids": [...]}

Seit #3237 ist die Tabelle "Was steht wo" die einzige Quelle; die
Kanal-Kaskade (per_report > per_channel > global) ist entfernt. Der
fruehere AC-3 (per_report schlaegt per_channel) beschrieb nur die Kaskade
und ist entfallen.
- AC-1: ohne Tabelle -> source="grundauswahl"
- AC-2: Tabelle mit E-Mail-Teilauswahl -> source="placements", genau diese Metriken
- AC-4: Telegram-Einstellung beeinflusst die Stelle E-Mail nicht
- AC-5: leere Stelle -> metric_ids=[] (kein Rueckfall)
- AC-6: Unbekannter Trip -> 404

Keine Mocks -- echte Trip-Dateien in data/users/.

Issue #1308: api/routers/validator.py importiert bare (`from app.loader
import ...`), damit greift die #1133-Isolation auch hier. Die Fixtures
(`_write_trip`) schreiben bewusst in den echten data/-Baum und raeumen ihn
danach ab (s. test_issue_221-Modul-Docstring) -- deshalb modulweit
`real_data_root` markiert.
"""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytestmark = pytest.mark.real_data_root


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """FastAPI TestClient für den validator-Router."""
    from api.routers import validator
    app = FastAPI()
    app.include_router(validator.router)
    return TestClient(app)


def _write_trip(user_id: str, trip_id: str, payload: dict) -> None:
    # Issue #1250 Scheibe 7a (Adversary F001): validator.py liest seit dem
    # Cutover briefings/, nicht mehr trips/ (s. test_issue_221 Modul-
    # Docstring fuer die src.app.loader-Isolations-Ausnahme).
    trip_dir = Path("data/users") / user_id / "briefings"
    trip_dir.mkdir(parents=True, exist_ok=True)
    (trip_dir / f"{trip_id}.json").write_text(json.dumps(payload))


# Ohne temperature: deren abgeleitete Tagesgroessen (Nacht, Tagesspanne) sind
# an der Stelle E-Mail gesperrt ("keine eigene Spalte") und gehoeren trotzdem
# zur Ausgabe -- das wuerde die Teilauswahl-Aussagen verwischen.
_METRIKEN = [
    {"metric_id": "sunshine", "enabled": True},
    {"metric_id": "wind", "enabled": True},
    {"metric_id": "precipitation", "enabled": True},
    {"metric_id": "humidity", "enabled": True},
]


def _trip_mit(placements_listen: dict | None) -> tuple[str, str]:
    """Trip mit Grundauswahl ``_METRIKEN``; ``placements_listen`` = Haken je
    Stelle als Tabelle (#3237: die Tabelle ist die einzige Quelle),
    ``None`` = Abo ohne Tabelle."""
    from tests.helpers.tabelle_aus_wunsch import tabelle

    user_id = f"test_issue_448_{uuid.uuid4().hex[:8]}"
    trip_id = "trip-448"
    dc = {"trip_id": trip_id, "metrics": [dict(m) for m in _METRIKEN]}
    if placements_listen is not None:
        dc["placements"] = tabelle(dc, "trip", listen=placements_listen)
    _write_trip(user_id, trip_id, {
        "id": trip_id, "name": "Trip 448", "stages": [], "display_config": dc,
    })
    return user_id, trip_id


@pytest.fixture
def trip_ohne_tabelle():
    """AC-1: Trip ohne Tabelle (nur Grundauswahl)."""
    user_id, trip_id = _trip_mit(None)
    yield user_id, trip_id
    shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)


@pytest.fixture
def trip_email_teilauswahl():
    """AC-2: Tabelle, an der Stelle E-Mail nur precipitation und humidity."""
    user_id, trip_id = _trip_mit({"email": ["precipitation", "humidity"]})
    yield user_id, trip_id
    shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)


@pytest.fixture
def trip_nur_telegram_eingestellt():
    """AC-4: Tabelle, nur an der Stelle Telegram eingeschraenkt (wind);
    E-Mail bleibt bei der Grundauswahl."""
    user_id, trip_id = _trip_mit({"telegram": ["wind"]})
    yield user_id, trip_id
    shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)


@pytest.fixture
def trip_email_leer():
    """AC-5: Tabelle, an der Stelle E-Mail alles abgewaehlt (expliziter Wunsch)."""
    user_id, trip_id = _trip_mit({"email": []})
    yield user_id, trip_id
    shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)


# ---------------------------------------------------------------------------
# Endpoint Tests: GET /api/_validator/metrics-for-channel
# ---------------------------------------------------------------------------

class TestMetricsForChannelEndpoint:
    """AC-1 bis AC-6: Metriken je Kanal laut Tabelle (#3237: Vertrag
    ``{source: placements|grundauswahl, metric_ids}``)."""

    @staticmethod
    def _abfrage(client, user_id, trip_id, channel="email", report="morning"):
        resp = client.get(
            "/api/_validator/metrics-for-channel",
            params={"trip": trip_id, "channel": channel, "report": report, "user_id": user_id},
        )
        assert resp.status_code == 200, f"Erwartet 200, got {resp.status_code}: {resp.text[:300]}"
        return resp.json()

    def test_ac1_ohne_tabelle_quelle_grundauswahl(self, client, trip_ohne_tabelle):
        """AC-1: Trip ohne Tabelle -> source='grundauswahl', Grundauswahl erscheint."""
        data = self._abfrage(client, *trip_ohne_tabelle)
        assert data["source"] == "grundauswahl", f"got: {data['source']!r}"
        assert isinstance(data["metric_ids"], list), "metric_ids muss eine Liste sein"
        for mid in ("sunshine", "wind", "precipitation", "humidity"):
            assert mid in data["metric_ids"], f"Grundauswahl-Metrik {mid} fehlt: {data['metric_ids']}"

    def test_ac2_tabelle_email_teilauswahl(self, client, trip_email_teilauswahl):
        """AC-2: Tabelle mit E-Mail-Teilauswahl -> source='placements', nur diese Metriken."""
        data = self._abfrage(client, *trip_email_teilauswahl)
        assert data["source"] == "placements", f"got: {data['source']!r}"
        assert data["metric_ids"] == ["precipitation", "humidity"], data["metric_ids"]
        assert "sunshine" not in data["metric_ids"], (
            "an der Stelle E-Mail abgewaehlter sunshine darf nicht erscheinen"
        )

    def test_ac4_telegram_einstellung_beeinflusst_email_nicht(
        self, client, trip_nur_telegram_eingestellt
    ):
        """AC-4: nur Telegram eingeschraenkt -> E-Mail zeigt weiter die Grundauswahl,
        Telegram nur seine Auswahl."""
        user_id, trip_id = trip_nur_telegram_eingestellt
        email = self._abfrage(client, user_id, trip_id, channel="email")
        assert email["source"] == "placements", f"got: {email['source']!r}"
        for mid in ("sunshine", "wind", "precipitation", "humidity"):
            assert mid in email["metric_ids"], f"E-Mail verliert {mid}: {email['metric_ids']}"
        telegram = self._abfrage(client, user_id, trip_id, channel="telegram")
        assert telegram["metric_ids"] == ["wind"], telegram["metric_ids"]

    def test_ac5_leere_stelle_kein_rueckfall(self, client, trip_email_leer):
        """AC-5: Stelle E-Mail ganz abgewaehlt -> metric_ids=[], kein Rueckfall."""
        data = self._abfrage(client, *trip_email_leer)
        assert data["source"] == "placements", f"got: {data['source']!r}"
        assert data["metric_ids"] == [], (
            f"Leere Stelle darf nicht auf die Grundauswahl fallen; got: {data['metric_ids']}"
        )

    def test_ac6_unknown_trip_returns_404(self, client):
        """AC-6: Nicht-existierende Trip-ID → HTTP 404."""
        resp = client.get(
            "/api/_validator/metrics-for-channel",
            params={
                "trip": "nonexistent-trip-id-448",
                "channel": "email",
                "report": "morning",
                "user_id": "default",
            },
        )
        assert resp.status_code == 404, (
            f"Unbekannter Trip muss 404 liefern, got {resp.status_code}: {resp.text[:200]}"
        )
