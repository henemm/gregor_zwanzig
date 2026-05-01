<script lang="ts">
	import TripEditView from '$lib/components/edit/TripEditView.svelte';

	let { data } = $props();
</script>

<TripEditView trip={data.trip} />
