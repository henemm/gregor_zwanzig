<script lang="ts">
	// WaypointRow — eine Zeile in der Waypoint-Liste rechts (Step 3).
	//
	// Props:
	//   waypoint   — Waypoint-Objekt
	//   index      — Position in der Liste (0-basiert) — fuer TestIDs
	//   onReject   — () => void (Löschen-Aktion)
	//
	// Layout (horizontal):
	//   [Pin-Indikator (Inline-SVG)] [Name] [Hoehe] [Zeit] [Verwerfen-Btn]
	//
	// Pin-Style: einheitlich solid (Issue #518): stroke=ink-strong, fill=ink-strong.
	// Verwerfen-Btn: immer sichtbar.

	import XIcon from '@lucide/svelte/icons/x';
	import type { Waypoint } from '$lib/types';

	interface Props {
		waypoint: Waypoint;
		index: number;
		onReject: () => void;
	}

	let { waypoint, index, onReject }: Props = $props();

	function handleReject() {
		onReject();
	}
</script>

<div
	data-testid="trip-wizard-step3-waypoint-row-{index}"
	data-waypoint-index={index}
	class="flex items-center gap-3 border border-[var(--g-ink-faint)]/30 rounded-md px-3 py-2 bg-white/40"
>
	<!-- Pin-Indikator (Inline-SVG, einheitlich solid) -->
	<svg width="14" height="14" viewBox="0 0 14 14" aria-label="Wegpunkt" role="img">
		<circle cx="7" cy="7" r="5" stroke="var(--g-ink-strong)" fill="var(--g-ink-strong)" />
	</svg>

	<span class="flex-1 truncate text-sm">{waypoint.name}</span>

	{#if waypoint.elevation_m}
		<span class="text-sm text-[var(--g-ink-muted)]">{waypoint.elevation_m} m</span>
	{/if}

	{#if waypoint.time_window}
		<span class="text-sm text-[var(--g-ink-muted)]">{waypoint.time_window}</span>
	{/if}

	<button
		type="button"
		data-testid="trip-wizard-step3-reject-{index}"
		onclick={handleReject}
		aria-label="Wegpunkt verwerfen"
		class="rounded p-1 text-[var(--g-ink-muted)] hover:bg-[var(--g-ink-faint)]/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--g-accent)]"
	>
		<XIcon class="size-4" />
	</button>
</div>
