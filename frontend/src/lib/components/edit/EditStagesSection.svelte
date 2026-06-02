<script lang="ts">
	import EditStagesPanelNew from './EditStagesPanelNew.svelte';
	import type { Stage } from '$lib/types';

	interface Props {
		stages?: Stage[];
		tripId: string;
		showSave?: boolean;
	}
	let { stages = $bindable([]), tripId, showSave = true }: Props = $props();
</script>

<EditStagesPanelNew bind:stages {tripId} {showSave} />
