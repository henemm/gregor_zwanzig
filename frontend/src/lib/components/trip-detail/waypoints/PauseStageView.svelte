<script lang="ts">
	// PauseStageView — Ansicht fuer einen Pausentag in der rechten Spalte.
	// Spec: docs/specs/modules/epic_137_wegpunkt_editor.md §8
	//        + docs/design-requests/stage_date_edit.md (#498)
	//
	// Zeigt: Eyebrow "Pausentag", Stage-Name, editierbares Datum (StageDateField),
	//        Standort aus Vorgaenger-Etappe, Weiter-nach aus Folge-Etappe.

	import { Eyebrow } from '$lib/components/atoms';
	import StageDateField from '$lib/components/edit/StageDateField.svelte';
	import type { Stage } from '$lib/types';

	interface Props {
		stage: Stage;
		prevStage: Stage | null;
		nextStage: Stage | null;
		// Issue #498 — Parent (EditStagesPanelNew) verschiebt das Datum + setzt
		// dateOverridden; lokal nur Hochbubble, kein Direkt-Mutation.
		onDateChange?: (newDate: string) => void;
	}

	let { stage, prevStage, nextStage, onDateChange }: Props = $props();

	const prevLocation = $derived(prevStage?.waypoints.at(-1)?.name ?? null);
	const nextLocation = $derived(nextStage?.waypoints[0]?.name ?? null);
</script>

<div data-testid="pause-stage-view" class="flex flex-col gap-3 p-4">
	<div class="flex items-start justify-between gap-8">
		<div class="min-w-0 flex-1">
			<Eyebrow>Pausentag</Eyebrow>
			<p class="truncate text-lg font-medium">{stage.name}</p>
		</div>
		<StageDateField value={stage.date} onchange={(newDate) => onDateChange?.(newDate)} />
	</div>

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
