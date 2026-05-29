# Context: Issue #442 — Compare Wizard Step 4 Layout

## Request Summary

Wizard Step 4 für den Orts-Vergleich: Der Nutzer wählt pro Kanal (E-Mail/Telegram/Signal/SMS), welche Metriken im Briefing erscheinen. Direkte Wiederverwendung der Infrastruktur aus dem Trip-Wizard (Issue #430/#431).

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/compare/steps/Step4Layout.svelte` | **NEU** — Haupt-Komponente (analog Trip-Wizard Step4Layout) |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | **MODIFY** — `channelLayouts`-Feld + Persistenz in save() |
| `frontend/src/lib/components/compare/CompareWizard.svelte` | **MODIFY** — Step4 im `{#if currentStep === 4}` routen |
| `frontend/src/routes/compare/[id]/edit/+page.svelte` | **MODIFY** — `state.channelLayouts` aus `display_config.channel_layouts` prefüllen |
| `frontend/src/lib/components/shared/OutputLayoutEditor.svelte` | Wiederverwendet (Bucket-Editor, SMS-Sonderfall) |
| `frontend/src/lib/components/trip-detail/ChannelPreviewBlock.svelte` | Wiederverwendet (Live-Vorschau) |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts` | Utils: `autoAssign`, `buildWeatherConfigMetrics`, `move`, `reorder`, `CHANNEL_COL_BUDGET` |
| `frontend/src/lib/components/trip-wizard/steps/Step4Layout.svelte` | **Vorlage** — 1:1-Muster für Compare Step4 |
| `frontend/src/lib/types.ts` | `ChannelLayouts`, `WeatherConfigMetric` — bereits vorhanden |

## Bestehende Muster

**Trip-Wizard Step4Layout.svelte** ist die direkte Vorlage. Muster:
1. `onMount` lädt Catalog + Templates + UserPresets parallel per API
2. Pro-Kanal-State: `channelBuckets`, `channelFriendly`, `channelHorizons`, `channelSelectedPreset`
3. `$effect` syncronisiert State → `wizard.channelLayouts` (kompletter Replace pro Tick)
4. `bucketsForChannel(ch)` liest aus gespeichertem State ODER Fallback
5. Channel-Tabs als `role="tablist"` mit styled buttons
6. Layout: `editor-row` Grid (2:1 — Editor links, Vorschau rechts)

**Compare-Abweichungen** gegenüber Trip-Wizard:
- State-Klasse: `CompareWizardState` statt `WizardState`
- Context-Key: `'compare-wizard-state'` statt `'trip-wizard-state'`
- Fallback für `bucketsForChannel`: `autoAssign([], catalog)` — kein Step-3 `weatherMetrics` im Compare-Wizard
- Kanal-Constraints gemäß `CHANNEL_COL_BUDGET`: email=∞, telegram=7, signal=5, sms=0
  (Issue-Text nennt 8/6, aber `metricsEditor.ts` ist die Single Source of Truth → 7/5 verwenden)

## State-Erweiterung (compareWizardState.svelte.ts)

Zu ergänzen:
```typescript
channelLayouts = $state<ChannelLayouts | null>(null);
```

In `save()` und `toggleEnabled()` unter `display_config`:
```typescript
if (this.channelLayouts !== null) {
  display_config.channel_layouts = this.channelLayouts;
}
```

## Edit-Modus-Prefill (compare/[id]/edit/+page.svelte)

Zu ergänzen nach dem bestehenden `state.region =` Block:
```typescript
const savedLayouts = state.existingDisplayConfig.channel_layouts;
if (savedLayouts) {
  state.channelLayouts = savedLayouts as ChannelLayouts;
}
```

## CompareWizard-Routing (CompareWizard.svelte)

Ersetzen:
```svelte
{:else if state.currentStep === 4}
  <div class="text-...">Schritt 4 — folgt in einem weiteren Issue.</div>
```
Durch:
```svelte
{:else if state.currentStep === 4}
  <Step4Layout />
```

## Dependencies

- Upstream: `metricsEditor.ts` (autoAssign, buildWeatherConfigMetrics, CHANNEL_COL_BUDGET)
- Upstream: `/api/metrics`, `/api/templates`, `/api/metric-presets` APIs
- Downstream: `compareWizardState.save()` → `display_config.channel_layouts` → Backend

## Risks & Considerations

- **Falsche Komponenten-Referenzen im Issue**: Issue #442 nennt `LayoutChannelTabs` und `ColumnSwitchList` als separate Komponenten aus "#407" — beides existiert nicht. Die korrekten Komponenten sind `OutputLayoutEditor` + `ChannelPreviewBlock`.
- **CHANNEL_COL_BUDGET-Divergenz**: Issue-Text nennt telegram=8/signal=6, Code hat 7/5. Code ist maßgebend.
- **Step-3-Fallback**: Step 3 (Idealwerte) noch nicht implementiert im Compare-Wizard → kein `weatherMetrics`-Fallback möglich → leere Liste als Fallback für `autoAssign([], catalog)`.
- **canAdvanceStep4**: Kein Gate — Weiter immer aktiv (wie im Trip-Wizard).
- **Kein Wizard-State-Verlust beim Speichern**: `save()` verwendet `existingDisplayConfig` als Merge-Basis — `channel_layouts` wird additiv gesetzt, andere `display_config`-Felder bleiben erhalten.
