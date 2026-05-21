<script lang="ts">
	import StagePill from './StagePill.svelte';
	import type { Stage } from '$lib/types.js';

	interface Props {
		stages: Stage[];
		activeStageid?: string | null;
	}

	let { stages, activeStageid = null }: Props = $props();

	const today = new Date().toISOString().slice(0, 10);
</script>

<div class="strip-wrap">
	<div data-testid="stage-strip" class="flex gap-2 overflow-x-auto pb-2 scroll-smooth">
		{#each stages as stage (stage.id || stage.date || stage.name)}
			<StagePill
				{stage}
				active={(!!activeStageid && stage.id === activeStageid) || stage.date === today}
				muted={!!stage.date && stage.date < today}
			/>
		{/each}
	</div>
	<div class="strip-fade-right" aria-hidden="true"></div>
</div>

<style>
	.strip-wrap {
		position: relative;
	}
	.strip-fade-right {
		position: absolute;
		top: 0;
		right: 0;
		bottom: 0;
		width: 32px;
		background: linear-gradient(to right, transparent, var(--g-paper));
		pointer-events: none;
	}
</style>
