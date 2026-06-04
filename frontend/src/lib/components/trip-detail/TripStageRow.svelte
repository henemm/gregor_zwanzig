<script lang="ts">
	import { Pill } from '$lib/components/atoms';
	import type { Stage } from '$lib/types';

	interface Props {
		stage: Stage;
		index: number;
		active?: boolean;
		onclick?: () => void;
	}
	let { stage, index, active = false, onclick }: Props = $props();

	const risk = $derived((stage as Stage & { risk?: string }).risk ?? '');

	const pillTone = $derived(
		risk === 'high' ? 'bad' : risk === 'med' ? 'warn' : 'good'
	);
	const pillLabel = $derived(
		risk === 'high' ? 'Risiko' : risk === 'med' ? 'Achten' : 'OK'
	);

	const wpCount = $derived(stage.waypoints?.length ?? 0);
	const kmVal = $derived((stage as Stage & { distance_km?: number }).distance_km ?? 0);
	const ascentVal = $derived((stage as Stage & { ascent_m?: number }).ascent_m ?? 0);
	const descentVal = $derived((stage as Stage & { descent_m?: number }).descent_m ?? 0);
	const elevVal = $derived((stage as Stage & { elevation_m?: number }).elevation_m ?? 0);
	const summaryVal = $derived((stage as Stage & { summary?: string }).summary ?? '');

	function makeClickHandler() {
		return function doClick() {
			onclick?.();
		};
	}
	const handleClick = makeClickHandler();
</script>

<div
	role="button"
	tabindex="0"
	data-testid="trip-stage-row-{index}"
	style="
		display: grid;
		grid-template-columns: 60px 1fr 280px 100px;
		gap: 16px;
		padding: 14px 18px;
		border-bottom: 1px solid var(--g-rule-soft);
		cursor: pointer;
		border-left: 3px solid {active ? 'var(--g-accent)' : 'transparent'};
		background: {active ? 'rgba(196,90,42,0.05)' : 'transparent'};
	"
	onclick={handleClick}
	onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleClick(); }}
>
	<!-- Col 1: Stage code -->
	<div
		style="
			font-family: var(--g-font-mono, ui-monospace, monospace);
			font-size: 11px;
			color: var(--g-ink-3);
			align-self: center;
		"
	>
		{(stage as Stage & { code?: string }).code ?? String(index + 1).padStart(2, '0')}
	</div>

	<!-- Col 2: Title + meta -->
	<div style="align-self: center; min-width: 0;">
		<div style="font-size: 14px; font-weight: 500; color: var(--g-ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
			{stage.name}
		</div>
		<div style="font-family: var(--g-font-mono, ui-monospace, monospace); font-size: 11px; color: var(--g-ink-3); margin-top: 3px;">
			{stage.date ?? ''}
			{#if kmVal} · {kmVal.toFixed(1)} km{/if}
			{#if ascentVal} · ↑{ascentVal} m{/if}
			{#if descentVal} · ↓{descentVal} m{/if}
			{#if elevVal} · {elevVal} m{/if}
			{#if wpCount} · {wpCount} WP{/if}
		</div>
	</div>

	<!-- Col 3: Summary -->
	<div
		style="
			font-size: 12px;
			font-style: italic;
			color: var(--g-ink-2);
			align-self: center;
			overflow: hidden;
			display: -webkit-box;
			-webkit-line-clamp: 2;
			-webkit-box-orient: vertical;
		"
	>
		{summaryVal}
	</div>

	<!-- Col 4: Risk pill -->
	<div style="align-self: center; display: flex; justify-content: flex-end;">
		<Pill tone={pillTone} label={pillLabel} />
	</div>
</div>
