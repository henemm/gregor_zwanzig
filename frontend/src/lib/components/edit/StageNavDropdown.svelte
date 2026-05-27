<script lang="ts">
	// StageNavDropdown — Mobile Etappen-Navigator fuer den Wegpunkt-Editor (Issue #407).
	// Spec: docs/specs/modules/issue_407_waypoint_editor_screen.md §2
	//
	// Zeigt die aktive Etappe als <Select>-Dropdown flankiert von Prev/Next-Pfeil-Buttons.
	// Prev/Next disabled an den Listen-Grenzen.

	import { Btn } from '$lib/components/ui/btn';
	import { Select } from '$lib/components/ui/select';
	import ChevronLeftIcon from '@lucide/svelte/icons/chevron-left';
	import ChevronRightIcon from '@lucide/svelte/icons/chevron-right';
	import type { Stage } from '$lib/types';

	interface Props {
		stages: Stage[];
		activeStageId: string;
		prev: Stage | null;
		next: Stage | null;
		onActivate: (id: string) => void;
	}
	let { stages, activeStageId, prev, next, onActivate }: Props = $props();

	function handleSelectChange(e: Event): void {
		const target = e.currentTarget as HTMLSelectElement;
		onActivate(target.value);
	}

	// Factory-Pattern (Safari-Closure-Schutz).
	function makeNavHandler(stage: Stage | null) {
		return function handleNav() {
			if (stage) onActivate(stage.id);
		};
	}
</script>

<div data-testid="stage-nav-dropdown" class="stage-nav">
	<Btn
		variant="outline"
		size="icon-sm"
		data-testid="stage-nav-prev-btn"
		disabled={prev === null}
		onclick={makeNavHandler(prev)}
		aria-label="Vorherige Etappe"
	>
		<ChevronLeftIcon class="size-4" />
	</Btn>

	<span class="stage-nav__select">
		<Select value={activeStageId} onchange={handleSelectChange} aria-label="Etappe wählen">
			{#each stages as stage, i (stage.id)}
				<option value={stage.id}>{i + 1}. {stage.name}</option>
			{/each}
		</Select>
	</span>

	<Btn
		variant="outline"
		size="icon-sm"
		data-testid="stage-nav-next-btn"
		disabled={next === null}
		onclick={makeNavHandler(next)}
		aria-label="Nächste Etappe"
	>
		<ChevronRightIcon class="size-4" />
	</Btn>
</div>

<style>
	.stage-nav {
		display: flex;
		align-items: center;
		gap: var(--g-s-2);
		padding: var(--g-s-2) var(--g-s-3);
	}
	.stage-nav__select {
		flex: 1;
		min-width: 0;
	}
	.stage-nav__select :global(.gz-select) {
		display: block;
		width: 100%;
	}
</style>
