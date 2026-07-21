---
entity_id: issue_458_compare_preset_backend
type: module
created: 2026-05-30
updated: 2026-05-30
status: implemented
version: "1.0"
issue: 458
tags: [compare, preset, backend, go, crud, api, storage]
---

# Issue #458 — Orts-Vergleich: Compare-Preset Backend (CRUD-Endpoints + DB-Modell)

## Approval

- [ ] Approved

## Purpose

Führt das neue `ComparePreset`-Entity im Go-Backend ein: ein persistiertes Konfigurations-Objekt, das Standorte, Zeitfenster, Aktivitätsprofil, Versandplanung und Empfänger für einen automatischen Orts-Vergleichs-Report bündelt. Fünf REST-Endpoints (List, Create, Update, Delete, Send-Stub) ermöglichen dem Frontend aus Epic #438, Presets vollständig zu verwalten — ohne dieses Backend können Presets im Compare-Wizard nicht gespeichert oder abgerufen werden.

## Source

**Neue Dateien (Go-Backend):**
- `internal/model/compare_preset.go` — `ComparePreset`-Struct (~25 LoC)
- `internal/handler/compare_preset.go` — 5 Handler-Funktionen + `newComparePresetID()` + `validateComparePreset()` (~170 LoC)
- `internal/handler/compare_preset_test.go` — 15 Testfälle (~250 LoC)

**Geänderte Dateien (Go-Backend):**
- `internal/store/store.go` — +2 Methoden: `LoadComparePresets`, `SaveComparePresets` (~55 LoC)
- `cmd/server/main.go` — 5 neue Routen registrieren (~8 LoC)

> **Schicht-Hinweis:** Reine Go-API-Änderung (`internal/`, `cmd/`). Python-Backend und SvelteKit-Frontend bleiben unberührt. Persistenz erfolgt als JSON-Array in `data/users/{userId}/compare_presets.json` — analog zu `metric_presets.json` (Referenzmuster für diesen Issue).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ActivityProfile`, `IsValidProfile()` (`internal/compare/types.go`) | intern | Validierung des `profil`-Feldes — `compare_preset.go` importiert `internal/compare` |
| `UserIDFromContext`, `ContextWithUserID` (`internal/middleware/auth.go`) | intern | User-Isolation: Handler liest `user_id` aus dem Auth-Kontext, setzt sie server-seitig |
| `github.com/go-chi/chi/v5` | extern | `chi.URLParam(r, "id")` für parametrisierte Routen `{id}` |
| `writeJSON()` (`internal/handler/metric_preset.go`) | intern | Package-private Hilfsfunktion, wird innerhalb des `handler`-Packages wiederverwendet |
| `newPresetID()` (`internal/handler/metric_preset.go`) | intern | Referenz-Muster; `newComparePresetID()` nutzt Präfix `"cp-"` statt `"p-"` um ID-Kollisionen zu vermeiden |
| `internal/store/store.go` — bestehende Store-Struktur | intern | `LoadComparePresets` / `SaveComparePresets` werden als neue Methoden additiv ergänzt |

## Implementation Details

### §1 `internal/model/compare_preset.go` — Neues Struct

```go
package model

import "time"

type ComparePreset struct {
    ID                   string     `json:"id"`                                    // "cp-{hex}", auto-generated
    Name                 string     `json:"name"`
    UserID               string     `json:"user_id"`                               // gesetzt durch Handler aus Auth-Kontext
    LocationIDs          []string   `json:"location_ids"`
    Schedule             string     `json:"schedule"`                              // "daily" | "weekly" | "manual"
    Profil               string     `json:"profil"`                                // ActivityProfile-String, validiert via IsValidProfile()
    HourFrom             int        `json:"hour_from"`                             // 0..23
    HourTo               int        `json:"hour_to"`                               // 0..23, >= HourFrom
    Empfaenger           []string   `json:"empfaenger"`                            // E-Mail-Adressen
    LetzterVersand       *time.Time `json:"letzter_versand,omitempty"`             // server-managed, gesetzt durch /send
    TopOrtLetzterVersand *string    `json:"top_ort_letzter_versand,omitempty"`     // server-managed, gesetzt durch /send
    CreatedAt            time.Time  `json:"created_at"`                            // gesetzt bei Erstellung
}
```

`Profil` wird als `string` gespeichert (kein Import von `internal/compare` im Model), um Import-Zyklen zu vermeiden — `internal/compare` importiert `internal/model`. Validierung via `compare.IsValidProfile()` findet nur im Handler statt.

### §2 `internal/store/store.go` — Neue Store-Methoden

```go
func (s *Store) comparePresetsFile() string {
    return filepath.Join(s.DataDir, "users", s.UserID, "compare_presets.json")
}

func (s *Store) LoadComparePresets() ([]model.ComparePreset, error) {
    data, err := os.ReadFile(s.comparePresetsFile())
    if os.IsNotExist(err) {
        return []model.ComparePreset{}, nil
    }
    if err != nil {
        return nil, err
    }
    var presets []model.ComparePreset
    if err := json.Unmarshal(data, &presets); err != nil {
        return nil, err
    }
    if presets == nil {
        presets = []model.ComparePreset{}
    }
    return presets, nil
}

func (s *Store) SaveComparePresets(presets []model.ComparePreset) error {
    dir := filepath.Join(s.DataDir, "users", s.UserID)
    if err := os.MkdirAll(dir, 0755); err != nil {
        return err
    }
    if presets == nil {
        presets = []model.ComparePreset{}
    }
    data, err := json.MarshalIndent(presets, "", "  ")
    if err != nil {
        return err
    }
    return os.WriteFile(s.comparePresetsFile(), data, 0644)
}
```

Kein einzelner `LoadComparePreset`-Accessor — Handler lädt die gesamte Liste und filtert nach `id` (entspricht dem `metric_preset`-Muster).

### §3 `internal/handler/compare_preset.go` — 5 Handler + Hilfsfunktionen

**ID-Generierung:**
```go
func newComparePresetID() string {
    b := make([]byte, 8)
    rand.Read(b)
    return "cp-" + hex.EncodeToString(b)
}
```
Präfix `"cp-"` verhindert Kollisionen mit `"p-"`-IDs aus `newPresetID()` (beide im gleichen Package).

**Validierung:**
```go
func validateComparePreset(p model.ComparePreset) error {
    if strings.TrimSpace(p.Name) == "" {
        return errors.New("name is required")
    }
    if p.Schedule != "daily" && p.Schedule != "weekly" && p.Schedule != "manual" {
        return errors.New("schedule must be daily, weekly, or manual")
    }
    if !compare.IsValidProfile(compare.ActivityProfile(p.Profil)) {
        return errors.New("profil is not a valid activity profile")
    }
    if p.HourFrom < 0 || p.HourFrom > 23 {
        return errors.New("hour_from must be 0..23")
    }
    if p.HourTo < 0 || p.HourTo > 23 {
        return errors.New("hour_to must be 0..23")
    }
    if p.HourTo < p.HourFrom {
        return errors.New("hour_to must be >= hour_from")
    }
    for _, e := range p.Empfaenger {
        if !strings.Contains(e, "@") {
            return fmt.Errorf("empfaenger entry %q is not a valid email address", e)
        }
    }
    return nil
}
```

**Endpoint-Übersicht:**

| Method | Handler | Verhalten |
|--------|---------|-----------|
| `GET /api/compare/presets` | `ListComparePresetsHandler` | Lädt alle Presets des Users → 200 + `[]ComparePreset` (leeres Array wenn keine vorhanden) |
| `POST /api/compare/presets` | `CreateComparePresetHandler` | Dekodiert Body, setzt `ID = newComparePresetID()`, `UserID` aus Auth-Kontext, `CreatedAt = time.Now()`, coerced `nil LocationIDs → []`, validiert, speichert → 201 + `ComparePreset` |
| `PUT /api/compare/presets/{id}` | `UpdateComparePresetHandler` | Lädt Liste, findet Preset per `id` (404 wenn nicht gefunden), übernimmt `UserID` + `CreatedAt` aus dem Original (nicht aus dem Body), coerced `nil LocationIDs → []`, validiert, ersetzt → 200 + `ComparePreset` |
| `DELETE /api/compare/presets/{id}` | `DeleteComparePresetHandler` | Lädt Liste, findet Preset (404 wenn nicht gefunden), entfernt, speichert → 204 |
| `POST /api/compare/presets/{id}/send` | `SendComparePresetHandler` | Lädt Liste, prüft ob `id` existiert (404 wenn nicht), gibt sofort `{"status":"queued"}` zurück → 200 (Stub; echte Logik in #461) |

**PUT-Sonderregeln:**
- `UserID` und `CreatedAt` werden aus dem bestehenden Datensatz übernommen, nie aus dem Request-Body.
- `LetzterVersand` und `TopOrtLetzterVersand` werden aus dem Body ignoriert — diese Felder sind server-managed und werden ausschließlich durch den `/send`-Endpoint gesetzt.

### §4 `cmd/server/main.go` — Routen registrieren

```go
r.Get("/api/compare/presets",             handler.ListComparePresetsHandler(store))
r.Post("/api/compare/presets",            handler.CreateComparePresetHandler(store))
r.Put("/api/compare/presets/{id}",        handler.UpdateComparePresetHandler(store))
r.Delete("/api/compare/presets/{id}",     handler.DeleteComparePresetHandler(store))
r.Post("/api/compare/presets/{id}/send",  handler.SendComparePresetHandler(store))
```

Alle fünf Routen liegen im authentifizierten Block (Cookie-Auth via Middleware), analog zu `/api/metric-presets`.

### §5 LoC-Budget

| Datei | Änderung | LoC |
|-------|---------|-----|
| `internal/model/compare_preset.go` | NEU — Struct | ~25 |
| `internal/store/store.go` | +2 Methoden | ~55 |
| `internal/handler/compare_preset.go` | NEU — 5 Handler + Helpers | ~170 |
| `internal/handler/compare_preset_test.go` | NEU — 15 Testfälle | ~250 |
| `cmd/server/main.go` | +5 Routen | ~8 |
| **Gesamt** | | **~508 LoC** |

LoC-Override vor Implementierungsstart setzen:
```bash
python3 .claude/hooks/workflow.py set-field loc_limit_override 550
```

## Expected Behavior

- **Input:** Authenticated HTTP-Requests gegen die fünf Endpoints; Body-JSON für POST/PUT enthält `ComparePreset`-Felder (ohne server-managed Felder).
- **Output:**
  - `GET` → 200 mit JSON-Array aller Presets des Users (leer wenn keine).
  - `POST` → 201 mit dem neu erstellten Preset inkl. auto-generierter `id`, `user_id` aus Auth-Kontext, `created_at`.
  - `PUT` → 200 mit dem aktualisierten Preset; `user_id` + `created_at` bleiben erhalten.
  - `DELETE` → 204 ohne Body.
  - `POST /{id}/send` → 200 mit `{"status":"queued"}`.
  - Alle Endpoints → 404 wenn `{id}` nicht in der Datei des Users existiert.
  - Alle Endpoints → 400 bei Validierungsfehler mit beschreibender Fehlermeldung.
- **Side effects:**
  - `data/users/{userId}/compare_presets.json` wird bei Create/Update/Delete vollständig neu geschrieben.
  - Kein Preset eines Users ist für einen anderen User sichtbar oder manipulierbar (User-Isolation via Auth-Kontext).

## Acceptance Criteria

**AC-1:** Given ein authentifizierter User ohne bestehende Presets / When `GET /api/compare/presets` aufgerufen wird / Then antwortet der Endpoint mit HTTP 200 und einem leeren JSON-Array `[]`
  - Test: (populated after /tdd-red)

**AC-2:** Given ein authentifizierter User und ein valider POST-Body mit Name, schedule="daily", profil="SUMMER_TREKKING", hour_from=6, hour_to=18, empfaenger=["a@b.com"] / When `POST /api/compare/presets` aufgerufen wird / Then antwortet der Endpoint mit HTTP 201 und einem JSON-Objekt, in dem `id` mit Präfix "cp-" auto-generiert ist, `user_id` aus dem Auth-Kontext stammt (nicht aus dem Body), und alle übergebenen Felder korrekt persistiert sind
  - Test: (populated after /tdd-red)

**AC-3:** Given ein POST-Body ohne `name`-Feld (oder leerem String) / When `POST /api/compare/presets` aufgerufen wird / Then antwortet der Endpoint mit HTTP 400
  - Test: (populated after /tdd-red)

**AC-4:** Given ein POST-Body mit `schedule="monatlich"` (ungültig) / When `POST /api/compare/presets` aufgerufen wird / Then antwortet der Endpoint mit HTTP 400
  - Test: (populated after /tdd-red)

**AC-5:** Given ein POST-Body mit `profil="UNBEKANNT"` (kein Wert, der `compare.IsValidProfile()` besteht) / When `POST /api/compare/presets` aufgerufen wird / Then antwortet der Endpoint mit HTTP 400
  - Test: (populated after /tdd-red)

**AC-6:** Given ein POST-Body mit `hour_from=14` und `hour_to=10` (hour_to < hour_from) / When `POST /api/compare/presets` aufgerufen wird / Then antwortet der Endpoint mit HTTP 400
  - Test: (populated after /tdd-red)

**AC-7:** Given ein POST-Body mit `empfaenger=["keine-email-adresse"]` (kein `@`-Zeichen) / When `POST /api/compare/presets` aufgerufen wird / Then antwortet der Endpoint mit HTTP 400
  - Test: (populated after /tdd-red)

**AC-8:** Given ein bestehendes Preset mit `id="cp-abc"`, `created_at="2026-01-01T00:00:00Z"`, `user_id="user1"`, und einem PUT-Body mit geändertem `name` und `schedule` / When `PUT /api/compare/presets/cp-abc` aufgerufen wird / Then antwortet der Endpoint mit HTTP 200, das Preset enthält den neuen `name` und `schedule`, `created_at` und `user_id` sind byte-identisch zum Original (nicht aus dem Body übernommen)
  - Test: (populated after /tdd-red)

**AC-9:** Given eine Preset-ID die nicht existiert / When `PUT /api/compare/presets/{id}` aufgerufen wird / Then antwortet der Endpoint mit HTTP 404
  - Test: (populated after /tdd-red)

**AC-10:** Given ein bestehendes Preset mit `id="cp-del"` / When `DELETE /api/compare/presets/cp-del` aufgerufen wird / Then antwortet der Endpoint mit HTTP 204, und ein anschließendes `GET /api/compare/presets` liefert ein Array ohne dieses Preset
  - Test: (populated after /tdd-red)

**AC-11:** Given eine Preset-ID die nicht existiert / When `DELETE /api/compare/presets/{id}` aufgerufen wird / Then antwortet der Endpoint mit HTTP 404
  - Test: (populated after /tdd-red)

**AC-12:** Given ein bestehendes Preset mit `id="cp-send"` / When `POST /api/compare/presets/cp-send/send` aufgerufen wird / Then antwortet der Endpoint mit HTTP 200 und Body `{"status":"queued"}` (Stub — keine E-Mail wird versendet)
  - Test: (populated after /tdd-red)

**AC-13:** Given eine Preset-ID die nicht existiert / When `POST /api/compare/presets/{id}/send` aufgerufen wird / Then antwortet der Endpoint mit HTTP 404
  - Test: (populated after /tdd-red)

**AC-14:** Given User A hat Preset `cp-a1` angelegt und User B ist authentifiziert / When User B `GET /api/compare/presets` aufruft / Then enthält die Response das Preset `cp-a1` nicht (User-Isolation, jede User-Datei ist getrennt)
  - Test: (populated after /tdd-red)

## Known Limitations

- **/send ist ein Stub:** `POST /{id}/send` gibt sofort `{"status":"queued"}` zurück und versendet keine E-Mail. Die tatsächliche Versandlogik (Compare-Engine aufrufen, Mail schreiben, `letzter_versand` setzen) wird in Issue #461 implementiert.
- **Keine Partial-Update-Semantik bei PUT:** PUT ist ein Full-Replace des editierbaren Teils des Presets — alle Felder außer `user_id`, `created_at` sowie server-managed `letzter_versand`/`top_ort_letzter_versand` müssen im Body mitgegeben werden. Ein PATCH-Endpoint ist nicht vorgesehen.
- **Empfänger-Validierung nur auf `@`-Enthaltensein:** Es wird keine vollständige RFC-5322-E-Mail-Adress-Validierung durchgeführt. Technisch ungültige, aber `@`-haltige Adressen werden akzeptiert und führen erst beim Versand zu einem Fehler.
- **Kein Limit für Preset-Anzahl:** Es gibt keine serverseitige Begrenzung, wie viele Presets ein User anlegen kann.
- **location_ids ohne Referenz-Validierung:** Der Handler prüft nicht, ob die übergebenen `location_ids` als Locations in `data/users/{userId}/locations.json` existieren. Ungültige IDs führen erst beim Versand-Lauf in #461 zu einem Fehler.

## Changelog

- 2026-05-30: IMPLEMENTED. ComparePreset-Entity im Go-Backend fertiggestellt: internal/model/compare_preset.go (Struct ~25 LoC), internal/store/store.go (+2 Methoden ~55 LoC), internal/handler/compare_preset.go (5 Handler ~170 LoC), cmd/server/main.go (+5 Routen ~8 LoC). Alle 14 AC erfüllt. Backend-Foundation für #456 (Auto-Briefings) complete.
- 2026-05-30: Initial spec — Issue #458. Neues `ComparePreset`-Entity im Go-Backend mit 5 CRUD-Endpoints (List/Create/Update/Delete/Send-Stub); Storage als `compare_presets.json`; User-Isolation via Auth-Kontext; Profil als String gespeichert (Import-Zyklus-Vermeidung); /send ist Stub für #461. ~508 LoC, LoC-Override auf 550 erforderlich. 14 Acceptance Criteria im AC-N-Format.
