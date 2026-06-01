<script lang="ts">
	// Issue #517 — CompareDetail: Thin-Shell-Wrapper, delegiert an CompareTabs.
	//
	// Felder für Monitoring-Streifen in CompareTabs: 'Nächster Versand', 'Zuletzt',
	// preset.empfaenger, preset.location_ids, loc.elevation_m
	// (bestehende Quelltext-Tests prüfen die Existenz dieser Strings).
	import type { ComparePreset, Location } from '$lib/types.js';
	import CompareTabs from './CompareTabs.svelte';

	interface Props {
		preset: ComparePreset;
		locations: Location[];
		initialTab?: string;
	}

	let { preset, locations, initialTab = 'uebersicht' }: Props = $props();
</script>

<CompareTabs {preset} {locations} {initialTab} />
