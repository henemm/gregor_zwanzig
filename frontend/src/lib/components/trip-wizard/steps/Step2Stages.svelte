<script lang="ts">
	// Step 2: Drag-Sort + Pause (Epic #136 Sub-Spec #162; Issue #300 Redesign).
	// Quelle: docs/specs/modules/issue_300_wizard_redesign.md
	//
	// Layout (#300 §"Step 2 — Etappen"):
	//   - Header: "N ETAPPEN ERKANNT AUS N GPX" (Badge-Stil)
	//   - Etappen-Liste (DnD-sortierbar) mit Pause-Inserter zwischen Rows
	//   - TemplatePicker (rechte Spalte, unverändert)
	//
	// AC-3 #300: Der GPX-Upload (Drop-Zone + Pending-Region) wurde nach Step 1
	// (Route) verschoben — hier gibt es keinen Upload-Bereich mehr.
	//
	// Logik:
	//   - DnD via svelte-dnd-action; nach finalize: wizard.recomputeStageDates()
	//   - Pause-Inserter: wizard.addPauseStageAt(afterIndex)
	//   - Auto-Datierung in WizardState; manueller Override setzt dateOverridden=true
	//
	// Safari/Factory: benannte Handler statt anonymer Closures (Spec §6, §7).

	import { getContext } from 'svelte';
	import PlusIcon from '@lucide/svelte/icons/plus';
	import { Btn } from '$lib/components/atoms';
	import { dndzone, type DndEvent } from 'svelte-dnd-action';
	import { flip } from 'svelte/animate';
	import type { Stage } from '$lib/types';
	import type { WizardState } from '../wizardState.svelte';
	import { isPauseStage } from '../wizardHelpers.ts';
	import StageRow from './StageRow.svelte';
	import TemplatePicker from '../templates/TemplatePicker.svelte';

	const wizard = getContext<WizardState>('trip-wizard-state');

	// --- Derivations --------------------------------------------------------

	// nonPauseIndex pro Stage berechnen (Spec §5): Position unter den
	// nicht-Pause-Stages — Pausen geben -1 zurueck.
	function computeNonPauseIndices(stages: Stage[]): number[] {
		let counter = 0;
		return stages.map((s) => (isPauseStage(s) ? -1 : counter++));
	}

	const nonPauseIndices = $derived(computeNonPauseIndices(wizard.stages));

	// AC-4 #300: Anzahl erkannter Etappen. Jede GPX = 1 Etappe, daher ist die
	// GPX-Anzahl identisch zur Nicht-Pause-Etappen-Anzahl.
	function countNonPauseStages(stages: Stage[]): number {
		return stages.filter((s) => !isPauseStage(s)).length;
	}

	const stageCount = $derived(countNonPauseStages(wizard.stages));

	// --- DnD-Handler --------------------------------------------------------

	function handleDndConsider(e: CustomEvent<DndEvent<Stage>>) {
		wizard.stages = e.detail.items;
	}

	function handleDndFinalize(e: CustomEvent<DndEvent<Stage>>) {
		wizard.stages = e.detail.items;
		wizard.recomputeStageDates();
	}

	// --- Stage-Row-Handler --------------------------------------------------

	function handleStageDateChange(id: string, newDate: string) {
		const idx = wizard.stages.findIndex((s) => s.id === id);
		if (idx < 0) return;
		const next = wizard.stages.slice();
		next[idx] = { ...next[idx], date: newDate, dateOverridden: true };
		wizard.stages = next;
	}

	function handleStageDelete(id: string) {
		wizard.deleteStage(id);
	}

	// --- Pause-Inserter -----------------------------------------------------

	function makePauseInsertHandler(afterIndex: number) {
		return function handlePauseInsert() {
			wizard.addPauseStageAt(afterIndex);
		};
	}

	// --- Platzhalter-Handler (Issue #391; Funktion folgt separat) -----------
	function handleMerge() {}
	function handleInsert() {}
</script>

<div
	data-testid="trip-wizard-step2-layout"
	class="grid gap-6 py-4 step2-grid"
>
	<div data-testid="trip-wizard-step2-stages" class="flex flex-col gap-6">
	<!-- Header: "N ETAPPEN ERKANNT AUS N GPX" (AC-4 #300) -->
	{#if wizard.stages.length > 0}
		<div class="flex flex-wrap items-center gap-2" data-testid="trip-wizard-step2-header">
			<span
				class="text-xs font-semibold uppercase tracking-widest text-[var(--g-ink-muted)]"
			>
				{stageCount} ETAPPEN ERKANNT AUS {stageCount} GPX
			</span>
			<div class="ml-auto flex items-center gap-2">
				<Btn variant="ghost" size="sm" onclick={handleMerge} data-testid="trip-wizard-step2-btn-merge">
					Zusammenführen
				</Btn>
				<Btn variant="ghost" size="sm" onclick={handleInsert} data-testid="trip-wizard-step2-btn-insert">
					+ Etappe einschieben
				</Btn>
			</div>
		</div>
	{/if}

	<!-- Etappen-Liste mit DnD + Pause-Inserter -->
	{#if wizard.stages.length > 0}
		<div
			data-testid="trip-wizard-step2-stage-list"
			class="flex flex-col gap-1"
			use:dndzone={{ items: wizard.stages, flipDurationMs: 200, dropTargetStyle: {} }}
			onconsider={handleDndConsider}
			onfinalize={handleDndFinalize}
		>
			{#each wizard.stages as stage, i (stage.id)}
				<div animate:flip={{ duration: 200 }} class="flex flex-col">
					<div class="flex items-center gap-2">
						<div class="flex-1">
							<StageRow
								{stage}
								index={i}
								nonPauseIndex={nonPauseIndices[i]}
								onDateChange={handleStageDateChange}
								onDelete={handleStageDelete}
							/>
						</div>
					</div>
					<div class="flex justify-center py-1">
						<button
							type="button"
							data-testid="trip-wizard-step2-pause-after-{i}"
							onclick={makePauseInsertHandler(i)}
							class="opacity-0 hover:opacity-100 focus-visible:opacity-100 transition-opacity inline-flex items-center gap-1 rounded-full border border-[var(--g-ink-faint)]/30 bg-white/60 px-2 py-0.5 text-xs text-[var(--g-ink-muted)]"
							aria-label="Pausentag nach dieser Etappe einfügen"
						>
							<PlusIcon class="size-3" />
							Pause
						</button>
					</div>
				</div>
			{/each}
		</div>
	{/if}
	</div>

	<!-- Rechte Spalte: Vorlagen-Picker (Sub-Spec #165) -->
	<div>
		<TemplatePicker />
	</div>
</div>

<style>
	.step2-grid {
		grid-template-columns: 2fr minmax(0, 220px);
	}
	@media (max-width: 640px) {
		.step2-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
