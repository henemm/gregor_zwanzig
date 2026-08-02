<script lang="ts">
	// Issue #864/#859 — Container: Globaler Quickset + Tabelle aus AlertMetricLevelRow.
	// Spec: docs/specs/modules/feat_864_859_alert_presets.md
	import type { AlertMetric, SensLevel } from '$lib/types';
	import AlertMetricLevelRow from './AlertMetricLevelRow.svelte';
	// #1401 Scheibe B: die Beschriftungen kommen aus dem geteilten Register.
	// Eine zweite Liste hier hatte davon abweichende Namen gefuehrt
	// ("Temperatursturz"/"Regenänderung") — sichtbar in Trip UND Vergleich.
	import { ALERT_METRIC_LABELS } from '$lib/utils/alertMetricLabels';

	interface Props {
		activeMetrics: AlertMetric[];
		levels: Record<AlertMetric, SensLevel>;
		onLevelChange: (metric: AlertMetric, level: SensLevel) => void;
	}

	let { activeMetrics, levels, onLevelChange }: Props = $props();

	const QUICKSET_LEVELS: SensLevel[] = ['off', 'entspannt', 'standard', 'sensibel'];
	const QUICKSET_LABELS: Record<SensLevel, string> = {
		off: 'Aus',
		entspannt: 'Entspannt',
		standard: 'Standard',
		sensibel: 'Sensibel'
	};

	const allSameLevel = $derived(
		activeMetrics.length > 0 &&
			activeMetrics.every((m) => levels[m] === levels[activeMetrics[0]])
	);
	const quicksetActiveLevel = $derived(allSameLevel ? levels[activeMetrics[0]] : null);
	const activeCount = $derived(activeMetrics.filter((m) => levels[m] !== 'off').length);
	const counterLabel = $derived(
		allSameLevel
			? `${activeCount} von ${activeMetrics.length} aktiv`
			: `${activeCount} von ${activeMetrics.length} · gemischt`
	);

	function setAllLevels(level: SensLevel) {
		for (const m of activeMetrics) {
			onLevelChange(m, level);
		}
	}
</script>

<div class="alert-metric-table" data-testid="alert-metric-level-table">
	<div class="quickset" data-testid="alert-quickset">
		<span class="quickset-label">Alle Metriken auf:</span>
		<div class="quickset-controls">
			{#each QUICKSET_LEVELS as l (l)}
				<button
					type="button"
					class:active={quicksetActiveLevel === l}
					aria-pressed={quicksetActiveLevel === l}
					onclick={() => setAllLevels(l)}
					data-testid="alert-quickset-{l}"
				>
					{QUICKSET_LABELS[l]}
				</button>
			{/each}
		</div>
		<span class="counter" data-testid="alert-quickset-counter">{counterLabel}</span>
	</div>

	{#if activeMetrics.length === 0}
		<p class="empty-hint" data-testid="alert-metric-empty">
			Keine alertable Metriken aktiv. Wähle Metriken im Wetter-Metriken-Tab.
		</p>
	{:else}
		<table>
			<thead>
				<tr>
					<th>Metrik</th>
					<th>Empfindlichkeit</th>
					<th>Schwellwert</th>
				</tr>
			</thead>
			<tbody>
				{#each activeMetrics as metric (metric)}
					<AlertMetricLevelRow
						{metric}
						label={ALERT_METRIC_LABELS[metric]?.label_de ?? metric}
						level={levels[metric] ?? 'standard'}
						onChange={onLevelChange}
					/>
				{/each}
			</tbody>
		</table>
	{/if}
</div>

<style>
	.quickset {
		display: flex;
		align-items: center;
		gap: 12px;
		flex-wrap: wrap;
		margin-bottom: 16px;
	}

	.quickset-label {
		font-size: 13px;
		font-weight: 600;
		color: var(--g-ink-2, #555);
	}

	.quickset-controls {
		display: flex;
		gap: 2px;
	}

	.quickset-controls button {
		min-height: 44px;
		padding: 6px 12px;
		border: 1px solid var(--g-rule, #ddd);
		background: transparent;
		color: var(--g-ink);
		cursor: pointer;
		font-size: 14px;
	}

	.quickset-controls button.active {
		background: var(--g-accent, #2563eb);
		color: white;
		border-color: var(--g-accent, #2563eb);
	}

	.counter {
		font-size: 13px;
		color: var(--g-ink-3, #888);
	}

	table {
		width: 100%;
		border-collapse: collapse;
	}
	th {
		text-align: left;
		padding: 8px;
		border-bottom: 1px solid var(--g-rule, #ddd);
		font-size: 12px;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--g-ink-2, #555);
	}

	.empty-hint {
		color: var(--g-ink-3, #888);
		font-style: italic;
	}

	@media (max-width: 899px) {
		.quickset {
			flex-direction: column;
			align-items: flex-start;
		}
		.quickset-controls {
			width: 100%;
		}
		.quickset-controls button {
			flex: 1;
			font-size: 16px;
		}
		table {
			display: block; /* Zeilen werden in AlertMetricLevelRow als Block gerendert */
		}
		thead {
			display: none;
		}
		tbody {
			display: block;
		}
	}
</style>
