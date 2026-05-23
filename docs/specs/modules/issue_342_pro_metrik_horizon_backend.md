---
entity_id: issue_342_pro_metrik_horizon_backend
type: module
created: 2026-05-23
updated: 2026-05-23
status: draft
version: "1.0"
tags: [backend, weather, metric-preset, schema-migration]
parent_epic: 304
---

<!-- Issue #342 — Pro-Metrik-Zeithorizont Backend + Datenmodell (Sub-Issue 1 von Klammer-Epic #304) -->

# Issue #342 — Pro-Metrik-Zeithorizont Backend + Datenmodell

## Approval

- [ ] Approved

## Purpose

Backend-Voraussetzung für die Pro-Metrik-Zeithorizont-Funktion aus Klammer-Epic #304: erweitert `MetricPreset` und `Trip.display_config.metrics[]` schema-additiv um ein `horizons`-Objekt (`today/tomorrow/day_after`), ergänzt einen PATCH-Endpoint für Read-Modify-Write-Updates, und filtert im E-Mail-Renderer pro Etappe Metriken heraus, deren Horizont für den jeweiligen Tag deaktiviert ist. Damit kann der User später (via UI in #343/#344) festlegen, dass z.B. Gewitter-Risiko nur in der morgigen, aber nicht in der übermorgigen Tabellenspalte erscheint — ohne dieses Backend bleiben Horizont-Toggles in der UI wirkungslos.

## Scope

### In Scope

- Go-Modell `MetricPreset.Metrics` von `[]string` + paralleler `FriendlyIDs []string` auf strukturierten `[]DisplayMetric` umstellen
- `Trip.DisplayConfig.metrics[]` additiv um `horizons`-Feld erweitern (kein Struct-Change, da `map[string]interface{}`)
- Neue PATCH-Route `/api/metric-presets/{id}` mit Read-Modify-Write-Semantik
- Default-Migration beim Load: fehlendes `horizons` → `{today:true, tomorrow:true, day_after:true}`; alter `FriendlyIDs []string` wird in `Metrics[].use_friendly_format` konsumiert
- Python-Renderer-Filter in `src/output/renderers/email/helpers.py` (`dp_to_row()` + `visible_cols()`): pro Etappe wird heute/morgen/übermorgen aus dem Etappen-Startdatum abgeleitet und Metriken mit deaktiviertem Horizont weggelassen
- Etappen ab Tag 4 (Horizont-Ableitung ergibt keinen Treffer) ignorieren den Filter und zeigen alle Metriken
- Schema-Backup via `data_schema_backup.py`-Hook + Roundtrip-Test (load alt → save → load → diff)
- Go-Unit-Tests (Modell, Handler, Store) und Python-Unit-Tests (Renderer-Filter) — KEINE MOCKS

### Out of Scope

- HorizonChip-UI-Komponente und Frontend-Toggles → **Issue #343**
- `/account` Wetter-Profile-Verwaltungs-Karte (Umbenennen, Löschen, Default-Setzen aus UI) → **Issue #344**
- Konsolidierung `EditWeatherSection` ↔ `WeatherMetricsTab` → **Issue #345**
- Mobile-Responsive-Anpassungen des Renderers
- SMS-Renderer-Horizont-Filterung (SMS nutzt `display_config.metrics` heute nicht direkt — separate Aufgabe falls gewünscht)
- Übersetzung in andere Sprachen
- TypeScript-Type-Synchronisation im Frontend (folgt in #343 zusammen mit UI-Konsumenten)

## Source

**Geänderte Dateien (Go-Backend):**
- `internal/model/metric_preset.go` — `MetricPreset.Metrics` umstellen auf `[]DisplayMetric`; neuen Typ `DisplayMetric` mit `MetricID`, `Enabled`, `UseFriendlyFormat`, `Horizons` einführen
- `internal/handler/metric_preset.go` — neuer `PatchMetricPresetHandler` mit Read-Modify-Write
- `internal/store/store.go` (L323+) — `LoadMetricPresets` mit Default-Migration für fehlende `horizons` und legacy `FriendlyIDs`
- `cmd/server/main.go` (L128–131) — PATCH-Route registrieren

**Geänderte Dateien (Python-Backend):**
- `src/output/renderers/email/helpers.py` (L66-86, L208) — `dp_to_row()` + `visible_cols()` erhalten optionalen Horizon-Filter; Etappen-Startdatum-zu-Horizon-Mapping
- `src/output/renderers/email/html.py` (L140-160) — `render_html()` propagiert `report_date` und pro Etappe das `etappe_date` an die Helper

**Neue Dateien (Tests):**
- `internal/handler/metric_preset_test.go` — PATCH-Endpoint-Tests, Roundtrip-Test
- `internal/store/store_test.go` — Default-Migration-Tests
- `tests/tdd/test_horizon_filter.py` — Renderer-Filter pro Etappe

> **Schicht-Hinweis:** Diese Spec betrifft **zwei Schichten gleichzeitig** — Go-API (Persistenz + Schema) und Python-Backend (Renderer). Frontend bleibt komplett unberührt (Sub-Issue #343 übernimmt UI). Der Python-Renderer liest das von Go gespeicherte `display_config.metrics[]` aus dem Trip-JSON — die Schicht-Grenze läuft am `data/users/<uid>/trips/<id>.json`-File.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `MetricPreset` Go-Struct | Model | Wird schema-erweitert; bestehendes Preset-System (#138/#177) baut darauf auf |
| `Trip.DisplayConfig` (`map[string]interface{}`) | Model | Additiv erweitert — Read-Modify-Write garantiert keine Datenverluste (BUG-DATALOSS-GR221) |
| `data_schema_backup.py` Hook | Tooling | Auto-Backup vor Edit von `src/app/models.py`, `internal/model/*.go`, `internal/store/store.go` |
| `LoadMetricPresets` / `SaveMetricPresets` | Store-Funktionen | Default-Migration findet hier statt |
| `dp_to_row()` (`helpers.py:66-86`) | Python-Function | Baut eine HTML-Tabellenzeile aus einem Datenpunkt — erhält Horizon-Filter |
| `visible_cols()` (`helpers.py:208`) | Python-Function | Bestimmt sichtbare Spalten — erhält Horizon-Filter |
| `render_html()` (`html.py:140`) | Python-Function | Top-Level-Renderer — propagiert `report_date` und Etappen-Startdatum |
| `epic_138_174_178_metriken_ui` Spec | Vorgänger-Spec | Definiert heutiges `MetricPreset`-Schema und User-Preset-Endpoints |

## Implementation Details

### §1 Go-Modell `internal/model/metric_preset.go` — Schema-Erweiterung

**Vorher (heutiger Stand, aus #138):**

```go
type MetricPreset struct {
    ID          string    `json:"id"`
    Name        string    `json:"name"`
    Description string    `json:"description,omitempty"`
    IsDefault   bool      `json:"is_default"`
    Metrics     []string  `json:"metrics"`       // enabled metric IDs
    FriendlyIDs []string  `json:"friendly_ids"`  // IDs mit use_friendly_format=true
    CreatedAt   time.Time `json:"created_at"`
}
```

**Nachher:**

```go
type Horizons struct {
    Today    bool `json:"today"`
    Tomorrow bool `json:"tomorrow"`
    DayAfter bool `json:"day_after"`
}

type DisplayMetric struct {
    MetricID          string   `json:"metric_id"`
    Enabled           bool     `json:"enabled"`
    UseFriendlyFormat bool     `json:"use_friendly_format"`
    Horizons          Horizons `json:"horizons"`
}

type MetricPreset struct {
    ID          string          `json:"id"`
    Name        string          `json:"name"`
    Description string          `json:"description,omitempty"`
    IsDefault   bool            `json:"is_default"`
    Metrics     []DisplayMetric `json:"metrics"`
    CreatedAt   time.Time       `json:"created_at"`
}
```

`FriendlyIDs []string` entfällt — der Wert wandert beim Load in `DisplayMetric.UseFriendlyFormat`. Damit existiert pro Metrik nur noch **eine** Quelle der Wahrheit für „Indikator-Format ja/nein".

### §2 `Trip.DisplayConfig.metrics[]` — schema-additive Erweiterung

`Trip.DisplayConfig` ist `map[string]interface{}` (siehe `internal/model/trip.go:76`). Keine Struct-Änderung nötig. Die schon heute persistierten Einträge

```json
{"metrics": [{"metric_id": "wind", "enabled": true, "use_friendly_format": false}]}
```

werden erweitert um:

```json
{"metrics": [{
  "metric_id": "wind",
  "enabled": true,
  "use_friendly_format": false,
  "horizons": {"today": true, "tomorrow": true, "day_after": true}
}]}
```

Beim Load: fehlt `horizons`, wird das Objekt mit `{true, true, true}` defaultet (Default = altes Verhalten, alle Metriken in allen Tabellen sichtbar). Diese Defaulting-Logik läuft im Python-Renderer beim Lesen aus `dc.metrics[]` — kein Migrations-Schreibvorgang nötig (additiv, lazy).

### §3 Default-Migration beim Load in `internal/store/store.go`

```go
func (s *Store) LoadMetricPresets() ([]model.MetricPreset, error) {
    raw, err := os.ReadFile(s.PresetsFile())
    if errors.Is(err, fs.ErrNotExist) {
        return []model.MetricPreset{}, nil
    }
    if err != nil {
        return nil, err
    }

    // Zwei-Phasen-Decode: erst Raw-Map zum Erkennen des Legacy-Layouts,
    // dann finale Struct-Form mit Defaulting.
    var rawPresets []map[string]interface{}
    if err := json.Unmarshal(raw, &rawPresets); err != nil {
        return nil, err
    }

    presets := make([]model.MetricPreset, 0, len(rawPresets))
    for _, rp := range rawPresets {
        presets = append(presets, migrateMetricPreset(rp))
    }
    return presets, nil
}

// migrateMetricPreset führt die Migration von Legacy-Schema
// ({metrics:[]string, friendly_ids:[]string}) auf neues Schema
// ({metrics:[]DisplayMetric}) durch — und defaultet horizons.
func migrateMetricPreset(rp map[string]interface{}) model.MetricPreset {
    // 1. ID/Name/Description/IsDefault/CreatedAt unverändert übernehmen
    // 2. Wenn rp["metrics"] []string → konvertiere zu []DisplayMetric,
    //    use_friendly_format = (metric_id in rp["friendly_ids"]),
    //    horizons = {true, true, true}
    // 3. Wenn rp["metrics"] []map → übernehme strukturiert, defaulte fehlende horizons
}
```

`SaveMetricPresets` bleibt unverändert (schreibt direkt das neue Schema; `FriendlyIDs` taucht in der serialisierten Form nicht mehr auf).

### §4 PATCH-Route `/api/metric-presets/{id}` mit Read-Modify-Write

Neuer Handler in `internal/handler/metric_preset.go`:

```go
func PatchMetricPresetHandler(store *store.Store) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        id := chi.URLParam(r, "id")

        // 1. Bestehende Presets laden
        presets, err := store.LoadMetricPresets()
        // ... error handling ...

        // 2. Existing Preset finden
        idx := -1
        for i, p := range presets {
            if p.ID == id { idx = i; break }
        }
        if idx < 0 { http.Error(w, "not found", 404); return }

        // 3. Partial-Update-Payload decoden (alle Felder optional)
        var patch struct {
            Name        *string          `json:"name,omitempty"`
            Description *string          `json:"description,omitempty"`
            IsDefault   *bool            `json:"is_default,omitempty"`
            Metrics     *[]DisplayMetric `json:"metrics,omitempty"`
        }
        json.NewDecoder(r.Body).Decode(&patch)

        // 4. Read-Modify-Write: nur vorhandene Felder überschreiben
        existing := presets[idx]
        if patch.Name != nil        { existing.Name = *patch.Name }
        if patch.Description != nil { existing.Description = *patch.Description }
        if patch.IsDefault != nil   { existing.IsDefault = *patch.IsDefault }
        if patch.Metrics != nil     { existing.Metrics = *patch.Metrics }

        // 5. is_default=true → alle anderen auf false
        if patch.IsDefault != nil && *patch.IsDefault {
            for i := range presets {
                if i != idx { presets[i].IsDefault = false }
            }
        }
        presets[idx] = existing

        // 6. Speichern
        store.SaveMetricPresets(presets)
        json.NewEncoder(w).Encode(existing)
    }
}
```

Route-Registrierung in `cmd/server/main.go`:

```go
r.Patch("/api/metric-presets/{id}", handler.PatchMetricPresetHandler(store))
```

### §5 Etappen-zu-Horizon-Mapping (Renderer-Logik)

Die Zuordnung erfolgt im Python-Renderer **pro Etappe** auf Basis des Etappen-Startdatums:

```python
def derive_horizon(report_date: date, etappe_date: date) -> str | None:
    """
    Liefert den Horizont-Schlüssel für eine Etappe relativ zum Report-Datum.
    None bedeutet: Etappe liegt außerhalb der drei Horizonte (Tag 4+),
    Horizon-Filter wird ignoriert → alle Metriken werden gezeigt.
    """
    delta = (etappe_date - report_date).days
    if delta == 0: return "today"
    if delta == 1: return "tomorrow"
    if delta == 2: return "day_after"
    return None  # Tag 4+: ignoriere Horizont
```

Aufruf-Stelle: `render_html()` in `html.py:140`. `report_date` wird einmalig aus `segments[0].segment.start_time.date()` extrahiert (siehe `html.py:160`). Pro Etappe wird `etappe_date = segment.start_time.date()` berechnet und an `dp_to_row()`/`visible_cols()` weitergereicht.

### §6 `helpers.py` — Filter in `visible_cols()` und `dp_to_row()`

`visible_cols()` (heute L208) wird erweitert um optionale `horizon: str | None`-Parameter:

```python
def visible_cols(
    dc_metrics: list[dict],
    horizon: str | None = None,
) -> list[str]:
    """
    Liefert die für diese Etappe sichtbaren metric_ids.

    horizon=None → kein Filter (Tag 4+ oder Renderer ohne Horizon-Support).
    horizon="today"|"tomorrow"|"day_after" → nur Metriken mit
      horizons[horizon] == True werden zurückgegeben.
    """
    cols = []
    for m in dc_metrics:
        if not m.get("enabled", True):
            continue
        if horizon is not None:
            horizons = m.get("horizons", {"today": True, "tomorrow": True, "day_after": True})
            if not horizons.get(horizon, True):
                continue
        cols.append(m["metric_id"])
    return cols
```

`dp_to_row()` (heute L66-86) wird analog erweitert: es ruft `visible_cols()` mit dem Etappen-Horizont auf und filtert die Spalten entsprechend, bevor es die HTML-Zelle baut.

**Default-Verhalten:** Fehlt `horizons` im Trip-JSON (Legacy-Trip ohne Migration), gibt `m.get("horizons", {...all True...})` alle drei Horizonte als `True` zurück — der Filter lässt alle Metriken durch. Damit ist Backward-Compat ohne Migrations-Lauf gegeben.

### §7 LoC-Budget

| Block | Datei | Δ LoC |
|-------|-------|-------|
| Go-Modell | `internal/model/metric_preset.go` | +25 / -8 = netto +17 |
| Go-Store-Migration | `internal/store/store.go` | +50 |
| Go-Handler PATCH | `internal/handler/metric_preset.go` | +55 |
| Go-Route | `cmd/server/main.go` | +1 |
| Go-Tests | `internal/handler/metric_preset_test.go`, `internal/store/store_test.go` | +90 |
| Python-Renderer | `src/output/renderers/email/helpers.py` | +25 |
| Python-Renderer-Wiring | `src/output/renderers/email/html.py` | +15 |
| Python-Tests | `tests/tdd/test_horizon_filter.py` | +65 |
| **Gesamt netto** | | **~318 LoC** |

Über 250-LoC-Limit. Override vor Implementierung mit Begründung „Schema-Migration mit Defaulting + Renderer-Filter + Roundtrip-Tests in zwei Schichten":

```bash
python3 .claude/hooks/workflow.py set-field loc_limit_override 400
```

## Expected Behavior

- **Input (Renderer):** `render_html(forecast, dc_metrics)` mit `forecast.segments[]` (mind. eine Etappe) und `dc.metrics[]` mit `horizons`-Objekt pro Metrik.
- **Output (Renderer):** HTML mit einer Tabelle pro Etappe; jede Tabelle zeigt nur die Spalten, für die der zur Etappe gehörige Horizont `True` ist. Etappen ab Tag 4 zeigen alle aktivierten Metriken.
- **Input (API PATCH):** `PATCH /api/metric-presets/{id}` mit Body `{"name": "Neuer Name"}` (Beispiel).
- **Output (API PATCH):** HTTP 200 mit komplettem Preset-Objekt; nur `name` ist geändert, `metrics[]` und alle anderen Felder unverändert. HTTP 404 wenn `id` nicht existiert.
- **Side effects:**
  - `data/users/<uid>/metric_presets.json` wird neu geschrieben (komplette Datei, kein Append)
  - Bei `is_default: true` werden alle anderen Presets auf `is_default: false` gesetzt
  - Vor jedem Schema-Edit greift `data_schema_backup.py`-Hook und schreibt `.backups/data-pre-rework-<ts>.tar.gz`

## Acceptance Criteria

- **AC-1:** Given ein Trip mit Etappen-Startdatum = Report-Datum und ein `display_config.metrics[]` mit Eintrag `{metric_id:"thunder", enabled:true, horizons:{today:false, tomorrow:true, day_after:true}}` / When `render_html()` die HTML-Tabelle für die heutige Etappe baut / Then enthält die Tabelle keine `thunder`-Spalte, alle anderen aktivierten Metriken bleiben sichtbar
  - Test: (populated after /4-tdd-red)

- **AC-2:** Given derselbe Trip wie AC-1 mit einer zweiten Etappe am Folgetag (Report-Datum + 1) / When `render_html()` die HTML-Tabelle für die morgige Etappe baut / Then enthält die Tabelle die `thunder`-Spalte, weil `horizons.tomorrow=true`
  - Test: (populated after /4-tdd-red)

- **AC-3:** Given ein Trip mit fünf Etappen, Etappe 4 startet am Report-Datum + 3 Tage / When `render_html()` die Tabelle für Etappe 4 baut / Then werden alle aktivierten Metriken gezeigt (Horizont-Filter ignoriert, weil `derive_horizon()` `None` liefert) — unabhängig von den `horizons`-Flags
  - Test: (populated after /4-tdd-red)

- **AC-4:** Given eine `metric_presets.json` mit einem Legacy-Preset (`{"metrics":["wind","temperature"], "friendly_ids":["wind"]}` ohne `horizons`-Feld) / When `LoadMetricPresets()` aufgerufen wird / Then wird das Preset zu `{"metrics":[{"metric_id":"wind", "enabled":true, "use_friendly_format":true, "horizons":{today:true, tomorrow:true, day_after:true}}, {"metric_id":"temperature", "enabled":true, "use_friendly_format":false, "horizons":{today:true, tomorrow:true, day_after:true}}]}` mit allen drei Horizonten auf `true` defaultet, und `use_friendly_format` korrekt aus der `friendly_ids`-Liste konsumiert
  - Test: (populated after /4-tdd-red)

- **AC-5:** Given ein bestehendes Preset mit ID `p1`, Name `"Original"`, Metrics `[{wind, enabled:true}]` und `is_default:false` / When `PATCH /api/metric-presets/p1` mit Body `{"name": "Umbenannt"}` aufgerufen wird / Then antwortet die API mit HTTP 200 und einem Body, in dem nur `name="Umbenannt"` geändert ist; `metrics[]`, `is_default`, `description`, `created_at` sind byte-identisch zum vorherigen Stand (Read-Modify-Write)
  - Test: (populated after /4-tdd-red)

- **AC-6:** Given eine `metric_presets.json` mit drei Presets im Legacy-Format / When `LoadMetricPresets()` → `SaveMetricPresets()` → `LoadMetricPresets()` ohne explizite Änderungen aufgerufen wird / Then liefert der zweite Load drei Presets, deren strukturierte `metrics[]`-Liste, `use_friendly_format`-Werte und `horizons`-Defaults dem Ergebnis des ersten Loads byte-identisch entsprechen (Roundtrip-Stabilität, keine Datenverluste)
  - Test: (populated after /4-tdd-red)

- **AC-7:** Given ein Trip-JSON mit `display_config.metrics` ohne `horizons`-Feld (Legacy) / When `render_html()` für diesen Trip läuft / Then werden alle aktivierten Metriken in allen Etappen-Tabellen gezeigt (Horizon-Default `{true,true,true}` greift), keine Exception, keine fehlende Spalte
  - Test: (populated after /4-tdd-red)

## Architecture

### Datenmodell vorher / nachher

```
VORHER (Schema #138):
+-------------------+         +---------------------+
| MetricPreset      |         | Trip.DisplayConfig  |
| - ID              |         | (map[string]any)    |
| - Name            |         |                     |
| - Metrics:        |         | metrics: [          |
|     []string      |         |   {metric_id,       |
| - FriendlyIDs:    |         |    enabled,         |
|     []string      |         |    use_friendly}    |
+-------------------+         | ]                   |
                              +---------------------+

NACHHER (Schema #342):
+----------------------------+         +---------------------+
| MetricPreset               |         | Trip.DisplayConfig  |
| - ID                       |         | (map[string]any)    |
| - Name                     |         |                     |
| - Metrics: []DisplayMetric |         | metrics: [          |
+----------------------------+         |   {metric_id,       |
            |                          |    enabled,         |
            v                          |    use_friendly,    |
+----------------------------+         |    horizons:{       |
| DisplayMetric              |         |      today,         |
| - MetricID                 |         |      tomorrow,      |
| - Enabled                  |         |      day_after}}    |
| - UseFriendlyFormat        |         | ]                   |
| - Horizons:                |         +---------------------+
|     {today, tomorrow,
|      day_after}            |
+----------------------------+
```

### Etappen-zu-Horizon-Mapping (Renderer-Flow)

```
render_html(forecast, dc_metrics)
  ├── report_date = forecast.segments[0].segment.start_time.date()
  └── für jede Etappe in forecast.segments:
        ├── etappe_date = segment.start_time.date()
        ├── horizon = derive_horizon(report_date, etappe_date)
        │     • delta=0 → "today"
        │     • delta=1 → "tomorrow"
        │     • delta=2 → "day_after"
        │     • sonst   → None (kein Filter)
        ├── cols = visible_cols(dc_metrics, horizon=horizon)
        └── dp_to_row(datapoint, cols)  → <tr><td>…</td></tr>
```

## Data Model

### `MetricPreset` JSON-Schema (nachher)

```json
{
  "id": "uuid-v4",
  "name": "Wandern Sommer",
  "description": "Hauptmetriken für Sommer-Trekking",
  "is_default": true,
  "metrics": [
    {
      "metric_id": "wind",
      "enabled": true,
      "use_friendly_format": false,
      "horizons": {"today": true, "tomorrow": true, "day_after": false}
    },
    {
      "metric_id": "thunder",
      "enabled": true,
      "use_friendly_format": true,
      "horizons": {"today": false, "tomorrow": true, "day_after": true}
    }
  ],
  "created_at": "2026-05-23T08:00:00Z"
}
```

### `Trip.display_config.metrics[]` JSON (nachher)

```json
{
  "display_config": {
    "metrics": [
      {
        "metric_id": "wind",
        "enabled": true,
        "use_friendly_format": false,
        "horizons": {"today": true, "tomorrow": true, "day_after": true}
      }
    ]
  }
}
```

## API

### PATCH `/api/metric-presets/{id}`

**Request:**

```http
PATCH /api/metric-presets/preset-abc123 HTTP/1.1
Content-Type: application/json

{
  "name": "Wandern Herbst"
}
```

**Response 200 OK:**

```json
{
  "id": "preset-abc123",
  "name": "Wandern Herbst",
  "description": "Hauptmetriken für Sommer-Trekking",
  "is_default": true,
  "metrics": [
    {"metric_id":"wind", "enabled":true, "use_friendly_format":false,
     "horizons":{"today":true,"tomorrow":true,"day_after":false}}
  ],
  "created_at": "2026-05-23T08:00:00Z"
}
```

**Response 404 Not Found:** Body `{"error":"preset not found"}` wenn `id` in der Datei nicht existiert.

**Partial-Update-Felder (alle optional):** `name`, `description`, `is_default`, `metrics`. Fehlende Felder bleiben unverändert (Read-Modify-Write).

## Migration Strategy

### 1. Pre-Edit Backup

Der `data_schema_backup.py`-Hook (siehe CLAUDE.md, „Daten-Schema-Reworks (PFLICHT)") schreibt automatisch ein tar.gz von `data/users/` nach `.backups/data-pre-rework-<ts>.tar.gz` (Retention 20), sobald eine der folgenden Dateien editiert wird:

- `internal/model/metric_preset.go`
- `internal/store/store.go`

Kein manueller Backup-Schritt nötig.

### 2. Lazy Migration beim Load

Es gibt **keinen separaten Migrations-Lauf**. Das alte Schema wird beim ersten Load durch `LoadMetricPresets()` zwei-phasig dekodiert (siehe §3) und im Speicher in das neue Schema überführt. Erst bei einem expliziten User-Save (z.B. via PATCH oder POST) wird das neue Schema persistiert. Damit:

- Bestehende JSON-Dateien bleiben unverändert, bis sie das nächste Mal geschrieben werden
- Roundtrip-Test (AC-6) garantiert, dass die Migration deterministisch und verlustfrei ist
- Rollback ist trivial: alte Code-Version weiter-deployen — die alten JSON-Dateien sind unverändert

### 3. Roundtrip-Test (AC-6)

Verifiziert, dass `Load → Save → Load` für ein Legacy-Preset deterministisch das gleiche Ergebnis liefert. Bei einer Diff bricht der Test mit detailliertem Fehler-Output, bevor irgendwas auf Production gelangt.

### 4. Post-Deploy-Verifikation

Nach Deploy: Liste aller User-Presets via `GET /api/metric-presets` abrufen und mit Pre-Snapshot vergleichen (gleiche Anzahl, gleiche Namen, gleiche enabled-Metriken). Bei Differenz → sofort Rollback aus `.backups/`.

## Affected Files

| Pfad | Änderung | Schicht |
|------|----------|---------|
| `internal/model/metric_preset.go` | `MetricPreset.Metrics` auf `[]DisplayMetric`; neue Typen `DisplayMetric` + `Horizons`; `FriendlyIDs` entfernt | Go-Backend |
| `internal/store/store.go` | `LoadMetricPresets()` mit zwei-phasigem Decode + Legacy-Migration | Go-Backend |
| `internal/handler/metric_preset.go` | Neuer `PatchMetricPresetHandler` | Go-Backend |
| `cmd/server/main.go` | PATCH-Route registriert | Go-Backend |
| `src/output/renderers/email/helpers.py` | `visible_cols()` + `dp_to_row()` mit `horizon`-Parameter | Python-Backend |
| `src/output/renderers/email/html.py` | `render_html()` propagiert `report_date` + Etappen-Horizont | Python-Backend |
| `internal/handler/metric_preset_test.go` | PATCH-Tests | Go-Tests |
| `internal/store/store_test.go` | Default-Migration- + Roundtrip-Tests | Go-Tests |
| `tests/tdd/test_horizon_filter.py` | Renderer-Filter pro Etappe | Python-Tests |

## Tests

Alle Tests laufen **ohne Mocks** (CLAUDE.md-Pflicht: „KEINE MOCKED TESTS!").

### Go-Unit-Tests (`internal/handler/metric_preset_test.go`)

- **`TestPatchMetricPreset_NameOnly`** (AC-5): Legt echtes Preset via `POST` an, ändert Name via `PATCH`, prüft Response + persistierten Zustand auf der Platte. Nutzt temporäres `t.TempDir()` als Store-Verzeichnis.
- **`TestPatchMetricPreset_NotFound`**: PATCH auf nicht-existierende ID → HTTP 404.
- **`TestPatchMetricPreset_IsDefaultExclusive`**: Zwei Presets, beide initial `is_default:false`. PATCH auf Preset B mit `is_default:true`. Erwartet: B hat danach `is_default:true`, A bleibt `is_default:false` (kein anderer wurde fälschlich umgesetzt). Zweiter PATCH auf A mit `is_default:true` → A=true, B=false.

### Go-Unit-Tests (`internal/store/store_test.go`)

- **`TestLoadMetricPresets_LegacyDefaulting`** (AC-4): Schreibt JSON mit Legacy-Schema (`{metrics:[...string], friendly_ids:[...]}`) auf Platte, ruft `LoadMetricPresets()`, prüft dass `Metrics[].UseFriendlyFormat` aus `friendly_ids` befüllt und alle `Horizons` auf `true` defaultet sind.
- **`TestLoadMetricPresets_RoundtripStability`** (AC-6): Load → Save → Load → DeepEqual. Drei Test-Presets (eines Legacy, eines neu, eines Mischform).
- **`TestLoadMetricPresets_NewSchemaHorizonsDefault`**: Neu-Schema-Preset ohne `horizons`-Feld (nur `metric_id`, `enabled`, `use_friendly_format`) → `horizons` wird auf `{true,true,true}` defaultet.

### Python-Unit-Tests (`tests/tdd/test_horizon_filter.py`)

- **`test_visible_cols_filters_today_metric`** (AC-1): Mock-freier Test, baut echte `dc_metrics`-Liste, ruft `visible_cols(dc, horizon="today")` mit einem Metric `thunder` (`horizons.today=false`) — erwartet, dass `thunder` nicht in der Liste ist.
- **`test_visible_cols_shows_tomorrow_metric`** (AC-2): Gleiche Liste, `horizon="tomorrow"` — `thunder` ist in der Liste (`horizons.tomorrow=true`).
- **`test_visible_cols_ignores_horizon_for_day4`** (AC-3): `horizon=None` (Tag 4+) → alle aktivierten Metriken in der Liste, unabhängig von `horizons`-Flags.
- **`test_visible_cols_legacy_no_horizons_field`** (AC-7): `dc_metrics` ohne `horizons`-Feld, `horizon="today"` → Metrik wird gezeigt (Default `{true,true,true}` greift).
- **`test_derive_horizon_mapping`**: Direkter Test der `derive_horizon()`-Funktion mit allen vier Delta-Fällen (0, 1, 2, 3).
- **`test_render_html_filters_per_stage`**: End-to-End-Test mit echtem `NormalizedForecast`-Objekt (drei Etappen heute/morgen/übermorgen), echtem `dc_metrics`-Dict mit pro Metrik unterschiedlichen `horizons` — assertet, dass die generierte HTML-Tabelle pro Etappe die richtigen Spalten enthält.

## Risks

1. **Schema-Migration in zwei Schichten:** Go-Modell ändert sich strukturell (`[]string` → `[]DisplayMetric`); Python liest dasselbe JSON. Risiko, dass Python alte Felder erwartet, die Go nicht mehr schreibt. **Mitigation:** Python liest nur aus `Trip.display_config.metrics[]` (additiv erweitert, kein Feld entfernt) — Preset-Schema-Änderung betrifft Python nicht direkt. Roundtrip-Test (AC-6) deckt Go-Seite ab.

2. **Renderer-Architektur ist pro-Etappe, nicht pro-Tag:** `helpers.py` kennt heute nur Datenpunkte, kein Etappen-Datum. Der Horizon-Filter erfordert, dass `render_html()` das Etappen-Datum an `visible_cols()` weiterreicht. **Mitigation:** §6 + AC-1/2/3 testen genau diese Datenpfad-Erweiterung.

3. **Parallele `FriendlyIDs`-Liste muss konsumiert werden:** Bei der Migration darf kein `use_friendly_format`-Bit verloren gehen. **Mitigation:** AC-4 testet genau diesen Pfad mit einer Legacy-`friendly_ids`-Liste.

4. **`data_schema_backup.py`-Hook könnte fehlende Backup-Trigger haben:** Vor Edit der relevanten Schicht-Dateien muss der Hook greifen. **Mitigation:** Vor dem ersten Schema-Edit manuell verifizieren, dass das tar.gz in `.backups/` entsteht. Falls Hook nicht triggert: vor der Spec-Implementierung Hook-Whitelist ergänzen (separater Mini-Issue).

5. **PATCH-Endpoint vor Frontend-Konsumenten:** PATCH wird in dieser Spec hinzugefügt, aber erst in #343/#344 vom Frontend konsumiert. Es entsteht für ~1 Sprint ein „toter" Endpoint. **Mitigation:** Endpoint vollständig testen (Go-Unit-Tests AC-5), damit er bei Anschluss in #343/#344 zuverlässig läuft.

6. **LoC-Limit 250 wird überschritten (~318 LoC):** Override `loc_limit_override 400` mit dokumentierter Begründung „Schema-Migration in zwei Schichten + Roundtrip-Tests" vor Phase 6.

## Out of Scope

- **HorizonChip-UI-Komponente** (drei Toggle-Pills pro Metrik-Zeile) → **Issue #343**
- **`/account` Wetter-Profile-Karte** (verwaltete Liste mit Umbenennen/Löschen/Default-Setzen aus UI) → **Issue #344**
- **Konsolidierung `EditWeatherSection` ↔ `WeatherMetricsTab`** → **Issue #345**
- **Mobile-Responsive-Anpassungen** des E-Mail-Renderers
- **Übersetzung** der Renderer-Texte in andere Sprachen
- **SMS-Renderer-Horizont-Filterung:** SMS-Renderer (`src/output/renderers/sms/`) nutzt `display_config.metrics` heute nicht direkt — wird ggf. in separatem Issue nachgezogen
- **TypeScript-Type-Synchronisation** im Frontend: passiert in #343 zusammen mit UI-Konsumenten
- **`metric_presets.json`-Bulk-Migration** auf Platte (Lazy-Migration via Load reicht — siehe Migration Strategy §2)

## Known Limitations

- **Lazy-Migration ohne Schreib-Lauf:** Bestehende JSON-Dateien werden erst beim nächsten User-Save in das neue Schema überführt. Wer das Schema „auf Platte" prüfen will, sieht alte Dateien — das ist beabsichtigt für Rollback-Sicherheit.
- **Tag 4+ ohne Horizont-Differenzierung:** Etappen außerhalb der drei Horizonte zeigen immer alle aktivierten Metriken. Eine feinere Steuerung („Tag 4 wie heute behandeln") ist nicht im Scope.
- **PATCH ohne Field-Level-Validation:** Der Handler akzeptiert beliebige `metrics[]`-Inhalte. Eine schema-genaue Validierung (z.B. „metric_id muss im /api/metrics-Katalog existieren") ist nicht im Scope dieser Spec.

## Changelog

- 2026-05-23: Initial spec erstellt. Sub-Issue 1 von Klammer-Epic #304. Schema-Erweiterung `MetricPreset` + `Trip.display_config.metrics[]` um `horizons`; neuer PATCH-Endpoint; Renderer-Filter pro Etappe in `src/output/renderers/email/helpers.py`. ~318 LoC netto, 9 Dateien (4 Go, 2 Python, 3 Tests). 7 Acceptance Criteria im AC-N-Format. Out-of-Scope: UI (#343), Account-Karte (#344), Editor-Konsolidierung (#345).
