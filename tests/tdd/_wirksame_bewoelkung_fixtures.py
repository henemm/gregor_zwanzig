"""Gemeinsamer Aufbau fuer die Tests zur wirksamen Bewoelkung (Issue #3106).

Kein Test-Modul (fuehrender Unterstrich). Liefert einen ECHTEN
``OpenMeteoProvider``, dessen ``httpx``-Client aus einem ``httpx.MockTransport``
im aufgezeichneten Open-Meteo-Antwortformat bedient wird (Muster
``tests/tdd/test_openmeteo_explizite_einheiten.py``) -- die Zeitreihe laeuft
damit durch den produktiven Abruf- und Normalisierungsweg, ohne Netz.
"""
from __future__ import annotations

import json
from datetime import date

import httpx
import tenacity

from providers.openmeteo import OpenMeteoProvider

_MODELLE = ["meteofrance_arome", "icon_d2", "metno_nordic", "icon_eu", "ecmwf_ifs04"]

#: Schleierwolken (nur hoch) -> wirksam 50 im Tal.
SCHLEIER = {"cloud_cover": 100, "cloud_cover_low": 0, "cloud_cover_mid": 0, "cloud_cover_high": 100}
#: AC-3: tief 20, mittel 0, hoch 80, gesamt 84 -> wirksam 52 im Tal.
GEMISCHT = {"cloud_cover": 84, "cloud_cover_low": 20, "cloud_cover_mid": 0, "cloud_cover_high": 80}
#: Nur tiefe Wolken -> wirksam 0 ab 2500 m, 100 im Tal.
NUR_TIEF = {"cloud_cover": 100, "cloud_cover_low": 100, "cloud_cover_mid": 0, "cloud_cover_high": 0}


def open_meteo_antwort(stunden: list[str], wolken: list[dict], **konstant) -> dict:
    """Open-Meteo-Antwort (``hourly``) aus Stundenliste und Wolken je Stunde;
    ``konstant`` legt weitere Stundenreihen mit festem Wert an."""
    hourly: dict = {"time": list(stunden)}
    for schluessel in ("cloud_cover", "cloud_cover_low", "cloud_cover_mid", "cloud_cover_high"):
        hourly[schluessel] = [w[schluessel] for w in wolken]
    for schluessel, wert in konstant.items():
        hourly[schluessel] = [wert] * len(stunden)
    return {"elevation": 0.0, "hourly": hourly}


def provider_mit_antwort(monkeypatch, tmp_path, antwort: dict,
                         status_je_pfad: dict | None = None) -> OpenMeteoProvider:
    """Echter ``OpenMeteoProvider``; jeder Forecast-Request bekommt ``antwort``,
    Pfade aus ``status_je_pfad`` antworten mit dem dort genannten Fehlerstatus."""
    cache = tmp_path / "model_availability.json"
    cache.write_text(json.dumps({
        "probe_date": date.today().isoformat(),
        "models": {m: {"available": [], "unavailable": []} for m in _MODELLE},
    }))
    monkeypatch.setattr("providers.openmeteo.AVAILABILITY_CACHE_PATH", cache)
    monkeypatch.setattr("providers.openmeteo.DIAGNOSTICS_PATH", tmp_path / "calls.jsonl")
    monkeypatch.setattr(OpenMeteoProvider._request.retry, "wait", tenacity.wait_none())
    monkeypatch.setattr(OpenMeteoProvider._request.retry, "stop", tenacity.stop_after_attempt(1))
    status = dict(status_je_pfad or {})

    def _antworten(request: httpx.Request) -> httpx.Response:
        code = status.get(request.url.path, 200)
        if code != 200:
            return httpx.Response(code, json={"error": True, "reason": "Testnaht"})
        return httpx.Response(200, json=antwort)

    provider = OpenMeteoProvider()
    provider._client = httpx.Client(transport=httpx.MockTransport(_antworten))
    return provider
