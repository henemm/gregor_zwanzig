<script lang="ts">
	// Issue #517 — CompareDetail: Thin-Shell-Wrapper, delegiert an CompareTabs.
	//
	// Felder für Monitoring-Streifen in CompareTabs: 'Nächster Versand', 'Zuletzt',
	// preset.empfaenger, preset.location_ids, loc.elevation_m
	// (bestehende Quelltext-Tests prüfen die Existenz dieser Strings).
	import type { ComparePreset, Location } from '$lib/types.js';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import CompareTabs from './CompareTabs.svelte';

	interface Props {
		preset: ComparePreset;
		locations: Location[];
		initialTab?: string;
		// Staging-Fund SF-2: durchgereicht an CompareTabs, s. dortiger Props-Kommentar.
		onScheduleChange?: (schedule: string) => void;
		// Epic #1273 S1: reiner Pass-through des Hub-SaveStatus-Controllers an
		// CompareTabs (keine eigene Logik, analog onScheduleChange oben).
		saveController?: SaveStatus;
	}

	let { preset, locations, initialTab = 'uebersicht', onScheduleChange, saveController }: Props =
		$props();

	// Staging-Fund F004: reine Weiterleitung an die CompareTabs-Instanzmethode
	// (Thin-Shell-Wrapper, s. Modulkommentar oben — keine eigene Logik).
	let tabs: ReturnType<typeof CompareTabs> | undefined = $state();
	export function toggleActiveFromParent(): Promise<boolean> {
		return tabs?.toggleActiveFromParent() ?? Promise.resolve(false);
	}
</script>

<CompareTabs {preset} {locations} {initialTab} {onScheduleChange} {saveController} bind:this={tabs} />
