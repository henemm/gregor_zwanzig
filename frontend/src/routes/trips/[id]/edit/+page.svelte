<script lang="ts">
	import TripWizard from '$lib/components/wizard/TripWizard.svelte';

	let { data } = $props();
</script>

<TripWizard mode="edit" existingTrip={data.trip} />
