"""AC-3 (#1765/#1839 Scheibe A): Die Fehlerformen der Vorschau-Endpunkte bleiben
unveraendert.

Spec: docs/specs/modules/fix_1765_1839_sa_vorschau_entblockung.md

🔴 **Diese Datei ist ABSICHTLICH schon in der RED-Phase gruen** — sie ist kein
fehlgeschlagener RED-Test und darf spaeter nicht dafuer gehalten werden. Ae1
stellt 13 Handler von ``async def`` auf ``def`` um; das aendert nur die
Ausfuehrungsebene (Threadpool statt Event-Loop), nicht die Logik. Diese Tests
zementieren das Bestandsverhalten VOR der Umstellung, damit ein stiller
Verhaltensbruch bei der Umstellung auffliegt.

**Was die Bestandssuite schon abdeckt** (geprueft in
``tests/tdd/test_epic_140_preview_endpoints.py`` und
``tests/tdd/test_issue_363_signal_telegram_preview.py``):

- **404** unbekannter Trip: abgedeckt fuer ``email``, ``sms``, ``telegram``.
- **422** ungueltiger ``type``: abgedeckt fuer ``email`` (als ``400|422``),
  ``telegram`` und ``signal``.
- **503**: NICHT abgedeckt. Der Statuscode kommt dort ausschliesslich als
  *geduldete* Alternative vor (``assert status_code in (200, 503)``, teils mit
  ``pytest.skip``) — kein einziger Test erzwingt ihn oder prueft die
  Zuordnung ``RuntimeError`` → 503.
- **``POST /api/preview/compare/{preset_id}``**: gar keine Fehlerform-Tests
  (kein Testtreffer auf den Pfad im gesamten Testbaum).

Ergaenzt werden deshalb genau diese Luecken: 503 fuer die drei Trip-Kanaele und
404/422/503 fuer den Vergleichs-Endpunkt.

Der 503-Fall braucht eine gesteuerte Stoerung — ein echter Wetterdienst-Ausfall
laesst sich offline nicht deterministisch herstellen. Der Ersatz wirft die
Ausnahme, die der echte Dienst wirft; geprueft wird die Zuordnung im Router
(``except RuntimeError`` → HTTP 503), also echter Produktivcode.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class _StoerenderDienst:
    """Steht fuer "Wetterdaten nicht verfuegbar" — die Ausnahme, die
    ``PreviewService``/``ComparePreviewService`` in dem Fall werfen."""

    MELDUNG = "Wetterdaten nicht verfuegbar (Testfall)"

    def _stoeren(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError(self.MELDUNG)

    render_email_preview = _stoeren
    render_sms_preview = _stoeren
    render_telegram_preview = _stoeren
    render_all_channels = _stoeren


@pytest.fixture
def client():
    from api.routers import preview

    app = FastAPI()
    app.include_router(preview.router)
    return TestClient(app)


@pytest.fixture
def gestoerter_trip_dienst(monkeypatch):
    from api.routers import preview

    monkeypatch.setattr(preview, "_build_service", lambda *a, **kw: _StoerenderDienst())


@pytest.mark.parametrize(
    "pfad",
    ["/api/preview/gr221-mallorca/email",
     "/api/preview/gr221-mallorca/sms",
     "/api/preview/gr221-mallorca/telegram"],
)
def test_trip_vorschau_meldet_wetterausfall_als_503(client, gestoerter_trip_dienst, pfad):
    """RuntimeError des Vorschau-Dienstes → HTTP 503 mit Klartext-Detail.

    Bestandsluecke: die Suite duldet 503 heute nur, erzwingt ihn nirgends.
    """
    antwort = client.get(pfad, params={"user_id": "default", "type": "morning"})

    assert antwort.status_code == 503, (
        f"Erwarte 503 bei nicht verfuegbaren Wetterdaten, bekam "
        f"{antwort.status_code}: {antwort.text[:200]}"
    )
    assert _StoerenderDienst.MELDUNG in antwort.text, (
        "Die Fehlermeldung des Dienstes muss im 503-Detail durchgereicht werden "
        f"(bekam: {antwort.text[:200]})"
    )


def test_vergleichs_vorschau_unbekanntes_preset_ist_404(client):
    """Unbekanntes Preset → 404. Echter Dienst, kein Ersatz, kein Netz:
    ``_load_preset`` wirft ``LookupError``, bevor irgendein Abruf startet."""
    antwort = client.post(
        "/api/preview/compare/gibt-es-nicht-4711", params={"user_id": "default"},
    )

    assert antwort.status_code == 404, (
        f"Erwarte 404 fuer unbekanntes Preset, bekam {antwort.status_code}: "
        f"{antwort.text[:200]}"
    )
    # Abgrenzung: der 404 muss aus dem HANDLER kommen (LookupError → 404), nicht
    # von Starlettes Router ("Not Found") — sonst wuerde der Test auch bei einer
    # geloeschten Route noch gruen sein.
    assert antwort.json().get("detail") != "Not Found", (
        "Der 404 stammt vom Router, nicht vom Handler — die Route "
        "POST /api/preview/compare/{preset_id} existiert nicht (mehr)."
    )


def test_vergleichs_vorschau_ohne_user_id_ist_422(client):
    """Fehlender Pflicht-Parameter ``user_id`` → 422 (FastAPI-Validierung).

    Mandantentrennung: ohne Session-Kennung darf der Endpunkt gar nicht erst
    rechnen, statt still auf ``"default"`` zu fallen (ADR-0003)."""
    antwort = client.post("/api/preview/compare/irgendein-preset")

    assert antwort.status_code == 422, (
        f"Erwarte 422 ohne user_id, bekam {antwort.status_code}: "
        f"{antwort.text[:200]}"
    )


def test_vergleichs_vorschau_meldet_wetterausfall_als_503(client, monkeypatch):
    """RuntimeError im Vergleichs-Pfad → HTTP 503."""
    from api.routers import preview

    monkeypatch.setattr(
        preview, "ComparePreviewService", lambda *a, **kw: _StoerenderDienst(),
    )
    antwort = client.post(
        "/api/preview/compare/irgendein-preset", params={"user_id": "default"},
    )

    assert antwort.status_code == 503, (
        f"Erwarte 503 bei nicht verfuegbaren Wetterdaten, bekam "
        f"{antwort.status_code}: {antwort.text[:200]}"
    )
    assert _StoerenderDienst.MELDUNG in antwort.text


def test_trip_vorschau_ohne_user_id_ist_422(client):
    """Gegenstueck zum Vergleich: auch der Trip-Pfad verlangt ``user_id``."""
    antwort = client.get("/api/preview/gr221-mallorca/email")

    assert antwort.status_code == 422, (
        f"Erwarte 422 ohne user_id, bekam {antwort.status_code}: "
        f"{antwort.text[:200]}"
    )
