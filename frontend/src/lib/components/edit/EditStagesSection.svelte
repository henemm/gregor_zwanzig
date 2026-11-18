<script lang="ts">
	import EditStagesPanelNew from './EditStagesPanelNew.svelte';
	import type { Stage, Trip, ActivityType } from '$lib/types';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import type { Snippet } from 'svelte';

	interface Props {
		stages?: Stage[];
		tripId: string;
		showSave?: boolean;
		onTripUpdate?: (updated: Trip) => void;
		saveController?: SaveStatus;
		activityType?: ActivityType;
		/** #3006: Bereichskopf des Reiters, wird an EditStagesPanelNew durchgereicht. */
		kopf?: Snippet;
		/** #3007: Hub-Listenmodus, wird an EditStagesPanelNew durchgereicht (Standard aus). */
		listeZuerst?: boolean;
	}
	let { stages = $bindable([]), tripId, showSave = true, onTripUpdate, saveController, activityType, kopf, listeZuerst = false }: Props = $props();
</script>

<EditStagesPanelNew bind:stages {tripId} {showSave} {onTripUpdate} {saveController} {activityType} {kopf} {listeZuerst} />
