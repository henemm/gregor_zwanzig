# Context: issue_341_group_backend

## Request Summary

Issue #341 (`type:feature`, `priority:high`, `area:compare`, `foundation`): Backend-Fundament
für #301. Echte `Group`-Entity (`id, name, default_profile, order`), `Location.group_id` (FK),
CRUD-Endpoints `/api/groups`, neues `PATCH /api/locations/{id}`, plus verlustfreie Migration
der bestehenden Freitext-`group`-Strings → Group-Objekte. Blockiert #301 (Frontend), Teil Epic #246.

## Ausgangslage (verifiziert)

- `Location.Group *string` (Freitext, JSON `"group"`) — `internal/model/location.go:14`.
- KEINE Group-Entity, KEIN `/api/groups`, KEIN `group_id`, KEIN PATCH auf Locations.
- **Python-Core liest das `group`-Feld NICHT** (geprüft: keine `locations/`- oder `.group`-Zugriffe
  in `src/`; Treffer sind Regex-`match.group(1)`). Compare-Engine ist Go-nativ (#250).
  → Migration vollständig im Go-Backend gekapselt, kein Python-Schema-Rework nötig.

## Related Files

| Datei | Relevanz |
|---|---|
| `internal/model/location.go` | `Location` — `GroupID *string` ergänzen (additiv, omitempty); `Group` bleibt während Transition |
| `internal/model/subscription.go` | Vorbild-Model (additive omitempty-Felder, #252) |
| `internal/model/group.go` | **neu** — `Group`-Struct |
| `internal/store/store.go` | Store-Muster: per-file (Locations 34–79) vs. single-file (Subscriptions 227–382, Presets 323–364). Lazy-Migration-Vorbild: `weekly_friday→weekly` (254–257), `AlertRules nil`-Coercion (113–115) |
| `internal/handler/location.go` | Handler-Muster: `WithUser`, `toKebab` (19–24), `validateLocation` (42–53), Update=Read-Modify (97–147). Hier `PatchLocationHandler` ergänzen |
| `internal/handler/subscription.go` | Vorbild Handler-Set (List/Get/Create/Update/Patch/Delete) |
| `internal/handler/group.go` | **neu** — Group-Handler-Set |
| `internal/handler/subscription_patch_test.go` | **Test-Vorbild** für PATCH (`store.New(t.TempDir(), …)`, httptest, chi-URLParam) |
| `internal/handler/location_write_test.go` | Test-Vorbild Location-CRUD |
| `cmd/server/main.go` | Routen-Registrierung (chi); `/api/locations` 91–95, `/api/subscriptions` 103–108 — hier `/api/groups` + `PATCH /api/locations/{id}` ergänzen |
| `frontend/src/lib/types.ts` | `Location.group?` (Z. 10) — später `group_id` ergänzen; Group-Type spiegeln (Frontend-Teil = #301) |

## Existing Patterns

- **Router:** `go-chi/chi/v5`, `chi.URLParam(r, "id")`, `r.Get/Post/Put/Patch/Delete`.
- **User-Scoping:** `s = s.WithUser(middleware.UserIDFromContext(r.Context()))` in jedem Handler.
- **ID-Gen:** `toKebab(name)` wenn ID leer (Create).
- **Fehler-Responses:** `{"error":"..."}` + Status (400/404/500), Create→201, Delete→204.
- **Store-Persistenz:** single-file `data/users/{uid}/<name>.json` (Subscriptions/Presets) ist
  für Groups passend (wenige Einträge, `order`-Sortierung). Save = MarshalIndent.
- **Lazy-Migration on-load:** Coercion beim Laden statt separatem Migrations-Skript (Vorbild
  `weekly_friday`, `alert_rules nil`). Empfehlung: `LoadGroups()` leitet bei fehlender
  `groups.json` Gruppen aus distinkten `Location.Group`-Strings ab und persistiert sie einmalig;
  `group_id`-Backfill auf Locations symmetrisch.
- **Tests:** Go-Handler/Store-Tests mit `t.TempDir()` + echtem Dateisystem (kein Mock).

## Dependencies

- **Upstream:** chi-Router, `middleware.UserIDFromContext`, `store.Store`.
- **Downstream:** #301 (Frontend) konsumiert `/api/groups` + `group_id`. Compare-Engine (#250)
  nutzt Locations — `GroupID` ist additiv, bricht nichts.
- **Daten:** Bestehende `Location.group`-Strings (produktiv vorhanden) müssen verlustfrei migrieren.

## Existing Specs

- `docs/specs/modules/compare_247_location_model.md` — Location-Datenmodell (additive omitempty-Konvention)
- `docs/specs/modules/issue_252_compare_presets.md` — Subscription-Backend inkl. PATCH (§2 AC-4)
- `docs/specs/modules/issue_250_compare_engine.md` — Compare-Engine (Go-nativ)
- `docs/specs/ux_redesign_navigation.md §3` — Soll-Ziel (Gruppen-Sidebar)
- Kontext Frontend-Folgeissue: `docs/context/issue_301_compare_master_detail.md`

## Offene Design-Entscheidungen für die Spec

1. **Store-Form:** single-file `groups.json` (empfohlen) vs. per-file `groups/{id}.json`.
2. **`default_profile`-Ableitung bei Migration:** null vs. häufigstes `activity_profile` der Orte.
3. **`Group`-Feld-Lebenszyklus:** `group` (String) additiv behalten und parallel pflegen,
   oder nach Migration `group_id` als alleinige Quelle (Freitext nur noch read-on-migrate).
4. **PATCH-Semantik Location:** echtes partielles Merge (nur gesetzte Felder) vs.
   Spezial-Endpoint nur für `group_id` (analog `subscriptions/{id}/run-status`).
5. **`DELETE /api/groups/{id}`:** Orte auf `group_id=null` setzen (Pflicht-AC, keine verwaisten FKs).

## Risks & Considerations

1. **Daten-Schema-Rework (BUG-DATALOSS-GR221):** Pre-Snapshot (Hook `data_schema_backup.py`
   greift bei Edit an `store.go`/`*.go`-Schema), Roundtrip-Test (load→migrate→load, Counts vor==nach),
   Read-Modify-Write/Merge bei allen Saves.
2. **Idempotenz der Lazy-Migration:** mehrfaches Laden darf keine Duplikat-Gruppen erzeugen.
3. **ID-Kollisionen:** zwei Gruppen-Strings mit gleichem Kebab-Slug → Dedup-Strategie nötig.
4. **Scope-Disziplin:** reines Backend. Frontend-Konsum bleibt #301. LoC-Limit 250 beachten
   (Go-Code zählt; ggf. `loc_limit_override`).
5. **AC-N-Format Pflicht** (Spec created >= 2026-05-11): `## Acceptance Criteria` mit
   `**AC-1:** Given/When/Then`.
