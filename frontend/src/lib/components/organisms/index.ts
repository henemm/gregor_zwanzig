// Epic #471 — Organisms-Schicht: kanonische Re-Export-Barrel.
//
// Eine Quelle fuer alle Organisms:
//   import { TripHeader, TripWizardShell, AlertRulesEditor, OutputLayoutEditor,
//            WeatherMetricsTab, ChannelPreviewBlock, ChannelPreviewCard,
//            MetricGroup, MetricCheckbox }
//     from '$lib/components/organisms';
//
// Barrel-Pattern: physische .svelte-Dateien verbleiben in ihren Feature-Ordnern.
// Organisms importieren nur aus atoms/, molecules/ oder anderen organisms/ (kein ui/).
//
// Spec: docs/specs/modules/epic_471_organisms_layer.md
//       docs/specs/modules/issue_520_organisms_barrel_completeness.md

export { default as TripHeader } from '../trip-detail/TripHeader.svelte';
export { default as TripWizardShell } from '../trip-wizard/TripWizardShell.svelte';
export { default as AlertRulesEditor } from '../alert-rules-editor/AlertRulesEditor.svelte';
export { default as OutputLayoutEditor } from '../shared/OutputLayoutEditor.svelte';

// Issue #520 — trip-detail Organisms aufnehmen
export { default as WeatherMetricsTab }   from '../trip-detail/WeatherMetricsTab.svelte';
export { default as ChannelPreviewBlock } from '../trip-detail/ChannelPreviewBlock.svelte';
export { default as ChannelPreviewCard }  from '../trip-detail/ChannelPreviewCard.svelte';
export { default as MetricGroup }         from '../trip-detail/MetricGroup.svelte';
export { default as MetricCheckbox }      from '../trip-detail/MetricCheckbox.svelte';

// Issue #578 — Block C: neue Home-Organisms + Metrics-Organisms
export { default as HomeHeroTrip }             from './HomeHeroTrip.svelte';
export { default as HomeHeroCompare }          from './HomeHeroCompare.svelte';
export { default as OutboxCard }               from './OutboxCard.svelte';
export { default as AlertsCard }               from './AlertsCard.svelte';
export { default as PresetRail }               from './PresetRail.svelte';
export { default as MetricOffShelf }           from './MetricOffShelf.svelte';
export { default as MetricsEditorContextBar }  from './MetricsEditorContextBar.svelte';
