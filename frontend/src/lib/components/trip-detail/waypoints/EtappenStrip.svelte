<script lang="ts">
	// EtappenStrip — horizontaler Strip mit sortierbaren Etappen und Pause-Inserter.
	// Issue #585: Design-Fidelity 1:1 nach screen-waypoint-editor.jsx
	// Eyebrow-Header + GPX/Pause-Zähler + PauseInsertGap + "+ Etappe"-Button
	// Issue #2288 / ADR-0024: Sortieren über den geteilten Baustein SortableList.
	// dndzone entfernt Nicht-Item-Kinder: die "+ Pause"-Lücke liegt deshalb im
	// Item-Snippet, "+ Etappe" als Geschwister der Zone.

	import StageCard from './StageCard.svelte';
	import SortableList from '$lib/components/shared/dnd/SortableList.svelte';
	import DragHandle from '$lib/components/shared/dnd/DragHandle.svelte';
	import { isPauseStage } from '$lib/components/shared/wizardHelpers';
	import type { Stage } from '$lib/types';

	interface Props {
		stages: Stage[];
		activeStageId: string;
		onStagesReorder: (stages: Stage[]) => void;
		/** Bug #1393 R2-F002: feuert einmal direkt nach `onStagesReorder`, beim
		 *  Ablegen. Wer auf die FERTIGE Reihenfolge reagieren muss, hängt sich hier
		 *  ein. Optional; bestehende Aufrufer bleiben unberührt. */
		onReorderEnd?: () => void;
		/** Bug #1393 R5-F001: solange eine Antwort auf die Kaskaden-Rückfrage
		 *  geschrieben wird, sind BAULICHE Änderungen (Umsortieren, Löschen,
		 *  Hinzufügen) gesperrt — sonst zerfällt der gerade abgeschickte Stand
		 *  gegen die Liste, die der Nutzer inzwischen vor sich hat. Sichtbar
		 *  gesperrt, nicht stillschweigend verschluckt. */
		locked?: boolean;
		onStageActivate: (stageId: string) => void;
		onPauseInsert?: (afterIndex: number) => void;
		onRemoveStage?: (stageId: string) => void;
		onAddStage?: () => void;
	}

	let { stages, activeStageId, onStagesReorder, onReorderEnd, locked = false, onStageActivate, onPauseInsert, onRemoveStage, onAddStage }: Props = $props();

	let hoverGap = $state<number | null>(null);

	const gpxCount = $derived(stages.filter(s => !isPauseStage(s)).length);
	const pauseCount = $derived(stages.filter(s => isPauseStage(s)).length);

	// SortableList meldet ID-Reihenfolgen (nur bei finalize); der Strip arbeitet mit Stage[].
	function handleDndReorder(newOrder: string[]): void {
		const byId = new Map(stages.map((s) => [s.id, s]));
		const reordered = newOrder.map((id) => byId.get(id)).filter((s): s is Stage => !!s);
		if (reordered.length === stages.length) onStagesReorder(reordered);
	}

	function handleDndReorderEnd(): void {
		onReorderEnd?.();
	}

	function stageName(id: string): string {
		return stages.find((s) => s.id === id)?.name ?? id;
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
</script>

{#snippet row(id: string, i: number)}
	{@const stage = stages.find((s) => s.id === id)}
	{#if stage}
		<div style="display:flex; flex-direction:row; align-items:stretch;">
			<DragHandle />
			<StageCard
				{stage}
				index={i}
				active={stage.id === activeStageId}
				onclick={makeStageActivateHandler(stage.id)}
				onRemove={onRemoveStage ? makeRemoveHandler(stage.id) : undefined}
			/>

			<!-- PauseInsertGap hinter der Karte, Teil des Items (wandert beim Sortieren mit) -->
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
		</div>
	{/if}
{/snippet}

<div
	data-testid="etappen-strip-wrapper"
	data-locked={locked ? 'true' : undefined}
	aria-busy={locked}
	style="{locked ? 'opacity:0.5; pointer-events:none; ' : ''}padding: 14px 40px 16px; border-bottom: 1px solid var(--g-rule-soft); background: rgba(255,255,255,0.4); backdrop-filter: blur(2px); -webkit-backdrop-filter: blur(2px);"
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

	<!-- Strip: Sortier-Zone + "+ Etappe" als Geschwister in einer Flex-Zeile -->
	<div
		data-testid="etappen-strip"
		style="display:flex; flex-direction:row; align-items:stretch; overflow-x:auto; padding-bottom:4px;"
	>
		<!-- Zone + "+ Etappe" teilen sich eine Flex-Zeile. Die Zone hat rechts Polster
		     (.strip-zone-wrap), unter dem der Knopf liegt: ein Ablegen am rechten
		     Strip-Rand bleibt damit INNERHALB der Zone (sonst wertet svelte-dnd-action
		     es als Ablegen ausserhalb und verwirft die Geste). -->
		<div class="strip-zone-wrap">
			<!-- flipDurationMs=0: svelte-dnd-action tastet die Zeigerposition im Takt von
			     flipDurationMs*1,07 ab (214 ms bei 200). Bei einer schnellen Geste ueber
			     mehrere Karten wuerden Stationen uebersprungen und die Karte landet am
			     falschen Platz (#2288, AC-4/AC-31). -->
			<SortableList
				direction="horizontal"
				flipDurationMs={0}
				items={stages.map((s) => s.id)}
				onDndReorder={handleDndReorder}
				onDndReorderEnd={handleDndReorderEnd}
				ariaLabel="Etappen sortieren"
				itemLabel={stageName}
				{row}
			/>

			{#if onAddStage}
				<button
					type="button"
					onclick={onAddStage}
					class="add-stage-btn"
					style="position:absolute; right:0; top:0; bottom:0; padding:0 16px; border:1px dashed var(--g-rule); background:transparent; color:var(--g-ink-3); font-size:11px; font-family:var(--g-font-mono); letter-spacing:0.06em; text-transform:uppercase; cursor:pointer; border-radius:4px; min-height:88px;"
				>
					+ Etappe
				</button>
			{/if}
		</div>
	</div>
</div>

<style>
	.strip-zone-wrap {
		position: relative;
		flex-shrink: 0;
		display: flex;
	}
	.strip-zone-wrap :global(.sortable-zone) {
		padding-right: 128px;
	}
	.add-stage-btn:hover {
		border-color: var(--g-accent) !important;
		color: var(--g-accent) !important;
	}
</style>
