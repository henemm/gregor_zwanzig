<script lang="ts">
	// PauseStageView — Ansicht fuer einen Pausentag in der rechten Spalte.
	// Spec: docs/specs/modules/epic_137_wegpunkt_editor.md §8
	//
	// Zeigt: Eyebrow "Pausentag", Stage-Name, Datum,
	//        Standort aus Vorgaenger-Etappe, Weiter-nach aus Folge-Etappe.

	import { Eyebrow } from '$lib/components/atoms';
	import type { Stage } from '$lib/types';

	interface Props {
		stage: Stage;
		prevStage: Stage | null;
		nextStage: Stage | null;
	}

	let { stage, prevStage, nextStage }: Props = $props();

	const prevLocation = $derived(prevStage?.waypoints.at(-1)?.name ?? null);
	const nextLocation = $derived(nextStage?.waypoints[0]?.name ?? null);
</script>

<div data-testid="pause-stage-view" class="flex flex-col gap-3 p-4">
	<Eyebrow>Pausentag</Eyebrow>

	<p class="text-lg font-medium">{stage.name}</p>

	<p class="text-sm text-[var(--g-ink-muted)]">{stage.date}</p>

	{#if prevLocation || nextLocation}
		<div class="flex flex-col gap-1 text-sm">
			{#if prevLocation}
				<span>Standort: {prevLocation}</span>
			{/if}
			{#if nextLocation}
				<span>Weiter nach: {nextLocation}</span>
			{/if}
		</div>
	{:else}
		<p class="text-sm text-[var(--g-ink-muted)]">Kein Standort hinterlegt</p>
	{/if}
</div>
