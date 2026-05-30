<script lang="ts">
	// StageCard — kompakte Etappen-Karte für Wegpunkt-Editor Sidebar.
	// Spec: docs/specs/modules/epic_137_wegpunkt_editor.md

	import { ElevSparkline, Pill } from '$lib/components/atoms';
	import { isPauseStage, formatStageNumber } from '$lib/components/trip-wizard/wizardHelpers';
	import type { Stage } from '$lib/types';

	interface Props {
		stage: Stage;
		index: number;
		active?: boolean;
		onclick?: () => void;
	}

	let { stage, index, active = false, onclick }: Props = $props();

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

	const descent = $derived(
		(() => {
			if (!stage.waypoints || stage.waypoints.length < 2) return null;
			let down = 0;
			for (let i = 1; i < stage.waypoints.length; i++) {
				const diff = (stage.waypoints[i].elevation_m ?? 0) - (stage.waypoints[i - 1].elevation_m ?? 0);
				if (diff < 0) down += Math.abs(diff);
			}
			return down > 0 ? down : null;
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
</script>

{#if isPause}
	<!-- Pause Stage -->
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<div
		data-testid="stage-card-pause-{index}"
		class="stage-card stage-card--pause"
		class:stage-card--active={active}
		role={onclick ? 'button' : undefined}
		tabindex={onclick ? 0 : undefined}
		onclick={onclick ? handleClick : undefined}
		onkeydown={onclick ? handleKeydown : undefined}
	>
		<span class="pause-label">Pausentag</span>
	</div>
{:else}
	<!-- Normal Stage -->
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<div
		data-testid="stage-card-{index}"
		class="stage-card"
		class:stage-card--active={active}
		role={onclick ? 'button' : undefined}
		tabindex={onclick ? 0 : undefined}
		onclick={onclick ? handleClick : undefined}
		onkeydown={onclick ? handleKeydown : undefined}
	>
		<div class="stage-card__header">
			<Pill tone="default">{stageLabel}</Pill>
		</div>
		{#if elevData.length > 0}
			<div class="stage-card__sparkline">
				<ElevSparkline data={elevData} width={120} height={32} />
			</div>
		{/if}
		<div class="stage-card__name">{stage.name}</div>
		{#if totalKm !== null || ascent !== null || descent !== null}
			<div class="stage-card__meta">
				{#if totalKm !== null}<span>{totalKm.toFixed(1)} km</span>{/if}
				{#if ascent !== null}<span>+{Math.round(ascent)} m</span>{/if}
				{#if descent !== null}<span>-{Math.round(descent)} m</span>{/if}
			</div>
		{/if}
	</div>
{/if}

<style>
	.stage-card {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-1);
		width: 160px;
		min-height: 100px;
		padding: var(--g-s-2);
		background: var(--g-paper);
		border: 1px solid var(--g-ink-faint);
		border-radius: var(--g-radius-md);
		cursor: default;
	}

	.stage-card--active {
		outline: 2px solid var(--g-accent);
		outline-offset: 1px;
	}

	.stage-card--pause {
		border-style: dashed;
		border-color: var(--g-ink-faint);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.pause-label {
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		text-align: center;
	}

	.stage-card__header {
		display: flex;
		align-items: center;
	}

	.stage-card__sparkline {
		color: var(--g-ink-muted);
	}

	.stage-card__name {
		font-size: var(--g-text-sm);
		color: var(--g-ink);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.stage-card__meta {
		display: flex;
		gap: var(--g-s-2);
		font-size: var(--g-text-xs);
		color: var(--g-ink-muted);
	}
</style>
