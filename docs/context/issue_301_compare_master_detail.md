# Context: issue_301_compare_master_detail

## ✅ Status-Update 2026-05-23: Backend-Vorbedingung #341 erledigt

Die als blockierende Vorbedingung definierte Backend-Arbeit ist **vollständig
deployed** (Commit `be9cca7`). Verifiziert im Code:

- `internal/model/group.go` — `Group{ID, Name, DefaultProfile *string, Order int}` ✅
- `Location.GroupID *string` (`internal/model/location.go:15`) — neben Legacy `Group` ✅
- `cmd/server/main.go:97–100` — `GET/POST/PATCH/DELETE /api/groups` ✅
- `cmd/server/main.go:95` — `PATCH /api/locations/{id}` (`PatchLocationHandler`, Drag-Move) ✅
- Lazy-Migration der `group`-Strings verlustfrei auf Staging verifiziert ✅

→ **Damit ist dieser Workflow rein Frontend.** Der Delta-Scope unten (GroupSection,
AutoReportsOverview, CreateGroupDialog, klickbarer Ortsname, Sidebar 240→320px) ist
vollständig umsetzbar. Frontend kennt `Group` noch **nicht** (`types.ts` ohne `Group`,
`+page.server.ts` lädt `/api/groups` nicht) — das ist der Startpunkt von Phase 2.

## Request Summary

Issue #301 (`priority:high`, `area:compare`, `ux`, `feature`): Compare-Screen auf
**Master-Detail-Layout** bringen — linke Sidebar mit Orten in **klappbaren Gruppen**,
rechter Content-Bereich (Default = **Auto-Reports-Karten-Grid**, nach Vergleich =
Ergebnis-Tabelle). `/locations` und `/subscriptions` werden in den Compare-Bereich
absorbiert. Grundlage: `docs/specs/ux_redesign_navigation.md §3`.

## ⚠️ Kernbefund: Großteil ist bereits gebaut

Das Issue wurde gegen einen älteren Stand (flache Ortsliste mit Checkboxen) formuliert.
Seither haben #249 (LocationsRail), #287 (Compare-Polish), #252 (Auto-Briefings/
Subscriptions) und #270 (Compare-Mobile) bereits große Teile geliefert. **Bereits
vorhanden:**

- 2-Spalten-Layout auf `/compare` (Sidebar + Content, inkl. Mobile-Bottom-Sheet)
- LocationsRail rendert Orte gruppiert, klappbar (Chevron + Checkbox + Count)
- Sidebar-Suche (`compare-rail-search`) filtert sidebar-weit
- `CompareSubscriptionsPanel` als Default-Content (Subscriptions als Karten-Liste)
- `/subscriptions` ist ein 301-Redirect auf `/compare`
- Sidebar/BottomNav enthalten **keine** `/locations`- oder `/subscriptions`-Nav-Items mehr
- `Location.group` (Freitext-String) existiert in Frontend-Type **und** Go-Model

## Gap-Analyse: Akzeptanzkriterien vs. Ist-Zustand

| AC aus #301 | Status | Lücke |
|---|---|---|
| 2-Spalten-Layout (Sidebar 320px + Content) | ⚠️ teilweise | Sidebar ist `w-60` = 240px, nicht 320px |
| Sidebar: gruppiert + klappbare Headers | ✅ erfüllt | — |
| Default-Content: Auto-Reports als **Karten-Grid** | ⚠️ teilweise | `CompareSubscriptionsPanel` ist Karten-*Liste*, kein Eyebrow/H1/Grid-Design wie Soll |
| Suche filtert sidebar-weit | ✅ erfüllt | — |
| Klick auf Ortsnamen (ohne Checkbox) → Edit-Dialog | ❌ fehlt | `{loc.name}` ist nicht klickbar; nur Wetter-Icon-Button vorhanden |
| „+ Gruppe" und „+ Ort" Buttons im Footer | ⚠️ teilweise | Nur `+ NEU` (Ort) vorhanden; kein „+ Gruppe", kein CreateGroupDialog |
| Nav `/locations` + `/subscriptions` entfernt | ✅ erfüllt | — |

## Strategischer Konflikt: Group-Entity vs. Freitext-String

Das **Datenmodell** im Issue verlangt deutlich mehr als die ACs:
- `Group`-Entity mit `id, name, default_profile, order`
- `Location.group_id` (FK statt Freitext)
- Backend-Endpoints `GET/POST/PATCH/DELETE /api/groups` + `PATCH /api/locations/:id`
- Profil-Dot im Gruppen-Header (Farbe nach `default_profile`)
- Das Issue selbst notiert: *„Vor diesem Issue: Backend muss `Group`-Entity und
  Endpoints liefern. Separates Backend-Issue erstellen."*

**Ist-Zustand (Stand 2026-05-23):** Backend-seitig ist der volle Group-Entity-Ausbau
**fertig** (siehe Status-Update oben, #341). Frontend-seitig sind Gruppen weiterhin nur
der Freitext-String `Location.group` — der `Group`-Type, das Laden von `/api/groups` und
die `group_id`-Verdrahtung fehlen im Svelte-Code noch komplett.

→ **Scoping-Entscheidung getroffen (PO 2026-05-22):** Voller Group-Entity-Ausbau. Backend
(#341) erledigt; dieser Workflow setzt das Frontend darauf um.

### PO-Entscheidung (2026-05-22): Voller Ausbau

Der PO hat sich für **echte Group-Objekte** (Variante mit Backend-Entity) entschieden.
Daraus folgt ein zweistufiger Plan — das Issue selbst fordert diese Aufteilung:

1. **Backend-Vorarbeit (separates Issue, ZUERST):**
   - `Group`-Entity (`id, name, default_profile, order`) in `internal/model/`
   - Store-Persistenz (`data/users/{uid}/groups/...` analog Locations) + CRUD
   - Endpoints `GET/POST/PATCH/DELETE /api/groups` + `PATCH /api/locations/{id}` (group_id)
   - **Daten-Migration:** bestehende `Location.group`-Strings → Group-Objekte + `group_id`;
     Pre-Snapshot + Roundtrip-Test (BUG-DATALOSS-GR221-Pflicht)
   - Vorbild: Subscription-Backend (Model + Store-CRUD + Handler-Set + Router + LastRun)
2. **Frontend #301 (dieses Issue, danach):**
   - GroupSection (Profil-Dot nach `default_profile`), CreateGroupDialog, „+ Gruppe"-Button
   - AutoReportsOverview als Kachel-Raster (Eyebrow + H1 + AutoReportCard + AddReportCard)
   - Klick auf Ortsname → Edit-Dialog, Sidebar-Breite 240 → 320px

→ Dieser Workflow (`issue_301_compare_master_detail`) bleibt für das **Frontend**.
Das Backend ist als **#341** angelegt (eigener Workflow) und ist **blockierende Vorbedingung**.

## Related Files

### Frontend (zu ändern / neu)
| Datei | Relevanz |
|---|---|
| `frontend/src/routes/compare/+page.svelte` | 2-Spalten-Layout, Gruppen-State (`groupedLocations` 168–181, `openGroups` 210–212, `toggleGroup`/`toggleGroupSelection` 214–234), Default-Content-Bedingung (437–442) |
| `frontend/src/routes/compare/+page.server.ts` | load: fetch `/api/locations` + `/api/subscriptions` parallel (7–23) |
| `frontend/src/lib/components/compare/LocationsRail.svelte` | Sidebar; Breite `w-60` (85), Gruppen-Render (135–177), ungruppiert (179–198), Footer nur `+ NEU` (201–209), Ortsname nicht klickbar (160/185) |
| `frontend/src/lib/components/compare/CompareSubscriptionsPanel.svelte` | aktueller Default-Content (Subscriptions-Karten 42–86) |
| `frontend/src/lib/components/compare/GroupSection.svelte` | **neu** (laut Issue) — bislang Inline in Rail gelöst |
| `frontend/src/lib/components/compare/AutoReportsOverview.svelte` | **neu** (laut Issue) — Eyebrow+H1+Grid; existiert nicht |
| `frontend/src/lib/components/compare/CreateGroupDialog.svelte` | **neu** (laut Issue); existiert nicht |
| `frontend/src/lib/components/LocationForm.svelte` | Group-Zuweisung (Edit-Dialog) |
| `frontend/src/lib/types.ts` | `Location.group?: string` (Z. 10) — kein `group_id` |
| `frontend/src/lib/components/compare/locationHelpers.ts` | `filterLocations()` (53–73) filtert bereits nach `loc.group` |
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` / `BottomNav.svelte` | Nav-Items (bereits ohne Locations/Subscriptions) |

### Backend (Go — ✅ vorhanden via #341, nur lesend genutzt)
| Datei | Relevanz |
|---|---|
| `internal/model/group.go` | `Group{ID, Name, DefaultProfile *string, Order int}` — Quelle für Frontend-`Group`-Type |
| `internal/model/location.go` | `Group *string` (Z. 14, Legacy) **+** `GroupID *string` (Z. 15) |
| `internal/handler/group.go` | `GroupsHandler` / `CreateGroupHandler` / `UpdateGroupHandler` / `DeleteGroupHandler` |
| `internal/handler/location.go` | `PatchLocationHandler` (Drag-Move `group_id`) ergänzt GET/POST/PUT/DELETE |
| `cmd/server/main.go` | `/api/groups` GET/POST/PATCH/DELETE (97–100) + `PATCH /api/locations/{id}` (95) |
| `internal/model/subscription.go` | `CompareSubscription` (für Auto-Reports) — vollständig vorhanden |

## Existing Patterns

- **Gruppierung heute = Freitext-String** auf Location; Gruppen entstehen implizit, sobald
  ein Ort denselben `group`-String trägt. `filterLocations()` und `groupedLocations`
  bauen die Map zur Laufzeit.
- **Design-System Pflicht:** `docs/design-system/` ist alleinige Autorität (Brand-Tokens,
  `Btn`, `Checkbox`, `Pill`, `data-slot`-Muster). Vor Frontend-Arbeit lesen. AP-007/008/009
  (keine Hex-Literale, keine Magic-Pixel, keine Emojis) gelten.
- **Subscriptions-Backend** als Vorbild für ein evtl. Group-Backend (Model + Store-CRUD +
  Handler-Set + Router-Registrierung + LastRun-Tracking).
- **Read-Modify-Write/Merge-Pflicht** bei Persistenz-Änderungen (CLAUDE.md „Daten-Schema-
  Reworks", BUG-DATALOSS-GR221). `Location.group` darf nicht verloren gehen.

## Dependencies

- **Upstream (Compare-Frontend nutzt):** `/api/locations`, `/api/subscriptions`, Compare-
  Engine (`POST /api/compare/run`, #250), Design-System-Komponenten.
- **Downstream (würde sich ändern):** Bei Wechsel Freitext→`group_id` müssten alle
  bestehenden Locations migriert werden (Schema-Rework mit Snapshot + Migration + Roundtrip-Test).
- **Issue-Abhängigkeit:** #301 bezieht sich auf Epic #246 (offen). Das im Issue geforderte
  Backend-Group-Issue wurde als **#341 angelegt und ist erledigt** (Commit `be9cca7`,
  deployed 2026-05-23). Vorbedingung damit erfüllt — Frontend entsperrt.

## Existing Specs

- `docs/specs/ux_redesign_navigation.md §3` — Soll-Layout Master-Detail (approved)
- `docs/specs/modules/issue_249_locations_rail.md` — LocationsRail-Ursprung
- `docs/specs/modules/issue_287_compare_polish.md` — Compare-Politur
- `docs/specs/modules/issue_252_compare_presets.md` — Auto-Briefings/Subscriptions
- `docs/specs/modules/issue_250_compare_engine.md` — Compare-Run-Backend
- `docs/specs/modules/compare_247_location_model.md` — Location-Datenmodell
- `docs/specs/modules/bug_270_compare_mobile.md` — Mobile-Verhalten Compare

## Soll-Mockup

`.github/issue-assets/soll-flow3A-sidebar-overview.png` (im Issue verlinkt).

## Analyse-Ergebnis (Phase 2, 2026-05-23)

### Kernbefund: Frontend ignoriert die neue Group-Entity noch komplett
Das Frontend gruppiert weiterhin nach dem Legacy-Freitext `loc.group`. Die in #341
gelieferte Entity (`group_id`, `default_profile`, `order`) wird im Compare-Fluss **nicht**
genutzt. `types.ts` kennt weder `Group` noch `group_id`; `+page.server.ts` lädt
`/api/groups` nicht; `NewLocationWizard` sendet noch `group` (Freitext) statt `group_id`.
Migration verifiziert: `store.go:438 migrateGroups()` backfillt `group_id` auf allen
Bestandsorten beim ersten `/api/groups`-Aufruf — die Sidebar zeigt vorhandene Gruppen also korrekt.

### Architektur-Entscheidung
- **Source of Truth für Gruppen = `/api/groups`** (`Group[]` mit `order`/`default_profile`).
  Frontend baut `Map<groupId, Group>` für Lookup.
- **Legacy `loc.group` bleibt im Type erhalten, wird aber nicht mehr gelesen** (kein Entfernen,
  kein Migrationscode im Frontend — Backend-Migration erledigt das).
- **Orte ohne `group_id` → synthetischer „Ungruppiert"-Bucket** (nur gerendert wenn nicht leer,
  immer als letztes nach `order`-sortierten Gruppen).
- **Profil-Dot** via `profileSignature(group.default_profile)` → `var(--g-profile-*)` (AP-007/008/009 erfüllt).
- **Anlegen/Zuweisen:** `CreateGroupDialog` → `POST /api/groups`; Ort-zu-Gruppe via `PATCH /api/locations/{id}`
  (`group_id`). `POST /api/locations` akzeptiert `group_id` direkt im Body (kein Post+Patch nötig).
- **`api.ts` braucht eine `patch()`-Methode** (Proxy `/api/[...path]/+server.ts` exportiert PATCH bereits).
- **Klick auf Ortsname → Edit:** `LocationForm` bekommt `groups`-Prop + `<Select>` auf Group-Entities,
  Save via bestehendem `PUT /api/locations/{id}` (überträgt `group_id` vollständig).

### Scope-Split: ZWEI kohärente Lieferungen (LoC-Limit-konform)
Gesamt ~385 LoC über ~13 Dateien — überschreitet das 250-LoC-Limit und die 4-5-Datei-Schwelle.
Daher Aufteilung (PO-sichtbar: erst Gruppen-Sidebar, dann Auto-Reports-Kachelübersicht):

**Lieferung A — Sidebar + Group-Entity (dieser Workflow `issue_301_compare_master_detail`, ~245 LoC):**
`types.ts` (Group, group_id), `api.ts` (patch), `+page.server.ts` (lädt /api/groups),
`locationHelpers.ts` + Test (Filter auf group_id), `CreateGroupDialog.svelte` (NEU),
`GroupSection.svelte` (NEU), `LocationsRail.svelte` (320px, `<aside>`, klickbarer Name, „+ Gruppe"),
`NewLocationWizard.svelte` (group_id), `LocationForm.svelte` (groups-Select), `+page.svelte` (Verdrahtung + Edit-Dialog).

**Lieferung B — AutoReportsOverview-Content (Folge-Workflow, ~140 LoC):**
`AutoReportCard.svelte` (NEU), `AddReportCard.svelte` (NEU), `AutoReportsOverview.svelte` (NEU,
ersetzt CompareSubscriptionsPanel als Default-Content), `+page.svelte` (Import-Swap).

Begründung: A ist die risikotragende Daten-Umstellung (group_id, neue API-Calls, Filter-Logik,
Edit-Dialog), B ist rein additiver Content. Getrennte Reviews/E2E, kleinere Developer-Läufe
(10-Min-Timeout). Beide gaten das Schließen von #301.

### Konkrete Test-/Integrations-Hinweise (für Spec & TDD)
- E2E `orts-vergleich-c1/c4.spec.ts` suchen `page.locator('aside')` → Rail muss `<aside>` nutzen (heute `<div>`).
- `locationHelpers.test.ts` testet alte `filterLocations(activeGroup)`-Signatur → Fixtures anpassen (group_id).
- `CreateGroupDialog`: doppelter Name → gleiche kebab-ID → Backend-Fehler; Error-State im Dialog zeigen.
- `openGroups`-Init auf `groups.map(g => g.id)` umstellen (nicht mehr Gruppennamen).

## Risks & Considerations

1. **Doppelarbeit vermeiden:** ~70 % der ACs sind erfüllt. Vor Implementierung muss der
   echte Delta-Scope geklärt werden, sonst wird Vorhandenes unnötig umgebaut
   (vgl. Memory „Sorgsam bei Änderungen").
2. **Scoping-Fork (Group-Entity vs. String)** — ✅ entschieden & abgearbeitet: voller
   Ausbau, Backend #341 erledigt. Für diesen Workflow keine offene Frage mehr.
3. **Daten-Schema-Risiko:** ✅ im Backend #341 adressiert (Lazy-Migration, Pre-Snapshot,
   Roundtrip-Test, verlustfrei auf Staging). Frontend liest/schreibt nur via API —
   Read-Modify-Write/Merge bleibt Pflicht beim Speichern der Location (Edit-Dialog).
4. **Default-Content-Design:** AutoReportsOverview (Eyebrow/H1/Grid + AddReportCard) ist ein
   echtes UI-Delta gegenüber dem schlichten CompareSubscriptionsPanel.
5. **Sidebar-Breite** 240→320px ist ein Layout-Detail mit möglichen Folgen für die
   Content-Spalte / Mobile-Breakpoints.
