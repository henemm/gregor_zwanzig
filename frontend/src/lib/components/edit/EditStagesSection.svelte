<script lang="ts">
	import EditStagesPanelNew from './EditStagesPanelNew.svelte';
	import type { Stage, Trip } from '$lib/types';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';

	interface Props {
		stages?: Stage[];
		tripId: string;
		showSave?: boolean;
		onTripUpdate?: (updated: Trip) => void;
		saveController?: SaveStatus;
	}
	let { stages = $bindable([]), tripId, showSave = true, onTripUpdate, saveController }: Props = $props();
</script>

<EditStagesPanelNew bind:stages {tripId} {showSave} {onTripUpdate} {saveController} />
