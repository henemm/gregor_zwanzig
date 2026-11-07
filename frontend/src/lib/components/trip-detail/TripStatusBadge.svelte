<script lang="ts">
	// Spec: docs/specs/modules/epic_135_step2_trip_detail_actions.md (§5)
	// #2837 AC-15 (BROKEN-Fix): dünner Wrapper — Ton, Wort und Pill-Atom trägt der geteilte
	// HubStatusBadge (auch im Ortsvergleich-Kopf). Hier nur: Trip → Status, Trip-testid.
	import HubStatusBadge from '$lib/components/shared/hub-kopf/HubStatusBadge.svelte';
	import { deriveTripStatus } from '$lib/utils/tripStatus';
	import type { Trip } from '$lib/types';

	interface Props {
		trip: Trip;
		now?: Date;
	}

	let { trip, now = new Date() }: Props = $props();

	const status = $derived(deriveTripStatus(trip, now));
</script>

<HubStatusBadge {status} testid="trip-detail-status-badge" />
