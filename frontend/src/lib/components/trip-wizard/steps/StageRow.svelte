<script lang="ts">
	// StageRow — eine Zeile in der Etappen-Liste (Sub-Spec #162 §5).
	//
	// Props:
	//   stage          — Stage-Objekt (kann Pause sein)
	//   index          — Position in der Liste (0-basiert) — fuer TestIDs
	//   nonPauseIndex  — Position unter den Nicht-Pause-Stages (fuer T01-Pill);
	//                    -1 wenn Stage eine Pause ist
	//   onDateChange   — (id, newDate) => void
	//   onDelete       — (id) => void
	//
	// Render-Konvention:
	//   - Pause: Pause-Marker statt T-Pill, Datum-Input weiterhin sichtbar
	//   - Echte Etappe: T-Pill mit formatStageNumber(nonPauseIndex)
	//
	// A11y:
	//   - Drag-Handle: aria-label="Etappe verschieben", cursor: grab
	//   - Delete-Btn:  aria-label="Etappe entfernen"
	//
	// Factory-Pattern (CLAUDE.md Safari): benannte Handler.

	import GripVertical from '@lucide/svelte/icons/grip-vertical';
	import Trash2Icon from '@lucide/svelte/icons/trash-2';
	import { Pill } from '$lib/components/ui/pill';
	import type { Stage } from '$lib/types';
	import { formatStageNumber, isPauseStage } from '../wizardHelpers.ts';

	interface Props {
		stage: Stage;
		index: number;
		nonPauseIndex: number;
		onDateChange: (id: string, newDate: string) => void;
		onDelete: (id: string) => void;
	}

	let { stage, index, nonPauseIndex, onDateChange, onDelete }: Props = $props();

	const isPause = $derived(isPauseStage(stage));

	function makeDateChangeHandler(id: string) {
		return function handleDateChange(e: Event) {
			const target = e.currentTarget as HTMLInputElement;
			onDateChange(id, target.value);
		};
	}

	function makeDeleteHandler(id: string) {
		return function handleDelete() {
			onDelete(id);
		};
	}
</script>

<div
	data-testid="trip-wizard-step2-stage-row-{index}"
	class="flex items-center gap-2 border border-[var(--g-ink-faint)]/30 rounded-md px-3 py-2 bg-white/40"
>
	<span
		data-testid="trip-wizard-step2-drag-handle-{index}"
		class="text-[var(--g-ink-muted)] cursor-grab focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--g-accent)]"
		aria-label="Etappe verschieben"
		role="button"
		tabindex="0"
	>
		<GripVertical class="size-4" />
	</span>

	{#if isPause}
		<span
			data-testid="trip-wizard-step2-pause-marker-{index}"
			class="text-xs uppercase tracking-wide text-[var(--g-ink-muted)]"
		>
			Pause
		</span>
	{:else}
		<span data-testid="trip-wizard-step2-stage-pill-{index}">
			<Pill tone="info">{formatStageNumber(nonPauseIndex)}</Pill>
		</span>
	{/if}

	{#if !isPause && stage.waypoints.length > 0}
		<Pill tone="ghost" data-testid="trip-wizard-step2-stage-wp-count-{index}">
			{stage.waypoints.length} WP
		</Pill>
	{/if}

	<input
		type="date"
		data-testid="trip-wizard-step2-stage-date-{index}"
		value={stage.date}
		oninput={makeDateChangeHandler(stage.id)}
		class="h-8 rounded border border-[var(--g-ink-faint)]/40 bg-transparent px-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)]"
	/>

	<span class="flex-1 text-sm truncate">
		{isPause ? 'Pausentag' : stage.name}
	</span>

	<button
		type="button"
		data-testid="trip-wizard-step2-stage-delete-{index}"
		onclick={makeDeleteHandler(stage.id)}
		aria-label="Etappe entfernen"
		class="rounded p-1 text-[var(--g-ink-muted)] hover:bg-[var(--g-ink-faint)]/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--g-accent)]"
	>
		<Trash2Icon class="size-4" />
	</button>
</div>
