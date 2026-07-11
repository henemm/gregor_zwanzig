<script lang="ts">
	// EtappenStrip — horizontaler Strip mit HTML5-Drag-Etappen und Pause-Inserter.
	// Issue #585: Design-Fidelity 1:1 nach screen-waypoint-editor.jsx
	// Eyebrow-Header + GPX/Pause-Zähler + PauseInsertGap + "+ Etappe"-Button
	// HTML5 Drag API statt svelte-dnd-action — damit PauseInsertGap und "+ Etappe"
	// im normalen DOM-Flow bleiben (svelte-dnd-action entfernt Nicht-Item-Kinder).

	import StageCard from './StageCard.svelte';
	import { isPauseStage } from '$lib/components/shared/wizardHelpers';
	import type { Stage } from '$lib/types';

	interface Props {
		stages: Stage[];
		activeStageId: string;
		onStagesReorder: (stages: Stage[]) => void;
		onStageActivate: (stageId: string) => void;
		onPauseInsert?: (afterIndex: number) => void;
		onRemoveStage?: (stageId: string) => void;
		onAddStage?: () => void;
	}

	let { stages, activeStageId, onStagesReorder, onStageActivate, onPauseInsert, onRemoveStage, onAddStage }: Props = $props();

	let drag = $state<string | null>(null);
	let hoverGap = $state<number | null>(null);

	const gpxCount = $derived(stages.filter(s => !isPauseStage(s)).length);
	const pauseCount = $derived(stages.filter(s => isPauseStage(s)).length);

	function reorder(fromId: string, toId: string): void {
		if (fromId === toId) return;
		const next = [...stages];
		const fromI = next.findIndex(s => s.id === fromId);
		const toI = next.findIndex(s => s.id === toId);
		const [moved] = next.splice(fromI, 1);
		next.splice(toI, 0, moved);
		onStagesReorder(next);
	}

	function makeStageActivateHandler(id: string) {
		return function handleStageActivate() { onStageActivate(id); };
	}

	function makeRemoveHandler(id: string) {
		return function handleRemove() { onRemoveStage?.(id); };
	}

	function makePauseInsertHandler(i: number) {
		return function handlePauseInsert() { onPauseInsert?.(i); hoverGap = null; };
	}

	function makeDragStartHandler(id: string) {
		return function handleDragStart() { drag = id; };
	}

	function makeDragOverHandler(id: string) {
		return function handleDragOver(e: DragEvent) {
			e.preventDefault();
			if (drag && drag !== id) reorder(drag, id);
		};
	}
</script>

<div
	data-testid="etappen-strip-wrapper"
	style="padding: 14px 40px 16px; border-bottom: 1px solid var(--g-rule-soft); background: rgba(255,255,255,0.4); backdrop-filter: blur(2px); -webkit-backdrop-filter: blur(2px);"
>
	<!-- Eyebrow-Header mit Zähler -->
	<div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:10px;">
		<span style="font-size:10px; font-family:var(--g-font-mono); font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:var(--g-ink-4);">
			ETAPPEN · DRAG ZUM SORTIEREN · + PAUSE ZWISCHEN
		</span>
		<span style="font-size:10px; font-family:var(--g-font-mono); color:var(--g-ink-4); letter-spacing:0.06em;">
			{gpxCount} GPX · {pauseCount} Pause
		</span>
	</div>

	<!-- Strip mit HTML5 Drag — PauseInsertGap und "+ Etappe"-Button bleiben im DOM -->
	<div
		data-testid="etappen-strip"
		style="display:flex; flex-direction:row; align-items:stretch; overflow-x:auto; padding-bottom:4px;"
	>
		{#each stages as stage, i (stage.id)}
			<!-- Draggable wrapper für jede Etappe -->
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div
				draggable={true}
				style="flex-shrink:0; display:flex; flex-direction:row; align-items:stretch;"
				ondragstart={makeDragStartHandler(stage.id)}
				ondragover={makeDragOverHandler(stage.id)}
				ondragend={() => { drag = null; }}
			>
				<StageCard
					{stage}
					index={i}
					active={stage.id === activeStageId}
					onclick={makeStageActivateHandler(stage.id)}
					onRemove={onRemoveStage ? makeRemoveHandler(stage.id) : undefined}
				/>
			</div>

			<!-- PauseInsertGap zwischen je zwei Karten (außerhalb dndzone, bleibt im DOM) -->
			{#if i < stages.length - 1 && onPauseInsert}
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div
					data-testid="etappen-strip-pause-after-{i}"
					style="flex-shrink:0; width:{hoverGap === i ? 56 : 8}px; min-height:88px; display:flex; align-items:center; justify-content:center; cursor:pointer; transition:width 140ms ease;"
					onmouseenter={() => hoverGap = i}
					onmouseleave={() => hoverGap = null}
					onclick={makePauseInsertHandler(i)}
				>
					{#if hoverGap === i}
						<span style="padding:3px 8px; font-size:9px; font-weight:600; background:var(--g-accent); color:#fff; border-radius:10px; letter-spacing:0.06em; text-transform:uppercase; font-family:var(--g-font-mono);">+ Pause</span>
					{:else}
						<span style="width:1px; height:24px; background:var(--g-rule); display:block;"></span>
					{/if}
				</div>
			{/if}
		{/each}

		<!-- "+ Etappe"-Button am Strip-Ende (außerhalb dndzone, bleibt im DOM) -->
		{#if onAddStage}
			<button
				type="button"
				onclick={onAddStage}
				class="add-stage-btn"
				style="flex-shrink:0; padding:0 16px; border:1px dashed var(--g-rule); background:transparent; color:var(--g-ink-3); font-size:11px; font-family:var(--g-font-mono); letter-spacing:0.06em; text-transform:uppercase; cursor:pointer; border-radius:4px; min-height:88px;"
			>
				+ Etappe
			</button>
		{/if}
	</div>
</div>

<style>
	.add-stage-btn:hover {
		border-color: var(--g-accent) !important;
		color: var(--g-accent) !important;
	}
</style>
