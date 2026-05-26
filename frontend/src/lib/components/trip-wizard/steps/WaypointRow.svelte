<script lang="ts">
	// WaypointRow — eine Zeile in der Waypoint-Confirm-UI rechts (Sub-Spec #163 §6).
	//
	// Props:
	//   waypoint   — Waypoint-Objekt (suggested?: boolean)
	//   index      — Position in der Liste (0-basiert) — fuer TestIDs
	//   onConfirm  — () => void
	//   onReject   — () => void
	//
	// Layout (horizontal):
	//   [Pin-Indikator (Inline-SVG)] [Name] [Hoehe] [Zeit] [Bestaetigen-Btn?] [Verwerfen-Btn]
	//
	// Pin-Style entspricht ProfileChart (Spec §5):
	//   - suggested:  stroke=warning, dasharray=3,3, fill=white
	//   - bestaetigt: stroke=ink-strong, fill=ink-strong, kein dash
	//
	// Bestaetigen-Btn: nur sichtbar wenn waypoint.suggested === true (AC#11).
	// Verwerfen-Btn: immer sichtbar.

	import Check from '@lucide/svelte/icons/check';
	import X from '@lucide/svelte/icons/x';
	import type { Waypoint } from '$lib/types';

	interface Props {
		waypoint: Waypoint;
		index: number;
		onConfirm: () => void;
		onReject: () => void;
	}

	let { waypoint, index, onConfirm, onReject }: Props = $props();

	const isSuggested = $derived(waypoint.suggested === true);

	function handleConfirm() {
		onConfirm();
	}

	function handleReject() {
		onReject();
	}
</script>

<div
	data-testid="trip-wizard-step3-waypoint-row-{index}"
	data-waypoint-index={index}
	class="flex items-center gap-3 border border-[var(--g-ink-faint)]/30 rounded-md px-3 py-2 bg-white/40"
>
	<!-- Pin-Indikator (Inline-SVG, gleiche Style-Logik wie ProfileChart) -->
	<svg
		width="14"
		height="14"
		viewBox="0 0 14 14"
		aria-label={isSuggested ? 'Vorschlag (unbestätigt)' : 'Bestätigt'}
		role="img"
	>
		{#if isSuggested}
			<circle
				cx="7"
				cy="7"
				r="5"
				stroke="var(--g-warning)"
				stroke-dasharray="3,3"
				stroke-width="2"
				fill="white"
			/>
		{:else}
			<circle cx="7" cy="7" r="5" stroke="var(--g-ink-strong)" fill="var(--g-ink-strong)" />
		{/if}
	</svg>

	<span class="flex-1 truncate text-sm">{waypoint.name}</span>

	{#if waypoint.elevation_m}
		<span class="text-sm text-[var(--g-ink-muted)]">{waypoint.elevation_m} m</span>
	{/if}

	{#if waypoint.time_window}
		<span class="text-sm text-[var(--g-ink-muted)]">{waypoint.time_window}</span>
	{/if}

	{#if isSuggested}
		<button
			type="button"
			data-testid="trip-wizard-step3-confirm-{index}"
			onclick={handleConfirm}
			aria-label="Vorschlag bestätigen"
			data-audit="audit:exempt: Icon (§1.4.11, 3:1)"
			class="rounded p-1 text-[var(--g-accent)] hover:bg-[var(--g-accent)]/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--g-accent)]"
		>
			<Check class="size-4" />
		</button>
	{/if}

	<button
		type="button"
		data-testid="trip-wizard-step3-reject-{index}"
		onclick={handleReject}
		aria-label="Wegpunkt verwerfen"
		class="rounded p-1 text-[var(--g-ink-muted)] hover:bg-[var(--g-ink-faint)]/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--g-accent)]"
	>
		<X class="size-4" />
	</button>
</div>
