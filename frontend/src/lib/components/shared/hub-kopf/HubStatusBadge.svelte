<script lang="ts">
	// #2837 AC-15 (BROKEN-Fix): EIN Status-Schild für den Kopf von Trip und Ortsvergleich.
	// Pill-Atom mit Ton und data-outlined (design_system.md §Pill/Badge: Großbuchstaben, Mono,
	// 11px) — Vorlage war TripStatusBadge (epic_135_step2_trip_detail_actions.md §5).
	// Wort für beide Arten aus trip.status.*: listen.status.* liefert andere Wörter
	// (Kleinschreibung, de „draft" statt „Entwurf").
	// Gemeinsames Merkmal für Tests: data-hub-status-badge (testid bleibt je Art wählbar).
	import { Pill } from '$lib/components/atoms';
	import type { TripStatus } from '$lib/utils/tripStatus';
	import { t, type MessageKey } from '$lib/i18n';

	interface Props {
		/** Normierter Status; der Vergleich (active/paused/draft) ist eine Teilmenge. */
		status: TripStatus;
		testid?: string;
	}

	let { status, testid = 'hub-kopf-status-badge' }: Props = $props();

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

<Pill tone={TONE_MAP[status]} data-outlined data-status={status} data-hub-status-badge data-testid={testid}>
	{$t(LABEL_MAP[status])}
</Pill>
