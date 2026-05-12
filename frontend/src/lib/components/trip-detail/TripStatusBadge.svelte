<script lang="ts">
	// Spec: docs/specs/modules/epic_135_step2_trip_detail_actions.md (§5)
	// Thin-Wrapper um Pill mit Tone-Mapping und deutschem Label pro Status.
	import Pill from '$lib/components/ui/pill/Pill.svelte';
	import { deriveTripStatus, type TripStatus } from '$lib/utils/tripStatus';
	import type { Trip } from '$lib/types';

	interface Props {
		trip: Trip;
		now?: Date;
	}

	let { trip, now = new Date() }: Props = $props();

	const TONE_MAP: Record<TripStatus, 'info' | 'success' | 'warning' | 'default'> = {
		planned: 'info',
		active: 'success',
		paused: 'warning',
		archived: 'default'
	};

	const LABEL_MAP: Record<TripStatus, string> = {
		planned: 'Geplant',
		active: 'Aktiv',
		paused: 'Pausiert',
		archived: 'Archiviert'
	};

	const status = $derived(deriveTripStatus(trip, now));
</script>

<Pill tone={TONE_MAP[status]} data-testid="trip-detail-status-badge">
	{LABEL_MAP[status]}
</Pill>
