<script lang="ts">
	// CompareHourlyLayoutControls — geteilte Stundenverlauf-Steuerung des
	// Ortsvergleich-Layout-Tabs (Toggle + Metrik-Auswahl). Epic #1301 Scheibe F2a.
	// Spec: docs/specs/modules/feat_1301_f2a_compare_new_trip_pattern.md § AC-7
	//
	// Extrahiert 1:1 aus dem Hub-Inline-Markup CompareTabs.svelte:1349-1373 (+ den
	// Handlern isHourlyMetricActive/makeHourlyMetricHandler :707-727). Genutzt vom
	// Hub UND von der Anlege-Seite (/compare/new) — verhindert die Dreifach-Kopie
	// der Metrik-Liste (Anti-Hand-Kopie, {#each ALL_HOURLY_METRICS}).
	//
	// Der Commit-Wrapper (.hub-layout-hourly-wrap mit onchange/onclick am
	// Hub-PUT-Queue bzw. der lokale saveNewPreset-Pfad der Anlege-Seite) bleibt
	// AUSSERHALB dieser Komponente — hier wird nur der reine wiz-State mutiert,
	// die Persistenz-Kopplung liegt beim jeweiligen Aufrufer (Trip/Compare-
	// Teilungs-Invariante: geteilt ist die Steuerung, nicht der Speicher-Weg).
	// Safari-Factory-Pattern für alle Handler (CLAUDE.md).

	import { SectionH } from '$lib/components/atoms';
	import ChannelToggle from '$lib/components/shared/ChannelToggle.svelte';
	import { ALL_HOURLY_METRICS } from '../compare/compareHourlyMetricDefs.ts';
	import type { CompareWizardState } from '../compare/compareWizardState.svelte';

	interface Props {
		wiz: CompareWizardState;
	}
	let { wiz }: Props = $props();

	// Leere Auswahl = „alle aktiv" (Renderer-Default). Erst beim ersten Abwählen
	// wird die volle Liste materialisiert (Hub-Verhalten, CompareTabs.svelte:707).
	function isHourlyMetricActive(key: string): boolean {
		return wiz.hourlyMetricKeys.length === 0 || wiz.hourlyMetricKeys.includes(key);
	}

	function makeHourlyMetricHandler(key: string) {
		return function handleHourlyMetric(checked: boolean): void {
			const current =
				wiz.hourlyMetricKeys.length === 0
					? ALL_HOURLY_METRICS.map((m) => m.key)
					: [...wiz.hourlyMetricKeys];
			if (checked) {
				if (!current.includes(key)) current.push(key);
			} else {
				const idx = current.indexOf(key);
				if (idx >= 0) current.splice(idx, 1);
			}
			wiz.hourlyMetricKeys = current;
		};
	}

	function handleEnabledToggle(checked: boolean): void {
		wiz.hourlyEnabled = checked;
	}
</script>

<SectionH title="Stundenverlauf" />
<ChannelToggle
	label="Stundenverlauf"
	checked={wiz.hourlyEnabled}
	onchange={handleEnabledToggle}
	testid="compare-layout-hourly-enabled-toggle"
/>
<div
	data-testid="compare-layout-hourly-metrics"
	style="display: flex; flex-direction: column; gap: 8px; margin-top: 10px"
>
	{#each ALL_HOURLY_METRICS as metric (metric.key)}
		<ChannelToggle
			label={metric.label}
			checked={isHourlyMetricActive(metric.key)}
			onchange={makeHourlyMetricHandler(metric.key)}
			testid={`compare-layout-hourly-metric-${metric.key}`}
		/>
	{/each}
</div>
