<script lang="ts">
	// ProfileSheetEmbedded — Bottom-Sheet mit Profil + Wegpunktliste (Mobile-Editor).
	// Spec: docs/specs/modules/wegpunkt_editor_handoff.md (AC-5)
	//
	// Drei Snap-Stufen (von Sheet.svelte vererbt):
	//   peek (~92px sichtbar) / half (~320px) / full (~540px)
	//
	// Inhalt:
	//   - EditorProfileSVG (343x70px)
	//   - scrollbare WaypointCard-Liste der aktiven Etappe
	//
	// Container muss position:relative + height: calc(100dvh - 56px) haben,
	// damit Sheet-%-Werte korrekt skalieren. Sheet.svelte bleibt unveraendert.

	import Sheet from '$lib/components/mobile/Sheet.svelte';
	import EditorProfileSVG from '$lib/components/trip-detail/waypoints/EditorProfileSVG.svelte';
	import WaypointCard from '$lib/components/trip-detail/waypoints/WaypointCard.svelte';
	import type { Stage, Waypoint } from '$lib/types';

	type Snap = 'peek' | 'half' | 'full';

	interface Props {
		stage: Stage;
		waypoints?: Waypoint[];
		snapPosition?: Snap;
		activeWaypointId?: string | null;
		onWaypointActivate?: (id: string) => void;
		onWaypointRename?: (id: string) => void;
		onWaypointDelete?: (id: string) => void;
		onProfileAdd?: (fraction: number) => void;
		onSnapChange?: (snap: Snap) => void;
	}

	let {
		stage,
		waypoints = undefined,
		snapPosition = 'half',
		activeWaypointId = null,
		onWaypointActivate = undefined,
		onWaypointRename = undefined,
		onWaypointDelete = undefined,
		onProfileAdd = undefined,
		onSnapChange = undefined
	}: Props = $props();

	// Liste kann explizit uebergeben werden, sonst aus Stage.
	const list = $derived(waypoints ?? stage.waypoints);
	const selectedIndex = $derived(
		activeWaypointId ? list.findIndex((w) => w.id === activeWaypointId) : -1
	);

	function makeActivate(id: string) {
		return () => onWaypointActivate?.(id);
	}
	function makeRename(id: string) {
		return () => onWaypointRename?.(id);
	}
	function makeDelete(id: string) {
		return () => onWaypointDelete?.(id);
	}

	function cycleSnap() {
		const order: Snap[] = ['peek', 'half', 'full'];
		const idx = order.indexOf(snapPosition);
		const next = order[(idx + 1) % order.length];
		onSnapChange?.(next);
	}
</script>

<div class="profile-sheet-host" data-testid="profile-sheet-host">
	<Sheet variant="embedded" snap={snapPosition} title="Wegpunkte" eyebrow="Etappe · {stage.name}">
		<div class="profile-sheet-body">
			<button
				type="button"
				class="snap-cycle-btn"
				data-testid="snap-cycle"
				onclick={cycleSnap}
				aria-label="Sheet-Höhe wechseln (peek/half/full)"
			>
				Höhe: {snapPosition}
			</button>

			<div class="profile-row" data-testid="profile-row">
				<EditorProfileSVG {stage} {onProfileAdd} {selectedIndex} />
			</div>

			<div class="waypoint-list" data-testid="waypoint-list">
				{#each list as wp, i (wp.id)}
					<WaypointCard
						waypoint={wp}
						index={i}
						active={wp.id === activeWaypointId}
						onActivate={makeActivate(wp.id)}
						onRename={makeRename(wp.id)}
						onDelete={makeDelete(wp.id)}
					/>
				{/each}
				{#if list.length === 0}
					<p class="empty">Keine Wegpunkte. Tippe auf die Karte, um einen zu setzen.</p>
				{/if}
			</div>
		</div>
	</Sheet>
</div>

<style>
	.profile-sheet-host {
		position: relative;
		height: calc(100dvh - 56px);
		pointer-events: none;
	}
	.profile-sheet-host :global([data-snap]) {
		pointer-events: auto;
	}
	.profile-sheet-body {
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding-bottom: 12px;
	}
	.snap-cycle-btn {
		align-self: flex-start;
		font-size: 12px;
		padding: 4px 10px;
		border: 1px solid var(--g-rule);
		background: var(--g-card);
		border-radius: 12px;
		cursor: pointer;
		color: var(--g-ink-muted);
	}
	.profile-row {
		display: flex;
		justify-content: center;
	}
	.waypoint-list {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.empty {
		padding: 14px;
		font-size: 13px;
		color: var(--g-ink-muted);
		margin: 0;
	}
</style>
