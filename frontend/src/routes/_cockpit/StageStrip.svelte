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

<div data-testid="stage-strip" class="flex gap-2 overflow-x-auto pb-2">
	{#each stages as stage (stage.id || stage.date || stage.name)}
		<StagePill
			{stage}
			active={(!!activeStageid && stage.id === activeStageid) || stage.date === today}
			muted={!!stage.date && stage.date < today}
		/>
	{/each}
</div>
