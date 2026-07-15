---
entity_id: config_merge_helper
type: module
created: 2026-07-15
updated: 2026-07-15
status: draft
version: "1.0"
tags: [go, backend, bugfix, refactor, dataloss-prevention]
---

<!-- Issue #1159 — Blind-Replace-Klasse konsolidieren (BUG-DATALOSS-GR221, 6. Wiederholung) -->

# Config-Merge-Helfer — Blind-Replace-Klasse konsolidieren

## Approval

- [ ] Approved

## Purpose

Einen gemeinsamen feldweisen Merge-Helfer (`mergeConfigMap`) im Go-Handler-Layer
einführen, über den alle drei Config-schreibenden PUT-Endpoints (Trip, Location,
ComparePreset) laufen. Behebt den **aktiven Datenverlust** am Location-Endpoint
(Teil-Update löscht `region`/`theme`/andere Keys) und konsolidiert die seit #102
sechsfach wiederholte Blind-Replace-Fehlerklasse (BUG-DATALOSS-GR221: #102 → #1082
→ #1103 → #1129 → #1151 → #1159) in einer einzigen, getesteten Implementierung
statt sie ein siebtes Mal einzeln nachzubauen.

## Source

- **File:** `internal/handler/config_merge.go` (NEU)
- **Identifier:** `func mergeConfigMap(dst, src map[string]interface{}) map[string]interface{}`

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `internal/handler/config_merge.go` | CREATE | Neuer Helfer `mergeConfigMap` (~12 LoC) |
| `internal/handler/weather_config.go` | MODIFY | `PutTripWeatherConfigHandler` (Z.64-69): inline-Loop → Helfer-Call (verhaltensneutral). `PutLocationWeatherConfigHandler` (Z.132): Blind-Replace → Helfer-Call (**Datenverlust-Fix**) |
| `internal/handler/trip.go` | MODIFY | `UpdateTripHandler`: 4 identische inline-Loops (Aggregation Z.214, WeatherConfig Z.222, DisplayConfig Z.230, ReportConfig Z.240) → je ein Helfer-Call (verhaltensneutral) |
| `internal/handler/compare_preset.go` | MODIFY | `UpdateComparePresetHandler` (Z.288-290): `display_config` von Objekt-Level-RMW auf feldweisen Merge umgestellt. NUR `display_config` — die ~20 anderen object-level-preserve-Felder (`OfficialWarnings`, `PreviousSchedule`, `AlertQuietFrom` etc.) bleiben unverändert |
| `internal/handler/config_merge_structure_test.go` | CREATE | Helfer-Unit-Test + table-driven Struktur-Test über alle 3 Endpoints (~100 LoC) |

## Estimated Scope

- **LoC:** Source ~+15/-16 (netto ≈ 0), Test ~+100 → gesamt ~+115
- **Files:** 4 Source (1 neu) + 1 neuer Test
- **Effort:** medium (Datenpersistenz-Schreibpfade, aber mechanisches Refactoring + ein client-kompatibler Bugfix)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/model/trip.go:106-109` (`DisplayConfig`, `Aggregation`, `WeatherConfig`, `ReportConfig`) | model | Vier opake `map[string]interface{}`-Felder, die der Helfer mergt |
| `internal/model/location.go:16` (`DisplayConfig`) | model | Opakes Map-Feld, aktuell Blind-Replace (aktiver Bug) |
| `internal/model/compare_preset.go:48` (`DisplayConfig`) | model | Opakes Map-Feld, wechselt von Objekt-Level-RMW auf Feld-Merge |
| `internal/store/trip.go:92,127` (`LoadTrip`/`SaveTrip`) | store | Pointer-basierte Persistenz — vom Merge-Wechsel nicht betroffen, muss weiter funktionieren |
| `internal/store/location.go:61,80` (`LoadLocation`/`SaveLocation`) | store | Value-basierte Persistenz — vom Merge-Wechsel nicht betroffen |
| `internal/store/compare_preset.go:58,122` (`LoadComparePresets`/`SaveComparePresets`) | store | Slice-basierte Persistenz (kein Single-Get) — vom Merge-Wechsel nicht betroffen |
| `internal/handler/weather_config_1151_test.go` (`TestPutTripWeatherConfigMergesDisplayConfig`) | test | Bestehender Trip-Merge-Test, muss nach Refactoring grün bleiben (verhaltensneutral) |
| `internal/handler/compare_preset_top_n_test.go` (`TestUpdateComparePreset_TopNPreservesDisplayConfigAndIsolatesUsers`) | test | Bestehender ComparePreset-RMW-Test (Round-Trip-Spread), muss nach Umstellung grün bleiben |
| `internal/handler/compare_preset_test.go` (`TestUpdateComparePreset_AlertFields_RoundtripAndRMW`) | test | Bestehender ComparePreset-RMW-Test (fehlendes `display_config` im Folge-PUT), muss grün bleiben |
| `model.ActiveAlertableMetricIDs` / `model.SyncAlertRules` (`weather_config.go:71-72`) | intern | Läuft nach dem Merge-Call im Trip-Pfad weiter unverändert |

## Implementation Details

### 1. Der Helfer

```go
// mergeConfigMap führt Read-Modify-Write feldweise aus: Keys aus src
// überschreiben/ergänzen dst, nicht mitgesendete Keys von dst bleiben
// erhalten. nil-sicher. Ersetzt die 5 inline-Loops in trip.go/weather_config.go.
func mergeConfigMap(dst, src map[string]interface{}) map[string]interface{} {
    if src == nil {
        return dst
    }
    if dst == nil {
        dst = map[string]interface{}{}
    }
    for k, v := range src {
        dst[k] = v
    }
    return dst
}
```

Repliziert exakt die Semantik der vorhandenen `#1151`-Schleife
(`weather_config.go:64-69`): nil-Init + Key-Copy. Paket `handler` (kein neues
`internal/util`-Paket — alle Aufrufer liegen bereits in `handler`).

### 2. Verhaltensneutrales Refactoring (bestehende Tests bleiben grün)

- `weather_config.go:64-69` (Trip-Pfad, `PutTripWeatherConfigHandler`):
  `trip.DisplayConfig = mergeConfigMap(trip.DisplayConfig, cfg)` statt inline-Loop.
- `trip.go:214/222/230/240` (`UpdateTripHandler`, vier Felder):
  `existing.Aggregation = mergeConfigMap(existing.Aggregation, *req.Aggregation)`
  (analog für `WeatherConfig`, `DisplayConfig`, `ReportConfig`) — je ein Helfer-Call
  statt der jeweiligen `if nil {...}; for k,v := range {...}`-Blöcke.

### 3. Datenverlust-Fix (Verhaltensänderung, client-kompatibel)

- `weather_config.go:132` (`PutLocationWeatherConfigHandler`):
  `loc.DisplayConfig = mergeConfigMap(loc.DisplayConfig, cfg)` statt
  `loc.DisplayConfig = cfg`. `loc` ist bereits per `LoadLocation` geladen — nur
  die Zuweisung tauscht sich. Kompatibel zum bestehenden Frontend-Client
  (`WeatherConfigDialog.svelte:126-133`), der ohnehin nur `{metrics}` sendet und
  keine anderen Keys löschen will.

### 4. ComparePreset — `display_config` auf Feld-Merge

- `compare_preset.go:288-290`, bisher:
  ```go
  if updated.DisplayConfig == nil {
      updated.DisplayConfig = original.DisplayConfig
  }
  ```
  neu:
  ```go
  updated.DisplayConfig = mergeConfigMap(original.DisplayConfig, updated.DisplayConfig)
  ```
  Wenn der Client `display_config` komplett weglässt, ist `updated.DisplayConfig`
  nach dem JSON-Decode `nil` → `mergeConfigMap(original, nil)` gibt `original`
  unverändert zurück (identisch zum bisherigen Verhalten). Wenn der Client
  `display_config` **teilweise** sendet (z.B. nur `{"region": "..."}`), werden ab
  jetzt die übrigen Original-Keys (`ideal_ranges`, `channel_layouts`, ...)
  feldweise erhalten statt komplett verworfen zu werden — das ist die
  Verhaltensänderung/Härtung. NUR `display_config` wird umgestellt, die ~20
  anderen object-level-preserve-Felder (`PreviousSchedule`, `OfficialWarnings`,
  `AlertQuietFrom` etc., Z.278-407) bleiben unverändert object-level.

### 5. Struktur-Test (table-driven, über echte HTTP-Handler)

Pro Endpoint (Trip, Location, ComparePreset): Seed mit ≥2 `display_config`-Keys →
Teil-PUT (ein Key weggelassen) über `httptest` gegen den echten
`http.HandlerFunc` → reload aus dem jeweiligen Store → weggelassener Key
überlebt UND gesendeter Key wird aktualisiert. Läuft bewusst über die realen
Handler (jeder mit eigenem Store-Pfad: Location Value-Save, Trip Pointer-Save,
Preset Slice-Save) und **nicht** gegen `mergeConfigMap` isoliert — sonst würde
ein Endpoint, der den Helfer künftig umgeht, nicht auffallen.

## Expected Behavior

- **Input:** PUT-Request mit partiellem `display_config`/`metrics`/`aggregation`/etc.
  Payload gegen `/api/trips/{id}/weather-config`, `/api/trips/{id}`,
  `/api/locations/{id}/weather-config` oder `/api/compare/presets/{id}`.
- **Output:** Persistiertes Objekt, dessen opake Map-Felder feldweise gemergt
  wurden — gesendete Keys aktualisiert, nicht gesendete Keys erhalten.
- **Side effects:** Keine neuen Side-Effects. `SyncAlertRules`-Aufruf im
  Trip-Pfad (`weather_config.go:71-72`) bleibt unverändert nach dem Merge-Call.
  Tenant-Isolation (`s.WithUser(...)`) wird vom Merge nicht berührt.

## Acceptance Criteria

- **AC-1:** Given `mergeConfigMap` wird mit `src == nil` aufgerufen / When der
  Helfer läuft / Then wird `dst` unverändert zurückgegeben (kein Panic, keine
  Mutation), unabhängig davon ob `dst` selbst `nil` oder eine gefüllte Map ist
  - Test: `TestMergeConfigMap_NilSrcReturnsDstUnchanged` — Tabellenzeile mit
    `dst={"a":1}, src=nil` und `dst=nil, src=nil`, prüft Rückgabewert direkt.

- **AC-2:** Given `mergeConfigMap` wird mit `dst == nil` und einer gefüllten
  `src`-Map aufgerufen / When der Helfer läuft / Then wird eine neue Map
  zurückgegeben, die exakt die Keys aus `src` enthält, ohne dass der
  Aufrufer vorher selbst `map[string]interface{}{}` initialisieren muss
  - Test: `TestMergeConfigMap_NilDstInitializes` — `dst=nil, src={"metrics":[...]}`
    → Rückgabe enthält `metrics`.

- **AC-3:** Given eine Location mit `display_config = {region: "Ortler",
  metrics: [...]}` / When `PUT /api/locations/{id}/weather-config` mit Body
  `{"metrics": [...neue Metriken...]}` (ohne `region`) gesendet wird / Then
  überlebt `region` unverändert und `metrics` reflektiert den neuen Payload —
  heute geht `region` verloren (der aktive Bug, den dieses Issue behebt)
  - Test: `TestLocationWeatherConfigPreservesUnsentDisplayConfigKeys` im
    table-driven Struktur-Test — Bug-Repro, rot vor dem Fix in
    `weather_config.go:132`, grün danach.

- **AC-4:** Given die bestehenden Trip-Merge-Tests (#1151
  `TestPutTripWeatherConfigMergesDisplayConfig` in `weather_config_1151_test.go`,
  #1129/#1103 Aggregation/ReportConfig/DisplayConfig-Preserve-Verhalten in
  `trip_write_test.go` — u.a. `TestUpdateTripHandlerMergesDisplayConfig`,
  `TestUpdateTripHandler...PreservesAggregation/ReportConfig/WeatherConfig`) /
  When die fünf inline-Loops durch `mergeConfigMap`-Calls ersetzt werden / Then
  bleiben alle diese Tests unverändert grün (verhaltensneutrales Refactoring,
  kein Regress der seit #1151/#1129/#1103 etablierten Merge-Semantik).

- **AC-5:** Given ein ComparePreset mit `display_config = {region: "Ortler",
  ideal_ranges: {...}}` / When `PUT /api/compare/presets/{id}` mit einem Body
  gesendet wird, der `display_config` nur mit geändertem `region` (ohne
  `ideal_ranges`) trägt / Then überlebt `ideal_ranges` unverändert und `region`
  wird aktualisiert — heute geht `ideal_ranges` in diesem Teilfall verloren,
  weil die Objekt-Level-RMW nur "ganz oder gar nicht" kennt.

- **AC-6:** Given die bestehenden ComparePreset-RMW-Tests
  (`TestUpdateComparePreset_TopNPreservesDisplayConfigAndIsolatesUsers`,
  `TestUpdateComparePreset_AlertFields_RoundtripAndRMW`) / When `display_config`
  auf feldweisen Merge umgestellt wird / Then bleiben beide Tests unverändert
  grün, weil sie entweder den vollen Round-Trip-Spread senden (Merge==Replace
  im Happy Path) oder `display_config` komplett weglassen (Merge mit
  `src==nil` verhält sich identisch zur bisherigen Objekt-Level-Preserve-Logik).

- **AC-7:** Given der table-driven Struktur-Test iteriert über die drei realen
  HTTP-Handler (Trip-, Location-, ComparePreset-Endpoint) / When für jeden
  Endpoint ein Seed mit ≥2 `display_config`-Keys gefolgt von einem Teil-PUT
  (ein Key weggelassen) durchläuft / Then bestätigt jeder der drei Fälle sowohl
  Preservation des weggelassenen Keys als auch Aktualisierung des gesendeten
  Keys — der Test läuft gegen `httptest`-Handler mit dem jeweils echten
  Store-Pfad (Value/Pointer/Slice), nicht gegen `mergeConfigMap` isoliert.

## Known Limitations

- Feldweiser Merge kann per Definition keinen `display_config`-Key mehr durch
  Weglassen **löschen** (nur setzen/überschreiben). Für Trip ist das seit #1151
  akzeptiertes Verhalten; für Location/ComparePreset ist kein genutzter
  Lösch-durch-Weglassen-Pfad bekannt.
- „Neue Endpoints fallen **automatisch** durch" (Issue-Wortlaut) ist mit einem
  table-driven Test **nicht buchstäblich erreichbar** — er deckt nur die 3
  gelisteten Endpoints (Trip, Location, ComparePreset) ab. Ein echter
  Auto-Wächter (Grep-Gate auf `.DisplayConfig = <body>`-Zuweisungen oder eine
  Reflection/Registry-Lösung) wird **bewusst nicht gebaut** (Regel-Budget: ein
  neues Gate bräuchte ein Prüfdatum und einen belegten Fang-Nachweis, den es
  hier nicht gibt). Der Struktur-Test fängt Regression der drei bekannten
  Endpoints, keine künftigen, unbekannten Endpoints.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein neues Paket, kein neuer Dienst, keine neue externe
  Abhängigkeit — Konsolidierung eines bereits etablierten Musters (#1151) in
  eine Helfer-Funktion innerhalb des bestehenden `handler`-Pakets. Kein
  architektur-relevanter Entscheidungsraum (Store-Layer, Auth-Layer,
  API-Contract bleiben unverändert).

## Test Coverage

Tests in `internal/handler/config_merge_structure_test.go` (neu, Kern-Schicht,
deterministisch, echte `httptest`-Handler — keine Mocks):

- `TestMergeConfigMap_NilSrcReturnsDstUnchanged` — Helfer-Unit-Test, `src=nil`
  (mit `dst=nil` und `dst` gefüllt) gibt `dst` unverändert zurück.
- `TestMergeConfigMap_NilDstInitializes` — Helfer-Unit-Test, `dst=nil` mit
  gefüllter `src` erzeugt neue Map mit den `src`-Keys.
- `TestMergeConfigMap_OverwritesAndPreserves` — Helfer-Unit-Test, überlappende
  und disjunkte Keys zwischen `dst`/`src`, prüft Overwrite + Preserve in einem
  Aufruf.
- `TestConfigMergePreservesUnsentDisplayConfigKeys` — table-driven, iteriert
  über die drei Endpoint-Fälle {Trip, Location, ComparePreset}: Seed mit ≥2
  `display_config`-Keys → Teil-PUT über den echten `http.HandlerFunc` (ein Key
  weggelassen) → reload aus dem jeweiligen Store → Assertion: weggelassener Key
  überlebt, gesendeter Key aktualisiert. Der Location-Fall in dieser Tabelle
  ist der Bug-Repro für den aktiven Datenverlust (rot vor dem Fix in
  `weather_config.go:132`, grün danach).

Zusätzlich bleiben folgende bestehende Tests unverändert grün (Regressions-Netz,
keine Änderung an diesen Dateien nötig):

- `internal/handler/weather_config_1151_test.go` (`TestPutTripWeatherConfigMergesDisplayConfig`)
- `internal/handler/trip_write_test.go` (`TestUpdateTripHandlerMergesDisplayConfig` + die `...Preserves{Aggregation,ReportConfig,WeatherConfig,DisplayConfig}`-Tests — das Trip-Regressions-Netz für die 4 umgestellten inline-Loops)
- `internal/handler/compare_preset_top_n_test.go` (`TestUpdateComparePreset_TopNPreservesDisplayConfigAndIsolatesUsers`)
- `internal/handler/compare_preset_test.go` (`TestUpdateComparePreset_AlertFields_RoundtripAndRMW`)
- `internal/handler/weather_config_test.go` (`TestPutLocationWeatherConfig`, weiterhin grün, wird durch den neuen Struktur-Test um die Preserve-Eigenschaft ergänzt)

## Changelog

- 2026-07-15: Initial spec erstellt — Issue #1159, basierend auf
  `docs/context/rework-1159-config-merge-helper.md` (PO-Entscheidung:
  ComparePreset `display_config` JA auf Feld-Merge umstellen).
