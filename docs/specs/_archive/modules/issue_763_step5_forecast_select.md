---
entity_id: issue_763_step5_forecast_select
type: module
created: 2026-06-11
updated: 2026-06-11
status: draft
version: "1.0"
tags: [frontend, compare, design-system, ios-zoom]
---

# Step 5 Versand — Horizont-Auswahl auf Design-System-Select

## Approval

- [x] Approved

## Purpose

Das native `<select>` für die Horizont-Auswahl (Heute/Morgen/Übermorgen) in der
Versand-Sektion des Orts-Vergleich-Editors wird durch die einheitliche
Design-System-Komponente `Select.svelte` ersetzt — für visuelle Konsistenz und den
iOS-Zoom-Schutz (vgl. #278/#382). Letztes verbliebenes natives Dropdown im Compare-Editor.

## Source

- **File:** `frontend/src/lib/components/compare/steps/Step5Versand.svelte`
- **Identifier:** Horizont-Sektion, `<select data-testid="compare-step5-forecast-hours">`

## Estimated Scope

- **LoC:** ~6
- **Files:** 1 (Produktivcode) + 1 Testdatei
- **Effort:** low

## Dependencies

- `frontend/src/lib/components/ui/select/Select.svelte` (Ziel-Komponente, Export via `ui/select`)
- `frontend/src/lib/components/compare/compareWizardState.svelte.ts` — `forecastHours = $state(48)` (Number)
- Vorbild-Nutzung: `frontend/src/lib/components/compare/PresetHeader.svelte` (Z.84-93, identischer forecastHours-Select)
- Eingebunden durch `CompareEditor.svelte` in **beiden** Modi (`create` + `edit`) → ein Fix deckt Erstellen und Bearbeiten ab.

## Acceptance Criteria

**AC-1:** Given ein eingeloggter Nutzer öffnet im Compare-Editor (Erstellen-Modus, `/compare/new`) den Versand-Tab,
When er die Horizont-Auswahl betrachtet,
Then wird das Feld über die Design-System-Komponente `Select.svelte` gerendert (erkennbar am Chevron-Icon `.gz-select__chevron` und der Wrapper-Klasse `.gz-select`), und es existiert **kein** nacktes natives `<select>` mehr für diesen Test-Selektor außerhalb des `.gz-select`-Wrappers.

**AC-2:** Given die migrierte Horizont-Auswahl im Erstellen-Modus (`/compare/new`),
When der Nutzer „Übermorgen (72 h)" auswählt und speichert,
Then enthält der abgesetzte Request-Payload `forecast_hours: 72` als **Zahl** (nicht `"72"`-String) — der Number-Typ von `state.forecastHours` bleibt über die Komponenten-Umstellung erhalten. (Kritischer Regress-Schutz der Migration.)

**AC-3:** Given der Versand-Tab im Bearbeiten-Modus (`/compare/[id]/edit`) eines bestehenden Vergleichs,
When der Editor geladen wird,
Then wird die Horizont-Auswahl ebenfalls über `Select.svelte` gerendert (gz-select-Wrapper + Chevron, kein natives `<select>`), und der Test-Selektor `compare-step5-forecast-hours` ist funktionsfähig (Optionen wählbar). — Reine Routen-Abdeckung der geteilten `Step5Versand`-Komponente; **nicht** im Scope: ob der gespeicherte Wert vorausgewählt erscheint (siehe Hinweis unten).

**AC-4:** Given die drei Horizont-Optionen,
When das Feld gerendert wird,
Then sind weiterhin exakt die Optionen „Heute (24 h)", „Morgen (48 h)", „Übermorgen (72 h)" mit den Werten 24/48/72 vorhanden (keine Option entfernt/umbenannt/hinzugefügt).

## Out of Scope

- Andere Felder in Step5Versand (Kanäle, Zeitfenster-Number-Inputs, Versandzeit-Kacheln).
- Verhaltens-/Layout-Änderungen über die Komponenten-Umstellung hinaus.
- Backend/Payload-Schema (`forecast_hours` bleibt unverändert).
- **Bestehende Persistenz-Lücke `forecast_hours` im Compare-Editor (NICHT #763):** Das
  `ComparePreset`-Modell (`internal/model/compare_preset.go`, `frontend/src/lib/types.ts`)
  hat **kein** `forecast_hours`-Feld; die Edit-Hydration (`/compare/[id]/edit/+page.svelte`)
  liest den Horizont nicht zurück → im Bearbeiten-Modus zeigt das Feld immer den Default (48 h),
  unabhängig vom gespeicherten Wert. Das ist eine eigenständige Daten-Round-Trip-Lücke,
  von der reinen Komponenten-Umstellung getrennt → **Folge-Issue**.

## Test Strategy

- **E2E (Playwright gegen Staging, eingeloggter Nutzer):** AC-1 (DOM: `.gz-select`-Wrapper + Chevron vorhanden, kein nacktes natives select), AC-2 (Auswahl 72h → Speichern → Payload `forecast_hours===72` numerisch via `waitForResponse`), AC-3 (Edit-Modus: persistierter Wert vorausgewählt), AC-4 (drei Optionen mit Werten 24/48/72).
- **Kein Quelltext-Grep** (Anti-Pattern #754). Nachweis ausschließlich über Nutzerverhalten/DOM gegen Staging.
