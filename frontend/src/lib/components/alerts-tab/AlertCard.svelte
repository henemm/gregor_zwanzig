<script lang="ts">
	// Issue #638 — AlertCard: Karten-Modell pro Alert (JSX TE2_AlertsTab 1:1).
	// Karte: Label · Metrik · Bedingung (mono) · Switch · Kanal-Chips.

	import type { AlertRule } from '$lib/types';

	let {
		rule = $bindable(),
		activeChannels,
	}: {
		rule: AlertRule;
		activeChannels: string[];  // channels active in report_config
	} = $props();

	function toggleEnabled() {
		rule = { ...rule, enabled: !rule.enabled };
	}

	// Issue #817: Δ-Framing — zeigt "Δ ≥ threshold unit" statt "metric · threshold unit"
	const metricCondition = $derived(`Δ ≥ ${rule.threshold} ${rule.unit ?? ''}`.trim());
</script>

<div
	class="alert-card"
	class:active={rule.enabled}
	data-testid="alert-card-{rule.id}"
>
	<div class="card-header">
		<div class="card-label-block">
			<div class="card-label">{rule.metric}</div>
			<div class="card-mono">{metricCondition}</div>
		</div>
		<!-- Switch: An/Aus (tone="accent") -->
		<button
			type="button"
			role="switch"
			aria-checked={rule.enabled}
			class="switch"
			class:switch-on={rule.enabled}
			onclick={toggleEnabled}
			data-testid="alert-switch-{rule.id}"
		>
			<span class="switch-thumb"></span>
		</button>
	</div>

	<!-- Threshold-Zeile (editierbar; Issue #817: Δ-Label statt absoluter "Schwelle:") -->
	<div class="threshold-row">
		<span class="threshold-label">Melde ab Änderung:</span>
		<input
			type="number"
			class="threshold-input"
			value={rule.threshold}
			oninput={(e) => {
				const n = parseFloat((e.target as HTMLInputElement).value);
				if (!isNaN(n)) rule = { ...rule, threshold: n };
			}}
			step="1"
			min="0"
		/>
		<span class="threshold-unit">{rule.unit ?? ''}</span>
	</div>

	<!-- Trennlinie + Kanal-Chips (read-only, Issue #701) -->
	<div class="card-channels">
		<span class="channel-label">Kanal:</span>
		{#each activeChannels as ch}
			<span
				class="channel-chip chip-active"
				data-testid="ch-ro-{rule.id}-{ch}"
			>
				{ch.charAt(0).toUpperCase() + ch.slice(1)}
			</span>
		{/each}
	</div>
</div>

<style>
	.alert-card {
		padding: 18px;
		background: var(--g-card);
		border: 1px solid var(--g-rule-soft);
		border-radius: var(--g-r-2);
	}
	.alert-card.active {
		border-left: 3px solid var(--g-accent);
	}
	.card-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 12px;
		margin-bottom: 12px;
	}
	.card-label {
		font-size: 15px;
		font-weight: 600;
	}
	.card-mono {
		font-size: 11px;
		color: var(--g-ink-3);
		margin-top: 3px;
		font-family: var(--g-font-mono);
	}
	/* Switch */
	.switch {
		flex-shrink: 0;
		width: 36px;
		height: 20px;
		border-radius: 10px;
		border: none;
		cursor: pointer;
		background: var(--g-rule);
		position: relative;
		padding: 0;
		transition: background 120ms;
	}
	.switch.switch-on {
		background: var(--g-accent);
	}
	.switch-thumb {
		position: absolute;
		top: 2px;
		left: 2px;
		width: 16px;
		height: 16px;
		border-radius: 50%;
		background: var(--g-paper);
		transition: transform 120ms;
	}
	.switch.switch-on .switch-thumb {
		transform: translateX(16px);
	}
	/* Threshold row */
	.threshold-row {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-bottom: 12px;
	}
	.threshold-label {
		font-size: 12px;
		color: var(--g-ink-3);
		min-width: 60px;
	}
	.threshold-input {
		width: 72px;
		border: 1px solid var(--g-rule);
		border-radius: 4px;
		padding: 4px 8px;
		font-size: 14px;
		font-family: var(--g-font-mono, monospace);
		background: var(--g-card);
		color: var(--g-ink);
	}
	.threshold-unit {
		font-size: 12px;
		color: var(--g-ink-3);
	}
	/* Channels row */
	.card-channels {
		padding-top: 12px;
		border-top: 1px solid var(--g-rule-soft);
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
	}
	.channel-label {
		font-size: 12px;
		color: var(--g-ink-3);
	}
	.channel-chip {
		font-size: 12.5px;
		font-weight: 500;
		padding: 4px 10px;
		border-radius: 4px;
		cursor: default;
		background: var(--g-paper-deep);
		color: var(--g-ink-4);
		border: 1px solid var(--g-rule);
	}
	.channel-chip.chip-active {
		background: var(--g-ink);
		color: var(--g-paper);
		border-color: var(--g-ink);
	}

	@media (max-width: 899px) {
		.alert-card {
			padding: 14px;
		}
		.channel-chip {
			min-height: 36px;
			padding: 6px 12px;
			font-size: 13px;
			display: inline-flex;
			align-items: center;
		}
		.threshold-input {
			width: 120px;
			min-height: 40px;
			font-size: 15px;
		}
	}
</style>
