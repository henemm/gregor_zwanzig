<script lang="ts">
	import WeatherSummaryCard from './WeatherSummaryCard.svelte';
	import type { Trip } from '$lib/types';

	interface Props {
		trip: Trip;
	}
	let { trip }: Props = $props();
</script>

<WeatherSummaryCard displayConfig={trip.display_config} tripId={trip.id} />
