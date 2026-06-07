---
entity_id: issue_618_mobile_weather_tab
type: module
created: 2026-06-07
updated: 2026-06-07
status: draft
version: "1.0"
tags: [frontend, mobile, design-compliance, trip-edit]
---

# Issue #618 — Mobile Wetter-Metriken-Tab (Trip bearbeiten 4/4)

## Approval

- [ ] Approved

## Purpose

Volle Handy-Parität für den neuen Wetter-Metriken-Tab: die vier Editor-Abschnitte
vertikal gestapelt, die Mail-Vorschau als von unten einfahrendes Bottom-Sheet
(statt gestapelter Inline-Spalte), ausgelöst über einen fixierten „So kommt es an"-
Button. Der veraltete #415-Accordion-Overlay wird entfernt, weil er der neuen
Design-Vorlage widerspricht und funktional hinter dem Desktop-Editor zurückbleibt.

## Source

- **File:** `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte`
- **Identifier:** `WeatherMetricsTab` (Mobil-Verhalten via `@media (max-width: 899px)` + Sheet-Trigger)
- **SOLL-Quelle:** `claude-code-handoff/current/jsx/screen-trip-edit-v2-mobile.jsx` → `TM2_WetterTab`

## Estimated Scope

- **LoC:** ~120 (Frontend)
- **Files:** 2–3 (`WeatherMetricsTab.svelte`; Entfernen `WeatherMetricsMobileView.svelte` + `.test.ts`)
- **Effort:** medium

## Dependencies

- `frontend/src/lib/components/mobile/Sheet.svelte` (Bottom-Sheet, #373)
- `frontend/src/lib/components/trip-detail/WeatherV2MailPreview.svelte` (Kanal-Tabs Email/Telegram/SMS, Telegram-Overflow)
- `frontend/src/lib/components/trip-detail/WeatherV2Reihenfolge.svelte` (Telegram-Schnittlinie `wm2-cut-line`)
- `frontend/src/lib/components/trip-detail/metricsEditor.ts` (`CHANNEL_COL_BUDGET.telegram = 8`)

## Behavior

Auf Viewports ≤ 899px:
- Die vier Abschnitte (01 Profil · 02 Grundauswahl · 03 Reihenfolge & Darstellung ·
  04 Kanäle) werden einspaltig untereinander gerendert (Reflow des bestehenden
  `.v2-layout`-Grids). Es werden dieselben `WeatherV2*`-Komponenten wie auf dem
  Desktop verwendet → identische Funktionalität (Toggle, Reorder, Roh/Einfach,
  Kanal-Schalter, Preset-Auswahl, Speichern).
- Die Inline-Vorschau-Spalte (`.preview-col`) wird **nicht** angezeigt.
- Stattdessen erscheint ein fixierter „So kommt es an"-Button am unteren Rand mit
  Metrik-Zähler-Badge; ein Tap öffnet ein Bottom-Sheet (`Sheet`), das
  `WeatherV2MailPreview` enthält.
- Der Legacy-Trigger `.mobile-metrics-trigger` und die Komponente
  `WeatherMetricsMobileView` (#415) entfallen vollständig.

Auf Viewports > 899px: unverändert (zweispaltiges Grid mit sticky Vorschau-Spalte).

## Acceptance Criteria

**AC-1:** Given ein eingeloggter Nutzer öffnet einen Trip im Wetter-Metriken-Tab auf
einem Viewport ≤ 899px, When die Seite gerendert ist, Then erscheinen die vier
Abschnitte „01 — Profil", „02 — Grundauswahl", „03 — Reihenfolge & Darstellung" und
„04 — Kanäle" einspaltig vertikal untereinander (nicht in einem zweispaltigen Grid).

**AC-2:** Given derselbe Mobil-Viewport, When der Nutzer den fixierten Button
„So kommt es an" antippt, Then fährt ein Bottom-Sheet von unten ein, das die
Mail-Vorschau (`WeatherV2MailPreview`) enthält; eine inline gestapelte Vorschau-
Spalte ist auf diesem Viewport nicht sichtbar.

**AC-3:** Given die Mail-Vorschau im Bottom-Sheet ist offen und der Telegram-Tab aktiv
mit mehr als 8 aktiven Spalten, When der Nutzer die Reihenfolge-Liste bzw. die
Telegram-Vorschau betrachtet, Then ist die Telegram-Schnittlinie nach Spalte 8
(`[data-testid="wm2-cut-line"]` bzw. Overflow-Hinweis) auch mobil sichtbar.

**AC-4:** Given die Mail-Vorschau im Bottom-Sheet, When der Nutzer die Kanal-Tabs
betrachtet, Then erscheinen genau die Tabs „Email", „Telegram" und „SMS" und kein
Signal-Tab oder Signal-Bezug.

**AC-5:** Given der Mobil-Wetter-Tab, When der Nutzer eine Metrik aktiviert/
deaktiviert, die Reihenfolge ändert, das Roh/Einfach-Format umstellt, einen Kanal
schaltet oder speichert, Then verhält sich der Editor funktional identisch zum
Desktop (gleiche Handler, gleiche Persistenz über `/api/trips/{id}/weather-config`),
und der alte Accordion-Overlay (`WeatherMetricsMobileView`/`.mobile-metrics-trigger`)
existiert nicht mehr.

## Out of Scope

- Andere Mobil-Tabs (Übersicht, Etappen, Zeitplan, Alerts) — eigene Slices/Issues.
- Backend-/Persistenz-Änderungen (keine — Frontend-only).
- SMS-Schwellwerte-Card (#624) im Bottom-Sheet — bleibt im Editor-Fluss, nicht Teil der Vorschau.
- Desktop-Layout (unverändert).

## Test Strategy

Frontend-only Design-Fidelity → Verifikation gegen Staging:
- `staging-validator` (Playwright) als eingeloggter Nutzer auf Mobil-Viewport (≤ 899px):
  AC-1 (vier Abschnitte einspaltig), AC-2 (Button → Sheet, keine Inline-Vorschau),
  AC-3 (Cut-Line sichtbar), AC-4 (Kanal-Tabs ohne Signal), AC-5 (Toggle/Reorder/Save).
- Pixel-Diff gegen aus JSX gerendertes SOLL (`screen-trip-edit-v2-mobile.jsx`).
- KEINE Datei-Inhalt-Checks (Projekt-Regel) — Verhalten im echten DOM beweisen.
