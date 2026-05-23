---
entity_id: issue_341_group_backend
type: module
created: 2026-05-22
updated: 2026-05-22
status: draft
version: "1.0"
issue: 341
tags: [compare, groups, backend, go, store, migration, foundation]
---

# Issue #341 — Compare-Backend: Group-Entity + /api/groups CRUD + Location.group_id

## Approval

- [ ] Approved

## Purpose

Führt eine echte `Group`-Entity (`id, name, default_profile, order`) ins Go-Backend ein, ergänzt
`Location.group_id` als Fremdschlüssel, liefert CRUD-Endpoints `/api/groups` sowie ein neues
`PATCH /api/locations/{id}` zum Verschieben eines Orts in eine andere Gruppe. Eine verlustfreie
Lazy-Migration überführt die bestehenden Freitext-`group`-Strings einmalig in Group-Objekte. Dieses
Issue ist das **blockierende Fundament** für #301 (Frontend) und Teil von Epic #246. Reines Backend —
kein Frontend-Konsum in diesem Issue.

## Source

- **NEU:** `internal/model/group.go` — `Group`-Struct
- **EDIT:** `internal/model/location.go` — `Location` um `GroupID *string` (additiv, omitempty); bestehendes `Group *string` bleibt während der Transition erhalten
- **EDIT:** `internal/store/store.go` — single-file Group-Persistenz (`data/users/{uid}/groups.json`): `GroupsFile`, `LoadGroups`, `SaveGroup`, `DeleteGroup`, `saveGroups`; Lazy-Migration in `LoadGroups`
- **NEU:** `internal/handler/group.go` — Handler-Set: `GroupsHandler`, `CreateGroupHandler`, `UpdateGroupHandler`, `DeleteGroupHandler`
- **EDIT:** `internal/handler/location.go` — `PatchLocationHandler` (partielles Merge, mind. `group_id`)
- **EDIT:** `cmd/server/main.go` — Routen `GET/POST/PATCH/DELETE /api/groups` + `PATCH /api/locations/{id}`
- **NEU:** `internal/handler/group_test.go`, `internal/store/group_migration_test.go` — Go-Tests (echtes Dateisystem via `t.TempDir()`, keine Mocks)

> **Schicht-Zuordnung:** Ausschließlich Go-API (`internal/`, `cmd/`). Verifiziert: Der Python-Core
> liest das Location-`group`-Feld NICHT (keine `locations/`-/`.group`-Zugriffe in `src/`; Compare-Engine
> ist Go-nativ, #250). Daher kein Python-Schema-Rework. Frontend-Konsum (`group_id` im Type, Group-UI)
> ist Gegenstand von #301.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Location` (`internal/model/location.go`) | intern | Basis-Struct; additiv um `GroupID *string` erweitert |
| `store.Store` (`internal/store/store.go`) | intern | Persistenz; single-file-Muster aus Subscriptions/Presets als Vorbild |
| `store.LoadLocations` / `store.SaveLocation` | intern | Migration backfillt `group_id`; DELETE-Group setzt `group_id=null` (Read-Modify-Write) |
| `middleware.UserIDFromContext` / `WithUser()` | intern | User-Scoping in jedem Handler |
| `toKebab()` (`internal/handler/location.go`) | intern | ID-Generierung aus Name |
| `go-chi/chi/v5` | extern | Router, `chi.URLParam` |
| `data_schema_backup.py`-Hook | intern | Pre-Snapshot bei Edit an `store.go`/Model (BUG-DATALOSS-GR221) |

## Implementation Details

### §1 `internal/model/group.go` — Group-Struct (NEU)

```go
package model

type Group struct {
    ID             string  `json:"id"`
    Name           string  `json:"name"`
    DefaultProfile *string `json:"default_profile,omitempty"` // wintersport|wandern|summer-trekking|allgemein
    Order          int     `json:"order"`
}
```

### §2 `internal/model/location.go` — group_id (additiv)

```go
type Location struct {
    // ... bestehende Felder unverändert ...
    Group   *string `json:"group,omitempty"`     // Freitext (Legacy, bleibt während Transition)
    GroupID *string `json:"group_id,omitempty"`  // NEU: FK auf Group.ID; nil = "Ungruppiert"
    // ...
}
```

`Group` (Freitext) bleibt nach der Migration als Read-Only-Spur erhalten (nicht weiter gepflegt);
`group_id` ist ab Migration die maßgebliche Quelle. Beide `omitempty` → bestehende JSONs ohne diese
Felder bleiben valide.

### §3 `internal/store/store.go` — Group-Persistenz (single-file)

Datei `data/users/{uid}/groups.json`, Wrapper `{"groups":[...]}` (analog Subscriptions).

```go
func (s *Store) groupsFile() string { return filepath.Join(s.DataDir, "users", s.UserID, "groups.json") }

func (s *Store) LoadGroups() ([]model.Group, error)   // siehe §4 (inkl. Lazy-Migration)
func (s *Store) SaveGroup(g model.Group) error         // Upsert per ID, dann saveGroups
func (s *Store) DeleteGroup(id string) error           // filtert ID raus, dann saveGroups
func (s *Store) saveGroups(gs []model.Group) error     // MkdirAll + MarshalIndent(wrapper)
```

`LoadGroups` gibt bei fehlender Datei NICHT sofort `[]` zurück, sondern triggert die Migration (§4).
Leere Resultate werden als `{"groups":[]}` persistiert (Migrations-Marker → keine Re-Derivation).

### §4 Lazy-Migration (in `LoadGroups`, einmalig & idempotent)

```
Wenn groups.json existiert:
    → laden, nach Order sortiert zurückgeben (keine Migration).
Wenn groups.json NICHT existiert (= noch nie migriert):
    1. Alle Locations laden.
    2. Distinkte, nicht-leere Location.Group-Strings sammeln (Reihenfolge: alphabetisch).
    3. Pro String ein Group-Objekt: id = toKebab(name) (bei Slug-Kollision Suffix -2/-3…),
       name = String, order = Index (0..n), default_profile = nil.
    4. groups.json schreiben (auch leer → {"groups":[]}).
    5. group_id-Backfill: jede Location mit passendem Group-String bekommt GroupID = group.ID,
       danach SaveLocation (Read-Modify-Write: nur group_id ergänzt, alle anderen Felder erhalten).
    6. Migrierte Gruppen (sortiert nach Order) zurückgeben.
```

Idempotenz garantiert durch Existenz von `groups.json` nach Schritt 4 — erneutes `LoadGroups`
nimmt den ersten Zweig. Slug-Kollisionen werden dedupliziert.

### §5 `internal/handler/group.go` — Handler-Set (NEU)

Muster identisch zu `subscription.go`/`location.go` (`WithUser`, JSON-Fehler `{"error":...}`):

- `GroupsHandler` — `GET /api/groups` → 200, Liste sortiert nach `order`.
- `CreateGroupHandler` — `POST /api/groups`: ID aus `toKebab(name)` wenn leer; `name` Pflicht (sonst 400 `validation_error`); `order` = `max(order)+1` wenn 0/ungesetzt; persistieren; 201 + Objekt.
- `UpdateGroupHandler` — `PATCH /api/groups/{id}`: existierende Group laden (404 wenn fehlt); nur im Body **vorhandene** Schlüssel mergen (`name`, `default_profile`, `order`); 200 + Objekt. Body via `map[string]json.RawMessage` (Schlüssel-Präsenz statt Null-Heuristik).
- `DeleteGroupHandler` — `DELETE /api/groups/{id}`: Group entfernen; **alle Locations mit `group_id == id` auf `group_id = nil` setzen** (Read-Modify-Write je Location); 204.

### §6 `internal/handler/location.go` — PatchLocationHandler (NEU)

`PATCH /api/locations/{id}`: existierende Location laden (404 wenn fehlt). Body als
`map[string]json.RawMessage` dekodieren; nur vorhandene Schlüssel anwenden. Mindestens `group_id`:

- Schlüssel `group_id` vorhanden mit String → `existing.GroupID = &val`.
- Schlüssel `group_id` vorhanden mit `null` → `existing.GroupID = nil` (ent-gruppieren).
- Schlüssel absent → unverändert.

Danach `SaveLocation(existing)` (vollständiges Merge — keine anderen Felder gehen verloren,
`CreatedAt` bleibt). 200 + Objekt. Validierung bleibt erfüllt, da nur das geladene, valide Objekt
verändert wird.

### §7 `cmd/server/main.go` — Routen

```go
r.Get("/api/groups", handler.GroupsHandler(s))
r.Post("/api/groups", handler.CreateGroupHandler(s))
r.Patch("/api/groups/{id}", handler.UpdateGroupHandler(s))
r.Delete("/api/groups/{id}", handler.DeleteGroupHandler(s))
r.Patch("/api/locations/{id}", handler.PatchLocationHandler(s))
```

(Bestehende `PUT /api/locations/{id}` bleibt unverändert; PATCH ist additiv.)

## Expected Behavior

- **Input:** JSON-Requests gegen `/api/groups` (List/Create/Patch/Delete) und `PATCH /api/locations/{id}`.
- **Output:** Group-JSON bzw. aktualisierte Location-JSON; Standard-Statuscodes (200/201/204/400/404/500).
- **Side effects:** `groups.json` pro User; einmalige Migration beschreibt `groups.json` + backfillt
  `group_id` in Location-JSONs; `DELETE group` mutiert betroffene Location-JSONs (group_id→null).

## Acceptance Criteria

- **AC-1:** Given ein eingeloggter User / When `GET /api/groups` aufgerufen wird / Then liefert die API
  Status 200 und ein JSON-Array der Gruppen aufsteigend nach `order` sortiert.
  - Test: (populated after /tdd-red)

- **AC-2:** Given ein Request `POST /api/groups` mit `{"name":"Skigebiete Tirol"}` ohne `id` / When
  verarbeitet / Then wird `id` aus dem Namen via Kebab-Case erzeugt, `order` automatisch vergeben,
  Status 201 und das gespeicherte Group-Objekt zurückgegeben.
  - Test: (populated after /tdd-red)

- **AC-3:** Given eine existierende Gruppe / When `PATCH /api/groups/{id}` mit nur `{"name":"Neu"}`
  gesendet wird / Then wird ausschließlich `name` geändert, `default_profile` und `order` bleiben
  unverändert erhalten, Status 200.
  - Test: (populated after /tdd-red)

- **AC-4:** Given eine Gruppe mit zwei zugeordneten Orten (`group_id == id`) / When
  `DELETE /api/groups/{id}` aufgerufen wird / Then wird die Gruppe entfernt und beide Orte erhalten
  `group_id = null`, ohne dass andere Location-Felder verloren gehen, Status 204.
  - Test: (populated after /tdd-red)

- **AC-5:** Given ein existierender Ort mit gesetztem Namen und Koordinaten / When
  `PATCH /api/locations/{id}` mit `{"group_id":"ski-tirol"}` und danach mit `{"group_id":null}`
  gesendet wird / Then wird nur `group_id` gesetzt bzw. genullt, alle übrigen Felder (Name, Lat, Lon,
  CreatedAt, activity_profile) bleiben unverändert, Status 200.
  - Test: (populated after /tdd-red)

- **AC-6:** Given ein User mit Locations, die nur das Legacy-`group`-Freitextfeld tragen und keine
  `groups.json` / When `LoadGroups` erstmals läuft / Then werden distinkte Gruppen-Strings verlustfrei
  in Group-Objekte überführt, `groups.json` persistiert und `group_id` auf den Orten backfilled; ein
  zweiter `LoadGroups`-Aufruf erzeugt KEINE Duplikate (idempotent).
  - Test: (populated after /tdd-red)

- **AC-7:** Given ein Snapshot des Datenstands vor der Migration / When die Migration läuft und der Store
  neu geladen wird / Then ist die Anzahl der Locations identisch (vorher == nachher) und jeder Ort, der
  zuvor einen `group`-String hatte, hat nun ein gültiges `group_id` auf eine existierende Gruppe (kein
  Datenverlust, kein verwaister FK).
  - Test: (populated after /tdd-red)

- **AC-8:** Given eine Location-JSON ohne `group_id`-Feld und ein leerer Group-Bestand / When geladen /
  Then parst die Location fehlerfrei (`group_id` = nil) und `GET /api/groups` liefert `[]` (200) —
  Backward-Compatibility gewahrt.
  - Test: (populated after /tdd-red)

## Known Limitations

- `default_profile` migrierter Gruppen ist initial leer; der User setzt es später (Frontend #301).
- Slug-Kollision zweier verschiedener Gruppen-Namen wird per Suffix dedupliziert; identische Namen
  werden zu einer Gruppe zusammengefasst (gewolltes Verhalten).
- Das Legacy-`group`-Freitextfeld wird nach der Migration nicht mehr gepflegt (read-only Spur);
  ein späteres Entfernen ist ein separates Cleanup.
- LoC: substanzieller Go-Code (Model + Store + 5 Handler + Migration + Tests) — voraussichtlich
  >250 LoC; in Phase 6 ggf. `workflow.py set-field loc_limit_override`.

## Changelog

- 2026-05-22: Initial spec aus Phase-2-Analyse erstellt (Kontext: `docs/context/issue_341_group_backend.md`)
