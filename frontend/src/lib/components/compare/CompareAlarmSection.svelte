<script lang="ts">
	// Issue #1170 — Compare-Editor: Tab „Alarme" (Epic #1095 Scheibe 3/3).
	// Verdrahtet die bestehenden Trip-Alarm-Controls (AlertMetricLevelTable —
	// unveraendert wiederverwendet) gegen wiz.*-State. Kein Kanal-Selektor:
	// Compare-Alarme bleiben E-Mail-only (Festlegung Scheibe 2, #1169).
	//
	// Issue #1232 Scheibe 2b: AlertCooldownCard/AlertQuietHoursCard zogen aus
	// diesem Tab in den geteilten VersandTab (Alert-Zustellung) um. Heading,
	// Radar-/Official-Trigger-Toggle und die Metrik-Level-Tabelle bleiben hier
	// (Korridor-Vorstufe #1231).
	// Spec: docs/specs/modules/issue_1170_compare_alert_config.md,
	//       docs/specs/modules/versand_tab_vergleich.md (Implementation Details Punkt 4)
	import AlertMetricLevelTable from '$lib/components/alerts-tab/AlertMetricLevelTable.svelte';
	import { ALERTABLE_METRICS } from '$lib/components/alerts-tab/alertMetricTable';
	import { Eyebrow } from '$lib/components/atoms';
	import ChannelToggle from '$lib/components/shared/ChannelToggle.svelte';
	import type { CompareWizardState } from './compareWizardState.svelte';
	import type { AlertMetric, SensLevel } from '$lib/types';

	interface Props {
		wiz: CompareWizardState;
	}
	let { wiz }: Props = $props();

	// Compare nutzt einen eigenen Metrik-Namensraum (compareMetricDefs.ts, z.B.
	// "wind_max_kmh"), nicht identisch mit AlertMetric ("wind_gust"). Analog zu
	// CATALOG_TO_ALERT_METRICS (alertMetricTable.ts, Trip-Seite): kleine lokale
	// Mapping-Tabelle Compare-Metrik-Key → AlertMetric.
	const COMPARE_TO_ALERT_METRIC: Record<string, AlertMetric> = {
		wind_max_kmh: 'wind_gust',
		precip_sum_mm: 'precipitation_sum',
		temp_max_c: 'temperature_max',
		thunder_level_max: 'thunder_level',
		snow_new_sum_cm: 'fresh_snow',
		visibility_min_m: 'visibility'
	};

	const activeMetrics = $derived.by(() => {
		const seen = new Set<AlertMetric>();
		for (const key of wiz.activeMetricKeys) {
			const mapped = COMPARE_TO_ALERT_METRIC[key];
			if (mapped) seen.add(mapped);
		}
		return ALERTABLE_METRICS.filter((m) => seen.has(m));
	});

	function onLevelChange(metric: AlertMetric, level: SensLevel) {
		wiz.metricAlertLevels = { ...wiz.metricAlertLevels, [metric]: level };
	}
</script>

<div class="compare-alarm-section" data-testid="compare-alarm-section">
	<Eyebrow>Alarme · Sofort-Meldung</Eyebrow>

	<ChannelToggle
		label="Radar-Alarm"
		checked={wiz.radarAlertEnabled}
		onchange={(checked) => (wiz.radarAlertEnabled = checked)}
		testid="compare-alarm-radar-toggle"
	/>

	<ChannelToggle
		label="Amtliche-Warnungen-Alarm"
		checked={wiz.officialAlertTriggersEnabled}
		onchange={(checked) => (wiz.officialAlertTriggersEnabled = checked)}
		testid="compare-alarm-official-toggle"
	/>

	{#if activeMetrics.length === 0}
		<p class="no-metrics-hint" data-testid="compare-alarm-no-metrics">
			Wähle im Tab „Wertebereiche" Metriken aus, um Alarm-Schwellen zu konfigurieren.
		</p>
	{:else}
		<AlertMetricLevelTable
			activeMetrics={activeMetrics as AlertMetric[]}
			levels={wiz.metricAlertLevels as Record<AlertMetric, SensLevel>}
			{onLevelChange}
		/>
	{/if}
</div>

<style>
	.compare-alarm-section {
		display: flex;
		flex-direction: column;
		gap: 14px;
		position: relative;
		padding: 28px 40px 60px;
		max-width: 900px;
	}

	.no-metrics-hint {
		margin: 0;
		padding: 24px;
		background: var(--g-card, #ffffff);
		border: 1px solid var(--g-line, #e2ddd2);
		border-radius: 12px;
		color: var(--g-ink);
		font-size: 16px;
	}

	@media (max-width: 899px) {
		.compare-alarm-section {
			padding: 1rem;
			max-width: 100%;
		}
	}
</style>
