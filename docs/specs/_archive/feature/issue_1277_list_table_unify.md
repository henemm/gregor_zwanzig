---
entity_id: issue_1277_list_table_unify
type: feature
created: 2026-07-16
updated: 2026-07-16
status: draft
version: "1.0"
tags: [frontend, sveltekit, ui, organisms, trips, compare, issue-1277]
---

<!-- Issue #1277 — Listen-Übersichten vereinheitlichen (ListTable) -->

# Feature #1277 — Listen-Übersichten vereinheitlichen (ListTable)

## Approval

- [ ] Approved

## Purpose

`/trips` und `/compare` zeigen auf dem Desktop aktuell unterschiedliche
Layouts für inhaltlich identische Listen (Trip-Tabelle vs. Compare-
Kachel-Grid). Ein geteiltes Tabellen-Organism `ListTable` (+ Sub-Organismen
`ListTableRow`, `ListActionsMenu`, `ListNameCell`) ersetzt beide Desktop-
Ansichten durch dieselbe dichte, scanbare Tabellen-Darstellung — Fachlogik
bleibt screen-spezifisch über `columns`/`rowActions`-Props injiziert, Chassis
und Zeilen-Verhalten sind identisch. PO-Entscheid 2026-07-16 (Henning): „Führe
beide als Tabelle. Verwende den gleichen Code / Atoms / Elemente." Mobile ist
ausdrücklich **nicht** betroffen (Known Limitations).

## Source

- **File:** `frontend/src/lib/components/organisms/ListTable.svelte` (NEU)
- **Identifier:** `ListTable`-Svelte-Komponente + Sub-Organismen
  `ListTableRow`, `ListActionsMenu`, `ListNameCell` (alle NEU, gleicher Ordner)
- Konsumiert von: `frontend/src/routes/trips/+page.svelte` und
  `frontend/src/routes/compare/+page.svelte` (jeweils nur der Desktop-Bereich)

**Schicht:** reines Frontend (`frontend/src/...`, SvelteKit). Kein Go-API-
und kein Python-Core-Code betroffen — keine Backend-Endpunkte, keine
Datenmodell-Änderungen, keine neuen API-Calls.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/atoms/{Card,Dot,Btn}.svelte` | Atom | `ListTable` baut auf bestehenden Atoms auf, kein neues Atom nötig |
| `frontend/src/lib/utils/tripStatus.ts` (`deriveTripStatus`, `tripStatus`) | Util | Liefert Status/Dot-Farbe für die Trip-`columns` |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts` (`deriveStatusFromPreset`, `presetLocationsLabel`, `presetProfileLabel`, `presetTileScheduleLabel`, `relativeLastSent`, `presetChannels`, `compareActions`) | Util | Liefern Status/Spaltendaten/Overflow-Aktionen für die Compare-`columns` |
| `frontend/src/lib/components/alerts-tab/AlertMetricTable.svelte` + `AlertMetricRow.svelte` | Vorbild | Struktureller Bauplan (Card-Wrapper + Grid-Header + separate Row-Komponente) für Chassis/Grid-Aufbau von `ListTable`/`ListTableRow` |
| `frontend/src/lib/components/compare/CompareKebab.svelte` | Vorbild | Overflow-Menü-Muster (Positionierung, `role="menu"`) für `ListActionsMenu`; Portal-/Flip-Logik zusätzlich aus `trips/+page.svelte` (`openMenuAtBtn`, `$effect`-Flip-Korrektur, Zeilen 89–124) übernehmen |
| `frontend/src/lib/components/compare/CompareTile.svelte` | Bleibt unverändert | Trägt weiterhin Mobile-Kachelliste (`dense={true}`) + Home-Kachel (`_home/CompareKachel.svelte`) — wird NICHT angefasst |
| `frontend/src/lib/components/organisms/index.ts` | Barrel | `ListTable` + Sub-Organismen dort exportieren, analog bestehender Organismen |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/organisms/ListTable.svelte` | CREATE | Geteiltes Tabellen-Organism (Chassis, Kopf, Zebra, Hover, Zeilen-Klick, Empty-State). API: `columns`, `rows`, `getRowId`, `onRowClick`, `rowActions`, `rowPrimary`, `onAction`, `emptyText` |
| `frontend/src/lib/components/organisms/ListTableRow.svelte` | CREATE | Zeile: Name-Zelle-Slot, dynamische Spalten aus `columns[].render(row)`, inline Quick-Action (`rowPrimary`), Kebab-Trigger |
| `frontend/src/lib/components/organisms/ListActionsMenu.svelte` | CREATE | Overflow-Menü (⋯), Positionierung/Portal analog `CompareKebab.svelte` + `trips/+page.svelte` Flip-Korrektur |
| `frontend/src/lib/components/organisms/ListNameCell.svelte` | CREATE | Status-Dot + Name + Status-Label; `dotColor` als Prop (Trip- und Compare-Paletten unterscheiden sich) |
| `frontend/src/routes/trips/+page.svelte` | MODIFY | Desktop-Bereich (Z. ~439–517, `<div class="hidden desktop:block">`) durch `ListTable`-Aufruf ersetzen (Spalten: Name · Etappen · Zeitraum; Overflow-Menü = bestehende 6 Einträge #486; inline „Briefing senden" nur bei `aktiv`). Mobile-Bereich (Z. ~405–438) unverändert |
| `frontend/src/routes/compare/+page.svelte` | MODIFY | Desktop-Bereich (Z. ~103–116, `<CompareGrid .../>`-Aufruf) durch `ListTable`-Aufruf ersetzen (Spalten: Name · Orte · Profil · Kanäle · Zeitplan; Overflow-Menü = `compareActions(status)`; Zeilen-Klick öffnet Detail-Hub `/compare/{id}`, nicht die Tages-Vorschau). Mobiler Kachel-Stack (Z. ~118–148) unverändert |
| `frontend/src/lib/components/compare/CompareGrid.svelte` | DELETE | Nur noch von `compare/+page.svelte` konsumiert — nach Ersatz verwaist. Vor Löschen mit Grep bestätigen, dass kein weiterer Konsument existiert |
| `frontend/src/routes/trips/issue_477_486.test.ts` | MODIFY | Source-Regex-Test auf `status-caption`-Klasse im Desktop-Tabellenbereich (Z. ~172ff) an neues `ListTable`-Markup anpassen |
| `frontend/src/lib/components/compare/__tests__/issue_462.test.ts` | MODIFY/DELETE | Prüft `CompareGrid`-spezifisches Verhalten — nach dessen Entfernung anpassen oder löschen (Kern-Schicht darf nicht rot bleiben) |
| `frontend/src/lib/components/compare/__tests__/issue_490_compare_grid.test.ts` | DELETE | Testet ausschließlich `CompareGrid`-Markup, das mit dieser Änderung entfällt |
| `frontend/src/lib/components/compare/__tests__/list_toggle_read_modify_write.test.ts` | MODIFY | Prüft Read-Modify-Write-Verhalten beim Pause-Toggle über `CompareGrid` — Testpfad auf `ListTable`/`ListActionsMenu` umstellen, Fachlogik-Assertion (Read-Modify-Write) bleibt erhalten |
| `frontend/e2e/compare-flow-navigation.spec.ts` | MODIFY | Desktop-Anteile nutzen `[data-testid="compare-tile-{id}"]:visible` — auf neue `ListTable`-Zeilen-Selektoren umstellen. Mobile-Anteile unverändert |
| `frontend/e2e/compare-mobile-vervollstaendigung.spec.ts` | MODIFY | Nur falls Desktop-Anteile betroffen sind (Grep vor Umbau zur Bestätigung) — Mobile-Anteile bleiben unverändert grün |
| `frontend/e2e/design-compliance-group-a.spec.ts` | MODIFY | Desktop-Compare-Screenshots/Selektoren auf `ListTable` umstellen |
| `frontend/e2e/bug-626-compare-menu-actions.spec.ts` | MODIFY | Nutzt `[data-testid="compare-tile"]` / `[data-testid="compare-tile-kebab"]` für das Desktop-Overflow-Menü — auf `ListTable`/`ListActionsMenu`-Selektoren umstellen, Kebab-Aktions-Assertions (`compareActions(status)`) bleiben fachlich identisch |

**Nicht angefasst (explizit, Trip/Compare-Teilungs-Invariante):**
`frontend/src/lib/components/compare/CompareTile.svelte`,
`frontend/src/lib/components/compare/CompareKebab.svelte` (nur als Vorbild
gelesen, nicht verändert) — beide bleiben für Mobile + Home-Kachel bestehen.

### Estimated Scope

- **Files:** ~13 (4 neu, ~9 geändert/gelöscht)
- **LoC:** ~+250/-120 (grobe Schätzung: 4 neue Organism-Dateien + 2 Seiten-
  Umbauten + Test-Anpassungen)
- **Effort:** medium

## Implementation Details

### `ListTable`-API

```
ListTable({
  columns,      // [{ key, header, align?, width?, render(row) }]
  rows,         // Daten-Array
  getRowId,     // (row) => stabile Key/Id
  onRowClick,   // (row) => void — ganze Zeile klickbar → Detail/Setup
  rowActions,   // (row) => [{ key, label, danger? }] | null — Overflow-Menü (⋯)
  rowPrimary,   // (row) => { label, onClick } | null — inline Quick-Action
  onAction,     // (key, row) => void — Auswahl aus dem Overflow-Menü
  emptyText,    // Text bei leerer Liste
})
```

### Gemeinsames Zeilen-Verhalten (beide Übersichten)

1. Ganze Zeile klickbar → Detail/Setup (`onRowClick`); Hover-Highlight
   (`--g-card-alt`), Zebra-Streifen (`--g-paper-deep` auf ungeraden Zeilen),
   Chevron (`›`) am rechten Rand.
2. Alle Sekundär-Aktionen in EINEM Overflow-Menü (`⋯`) — kein
   Icon-Geschwader.
3. Aktive Einträge zeigen zusätzlich EINE inline Quick-Action „Briefing
   senden" links vom `⋯` (`rowPrimary`).
4. Tabellenkopf mono-caps auf `--g-paper-deep`; rechte Spalte immer
   „Aktionen".

### Spalten pro Screen (Fachlogik lebt ausschließlich hier, nicht im Chassis)

- **Trips:** Name (Status-Dot + Label) · Etappen · Zeitraum. Overflow-Menü
  unverändert zu #486 (Briefing senden nur bei `aktiv` · Email-Vorschau ·
  Alert-Konfiguration · Wetter-Metriken · Bearbeiten · Löschen).
- **Orts-Vergleiche:** Name (Status-Dot + Label) · Orte
  (`presetLocationsLabel`) · Profil (`presetProfileLabel`) · Kanäle
  (`presetChannels`, Mono-Pills) · Zeitplan (`presetTileScheduleLabel` +
  „zuletzt {relativeLastSent}", bei `draft` „Setup unvollständig"). Overflow-
  Menü = `compareActions(status)` (unverändert). Zeilenklick →
  `goto('/compare/' + preset.id)` (Detail-Hub, NICHT die Tages-
  Briefing-Vorschau).

### Status-Paletten (unverändert übernommen)

- Trip: aktiv `--g-accent` · geplant `#3d6b3a` · fertig `--g-ink-3` · draft
  `--g-ink-4`
- Vergleich: aktiv `--g-good` · pausiert `--g-ink-3` · draft `--g-ink-4`

### Vorgehen

1. `ListTable`/`ListTableRow`/`ListActionsMenu`/`ListNameCell` neu anlegen
   (Bauplan: `AlertMetricTable.svelte` + `AlertMetricRow.svelte` für
   Chassis/Grid; `CompareKebab.svelte` + `trips/+page.svelte`
   `openMenuAtBtn`/Flip-`$effect` für das Overflow-Menü).
2. `trips/+page.svelte`: Desktop-`<div class="hidden desktop:block">`-Block
   durch `<ListTable columns={tripColumns} rows={filteredTrips} .../>`
   ersetzen. Bestehende Handler (`runTestReport`, `openReportConfig`,
   `openEdit`, `deleteTarget`, `handlePauseToggle`) bleiben — sie werden nur
   über `onAction`/`rowPrimary` statt Inline-Markup verdrahtet.
3. `compare/+page.svelte`: `<CompareGrid bind:presets {searchQuery} />` durch
   `<ListTable columns={compareColumns} rows={filteredPresets} .../>`
   ersetzen. Aktions-Logik aus `CompareGrid.svelte` (`togglePause`,
   `confirmSend`, `archivePreset`, `confirmDelete`) in `compare/+page.svelte`
   verschieben oder als Utility mitziehen, danach `CompareGrid.svelte`
   löschen.
4. Betroffene Tests (Vitest + Playwright) anpassen — siehe Affected-Files-
   Tabelle. Test-Politik: Kern-Schicht muss 100 % grün bleiben, veraltete
   Tests werden gelöscht statt rot liegengelassen.

## Expected Behavior

- **Input:** Trip-Liste (`Trip[]`) bzw. ComparePreset-Liste
  (`ComparePreset[]`) wie bisher aus `+page.server.ts`/`load()`.
- **Output:** Desktop (`≥900px`) zeigt für beide Screens eine `ListTable`
  mit identischem Zeilen-Verhalten (Zebra, Hover, Chevron, Kebab, inline
  Quick-Action). Mobile (`<900px`) unverändert Karten-Stapel bzw.
  `CompareTile dense`.
- **Side effects:** keine neuen API-Calls — alle bestehenden Mutationen
  (Archivieren, Pause-Toggle, Löschen, Senden) laufen über dieselben
  Endpunkte wie vorher, nur die aufrufende UI-Schicht ändert sich.

## Acceptance Criteria

- **AC-1:** Given der Organism-Ordner `frontend/src/lib/components/organisms/`
  / When `ListTable`, `ListTableRow`, `ListActionsMenu`, `ListNameCell`
  implementiert sind / Then existiert für keinen der vier Bausteine ein
  Fork oder eine Kopie in `trips/` oder `compare/` — beide Screens
  importieren exakt dieselben vier Dateien.
  - Test: Statischer Grep auf `from '$lib/components/organisms'` in
    `trips/+page.svelte` und `compare/+page.svelte` bestätigt denselben
    Importpfad; kein zweites `ListTable*.svelte` existiert im Repo.

- **AC-2:** Given ein eingeloggter Nutzer mit mindestens 2 Trips und 2
  Orts-Vergleichen / When er `/trips` bzw. `/compare` auf einem Desktop-
  Viewport (≥900px) öffnet / Then sieht er auf beiden Seiten dieselbe
  Tabellen-Optik: Zebra-Streifen auf ungeraden Zeilen, Hover-Highlight beim
  Überfahren einer Zeile, Chevron rechts, und bei genau den aktiven
  Einträgen eine zusätzliche inline „Briefing senden"-Aktion links vom
  Kebab-Button.
  - Test: Playwright öffnet beide Seiten auf Desktop-Viewport, fährt eine
    Zeile mit der Maus an und prüft den Hover-Hintergrund, klickt auf eine
    aktive Zeile und beobachtet, dass „Briefing senden" sichtbar ist,
    während eine pausierte/fertige Zeile diese Aktion nicht zeigt.

- **AC-3:** Given eine Trip-Zeile bzw. eine Compare-Zeile auf Desktop /
  When der Nutzer auf den Kebab (⋯) klickt / Then öffnet sich bei Trips ein
  Menü mit genau den 6 Einträgen aus #486 (Briefing jetzt senden ·
  Email-Vorschau · Alert-Konfiguration · Wetter-Metriken · Bearbeiten ·
  Löschen) und bei Compare ein Menü mit den Einträgen aus
  `compareActions(status)` für den jeweiligen Status.
  - Test: Playwright klickt den Kebab je einer aktiven Trip-Zeile und einer
    aktiven/pausierten/Draft-Compare-Zeile und zählt/liest die sichtbaren
    Menüpunkt-Texte gegen die erwartete Liste.

- **AC-4:** Given eine Orts-Vergleichs-Zeile auf Desktop / When der Nutzer
  auf die Zeile (außerhalb des Kebabs) klickt / Then navigiert er zum
  Detail-Hub `/compare/{id}` (Übersicht-Tab) — NICHT zur
  Tages-Briefing-Vorschau.
  - Test: Playwright klickt eine Compare-Zeile und prüft
    `page.url()` == `/compare/{id}` (bzw. Redirect auf den Default-Tab
    der Detailseite), nicht `?tab=vorschau`.

- **AC-5:** Given der Umbau ist abgeschlossen / When das Repo nach
  Desktop-Tabellen-/Kachel-Markup außerhalb von `ListTable*` durchsucht
  wird / Then existiert weder ein eigenständiges Inline-Grid in
  `trips/+page.svelte` noch `CompareGrid.svelte` mehr im Repo.
  - Test: `git status`/Grep bestätigt, dass `CompareGrid.svelte` gelöscht
    ist und keine verbleibenden Importe dieser Datei existieren; visuelle
    Kontrolle beider Desktop-Seiten zeigt nur noch `ListTable`.

- **AC-6:** Given ein Nutzer auf einem mobilen Viewport (<900px) / When er
  `/trips` bzw. `/compare` öffnet / Then sieht er unverändert die
  bestehenden Karten-Layouts (`trip-card-stack` bzw. `CompareTile dense`)
  — keine Tabellenzeilen, kein visueller Unterschied zum Verhalten vor
  diesem Feature.
  - Test: Playwright öffnet beide Seiten mit mobilem Viewport (z. B.
    390×844) und prüft, dass `[data-testid="trip-card-stack"]` bzw. die
    `CompareTile`-Kacheln sichtbar sind und keine `ListTable`-Zeile im DOM
    vorhanden ist.

- **AC-7:** Given bestehende `data-testid`-Selektoren, die NICHT
  Desktop-spezifisches Kachel-/Grid-Markup betreffen (z. B.
  `trip-card-stack`, `trip-card-menu-btn`, `trip-action-sheet`,
  `top-app-bar-new-compare`) / When der Umbau abgeschlossen ist / Then
  bleiben diese Selektoren unverändert vorhanden und funktionsfähig.
  - Test: Bestehende Mobile-Playwright-Suiten (u. a.
    `compare-mobile-vervollstaendigung.spec.ts`) laufen ohne Anpassung
    weiterhin grün.

- **AC-8:** Given die vier E2E-Spec-Dateien
  `compare-flow-navigation.spec.ts`, `compare-mobile-vervollstaendigung.spec.ts`,
  `design-compliance-group-a.spec.ts`, `bug-626-compare-menu-actions.spec.ts`,
  die aktuell `[data-testid="compare-tile-{id}"]`/`compare-tile-kebab` für
  die DESKTOP-Ansicht referenzieren / When der Umbau abgeschlossen ist /
  Then sind ihre Desktop-Anteile auf die neuen `ListTable`-Zeilen-Selektoren
  umgestellt und laufen grün gegen das neue Markup, während ihre
  Mobile-Anteile (die weiterhin `CompareTile`/Kachel-Selektoren nutzen)
  unverändert und ohne Codeänderung grün bleiben.
  - Test: `npx playwright test compare-flow-navigation.spec.ts
    compare-mobile-vervollstaendigung.spec.ts design-compliance-group-a.spec.ts
    bug-626-compare-menu-actions.spec.ts` läuft komplett grün gegen Staging
    nach dem Umbau; Diff der vier Dateien zeigt Änderungen ausschließlich in
    den als „Desktop" markierten Testblöcken/Selektoren, keine Änderung an
    mobilen `test.describe`-Blöcken.

## Known Limitations

- **Mobile bleibt unverändert Kachel-/Karten-basiert für beide
  Übersichten** (`TripCardM`-Stack bzw. `CompareTile dense`). Dies ist
  bewusst so spezifiziert (body-30, Abschnitt „Mobile") — nur die
  Desktop-Ansicht wird auf `ListTable` vereinheitlicht. Kein Nacharbeiten
  erforderlich, keine offene Frage.
- `CompareTile`/`CompareKebab` bleiben als eigenständige Komponenten für
  Mobile-Kachelliste und Home-Kachel bestehen — sie sind bewusst NICHT Teil
  der `ListTable`-Migration (Trip/Compare-Teilungs-Invariante: geteilt ist
  die Tabelle, nicht die Mobile-Kachel).
- `CompareGrid.svelte` wird gelöscht, nicht umgebaut — vor dem Löschen muss
  per Grep bestätigt werden, dass kein weiterer Konsument (z. B. eine
  Vorschau-Komponente) existiert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine UI-Konsolidierung auf Basis einer bereits
  PO-freigegebenen, verbindlichen Design-Spec (body-30/Issue #1277). Es wird
  keine neue Architekturschicht, kein neues Datenmodell und kein neuer
  Kommunikationspfad eingeführt — lediglich zwei bestehende Desktop-Listen-
  Darstellungen auf ein gemeinsames, bereits etabliertes Organism-Muster
  (vgl. `AlertMetricTable`/`AlertMetricRow`) vereinheitlicht. Die
  strukturelle Leitplanke (Trip/Compare-Code-Teilung) ist bereits in
  CLAUDE.md verankert, kein separater ADR nötig.

## Changelog

- 2026-07-16: Initial spec erstellt — Issue #1277, PO-Entscheid 2026-07-16
