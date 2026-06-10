---
entity_id: issue_702_alerts_mobile_parity
type: module
created: 2026-06-10
updated: 2026-06-10
status: draft
version: "1.0"
tags: [alerts, mobile, frontend, epic-700]
---

# Issue #702 — Alerts-Tab Mobile-Parität TM2 (Epic #700, Slice 2/2)

## Approval

- [ ] Approved

## Purpose

Mobile-Umsetzung der metrik-gekoppelten Alerts-Tab (TM2_AlertsTab, ≤899px). Aufbauend auf Slice 1 (#701): rein CSS/Markup, keine Logik-Duplikation. Desktop bleibt byte-identisch.

## Source

- `frontend/src/lib/components/alerts-tab/AlertsTab.svelte`
- `frontend/src/lib/components/alerts-tab/AlertCard.svelte`
- `frontend/src/lib/components/alerts-tab/AlertCooldownCard.svelte`
- `frontend/src/lib/components/alerts-tab/AlertQuietHoursCard.svelte`

## Estimated Scope

- **LoC:** ~60–80
- **Files:** 4 Svelte (CSS-only + minimale Markup-Klassen)
- **Effort:** small

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `AlertsTab.svelte` | Modify | `.actions` auf ≤899px ausblenden, `max-width` aufheben |
| `AlertCard.svelte` | Modify | Mobile-CSS: Channel-Chips Touch-Targets, Threshold-Input, Padding |
| `AlertCooldownCard.svelte` | Modify | Mobile: Input Touch-Target vergrößern |
| `AlertQuietHoursCard.svelte` | Modify | Mobile: Time-Input Touch-Targets vergrößern |

## Acceptance Criteria

**AC-1:** Given Viewport ≤899px, When die Alerts-Tab geöffnet wird, Then ist das Mobile-Layout sichtbar: jede AlertCard nimmt die volle Breite ein, kein „Regel hinzufügen"-Button vorhanden, genau eine Regel pro aktiver Metrik (gemeinsames Datenmodell aus #701).

**AC-2:** Given Viewport ≤899px, When eine AlertCard angezeigt wird, Then haben die Channel-Chips eine Mindesthöhe von 36px und sind tappbar (mind. `padding: 6px 12px`); das Threshold-Input-Feld ist ≥120px breit für komfortable Eingabe.

**AC-3:** Given Viewport ≤899px, When der Alerts-Tab geöffnet ist, Then ist nur ein einziger Save-Button sichtbar (der fixed Mobile-Footer) — der Desktop-`.actions`-Bar ist ausgeblendet.

**AC-4:** Given Viewport ≥900px (Desktop), When die Alerts-Tab geöffnet wird, Then ist das Layout byte-identisch zu vor dieser Änderung — keine Desktop-Regression.

**AC-5:** Given Viewport ≤899px, When Cooldown-Minuten oder Stille-Stunden eingestellt werden, Then sind die Eingabefelder (Number- und Time-Inputs) mind. 44px hoch (WCAG Touch-Target).

## Implementation Details

### AlertsTab.svelte — bestehender `@media (max-width: 899px)` erweitern

```css
@media (max-width: 899px) {
    /* Bereits vorhanden: padding, mobile-footer display:flex */

    /* Neu: Desktop-Save-Bar ausblenden */
    .actions {
        display: none;
    }

    /* Neu: max-width aufheben damit Karten bis Rand laufen */
    .alerts-tab {
        max-width: 100%;
    }
}
```

### AlertCard.svelte — Mobile-Block hinzufügen

```css
@media (max-width: 899px) {
    .alert-card {
        padding: 14px;
    }
    .channel-chip {
        min-height: 36px;
        padding: 6px 12px;
        font-size: 13px;
        display: inline-flex;
        align-items: center;
    }
    .threshold-input {
        width: 120px;
        min-height: 40px;
        font-size: 15px;
    }
}
```

### AlertCooldownCard.svelte + AlertQuietHoursCard.svelte

```css
@media (max-width: 899px) {
    .cooldown-input,
    .time-input {
        min-height: 44px;
        font-size: 16px; /* verhindert iOS-Auto-Zoom */
        width: 100%;
    }
}
```

## Test Strategy

Playwright gegen Staging, Viewport 375×812px:
- Login → Trip-Detail → Alerts-Tab öffnen
- AC-1: Karten vorhanden, kein Add-Rule-Button (`alerts-add-rule` absent)
- AC-2: Channel-Chip bounding-box height ≥36px
- AC-3: `.actions` not visible, `alerts-tab-mobile-footer` visible
- AC-4: Viewport auf 1280×800 → kein Regressions-Check (Desktop-Layout unverändert)
- AC-5: Cooldown-Input bounding-box height ≥44px

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-06-10 | Initial spec |
