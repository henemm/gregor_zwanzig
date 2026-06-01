---
id: bug_499_skala_label
title: "Bug #499 — Label «Skala» durch «Einfach» ersetzen"
status: draft
workflow: bug-499-skala-label
issue: 499
created: 2026-05-31
---

## Problem

Im Wetter-Metriken-Tab (`#weather`) und in Konfigurations-Dialogen wird das Label
"Skala" verwendet, wenn eine Metrik in menschlich lesbarer Form (z.B. "stark" statt
"35 km/h") angezeigt wird. Nutzer verwechseln "Skala" mit einem Messinstrument mit
Zeiger — die Bedeutung ist unklar.

## Lösung

"Skala" wird app-weit durch **"Einfach"** ersetzt. Der interne Code-Begriff bleibt
unverändert (`friendlyMap`, `indicatorCapable` etc. — nur UI-Labels ändern sich).

## Betroffene Dateien

| Datei | Stelle | Alt → Neu |
|-------|--------|-----------|
| `frontend/src/lib/components/trip-detail/ActiveMetricRow.svelte` | Z. 45 aria-label | `"Roh oder Skala"` → `"Roh oder Einfach"` |
| `frontend/src/lib/components/trip-detail/ActiveMetricRow.svelte` | Z. 59 Button | `Skala` → `Einfach` |
| `frontend/src/lib/components/WeatherConfigDialog.svelte` | Z. 15 | `scale: 'Skala'` → `scale: 'Einfach'` |
| `frontend/src/lib/components/trip-wizard/steps/Step3Weather.svelte` | Z. 81 | `scale: 'Skala'` → `scale: 'Einfach'` |
| `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte` | Z. 171 | `als Skala` → `als Einfach` |
| `frontend/src/lib/components/trip-detail/TablePreview.svelte` | Z. 108 | `·skala` → `·einfach` |

## Acceptance Criteria

**AC-1:** Given der Wetter-Metriken-Editor ist geöffnet /
When eine Metrik mit Indikator-Fähigkeit angezeigt wird /
Then zeigt der Toggle-Button "Roh" und "Einfach" (nicht "Skala").

**AC-2:** Given der Format-Modus-Dropdown (WeatherConfigDialog oder Wizard Step 3) ist geöffnet /
When die Optionen aufgelistet werden /
Then erscheint "Einfach" als Option (nicht "Skala") für den scale-Wert.

**AC-3:** Given ein Preset gespeichert wird /
When die Zusammenfassung angezeigt wird /
Then steht "X als Einfach" (nicht "als Skala").

**AC-4:** Given die Tabellen-Vorschau eine Indikator-Spalte zeigt /
When der Spalten-Header gerendert wird /
Then lautet das Suffix "·einfach" (nicht "·skala").

## Nicht geändert

- Interne Code-Bezeichner: `friendlyMap`, `indicatorCapable`, `useIndicator`, `INDICATOR_MAP`, `has_friendly_format`
- API-Werte: `format_mode: 'scale'` bleibt unverändert (Backend-Vertrag)
- Testids: `data-testid="metric-mode-scale-*"` bleibt (keine UI-Test-Regression)
