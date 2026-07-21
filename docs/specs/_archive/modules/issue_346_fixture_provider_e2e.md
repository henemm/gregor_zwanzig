---
entity_id: issue_346_fixture_provider_e2e
type: module
created: 2026-05-23
updated: 2026-05-23
status: draft
version: "1.0"
issue: 346
tags: [python, provider, fixture, testing, openmeteo, pytest, offline]
---

# Issue #346 — Python Fixture-Provider erzwingt Offline-Tests

## Approval

- [x] Approved

## Purpose

Implementiert einen Python-seitigen `FixtureProvider`, der statische aufgezeichnete Wetterdaten aus lokalen JSON-Dateien liest und damit das `WeatherProvider`-Protocol aus `src/providers/base.py` erfüllt. Er wird aktiv, wenn die Umgebungsvariable `GZ_TEST_FIXTURE_DIR` gesetzt ist, und verhindert so, dass pytest-Läufe (in den Phasen 4-tdd-red, 5-implement, 6-validate) echte Open-Meteo-API-Calls auslösen, die das server-IP-weite Tageslimit erschöpfen und damit Produktivbriefings mit 429-Fehlern blockieren (Issue #338: 1.160 `vorschau`-Calls in einer Stunde, ausschließlich aus Test-Kontext).

## Source

- **NEU:** `src/providers/fixture.py` — `FixtureProvider`-Klasse (~100 LoC)
- **EDIT:** `src/providers/base.py` — `get_provider()` Fixture-Zweig bei gesetzter ENV-Var (~10 LoC)
- **EDIT:** `tests/conftest.py` — autouse-Fixture setzt `GZ_TEST_FIXTURE_DIR` für alle pytest-Läufe (~15 LoC)
- **EDIT:** `pyproject.toml` — Marker `live` registrieren (~3 LoC)

> **Schicht-Hinweis:** Alle Änderungen betreffen ausschließlich das Python-Backend (`src/providers/`) und die Test-Infrastruktur (`tests/`). Der Produktions-API-Pfad (`api/routers/preview.py`) und der Go-Server (`internal/`) bleiben unberührt. Die vorhandenen `fixtures/openmeteo/*.json`-Dateien (Go-Format, erstellt durch Issue #263) werden vom FixtureProvider direkt gelesen — kein eigenes Fixture-Format.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WeatherProvider` (`src/providers/base.py`) | intern | `@runtime_checkable` Protocol mit `name`-Property und `fetch_forecast(location, start, end, enrich_ensemble)` — FixtureProvider muss dieses Protocol strukturell erfüllen |
| `NormalizedTimeseries` (`src/app/models.py`) | intern | Rückgabetyp von `fetch_forecast`; enthält `meta: ForecastMeta` und `data: List[ForecastDataPoint]` |
| `ForecastDataPoint` (`src/app/models.py`) | intern | Einzelner Stundenpunkt; relevante Felder aus Go-Fixture: `ts`, `t2m_c`, `wind10m_kmh`, `gust_kmh`, `precip_1h_mm`, `cloud_total_pct`, `wmo_code`, `thunder_level`, `visibility_m`, `cape_jkg`, `is_day`, `dni_wm2`, `uv_index`, `snow_depth_cm` |
| `ForecastMeta` (`src/app/models.py`) | intern | Metadata-Struct für die Timeseries; `provider`, `model`, `grid_res_km` werden mit Fixture-Werten gesetzt |
| `Provider` enum (`src/app/models.py`) | intern | `Provider.OPENMETEO` als `provider`-Wert in `ForecastMeta` (kein eigener FIXTURE-Enum nötig — Fixture simuliert OpenMeteo) |
| `ThunderLevel` enum (`src/app/models.py`) | intern | **String**-Enum (`NONE`/`MED`/`HIGH`). Go-Fixture liefert `thunder_level` bereits als String (z.B. `"NONE"`) → direkt `ThunderLevel(v)`. KEIN Integer-Mapping. |
| `Location` (`src/app/config.py`) | intern | Argument von `fetch_forecast`; `location.latitude` und `location.longitude` für Nearest-Location-Lookup |
| `get_provider()` (`src/providers/base.py`) | intern | Zentraler Hebel: gibt bei gesetztem `GZ_TEST_FIXTURE_DIR` einen `FixtureProvider` zurück statt `OpenMeteoProvider` |
| `fixtures/openmeteo/innsbruck.json` | intern | 72-Punkte-Fixture (T=+2°C, Talwerte); bereits vorhanden durch Issue #263 |
| `fixtures/openmeteo/stubai.json` | intern | 72-Punkte-Fixture (T=-5°C, Hochlagen); bereits vorhanden durch Issue #263 |
| `fixtures/openmeteo/zillertal.json` | intern | 72-Punkte-Fixture (T=+1°C, Talwerte mit mehr Wind); bereits vorhanden durch Issue #263 |
| `tests/conftest.py` | intern | Globale pytest-Konfiguration (aktuell nur sys.path); erhält autouse-Fixture für `GZ_TEST_FIXTURE_DIR` |
| `pyproject.toml` | intern | pytest-Konfiguration; erhält Marker-Registrierung für `live` |

## Implementation Details

### §1 `src/providers/fixture.py` — FixtureProvider

**Fixture-Location-Registry** (hardcodiert, identisch zu Go #263):

```python
from dataclasses import dataclass

@dataclass
class _FixtureLocation:
    name: str
    lat: float
    lon: float
    filename: str

_FIXTURE_LOCATIONS = [
    _FixtureLocation("Innsbruck", 47.2692, 11.4041, "innsbruck.json"),
    _FixtureLocation("Stubai",    47.1015, 11.2958, "stubai.json"),
    _FixtureLocation("Zillertal", 47.2190, 11.8767, "zillertal.json"),
]
```

**Klasse und Initialisierung:**

```python
class FixtureProvider:
    def __init__(self, fixture_dir: str) -> None:
        self._dir = fixture_dir  # relativer oder absoluter Pfad

    @property
    def name(self) -> str:
        return "openmeteo"  # identisch zum echten Provider — transparent für Aufrufer
```

**`fetch_forecast`-Implementierung — 5 Schritte:**

1. **Nearest-Location-Suche:** Iteriert über `_FIXTURE_LOCATIONS`, berechnet für jeden Eintrag `(loc.lat - location.latitude)**2 + (loc.lon - location.longitude)**2` (keine Wurzel nötig). Wählt den Eintrag mit dem kleinsten Wert. Keine Ausnahme wenn keine Location passt — es gibt immer eine (3 Einträge).

2. **Datei lesen:** `Path(self._dir) / nearest.filename` öffnen und JSON laden. Wenn Datei fehlt: `ProviderError("fixture", f"Fixture file not found: {path}")` werfen.

3. **Go-JSON → Python-Mapping:** Go-Format: `{"timezone": "...", "meta": {...}, "data": [...]}`. Jeden Datenpunkt (`data[i]`) in einen `ForecastDataPoint` überführen:

   | Go-Feld | Python-Feld | Typ | Anmerkung |
   |---------|-------------|-----|-----------|
   | `ts` | `ts` | `datetime` (UTC) | ISO-8601-Parse, dann re-stampen |
   | `t2m_c` | `t2m_c` | `Optional[float]` | direkt |
   | `wind10m_kmh` | `wind10m_kmh` | `Optional[float]` | direkt |
   | `gust_kmh` | `gust_kmh` | `Optional[float]` | direkt |
   | `precip_1h_mm` | `precip_1h_mm` | `Optional[float]` | direkt |
   | `cloud_total_pct` | `cloud_total_pct` | `Optional[int]` | `int(v)` falls nicht None |
   | `wmo_code` | `wmo_code` | `Optional[int]` | `int(v)` falls nicht None |
   | `thunder_level` | `thunder_level` | `Optional[ThunderLevel]` | Go liefert String → `ThunderLevel(v)` (`"NONE"`/`"MED"`/`"HIGH"`); `None`-Wert bleibt `None` |
   | `visibility_m` | `visibility_m` | `Optional[int]` | `int(v)` falls nicht None |
   | `cape_jkg` | `cape_jkg` | `Optional[float]` | direkt |
   | `is_day` | `is_day` | `Optional[int]` | `int(v)` falls nicht None |
   | `dni_wm2` | `dni_wm2` | `Optional[float]` | direkt |
   | `uv_index` | `uv_index` | `Optional[float]` | direkt |
   | `snow_depth_cm` | `snow_depth_cm` | `Optional[float]` | direkt |

   Felder in `ForecastDataPoint` ohne Go-Fixture-Entsprechung (z.B. `wind_direction_deg`, `precip_rate_mmph`, `symbol`, `pop_pct`, `pressure_msl_hpa`, `humidity_pct`, `dewpoint_c`, `snow_new_24h_cm`, `freezing_level_m`, `confidence_pct` u.a.) bleiben `None` (Dataclass-Default).

4. **Timestamp Re-Stamping:** Nach dem Mapping alle `ts`-Felder ersetzen. Basiszeit = `datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)`. Punkt `i` erhält `base + timedelta(hours=i)`. Exakt so wie Go #263: unveränderliche Fixture-Daten, immer auf den aktuellen UTC-Tag verankert.

5. **ForecastMeta aufbauen und zurückgeben:**

   ```python
   meta = ForecastMeta(
       provider=Provider.OPENMETEO,
       model="fixture",
       grid_res_km=0.0,
   )
   return NormalizedTimeseries(meta=meta, data=data_points)
   ```

   `enrich_ensemble`-Parameter wird bewusst ignoriert: Der FixtureProvider macht keine Ensemble-Calls. Dies ist dokumentiertes Verhalten — im Docstring explizit festhalten: "enrich_ensemble wird ignoriert; kein HTTP-Call wird ausgelöst."

### §2 `src/providers/base.py` — Fixture-Zweig in `get_provider()`

In `get_provider(name: str)` direkt VOR der lazy `_load_providers()`-Prüfung einfügen:

```python
import os

def get_provider(name: str) -> WeatherProvider:
    fixture_dir = os.environ.get("GZ_TEST_FIXTURE_DIR", "")
    if fixture_dir and name == "openmeteo":
        from providers.fixture import FixtureProvider
        return FixtureProvider(fixture_dir)

    # ... bestehende Logik unverändert ...
```

Wichtig: Der Import von `FixtureProvider` erfolgt lazy (innerhalb der Bedingung), um Zirkelimporte zu vermeiden und sicherzustellen, dass in der Produktion (Var ungesetzt) `fixture.py` nie importiert wird.

### §3 `tests/conftest.py` — autouse-Fixture

Den bestehenden Inhalt (sys.path-Setup) erhalten. Additiv am Ende hinzufügen:

```python
import os
import pytest

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures", "openmeteo")

@pytest.fixture(autouse=True)
def _use_fixture_provider(request):
    """Zwingt alle Tests auf den Offline-FixtureProvider.

    Tests mit @pytest.mark.live erhalten keinen Fixture-Override — sie
    treffen die echte API (Vertragstest-Pflicht, Mock-Verbot).
    """
    if request.node.get_closest_marker("live"):
        # live-Tests: ENV-Var entfernen falls gesetzt (Isolation)
        old = os.environ.pop("GZ_TEST_FIXTURE_DIR", None)
        yield
        if old is not None:
            os.environ["GZ_TEST_FIXTURE_DIR"] = old
    else:
        os.environ["GZ_TEST_FIXTURE_DIR"] = FIXTURE_DIR
        yield
        os.environ.pop("GZ_TEST_FIXTURE_DIR", None)
```

Scope: `function` (Default). Jeder Test startet mit sauberer ENV, kein Leak zwischen Tests.

### §4 `pyproject.toml` — Marker registrieren

In `[tool.pytest.ini_options]` den `markers`-Eintrag ergänzen (oder neu anlegen falls nicht vorhanden):

```toml
[tool.pytest.ini_options]
markers = [
    "live: Tests that hit the real external weather API (excluded from default offline fixture mode)",
]
```

**Revision (2026-05-23, nach TDD-Regressions-Befund):** `addopts` WIRD geändert auf
`-q -m 'not email and not live'`. Grund: Bestehende echte-API-Vertragstests (Diagnose-
Source-Auflösung `test_bug_338`, Provider-Selektion `test_compare_provider_routing`, direkte
`OpenMeteoProvider()`-Unit-Tests, Geosphere-Tests) brechen bzw. treffen weiter die echte API,
wenn sie im Default-Lauf bleiben. Damit der normale Workflow-Lauf (4-tdd-red/5-implement/
6-validate) **null** echte Wetter-Abrufe macht, müssen diese Tests aus dem Default
ausgeschlossen werden. Sie laufen künftig explizit (`pytest -m live`) bzw. in der
Staging-Acceptance (#339).

### §4b Echte-API-Vertragstests mit `@pytest.mark.live` markieren

Alle Backend-Test-Dateien, die echte Open-Meteo-/Geosphere-API treffen ODER die echte
Provider-Klasse/echte Source erwarten, erhalten Modul-Level `pytestmark = pytest.mark.live`.
Empirisch verifiziert (Lauf grün + 0 Call-Delta im Diagnose-Log). **Ausnahme:** Vorschau-/
Rendering-Tests (`test_epic_140_preview_endpoints`, `test_issue_346_fixture_provider`) bleiben
OFFLINE (Fixture) und werden NICHT live-markiert — sie sind tolerant (200/503) bzw. der
eigentliche Beleg, dass der Vorschau-Pfad offline läuft.

### §5 LoC-Schätzung

| Datei | Inhalt | LoC |
|-------|--------|-----|
| `src/providers/fixture.py` | FixtureProvider + Registry + fetch_forecast | ~100 |
| `src/providers/base.py` | Fixture-Zweig in get_provider | ~10 |
| `tests/conftest.py` | autouse-Fixture | ~15 |
| `pyproject.toml` | Marker-Registrierung | ~3 |
| **Summe** | | **~128 LoC** |

LoC-Limit 250 (Default) ausreichend. Kein Override nötig.

## Expected Behavior

- **Input:** `fetch_forecast(location, start=None, end=None, enrich_ensemble=True)` — beliebige `Location` mit `latitude`/`longitude`. `start`/`end` werden ignoriert (Fixture hat feste 72 Punkte ab aktuellem UTC-Tag). `enrich_ensemble` wird ignoriert (kein Ensemble-Call).
- **Output:** `NormalizedTimeseries` mit 72 `ForecastDataPoint`-Instanzen. Timestamps beginnen an `datetime.now(UTC)` 00:00 und schreiten stündlich fort. Feldwerte entsprechen der koordinatennächsten Fixture-Datei (Innsbruck/Stubai/Zillertal per Nearest-Lookup). Kein HTTP-Call.
- **Side effects:**
  - Kein Caching: jeder `fetch_forecast`-Aufruf liest von Disk (Thread-Safe durch Verzicht auf shared mutable state).
  - Wenn `GZ_TEST_FIXTURE_DIR` nicht gesetzt ist: `FixtureProvider` wird nie instanziiert, kein Import, kein Einfluss auf Laufzeitverhalten in Produktion.
  - Wenn Fixture-Datei fehlt: `ProviderError` — kein stiller Fallback auf echte API.

## Acceptance Criteria

**AC-1:** Given `FixtureProvider` ist instanziiert mit einem gültigen `fixture_dir` / When `isinstance(provider, WeatherProvider)` geprüft wird / Then gibt das `True` zurück — der Provider erfüllt das `@runtime_checkable`-Protocol strukturell.
  - Test: (populated after /tdd-red)

**AC-2:** Given `GZ_TEST_FIXTURE_DIR` ist in `os.environ` gesetzt / When `get_provider("openmeteo")` aufgerufen wird / Then ist die Rückgabe eine Instanz von `FixtureProvider` (nicht `OpenMeteoProvider`).
  - Test: (populated after /tdd-red)

**AC-3:** Given `GZ_TEST_FIXTURE_DIR` ist NICHT in `os.environ` gesetzt / When `get_provider("openmeteo")` aufgerufen wird / Then ist die Rückgabe eine Instanz von `OpenMeteoProvider` — Prod-Pfad bleibt 100% unberührt.
  - Test: (populated after /tdd-red)

**AC-4:** Given `GZ_TEST_FIXTURE_DIR` zeigt auf `fixtures/openmeteo` und die drei JSON-Dateien sind vorhanden / When `FixtureProvider.fetch_forecast(location)` für eine beliebige Location in den Alpen aufgerufen wird / Then liefert die Rückgabe ein `NormalizedTimeseries` mit genau 72 `ForecastDataPoint`-Einträgen und macht dabei keinen einzigen HTTP-Request (verifizierbar: Test läuft komplett offline).
  - Test: (populated after /tdd-red)

**AC-5:** Given `FixtureProvider` ist aktiv / When `fetch_forecast` aufgerufen wird / Then ist `data[0].ts` der aktuelle UTC-Tag um 00:00 UTC, `data[1].ts` derselbe Tag um 01:00 UTC — Timestamps sind auf den Aufrufzeitpunkt verankert, unabhängig vom Erstellungsdatum der Fixture-Dateien.
  - Test: (populated after /tdd-red)

**AC-6:** Given conftest ist aktiv und `GZ_TEST_FIXTURE_DIR` ist gesetzt / When `PreviewService.render_email_preview(trip)` in einem Test aufgerufen wird / Then wird kein HTTP-Call an api.open-meteo.com ausgelöst — verifizierbar durch Abwesenheit von `vorschau`-Einträgen in `data/diagnostics/openmeteo_calls*.jsonl` nach dem Testlauf.
  - Test: (populated after /tdd-red)

**AC-7:** Given ein Test trägt `@pytest.mark.live` / When pytest diesen Test ausführt / Then ist `GZ_TEST_FIXTURE_DIR` für diesen Test NICHT gesetzt — `get_provider("openmeteo")` gibt den echten `OpenMeteoProvider` zurück.
  - Test: (populated after /tdd-red)

## Known Limitations

- **Nur 3 Alpen-Locations:** Trips mit Wegpunkten außerhalb des Alpenraums (z.B. GR221 auf Mallorca) erhalten via Nearest-Lookup Alpenwerte (z.B. Innsbruck). Für Render- und Strukturtests (HTML-Aufbau, PreviewService-Pipeline) ist das ausreichend; für den Email-Spec-Validator mit inhaltlicher Plausibilitätsprüfung ggf. nicht — wenn der Validator Temperaturplausibilität gegen Regio-Erwartungen prüft, muss der Test entweder auf eine der 3 Alpen-Locations gehen oder mit `@pytest.mark.live` gegen echte API laufen.
- **Fixture-Format muss mit Go #263 synchron bleiben:** Die JSON-Dateien wurden durch den Go-FixtureProvider generiert. Wenn `model.Timeseries` in Go neue Felder erhält oder umbenennt, muss `fixture.py` das Mapping entsprechend anpassen und die Dateien via `scripts/refresh-openmeteo-fixtures.sh` neu generiert werden. Kein automatischer Kompatibilitäts-Check.
- **`start`/`end` werden ignoriert:** Der FixtureProvider liefert immer 72 Punkte ab aktuellem UTC-Tag, unabhängig vom angeforderten Zeitraum. Tests, die explizit einen bestimmten Datumsbereich prüfen (z.B. historische Abdeckung), müssen mit `@pytest.mark.live` arbeiten.
- **`name` gibt `"openmeteo"` zurück:** Das ist für Transparenz gegenüber Aufrufer gewollt — `SegmentWeatherData.provider` enthält dann `"openmeteo"` statt `"fixture"`. Tests, die den Provider-Namen prüfen, müssen dies berücksichtigen.

## Changelog

- 2026-05-23: Initial spec — Issue #346. Python-Fixture-Provider analog Go #263: FixtureProvider liest vorhandene fixtures/openmeteo/*.json, Nearest-Location-Lookup + Timestamp-Re-Stamping auf aktuellen UTC-Tag, get_provider()-Fixture-Zweig bei GZ_TEST_FIXTURE_DIR, autouse-Fixture in conftest mit live-Marker-Opt-out, pyproject.toml-Marker-Registrierung. ~128 LoC, kein LoC-Override nötig.
