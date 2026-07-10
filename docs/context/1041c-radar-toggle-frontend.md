# Context: Radar-Alarm-Schalter im Compare-Editor (Slice 2/3, #1041)

## Request Summary
Ein Ein/Aus-Schalter „Radar-Alarm" im Orts-Vergleichs-Editor, der das in Slice 1b gelieferte Backend-Feld `radar_alert_enabled` (Default AUS) editierbar macht. Bis dahin nur direkt in `compare_presets.json` setzbar. Folgt exakt dem #1040-Muster (`official_alerts_enabled`).

## Verdrahtungskette (Copy-Vorbild #1040 → neu für radar)

| Datei | Zeile | #1040-Vorbild | Neu (radar) |
|------|------|---------------|-------------|
| `frontend/src/lib/types.ts` | 497 | `official_alerts_enabled?: boolean` im `ComparePreset` | `radar_alert_enabled?: boolean` daneben |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | 40 | `officialAlertsEnabled = $state(true)` | `radarAlertEnabled = $state(false)` (Default AUS) |
| " | 175 | Create-Payload `official_alerts_enabled: this.officialAlertsEnabled` | `radar_alert_enabled: this.radarAlertEnabled` |
| " | 227 | Edit-`edits` `officialAlertsEnabled: this.officialAlertsEnabled` | `radarAlertEnabled: this.radarAlertEnabled` |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | 27 | Interface `officialAlertsEnabled?: boolean` | `radarAlertEnabled?: boolean` |
| " | 104-107 | konditionaler Spread `official_alerts_enabled` | analog `radar_alert_enabled` |
| `frontend/src/routes/compare/[id]/edit/+page.svelte` | 36 | `state.officialAlertsEnabled = data.preset.official_alerts_enabled ?? true` | `state.radarAlertEnabled = data.preset.radar_alert_enabled ?? false` (Default AUS!) |

## Einbaustelle des UI-Toggles
- **`frontend/src/lib/components/compare/CompareAlarmSection.svelte`** (der „Alarme"-Tab, #1170) — semantisch passend (Radar-Alarm ist ein Alarm). NICHT Step5Versand (dort sitzt zwar der #1040-Toggle, aber der ist ein Versand-Inhalt-Flag).
  - Prop `wiz: CompareWizardState` (Zeile 17-19), direkt gelesen/geschrieben.
  - Vorhandene Controls: `AlertMetricLevelTable` (56-60), `AlertCooldownCard` (64), `AlertQuietHoursCard` (65).
  - `ChannelToggle`-Import ergänzen (`$lib/components/trip-wizard/steps/ChannelToggle.svelte`).
  - Toggle-Muster (aus Step5Versand:135-142): `<ChannelToggle label="Radar-Alarm" checked={wiz.radarAlertEnabled} onchange={(checked) => (wiz.radarAlertEnabled = checked)} testid="compare-alarm-radar-toggle" />`
  - Platzierung: eigener Block, z.B. nach `<Eyebrow>` (Zeile 49) / vor `<div class="extra-cards">` (Zeile 63).
- Gerendert in `CompareEditor.svelte:574,730` via `<CompareAlarmSection {wiz} />`.

## E2E-Test-Vorbild
- `frontend/e2e/compare-alarm-config.spec.ts` — Playwright, Alarme-Tab (#1170), `createPreset`-Helper (display_config.active_metrics gesetzt), login-Fixture, Desktop 1280×900. Vorbild für den Radar-Toggle-Roundtrip-Test.
- Boolean-Persistenz-Assert-Muster: `frontend/e2e/issue-1117-official-alerts-content-tab.spec.ts`.

## Risks & Considerations
- **Default AUS ist kritisch:** Hydration `?? false` (nicht `?? true` wie #1040). Sonst würde der Radar-Alarm bei Altpresets fälschlich als „an" angezeigt.
- **JSX/Svelte ist die Wahrheit** — genaue Prop-Namen von `ChannelToggle` aus der echten Komponente übernehmen.
- **Datenfluss-Vollständigkeit:** Toggle → wiz.radarAlertEnabled → Create- UND Edit-Save-Payload → Go RMW (bereits in 1b live) → Backend-Lesung (1b live). Roundtrip (Speichern → neu laden → Zustand bleibt) ist der Kern-E2E-Nachweis.
- Rein additiv, opt-in, kein Umbau bestehender Controls. Frontend-only.

## Type
Feature (Frontend). Scope: 5 Dateien, ~35-50 LoC. Blast Radius niedrig (additiv/opt-in). Uncertainty niedrig (exaktes #1040-Muster). Risk: LOW.
