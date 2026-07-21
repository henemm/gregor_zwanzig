---
entity_id: issue_582_compare_design_fidelity
type: module
created: 2026-06-04
updated: 2026-06-04
status: draft
version: "1.0"
tags: [frontend, design-compliance, compare]
---

# Compare-Screen Design-Fidelity (#582)

## Approval

- [ ] Approved

## Purpose

Compare-Liste, Compare-Hub (Detail) und Compare-Wizard 1:1 nach JSX-Vorlagen implementieren. Alle Inline-Styles verwenden ausschließlich `var(--g-*)` Tokens — kein rohes Hex/px, keine Tailwind-Klassen für Layout/Spacing/Farbe, keine eigenen Design-Entscheidungen.

## Source

- **JSX-Vorlage Liste:** `claude-code-handoff/current/jsx/screen-compare-list.jsx`
- **JSX-Vorlage Hub:** `claude-code-handoff/current/jsx/screen-compare-detail.jsx`
- **JSX-Vorlage Wizard:** `claude-code-handoff/current/jsx/screen-compare-wizard.jsx`
- **SOLL-Screenshots:** `claude-code-handoff/current/soll/G-compare-*.png` (7 Bilder)

## Estimated Scope

- **LoC:** ~600–800 geänderte Zeilen (4–5 Dateien)
- **Files:** 4 Hauptdateien + ggf. Hilfsdateien
- **Effort:** high
- **LoC-Override:** 800 notwendig (JSX-Wizard = 1037 Z)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Stat` Molecule | upstream | Inline-Stat in Compare-Liste |
| `CompareStatusPill` | upstream | Status-Anzeige im Hub-Header |
| `CompareKebab` | upstream | Lifecycle-Aktionen im Hub-Header |
| `CompareLocationRow` | upstream | Orte-Tab |
| `CompareIdealRow` | upstream | Idealwerte-Tab |
| `CompareLayoutRow` | upstream | Layout-Tab |
| `CompareChannelSwitch` | upstream | Vorschau-Tab |
| `CompareBriefingPreview` | upstream | Vorschau-Tab |
| Bestehende Tests `compare/__tests__/` | downstream | Müssen grün bleiben |

## Affected Files

| Datei | Änderungstyp |
|-------|-------------|
| `frontend/src/routes/compare/+page.svelte` | Vollständige Neufassung |
| `frontend/src/routes/compare/[id]/+page.svelte` | Hub-Layout + Header anpassen |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | Tab-Buttons + Inhalt-Styling |
| `frontend/src/lib/components/compare/CompareWizard.svelte` | Edit-Header + Stepper |

## Implementation Details

### Block A — Compare-Liste (`+page.svelte`)

JSX-Vorgabe: `padding: "32px 40px 60px"`, kein `max-w` Container.

Änderungen:
- Outer wrapper: `<div style="background: var(--g-paper)">`, kein Tailwind-Padding
- `<main style="flex: 1; padding: 32px 40px 60px; overflow: auto">`
- Eyebrow-Text: `"Workspace · Orts-Vergleiche"` (Mixed Case, nicht CAPS)
- Beschreibungstext: aus JSX 1:1 übernehmen (`"einmalig eingerichtet, läuft pro Vergleich automatisch"`)
- Stats-Zeile: `<Stat label="Aktiv" value={counts.active} layout="inline" tone="accent" mono/>` etc.
- Suche: immer sichtbar (kein `showSearch`-Guard), `style` statt Tailwind-Klassen
- Leerzustand: `<Card padding={40} style="text-align: center; color: var(--g-ink-3); font-size: 13px">`
- Footer-Zähler: `{filtered.length} von {presets.length} Vergleichen` in mono, ink-4, 11px

### Block B — Compare-Hub Header + Tab-Leiste (`[id]/+page.svelte` + `CompareTabs.svelte`)

JSX-Vorgabe: Full-width Header mit `padding: "22px 40px 0"`, `borderBottom: "1px solid var(--g-rule)"`.

Desktop-Header (`[id]/+page.svelte`):
- Container: `style="position: relative; padding: 22px 40px 0; border-bottom: 1px solid var(--g-rule)"` statt `class="p-8 max-w-5xl mx-auto"`
- Breadcrumb: `<a style="font-size:11px; font-family:var(--g-font-mono); ...">Orts-Vergleiche</a> <span>/</span> <span>Hub</span>` (kein `<nav>`, kein Eyebrow)
- H1: `font-size: 30px; font-weight: 600; letter-spacing: -0.025em; line-height: 1.1`
- Untertitel: `font-size: 14px; color: var(--g-ink-3)` mit Region · Profil · N Orte
- Status-Pill: `<CompareStatusPill>` statt rohem `<span class="inline-flex ...">` mit Inline-Color

Tab-Leiste (`CompareTabs.svelte`):
- Tabs als individuelle `<button>` mit:
  ```
  padding: 12px 16px; font-size: 13px; font-weight: on ? 600 : 500;
  color: on ? var(--g-ink) : var(--g-ink-3);
  border-bottom: on ? 2px solid var(--g-accent) : 2px solid transparent;
  margin-bottom: -1px;
  ```
- Badge in Orte-Tab: `font-size: 10px; padding: 2px 6px; border-radius: 3px; background: var(--g-paper-deep); color: var(--g-ink-3)`
- Tab-Inhalt-Wrapper: `style="position: relative; padding: 28px 40px 80px; max-width: 1320px"`

### Block C — Hub Tab-Inhalte (`CompareTabs.svelte`)

Übersicht-Tab:
- Monitoring-Streifen: `<Card padding={0} style="overflow: hidden">` + `padding: 18px 24px; display: flex; gap: 40px; flex-wrap: wrap`
- 4 `CHub_Stat`-Felder: Status (mit `<Dot>`), Nächster Versand, Zuletzt raus, Kanäle
- 2×2-Summary-Grid: `display: grid; grid-template-columns: 1fr 1fr; gap: 16px`
- `CHub_SummaryCard`: `<Card padding={20}>` + Eyebrow + Titel + Beschreibung + `"Bearbeiten →"`-Link
- Verifikations-Hinweis: `padding: 14px 18px; border-left: 3px solid var(--g-accent); border-radius: var(--g-r-3)` + Button "Vorschau prüfen →"

Orte-Tab:
- `CHub_EditSection`-Wrapper: Titel + Hint-Text oben
- Drag-Handle: SVG-Dots-Icon links, `cursor: grab`
- Zebra-Stripes: `background: i % 2 === 1 ? var(--g-paper-deep) : transparent`
- Footer: `"+ Ort hinzufügen"` Link in `padding: 14px`

Idealwerte-Tab:
- `CHub_EditSection` + vertikale Liste von `<CompareIdealRow>` mit Drag-Handles

Layout-Tab:
- `CHub_EditSection` + `<CompareLayoutRow>` je Kanal

Versand-Tab:
- Zwei-Spalten-Grid `grid-template-columns: 1fr 1fr`
- Links: Zeitplan-Card + Kanal-Status-Card
- Rechts: Aktivierungs-Card

Vorschau-Tab:
- Verifikations-Hinweis-Banner (identisch Übersicht)
- `<CompareChannelSwitch>` + Email-View-Toggle (Desktop/iPhone)
- `<CompareBriefingPreview>`-Wrapper mit `padding: 24px; background: var(--g-paper-deep)` bei Email-Desktop

### Block D — Wizard-Header + Stepper (`CompareWizard.svelte`)

Edit-Header (`CW_EditHeader`):
- Eyebrow: `"ORTS-VERGLEICH · BEARBEITEN"` oder Status-Pill-Badge
- H1: Name des Vergleichs, `font-size: 30px; font-weight: 600`
- Rechts: Save- + Cancel-Buttons

Stepper (`CW_Stepper`):
- `display: flex; align-items: flex-start; gap: 0; padding: 8px 0`
- Step-State: `done` (grün-Haken) | `current` (Accent-Nummer) | `upcoming` (grau)
- Connector-Linie zwischen Steps: `background: done ? var(--g-ink-3) : var(--g-rule); opacity: done ? 0.5 : 1`
- Klickbar: im Create-Mode nur `n <= step`; im Edit-Mode alle Steps

## Acceptance Criteria

**AC-1:** Given die Compare-Übersicht (`/compare`) mit mindestens einem Vergleich / When die Seite auf 1440px gerendert wird / Then zeigt der Header `"Workspace · Orts-Vergleiche"` als Eyebrow (Mixed Case), die Stats-Zeile nutzt das `<Stat>`-Molecule mit `tone="accent"` für Aktiv, und das Such-Input ist immer sichtbar (unabhängig von der Anzahl der Vergleiche).

**AC-2:** Given die Compare-Übersicht ohne Vergleiche oder mit Suchfilter ohne Treffer / When die Seite gerendert wird / Then erscheint ein `<Card>`-Leerzustand mit zentriertem Text und `color: var(--g-ink-3)` — kein roher `<div>`-Text.

**AC-3:** Given die Compare-Übersicht mit N Vergleichen (gefiltert) / When die Seite gerendert wird / Then zeigt der Footer `"{N} von {M} Vergleichen"` in `font-family: var(--g-font-mono); font-size: 11px; color: var(--g-ink-4)`.

**AC-4:** Given die Compare-Hub-Seite (`/compare/[id]`) / When die Seite auf 1440px gerendert wird / Then ist der Header full-width mit `padding: 22px 40px 0` und einer horizontalen Trennlinie (`border-bottom: 1px solid var(--g-rule)`) — kein `max-w-5xl`-Container.

**AC-5:** Given die Compare-Hub-Seite / When ein Tab ausgewählt ist / Then zeigt der aktive Tab `border-bottom: 2px solid var(--g-accent)` und `font-weight: 600`, inaktive Tabs haben `color: var(--g-ink-3)` und `font-weight: 500` — kein `<Segmented>`-Wrapper.

**AC-6:** Given der Übersicht-Tab im Compare-Hub / When die Seite gerendert wird / Then erscheinen 4 Status-Felder im Monitoring-Streifen (`Status`, `Nächster Versand`, `Zuletzt raus`, `Kanäle`) und 4 `CHub_SummaryCard`-Kacheln im 2×2-Grid mit je einem `"Bearbeiten →"`-Link.

**AC-7:** Given der Vorschau-Tab im Compare-Hub / When die Seite gerendert wird / Then ist der `<CompareChannelSwitch>` sichtbar, das Email-View-Toggle (Desktop/iPhone) erscheint wenn Email aktiv ist, und `<CompareBriefingPreview>` rendert den Vorschauinhalt.

**AC-8:** Given der Compare-Wizard im Bearbeiten-Modus (`mode="edit"`) / When Schritt 1 geöffnet ist / Then zeigt der Header den Vergleichs-Namen als H1 (`font-size: 30px; font-weight: 600`) und zwei Buttons (`Speichern`, `Abbrechen`) rechts oben.

**AC-9:** Given der Compare-Wizard im Erstellen-Modus / When Schritt 1 geöffnet ist / Then zeigt der Stepper Schritt 1 im `current`-State (Accent-Farbe), Schritte 2–5 im `upcoming`-State (grau), und die Step-Titel-Zeile erscheint über dem Inhalt.

**AC-10:** Given alle Compare-Screens nach der Implementierung / When die bestehende Test-Suite (`uv run pytest` + `npm run test`) läuft / Then sind alle Tests grün (keine Regression).
