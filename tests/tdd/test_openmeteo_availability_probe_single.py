"""AC-10 (Epic #1539, S1a): die Auto-Probe der Modellverfuegbarkeit laeuft genau einmal.

Given ein abgelaufener Verfuegbarkeits-Cache und N=12 gleichzeitige
      `fetch_forecast()`-Abrufe (Barrier)
When  alle gleichzeitig die Modellverfuegbarkeit brauchen
Then  laeuft die Auto-Probe genau einmal (Double-Checked-Locking unter
      `exclusive_lock`), und alle Abrufe sehen danach den gueltigen Cache.

Naht (Begruendung): `--disable-socket` sperrt auch Loopback, ein lokaler
HTTP-Server (wie in aelteren, `live`-markierten Tests) scheidet im Kern aus.
Zulaessiger Grenz-Ersatz ist deshalb `OpenMeteoProvider._request` -- die
einzige HTTP-Grenze des Providers. Der Ersatz zaehlt Probe-Aufrufe (am
`hourly`-Parameter = komplette PROBE_PARAMS erkennbar), liefert fuer jeden
Aufruf eine echt aussehende Open-Meteo-Antwort (Stundenwerte fuer genau die
angefragten Parameter) und verzoegert die Probe kuenstlich, damit das
Race-Fenster deterministisch breit ist. Alles andere (Cache-Datei, Sperre,
Parser, Aggregation) ist echter Produktivcode auf tmp-Pfaden.

RED heute: jeder der 12 Threads sieht den abgelaufenen Cache und probt selbst.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import providers.openmeteo as om  # noqa: E402
from app.config import Location  # noqa: E402

N_THREADS = 12
_PROBE_HOURLY = ",".join(om.PROBE_PARAMS)


def _antwort(params: dict) -> dict:
    basis = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    zeiten = [(basis + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(6)]
    hourly: dict = {"time": zeiten}
    for name in str(params.get("hourly", "temperature_2m")).split(","):
        hourly[name] = [1.0 + i for i in range(len(zeiten))]
    return {"latitude": 48.0, "longitude": 8.0, "generationtime_ms": 0.1,
            "utc_offset_seconds": 0, "timezone": "GMT", "hourly": hourly}


@pytest.mark.timeout(60)
def test_auto_probe_laeuft_bei_gleichzeitigen_abrufen_genau_einmal(monkeypatch, tmp_path):
    """AC-10: 12 gleichzeitige Abrufe mit abgelaufenem Cache -> Probe genau 1x,
    Cache danach gueltig und fuer alle lesbar."""
    cache = tmp_path / "model_availability.json"
    cache.write_text(json.dumps({
        "probe_date": (date.today() - timedelta(days=30)).isoformat(),
        "models": {},
    }))
    monkeypatch.setattr(om, "AVAILABILITY_CACHE_PATH", cache)
    monkeypatch.setattr(om, "DIAGNOSTICS_PATH", tmp_path / "openmeteo_calls.jsonl")

    zaehler_lock = threading.Lock()
    probe_je_endpoint: dict[str, int] = {}

    def zaehlender_request(self, endpoint, params, *args, **kwargs):
        if params.get("hourly") == _PROBE_HOURLY:
            with zaehler_lock:
                probe_je_endpoint[endpoint] = probe_je_endpoint.get(endpoint, 0) + 1
            time.sleep(0.05)  # Race-Fenster breit machen (Netzlatenz der Probe)
        return _antwort(params)

    monkeypatch.setattr(om.OpenMeteoProvider, "_request", zaehlender_request)
    # Gewitter-Anreicherung fragt FREMDE Direkt-Provider (DWD ICON-EU) per Netz
    # ab -- fremde HTTP-Grenze, fuer die Probe-Aussage irrelevant, daher still.
    monkeypatch.setattr(om.OpenMeteoProvider, "_enrich_thunder",
                        lambda self, *a, **k: None)

    fehler: list = []
    monkeypatch.setattr(threading, "excepthook", lambda a: fehler.append(a.exc_value))
    barrier = threading.Barrier(N_THREADS)
    ort = Location(latitude=48.0, longitude=8.0, name="Schwarzwald")

    def arbeiter() -> None:
        provider = om.OpenMeteoProvider()
        barrier.wait(timeout=10)
        provider.fetch_forecast(ort, enrich_ensemble=False, enrich_snow=False)

    threads = [threading.Thread(target=arbeiter) for _ in range(N_THREADS)]
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout=50)

    assert not fehler, f"Thread-Ausnahmen: {fehler!r}"
    proben = probe_je_endpoint.get("/v1/ecmwf", 0)  # genau ein Modell nutzt diesen Endpoint
    assert proben == 1, (
        f"Auto-Probe lief {proben}x statt genau 1x (je Endpoint: {probe_je_endpoint})"
    )
    for _ in range(N_THREADS):
        gueltig = om.OpenMeteoProvider()._load_availability_cache()
        assert gueltig is not None and gueltig["probe_date"] == date.today().isoformat(), (
            "Cache nach den Abrufen nicht gueltig"
        )


@pytest.mark.timeout(30)
def test_wartender_abruf_wartet_laenger_als_die_standardfrist_auf_die_probe(monkeypatch, tmp_path):
    """Adversary F006: haelt ein anderer Thread die Probe-Sperre laenger als die
    Standardfrist (hier 0.3 s, Halter 0.8 s), wartet der Abruf trotzdem und sieht
    danach den gueltigen Cache -- er arbeitet nicht ohne Cache weiter."""
    import fcntl
    import os

    from services import file_lock

    cache = tmp_path / "model_availability.json"
    monkeypatch.setattr(om, "AVAILABILITY_CACHE_PATH", cache)
    monkeypatch.setattr(file_lock, "BRIEFING_LOCK_TIMEOUT_SECONDS", 0.3)
    gueltig = {"probe_date": date.today().isoformat(), "models": {}}
    gehalten = threading.Event()

    def halter() -> None:
        fd = os.open(str(cache) + ".lock", os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            gehalten.set()
            time.sleep(0.8)  # "laufende Probe", laenger als die Standardfrist
            cache.write_text(json.dumps(gueltig))
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    th = threading.Thread(target=halter, daemon=True)
    th.start()
    assert gehalten.wait(timeout=5)
    ergebnis = om.OpenMeteoProvider()._auto_probe_single()
    th.join(timeout=5)
    assert ergebnis is not None and ergebnis["probe_date"] == gueltig["probe_date"], (
        "Wartender gab nach der Standardfrist auf und lief ohne Cache weiter"
    )
