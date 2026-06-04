<script lang="ts">
	// StageCard — kompakte Etappen-Karte für Wegpunkt-Editor.
	// Issue #585: Design-Fidelity 1:1 nach screen-waypoint-editor.jsx
	// Inline SVG-Polyline (MiniSpark), width 200px, border statt outline für aktiven Zustand.

	import { isPauseStage, formatStageNumber } from '$lib/components/trip-wizard/wizardHelpers';
	import type { Stage } from '$lib/types';

	interface Props {
		stage: Stage;
		index: number;
		active?: boolean;
		onclick?: () => void;
		onRemove?: () => void;
	}

	let { stage, index, active = false, onclick, onRemove }: Props = $props();

	const isPause = $derived(isPauseStage(stage));
	const elevData = $derived(stage.waypoints.map((wp) => wp.elevation_m ?? 0));
	const stageLabel = $derived(formatStageNumber(index));

	const totalKm = $derived(
		(() => {
			if (!stage.waypoints || stage.waypoints.length < 2) return null;
			let dist = 0;
			for (let i = 1; i < stage.waypoints.length; i++) {
				const a = stage.waypoints[i - 1];
				const b = stage.waypoints[i];
				const dlat = (b.lat - a.lat) * 111.32;
				const dlon = (b.lon - a.lon) * 111.32 * Math.cos((a.lat * Math.PI) / 180);
				dist += Math.sqrt(dlat * dlat + dlon * dlon);
			}
			return dist;
		})()
	);

	const ascent = $derived(
		(() => {
			if (!stage.waypoints || stage.waypoints.length < 2) return null;
			let up = 0;
			for (let i = 1; i < stage.waypoints.length; i++) {
				const diff = (stage.waypoints[i].elevation_m ?? 0) - (stage.waypoints[i - 1].elevation_m ?? 0);
				if (diff > 0) up += diff;
			}
			return up > 0 ? up : null;
		})()
	);

	function handleClick(): void {
		onclick?.();
	}

	function handleKeydown(e: KeyboardEvent): void {
		if (onclick && (e.key === 'Enter' || e.key === ' ')) {
			e.preventDefault();
			onclick();
		}
	}

	function makeRemoveClick() {
		return (e: MouseEvent) => {
			e.stopPropagation();
			onRemove?.();
		};
	}
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<div
	data-testid={isPause ? `stage-card-pause-${index}` : `stage-card-${index}`}
	style="
		width: 200px;
		min-height: 88px;
		padding: 10px 12px;
		flex-shrink: 0;
		display: flex;
		flex-direction: column;
		gap: 4px;
		border-radius: 4px;
		cursor: {onclick ? 'pointer' : 'default'};
		background: {isPause ? 'var(--g-card-alt)' : 'var(--g-card)'};
		border: {active ? '2px solid var(--g-accent)' : (isPause ? '1px dashed var(--g-rule)' : '1px solid var(--g-rule)')};
		position: relative;
	"
	role={onclick ? 'button' : undefined}
	tabindex={onclick ? 0 : undefined}
	onclick={onclick ? handleClick : undefined}
	onkeydown={onclick ? handleKeydown : undefined}
>
	<!-- Header row: drag handle + code + remove button -->
	<div style="display:flex; justify-content:space-between; align-items:center;">
		<span style="font-size:9px; font-family:var(--g-font-mono); font-weight:600; color:{active ? 'var(--g-accent-deep)' : 'var(--g-ink-4)'}; letter-spacing:0.04em;">
			⋮⋮ {stageLabel} · {stage.code ?? ''}
		</span>
		{#if onRemove}
			<button
				type="button"
				onclick={makeRemoveClick()}
				style="font-size:12px; color:var(--g-ink-4); background:none; border:none; cursor:pointer; padding:0; line-height:1;"
				aria-label="Etappe entfernen"
			>×</button>
		{/if}
	</div>

	{#if isPause}
		<!-- Pause stage content -->
		<div style="font-size:12px; font-weight:600; color:var(--g-ink-2); font-style:italic; margin-top:4px; line-height:1.3;">
			Pausentag
		</div>
		<div style="font-size:9px; font-family:var(--g-font-mono); color:var(--g-ink-3); margin-top:auto;">
			⌂ Pause · {stage.location || '—'}
		</div>
	{:else}
		<!-- Normal stage content -->
		<div style="font-size:12px; font-weight:600; margin-top:4px; line-height:1.3; color:var(--g-ink); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
			{stage.name}
		</div>
		<!-- Inline SVG sparkline -->
		{#if elevData.length >= 2}
			{@const W = 174}
			{@const H = 18}
			{@const min = Math.min(...elevData)}
			{@const max = Math.max(...elevData)}
			{@const range = max - min || 1}
			{@const pts = elevData.map((v, i) => `${((i / (elevData.length - 1)) * W).toFixed(1)},${(H - ((v - min) / range) * (H - 2) - 1).toFixed(1)}`).join(' ')}
			<svg viewBox="0 0 {W} {H}" width="100%" height={H} preserveAspectRatio="none" style="display:block">
				<polyline points={pts} fill="none" stroke={active ? 'var(--g-accent)' : 'var(--g-ink-4)'} stroke-width="1.2"/>
			</svg>
		{/if}
		<!-- Stats row -->
		{#if totalKm !== null || ascent !== null}
			<div style="font-size:9px; font-family:var(--g-font-mono); color:var(--g-ink-3);">
				{#if totalKm !== null}{totalKm.toFixed(1)} km{/if}{#if totalKm !== null && ascent !== null} · {/if}{#if ascent !== null}↑{Math.round(ascent)}{/if}
			</div>
		{/if}
	{/if}
</div>
