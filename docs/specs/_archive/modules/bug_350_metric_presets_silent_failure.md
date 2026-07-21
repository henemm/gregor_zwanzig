---
entity_id: bug_350_metric_presets_silent_failure
type: module
created: 2026-05-24
updated: 2026-05-24
status: draft
version: "1.0"
tags: [bug, store, metric-presets, data-loss]
---

# Bug #350 — LoadMetricPresets behandelt korruptes JSON wie leere Datei

## Approval

- [ ] Approved

## Purpose

`Store.LoadMetricPresets()` schluckt Lese- und JSON-Parse-Fehler still und gibt in
beiden Fällen `([], nil)` zurück. Eine korrupte `metric_presets.json` ist dadurch
nicht von einem legitim leeren Zustand zu unterscheiden — beim nächsten Save wird
die korrupte Datei mit der leeren Liste überschrieben und alle Presets gehen
verloren. Der Fix gleicht die Funktion an das im Store bereits etablierte
Fehler-Muster an: kaputt/unlesbar → Fehler melden, Datei-fehlt → legitim leer.

## Source

- **File:** `internal/store/store.go`
- **Identifier:** `func (s *Store) LoadMetricPresets() ([]model.MetricPreset, error)` (Z. 339-356)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `os.ReadFile` / `os.IsNotExist` | stdlib | Datei lesen, Not-Found vom echten Fehler trennen |
| `json.Unmarshal` | stdlib | JSON dekodieren; Fehler = korruptes File |
| `ListMetricPresetsHandler` / `CreateMetricPresetHandler` / `DeleteMetricPresetHandler` | Go-Handler | Aufrufer — bilden `err != nil` bereits auf `500 store_error` ab, kein Handler-Fix nötig |

## Implementation Details

Nur die zwei still-schluckenden Returns in `LoadMetricPresets()` ändern. Das
File-not-found-Verhalten (`os.IsNotExist` → leerer Slice) bleibt unverändert.

```go
func (s *Store) LoadMetricPresets() ([]model.MetricPreset, error) {
	data, err := os.ReadFile(s.PresetsFile())
	if err != nil {
		if os.IsNotExist(err) {
			return []model.MetricPreset{}, nil // legitim leer — bleibt
		}
		return nil, err // VORHER: return []MetricPreset{}, nil  (Z. 345)
	}
	var rawPresets []map[string]interface{}
	if err := json.Unmarshal(data, &rawPresets); err != nil {
		return nil, fmt.Errorf("metric_presets.json korrupt: %w", err) // VORHER: return []MetricPreset{}, nil  (Z. 349)
	}
	// ... Migration unverändert ...
}
```

Spiegelt exakt das Muster von `LoadTrip` (Z. 138-146), `LoadLocation` (Z. 192-200)
und Subscriptions-Load (Z. 242-252).

## Expected Behavior

- **Input:** Pfad auf `metric_presets.json` des aktuellen Users.
- **Output:**
  - Datei fehlt → `([]MetricPreset{}, nil)` (unverändert)
  - Datei valide → migrierte Preset-Liste, `nil`-Fehler (unverändert)
  - Datei korrupt (ungültiges JSON) → `(nil, error)` **(neu)**
  - Datei unlesbar (Permission o.ä.) → `(nil, error)` **(neu)**
- **Side effects:** Keine. `SaveMetricPresets` bleibt byte-gleich; ein korruptes
  File wird nicht mehr überschrieben, weil der Handler beim Load-Fehler mit `500`
  abbricht, bevor Save erreicht wird.

## Acceptance Criteria

- **AC-1:** Given eine `metric_presets.json` mit ungültigem JSON-Inhalt / When
  `LoadMetricPresets()` aufgerufen wird / Then liefert sie einen Fehler (`err != nil`)
  und NICHT `([], nil)`.
  - Test: (populated after /tdd-red)

- **AC-2:** Given keine `metric_presets.json` (Erst-Aufruf, File existiert nicht) /
  When `LoadMetricPresets()` aufgerufen wird / Then liefert sie `([]MetricPreset{}, nil)`
  ohne Fehler (legitimer Leer-Zustand bleibt erhalten).
  - Test: (populated after /tdd-red)

- **AC-3:** Given eine korrupte `metric_presets.json` mit zuvor 5 gültigen Presets im
  Backup-Stand / When ein POST `/api/metric-presets` ein neues Preset anlegen will /
  Then antwortet der Handler mit `500 store_error` und die Datei auf der Platte wird
  NICHT mit der leeren/einelementigen Liste überschrieben.
  - Test: (populated after /tdd-red)

## Known Limitations

- Reparatur der korrupten Datei bleibt manuell — der Fix verhindert Datenverlust durch
  Überschreiben, repariert aber nicht den bereits korrupten Inhalt.
- Backup-on-Save (`.backups/metric_presets-<ts>.json`, Retention 10) ist bewusst NICHT
  im Scope (PO-Entscheidung 2026-05-24) — der Kern-Fix genügt zur Verhinderung des
  gemeldeten Datenverlusts.

## Changelog

- 2026-05-24: Initial spec created (Adversary-Finding F002 aus #342)
