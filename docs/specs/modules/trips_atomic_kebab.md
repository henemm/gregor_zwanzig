---
entity_id: trips_atomic_kebab
type: module
created: 2026-05-31
updated: 2026-05-31
status: completed
version: "1.0"
tags: [frontend, atomic-design, svelte, trips, ux, kebab-menu]
---

# Spec: Trips-Liste — Atomic-Design-Migration + Kebab-UX-Redesign (Issues #477 + #486)

## Approval

- [x] Approved (2026-05-31)

## Purpose

Die Trips-Listenroute (`frontend/src/routes/trips/+page.svelte`) wird von shadcn-`ui/`-Importen auf die projektweite Atomic-Bibliothek migriert und dabei um zwei neue Molecule-Komponenten (`ReportConfigDialog`, `TestReportDialog`) entschlackt. Gleichzeitig erhält die Liste das im Design-System definierte Kebab-UX-Redesign: kontextsensitiver Primär-Button basierend auf `HomeTripStatus`, anklickbarer Trip-Name, "Pausieren/Reaktivieren" im Kebab und aktualisierter Footer-Counter.

## Source

- **File:** `frontend/src/routes/trips/+page.svelte`
- **Identifier:** `+page.svelte` (SvelteKit Route)
- **Neue Molecules:** `frontend/src/lib/components/molecules/ReportConfigDialog.svelte`, `frontend/src/lib/components/molecules/TestReportDialog.svelte`
- **Molecules-Index:** `frontend/src/lib/components/molecules/index.ts`

## Estimated Scope

- **LoC:** ~696 bestehend; nach Migration ~550 in `+page.svelte` + ~120 `ReportConfigDialog` + ~25 `TestReportDialog`
- **Files:** 4 (1 modifiziert, 2 neu, 1 modifiziert)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `$lib/components/molecules/ConfirmDialog.svelte` | Molecule (vorhanden) | Ersetzt den manuellen Lösch-Dialog (`ui/dialog`-Block Zeilen 477–493) |
| `$lib/components/molecules/ReportConfigDialog.svelte` | Molecule (neu) | Kapselt das ~120-Zeilen-Report-Konfig-Formular; importiert intern `ui/dialog`, `ui/checkbox`, `ui/select` |
| `$lib/components/molecules/TestReportDialog.svelte` | Molecule (neu) | Kapselt den ~25-Zeilen-Test-Briefing-Status-Dialog |
| `$lib/components/atoms/Btn` | Atom (vorhanden) | Primär-Button und Kebab-Aktionsbuttons |
| `$lib/components/atoms/Eyebrow` | Atom (vorhanden) | Ersetzt `EmptyState`-Überschrift im Leerzustand |
| `$lib/components/atoms/Stat` | Molecule/Atom (vorhanden) | Ersetzt die vier Desktop-Stat-Kacheln (Aktiv, Geplant, Abgeschlossen, Drafts) |
| `$lib/utils/tripStatus.ts` (`tripStatus`) | Utility (vorhanden) | Liefert `HomeTripStatus` (`aktiv|geplant|fertig|draft`) für Primär-Button-Logik |
| Natives HTML `<table>/<thead>/<tbody>/<tr>/<th>/<td>` | HTML | Ersetzt `ui/table`-Wrapper-Komponenten; gleiche Tailwind-Klassen |
| `$lib/components/molecules/index.ts` | Barrel-Export | Muss `ReportConfigDialog` und `TestReportDialog` neu exportieren |

## Implementation Details

### Teil A — Import-Migration (#477)

**Schritt 1 — `ui/table` → natives HTML**

Ersetze alle `Table.Root`, `Table.Header`, `Table.Body`, `Table.Row`, `Table.Cell`, `Table.Head`-Vorkommen in der Desktop-Tabelle (Zeilen 378–471) durch semantisch äquivalente native HTML-Elemente. Die Tailwind-Klassen der bestehenden `ui/table`-Wrapper werden 1:1 übernommen. Import Zeile 6 entfällt.

**Schritt 2 — `ui/dialog`-Lösch-Dialog → `ConfirmDialog`**

Ersetze den Dialog-Root-Block für die Trip-Löschung (Zeilen 477–493) durch:

```svelte
<ConfirmDialog
  open={deleteTarget !== null}
  title="Trip löschen"
  description="Diese Aktion kann nicht rückgängig gemacht werden."
  confirmLabel="Löschen"
  confirmVariant="destructive"
  onConfirm={handleDelete}
  onCancel={() => (deleteTarget = null)}
  onOpenChange={(o) => { if (!o) deleteTarget = null; }}
/>
```

**Schritt 3 — Report-Config-Dialog → `ReportConfigDialog`-Molecule**

Extrahiere das ~120-Zeilen-Formular (Zeit, Kanäle, Schwellwerte) in `frontend/src/lib/components/molecules/ReportConfigDialog.svelte`. Die neue Molecule-Datei importiert intern `$lib/components/ui/dialog`, `$lib/components/ui/checkbox`, `$lib/components/ui/select`. Props: `open: boolean`, `trip: Trip`, `onSave: (config) => void`, `onClose: () => void`. In `+page.svelte` verbleibt nur noch `import { ReportConfigDialog } from '$lib/components/molecules'`.

**Schritt 4 — Test-Report-Dialog → `TestReportDialog`-Molecule**

Extrahiere den ~25-Zeilen-Status-Rückmeldungs-Dialog in `frontend/src/lib/components/molecules/TestReportDialog.svelte`. Props: `open: boolean`, `result: string | null`, `onClose: () => void`. Import in `+page.svelte` analog zu Schritt 3.

**Schritt 5 — `EmptyState` → inline mit Atoms**

Ersetze den einzelnen `<EmptyState>`-Aufruf (Zeile 287) durch:

```svelte
<div class="flex flex-col items-center gap-3 py-12">
  <Eyebrow>Noch keine Trips</Eyebrow>
  <p class="text-sm text-muted-foreground mt-1">Erstelle deinen ersten Trip, um Briefings zu erhalten.</p>
  <Btn onclick={openCreate} variant="primary">Neuer Trip</Btn>
</div>
```

Import Zeile 20 (`ui/empty-state`) entfällt.

**Schritt 6 — Desktop-Stats → `Stat`-Molecule**

Ersetze die vier Desktop-Stat-Kacheln (Aktiv, Geplant, Abgeschlossen, Drafts, Zeilen 266–279) jeweils durch `<Stat label="..." value={...} />`.

**Schritt 7 — `molecules/index.ts` aktualisieren**

Füge zwei neue Named-Exports hinzu:

```typescript
export { default as ReportConfigDialog } from './ReportConfigDialog.svelte';
export { default as TestReportDialog } from './TestReportDialog.svelte';
```

### Teil B — UX-Redesign (#486)

**Schritt 8 — Primary Action auf `HomeTripStatus` umstellen**

Ersetze die bestehende `primaryLabel()`/`handlePrimaryAction()`-Logik (basiert auf `TripStatus`) durch eine neue Funktion auf Basis von `tripStatus()` (`HomeTripStatus`):

```
aktiv | geplant  → Label "Briefing-Vorschau",  Action: navigate(`/trips/${id}#preview`)
fertig + archived_at == null → Label "Archivieren",  Action: PATCH { archived: true }
fertig + archived_at != null → Label "Dearchivieren", Action: PATCH { archived: false }
draft               → Label "Fertigstellen",  Action: navigate(`/trips/${id}/wizard`)
```

**Schritt 9 — Trip-Name → klickbarer Link**

In der Desktop-Tabellen-Namensspalte den Plaintext-Namen durch ersetzen:

```svelte
<a href="/trips/{trip.id}" class="trip-link hover:underline">{trip.name}</a>
```

**Schritt 10 — Status-Caption neben Trip-Name**

Unmittelbar hinter dem `<a>`-Tag einfügen:

```svelte
<span class="status-caption font-mono text-[9px] uppercase tracking-widest text-[var(--g-ink-4)] ml-1">
  · {tripStatus(trip)}
</span>
```

**Schritt 11 — Kebab: "Pausieren/Reaktivieren" ergänzen**

Nach dem bestehenden "Bearbeiten"-Eintrag im Kebab-Menü einen neuen Eintrag einfügen:

```svelte
<button role="menuitem" onclick={() => handlePauseToggle(trip)}>
  {trip.paused_at ? 'Reaktivieren' : 'Pausieren'}
</button>
```

`handlePauseToggle` sendet `PATCH /api/trips/{id}` mit `{ paused: !trip.paused_at }`.

**Schritt 12 — "Report-Konfiguration" → "Alerts justieren"**

Im Kebab-Menü den Label-Text des Report-Konfiguration-Eintrags von `"Report-Konfiguration"` auf `"Alerts justieren"` ändern.

**Schritt 13 — Footer-Counter aktualisieren**

Zeile 469 von:
```
{filteredTrips.length} von {trips.length} Trips
```
auf:
```svelte
<span class="font-mono text-xs uppercase tracking-widest">
  {filteredTrips.length} Trips · {trips.length - filteredTrips.length} versteckt
</span>
```

## Expected Behavior

- **Input:** Bestehende Trips-Route mit shadcn-`ui/`-Importen und handgebautem Kebab
- **Output:** Identisch aussehende Route ohne direkte `ui/`-Importe in `+page.svelte`; Primär-Button und Kebab-Menü nach `#486`-Design; alle `data-testid`-Attribute unverändert
- **Side effects:**
  - `ReportConfigDialog` und `TestReportDialog` sind neue Molecules und ab sofort app-weit wiederverwendbar
  - `molecules/index.ts` exportiert zwei neue Einträge
  - Alle bestehenden E2E-Tests und Unit-Tests laufen weiter grün, da keine `data-testid`s entfernt werden

## Acceptance Criteria

**AC-1:** Given die migrierte `+page.svelte`, When der Datei-Inhalt auf `$lib/components/ui/`-Importe geprüft wird, Then existieren keine Importe von `ui/table`, `ui/dialog`, `ui/checkbox`, `ui/select` oder `ui/empty-state` mehr in dieser Datei.
- Test: (populated after /tdd-red)

**AC-2:** Given die migrierte Desktop-Tabelle, When die Trips-Seite im Browser geladen wird, Then sind alle Spalten (Name, Etappen, Zeitraum, Primär-Button, Kebab) sichtbar und optisch identisch zur Vorversion; `svelte-check` und alle Unit-Tests laufen grün.
- Test: (populated after /tdd-red)

**AC-3:** Given ein Trip in der Desktop-Tabelle, When der Trip-Name gerendert wird, Then ist er ein `<a href="/trips/{id}">` mit sichtbarem Underline beim Hover.
- Test: (populated after /tdd-red)

**AC-4:** Given Trips mit unterschiedlichen Status (`aktiv`, `geplant`, `fertig` ohne/mit `archived_at`, `draft`), When der Primär-Button gerendert wird, Then zeigt er "Briefing-Vorschau" (aktiv/geplant), "Archivieren" (fertig, nicht archiviert), "Dearchivieren" (fertig, archiviert), "Fertigstellen" (draft).
- Test: (populated after /tdd-red)

**AC-5:** Given ein aktiver oder geplanter Trip, When das Kebab-Menü geöffnet wird, Then enthält es einen Eintrag "Pausieren"; Given ein pausierter Trip, Then enthält es stattdessen "Reaktivieren".
- Test: (populated after /tdd-red)

**AC-6:** Given die migrierte `+page.svelte`, When der Lösch-Dialog ausgelöst wird, Then verwendet er `ConfirmDialog` aus `$lib/components/molecules`; der Report-Konfig-Dialog ist `ReportConfigDialog` und der Test-Briefing-Dialog ist `TestReportDialog` — kein `ui/dialog`-Import in `+page.svelte`.
- Test: (populated after /tdd-red)

**AC-7:** Given die migrierte Trips-Seite, When die Playwright-E2E-Tests `bug-282-295-trips-list-redesign.spec.ts`, `trips.spec.ts` und `issue-268-trips-mobile-card-stack.spec.ts` laufen, Then bestehen alle ohne Anpassung; alle `data-testid`-Attribute (`trip-card-stack`, `trip-card`, `trip-card-content-btn`, `trip-card-menu-btn`, `trip-edit-btn`, `trip-action-sheet`) sind erhalten.
- Test: (populated after /tdd-red)

**AC-8:** Given die migrierte Seite, When das visuelle Ergebnis der Desktop-Trips-Liste verglichen wird, Then entspricht es der Soll-Vorlage `docs/design-requests/issue_15_atomic_design/spec/screen-trips.jsx`.
- Test: (populated after /tdd-red)

## Known Limitations

- `ui/checkbox` und `ui/select` haben keine Atom-Pendants in der aktuellen Bibliothek. Sie bleiben **innerhalb** von `ReportConfigDialog.svelte` — `+page.svelte` ist damit frei, die Molecules sind es nicht. Ein separates Refactoring ist nötig, sobald Atom-Pendants existieren.
- "Duplizieren" ist explizit nicht im Scope, da kein Backend-Endpunkt vorhanden ist. Ein Follow-up-Issue ist zu erstellen.
- Das `loc_limit_override` muss vor Implementierungsbeginn auf mindestens 400 gesetzt werden (Gesamtänderung über 250 LoC erwartet).

## Changelog

- 2026-05-31: Implementation complete (Issues #477 + #486, Workflow trips-atomic-kebab). Trips-Liste migriert auf Atomic-Design: `ReportConfigDialog` und `TestReportDialog` als wiederverwendbare Molecules, keine direkten `ui/`-Importe in `+page.svelte`, Kebab-UX mit Pausieren/Reaktivieren, primärer Button basierend auf `HomeTripStatus`.
- 2026-05-31: Initial spec created (Issues #477 + #486, Workflow trips-atomic-kebab)
