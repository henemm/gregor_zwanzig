---
entity_id: snapshot_plausibility_and_cache_isolation
type: bugfix
created: 2026-02-20
updated: 2026-02-20
status: draft
version: "1.0"
severity: HIGH
tags: [test-isolation, cache, fallback, visibility, plausibility, openmeteo, weather-05b]
---

# Bugfix BUG-VIS-01: Test-Isolation + Snapshot Plausibility

## Approval

- [x] Approved for implementation

## Symptom

Nach jedem `pytest`-Lauf zeigt der Weather-Report Visibility (und andere Fallback-Metriken) als "–".
Das Fallback-System (WEATHER-05b) greift nicht, weil `data/cache/model_availability.json` entweder
fehlt oder korrumpiert ist.

**Root Cause:** Tests in `test_metric_availability_probe.py`, `test_model_metric_fallback.py` und
`test_uv_air_quality.py` schreiben direkt auf den echten `AVAILABILITY_CACHE_PATH`. Ein Test
ruft sogar `.unlink()` darauf auf. Nach dem Testlauf ist der Cache weg oder enthält Fake-Daten
aus Testfixtures.

**Business Impact:**
- Visibility-Wert fehlt im Report (zeigt "–") obwohl AROME diesen Wert nicht liefert und
  der ICON-EU-Fallback eigentlich greifen sollte
- WEATHER-05b Fallback-Mechanismus ist nach jedem CI-/Entwickler-Run strukturell kaputt
- Fehler ist schwer zu reproduzieren (funktioniert solange kein `pytest` lief)

## Root Cause

### Problem 1: Tests schreiben auf echten Cache-Pfad

`AVAILABILITY_CACHE_PATH` ist ein Modul-Level-Konstant in `src/providers/openmeteo.py`.
Tests importieren ihn direkt und schreiben ohne Umleitung auf den echten Pfad:

```python
# test_metric_availability_probe.py — TestCacheLoad und TestCacheWrite
AVAILABILITY_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
AVAILABILITY_CACHE_PATH.write_text(json.dumps(cache_data))  # Echter Pfad!

# test_model_metric_fallback.py — test_finds_fallback_for_arome_coords
AVAILABILITY_CACHE_PATH.write_text(json.dumps(cache))  # Fake-Daten auf echtem Pfad!

# test_model_metric_fallback.py — test_returns_none_without_cache
if AVAILABILITY_CACHE_PATH.exists():
    AVAILABILITY_CACHE_PATH.unlink()  # LOESCHT den echten Cache!

# test_uv_air_quality.py — test_weather_05b_fallback_still_works_with_uv
AVAILABILITY_CACHE_PATH.write_text(json.dumps(cache))  # Fake-Daten auf echtem Pfad!
```

### Problem 2: Kein Self-Healing bei fehlendem Cache

In `src/providers/openmeteo.py` (Zeile 640) in `fetch_forecast()` wird bei `cache is None`
kein Auto-Probe ausgeloest. Das System faellt stumm auf "kein Fallback" zurueck, statt
den Cache neu aufzubauen.

### Problem 3: Kein Integrationstest der den Fallback E2E beweist

Es gibt keinen Test, der echte API-Daten holt und dann sicherstellt, dass Visibility
(und andere Fallback-Metriken) nicht `None` sind. Ohne diesen Test kann der Fallback
stillschweigend kaputt gehen ohne dass ein Test rot wird.

## Design

### Part A: Test-Isolation via monkeypatch (~30 LOC, 3 Dateien)

Jeder Test, der `AVAILABILITY_CACHE_PATH` beschreibt oder loescht, muss stattdessen
auf einen `tmp_path`-Pfad umgeleitet werden. Dafuer wird `monkeypatch.setattr` verwendet,
um das Modul-Attribut fuer die Dauer des Tests zu ueberschreiben.

**Pattern (gleichartig in allen drei Dateien):**

```python
def test_xyz(self, tmp_path, monkeypatch):
    import providers.openmeteo as om
    monkeypatch.setattr(om, "AVAILABILITY_CACHE_PATH", tmp_path / "model_availability.json")
    # ... Rest des Tests unveraendert
```

`monkeypatch` stellt das Original nach dem Test automatisch wieder her.

### Part B: Auto-Probe bei Cache-Miss (~8 LOC, 1 Datei)

In `fetch_forecast()` (openmeteo.py, Zeile 640) wird nach einem `None`-Return von
`_load_availability_cache()` ein automatischer Probe-Aufruf hinzugefuegt:

```python
cache = self._load_availability_cache()
if cache is None:
    try:
        logger.info("Availability cache missing/expired — auto-probing...")
        cache = self.probe_model_availability()
    except Exception as e:
        logger.warning("Auto-probe failed: %s", e)
if cache is not None:
    # bestehende Fallback-Logik (unveraendert)
```

**Kein Rekursions-Risiko:** `probe_model_availability()` ruft `_request()` direkt auf,
nicht `fetch_forecast()`.

### Part C: Snapshot-Plausibilitaetstest (~120 LOC, 1 neue Datei)

Neue Datei `tests/integration/test_snapshot_plausibility.py` prueft echte API-Daten
auf Plausibilitaet. Kein Mock — echter OpenMeteo-Call an Mallorca-Koordinaten
(39.77°N, 2.71°E), wo AROME priminaeres Modell ist und ICON-EU als Fallback greift.

## Affected Files

| Datei | Aenderung | LOC |
|-------|-----------|-----|
| `tests/unit/test_metric_availability_probe.py` | `TestCacheLoad` + `TestCacheWrite`: monkeypatch fuer AVAILABILITY_CACHE_PATH | ~8 |
| `tests/unit/test_model_metric_fallback.py` | `test_finds_fallback_for_arome_coords` + `test_returns_none_without_cache`: monkeypatch | ~10 |
| `tests/unit/test_uv_air_quality.py` | `test_weather_05b_fallback_still_works_with_uv`: monkeypatch | ~6 |
| `src/providers/openmeteo.py` | Auto-Probe in `fetch_forecast()` bei Cache-Miss | ~8 |
| `tests/integration/test_snapshot_plausibility.py` | NEU: Snapshot-Plausibilitaetstest | ~120 |
| **Gesamt** | | **~152 LOC** |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `providers.openmeteo.AVAILABILITY_CACHE_PATH` | const | Wird in Tests via monkeypatch umgeleitet |
| `OpenMeteoProvider.probe_model_availability()` | method | Wird bei Auto-Probe in fetch_forecast() aufgerufen |
| `OpenMeteoProvider._load_availability_cache()` | method | Rueckgabe None triggert Auto-Probe |
| `OpenMeteoProvider.fetch_forecast()` | method | Erhaelt Auto-Probe-Block (Part B) |
| `SegmentWeatherService` | class | Wird in Plausibilitaetstest fuer End-to-End-Call genutzt |
| `WeatherMetricsService` | class | Liefert aggregierte Werte fuer Plausibilitaets-Ranges |
| `ForecastDataPoint` | dto | Enthaelt visibility_m und alle anderen Metrik-Felder |
| `SegmentWeatherSummary` | dto | Aggregierte Werte fuer Range-Checks |
| `TripSegment` | dto | Input fuer Segment-Weather-Abfrage im Plausibilitaetstest |
| `docs/specs/modules/metric_availability_probe.md` | spec | WEATHER-05a: Cache-Schema und TTL-Logik |
| `docs/specs/modules/model_metric_fallback.md` | spec | WEATHER-05b: Fallback-Mechanismus der getestet wird |

## Implementation Details

### Part A: Test-Isolation (3 Dateien aendern)

#### tests/unit/test_metric_availability_probe.py

`TestCacheWrite.test_cache_file_written_after_probe` und alle `TestCacheLoad`-Methoden
erhalten `tmp_path` + `monkeypatch`-Parameter. Der `monkeypatch.setattr`-Aufruf kommt
als erste Zeile im Test-Body:

```python
class TestCacheWrite:
    def test_cache_file_written_after_probe(self, tmp_path, monkeypatch) -> None:
        import providers.openmeteo as om
        fake_cache = tmp_path / "model_availability.json"
        monkeypatch.setattr(om, "AVAILABILITY_CACHE_PATH", fake_cache)

        from providers.openmeteo import OpenMeteoProvider
        provider = OpenMeteoProvider()
        provider.probe_model_availability()

        assert fake_cache.exists(), "Cache file not written after probe"


class TestCacheLoad:
    def test_load_returns_dict_when_valid(self, tmp_path, monkeypatch) -> None:
        import providers.openmeteo as om
        fake_cache = tmp_path / "model_availability.json"
        monkeypatch.setattr(om, "AVAILABILITY_CACHE_PATH", fake_cache)

        cache_data = {
            "probe_date": date.today().isoformat(),
            "models": {"test_model": {"available": ["temperature_2m"], "unavailable": []}}
        }
        fake_cache.write_text(json.dumps(cache_data))

        from providers.openmeteo import OpenMeteoProvider
        provider = OpenMeteoProvider()
        result = provider._load_availability_cache()

        assert result is not None
        assert result["probe_date"] == date.today().isoformat()

    def test_load_returns_none_when_expired(self, tmp_path, monkeypatch) -> None:
        import providers.openmeteo as om
        fake_cache = tmp_path / "model_availability.json"
        monkeypatch.setattr(om, "AVAILABILITY_CACHE_PATH", fake_cache)

        old_date = (date.today() - timedelta(days=8)).isoformat()
        cache_data = {
            "probe_date": old_date,
            "models": {"test_model": {"available": ["temperature_2m"], "unavailable": []}}
        }
        fake_cache.write_text(json.dumps(cache_data))

        from providers.openmeteo import OpenMeteoProvider
        provider = OpenMeteoProvider()
        result = provider._load_availability_cache()

        assert result is None
```

#### tests/unit/test_model_metric_fallback.py

`TestFindFallbackModel.test_finds_fallback_for_arome_coords` und
`test_returns_none_without_cache` werden isoliert:

```python
class TestFindFallbackModel:
    def test_finds_fallback_for_arome_coords(self, tmp_path, monkeypatch) -> None:
        import providers.openmeteo as om
        fake_cache = tmp_path / "model_availability.json"
        monkeypatch.setattr(om, "AVAILABILITY_CACHE_PATH", fake_cache)

        cache = {
            "probe_date": date.today().isoformat(),
            "models": {
                "meteofrance_arome": {"available": ["temperature_2m"], "unavailable": ["cape", "visibility"]},
                "icon_eu": {"available": ["temperature_2m", "cape", "visibility"], "unavailable": []},
                "ecmwf_ifs04": {"available": ["temperature_2m", "cape"], "unavailable": ["visibility"]},
            }
        }
        fake_cache.parent.mkdir(parents=True, exist_ok=True)
        fake_cache.write_text(json.dumps(cache))

        from providers.openmeteo import OpenMeteoProvider
        provider = OpenMeteoProvider()
        result = provider._find_fallback_model("meteofrance_arome", 39.7, 2.6, ["cape", "visibility"])

        assert result is not None
        fb_model_id, fb_grid_res_km, fb_endpoint = result
        assert fb_model_id == "icon_eu"

    def test_returns_none_without_cache(self, tmp_path, monkeypatch) -> None:
        import providers.openmeteo as om
        # Zeige auf nicht-existierende Datei — kein .unlink() auf echtem Pfad!
        monkeypatch.setattr(om, "AVAILABILITY_CACHE_PATH", tmp_path / "model_availability.json")

        from providers.openmeteo import OpenMeteoProvider
        provider = OpenMeteoProvider()
        result = provider._find_fallback_model("meteofrance_arome", 39.7, 2.6, ["cape"])

        assert result is None
```

#### tests/unit/test_uv_air_quality.py

`test_weather_05b_fallback_still_works_with_uv` erhaelt monkeypatch:

```python
def test_weather_05b_fallback_still_works_with_uv(self, tmp_path, monkeypatch) -> None:
    import providers.openmeteo as om
    fake_cache = tmp_path / "model_availability.json"
    monkeypatch.setattr(om, "AVAILABILITY_CACHE_PATH", fake_cache)

    cache = {
        "probe_date": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
        "models": {
            "meteofrance_arome": {
                "available": ["temperature_2m"],
                "unavailable": ["visibility"],
            },
            "icon_eu": {
                "available": ["temperature_2m", "visibility"],
                "unavailable": [],
            },
        }
    }
    fake_cache.write_text(json.dumps(cache))
    # ... Rest des Tests unveraendert
```

### Part B: Auto-Probe bei Cache-Miss (openmeteo.py)

In `fetch_forecast()` ab Zeile 640, den `if cache is not None:` Block ersetzen durch:

```python
# WEATHER-05b: Check for missing metrics and fetch fallback
cache = self._load_availability_cache()
if cache is None:
    try:
        logger.info("Availability cache missing/expired — auto-probing...")
        cache = self.probe_model_availability()
    except Exception as e:
        logger.warning("Auto-probe failed: %s", e)
if cache is not None:
    primary_info = cache["models"].get(model_id)
    if primary_info:
        missing = primary_info.get("unavailable", [])
        if missing:
            # ... (bestehende Fallback-Logik unveraendert)
```

### Part C: Snapshot-Plausibilitaetstest (neue Datei)

**Datei:** `tests/integration/test_snapshot_plausibility.py`

```python
"""
Integration test: Real OpenMeteo snapshot for Mallorca — plausibility checks.

Regression target: visibility_min_m must NOT be None after WEATHER-05b fallback.
Uses real API calls (no mocks) per CLAUDE.md.
SPEC: docs/specs/bugfix/snapshot_plausibility_and_cache_isolation.md
"""
from __future__ import annotations

import sys
from datetime import date, datetime, time, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

MALLORCA_LAT = 39.77
MALLORCA_LON = 2.71


@pytest.fixture(scope="module")
def mallorca_summary():
    """Fetch real weather for Mallorca once per test module."""
    from app.config import Location
    from app.models import TripSegment, GPXPoint
    from services.segment_weather import SegmentWeatherService

    location = Location(latitude=MALLORCA_LAT, longitude=MALLORCA_LON, name="Mallorca Test")
    today = date.today()
    start = datetime.combine(today, time(8, 0), tzinfo=timezone.utc)
    end = datetime.combine(today, time(18, 0), tzinfo=timezone.utc)

    segment = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=MALLORCA_LAT, lon=MALLORCA_LON, elevation_m=100.0),
        end_point=GPXPoint(lat=MALLORCA_LAT, lon=MALLORCA_LON, elevation_m=100.0),
        start_time=start,
        end_time=end,
        duration_hours=10.0,
        distance_km=20.0,
        ascent_m=500.0,
        descent_m=500.0,
    )

    service = SegmentWeatherService()
    return service.get_segment_weather(segment)


class TestCoreMetricsNotNone:
    """Core metrics must always be present — no fallback needed."""

    def test_temp_min_not_none(self, mallorca_summary):
        assert mallorca_summary.aggregated.temp_min_c is not None

    def test_temp_max_not_none(self, mallorca_summary):
        assert mallorca_summary.aggregated.temp_max_c is not None

    def test_wind_max_not_none(self, mallorca_summary):
        assert mallorca_summary.aggregated.wind_max_kmh is not None

    def test_gust_max_not_none(self, mallorca_summary):
        assert mallorca_summary.aggregated.gust_max_kmh is not None

    def test_precip_sum_not_none(self, mallorca_summary):
        assert mallorca_summary.aggregated.precip_sum_mm is not None

    def test_cloud_avg_not_none(self, mallorca_summary):
        assert mallorca_summary.aggregated.cloud_avg_pct is not None

    def test_humidity_avg_not_none(self, mallorca_summary):
        assert mallorca_summary.aggregated.humidity_avg_pct is not None


class TestFallbackMetricsNotNone:
    """Fallback metrics (WEATHER-05b) must be filled via ICON-EU for AROME at Mallorca."""

    def test_visibility_min_not_none(self, mallorca_summary):
        """REGRESSION TARGET: visibility must not be None after fallback."""
        assert mallorca_summary.aggregated.visibility_min_m is not None, (
            "visibility_min_m is None — WEATHER-05b fallback broken or cache deleted by tests"
        )


class TestValueRanges:
    """All metric values must be within physically plausible ranges."""

    def test_temp_range(self, mallorca_summary):
        agg = mallorca_summary.aggregated
        assert -50 <= agg.temp_min_c <= 50
        assert -50 <= agg.temp_max_c <= 50

    def test_wind_range(self, mallorca_summary):
        agg = mallorca_summary.aggregated
        assert 0 <= agg.wind_max_kmh <= 300
        assert 0 <= agg.gust_max_kmh <= 300

    def test_precip_range(self, mallorca_summary):
        assert 0 <= mallorca_summary.aggregated.precip_sum_mm <= 500

    def test_cloud_humidity_range(self, mallorca_summary):
        agg = mallorca_summary.aggregated
        assert 0 <= agg.cloud_avg_pct <= 100
        assert 0 <= agg.humidity_avg_pct <= 100

    def test_visibility_range(self, mallorca_summary):
        vis = mallorca_summary.aggregated.visibility_min_m
        if vis is not None:
            assert 0 <= vis <= 100_000

    def test_pressure_range_if_present(self, mallorca_summary):
        p = mallorca_summary.aggregated.pressure_hpa
        if p is not None:
            assert 800 <= p <= 1100

    def test_uv_range_if_present(self, mallorca_summary):
        uv = mallorca_summary.aggregated.uv_index_max
        if uv is not None:
            assert 0 <= uv <= 15

    def test_cape_range_if_present(self, mallorca_summary):
        cape = mallorca_summary.aggregated.cape_max_jkg
        if cape is not None:
            assert 0 <= cape <= 5000


class TestCrossMetricConsistency:
    """Aggregated metrics must be mutually consistent."""

    def test_gust_gte_wind(self, mallorca_summary):
        agg = mallorca_summary.aggregated
        assert agg.gust_max_kmh >= agg.wind_max_kmh, (
            f"gust_max ({agg.gust_max_kmh}) must be >= wind_max ({agg.wind_max_kmh})"
        )

    def test_temp_max_gte_avg_gte_min(self, mallorca_summary):
        agg = mallorca_summary.aggregated
        if agg.temp_avg_c is not None:
            assert agg.temp_max_c >= agg.temp_avg_c >= agg.temp_min_c, (
                f"temp order violated: max={agg.temp_max_c} avg={agg.temp_avg_c} min={agg.temp_min_c}"
            )


class TestFallbackMechanismActive:
    """For AROME at Mallorca coordinates, fallback_model must be set."""

    def test_fallback_model_is_set(self, mallorca_summary):
        """AROME does not provide visibility — fallback must kick in."""
        meta = mallorca_summary.timeseries.meta
        assert meta.fallback_model is not None, (
            "fallback_model is None — WEATHER-05b did not activate for AROME/Mallorca"
        )
```

## Expected Behavior

### Szenario 1: Tests laufen — Cache bleibt unberuehrt

- **Vorher:** `pytest` loescht/korrumpiert `data/cache/model_availability.json`
- **Nachher:** Jeder Test nutzt `tmp_path` — echter Cache unveraendert nach Testlauf

### Szenario 2: Server startet ohne Cache (z.B. nach Git-Clone)

- **Vorher:** Visibility zeigt "–" bis manuell `--probe-models` ausgefuehrt wird
- **Nachher:** `fetch_forecast()` probt automatisch beim ersten Call, Cache wird aufgebaut

### Szenario 3: Plausibilitaetstest schlaegt rot

- **Signal:** `visibility_min_m is None` oder `fallback_model is None`
- **Bedeutung:** WEATHER-05b ist kaputt oder Cache wurde durch Test zerstoert
- **Aktion:** Root-Cause-Analyse: Ist ein neuer Test ohne monkeypatch hinzugekommen?

### Szenario 4: Wertebereichs-Verletzung

- **Signal:** `assert 0 <= gust_max_kmh <= 300` schlaegt fehl
- **Bedeutung:** API liefert implausible Daten oder Aggregation-Bug
- **Aktion:** Raw-Timeseries-Daten inspizieren

## Test Plan

| # | Test-Klasse / Methode | Typ | Assertion |
|---|----------------------|-----|-----------|
| A1 | `TestCacheWrite.test_cache_file_written_after_probe` | Unit | `fake_cache.exists()` (nicht echter Pfad) |
| A2 | `TestCacheLoad.test_load_returns_dict_when_valid` | Unit | `result is not None`, nur `tmp_path` beschrieben |
| A3 | `TestCacheLoad.test_load_returns_none_when_expired` | Unit | `result is None`, echter Cache unveraendert |
| A4 | `TestFindFallbackModel.test_finds_fallback_for_arome_coords` | Unit | `fb_model_id == "icon_eu"`, nur `tmp_path` beschrieben |
| A5 | `TestFindFallbackModel.test_returns_none_without_cache` | Unit | `result is None`, kein `.unlink()` auf echtem Pfad |
| A6 | `test_weather_05b_fallback_still_works_with_uv` | Unit | Fallback aktiv, nur `tmp_path` beschrieben |
| B1 | Manuell: `fetch_forecast()` ohne Cache | Integration | Auto-Probe wird gelogt, Cache entsteht |
| C1 | `TestCoreMetricsNotNone` (7 Tests) | Integration | Alle Core-Felder not None |
| C2 | `TestFallbackMetricsNotNone.test_visibility_min_not_none` | Integration | `visibility_min_m is not None` (Regression-Target) |
| C3 | `TestValueRanges` (8 Tests) | Integration | Alle Werte in physikalisch plausiblen Ranges |
| C4 | `TestCrossMetricConsistency` (2 Tests) | Integration | gust >= wind, temp_max >= avg >= min |
| C5 | `TestFallbackMechanismActive.test_fallback_model_is_set` | Integration | `meta.fallback_model is not None` |

## Known Limitations

- Part C Integrationstests machen echte API-Calls und brauchen Netzwerkzugang
- Mallorca-Koordinate prueft AROME-Coverage; Tests in anderen Regionen (ICON-D2, Nordic)
  sind nicht abgedeckt — moegliche Erweiterung in v2.0
- Auto-Probe (Part B) macht 5 API-Calls beim ersten `fetch_forecast()` nach Cache-Miss;
  das verlaengert die erste Anfrage nach Server-Start sichtbar (~3-5 Sekunden)
- `SegmentWeatherSummary`-Feldnamen im Plausibilitaetstest muessen mit tatsaechlichem
  Modell uebereinstimmen — bei DTO-Umbenennungen muss der Test angepasst werden

## Acceptance Criteria

- [ ] `pytest tests/unit/test_metric_availability_probe.py` beendet mit Exit 0, ohne `data/cache/model_availability.json` zu veraendern
- [ ] `pytest tests/unit/test_model_metric_fallback.py` beendet mit Exit 0, ohne `data/cache/model_availability.json` zu veraendern oder zu loeschen
- [ ] `pytest tests/unit/test_uv_air_quality.py` beendet mit Exit 0, ohne `data/cache/model_availability.json` zu veraendern
- [ ] `pytest tests/integration/test_snapshot_plausibility.py` beendet mit Exit 0
- [ ] `test_visibility_min_not_none` ist gruen (WEATHER-05b Regression geheilt)
- [ ] `test_fallback_model_is_set` ist gruen (Fallback-Mechanismus aktiv)
- [ ] `data/cache/model_availability.json` existiert und ist valid nach vollstaendigem Testlauf
- [ ] Bestehende Tests bleiben gruen (keine Regression)

## Changelog

- 2026-02-20: v1.0 Bugfix-Spec erstellt (BUG-VIS-01)
