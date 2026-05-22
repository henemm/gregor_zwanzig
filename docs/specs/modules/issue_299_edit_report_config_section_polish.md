---
entity_id: issue_299_edit_report_config_section_polish
type: module
created: 2026-05-22
updated: 2026-05-22
status: implemented
version: "1.0"
tags: [frontend, design-system, edit-report-config, ui-polish, css-tokens, svelte, issue-299]
---

# Issue #299 — EditReportConfigSection: Zeit-Inputs, Quick-Chips, Channel-Rows, Sektions-Cards

## Approval

- [x] Approved

## Purpose

`EditReportConfigSection.svelte` rendert die Briefing-Zeitplan-Konfiguration (Uhrzeit, Kanal-Auswahl, Erweiterte Optionen) und nutzt derzeit ad-hoc Tailwind-Klassen, die nicht aus dem Design-System stammen. Dieses Modul ersetzt alle fünf visuellen Inkonsistenzen durch Brand-Token-konforme Darstellung: Quick-Chips erhalten eine Pill-förmige Mono-Schrift-Variante, Channel-Hint-Links wechseln auf Accent-Orange, der Advanced-Toggle wird zur Ghost-Btn mit rotierendem Chevron, der Wind-Exposition-Input erhält eine Einheitenbeschriftung wie in `EditStagesSection`, die drei Sektions-Container wechseln auf `Card.Root`, und Zeit-Inputs erhalten die Mono-Font-Klasse `g-num-input`. Es handelt sich ausschließlich um visuelle Änderungen ohne Logik-Eingriff.

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Frontend-Layer (`frontend/src/`). Kein Go-API-Code, kein Python-Backend-Code ist betroffen.

## Source

- **Layer:** Frontend / User-UI (`frontend/src/`)
- **Scope:** 1 Datei

### Betroffene Dateien

| Datei | Änderung |
|---|---|
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | Alle 6 Fixes (Quick-Chips, Hint-Links, Advanced-Toggle, Wind-Unit, Card.Root-Sektionen, Zeit-Inputs Mono) |

### Nur gelesen, keine Änderungen

| Datei | Rolle |
|---|---|
| `frontend/src/lib/components/edit/TripEditView.svelte` | Consumer |
| `frontend/src/lib/components/briefings-tab/BriefingsTab.svelte` | Consumer |
| `frontend/e2e/issue-88-report-config-dialog.spec.ts` | Playwright-Tests (data-testids müssen unverändert bleiben) |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/ui/btn/index.js` | Svelte-Komponente (vorhanden) | Ersetzt den nackten `<button>` des Advanced-Toggles; Variante `ghost`, Größe `sm`; leitet `...restProps` an den inneren `<button>` weiter, damit `data-testid="report-show-advanced"` erhalten bleibt |
| `frontend/src/lib/components/ui/card/index.js` | Svelte-Komponente (vorhanden) | `Card.Root` ersetzt die drei `<section class="rounded-md border border-input ...">` Container; `hover:translate-y-0 hover:shadow-none` deaktiviert den Card-Default-Lift |
| `@lucide/svelte/icons/chevron-down` | Icon-Bibliothek (vorhanden) | Chevron-Icon für den Advanced-Toggle, dreht 180° wenn `showAdvanced === true` |
| `frontend/src/app.css` | CSS-Datei (vorhanden) | Enthält `.g-num-input` (JetBrains Mono, tabular-nums) — wird auf Zeit-Inputs und Wind-Exposition angewendet; `--g-radius-pill`, `--g-font-data`, `--g-ink-faint`, `--g-ink-muted`, `--g-ink`, `--g-surface-2`, `--g-accent` sind dort definiert |
| `frontend/src/lib/components/edit/EditStagesSection.svelte` | Referenz-Komponente (read-only) | Vorbild für `.g-num-with-unit` / `.g-num-unit` Muster (Einheitenbeschriftung neben Input) |

## Implementation Details

### Fix 1 — Quick-Chips Scoped CSS-Klasse

Neuen Scoped-CSS-Block `<style>` ergänzen (oder vorhandenen erweitern):

```css
.g-quick-chip {
  border: 1px solid var(--g-ink-faint);
  border-radius: var(--g-radius-pill);
  font-family: var(--g-font-data);
  font-size: 11px;
  color: var(--g-ink-muted);
  padding: 2px 8px;
  background: transparent;
  cursor: pointer;
}
.g-quick-chip:hover {
  background: var(--g-surface-2);
  color: var(--g-ink);
}
```

Alle 4 Quick-Chip-Buttons (2 × Morgen, 2 × Abend) erhalten `class="g-quick-chip disabled:opacity-50"`.
Tailwind-Klassen `rounded-md border border-input bg-background px-2 py-1 text-xs hover:bg-accent` werden entfernt.

### Fix 2 — Channel-Hint-Links Accent-Farbe

Die 3 `<a>`-Tags für `data-testid="channel-email-hint"`, `data-testid="channel-signal-hint"` und `data-testid="channel-telegram-hint"` werden von:

```svelte
class="underline hover:text-primary"
```

auf Inline-Style geändert:

```svelte
style="color:var(--g-accent);text-decoration:underline;text-underline-offset:2px"
```

Die `class`-Attribute dieser drei Links werden vollständig entfernt.

### Fix 3 — Advanced-Toggle Ghost Btn mit Chevron

**Neue Imports** am Dateianfang ergänzen:

```svelte
import { Btn } from '$lib/components/ui/btn/index.js';
import ChevronDown from '@lucide/svelte/icons/chevron-down';
```

Den nackten `<button>` des Advanced-Toggles ersetzen:

```diff
- <button class="text-sm font-semibold text-primary hover:underline" data-testid="report-show-advanced">
-   Erweiterte Optionen
- </button>
+ <Btn variant="ghost" size="sm" data-testid="report-show-advanced">
+   Erweiterte Optionen
+   <ChevronDown
+     style="transform: rotate({showAdvanced ? 180 : 0}deg); transition: transform 150ms ease"
+   />
+ </Btn>
```

`Btn` leitet `...restProps` an den inneren `<button>` weiter — `data-testid="report-show-advanced"` ist damit vollständig erhalten.

### Fix 4 — Wind-Exposition Input mit Einheitenbeschriftung

**Scoped CSS** ergänzen:

```css
.g-num-with-unit {
  position: relative;
  display: block;
}
.g-num-unit {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  font-family: var(--g-font-data);
  font-size: 11px;
  color: var(--g-ink-faint);
  pointer-events: none;
}
```

Den Wind-Exposition-Input einschließen:

```diff
- <input
-   type="number"
-   class="w-full max-w-xs rounded-md border border-input bg-background px-2 py-1 text-sm"
-   data-testid="report-wind-exposition"
- >
+ <label class="g-num-with-unit block w-full max-w-xs">
+   <input
+     type="number"
+     class="g-num-input w-full rounded-md border border-input bg-background px-2 py-1 text-sm pr-7"
+     data-testid="report-wind-exposition"
+   >
+   <span class="g-num-unit" aria-hidden="true">m</span>
+ </label>
```

Das `data-testid`-Attribut bleibt am `<input>` erhalten.

### Fix 5 — Sektions-Container Card.Root

**Neuer Import** am Dateianfang:

```svelte
import * as Card from '$lib/components/ui/card/index.js';
```

Alle drei `<section class="space-y-... rounded-md border border-input p-3">` Elemente ersetzen:

```diff
- <section class="space-y-3 rounded-md border border-input p-3">
+ <Card.Root class="p-3 space-y-3 hover:translate-y-0 hover:shadow-none">
```

```diff
- </section>
+ </Card.Root>
```

Gilt für die Morgen-Sektion, die Abend-Sektion und die Kanal-Sektion (3 Vorkommen). `hover:translate-y-0 hover:shadow-none` ist zwingend, da `Card.Root` einen Default-Lift-Effekt hat, der bei Formular-Sektionen unerwünscht ist.

### Fix 6 — Zeit-Inputs Mono-Font

Beide Zeit-Inputs (`data-testid="report-morning-time"` und `data-testid="report-evening-time"`) erhalten die Klasse `g-num-input`:

```diff
- <input type="time" class="rounded-md border border-input bg-background px-2 py-1 text-sm"
+ <input type="time" class="g-num-input rounded-md border border-input bg-background px-2 py-1 text-sm"
```

`.g-num-input` ist bereits in `app.css` definiert und setzt JetBrains Mono + `font-variant-numeric: tabular-nums`. Kein `font-size`-Override — iOS Safari Auto-Zoom-Schutz aus Bug #272 bleibt intakt.

### Umsetzungsreihenfolge

1. Imports ergänzen (`Btn`, `Card`, `ChevronDown`)
2. Scoped `<style>` Block: `.g-quick-chip`, `.g-num-with-unit`, `.g-num-unit`
3. Fix 5: `<section>` → `<Card.Root>` (alle 3)
4. Fix 1: Quick-Chip-Buttons (alle 4)
5. Fix 2: Hint-Link `<a>`-Tags (alle 3)
6. Fix 3: Advanced-Toggle-Button → `<Btn>` + Chevron
7. Fix 4: Wind-Exposition Input einschließen
8. Fix 6: `g-num-input` auf Zeit-Inputs

### Kritische Nebenbedingung — data-testids

Folgende `data-testid`-Attribute MÜSSEN unverändert erhalten bleiben (Playwright-Tests in `frontend/e2e/issue-88-report-config-dialog.spec.ts`):

`morning-master-switch`, `report-morning-time`, `report-morning-quickpick-07`, `report-morning-quickpick-18`, `report-morning-trend`, `evening-master-switch`, `report-evening-time`, `report-evening-quickpick-07`, `report-evening-quickpick-18`, `report-evening-trend`, `channel-email`, `channel-email-hint`, `channel-signal`, `channel-signal-hint`, `channel-telegram`, `channel-telegram-hint`, `report-show-advanced`, `report-compact-summary`, `report-show-daylight`, `report-wind-exposition`

### LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | ~+36 netto | ja |
| **Gesamt** | **~+36 netto** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input:** Bestehende `ReportConfig`-Daten eines Trips (Morgen-/Abend-Uhrzeiten, aktivierte Kanäle, Advanced-Optionen wie Wind-Exposition und Trend-Flags)
- **Output (visuell):**
  - Quick-Chips: Pill-Form mit `--g-radius-pill`, `--g-font-data` 11px, `--g-ink-muted`; Hover: `--g-surface-2` Hintergrund, `--g-ink` Text
  - Channel-Hint-Links: Accent-Orange (`--g-accent`) statt Browser-Blau, `text-underline-offset: 2px`
  - Advanced-Toggle: Ghost-Btn mit rotierendem Chevron (0° → 180° bei Öffnen, 150ms ease)
  - Wind-Exposition-Input: Einheitenbeschriftung "m" rechts innerhalb des Inputs, `--g-font-data` 11px `--g-ink-faint`
  - Morgen-, Abend- und Kanal-Sektionen: `Card.Root` Wrapper ohne Lift-Effekt
  - Zeit-Inputs: JetBrains Mono, tabular-nums; kein font-size-Override
- **Side effects:** Keine — es werden ausschließlich CSS-Klassen und Komponenten-Typen getauscht, alle Bindings, Event-Handler und Reaktivitätsvariablen bleiben unverändert. Keine Änderungen an der Datenpersistenz.

## Acceptance Criteria

**AC-1:** Given die EditReportConfigSection mit sichtbaren Quick-Chip-Buttons / When die Morgen- oder Abend-Zeitauswahl gerendert wird / Then haben alle 4 Quick-Chip-Buttons `border-radius: var(--g-radius-pill)`, `font-family: var(--g-font-data)` und `font-size: 11px`, und sind keine Tailwind-Klassen `rounded-md bg-background hover:bg-accent` mehr auf diesen Buttons vorhanden.
  - Test: (populated after /tdd-red)

**AC-2:** Given die Channel-Hint-Links (`channel-email-hint`, `channel-signal-hint`, `channel-telegram-hint`) / When die Sektions-Ansicht gerendert wird / Then haben alle drei `<a>`-Elemente `color: var(--g-accent)` als Inline-Style und `text-decoration: underline` — kein `text-primary` Tailwind-Attribut mehr vorhanden.
  - Test: (populated after /tdd-red)

**AC-3:** Given der Advanced-Toggle-Button mit `data-testid="report-show-advanced"` / When der Button gerendert wird / Then ist er ein `<Btn variant="ghost" size="sm">`-Element, enthält ein `<ChevronDown>`-Icon, und das `data-testid="report-show-advanced"` ist am inneren `<button>`-DOM-Element vorhanden.
  - Test: (populated after /tdd-red)

**AC-4:** Given der Advanced-Toggle in geschlossenem Zustand (`showAdvanced === false`) / When der Toggle auf geöffnet geklickt wird (`showAdvanced === true`) / Then dreht sich das ChevronDown-Icon von 0° auf 180° mit einer CSS-Transition von 150ms ease, und beim erneuten Schließen zurück auf 0°.
  - Test: (populated after /tdd-red)

**AC-5:** Given der Wind-Exposition-Input (`data-testid="report-wind-exposition"`) / When die Advanced-Optionen geöffnet und die Section gerendert wird / Then enthält der Input die Klassen `g-num-input` und `pr-7`, ist von einem `<label class="g-num-with-unit ...">` eingeschlossen, und ein `<span class="g-num-unit" aria-hidden="true">m</span>` ist als Geschwister-Element positioniert. Das `data-testid`-Attribut ist am `<input>` erhalten.
  - Test: (populated after /tdd-red)

**AC-6:** Given die Morgen-Sektion, Abend-Sektion und Kanal-Sektion / When die EditReportConfigSection gerendert wird / Then sind alle drei Sektionen `<Card.Root>`-Elemente mit der Klasse `hover:translate-y-0 hover:shadow-none` — kein `<section class="... border border-input ...">`-Element mehr vorhanden.
  - Test: `grep -c '<section class=' frontend/src/lib/components/edit/EditReportConfigSection.svelte` → `0`

**AC-7:** Given die Zeit-Inputs `data-testid="report-morning-time"` und `data-testid="report-evening-time"` / When die Sektions-Ansicht gerendert wird / Then enthält die `class`-Eigenschaft beider Inputs `g-num-input`, und kein explizites `font-size`-Override ist als Inline-Style gesetzt (iOS-Zoom-Schutz aus Bug #272 bleibt intakt).
  - Test: (populated after /tdd-red)

**AC-8:** Given der Playwright-Test `frontend/e2e/issue-88-report-config-dialog.spec.ts` / When `npx playwright test issue-88-report-config-dialog` ausgeführt wird / Then laufen alle Tests durch (Exit 0) — alle 20 data-testid-Selektoren schlagen nicht fehl.
  - Test: Playwright-Testsuite — bestehende Tests dürfen nicht brechen

## Known Limitations

- AC-4 (Chevron-Rotation) ist eine CSS-Transition im Inline-Style und kann in Playwright-Tests nur über DOM-Snapshot-Prüfung verifiziert werden, nicht durch Animation-Tracking. Ausreichend ist der Nachweis, dass `style` das korrekte `transform: rotate(180deg)` enthält wenn `showAdvanced === true`.
- Die scoped CSS-Klassen `.g-num-with-unit` und `.g-num-unit` werden als Duplikat zu `EditStagesSection.svelte` eingeführt. Eine gemeinsame globale Utility-Klasse in `app.css` ist sinnvoll, liegt aber außerhalb des Scope dieses Issues.
- `Card.Root` aus dem UI-Kit kann zukünftige Breaking-API-Änderungen in `$lib/components/ui/card/index.js` empfangen — die `hover:translate-y-0 hover:shadow-none` Überschreibung muss bei Card-Komponent-Updates erneut geprüft werden.

## Changelog

- 2026-05-22: Initial spec created (Issue #299 — EditReportConfigSection visual polish)
