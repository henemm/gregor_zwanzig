<script lang="ts">
	// Epic #135 Step 4 (Issue #157) — Stage-Liste fuer Trip-Overview.
	// Spec: docs/specs/modules/epic_135_step4_left_column.md §4.

	import type { Trip } from '$lib/types';
	import StageDetailRow from './StageDetailRow.svelte';
	import { computeStageBoundaries, getActiveStageId } from '$lib/utils/fullProfile';

	interface Props {
		trip: Trip;
		selectedStageId: string | null;
		onSelectStage: (id: string) => void;
		now?: Date;
	}

	let {
		trip,
		selectedStageId,
		onSelectStage,
		now = new Date()
	}: Props = $props();

	const boundaries = $derived(computeStageBoundaries(trip));
	const activeStageId = $derived(getActiveStageId(trip, now));

	// Safari-Closure-Factory: pro stageId einen benannten Handler erzeugen.
	function makeSelectHandler(id: string) {
		return function onSelect() {
			onSelectStage(id);
		};
	}
</script>

<div data-testid="trip-stage-list" class="trip-stage-list">
	{#if !trip.stages || trip.stages.length === 0}
		<p data-testid="trip-stage-empty" class="empty">Keine Etappen geplant</p>
	{:else}
		{#each trip.stages as stage, index (stage.id)}
			{@const boundary = boundaries.find((b) => b.stageId === stage.id)}
			<StageDetailRow
				{stage}
				{index}
				code={boundary?.code ?? ''}
				selected={selectedStageId === stage.id}
				active={activeStageId === stage.id}
				onSelect={makeSelectHandler(stage.id)}
				{now}
			/>
		{/each}
	{/if}
</div>

<style>
	.trip-stage-list {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.empty {
		padding: 1rem;
		color: var(--g-ink-faint, #6b7280);
		font-size: 0.875rem;
	}
</style>
