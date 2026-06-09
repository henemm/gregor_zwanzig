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

	// Effective channels for this rule: rule.channels if set, else all activeChannels
	const effectiveChannels = $derived(
		rule.channels && rule.channels.length > 0
			? rule.channels
			: [...activeChannels]
	);

	function toggleChannel(ch: string) {
		const current = rule.channels && rule.channels.length > 0
			? [...rule.channels]
			: [...activeChannels];
		const idx = current.indexOf(ch);
		if (idx >= 0) {
			current.splice(idx, 1);
		} else {
			current.push(ch);
		}
		rule = { ...rule, channels: current };
	}

	function toggleEnabled() {
		rule = { ...rule, enabled: !rule.enabled };
	}

	// Label for metric · condition
	const metricCondition = $derived(`${rule.metric} · ${rule.threshold} ${rule.unit ?? ''}`);
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

	<!-- Trennlinie + Kanal-Chips -->
	<div class="card-channels">
		<span class="channel-label">Kanal:</span>
		{#each activeChannels as ch}
			<button
				type="button"
				class="channel-chip"
				class:chip-active={effectiveChannels.includes(ch)}
				onclick={() => toggleChannel(ch)}
				data-testid="channel-chip-{rule.id}-{ch}"
			>
				{ch.charAt(0).toUpperCase() + ch.slice(1)}
			</button>
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
		cursor: pointer;
		background: var(--g-paper-deep);
		color: var(--g-ink-4);
		border: 1px solid var(--g-rule);
		transition: background 100ms, color 100ms;
	}
	.channel-chip.chip-active {
		background: var(--g-ink);
		color: var(--g-paper);
		border-color: var(--g-ink);
	}
</style>
