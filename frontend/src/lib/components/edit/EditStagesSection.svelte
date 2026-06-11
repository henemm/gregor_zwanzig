<script lang="ts">
	import EditStagesPanelNew from './EditStagesPanelNew.svelte';
	import type { Stage, Trip } from '$lib/types';

	interface Props {
		stages?: Stage[];
		tripId: string;
		showSave?: boolean;
		onTripUpdate?: (updated: Trip) => void;
	}
	let { stages = $bindable([]), tripId, showSave = true, onTripUpdate }: Props = $props();
</script>

<EditStagesPanelNew bind:stages {tripId} {showSave} {onTripUpdate} />
