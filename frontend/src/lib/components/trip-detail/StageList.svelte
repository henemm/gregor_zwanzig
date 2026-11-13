<script lang="ts">
	// Epic #135 Step 4 (Issue #157) — Stage-Liste fuer Trip-Overview.
	// Spec: docs/specs/modules/epic_135_step4_left_column.md §4.

	import type { Trip, StagesWeatherResponse, StageWeatherResult } from '$lib/types';
	import StageDetailRow from './StageDetailRow.svelte';
	import { computeStageBoundaries, getActiveStageId } from '$lib/utils/fullProfile';
	import { t } from '$lib/i18n';

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

	// Issue #203 — Stage-Wetter asynchron nach Trip-Load nachladen.
	let stageWeather: Record<string, StageWeatherResult | null> = $state({});
	// Issue #2961 (ADR-0117): ist das Abruf-Kontingent erschöpft, sagt der
	// Server das in der Kontosprache (200 mit `hinweis` bzw. 429 mit `detail`)
	// — die Etappen bleiben dann nicht kommentarlos ohne Wetter.
	let kontingentHinweis: string | null = $state(null);

	$effect(() => {
		if (!trip?.id) return;
		kontingentHinweis = null;
		fetch(`/api/trips/${trip.id}/stages/weather`)
			.then(async (r) => {
				if (r.ok) return (await r.json()) as StagesWeatherResponse;
				if (r.status === 429) {
					const body = (await r.json().catch(() => null)) as { detail?: string } | null;
					kontingentHinweis = body?.detail ?? null;
				}
				return null;
			})
			.then((data) => {
				if (!data) return;
				stageWeather = data.results;
				kontingentHinweis = data.hinweis ?? null;
			})
			.catch(() => {});
	});

	// Safari-Closure-Factory: pro stageId einen benannten Handler erzeugen.
	function makeSelectHandler(id: string) {
		return function onSelect() {
			onSelectStage(id);
		};
	}
</script>

<div data-testid="trip-stage-list" class="trip-stage-list">
	{#if kontingentHinweis}
		<p data-testid="trip-stage-weather-quota-hint" class="hint" role="status">{kontingentHinweis}</p>
	{/if}
	{#if !trip.stages || trip.stages.length === 0}
		<p data-testid="trip-stage-empty" class="empty">{$t('trip.hub.keine_etappen')}</p>
	{:else}
		{#each trip.stages as stage, index (stage.id || `idx-${index}`)}
			{@const boundary = boundaries.find((b) => b.stageId === stage.id)}
			<StageDetailRow
				{stage}
				{index}
				code={boundary?.code ?? ''}
				selected={selectedStageId === stage.id}
				active={activeStageId === stage.id}
				onSelect={makeSelectHandler(stage.id)}
				weatherData={stageWeather[stage.id] ?? null}
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
	.hint {
		margin: 0;
		padding: 0.5rem 0.75rem;
		border-left: 3px solid var(--g-warn-deep);
		background: var(--g-warn-bg);
		color: var(--g-ink-strong);
		font-size: 0.875rem;
	}
	.empty {
		padding: 1rem;
		color: var(--g-ink-muted);
		font-size: 0.875rem;
	}
</style>
