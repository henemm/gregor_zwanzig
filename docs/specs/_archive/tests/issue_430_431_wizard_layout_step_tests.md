---
entity_id: issue_430_431_wizard_layout_step_tests
type: tests
created: 2026-05-28
updated: 2026-05-28
status: draft
version: "1.0"
tags: [tests, frontend, wizard, stepper, layout-editor, issue-430, issue-431, epic-428]
parent: issue_430_431_wizard_layout_step
phase: phase5_tdd_red
---

# Issue #430 + #431 — Wizard auf 5 Steps + Layout-Editor (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für `docs/specs/modules/issue_430_431_wizard_layout_step.md`. Jeder Test mappt auf ein Acceptance Criterion der Parent-Spec (AC-1..AC-15). Tests sind reine Source-Inspection (`readFileSync`) und Pure-Logic — kein Svelte-Renderer, kein Mock.

Parent-Spec: `docs/specs/modules/issue_430_431_wizard_layout_step.md` v1.0

## Source

Vier Test-Dateien:

- `frontend/src/lib/components/trip-wizard/__tests__/issue_430_431_wizard_state.test.ts` (NEU) — WizardState-Erweiterungen, Pure-Logic-Tests.
- `frontend/src/lib/components/trip-wizard/__tests__/issue_430_431_stepper.test.ts` (NEU) — Stepper-Komponente + `progressBarSegments`-Helper.
- `frontend/src/lib/components/shared/__tests__/OutputLayoutEditor.test.ts` (NEU) — Source-Inspection für trip-agnostischen Editor.
- `frontend/src/lib/components/trip-wizard/__tests__/issue_430_431_step4_layout.test.ts` (NEU) — Step4Layout Source-Inspection + WeatherMetricsTab-Regression.

## Test Inventory

### WizardState (`issue_430_431_wizard_state.test.ts`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac4_wizard_state_current_step_accepts_5` | AC-4 | `WizardState.currentStep` lässt sich auf 5 setzen ohne Typ-Fehler (TS-Compile + Runtime). |
| `test_ac5_next_step_caps_at_5` | AC-5 | `nextStep` von 5 aus bleibt auf 5 (kein Overflow). |
| `test_ac5_prev_step_caps_at_1` | AC-5 | `prevStep` von 1 aus bleibt auf 1. |
| `test_ac5_next_step_advances_through_5_steps` | AC-5 | 1 → 2 → 3 → 4 → 5 funktioniert sequenziell. |
| `test_ac4_can_advance_step_4_returns_true` | AC-4 / Plumbing | `canAdvanceStep4` (Layout) liefert true — kein Gate. |
| `test_ac4_can_advance_step_5_returns_true` | AC-4 / Plumbing | `canAdvanceStep5` (Reports) liefert true — kein Gate. |
| `test_ac4_can_advance_current_at_step_5_returns_true` | AC-4 | `canAdvanceCurrent` mit `currentStep=5` liefert true. |
| `test_ac4_channel_layouts_default_null` | AC-4 / Save-Pipeline | `wizard.channelLayouts` ist initial `null`. |
| `test_ac11_to_trip_payload_omits_channel_layouts_when_null` | AC-11 | `toTripPayload()` schreibt KEIN `display_config.channel_layouts` wenn `channelLayouts === null`. |
| `test_ac11_to_trip_payload_writes_channel_layouts_when_set` | AC-11 | `toTripPayload()` schreibt `display_config.channel_layouts` mit den vier Kanal-Listen wenn nicht null. |

### Stepper + progressBarSegments (`issue_430_431_stepper.test.ts`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_stepper_source_supports_5_steps` | AC-1 | Stepper-Source-File akzeptiert `current: 1\|2\|3\|4\|5` als Prop-Typ. |
| `test_ac2_progress_bar_segments_returns_correct_array` | AC-2 | `progressBarSegments(3, 5)` liefert `['done', 'done', 'active', 'pending', 'pending']`. |
| `test_ac2_progress_bar_segments_first_step` | AC-2 | `progressBarSegments(1, 5)` liefert `['active', 'pending', 'pending', 'pending', 'pending']`. |
| `test_ac2_progress_bar_segments_last_step` | AC-2 | `progressBarSegments(5, 5)` liefert `['done', 'done', 'done', 'done', 'active']`. |
| `test_ac2_stepper_mobile_renders_progress_bar` | AC-2 | Stepper-Mobile-Variante im Source: data-Marker `trip-wizard-stepper-progress` mit 5 Segmenten + done/active/pending-Klassen. |
| `test_ac1_shell_step_labels_have_5_entries` | AC-1 / AC-3 | `TripWizardShell.svelte`-Source enthält 5-Element-`stepLabels`-Array mit Reihenfolge Route/Etappen/Wetter/Layout/Reports. |
| `test_ac3_shell_eyebrow_says_von_5` | AC-3 | `TripWizardShell.svelte`-Source enthält Eyebrow-Text mit "SCHRITT" + "VON 5" + "NEUER TRIP". |
| `test_ac12_save_button_label_trip_speichern` | AC-12 | `TripWizardShell.svelte`-Source: Save-Label "Trip speichern" (oder „Speichern" als zulässiger Bezeichner für die Save-Status-Variante, aber Button-Text auf Step 5 ist "Trip speichern"). |
| `test_ac12_next_button_only_below_step_5` | AC-12 | `TripWizardShell.svelte`-Source: Weiter-Button-Bedingung `currentStep < 5`. |

### OutputLayoutEditor (`OutputLayoutEditor.test.ts`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac6_output_layout_editor_file_exists` | AC-6 | `frontend/src/lib/components/shared/OutputLayoutEditor.svelte` existiert. |
| `test_ac6_output_layout_editor_has_no_api_imports` | AC-6 | Source enthält KEINE `import { api }`, KEIN `from '$lib/api'`, KEIN `fetch(`-Aufruf — trip-agnostisch. |
| `test_ac6_output_layout_editor_has_no_trip_prop` | AC-6 | Source-Inspection: kein `trip:` und kein `Trip` als Prop-Typ. Buckets/friendlyMap/channel sind die Props. |
| `test_ac8_output_layout_editor_sms_branch_present` | AC-8 | Source enthält Conditional `{#if channel === 'sms'}` oder äquivalent — flat-list-Mode für SMS-Channel. |

### Step4Layout + Trip-Detail-Regression (`issue_430_431_step4_layout.test.ts`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac7_step4_layout_file_exists` | AC-7 | `frontend/src/lib/components/trip-wizard/steps/Step4Layout.svelte` existiert. |
| `test_ac7_step4_layout_has_four_channel_tabs` | AC-7 | Source enthält die vier Channel-Tab-Identifier (email/telegram/signal/sms). |
| `test_ac10_step4_layout_imports_channel_preview_block` | AC-10 | Source importiert `ChannelPreviewBlock`. |
| `test_ac9_step4_layout_binds_per_channel_state` | AC-9 | Source verwendet `wizard.channelLayouts` oder bind-equivalent pro Kanal. |
| `test_ac13_weather_metrics_tab_imports_output_layout_editor` | AC-13 | `WeatherMetricsTab.svelte`-Source importiert `OutputLayoutEditor`. |
| `test_ac13_weather_metrics_tab_keeps_save_button` | AC-13 | `WeatherMetricsTab.svelte` behält den Save-Button (`weather-metrics-tab-save` testid). |
| `test_ac15_shell_imports_step4_layout` | AC-15 (Plumbing) | `TripWizardShell.svelte` importiert `Step4Layout` und mountet ihn bei `currentStep === 4`. |

## RED-Phase-Erwartung

Vor der Implementierung:
- WizardState-Tests: `currentStep`-Typ heute `1\|2\|3\|4` — Setzen auf 5 schlägt fehl in TS / Runtime; `canAdvanceStep5`, `channelLayouts`, `toTripPayload`-Erweiterung existieren noch nicht → AttributeError / TypeError.
- Stepper-Tests: `progressBarSegments`-Export fehlt → ImportError; Mobile-Markup nutzt heute `compactStepperText`-Variante.
- Shell-Tests: stepLabels hat 4 Einträge; Eyebrow sagt "VON 4"; Save-Button bei `currentStep < 4`.
- OutputLayoutEditor + Step4Layout: Dateien existieren NICHT → existsSync schlägt fehl.
- WeatherMetricsTab-Tests: Datei importiert noch keinen OutputLayoutEditor.

## Expected Behavior

- **Input:** Source-Files + WizardState-Instanzen.
- **Output:** assertions zu Substring-Matches + Pure-Logic-Werten.
- **Side effects:** Keine (nur read).

## Acceptance Criteria

**AC-T1:** Given alle Test-Files unter `frontend/src/lib/components/.../*issue_430_431*.test.ts` und `OutputLayoutEditor.test.ts` /
When `node --experimental-strip-types --test`-Lauf ausgeführt wird /
Then schlagen mindestens 80 % der Tests in der RED-Phase mit ImportError/AssertionError fehl (Implementierung fehlt).

**AC-T2:** Given die GREEN-Phase ist abgeschlossen /
When derselbe Lauf wiederholt wird /
Then sind alle Tests grün und alle 15 ACs der Parent-Spec sind durch mindestens einen Test belegt — kein Test wurde stillgelegt oder geskipt.

## Known Limitations

- E2E-Tests (Playwright) sind nicht Teil dieses Manifests — sie werden in der GREEN-Phase ergänzt, sobald die Komponenten existieren.
- AC-14 (Live-Preview reagiert auf Bucket-Änderungen) lässt sich ohne Render-Framework nur indirekt prüfen (Source-Inspect: `ChannelPreviewBlock` bekommt reaktive Props). Echte Reaktivitäts-Verifikation bleibt der manuellen Verifikation gegen Staging vorbehalten.
- AC-15 wird durch zwei Source-Inspect-Asserts approximiert (Import + Mount-Stelle); eine vollständige Verifikation der Trip-Detail-Tab-Funktion erfolgt manuell gegen Staging nach dem Deploy.

## Changelog

- 2026-05-28: Initial test manifest für Issue #430 + Issue #431 (PR 2+3 kombiniert von Epic #428).
