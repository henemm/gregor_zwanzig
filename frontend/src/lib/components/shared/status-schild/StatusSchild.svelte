<script lang="ts">
	// #2837 S1b (Spec docs/specs/modules/rework_2837_s1b_status_profil.md, ADR-0110 Punkt 4,
	// ADR-0097): EIN Status-Schild für Trip und Ortsvergleich (vormals TripStatusBadge und
	// CompareStatusPill). Gefüllte Pill (seit #2980) mit Tone je Zustand, Text aus dem Katalog trip.status.*;
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

	// #2980 AC-21 (ADR-0118, Mockup Z. 41–43 und 326): gefüllt ohne Rahmen — aktiv = good
	// (--g-good auf hellgrün), alle anderen Zustände neutral (--g-ink-3 auf --g-paper-deep).
	// Die Mockup-Töne setzt app.css über data-schild="status" (andere Pill-Konsumenten unberührt).
	const TONE_MAP: Record<TripStatus, 'good' | 'neutral'> = {
		draft: 'neutral',
		planned: 'neutral',
		active: 'good',
		paused: 'neutral',
		finished: 'neutral',
		archived: 'neutral'
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

<Pill tone={TONE_MAP[status]} data-schild="status" data-status={status} data-testid={testid}>
	{$t(LABEL_MAP[status])}
</Pill>
