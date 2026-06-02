<script lang="ts">
	// StageSelectSheet — Bottom-Sheet (snap: half) zur Etappen-Auswahl auf Mobile.
	// Spec: docs/specs/modules/wegpunkt_editor_handoff.md (AC-4)
	//
	// Oeffnet sich beim Klick auf die EtappenSwitcher-Pill. Zeigt scrollbare
	// Etappen-Liste. Klick auf eine Etappe ruft onSelect(index) auf und schliesst
	// das Sheet (via onClose, das der Parent steuert).

	import Sheet from '$lib/components/mobile/Sheet.svelte';
	import type { Stage } from '$lib/types';

	interface Props {
		stages: Stage[];
		activeIndex: number;
		open?: boolean;
		onClose?: () => void;
		onSelect?: (index: number) => void;
	}

	let {
		stages,
		activeIndex,
		open = false,
		onClose = undefined,
		onSelect = undefined
	}: Props = $props();

	function makeSelectHandler(index: number) {
		return function handleSelect() {
			onSelect?.(index);
			onClose?.();
		};
	}

	function isPause(s: Stage): boolean {
		return s.waypoints.length === 0;
	}
</script>

<Sheet {open} {onClose} snap="half" title="Etappe wählen" eyebrow="Touren-Navigation">
	<ul class="stage-list" data-testid="stage-select-list">
		{#each stages as stage, i (stage.id)}
			{@const active = i === activeIndex}
			{@const pause = isPause(stage)}
			<li>
				<button
					type="button"
					class="stage-item"
					class:active
					class:pause
					data-testid="stage-select-item-{i}"
					onclick={makeSelectHandler(i)}
				>
					<span class="stage-index">{i + 1}</span>
					<span class="stage-meta">
						<span class="stage-name">{stage.name}</span>
						<span class="stage-info">
							{#if stage.date}{stage.date} · {/if}
							{pause ? 'Pausentag' : `${stage.waypoints.length} Wegpunkte`}
						</span>
					</span>
				</button>
			</li>
		{/each}
	</ul>
</Sheet>

<style>
	.stage-list {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.stage-item {
		display: flex;
		align-items: center;
		gap: 12px;
		width: 100%;
		padding: 12px 14px;
		background: var(--g-card);
		border: 1px solid var(--g-rule);
		border-radius: 8px;
		text-align: left;
		cursor: pointer;
		min-height: 44px;
		color: var(--g-ink);
	}
	.stage-item.active {
		border-color: var(--g-accent, var(--g-ink));
		background: var(--g-accent-tint, var(--g-card));
	}
	.stage-item.pause {
		opacity: 0.75;
	}
	.stage-index {
		font-family: var(--g-font-mono);
		font-size: 12px;
		color: var(--g-ink-muted);
		min-width: 20px;
	}
	.stage-meta {
		display: flex;
		flex-direction: column;
		gap: 2px;
		flex: 1;
		min-width: 0;
	}
	.stage-name {
		font-size: 15px;
		font-weight: 600;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.stage-info {
		font-size: 12px;
		color: var(--g-ink-muted);
	}
</style>
