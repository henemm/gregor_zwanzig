# Spec: Issue #578 — Design-Fidelity: Molecules + Organisms 1:1

**Status:** Draft  
**Workflow:** issue-578-molecules-organisms  
**Bindende Quellen:** `claude-code-handoff/current/jsx/molecules.jsx`, `organisms.jsx`, `sidebar.jsx`, `screen-home.jsx`  
**Abhängigkeit:** #576 (Tokens ✅), #577 (Atoms ✅)

---

## Scope

Diese Spec deckt drei Arbeitsblöcke:

**Block A — Divergenz-Fixes (bestehende Molecules):** 4 Svelte-Moleküle korrigieren, die strukturell oder token-seitig vom JSX abweichen.

**Block B — Fehlende Molecules:** 8 Molecules neu erstellen, die in `molecules.jsx` definiert sind aber noch keine Svelte-Implementierung haben.

**Block C — Fehlende Organisms:** 7 Organisms erstellen — 3 aus `organisms.jsx` und 4 Home-Organisms aus `screen-home.jsx` — sowie alle neuen Organisms in `organisms/index.ts` registrieren.

---

## Acceptance Criteria

### Block A — Divergenz-Fixes

**AC-1:** Given die Molecule `QuickAction.svelte`, When sie gerendert wird, Then enthält sie `box-shadow: var(--g-shadow-1)` im Normalzustand, `box-shadow: var(--g-shadow-2)` + `border-color: var(--g-ink-3)` im Hover-Zustand, und `border: 1px solid var(--g-rule)` (nicht `--g-rule-soft`). Der sub-Text (`<span>`) hat `font-family: var(--g-font-mono)`, `text-transform: uppercase`, `letter-spacing: 0.04em`, `font-size: 10.5px`. Das Chevron-Icon rechts ist ein SVG `<path d="M9 6l6 6-6 6"/>` (nicht ASCII `›`).

**AC-2:** Given die Molecule `SetupResumeCard.svelte`, When `tone="accent"`, Then hat das `<article>`-Element `border-left: 3px solid var(--g-accent)` UND `border: 1px solid var(--g-rule)` (nicht nur `--g-rule-soft`) UND `box-shadow: var(--g-shadow-1)`. When `tone="default"`, Then ist `border-left: 1px solid var(--g-rule)` (keine Akzent-Farbe).

**AC-3:** Given die Molecule `SetupResumeCard.svelte`, When Schritte übergeben werden, Then werden sie als **Chip-Reihe** (`display: flex; flex-wrap: wrap; gap: 7px`) dargestellt — jeder Schritt ist ein `<span>` mit `border-radius: var(--g-r-pill)`, Fortschritt-Kreis (Checkmark-SVG bei done, gestrichelter Kreis bei offen). Unterhalb der Chips liegt eine Footer-Leiste (`background: var(--g-card-alt)`; `border-top: 1px solid var(--g-rule-soft)`) mit "Weiter bei: <step>" links und CTA rechts.

**AC-4:** Given die Molecule `BriefingTimelineRow.svelte`, When `report.status !== 'sent'`, Then hat das Status-Label `color: var(--g-ink-4)` (nicht `--g-ink-3`).

**AC-5:** Given die Molecule `CompareStatusRow.svelte`, When mehrere Rows nebeneinander stehen, Then belegt jede Row dieselbe Spalten-Breite für Name, Orte-Zahl und Versand-Zeit (Mono-Font, `white-space: nowrap`). Das Empfänger-Chip am Ende erscheint nur wenn `preset.empfaenger` gesetzt ist — konsistent in JEDER Zeile an derselben Position.

---

### Block B — Fehlende Molecules

**AC-6:** Given die neue Molecule `StageCascadeNotice.svelte`, When `done=false`, Then zeigt sie ein Banner mit `background: var(--g-accent-tint)`, `border-left: 3px solid var(--g-accent)`, Beschreibungstext + zwei Btns: „Alle mitverschieben" (accent) und „Nur diese Etappe" (ghost). When `done=true`, Then `background: rgba(61,107,58,0.10)`, `border-left: 3px solid var(--g-good)`, Dot-Good + Bestätigungstext + „Schließen"-Link.

**AC-7:** Given die neue Molecule `HorizonChips.svelte` (ersetzt `ui/horizon-chip/HorizonChip.svelte` als Barrel-Export), When `value={morning: true, evening: false}`, Then ist der „Morgen"-Chip aktiviert (Hintergrund `--g-accent-tint`, Border `--g-accent`, Text `--g-accent-deep`) und „Abend" inaktiv (Hintergrund `--g-paper-deep`, Border transparent). Kompakt-Variante (`compact=true`) reduziert Padding. Die `HorizonChips`-Komponente exportiert das `onToggle`-Callback-Interface.

**AC-8:** Given die neue Molecule `ScoreToggle.svelte`, When `on=true`, Then Background `var(--g-accent-tint)`, Text `var(--g-accent-deep)`, Border `1px solid var(--g-accent)`. When `on=false`, Then Border `1px solid var(--g-rule)`, Background `var(--g-paper-deep)`, Text `--g-ink-3`.

**AC-9:** Given die neue Molecule `CompareChannelSwitch.svelte`, When `value="email"`, Then ist der Email-Button mit `background: var(--g-card)`, `box-shadow: var(--g-shadow-1)`, `font-weight: 600` aktiv. Kanäle, die nicht in `channels[]` enthalten sind, zeigen einen 5×5-px-Punkt-Indikator und haben `color: var(--g-ink-4)`.

**AC-10:** Given die neue Molecule `CompareBriefingPreview.svelte`, When `channel="signal"` oder `channel="telegram"`, Then delegiert sie an `CompareChatBubble.svelte`. When `channel="sms"`, Then an `CompareSmsPreview.svelte`. When `channel="email"`, Then an den `CompareEmail`-Slot. When kein Profil verfügbar, Then `ComparePreviewMissing.svelte` anzeigen.

**AC-11:** Given die neue Molecule `CompareChatBubble.svelte`, When `channel="signal"`, Then `backdrop: #0b0b0d`, `bubbleBg: #26252b`, `accent: #2c6bed`. When `channel="telegram"`, Then `#17212b`, `#1e2c3a`, `#5ea9dd`. Die Bubble zeigt Rang+Name+Score in der Header-Zeile + Metrik-Werte im Mono-Grid darunter.

**AC-12:** Given die neue Molecule `CompareSmsPreview.svelte`, When `body.length > 140`, Then wird der Text auf 139 Zeichen gekürzt + `…` angehängt, und der Längen-Counter hat `color: #f0a060`.

**AC-13:** Given die neue Molecule `ComparePreviewMissing.svelte`, When sie gerendert wird, Then zeigt sie `border: 1px dashed var(--g-rule)` + `background: var(--g-card)` + Text `color: var(--g-ink-3)`.

---

### Block C — Fehlende Organisms

**AC-14:** Given der neue Organism `HomeHeroTrip.svelte`, When er gerendert wird, Then ist die Reihenfolge des Inhalts: (1) Pills-Reihe (`Pill tone="accent"` „Live · Tag X von Y" + `Pill tone="ghost"` Profil-Name), (2) Titel (34 px, fontWeight 600), (3) Route-Subtitel (15 px, `--g-ink-2`), (4) Fortschrittsbalken-Block mit Label „Tag X / Y" + Datumsrange, (5) Footer-Leiste (`card-alt`-Hintergrund, `border-top: 1px solid var(--g-rule-soft)`) mit Kanal-Dot-Reihe links + „Trip öffnen →"-Link rechts.

**AC-15:** Given der neue Organism `HomeHeroCompare.svelte`, When er gerendert wird, Then zeigt er: (1) Pills (accent „Aktiv · läuft automatisch" + ghost Profil-Label), (2) Titel, (3) Subtitel (Orte/Region/Horizont), (4) 2-Spalten-Stat-Grid (Zeitplan + Nächster Versand, je mit Mono-Label + Wert), (5) Footer-Leiste mit Kanal-Dots + „Vergleich öffnen →". Beide Heroes haben `border-left: 3px solid var(--g-accent)`.

**AC-16:** Given der neue Organism `OutboxCard.svelte`, When er gerendert wird, Then zeigt er `Eyebrow` „Versand · heute" + Titel „Was geht raus · {contextName}" + `Pill tone="good"` „Alle Kanäle ok" in einem Flex-Header. Darunter bis zu 3 `BriefingTimelineRow`-Komponenten.

**AC-17:** Given der neue Organism `AlertsCard.svelte`, When `alerts.length > 0`, Then rendert sie Titel „{count} ausgelöst" + jeden Alert als `AlertRow`. When `alerts.length === 0`, Then zeigt sie Titel „Keine" + Erklärungs-Text (13 px, `--g-ink-3`). In beiden Fällen: `Eyebrow` „Alerts · letzte 24 h" + „Schwellen →"-Link.

**AC-18:** Given die neuen Organisms `PresetRail.svelte`, `MetricOffShelf.svelte`, `MetricsEditorContextBar.svelte`, When sie gerendert werden, Then entsprechen sie 1:1 den JSX-Definitionen in `organisms.jsx` (gleiche Props, gleiche DOM-Struktur, gleiche Token-Werte).

**AC-19:** Given die Datei `organisms/index.ts`, When sie importiert wird, Then exportiert sie alle neuen Organisms: `HomeHeroTrip`, `HomeHeroCompare`, `OutboxCard`, `AlertsCard`, `PresetRail`, `MetricOffShelf`, `MetricsEditorContextBar`.

**AC-20:** Given die Datei `molecules/index.ts`, When sie importiert wird, Then exportiert sie alle neuen Molecules: `StageCascadeNotice`, `HorizonChips`, `ScoreToggle`, `CompareChannelSwitch`, `CompareBriefingPreview`, `CompareChatBubble`, `CompareSmsPreview`, `ComparePreviewMissing`.

---

## Nicht im Scope

- `StageDateField`: Existiert als `edit/StageDateField.svelte` mit anderem API (bindable value). Wird NICHT nach molecules/ verschoben — der JSX-API-Unterschied ist gewollt.
- `MetricEditorRow`, `ChannelLimitChip`: Interne Sub-Komponenten von `WeatherMetricsTab`, werden NICHT als eigenständige Exports in molecules/ registriert — sie bleiben private Implementierungsdetails.
- `stageWeekdayDE`, `compareActions`, `compareShownCols`: Pure Helper-Funktionen, keine Svelte-Komponenten — werden als TypeScript-Utilities in `$lib/utils/` gelagert wenn nötig.
- Screen-Implementierungen (#579–#588): In separaten Issues.

---

## Implementierungsreihenfolge (empfohlen)

1. **Block A** (Fixes): QuickAction → SetupResumeCard → BriefingTimelineRow → CompareStatusRow
2. **Block B** (neue Molecules): StageCascadeNotice → HorizonChips → ScoreToggle → CompareChannelSwitch → ComparePreviewMissing → CompareChatBubble → CompareSmsPreview → CompareBriefingPreview
3. **Block C** (neue Organisms): HomeHeroTrip → HomeHeroCompare → OutboxCard → AlertsCard → PresetRail → MetricOffShelf → MetricsEditorContextBar → Index-Updates

## Tests

Für jede neue Svelte-Komponente: Snapshot- oder DOM-Assertions in `molecules.test.ts` / `organisms.test.ts`. Mindestens: korrekte Prop-Defaults, konditionaler Rendering-Zweig, Token-Verwendung (grep auf falschen Token).

**KEINE Mocks** — alle Tests sind reine Render-Tests ohne API-Calls.
