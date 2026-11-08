<script lang="ts">
	// #2837 S1b (Spec docs/specs/modules/rework_2837_s1b_status_profil.md, ADR-0110 Punkt 4,
	// ADR-0097): EIN Status-Schild für Trip und Ortsvergleich (vormals TripStatusBadge und
	// CompareStatusPill). Umrandete Pill mit Tone je Zustand, Text aus dem Katalog trip.status.*;
	// die drei Vergleichs-Zustände active|paused|draft sind eine Teilmenge von TripStatus.
	// Ursprung der Tone-Zuordnung: epic_135_step2_trip_detail_actions.md (§5), #389.
	import { Pill } from '$lib/components/atoms';
	import type { TripStatus } from '$lib/utils/tripStatus';
	import { t, type MessageKey } from '$lib/i18n';

	interface Props {
		status: TripStatus;
		testid?: string;
	}

	let { status, testid }: Props = $props();

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
</script>

<Pill tone={TONE_MAP[status]} data-outlined data-status={status} data-testid={testid}>
	{$t(LABEL_MAP[status])}
</Pill>
