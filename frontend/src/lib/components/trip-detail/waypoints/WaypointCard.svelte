<script lang="ts">
	// WaypointCard — Listeneintrag fuer einen Wegpunkt in der rechten Spalte.
	// Spec: docs/specs/modules/epic_137_wegpunkt_editor.md §7
	//
	// Layout (horizontal):
	//   [Kreis-Pin (SVG 14px)] [Name] [Hoehe?] [Bestaetigen+Verwerfen | Umbenennen+Loeschen]
	//
	// Aktiv-Hervorhebung: bg-[var(--g-surface-raised)] wenn active === true
	// Pin-Stil: suggested → gestrichelt orange; sonst solid ink-strong

	import CheckIcon from '@lucide/svelte/icons/check';
	import XIcon from '@lucide/svelte/icons/x';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import { Btn } from '$lib/components/ui/btn';
	import WaypointPin from './WaypointPin.svelte';
	import type { Waypoint } from '$lib/types';

	interface Props {
		waypoint: Waypoint;
		index: number;
		active?: boolean;
		onActivate: () => void;
		onConfirm: () => void;
		onReject: () => void;
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
		onConfirm,
		onReject,
		onRename,
		onDelete,
		arrival = null
	}: Props = $props();

	const isSuggested = $derived(waypoint.suggested === true);
</script>

<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
<div
	data-testid="waypoint-card-{index}"
	class="flex items-center gap-3 rounded-md px-3 py-2 cursor-pointer {active
		? 'bg-[var(--g-surface-raised)]'
		: ''}"
	onclick={onActivate}
>
	<!-- WaypointPin-Indikator (sm) -->
	<svg width="14" height="20" role="img" aria-hidden="true">
		<WaypointPin index={index + 1} suggested={isSuggested} active={active} size="sm" />
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

	<!-- Aktionen fuer vorgeschlagene Wegpunkte -->
	{#if isSuggested}
		<Btn
			variant="primary"
			size="xs"
			data-testid="waypoint-confirm-{index}"
			onclick={(e: MouseEvent) => {
				e.stopPropagation();
				onConfirm();
			}}
			aria-label="Wegpunkt bestätigen"
		>
			<CheckIcon class="size-3" />
		</Btn>
		<Btn
			variant="ghost"
			size="xs"
			data-testid="waypoint-reject-{index}"
			onclick={(e: MouseEvent) => {
				e.stopPropagation();
				onReject();
			}}
			aria-label="Wegpunkt verwerfen"
		>
			<XIcon class="size-3" />
		</Btn>
	{:else}
		<!-- Aktionen fuer manuelle (bestaetigte) Wegpunkte -->
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
	{/if}
</div>
