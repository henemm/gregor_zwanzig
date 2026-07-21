---
entity_id: issue_90_trip_overview_icons
type: module
created: 2026-05-15
updated: 2026-05-15
status: draft
version: "1.0"
tags: [frontend, ui, trips, design-system]
---

# Issue #90 — Trip-Übersicht: Aktionsicons gruppieren

## Approval

- [ ] Approved

## Purpose

Die Aktionsleiste pro Trip-Zeile zeigt aktuell 6 Icons in einer Reihe mit gleichem 2 px-Abstand und durchmischter Reihenfolge. Die drei Aktionsklassen (Editieren / Verschicken / Löschen) sind dadurch optisch nicht erkennbar. Diese Änderung gruppiert die Icons visuell durch größere Abstände zwischen den Gruppen und korrigiert die DOM-Reihenfolge so, dass jedes Icon in seiner semantischen Gruppe steht.

## Source

- **File:** `frontend/src/routes/trips/+page.svelte`
- **Identifier:** Tabellenzeile in `#each filteredTrips`, Aktions-Cell (Z. 257–266)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `$lib/components/ui/button` (Btn) | Komponente | Rendert die Icon-Buttons |
| `@lucide/svelte` (BellIcon, CloudSunIcon, PlayIcon, PencilIcon, Trash2Icon) | Icon-Lib | Visualisiert die Aktionen |
| Tailwind Layout-Klassen (`inline-flex`, `gap-*`, `hidden sm:inline-flex`) | Styling | Anordnung und Responsive |

## Implementation Details

**Vorher (Z. 258–265 in `frontend/src/routes/trips/+page.svelte`):**

```svelte
<div class="inline-flex flex-wrap justify-end gap-0.5">
  <Btn variant="outline" ... title="Report-Konfiguration"><BellIcon /></Btn>
  <Btn variant="outline" ... title="Wetter-Konfiguration"><CloudSunIcon /></Btn>
  <Btn variant="outline" class="hidden sm:inline-flex" title="Test Morgen-Report"><PlayIcon /></Btn>
  <Btn variant="outline" class="hidden sm:inline-flex" title="Test Abend-Report"><PlayIcon /></Btn>
  <Btn variant="ghost" data-testid="trip-edit-btn" title="Bearbeiten"><PencilIcon /></Btn>
  <Btn variant="ghost" class="hidden sm:inline-flex" title="Löschen"><Trash2Icon /></Btn>
</div>
```

**Nachher:**

```svelte
<div class="inline-flex flex-wrap justify-end gap-3">
  <!-- Edit-Gruppe -->
  <div class="inline-flex gap-0.5">
    <Btn variant="outline" ... title="Report-Konfiguration"><BellIcon /></Btn>
    <Btn variant="outline" ... title="Wetter-Konfiguration"><CloudSunIcon /></Btn>
    <Btn variant="ghost" data-testid="trip-edit-btn" title="Bearbeiten"><PencilIcon /></Btn>
  </div>
  <!-- Send-Gruppe (auf Mobile versteckt) -->
  <div class="hidden sm:inline-flex gap-0.5">
    <Btn variant="outline" ... title="Test Morgen-Report"><PlayIcon /></Btn>
    <Btn variant="outline" ... title="Test Abend-Report"><PlayIcon /></Btn>
  </div>
  <!-- Delete-Gruppe (auf Mobile versteckt) -->
  <div class="hidden sm:inline-flex gap-0.5">
    <Btn variant="ghost" title="Löschen"><Trash2Icon /></Btn>
  </div>
</div>
```

**Änderungen im Detail:**

1. **Äußerer Container** behält `inline-flex flex-wrap justify-end`, der Gap wechselt von `gap-0.5` (2 px) auf `gap-3` (12 px).
2. **Drei innere Container** mit `inline-flex gap-0.5` (Edit-, Send-, Delete-Gruppe).
3. **Pencil-Icon wandert** aus der vierten Position in die Edit-Gruppe (zwischen CloudSun und Send-Gruppe entfällt es als trennendes Element).
4. **Responsive Hiding** wandert von einzelnen Buttons auf die Gruppen-Container (`hidden sm:inline-flex` auf Send- und Delete-Container).
5. **Button-Varianten, Tooltips, Handler, `data-testid`-Attribute, Icon-Komponenten** bleiben 1:1 unverändert.

## Expected Behavior

- **Input:** Liste `filteredTrips`, jeweils ein Trip mit 6 verfügbaren Aktionen.
- **Output:** Pro Trip-Zeile sind die 6 Aktions-Icons in drei optisch unterscheidbaren Gruppen sichtbar (Edit links, Send Mitte, Delete rechts), getrennt durch einen sichtbar größeren Abstand (12 px) als der Abstand innerhalb einer Gruppe (2 px).
- **Side effects:** Keine. Klick-Handler, Test-IDs und Tooltips identisch zum Vorher-Zustand.

## Acceptance Criteria

- **AC-1:** Given die Trip-Übersicht ist auf Viewport ≥ 640 px geladen / When eine Trip-Zeile sichtbar ist / Then sind die 6 Icons in drei nebeneinanderstehenden Container-Divs gerendert (Edit-Gruppe mit 3 Buttons, Send-Gruppe mit 2 Buttons, Delete-Gruppe mit 1 Button), wobei der äußere Container die Klasse `gap-3` und die inneren Container die Klasse `gap-0.5` tragen.
  - Test: (populated after /tdd-red)

- **AC-2:** Given die Trip-Übersicht ist auf Viewport < 640 px (Mobile) geladen / When eine Trip-Zeile sichtbar ist / Then sind nur die drei Edit-Icons (BellIcon, CloudSunIcon, PencilIcon) sichtbar — Send- und Delete-Gruppen-Container sind via `hidden sm:inline-flex` ausgeblendet und erzeugen keine Layout-Lücke.
  - Test: (populated after /tdd-red)

- **AC-3:** Given die DOM-Reihenfolge der Buttons innerhalb der Aktions-Cell / When die Buttons in Lesereihenfolge inspiziert werden / Then ist die Sequenz: BellIcon → CloudSunIcon → PencilIcon → PlayIcon(7) → PlayIcon(18) → Trash2Icon (Pencil steht in der Edit-Gruppe, nicht mehr zwischen Send und Delete).
  - Test: (populated after /tdd-red)

- **AC-4:** Given existierende Playwright-Tests, die `data-testid="trip-edit-btn"` verwenden / When die Tests nach der Änderung laufen / Then bleiben sie grün — der Selektor existiert weiterhin am Pencil-Button mit identischem Handler `openEdit(trip)`.
  - Test: (populated after /tdd-red)

## Known Limitations

- **Mobile-Viewport (`<sm`):** Es bleibt nur die Edit-Gruppe sichtbar; die Gruppierung trägt dort keine Information, das Layout wirkt aber identisch zur ungrupperten Variante (3 Icons mit `gap-0.5`). Kein UX-Regress.
- **Button-Varianten-Mix:** Die Edit-Gruppe enthält weiterhin sowohl `outline` (Bell, CloudSun) als auch `ghost` (Pencil). Eine Harmonisierung ist außerhalb des Scope dieser Änderung — Issue #90 betrifft ausschließlich Gruppierung, nicht Farbsystem.

## Changelog

- 2026-05-15: Initial spec created (Issue #90)
