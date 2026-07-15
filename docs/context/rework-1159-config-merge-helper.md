# Context: rework-1159-config-merge-helper

## Request Summary

Issue #1159 (priority:high, type:bug + type:rework): Die „Blind-Replace"-Fehlerklasse
(BUG-DATALOSS-GR221, #102 → #1082 → #1103 → #1129 → #1151 → hier) strukturell töten
statt zum sechsten Mal einzeln zu fixen. Ziel: **ein gemeinsamer feldweiser Merge-Helfer**
im Go-Handler-Layer, über den **alle** Config-schreibenden PUT-Endpoints laufen, plus ein
**iterierender Struktur-Test**, durch den neue Endpoints automatisch fallen, wenn sie den
Helfer umgehen.

## Scope-Abgleich (Stand 2026-07-15, wichtig — Issue-Text ist vom 09.07.)

- **Subscription-Handler entfällt:** `PutSubscriptionWeatherConfigHandler` wurde in
  **#1250 Scheibe 0** entfernt (Legacy-Drittstack `CompareSubscription`), siehe
  `weather_config.go:149-150`. Aus den ursprünglich 4 Endpoint-Familien werden **3**:
  Trip, Location, ComparePreset.
- Die im Issue genannte Blind-Stelle Subscription (`sub.DisplayConfig = cfg`) existiert
  nicht mehr.

## Kernbefund: Location ist ein AKTIVER Datenverlust-Pfad

| Endpoint | Backend-Verhalten | Client-Payload | Risiko |
|---|---|---|---|
| `PUT /api/trips/{id}/weather-config` | Feldweiser Merge (#1151) | partiell **+ Client-Spread** `...trip.display_config` | doppelt abgesichert |
| `PUT /api/locations/{id}/weather-config` | **Blind-Replace** (`loc.DisplayConfig = cfg`) | partiell, **nur `{metrics}`, KEIN Spread** | **AKTIVER Datenverlust — Fokus** |
| `PUT /api/compare/presets/{id}` | Objekt-Level-RMW (ganzer Blob erhalten wenn nil) | **voll** (`...original.display_config`) | abgesichert nur durch Client-Disziplin |

Der Location-Dialog (`WeatherConfigDialog.svelte:126-133`) baut `config = { metrics: [...] }`
ohne `...currentConfig` und reicht ihn 1:1 durch (`routes/locations/+page.svelte:99`). In
Kombination mit dem Backend-Blind-Replace geht **jeder andere `display_config`-Key der Location
beim Speichern verloren** (z.B. `region`, `theme`, `channel_layouts`, `ideal_ranges`).

## Related Files

| File | Relevance |
|------|-----------|
| `internal/handler/weather_config.go:37-82` | `PutTripWeatherConfigHandler` — Feld-Merge-Vorbild (#1151), Schleife Z.64-69 |
| `internal/handler/weather_config.go:108-142` | `PutLocationWeatherConfigHandler` — **Blind-Replace Z.132**, zu fixen |
| `internal/handler/compare_preset.go:255-427` | `UpdateComparePresetHandler` — Objekt-Level-RMW, DisplayConfig Z.288-290 |
| `internal/handler/trip.go:~170, 209-243` | Trip-Update — **4 identische inline Merge-Loops** (Aggregation Z.214, WeatherConfig Z.222, DisplayConfig Z.230, ReportConfig Z.240) |
| `internal/model/trip.go:106-109` | `DisplayConfig`, `Aggregation`, `WeatherConfig`, `ReportConfig` — alle `map[string]interface{}` |
| `internal/model/location.go:16` | `DisplayConfig map[string]interface{}` |
| `internal/model/compare_preset.go:48` | `DisplayConfig map[string]interface{}` |
| `internal/store/location.go:61,80` | `LoadLocation` / `SaveLocation` (Value-Receiver, kein Merge) |
| `internal/store/trip.go:92,127` | `LoadTrip` / `SaveTrip` (Pointer seit #1244, normalize, kein Key-Merge) |
| `internal/store/compare_preset.go:58,122` | `LoadComparePresets` / `SaveComparePresets` (ganze Slice, kein Single-Get) |
| `internal/handler/weather_config_1151_test.go:19` | `TestPutTripWeatherConfigMergesDisplayConfig` — vorhandener Struktur-Test, **nur Trip** |
| `internal/handler/weather_config_test.go:122-141` | `TestPutLocationWeatherConfig` — prüft nur `!= nil`, **keine Preservation** |
| `frontend/src/lib/components/WeatherConfigDialog.svelte:126-133` | Location-Client — sendet **nur `{metrics}`**, kein Spread |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte:429-446` | Trip-Client — spreadet `...trip.display_config` |
| `frontend/src/lib/components/compare/compareEditorSave.ts:71-162` | ComparePreset-Client — voller Round-Trip-Spread |

## Existing Patterns

- **Vorbild feldweiser Merge (korrekt, #1151):** `weather_config.go:64-69`
  ```go
  if trip.DisplayConfig == nil { trip.DisplayConfig = map[string]interface{}{} }
  for k, v := range cfg { trip.DisplayConfig[k] = v }
  ```
- **Dieselbe Schleife 4× in `trip.go`** (Z.214/222/230/240) für die vier Opaque-Maps —
  das ist die zu konsolidierende Duplizierung.
- **Kein bestehender Merge-Helfer** für Config-Maps. Kein `internal/util`-Paket.
  (`mergeFallback` in `provider/openmeteo/provider.go:448` ist thematisch unabhängig.)
- **Anti-Pattern dokumentiert:** `operations_playbook.md:152-174` — „Read-Modify-Write mit
  Merge, niemals Replace"; der Location-Fall ist dort wörtlich das verbotene Beispiel.

## Dependencies

- **Upstream:** `internal/model/*` (die drei `map[string]interface{}`-Felder), `internal/store/*`
  (Load/Save-Signaturen unterscheiden sich je Entity — Location Value, Trip Pointer, Preset Slice).
- **Downstream:** Frontend-Clients (siehe Tabelle). Verhaltensänderung am Location-Backend ist
  **kompatibel** zum vorhandenen Client (der sendet ohnehin nur `{metrics}`, will die anderen
  Keys nicht löschen). ComparePreset-Umstellung auf Feld-Merge ist kompatibel, weil der Client
  bereits den vollen Blob schickt (Merge == Replace im Happy Path, plus Defense-in-Depth).

## Zwei Ebenen der Aufgabe (Design-Achse)

1. **Reines Refactoring (verhaltensneutral):** `mergeMap(dst, src map[string]interface{})`-Helfer
   extrahieren, die 5 inline-Loops ersetzen (4× trip.go + 1× weather_config.go Trip-Pfad).
2. **Verhaltensänderung (Datenverlust-Fix):** Location-Handler auf feldweisen Merge umstellen
   (**behebt den aktiven Bug**); optional ComparePreset-`display_config` ebenfalls auf feldweisen
   Merge (Defense-in-Depth, kein aktiver Bug dort).

## Risks & Considerations

- **Store-Heterogenität:** Der Helfer arbeitet auf Map-Ebene und ist store-agnostisch. Aber der
  **iterierende Struktur-Test muss über die echten HTTP-Handler** laufen (jeder mit eigenem
  Store-Pfad: Value / Pointer / Slice), nicht nur über die Helfer-Funktion — sonst fängt er
  einen neuen Endpoint nicht, der den Helfer umgeht.
- **Key-Löschung:** Feldweiser Merge kann per Definition keinen `display_config`-Key mehr löschen
  (nur setzen/überschreiben). Für Trip ist das seit #1151 akzeptiert. Für Location/Preset klären,
  ob Key-Löschung ein genutztes Feature ist (Erwartung: nein).
- **ComparePreset-Reichweite (offene PO-Entscheidung):** display_config auf Feld-Merge umstellen
  ja/nein — erweitert Blast Radius, ist aber der einzige Weg, den Struktur-Test sauber über alle
  3 Endpoints iterieren zu lassen. In `/20-analyse` mit Empfehlung vorlegen.
- **Trip-Doppel-PUT:** Trip nutzt zwei Endpoints (`/weather-config` + `/trips/{id}`), beide mergen
  bereits. Nicht regredieren.
- **Datenverlust-Schutz-Pflicht (CLAUDE.md):** Schema-relevante Dateien (`model/*.go`, `store.go`)
  lösen den Pre-Snapshot-Hook aus; Bestandsdaten müssen erhalten bleiben. Roundtrip-Test Pflicht.
- **Test-Lücke Location:** aktuell kein einziger Merge/Preserve-Test — der wird in TDD-RED zum
  Bug-Repro (rot vor Fix, grün nach Fix, aus Nutzersicht: „Metriken speichern löscht Region").

## Existing Specs / Referenzen

- `docs/reference/api_contract.md:759-797` — Weather-Config-Endpoints, benennt #1159 explizit
  als Folge-Issue für Location/Subscription-Blind-Replace.
- `docs/reference/operations_playbook.md:152-174` — Read-Modify-Write-Merge-Prinzip + Anti-Pattern.
- `docs/project/known_issues.md:288-336` — BUG-DATALOSS-GR221 (#102), Lehre: Backend-Merge als
  Defense-in-Depth (#99).

---

## Analysis

### Type
Bug + Rework (aktiver Datenverlust am Location-Endpoint + strukturelle Konsolidierung der Klasse).

### Technical Approach

**1. Ein gemeinsamer Helfer.** Alle betroffenen Maps sind `map[string]interface{}`. Neue Datei
`internal/handler/config_merge.go`, Paket `handler` (kein neues `internal/util`-Paket nötig — alle
Aufrufer liegen in `handler`):

```go
// mergeConfigMap führt Read-Modify-Write feldweise aus: Keys aus src überschreiben/ergänzen dst,
// nicht mitgesendete Keys von dst bleiben erhalten. nil-sicher. Ersetzt die 5 inline-Loops.
func mergeConfigMap(dst, src map[string]interface{}) map[string]interface{} {
    if src == nil { return dst }
    if dst == nil { dst = map[string]interface{}{} }
    for k, v := range src { dst[k] = v }
    return dst
}
```

Repliziert exakt die Semantik der vorhandenen `#1151`-Schleife (nil-Init + Key-Copy).

**2. Verhaltensneutrales Refactoring** (bestehende Tests bleiben grün) — 5 inline-Loops ersetzen:
- `weather_config.go:64-69` (Trip-Pfad) → `trip.DisplayConfig = mergeConfigMap(trip.DisplayConfig, cfg)`
- `trip.go:214/222/230/240` (Aggregation, WeatherConfig, DisplayConfig, ReportConfig) → je ein Helfer-Call.

**3. Datenverlust-Fix** (Verhaltensänderung, client-kompatibel):
- `weather_config.go:132` (Location) → `loc.DisplayConfig = mergeConfigMap(loc.DisplayConfig, cfg)`.
  `loc` wird bereits per `LoadLocation` geladen — nur die Zuweisung tauschen. Behebt den aktiven Bug.

**4. ComparePreset** — offene PO-Entscheidung (siehe unten). Surgical nur für `display_config`, NICHT
die ~20 anderen object-level-preserve-Felder anfassen (out of scope, viele sind Skalare).

**5. Struktur-Test** (table-driven, über die echten HTTP-Handler): pro Endpoint Seed mit ≥2
display_config-Keys → Teil-PUT (ein Key weggelassen) → reload → weggelassener Key überlebt UND
gesendeter Key aktualisiert. Läuft über httptest gegen die realen Handler (jeder mit eigenem
Store-Pfad: Location value-save / Trip pointer-save / Preset slice-save), nicht gegen die
Helfer-Funktion isoliert — sonst fängt er einen Endpoint nicht, der den Helfer umgeht.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/handler/config_merge.go` | CREATE | `mergeConfigMap`-Helfer (~12 LoC) |
| `internal/handler/weather_config.go` | MODIFY | Trip-Loop → Helfer; Location Blind-Replace → Helfer (Fix) |
| `internal/handler/trip.go` | MODIFY | 4 inline-Loops → Helfer-Calls |
| `internal/handler/compare_preset.go` | MODIFY | (bedingt) display_config → Helfer statt object-level-preserve |
| `internal/handler/config_merge_structure_test.go` | CREATE | table-driven Struktur-Test über 3 Endpoints (~100 LoC) |
| `internal/handler/weather_config_test.go` | MODIFY | Location-Preserve-Assertion nachrüsten (oder via Struktur-Test) |

### Scope Assessment
- Files: 4 Source + 1-2 Test
- Estimated LoC: Source ~+15/-16 (netto ≈ 0), Test ~+100 → gesamt ~+115 (unter 250-Limit)
- Risk Level: **MEDIUM** — Datenpersistenz-Schreibpfade, aber Refactoring-Teile mechanisch/neutral,
  Location-Fix client-kompatibel.

### Dependencies / Sequencing
- **Kollisionsrisiko mit #1250:** aktiver Workflow `feat-1250-s4-trip-konvergenz` (Validation) berührt
  `trip.go`; Issue-Kommentar 2026-07-13 verweist auf „#1250 Scheibe 6 (gemeinsamer PUT-Merge-Pfad)".
  Andere Ebene (Go-Backend-Helfer vs. FE `buildComparePresetSavePayload`), aber evtl. dieselben Dateien.
  Integrationspunkt ist `origin/main`; vor Commit sauber rebasen, `trip.go`-Merge prüfen.

### Grenzen / ehrliche Einordnung
- „Neue Endpoints fallen **automatisch** durch" (Issue-Wortlaut) erreicht ein table-driven Test
  **nicht** buchstäblich — er deckt nur die 3 gelisteten Endpoints. Ein wirklich automatischer
  Wächter bräuchte Reflection/Registry oder ein Grep-Gate auf `.DisplayConfig = <body>`-Zuweisungen.
  Empfehlung: table-driven über die 3 realen Endpoints (fängt Regression der bekannten Klasse);
  **kein** neues Grep-Gate (Regel-Budget — neues Gate bräuchte Prüfdatum, geringer Fang-Nachweis).
- Feldweiser Merge kann per Definition keinen display_config-Key mehr **löschen** (nur setzen).
  Für Trip seit #1151 akzeptiert; für Location/Preset kein genutzter Lösch-Pfad bekannt.

### Open Questions
- [x] **ComparePreset-Reichweite:** PO-Entscheidung 2026-07-15 → **JA**, `display_config` auf
  feldweisen Merge umstellen (`compare_preset.go:288-290`). Damit laufen alle 3 Endpoints über
  `mergeConfigMap` und der Struktur-Test iteriert einheitlich über Trip + Location + ComparePreset.
  Nur `display_config` — die ~20 anderen object-level-preserve-Felder bleiben unberührt.
