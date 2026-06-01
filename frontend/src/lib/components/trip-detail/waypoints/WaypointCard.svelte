<script lang="ts">
	// WaypointCard — Listeneintrag fuer einen Wegpunkt in der rechten Spalte.
	// Spec: docs/specs/modules/epic_137_wegpunkt_editor.md §7
	//
	// Issue #503: Die KI/Auto/Manuell-Unterscheidung wurde entfernt. Alle Wegpunkte
	// sind gleichwertig — Aktionen sind einheitlich Umbenennen + Löschen.
	// Layout (horizontal):
	//   [Kreis-Pin (SVG 14px)] [Name] [Hoehe?] [Ankunft?] [Umbenennen] [Löschen]
	//
	// Aktiv-Hervorhebung: bg-[var(--g-surface-raised)] wenn active === true
	// `onConfirm`/`onReject` bleiben als optionale No-Op-Props erhalten (Backward-Compat
	// mit WaypointsPanel.svelte) — werden im UI nicht mehr ausgelöst.

	import XIcon from '@lucide/svelte/icons/x';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import { Btn } from '$lib/components/atoms';
	import WaypointPin from './WaypointPin.svelte';
	import type { Waypoint } from '$lib/types';

	interface Props {
		waypoint: Waypoint;
		index: number;
		active?: boolean;
		onActivate: () => void;
		/** @deprecated Issue #503: KI-Bestätigen entfernt; Prop bleibt für Backward-Compat. */
		onConfirm?: () => void;
		/** @deprecated Issue #503: KI-Verwerfen entfernt; Prop bleibt für Backward-Compat. */
		onReject?: () => void;
		onRename: () => void;
		onDelete: () => void;
		// Issue #296-FE: berechnete Ankunftszeit "HH:MM" (computeArrivalTimes).
		// Nur im Trip-Editor gesetzt; Detail-View gibt das Prop NICHT → unveraendert.
		arrival?: string | null;
	}

	let {
		waypoint,
		index,
		active = false,
		onActivate,
		onRename,
		onDelete,
		arrival = null
	}: Props = $props();
</script>

<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
<div
	data-testid="waypoint-card-{index}"
	class="flex items-center gap-3 rounded-md px-3 py-2 cursor-pointer {active
		? 'bg-[var(--g-surface-raised)]'
		: ''}"
	onclick={onActivate}
>
	<!-- WaypointPin-Indikator (sm) — Issue #503: kein suggested-Stil mehr. -->
	<svg width="14" height="20" role="img" aria-hidden="true">
		<WaypointPin index={index + 1} suggested={false} active={active} size="sm" />
	</svg>

	<!-- Name -->
	<span class="flex-1 truncate text-sm">{waypoint.name}</span>

	<!-- Hoehe (optional) -->
	{#if waypoint.elevation_m}
		<span class="text-xs text-[var(--g-ink-muted)]">{waypoint.elevation_m} m</span>
	{/if}

	<!-- Ankunftszeit (Issue #296-FE, nur wenn Prop gesetzt) -->
	{#if arrival}
		<span
			data-testid="wp-arrival-{index}"
			class="text-xs font-[var(--g-font-data)] text-[var(--g-ink-muted)] tabular-nums"
		>{arrival}</span>
	{/if}

	<!-- Issue #503: einheitliche Aktionen (Umbenennen + Löschen) für ALLE Wegpunkte. -->
	<Btn
		variant="ghost"
		size="xs"
		data-testid="waypoint-rename-{index}"
		onclick={(e: MouseEvent) => {
			e.stopPropagation();
			onRename();
		}}
		aria-label="Wegpunkt umbenennen"
	>
		<PencilIcon class="size-3" />
	</Btn>
	<Btn
		variant="ghost"
		size="xs"
		data-testid="waypoint-delete-{index}"
		onclick={(e: MouseEvent) => {
			e.stopPropagation();
			onDelete();
		}}
		aria-label="Wegpunkt löschen"
	>
		<XIcon class="size-3" />
	</Btn>
</div>
