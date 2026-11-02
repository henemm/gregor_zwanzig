<script lang="ts">
	// Spec: docs/specs/modules/epic_135_step2_trip_detail_actions.md (§5)
	// Thin-Wrapper um Pill mit Tone-Mapping und deutschem Label pro Status.
	import { Pill } from '$lib/components/atoms';
	import { deriveTripStatus, type TripStatus } from '$lib/utils/tripStatus';
	import type { Trip } from '$lib/types';
	import { t, type MessageKey } from '$lib/i18n';

	interface Props {
		trip: Trip;
		now?: Date;
	}

	let { trip, now = new Date() }: Props = $props();

	const TONE_MAP: Record<TripStatus, 'info' | 'accent' | 'warning' | 'default'> = {
		draft: 'default',
		planned: 'info',
		active: 'accent',
		paused: 'warning',
		finished: 'default',
		archived: 'default'
	};

	// i18n F9: Status-Namen aus dem Katalog (trip.status.*; de: Entwurf, Geplant, Aktiv,
	// Pausiert, Fertig, Archiviert), aufgeloest beim Rendern.
	const LABEL_MAP: Record<TripStatus, MessageKey> = {
		draft: 'trip.status.draft',
		planned: 'trip.status.planned',
		active: 'trip.status.active',
		paused: 'trip.status.paused',
		finished: 'trip.status.finished',
		archived: 'trip.status.archived'
	};

	const status = $derived(deriveTripStatus(trip, now));
</script>

<Pill tone={TONE_MAP[status]} data-outlined data-testid="trip-detail-status-badge">
	{$t(LABEL_MAP[status])}
</Pill>
