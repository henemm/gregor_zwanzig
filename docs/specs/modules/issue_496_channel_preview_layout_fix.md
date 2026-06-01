---
entity_id: issue_496_channel_preview_layout_fix
type: bugfix
created: 2026-06-01
updated: 2026-06-01
status: draft
version: "1.0"
tags: [bugfix, frontend, layout, overflow, channel-preview, issue-496]
---

# Issue #496 — Bug-Fix: ChannelPreviewBlock overflow-hidden + Breite in WeatherMetricsTab

## Approval

- [ ] Approved

## Purpose

Zwei Layout-Regressions im `ChannelPreviewBlock` werden behoben, die nach dem Issue-#496-Deploy ohne Adversary-Verifikation entdeckt wurden. Bug 1 blockiert das horizontale Scrollen der Email-Tabelle, weil `overflow-hidden` auf `Card.Root` das `overflow-x: auto` des inneren `.table-wrap` aufhebt — Spalten werden hart abgeschnitten statt scrollbar zu sein. Bug 2 lässt den Block in `WeatherMetricsTab` nur auf `editor-col`-Breite (~628 px) rendern, obwohl die volle Tab-Breite (~1100 px auf 1440-px-Screen) verfügbar wäre und für lesbare Metriktabellen nötig ist.

## Source

**Geänderte Dateien:**
- `frontend/src/lib/components/trip-detail/ChannelPreviewBlock.svelte` (1 LoC: `class="overflow-visible"` auf `Card.Root`)
- `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` (~11 LoC: ChannelPreviewBlock aus `editor-col` herausziehen)

**NICHT ändern:**
- `frontend/src/lib/components/ui/card/card.svelte` — Library-Basisdatei, kein direktes Anfassen
- `frontend/src/lib/components/trip-wizard/steps/Step4Layout.svelte` — dort ist ChannelPreviewBlock in `preview-col` (gewolltes Side-by-Side-Layout neben Channel-Editor)
- `frontend/src/lib/components/compare/steps/Step4Layout.svelte` — gleicher Grund wie Step4Layout Wizard

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im SvelteKit-Frontend-Layer (`frontend/src/`). Kein Go-API- oder Python-Backend-Code ist betroffen.

## Estimated Scope

- **LoC:** ~12
- **Files:** 2
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/trip-detail/ChannelPreviewBlock.svelte` | Svelte-Komponente | Wrapper-Block für die Kanal-Vorschau; erhält `class="overflow-visible"` auf `Card.Root` (Bug 1) |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Svelte-Komponente | Tab-Layout mit `editor-col` / `layout`-Grid; ChannelPreviewBlock wird aus `editor-col` herausgezogen (Bug 2) |
| `frontend/src/lib/components/ui/card/card.svelte` | Shadcn-Basiskomponente | Hardcoded `overflow-hidden` in der Basisklasse; Tailwind-Merge überschreibt es korrekt wenn `overflow-visible` per `class`-Prop übergeben wird |
| `frontend/src/lib/components/trip-detail/ChannelFidelityEmail.svelte` | Svelte-Komponente | Enthält `.table-wrap` mit `overflow-x: auto`; profitiert von Bug-1-Fix ohne eigene Änderung |

## Implementation Details

### Bug 1 — `overflow-hidden` auf `Card.Root` überschreiben

In `ChannelPreviewBlock.svelte`, Zeile 35, das `<Card.Root>`-Element um das `class`-Prop ergänzen:

```svelte
<!-- Vorher -->
<Card.Root ...>

<!-- Nachher -->
<Card.Root class="overflow-visible" ...>
```

Tailwind-Merge (wird in der shadcn-Svelte-Integration automatisch angewendet) überschreibt das Basis-`overflow-hidden` mit `overflow-visible`. Damit kann `.table-wrap` in `ChannelFidelityEmail.svelte` wieder horizontal scrollen.

### Bug 2 — ChannelPreviewBlock aus `editor-col` herausziehen

In `WeatherMetricsTab.svelte` liegt die aktuelle Struktur ungefähr so:

```svelte
<div class="layout">          <!-- 300px | 1fr Grid -->
  <div class="editor-col">   <!-- 1fr = ~628px auf 1440px -->
    <!-- Channel-Editor-Steuerung -->
    ...
    <ChannelPreviewBlock ... />   <!-- sitzt HIER → zu schmal -->
  </div>
</div>
```

Zielstruktur: ChannelPreviewBlock direkt unter `<div class="layout">` platzieren, außerhalb von `editor-col`:

```svelte
<div class="layout">
  <div class="editor-col">
    <!-- Channel-Editor-Steuerung -->
    ...
  </div>
</div>
<ChannelPreviewBlock ... />     <!-- volle Tab-Breite -->
```

Dadurch bekommt der Block die volle Tab-Breite (~1100 px auf 1440-px-Screen) statt der eingeschränkten `1fr`-Spalte.

### LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `ChannelPreviewBlock.svelte` | +1 (class-Prop) | ja |
| `WeatherMetricsTab.svelte` | ~11 (Verschiebung) | ja |
| **Gesamt** | **~12** | **weit unter 250 LoC-Limit** |

## Expected Behavior

- **Input:** Keine Laufzeit-Eingabe — reine Layout-Änderungen
- **Output:** Email-Tabelle in `ChannelFidelityEmail` scrollt horizontal wenn Spalten die Container-Breite überschreiten; `ChannelPreviewBlock` in `WeatherMetricsTab` nutzt volle Tab-Breite
- **Side effects:** Wizard Step4 (`trip-wizard` und `compare`) bleiben unverändert — der Block sitzt dort in `preview-col` (gewolltes Side-by-Side) und wird von dieser Änderung nicht berührt

## Acceptance Criteria

**AC-1:** Given Email ist aktiver Kanal und 10+ Metriken sind in primary / When der Nutzer zur Email-Fidelity-Vorschau scrollt / Then ist die Tabelle horizontal scrollbar und alle Spalten erreichbar (kein harter Abschnitt am rechten Rand).
- Test: Playwright — `.table-wrap` auf `scrollWidth > clientWidth` prüfen

**AC-2:** Given der Wetter-Briefing-Tab auf einem 1440px-Desktop / When ChannelPreviewBlock gerendert wird / Then hat der Block eine Breite > 900px (volle Tab-Breite, nicht `editor-col`-Breite von ~628px).
- Test: Playwright — Bounding Box von `[data-testid="channel-preview-block"]` auf 1440px-Viewport messen

**AC-3:** Given Email-Vorschau mit 5 primären Metriken / When Desktop-Mail-Ansicht aktiv / Then sind alle 5 Spalten ohne Scrollen vollständig sichtbar (kein Abschneiden am rechten Rand).
- Test: Playwright — `scrollWidth === clientWidth` bei 5-Metriken-Trip auf 1440px

**AC-4:** Given bestehende data-testids / When Fix deployed / Then sind `data-testid="channel-preview-block"` und `data-testid="channel-fidelity-email"` weiterhin im DOM vorhanden (keine Regression durch Verschiebung).
- Test: Playwright — Existenz beider Selektoren nach DOM-Aufbau prüfen

## Known Limitations

- **Wizard-Kontext bewusst ausgenommen:** In `Step4Layout` (Wizard + Compare) bleibt ChannelPreviewBlock in `preview-col`. Das Side-by-Side-Layout ist dort gewollt. Eine vereinheitlichende Lösung (z.B. max-width-Prop) ist Out of Scope dieses Fixes.
- **Kein Unit-Test für CSS-Merge:** Tailwind-Merge-Verhalten (`overflow-visible` überschreibt `overflow-hidden`) ist durch AC-1/AC-3 Playwright-Tests abgedeckt; ein isolierter CSS-Unit-Test existiert nicht.

## Out of Scope

- Änderungen an `card.svelte` (shadcn-Basiskomponente)
- Layout-Anpassungen in `Step4Layout.svelte` (Wizard oder Compare)
- Neue Metriken oder Channel-Konfigurationslogik

## Changelog

- 2026-06-01: Initial spec erstellt. Behebt zwei Layout-Regressions aus Issue #496 Deploy: overflow-hidden blockiert Email-Tabellen-Scroll (Bug 1) und editor-col-Einschränkung macht ChannelPreviewBlock zu schmal in WeatherMetricsTab (Bug 2).
