---
entity_id: epic_135_step2_trip_detail_actions
type: module
created: 2026-05-12
updated: 2026-05-12
status: approved
version: "1.0"
parent_spec: epic_135_trip_detail
related: epic_135_step1_tab_navigation
issue: 153
tags: [frontend, sveltekit, svelte5, backend, go, schema-rework, trip-detail, epic-135, issue-153]
---

# Epic 135 — Sub-Spec #153: Trip-Detail Header (Breadcrumb + Status-Badge + Aktionen)

## Approval

- [x] Approved (2026-05-12)

## Purpose

Ergänzt die Trip-Detail-Seite (`/trips/[id]`) mit drei Header-Bausteinen oberhalb der bestehenden Tab-Navigation aus Issue #155: einem Breadcrumb zurück zur Trip-Liste, einem Status-Badge mit vier semantischen Status (Geplant / Aktiv / Pausiert / Archiviert) und zwei reversiblen Aktions-Buttons (Pausieren/Fortsetzen, Archivieren/Reaktivieren). Der Status wird nicht als String persistiert, sondern per Pure-Function `deriveTripStatus(trip, now)` aus zwei neuen Backend-Zeitstempel-Feldern (`paused_at`, `archived_at`) und dem Stage-Datumsbereich abgeleitet — einmalig an einer testbaren Stelle, keine Inkonsistenz zwischen gespeichertem Status-String und tatsächlichem Zustand. Die Persistenz der Flags läuft über einen eigenen `PATCH /api/trips/{id}/state`-Endpoint, damit der bestehende `PUT /api/trips/{id}`-Handler unverändert bleibt und das Go-Tristate-Problem (absent vs. explicit null) vermieden wird.

## Source

- **Route (EDIT):** `frontend/src/routes/trips/[id]/+page.svelte`
- **Backend-Modell (EDIT):** `internal/model/trip.go`
- **Backend-Handler (EDIT + NEU):** `internal/handler/trip.go` — neuer `UpdateTripStateHandler`
- **Route-Registrierung (EDIT):** `cmd/server/main.go`
- **Backend-Tests (NEU):** `internal/handler/trip_state_test.go`
- **Frontend-Types (EDIT):** `frontend/src/lib/types.ts`
- **Pure-Function (NEU):** `frontend/src/lib/utils/tripStatus.ts`
- **Pure-Function-Tests (NEU):** `frontend/src/lib/utils/tripStatus.test.ts`
- **Komponente (NEU):** `frontend/src/lib/components/trip-detail/TripStatusBadge.svelte`
- **Komponente (NEU):** `frontend/src/lib/components/trip-detail/TripHeader.svelte`
- **Barrel-Export (EDIT):** `frontend/src/lib/components/trip-detail/index.ts`
- **E2E-Tests (NEU):** `frontend/e2e/trip-detail-actions.spec.ts`
- **Identifier:** `UpdateTripStateHandler`, `deriveTripStatus`, `TripStatusBadge`, `TripHeader`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/model/trip.go` (`Trip`) | bestehend (EDIT) | Neue Felder `PausedAt *time.Time` + `ArchivedAt *time.Time` (`json:"paused_at,omitempty"`, `json:"archived_at,omitempty"`) |
| `internal/handler/trip.go` (`UpdateTripHandler`, `tripUpdateRequest`) | bestehend | Referenz-Pattern für Merge-Logik; neue Felder werden dort **nicht** aufgenommen — getrennte Verantwortung |
| `PATCH /api/trips/{id}/state` | NEU (Go-Handler) | Einziger Schreibpfad für `paused_at`/`archived_at`; Boolean-Body `{paused?: bool, archived?: bool}` → Timestamp setzen/löschen |
| `GET /api/trips/{id}` | bestehend | Liefert Trip-JSON inkl. der neuen optionalen Felder (nach Schema-Edit) |
| `frontend/src/lib/types.ts` (`Trip`) | bestehend (EDIT) | Interface um `paused_at?: string` + `archived_at?: string` erweitern (ISO-8601, optional) |
| `frontend/src/lib/utils/tripStatus.ts` (`deriveTripStatus`) | NEU | Pure-Function gibt `'planned' \| 'active' \| 'paused' \| 'archived'` zurück |
| `frontend/src/lib/components/ui/pill/Pill.svelte` (`Pill`) | bestehend | TripStatusBadge ist ein Thin-Wrapper um Pill mit Tone-Mapping |
| `frontend/src/routes/trips/+page.svelte` (Z. 277–293) | bestehend (Referenz) | Confirm-Dialog-Pattern für destruktive Aktionen; hier angepasst für Archivieren |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | bestehend (NICHT BERÜHRT) | Bleibt unverändert unterhalb von TripHeader; wird von `+page.svelte` weiterhin eingebunden |
| `frontend/src/routes/trips/[id]/+page.svelte` | bestehend (EDIT) | `<h1>{trip.name}</h1>` wird durch `<TripHeader {trip} />` ersetzt; `<TripTabs>` bleibt darunter |
| `frontend/e2e/trip-detail-tabs.spec.ts` | bestehend (Referenz) | Playwright-Pattern für Route `/trips/[id]` und Auth via `playwright/.auth/admin.json` |
| `global.setup.ts` (`e2e-cockpit-test`) | bestehend | E2E-Testdaten-Trip für alle trip-detail-Specs |

## Implementation Details

### §1 Backend: Schema-Erweiterung `internal/model/trip.go`

Zwei neue optionale Felder im `Trip`-Struct, nach den bestehenden Zeitstempel-Feldern:

```go
// internal/model/trip.go
PausedAt   *time.Time `json:"paused_at,omitempty"`
ArchivedAt *time.Time `json:"archived_at,omitempty"`
```

`omitempty` stellt sicher, dass alte Trips ohne diese Felder sauberes JSON ohne `null`-Keys liefern. Python-Loader liest Trips als Dict und ignoriert unbekannte Felder — keine Python-seitige Änderung nötig.

### §2 Backend: Neuer Handler `UpdateTripStateHandler`

Neuer Handler in `internal/handler/trip.go`, registriert als `PATCH /api/trips/{id}/state` in `cmd/server/main.go`.

**Request-DTO:**

```go
type tripStateRequest struct {
    Paused   *bool `json:"paused"`
    Archived *bool `json:"archived"`
}
```

**Handler-Logik:**

```
1. Trip per ID aus Store laden → 404 wenn nicht vorhanden
2. JSON-Body in tripStateRequest dekodieren
3. Wenn req.Paused != nil:
   - true  → trip.PausedAt = ptr(time.Now())
   - false → trip.PausedAt = nil
4. Wenn req.Archived != nil:
   - true  → trip.ArchivedAt = ptr(time.Now())
   - false → trip.ArchivedAt = nil
5. Trip speichern (Read-Modify-Write, alle anderen Felder unverändert)
6. HTTP 200 + aktualisiertes Trip-JSON zurückgeben
```

Idempotenz-Verhalten: `PATCH /state` mit `paused: true` auf einem bereits pausierten Trip überschreibt `paused_at` mit einem neuen Timestamp. Kein Fehler; Idempotenz auf Ergebnis-Ebene (Trip bleibt pausiert), nicht auf Timestamp-Ebene.

**Route-Registrierung in `cmd/server/main.go`:**

```go
r.Patch("/api/trips/{id}/state", handler.UpdateTripStateHandler(store))
```

Der bestehende `PUT /api/trips/{id}` bleibt unverändert. `tripUpdateRequest` wird **nicht** um `paused_at`/`archived_at` erweitert — Mutation dieser Felder läuft ausschließlich über den neuen PATCH-Endpoint.

### §3 Frontend: Types-Erweiterung `frontend/src/lib/types.ts`

```typescript
// Am Trip-Interface ergänzen:
paused_at?: string;   // ISO-8601, optional
archived_at?: string; // ISO-8601, optional
```

### §4 Frontend: Pure-Function `frontend/src/lib/utils/tripStatus.ts`

```typescript
export type TripStatus = 'planned' | 'active' | 'paused' | 'archived';

export function deriveTripStatus(trip: Trip, now: Date): TripStatus {
  if (trip.archived_at != null) return 'archived';
  if (trip.paused_at != null) return 'paused';

  const stages = trip.stages ?? [];
  if (stages.length === 0) return 'planned';

  const dates = stages.flatMap((s) => [s.date].filter(Boolean));
  if (dates.length === 0) return 'planned';

  const first = new Date(dates[0]);
  const last  = new Date(dates[dates.length - 1]);
  const today = new Date(now.toDateString()); // Zeit-Normalisierung

  if (today >= first && today <= last) return 'active';
  return 'planned';
}
```

Bedingungsreihenfolge ist verbindlich: `archived` hat Vorrang vor `paused`, `paused` hat Vorrang vor der Datumsableitung.

### §5 Frontend: `TripStatusBadge.svelte`

Thin-Wrapper um die bestehende `Pill`-Komponente (`frontend/src/lib/components/ui/pill/Pill.svelte`).

```svelte
<script lang="ts">
  import Pill from '$lib/components/ui/pill/Pill.svelte';
  import { deriveTripStatus, type TripStatus } from '$lib/utils/tripStatus';
  import type { Trip } from '$lib/types';

  interface Props { trip: Trip; now?: Date; }
  let { trip, now = new Date() }: Props = $props();

  const TONE_MAP: Record<TripStatus, string> = {
    planned:  'info',
    active:   'success',
    paused:   'warning',
    archived: 'default',
  };

  const LABEL_MAP: Record<TripStatus, string> = {
    planned:  'Geplant',
    active:   'Aktiv',
    paused:   'Pausiert',
    archived: 'Archiviert',
  };

  const status = $derived(deriveTripStatus(trip, now));
</script>

<Pill tone={TONE_MAP[status]} data-testid="trip-detail-status-badge">
  {LABEL_MAP[status]}
</Pill>
```

### §6 Frontend: `TripHeader.svelte`

Bündelt Breadcrumb + StatusBadge + Aktions-Buttons + Confirm-Dialog in einer Komponente (~100 LoC).

**Prop-Signatur:**

```typescript
interface Props {
  trip: Trip;
  onStatusChange?: (updated: Trip) => void;
}
let { trip, onStatusChange }: Props = $props();
```

**Breadcrumb-Aufbau:**

```svelte
<nav data-testid="trip-detail-breadcrumb" aria-label="Breadcrumb">
  <a href="/trips" data-testid="trip-detail-breadcrumb-link-trips">Trips</a>
  <span aria-hidden="true"> / </span>
  <span data-testid="trip-detail-breadcrumb-current">
    {trip.shortcode ?? trip.name}
  </span>
</nav>
```

**Aktions-Buttons:**

Button-Labels wechseln je nach Status. Sichtbarkeitsregel: Wenn Trip archiviert ist, wird „Pausieren" ausgeblendet (nicht nur disabled). Wenn Trip pausiert ist, lautet der Button „Fortsetzen".

```
Status = archived  → Button "Reaktivieren" (archived: false) | kein Pause-Button
Status = paused    → Button "Fortsetzen" (paused: false) + Button "Archivieren" (archived: true)
Status = active    → Button "Pausieren" (paused: true) + Button "Archivieren" (archived: true)
Status = planned   → Button "Pausieren" (paused: true) + Button "Archivieren" (archived: true)
```

**Confirm-Dialog (nur für Archivieren/Reaktivieren):**

Pattern aus `routes/trips/+page.svelte:277-293`. Statt „Löschen" zeigt der Dialog:
- Titel: „Trip archivieren?" / „Trip reaktivieren?"
- Body: „Der Trip wird ins Archiv verschoben — er kann später reaktiviert werden." / „Der Trip wird aus dem Archiv zurückgeholt und ist wieder aktiv."
- Buttons: „Bestätigen" (`data-testid="trip-detail-archive-confirm-yes"`) + „Abbrechen" (`data-testid="trip-detail-archive-confirm-cancel"`)

**API-Call (PATCH):**

```typescript
async function sendStateUpdate(paused?: boolean, archived?: boolean): Promise<void> {
  const body: Record<string, boolean> = {};
  if (paused   !== undefined) body.paused   = paused;
  if (archived !== undefined) body.archived = archived;

  const res = await fetch(`/api/trips/${trip.id}/state`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`PATCH /state failed: ${res.status}`);
  const updated: Trip = await res.json();
  onStatusChange?.(updated);
}
```

**Named-Function-Pattern (Safari-Kompatibilität):**

Alle `on:click`-Handler müssen benannte Funktionen sein (`function handlePauseClick()`, `function handleArchiveConfirm()` usw.) — kein Inline-Arrow in `on:click={...}`. Vorbild: `TripTabs.svelte` (`handleValueChange`).

### §7 Route-Edit `+page.svelte`

```svelte
<script lang="ts">
  import { page } from '$app/stores';
  import { TripHeader, TripTabs } from '$lib/components/trip-detail';

  let { data } = $props();
  let trip = $state(data.trip);

  const initialTab = $derived($page.url.hash.replace('#', '') || 'overview');

  function handleStatusChange(updated: Trip): void {
    trip = updated;
  }
</script>

<TripHeader {trip} onStatusChange={handleStatusChange} />
<TripTabs {initialTab} />
```

Das `<h1>{trip.name}</h1>` aus Step 1 wird durch `<TripHeader {trip} ... />` ersetzt. `<TripTabs>` bleibt unverändert darunter.

### §8 TestID-Inventar

| TestID | Element | Zweck |
|--------|---------|-------|
| `trip-detail-breadcrumb` | `<nav>` | Breadcrumb-Container |
| `trip-detail-breadcrumb-link-trips` | `<a href="/trips">` | Klick → Navigation zu `/trips` |
| `trip-detail-breadcrumb-current` | `<span>` | Zeigt Shortcode (wenn vorhanden) oder Trip-Name |
| `trip-detail-status-badge` | `<Pill>` | Statusanzeige (Text + Tone) |
| `trip-detail-action-pause` | `<button>` | Label „Pausieren" oder „Fortsetzen"; bei archiviertem Trip nicht gerendert |
| `trip-detail-action-archive` | `<button>` | Label „Archivieren" oder „Reaktivieren" |
| `trip-detail-archive-confirm-dialog` | Dialog.Root | Confirm-Dialog für Archivieren/Reaktivieren |
| `trip-detail-archive-confirm-yes` | `<button>` | Bestätigen → sendet PATCH |
| `trip-detail-archive-confirm-cancel` | `<button>` | Abbrechen → Dialog schließt, keine Änderung |

### §9 Datei-Liste

| Art | Datei | Zweck | LoC (Schätzung) |
|-----|-------|-------|-----------------|
| NEU | `internal/handler/trip_state_test.go` | Go-Tests: PATCH /state Toggle, 404, PUT-Isolation | ~80 |
| EDIT | `internal/model/trip.go` | +2 Felder (`PausedAt`, `ArchivedAt`) | +2 |
| EDIT | `internal/handler/trip.go` | `UpdateTripStateHandler` + `tripStateRequest` DTO | +50 |
| EDIT | `cmd/server/main.go` | Route `PATCH /api/trips/{id}/state` registrieren | +1 |
| EDIT | `frontend/src/lib/types.ts` | `paused_at?`, `archived_at?` am Trip-Interface | +2 |
| NEU | `frontend/src/lib/utils/tripStatus.ts` | Pure-Function `deriveTripStatus` | ~25 |
| NEU | `frontend/src/lib/utils/tripStatus.test.ts` | Vitest-Unit-Tests für alle 4 Status | ~50 |
| NEU | `frontend/src/lib/components/trip-detail/TripStatusBadge.svelte` | Pill-Wrapper mit Tone-Mapping | ~30 |
| NEU | `frontend/src/lib/components/trip-detail/TripHeader.svelte` | Breadcrumb + Badge + Buttons + Confirm-Dialog | ~100 |
| EDIT | `frontend/src/lib/components/trip-detail/index.ts` | Barrel: TripStatusBadge + TripHeader exportieren | +2 |
| EDIT | `frontend/src/routes/trips/[id]/+page.svelte` | `<h1>` ersetzen durch `<TripHeader>` | +5 / -1 |
| NEU | `frontend/e2e/trip-detail-actions.spec.ts` | Playwright-E2E: alle AC-Szenarien | ~120 |
| **Summe** | | | **~360 LoC** |

**LoC-Override erforderlich:** Erwartete Gesamt-LoC ~360 überschreiten das Standard-Limit von 250. Override-Begründung: Backend-Handler NEU + Backend-Test NEU + 2 Frontend-Komponenten NEU + Util + Util-Tests + E2E-Test treiben die Zahl. Aufteilung würde Inkonsistenz erzeugen (UI ohne Backend-Persistenz, Backend ohne UI). Override-Befehl vor Phase 6: `workflow.py set-field loc_limit_override 400`.

## Expected Behavior

- **Input:** Trip-Objekt mit optionalen Feldern `paused_at` und `archived_at` (ISO-8601-String oder undefined), Stage-Array mit Datums-Feldern, aktuellem Datum `now`.
- **Output:**
  - `deriveTripStatus(trip, now)` liefert genau einen der vier Werte: `'planned' | 'active' | 'paused' | 'archived'`.
  - `TripStatusBadge` rendert den deutschen Label-Text und den zugehörigen Pill-Tone (success für Aktiv, warning für Pausiert, info für Geplant, default für Archiviert).
  - `TripHeader` rendert Breadcrumb-Nav, StatusBadge und kontextsensitive Action-Buttons. Bei archivierten Trips fehlt der Pause-Button.
  - `PATCH /api/trips/{id}/state` liefert HTTP 200 + aktualisiertes Trip-JSON bei gültiger Trip-ID; HTTP 404 bei unbekannter ID; HTTP 400 bei nicht dekodierbarem Body.
- **Side effects:**
  - PATCH setzt oder löscht `paused_at`/`archived_at` im Store. Alle anderen Trip-Felder bleiben unverändert (Read-Modify-Write).
  - Nach erfolgreichem PATCH ruft `TripHeader` `onStatusChange(updatedTrip)` auf → `+page.svelte` aktualisiert seinen lokalen `trip`-State → Badge + Button-Labels wechseln reaktiv ohne Page-Reload.
  - `PUT /api/trips/{id}` ohne `paused_at`/`archived_at` im Body lässt die Felder im Store unverändert (weil `tripUpdateRequest` sie nicht kennt).

## Acceptance Criteria

- **AC-1:** Given ein Trip ohne `paused_at` und `archived_at`, dessen Stage-Daten heute umschließen / When `deriveTripStatus(trip, now)` aufgerufen wird / Then gibt die Funktion `'active'` zurück, kein anderer Wert.

- **AC-2:** Given ein Trip mit gesetztem `archived_at` und gesetztem `paused_at` / When `deriveTripStatus(trip, now)` aufgerufen wird / Then gibt die Funktion `'archived'` zurück (archived hat Vorrang vor paused).

- **AC-3:** Given ein Trip mit gesetztem `paused_at` und ohne `archived_at`, dessen Stage-Daten heute umschließen / When `deriveTripStatus(trip, now)` aufgerufen wird / Then gibt die Funktion `'paused'` zurück (paused hat Vorrang vor Datumsableitung).

- **AC-4:** Given ein Trip ohne Flags und ohne Stage-Daten, die heute umschließen / When `deriveTripStatus(trip, now)` aufgerufen wird / Then gibt die Funktion `'planned'` zurück.

- **AC-5:** Given ein bestehender Trip im Backend / When `PATCH /api/trips/{id}/state` mit Body `{"paused": true}` gesendet wird / Then antwortet der Endpoint mit HTTP 200 und das zurückgegebene Trip-JSON enthält ein nicht-leeres `paused_at`-Feld.

- **AC-6:** Given ein Trip mit gesetztem `paused_at` / When `PATCH /api/trips/{id}/state` mit Body `{"paused": false}` gesendet wird / Then antwortet der Endpoint mit HTTP 200 und das zurückgegebene Trip-JSON enthält kein `paused_at`-Feld (oder `null`).

- **AC-7:** Given ein Trip mit gesetztem `paused_at` / When `PATCH /api/trips/{id}/state` ein zweites Mal mit Body `{"paused": true}` gesendet wird / Then antwortet der Endpoint mit HTTP 200 und kein Fehler — der Trip bleibt pausiert (Idempotenz auf Ergebnis-Ebene; `paused_at` wird mit neuem Timestamp überschrieben).

- **AC-8:** Given eine nicht existierende Trip-ID / When `PATCH /api/trips/{non-existent-id}/state` mit beliebigem Body gesendet wird / Then antwortet der Endpoint mit HTTP 404.

- **AC-9:** Given ein Trip mit gesetztem `paused_at` / When `PUT /api/trips/{id}` mit einem Body ohne `paused_at`-Feld gesendet wird / Then antwortet der Endpoint mit HTTP 200 und das zurückgegebene Trip-JSON enthält das ursprüngliche `paused_at`-Feld unverändert.

- **AC-10:** Given ein Trip mit Shortcode `"KHW 403"` / When die Route `/trips/[id]` aufgerufen wird und `TripHeader` gerendert ist / Then zeigt `data-testid="trip-detail-breadcrumb-current"` den Text `KHW 403` (Shortcode hat Vorrang vor Name).

- **AC-11:** Given ein Trip ohne Shortcode / When `TripHeader` gerendert ist / Then zeigt `data-testid="trip-detail-breadcrumb-current"` den Trip-Namen (Fallback).

- **AC-12:** Given ein Trip mit Status `active` (keine Flags, Stage-Daten umschließen heute) / When `TripHeader` gerendert ist / Then zeigt `data-testid="trip-detail-status-badge"` den Text `Aktiv` und die Pill hat Tone `success`.

- **AC-13:** Given ein Trip mit Status `active` / When der User auf `data-testid="trip-detail-action-pause"` klickt / Then wird `PATCH /api/trips/{id}/state` mit `{"paused": true}` gesendet, und nach dem Response wechselt `data-testid="trip-detail-status-badge"` auf `Pausiert` und `data-testid="trip-detail-action-pause"` zeigt Label `Fortsetzen` — ohne Page-Reload.

- **AC-14:** Given ein Trip mit Status `active` / When der User auf `data-testid="trip-detail-action-archive"` klickt / Then öffnet sich `data-testid="trip-detail-archive-confirm-dialog"` und es wird noch kein PATCH gesendet.

- **AC-15:** Given der Confirm-Dialog für Archivieren ist offen / When der User auf `data-testid="trip-detail-archive-confirm-cancel"` klickt / Then schließt der Dialog und der Trip-Status bleibt unverändert.

- **AC-16:** Given der Confirm-Dialog für Archivieren ist offen / When der User auf `data-testid="trip-detail-archive-confirm-yes"` klickt / Then wird `PATCH /api/trips/{id}/state` mit `{"archived": true}` gesendet, der Dialog schließt, `data-testid="trip-detail-status-badge"` zeigt `Archiviert` und `data-testid="trip-detail-action-pause"` ist nicht mehr im DOM.

- **AC-17:** Given ein archivierter Trip / When `TripHeader` gerendert ist / Then zeigt `data-testid="trip-detail-action-archive"` Label `Reaktivieren` und es gibt kein Element mit `data-testid="trip-detail-action-pause"` im DOM.

- **AC-18:** Given ein pausierter Trip / When `TripHeader` gerendert ist / Then zeigt `data-testid="trip-detail-action-pause"` Label `Fortsetzen` und `data-testid="trip-detail-action-archive"` ist weiterhin sichtbar mit Label `Archivieren`.

- **AC-19:** Given ein Trip wurde pausiert und die Seite wird danach neu geladen / When `/trips/[id]` erneut aufgerufen wird / Then zeigt `data-testid="trip-detail-status-badge"` `Pausiert` und `data-testid="trip-detail-action-pause"` zeigt `Fortsetzen` (persistierter Zustand wird korrekt geladen).

- **AC-20:** Given die Trip-Detail-Seite mit TripHeader / When diese gerendert ist / Then ist die Tab-Navigation (`data-testid="trip-detail-tab-list"`) weiterhin vollständig sichtbar und alle 6 Tabs sind klickbar (Step-1-Funktionalität unberührt).

## Known Limitations

- ~~**Scheduler ignoriert pausierten Status:** Der Briefing-Scheduler sendet weiterhin Reports auch für pausierte Trips.~~ **Erledigt durch Issue #995 (2026-07-03):** `trip_report_scheduler.py::_get_active_trips()` prüft jetzt `trip.paused_at` und überspringt pausierte Trips beim automatischen Versand (Go↔Python-Roundtrip analog `archived_at`/#805). Manueller Test-Versand und Alert-Dispatch bleiben bewusst unberührt. Siehe `docs/specs/modules/issue_995_mail_bugs_bundle.md`.
- **Trip-Liste filtert Archivierte nicht:** Die Trip-Übersicht (`/trips`) zeigt archivierte Trips weiterhin ohne Filter oder visuellen Unterschied. Ein Archiv-Filter oder eine Ausblend-Option kommt als separates Folge-Issue.
- **Cockpit-Status-Funktion bleibt dupliziert:** `routes/+page.svelte` (Cockpit) enthält eine eigene `getTripStatus`-Funktion mit nur 3 Status. Konsolidierung mit `deriveTripStatus` aus diesem Issue ist in einem separaten Tech-Debt-Ticket geplant — kein Import-Konflikt, da unterschiedliche Dateipfade und unterschiedliche Funktionsnamen.
- **`TODO(epic-135)` in `wizardState.svelte.ts`** bleibt bis zum letzten Sub-Issue von Epic #135 stehen — explizit nicht in Scope für #153.
- **Wizard-Save schickt keine Status-Flags:** `toTripPayload()` im Wizard übergibt `paused_at`/`archived_at` nicht. Das ist korrekt — der `CreateTripHandler` erwartet keine Pflichtfelder dafür, und neue Trips starten implizit als `planned` oder `active` je nach Stage-Datum (Default `nil`).
- **Idempotenz auf Timestamp-Ebene:** Ein zweites `paused: true` überschreibt `paused_at` mit einem neuen Timestamp. Das ist dokumentiertes Verhalten, kein Bug — falls ein stabiler Timestamp benötigt wird, muss ein Folge-Issue eine „setze nur wenn noch nicht gesetzt"-Semantik einführen.

## Changelog

- 2026-07-03: Known-Limitations-Eintrag „Scheduler ignoriert pausierten Status" als erledigt
  markiert — geschlossen durch Issue #995 (`trip_report_scheduler.py::_get_active_trips()`
  wertet jetzt `trip.paused_at` aus). Siehe `docs/specs/modules/issue_995_mail_bugs_bundle.md`.
- 2026-05-12: Initial spec — Issue #153 (Epic #135 Sub-Spec: Trip-Detail Header). Backend-Schema (`paused_at`/`archived_at`), neuer `PATCH /api/trips/{id}/state`-Endpoint, Pure-Function `deriveTripStatus` mit 4-Status-Hierarchie, `TripStatusBadge` (Pill-Wrapper), `TripHeader` (Breadcrumb + Badge + Actions + Confirm-Dialog), Route-Edit, 20 Acceptance Criteria im AC-N-Format, TestID-Inventar (9 IDs), Datei-Liste (12 Dateien, ~360 LoC), LoC-Override-Dokumentation, Known Limitations (6 Einträge).
