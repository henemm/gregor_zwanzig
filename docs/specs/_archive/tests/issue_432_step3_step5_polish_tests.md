---
entity_id: issue_432_step3_step5_polish_tests
type: tests
created: 2026-05-28
updated: 2026-05-28
status: draft
version: "1.0"
tags: [tests, frontend, wizard, step3, step5, issue-432, epic-428]
parent: issue_432_step3_step5_polish
phase: phase5_tdd_red
---

# Issue #432 — Step 3 Wetter-Umbau + Step 5 Reports (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für `docs/specs/modules/issue_432_step3_step5_polish.md`. Jeder Test mappt auf ein Acceptance Criterion der Parent-Spec (AC-1..AC-15). Reine Source-Inspection-Tests (`readFileSync`) — kein Svelte-Renderer, kein Mock. Konsistent mit dem etablierten Pattern aus Issues #429, #430+#431.

Parent-Spec: `docs/specs/modules/issue_432_step3_step5_polish.md` v1.0

## Source

Drei Test-Dateien:

- `frontend/src/lib/components/trip-wizard/__tests__/issue_432_step3_weather.test.ts` (NEU) — Step3Weather-Umbau (HorizonChip-Entfernung, Format-Dropdown, Kategorien-Gruppen, Sticky-Header).
- `frontend/src/lib/components/trip-wizard/__tests__/issue_432_step5_reports.test.ts` (NEU) — Step5Reports (Datei-Existenz, 3 Cards statt 4, Trend-Toggle, Kanal-Chips).
- `frontend/src/lib/components/trip-wizard/__tests__/issue_432_shell_step5_import.test.ts` (NEU) — TripWizardShell-Import-Swap auf Step5Reports.

## Test Inventory

### Step 3 Wetter (`issue_432_step3_weather.test.ts`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_step3_no_horizonchip_import` | AC-1 | `Step3Weather.svelte` enthält keinen Import von `HorizonChip` mehr. |
| `test_ac1_step3_no_horizonchip_tags` | AC-1 | `Step3Weather.svelte` Template enthält kein `<HorizonChip`-Tag mehr. |
| `test_ac2_step3_format_dropdown_per_metric` | AC-2 | `Step3Weather.svelte` enthält `<select>` (oder Select-Atom) mit 4 `<option>`-Werten: `raw`, `scale`, `simplified`, `symbol`. |
| `test_ac3_step3_five_category_groups` | AC-3 | `Step3Weather.svelte` rendert die 5 Kategorien-Labels (Temperatur, Wind, Niederschlag, Atmosphäre, Winter / Schnee) als Eyebrow-Header. |
| `test_ac4_step3_loads_metrics_from_api` | AC-4 | `Step3Weather.svelte` ruft `api.get('/api/metrics')` (oder äquivalent) auf — kein hartcodiertes 6-Metriken-Array mehr. |
| `test_ac5_step3_sticky_group_headers` | AC-5 | `Step3Weather.svelte` enthält CSS-Regel `position: sticky` für Gruppen-Header. |
| `test_ac6_step3_counter_header` | AC-6 | `Step3Weather.svelte` enthält den Zähler-Header „METRIKEN" + „AKTIV VON" (Source-Inspect). |
| `test_ac7_step3_fade_indicator` | AC-7 | `Step3Weather.svelte` enthält einen Fade-Indikator (CSS-Gradient-Maske oder dediziertes `data-testid="step3-scroll-fade"`). |

### Step 5 Reports (`issue_432_step5_reports.test.ts`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac8_step5_reports_file_exists` | AC-12 | `Step5Reports.svelte` existiert unter `steps/`. |
| `test_ac8_step4_reports_file_removed` | AC-12 | `Step4Reports.svelte` existiert NICHT mehr (Datei-Umbenennung). |
| `test_ac9_step5_has_three_cards` | AC-7 | `Step5Reports.svelte` enthält die 3 Eyebrow-Texte „Abend-Briefing", „Morgen-Update", „Warnungen" — kein vierter Eyebrow „Mehrtages-Trend" als Card-Header. |
| `test_ac9_step5_no_trend_card` | AC-7 | `Step5Reports.svelte` hat keinen `data-testid="card-trend"` mehr (alte Card-ID). |
| `test_ac10_step5_evening_card_has_trend_toggle` | AC-8 | `Step5Reports.svelte` enthält in der evening-Card einen Toggle „3–7-Tage-Ausblick" (Switch-Atom oder `<input type="checkbox">` mit zugehörigem Label-Text). |
| `test_ac11_step5_warnings_no_autark_pill` | AC-9 | `Step5Reports.svelte` enthält keinen `<Pill ... >AUTARK</Pill>` mehr. |
| `test_ac12_step5_no_deine_kanaele_card` | AC-10 | `Step5Reports.svelte` enthält keinen `data-testid="card-channels"` (die alte „DEINE KANÄLE"-Karte) und keinen Eyebrow-Text „DEINE KANÄLE". |
| `test_ac13_step5_channel_chips_per_card` | AC-11 | `Step5Reports.svelte` enthält Kanal-Chips pro Card — pro Report-Card erscheinen die vier Kanal-Identifier (`email`, `signal`, `telegram`, `sms`) im Card-Block. |
| `test_ac14_step5_time_inputs_lang_de` | AC-13 (Bug #422 Härtung) | `Step5Reports.svelte` enthält `<input type="time"` mit `lang="de"` (bleibt erhalten). |

### Shell-Import-Swap (`issue_432_shell_step5_import.test.ts`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac15_shell_imports_step5_reports` | AC-14 | `TripWizardShell.svelte` importiert `Step5Reports` und NICHT mehr `Step4Reports`. |
| `test_ac15_shell_mounts_step5_at_currentstep_5` | AC-14 | `TripWizardShell.svelte` mountet `<Step5Reports />` (nicht `<Step4Reports />`) bei `currentStep === 5`. |

### Trend-Persistenz (`issue_432_trend_persistence.test.ts`) — Scope-Erweiterung 2026-05-28 (schließt Issue #437)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac16_wizard_state_trend_enabled_default_true` | AC-16 / AC-18 | `wizardState.svelte.ts` deklariert `trendEnabled = $state<boolean>(true)` mit Default true (BC). |
| `test_ac16_to_trip_payload_writes_multi_day_trend_evening` | AC-16 | `toTripPayload()` schreibt `rc.multi_day_trend_evening` aus `this.trendEnabled`. |
| `test_ac19_step5_binds_toggle_to_wizard_trend_enabled` | AC-19 | `Step5Reports.svelte` bindet `<input type="checkbox" bind:checked={wizard.trendEnabled} data-testid="evening-trend-toggle">`. |
| `test_ac19_step5_no_local_trend_state` | AC-19 | `Step5Reports.svelte` enthält KEIN `let trendEnabled = $state(...)` mehr. |
| `test_ac18_trend_default_true_bc` | AC-18 | (Doppelt mit AC-16 — Default true ist die BC-Garantie). |

## RED-Phase-Erwartung

Vor der Implementierung:
- Step 3: HorizonChip-Imports/-Tags noch vorhanden → AC-1-Tests rot. Kein Format-Dropdown, kein Kategorien-Header, kein Sticky-Header — AC-2..AC-7 rot.
- Step 5: `Step5Reports.svelte` existiert nicht (heute `Step4Reports.svelte`) → AC-8 + AC-9 (existsSync) rot. AUTARK-Pill und DEINE-KANÄLE-Karte sind heute noch da — AC-11 + AC-12 rot. Trend-Toggle existiert nicht — AC-10 rot. Kanal-Chips pro Card fehlen — AC-13 rot.
- Shell: importiert noch `Step4Reports` → AC-15 rot.

Erwartete RED-Rate: ≥80 % der Tests scheitern. Die Ausnahmen:
- `test_ac14_step5_time_inputs_lang_de` läuft heute schon grün (Bug #422 ist live). Regression-Sentinel.

## Expected Behavior

- **Input:** Source-Files der Wizard-Step-Komponenten.
- **Output:** Substring-/Regex-Asserts.
- **Side effects:** Keine.

## Acceptance Criteria

**AC-T1:** Given die drei Test-Files unter `frontend/src/lib/components/trip-wizard/__tests__/issue_432_*.test.ts` /
When `node --experimental-strip-types --test`-Lauf ausgeführt wird /
Then schlagen mindestens 80 % der Tests in der RED-Phase mit AssertionError / ENOENT fehl, weil Komponenten/Imports/Markup-Strings noch nicht vorhanden sind.

**AC-T2:** Given die GREEN-Phase ist abgeschlossen /
When derselbe Lauf wiederholt wird /
Then sind alle Tests grün und alle 15 ACs der Parent-Spec sind durch mindestens einen Test belegt — kein Test wurde stillgelegt oder geskipt.

## Known Limitations

- AC-4 (Catalog-Load) lässt sich per Source-Inspect nur indirekt prüfen (Substring-Match auf `api.get('/api/metrics')` oder den Import-Pfad). Echtes Reaktivitäts-Testing erfolgt manuell gegen Staging.
- Trend-Toggle-State-Persistierung (Issue #437) ist explizit NICHT Teil dieses Manifests.

## Changelog

- 2026-05-28: Initial test manifest für Issue #432 (PR 4/4 von Epic #428).
