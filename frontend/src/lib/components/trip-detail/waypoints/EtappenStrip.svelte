<script lang="ts">
	// EtappenStrip — horizontaler Strip mit DnD-Etappen und Pause-Inserter.
	// Spec: docs/specs/modules/epic_137_wegpunkt_editor.md §4

	import { dndzone, type DndEvent } from 'svelte-dnd-action';
	import { flip } from 'svelte/animate';
	import StageCard from './StageCard.svelte';
	import { isPauseStage } from '$lib/components/trip-wizard/wizardHelpers';
	import type { Stage } from '$lib/types';

	interface Props {
		stages: Stage[];
		activeStageId: string;
		onStagesReorder: (stages: Stage[]) => void;
		onStageActivate: (stageId: string) => void;
		onPauseInsert?: (afterIndex: number) => void;
	}

	let { stages, activeStageId, onStagesReorder, onStageActivate, onPauseInsert }: Props = $props();

	function handleDndConsider(e: CustomEvent<DndEvent<Stage>>): void {
		stages = e.detail.items;
	}

	function handleDndFinalize(e: CustomEvent<DndEvent<Stage>>): void {
		stages = e.detail.items;
		onStagesReorder(stages);
	}

	function makeStageActivateHandler(id: string) {
		return function handleStageActivate() {
			onStageActivate(id);
		};
	}

	function makePauseInsertHandler(afterIndex: number) {
		return function handlePauseInsert() {
			onPauseInsert?.(afterIndex);
		};
	}
</script>

<div
	data-testid="etappen-strip"
	class="etappen-strip flex flex-row gap-2 overflow-x-auto pb-2"
	use:dndzone={{ items: stages, flipDurationMs: 150, dropTargetStyle: {}, type: 'horizontal' }}
	onconsider={handleDndConsider}
	onfinalize={handleDndFinalize}
>
	{#each stages as stage, i (stage.id)}
		<div animate:flip={{ duration: 150 }} class="flex flex-col items-center">
			<StageCard
				{stage}
				index={i}
				active={stage.id === activeStageId}
				onclick={makeStageActivateHandler(stage.id)}
			/>
			{#if i < stages.length - 1 && onPauseInsert}
				<button
					type="button"
					data-testid="etappen-strip-pause-after-{i}"
					onclick={makePauseInsertHandler(i)}
					class="opacity-0 hover:opacity-100 focus-visible:opacity-100 transition-opacity text-xs text-[var(--g-ink-muted)] px-2 py-0.5"
					aria-label="Pausentag nach Etappe {i + 1} einfügen"
				>+ Pause</button>
			{/if}
		</div>
	{/each}
</div>

<style>
	/* AC-8: semi-transparent weisser Hintergrund + Blur — Strip schwebt ueber dem Editor.
	   Das Wrapper-Element in WaypointEditorPage rendert den Eyebrow + Zaehler darum herum. */
	.etappen-strip {
		background: rgba(255, 255, 255, 0.4);
		backdrop-filter: blur(2px);
		-webkit-backdrop-filter: blur(2px);
	}
</style>
