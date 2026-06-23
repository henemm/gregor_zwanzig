<script lang="ts">
	// Issue #864/#859 — Eine Metrik-Zeile im Alerts-Tab: Segmented-Control (4 Stufen)
	// + Schwellwert-Anzeige. Spec: docs/specs/modules/feat_864_859_alert_presets.md
	import type { AlertMetric, SensLevel } from '$lib/types';
	import { levelToThreshold } from './alertMetricTable.ts';

	interface Props {
		metric: AlertMetric;
		label: string;
		level: SensLevel;
		onChange: (metric: AlertMetric, level: SensLevel) => void;
	}

	let { metric, label, level, onChange }: Props = $props();

	const LEVELS: SensLevel[] = ['off', 'entspannt', 'standard', 'sensibel'];
	const LABELS_DESKTOP: Record<SensLevel, string> = {
		off: 'Aus',
		entspannt: 'Entspannt',
		standard: 'Standard',
		sensibel: 'Sensibel'
	};
	const LABELS_MOBILE: Record<SensLevel, string> = {
		off: 'Aus',
		entspannt: 'Entsp.',
		standard: 'Std.',
		sensibel: 'Sens.'
	};

	const threshold = $derived(levelToThreshold(metric, level));
	const isDimmed = $derived(level === 'off');
</script>

<tr
	class:dimmed={isDimmed}
	data-testid="alert-metric-row-{metric}"
	data-metric={metric}
	data-level={level}
>
	<td class="metric-label">{label}</td>
	<td class="segmented-control" data-testid="alert-metric-segmented-{metric}">
		{#each LEVELS as l (l)}
			<button
				type="button"
				class:active={level === l}
				onclick={() => onChange(metric, l)}
				aria-pressed={level === l}
				data-testid="alert-level-{metric}-{l}"
			>
				<span class="label-desktop">{LABELS_DESKTOP[l]}</span>
				<span class="label-mobile">{LABELS_MOBILE[l]}</span>
			</button>
		{/each}
	</td>
	<td class="threshold" data-testid="alert-threshold-{metric}">{threshold ?? '—'}</td>
</tr>

<style>
	tr {
		transition: opacity 0.2s;
	}
	tr.dimmed {
		opacity: 0.6;
	}

	.metric-label {
		padding: 8px;
		font-size: 14px;
		color: var(--g-ink);
	}

	.threshold {
		padding: 8px;
		font-family: var(--g-font-mono, monospace);
		font-size: 13px;
		color: var(--g-ink-2, #555);
		white-space: nowrap;
	}

	.segmented-control {
		display: flex;
		gap: 2px;
		padding: 8px;
	}

	.segmented-control button {
		min-height: 44px;
		padding: 8px 10px;
		border: 1px solid var(--g-rule, #ddd);
		background: transparent;
		color: var(--g-ink);
		cursor: pointer;
		font-size: 14px;
	}

	.segmented-control button.active {
		background: var(--g-accent, #2563eb);
		color: white;
		border-color: var(--g-accent, #2563eb);
	}

	.label-mobile {
		display: none;
	}

	@media (max-width: 899px) {
		.label-desktop {
			display: none;
		}
		.label-mobile {
			display: inline;
		}

		tr {
			display: block;
			margin-bottom: 12px;
			border-bottom: 1px solid var(--g-rule-soft, #eee);
			padding-bottom: 8px;
		}

		td {
			display: block;
		}

		.metric-label {
			display: inline-block;
			font-weight: 600;
		}

		.threshold {
			display: inline-block;
			margin-left: 8px;
		}

		.segmented-control {
			width: 100%;
			padding: 8px 0 0;
		}

		.segmented-control button {
			flex: 1;
			font-size: 16px; /* verhindert iOS-Zoom */
		}
	}
</style>
