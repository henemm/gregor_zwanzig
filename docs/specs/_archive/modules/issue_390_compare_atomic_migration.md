---
entity_id: issue_390_compare_atomic_migration
type: module
created: 2026-05-26
updated: 2026-05-26
status: active
version: "1.0"
tags: [compare, atomic-design, migration, refactoring, svelte, epic-368, issue-390]
---

# Issue #390 — Compare-Screen: Migration auf Atomic-Bibliothek (Epic #368 Phase 2, 5/6)

## Approval

- [x] Approved

## Zweck

Der Compare-Screen (`/compare`) verwendet an drei Stellen inline definierte Hilfskomponenten
(`ChipBtn`, `CompareField`, `FocusBadge`), die funktional bereits durch fertige Bausteine
der Atomic-Bibliothek abgedeckt werden. Dieses Modul migriert diese drei Inline-Helfer auf
`Pill` (atoms) und `Field` (molecules), sodass Design-System-Tokens konsequent genutzt werden,
Duplikate aus dem Codebase verschwinden und der Compare-Screen am einheitlichen Erscheinungsbild
des Atomic-Design-Systems teilnimmt. Page-lokale Komposita (CompareMatrix, HourlyMatrix,
RecommendationBanner u. a.) bleiben byte-gleich.

## Quelle / Source

**Geänderte Dateien:**
- `frontend/src/routes/compare/+page.svelte` — Mobile Chip-Row: inline `<button class="...">` → `Pill`-Toggle
- `frontend/src/lib/components/compare/PresetHeader.svelte` — 5 Felder (Datum Von/Bis, Horizont, Profil, …): `div+label+input` → `Field`
- `frontend/src/lib/components/compare/GroupSection.svelte` — FocusBadge addieren: `Pill tone="accent"` für Activity-Profile != `allgemein`

**NICHT ändern:**
- `frontend/src/lib/components/compare/CompareMatrix.svelte`
- `frontend/src/lib/components/compare/HourlyMatrix.svelte`
- `frontend/src/lib/components/compare/RecommendationBanner.svelte`
- `frontend/src/lib/components/compare/CompareLocationsRail.svelte`
- `frontend/src/lib/components/compare/CompareSubscriptionsPanel.svelte`
- `frontend/src/lib/components/compare/LocationRow.svelte`
- `frontend/src/lib/components/compare/SubRow.svelte`

> **Schicht-Hinweis:** Ausschließlich Frontend-Schicht (`frontend/src/`). Go-API und Python-Backend werden nicht angefasst.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `$lib/components/ui/pill/index.js` | Svelte-Atom | Toggle-Chips in der Mobile Chip-Row (`+page.svelte`); in `GroupSection` wird stattdessen das Dot-Pattern verwendet |
| `$lib/components/molecules/index.js` — `Field` | Svelte-Molecule | Label+Input/Select-Wrapper mit konsistenter Abstands- und Typografie-Behandlung |
| `profileSignature` | Hilfsfunktion (bereits importiert) | Liefert `icon` und `eyebrow` für ein Activity-Profile — wird in GroupSection genutzt |
| `contrast-audit.test.ts` | Test | WCAG-AA-Wächter — muss nach Migration grün bleiben |
| E2E Playwright `compare-*.spec.ts` | Test | Nutzt `data-testid`-Selektoren die erhalten bleiben müssen |

## Implementation Details

### 1. `+page.svelte` — Mobile Chip-Row: `ChipBtn` → `Pill`

**Vorher (ca. Z. 299–306):**
```svelte
<button
  class="shrink-0 rounded-full border border-border bg-muted px-3 py-1 text-xs"
  onclick={() => toggleLocation(loc.id)}
>
  {loc.name} ×
</button>
```

**Nachher:**
```svelte
<button
  class="cursor-pointer shrink-0"
  onclick={() => toggleLocation(loc.id)}
  aria-pressed={selectedIds.includes(loc.id)}
>
  <Pill tone={(allSelected || selectedIds.includes(loc.id)) ? 'accent' : 'default'}>
    {loc.name} ×
  </Pill>
</button>
```

Import ergänzen:
```svelte
import { Pill } from '$lib/components/ui/pill/index.js';
```

`aria-pressed` wird neu gesetzt — damit ist der Toggle-Zustand für Screenreader sichtbar
(zuvor fehlte dieses ARIA-Attribut vollständig).

### 2. `PresetHeader.svelte` — 5 Felder: `CompareField` → `Field`

Für jedes der 5 Felder (Datum Von, Datum Bis, Horizont, Profil und ggf. weitere) wird das
bisherige `div > label + input/select`-Konstrukt durch `Field` ersetzt.

**Vorher (Beispiel Datum-Feld):**
```svelte
<div>
  <label for="cmp-date" class="text-sm font-medium">Datum</label>
  <input id="cmp-date" data-testid="compare-preset-date-input" ... class="mt-1 block w-full ..." />
</div>
```

**Nachher:**
```svelte
<Field label="Datum" dense={false}>
  <input id="cmp-date" aria-label="Datum" data-testid="compare-preset-date-input" ... class="block w-full ..." />
</Field>
```

Regeln für alle 5 Felder:
- `dense={false}` — verhindert das `margin-bottom`-Override von `Field` im Grid-Layout von `PresetHeader`
- `data-testid`-Attribute bleiben an den nativen `<input>`/`<select>`-Elementen erhalten
- `mt-1` auf dem Input entfernen (übernimmt `Field` intern)

Import ergänzen:
```svelte
import { Field } from '$lib/components/molecules/index.js';
```

### 3. `GroupSection.svelte` — Profil-Dot pro Location-Item (Dot-Pattern)

Nach dem bestehenden Location-Namen wird ein `<span data-slot="dot">` eingefügt, das das
Aktivitätsprofil als farbigen Punkt visualisiert. Die Einfügung ist **rein additiv** —
keine bestehende Logik wird verändert. Das Dot-Pattern folgt dem identischen Muster aus dem
Gruppen-Header (Z. 66–71) und ist kontrast-sicherer als ein `<Pill>`-Element an dieser Stelle.

```svelte
<span
  data-slot="dot"
  data-size="xs"
  style="background: {profileSignature(loc.activity_profile).accent}; flex-shrink: 0;"
  title={profileSignature(loc.activity_profile).eyebrow}
></span>
```

Position: direkt nach dem Location-Namen, vor dem Wetter-Button. `flex-shrink: 0` verhindert
das Quetschen des Dots bei langen Location-Namen.

**Kein neuer Import nötig** — `profileSignature` ist in `GroupSection.svelte` bereits importiert.
`Pill` wird an dieser Stelle bewusst NICHT verwendet.

### 4. LoC-Budget

| Datei | Δ LoC (geschätzt) | Zählt |
|-------|-------------------|-------|
| `+page.svelte` | ~8 (Chip-Umbau + Import) | ja |
| `PresetHeader.svelte` | ~15 (5 × 3 Zeilen Tausch + Import) | ja |
| `GroupSection.svelte` | ~6 (5 Zeilen additiv + Import) | ja |
| **Gesamt** | **~29** | **weit unter 250 LoC-Limit** |

## Expected Behavior

- **Input:** Keine Verhaltensänderung — die Migration ist rein strukturell. Alle bestehenden
  User-Interaktionen (Toggle, Datumseingabe, Profil-Auswahl) verhalten sich identisch.
- **Output:** Der Compare-Screen rendert visuell konsistent mit dem Atomic-Design-System.
  Mobile Chips zeigen korrekte `accent`/`default`-Töne je nach Selektionsstatus. Felder in
  `PresetHeader` erhalten einheitliche Label-Typografie. Activity-Profile-Icons erscheinen
  in `GroupSection` als akzentuierte Pills.
- **Side effects:** Keine. Go-API und Python-Backend sind unberührt. Daten-Rendering
  (CompareMatrix, HourlyMatrix) läuft durch unverändertes Code-Pfad.

## Acceptance Criteria

- **AC-1:** Given der Compare-Screen auf einem mobilen Viewport / When eine Location in der Chip-Row selektiert ist / Then zeigt der zugehörige Chip `tone="accent"` und hat `aria-pressed="true"`, während nicht-selektierte Chips `tone="default"` und `aria-pressed="false"` tragen
  - Test: (populated after /tdd-red)

- **AC-2:** Given das `PresetHeader`-Formular mit seinen 5 Einstellungs-Feldern / When die Felder gerendert werden / Then sind alle `data-testid`-Attribute (`compare-preset-date-input` u. a.) an den nativen `<input>`/`<select>`-Elementen erhalten und via `document.querySelector` auffindbar
  - Test: (populated after /tdd-red)

- **AC-3:** Given eine Location in `GroupSection` mit einem gesetzten `activity_profile` / When der Compare-Screen geladen wird / Then ist neben dem Location-Namen ein `<span data-slot="dot">` mit der `background`-Farbe des Aktivitätsprofils (`profileSignature(...).accent`) und einem `title`-Attribut vorhanden; das Element hat `flex-shrink: 0` und kein `<Pill>`-Element ersetzt es
  - Test: (populated after /tdd-red)

- **AC-4:** Given der gesamte Frontend-Code nach der Migration / When `svelte-check` und `contrast-audit.test.ts` ausgeführt werden / Then sind beide ohne Fehler oder WCAG-AA-Verstöße — `Pill` und `Field` verwenden ausschließlich konforme Design-System-Tokens
  - Test: `svelte-check` (Compiler), `contrast-audit.test.ts` (WCAG-AA-Guard)

- **AC-5:** Given die drei migrierten Dateien nach der Umstellung / When nach den alten Inline-Klassen (`rounded-full border border-border bg-muted`, `text-sm font-medium mt-1`) gesucht wird / Then sind diese Zeichenketten in den betroffenen Dateien nicht mehr vorhanden — die Inline-Helfer wurden vollständig entfernt
  - Test: Source-Inspection via `grep` auf die drei Dateipfade

- **AC-6:** Given die sieben page-lokalen Komposita (CompareMatrix, HourlyMatrix, RecommendationBanner, CompareLocationsRail, CompareSubscriptionsPanel, LocationRow, SubRow) / When `git diff` nach der Migration ausgeführt wird / Then zeigen alle sieben Dateien keine Änderungen — sie sind byte-gleich gegenüber dem Ausgangszustand
  - Test: `git diff --name-only` auf die genannten Dateipfade

## Known Limitations

- **Keine visuellen Regressionstests:** Die Chip-Farb-Tonstufung (`accent`/`default`) wird nicht durch einen Screenshot-Vergleich geprüft, da kein Playwright-Visual-Snapshot für den Compare-Screen existiert. Scope-Abgrenzung bewusst.
- **`dense={false}` ungeprüft in allen Grid-Varianten:** Das `Field`-Molecule mit `dense={false}` wird nur im aktuellen `PresetHeader`-Grid-Layout getestet. Bei zukünftigen Layout-Änderungen an `PresetHeader` muss der Parameter erneut bewertet werden.

## Out of Scope

- Migration der sieben page-lokalen Komposita (CompareMatrix u. a.)
- Neue Playwright-Visual-Snapshot-Tests anlegen
- Änderungen am Compare-Screen-Routing oder an der Datenlage
- Änderungen an Go-API (`internal/`) oder Python-Backend (`src/`)

## Changelog

- 2026-05-26: Initial spec erstellt. Beschreibt Migration von 3 Inline-Helfern (`ChipBtn`, `CompareField`, `FocusBadge`) auf Atomic-Bibliothek (`Pill`, `Field`) in 3 Dateien; ~29 LoC, 6 Acceptance Criteria.
