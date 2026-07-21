---
entity_id: bug_538_539_540_546_retrospective_test_fixes
type: bugfix
created: 2026-06-02
updated: 2026-06-02
status: draft
version: "1.0"
tags: [bugfix, tests, retrospective-audit, issue-538, issue-539, issue-540, issue-546]
---

# Bug #538/#539/#540/#546 — Retrospektive Test-Fixes (Audit #510)

## Approval

- [ ] Approved

## Purpose

4 kleine Korrekturen aus dem retrospektiven Adversary-Audit (#510): Ein falscher Test-Marker,
ein falscher UI-Text, 5 fehlende Python-Tests und 1 fehlender Go-Test.
Kein Produktionscode wird geändert — ausschließlich Testdateien und ein Svelte-String.

## Source

- **#539:** `tests/tdd/test_bug_288_ensemble_api_limit.py` — falscher Modul-Marker
- **#546:** `frontend/src/routes/+page.svelte:111` — falscher H1-Text
- **#538:** `tests/tdd/test_bug305_mobile_email.py` — fehlende `include_header`-Tests
- **#540:** `internal/handler/metric_preset_test.go` — fehlender `LoadMetricPresets`-Test

## Estimated Scope

- **LoC:** ~60 (5 Python-Tests + 1 Go-Test + Marker-Verschiebung + 1 String)
- **Files:** 4
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `pyproject.toml` `addopts = "-q -m 'not email and not live'"` | Konfiguration | Definiert welche Marker vom Default-Lauf ausgeschlossen sind |
| `src/output/renderers/email/html.py` — `_render_mobile_compact_rows` | Implementierung | Bereits fertig mit `include_header`-Parameter (Zeilen 168, 329, 349) |
| `internal/store/store.go:340` — `LoadMetricPresets` | Implementierung | Gibt `nil, error` bei korruptem JSON zurück — Test fehlt |
| `docs/specs/modules/bug_463_mobile_email_table_headers.md` | Spec | AC-1–AC-5 für `include_header` |

## Implementation Details

### #539 — Marker-Fix

```python
# tests/tdd/test_bug_288_ensemble_api_limit.py

# ENTFERNEN (Zeile 21):
pytestmark = pytest.mark.live

# ERGÄNZEN — nur auf die zwei Tests die echte API-Calls machen:
@pytest.mark.live
def test_ac1_fetch_segment_weather_accepts_enrich_ensemble_false():
    ...

@pytest.mark.live
def test_ac4_fetch_forecast_default_true_is_backward_compatible():
    ...
```

### #546 — Text-Fix

```svelte
<!-- frontend/src/routes/+page.svelte:111 -->
<!-- vorher -->
Deine Trips & Vergleiche
<!-- nachher -->
Deine Touren & Vergleiche
```

### #538 — 5 neue Python-Tests (class TestMobileCompactHeader)

Direkt `_render_mobile_compact_rows` aus `src.output.renderers.email.html` importieren
und mit `include_header=True/False` aufrufen. Keine Mocks.

```python
from src.output.renderers.email.html import _render_mobile_compact_rows

_ROWS = [{
    "time": "08:00", "temp": "15", "wind": "12",
    "gust": "30", "precip": "0.2", "pop": "10",
    "confidence": "ok", "thunder": None,
    "snow_limit": "2500", "cloud": "50",
    "cloud_low": "30", "visibility": "good", "uv": "4.2", "freeze_lvl": "2710",
}]

class TestMobileCompactHeader:
    # AC-1: include_header=True → Header vor den Daten
    def test_header_present_when_include_header_true():
        result = _render_mobile_compact_rows(_ROWS, friendly_keys=set(), include_header=True)
        assert "Zeit" in result  # Header enthält Zeitlabel

    # AC-2: Night-Rows ebenfalls mit include_header=True → Header
    #       (render_html liefert include_header=True für night_rows — Test via render_html)

    # AC-3: Leere Row-Liste + include_header=True → kein Header, leerer String
    def test_no_header_when_rows_empty():
        result = _render_mobile_compact_rows([], friendly_keys=set(), include_header=True)
        assert "Zeit" not in result

    # AC-4: include_header=False (Default) → kein Header-Div
    def test_no_header_when_include_header_false():
        result = _render_mobile_compact_rows(_ROWS, friendly_keys=set(), include_header=False)
        assert "border-bottom" not in result  # Header-Div hat border-bottom-Style

    # AC-5: Nur sichtbare Spalten erscheinen im Header (wind=None → nicht im Header)
```

### #540 — 1 neuer Go-Test

```go
// internal/handler/metric_preset_test.go
func TestStore_LoadMetricPresets_CorruptJSON(t *testing.T) {
    tmpDir := t.TempDir()
    s := store.New(tmpDir, "test")

    // Korrupte Datei schreiben
    presetsPath := filepath.Join(tmpDir, "users", "test", "metric_presets.json")
    os.MkdirAll(filepath.Dir(presetsPath), 0755)
    os.WriteFile(presetsPath, []byte(`{kaputt`), 0644)

    presets, err := s.LoadMetricPresets()
    if err == nil {
        t.Fatal("LoadMetricPresets sollte bei korruptem JSON einen Fehler liefern, hat aber nil")
    }
    if presets != nil {
        t.Errorf("LoadMetricPresets sollte bei Fehler nil zurückgeben, hat aber %v", presets)
    }
}
```

## Expected Behavior

- **#539:** `uv run pytest` läuft die Signatur-/Logik-Tests aus `test_bug_288_ensemble_api_limit.py`
  ohne `--live`-Flag. Die zwei echten API-Call-Tests bleiben weiterhin über `@pytest.mark.live`
  aus dem Default-Lauf ausgeschlossen.
- **#546:** `test_trips_naming.py::test_homepage_uses_trip_terminology` schlägt nicht mehr fehl.
- **#538:** 5 neue Tests in `TestMobileCompactHeader` laufen grün im Default-CI.
- **#540:** `go test ./internal/handler/...` enthält `TestStore_LoadMetricPresets_CorruptJSON` und läuft grün.

## Acceptance Criteria

- **AC-1:** Given `uv run pytest` (ohne `-m live`) / When die Testsuite läuft / Then werden alle Signatur- und Logik-Tests aus `test_bug_288_ensemble_api_limit.py` ausgeführt (nicht mehr durch modul-weiten `live`-Marker blockiert)
  - Test: (populated after /tdd-red)

- **AC-2:** Given `frontend/src/routes/+page.svelte` / When die Startseite gerendert wird / Then lautet der H1-Text `"Deine Touren & Vergleiche"` (nicht `"Trips"`)
  - Test: (populated after /tdd-red)

- **AC-3:** Given `_render_mobile_compact_rows` mit `include_header=True` und mindestens einer sichtbaren Spalte / When die Funktion aufgerufen wird / Then enthält der Rückgabe-String ein Header-Element mit dem Label `"Zeit"` vor den Daten-Rows
  - Test: (populated after /tdd-red)

- **AC-4:** Given `_render_mobile_compact_rows` mit leerem `rows=[]` und `include_header=True` / When die Funktion aufgerufen wird / Then ist der Rückgabe-String leer (kein Header erzeugt)
  - Test: (populated after /tdd-red)

- **AC-5:** Given `_render_mobile_compact_rows` mit `include_header=False` (Default) / When die Funktion aufgerufen wird / Then enthält der Rückgabe-String kein Header-Element (Regressions-Schutz)
  - Test: (populated after /tdd-red)

- **AC-6:** Given eine E-Mail mit Segment-Rows und ausgeblendeten Spalten (z.B. `thunder=None`) / When die mobile Ansicht gerendert wird / Then zeigt der Header nur die Labels der sichtbaren Spalten
  - Test: (populated after /tdd-red)

- **AC-7:** Given `store.LoadMetricPresets()` mit einer korrupten `metric_presets.json` / When die Methode aufgerufen wird / Then gibt sie `(nil, error)` zurück (nicht `([], nil)`)
  - Test: (populated after /tdd-red)

## Known Limitations

- AC-2 (Nacht-Rows mit Header) aus `bug_463_mobile_email_table_headers.md` wird via
  `render_html()` getestet (nicht direkt `_render_mobile_compact_rows`), da Night-Rows
  nur über den vollständigen Renderer übergeben werden.
- Die Svelte-Änderung (#546) erfordert einen Frontend-Build, hat aber kein eigenes
  E2E-Test-Artefakt — der bestehende `test_trips_naming.py`-Test ist der Nachweis.

## Changelog

- 2026-06-02: Initial spec erstellt. Bündelt 4 kleine Test-Fixes aus Adversary-Audit #510.
