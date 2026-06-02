<script lang="ts">
	// MapControl — neutraler Karten-Werkzeug-Cluster fuer Mobile-Editor (Issue #542).
	// Spec: docs/specs/modules/wegpunkt_editor_handoff.md (AC-2)
	// Design-Referenz: docs/design-requests/Gregor 20 - Wegpunkt-Editor im Etappen-Tab.html
	//
	// Drei vertikal gestapelte Buttons (44x44px Touch-Target):
	//   1. add-waypoint (plus-Icon)
	//   2. map-style    (map-Icon)
	//   3. search       (search-Icon)
	//
	// AP-012-Ausnahme: neutral (--g-card Hintergrund, KEIN Akzent), damit der
	// Cluster nicht mit Wetter-/Status-Pills konkurriert.
	//
	// Positionierung: absolute top:12px right:12px (Eltern-Container muss
	// position: relative haben).

	import MIcon from '$lib/components/mobile/MIcon.svelte';

	interface Props {
		onAddWaypoint?: () => void;
		onMapStyle?: () => void;
		onSearch?: () => void;
	}

	let {
		onAddWaypoint = undefined,
		onMapStyle = undefined,
		onSearch = undefined
	}: Props = $props();

	// Factory-Pattern fuer Safari-Closure-Schutz (siehe CLAUDE.md).
	function makeAddHandler() {
		return function handleAdd() {
			onAddWaypoint?.();
		};
	}
	function makeStyleHandler() {
		return function handleStyle() {
			onMapStyle?.();
		};
	}
	function makeSearchHandler() {
		return function handleSearch() {
			onSearch?.();
		};
	}
</script>

<div class="map-control" data-testid="map-control">
	<button
		type="button"
		class="map-control-btn"
		data-testid="add-waypoint"
		aria-label="Wegpunkt hinzufügen"
		onclick={makeAddHandler()}
	>
		<MIcon kind="plus" />
	</button>
	<button
		type="button"
		class="map-control-btn"
		data-testid="map-style"
		aria-label="Kartenstil wechseln"
		onclick={makeStyleHandler()}
	>
		<MIcon kind="map" />
	</button>
	<button
		type="button"
		class="map-control-btn"
		data-testid="search"
		aria-label="Suchen"
		onclick={makeSearchHandler()}
	>
		<MIcon kind="search" />
	</button>
</div>

<style>
	.map-control {
		position: absolute;
		top: 12px;
		right: 12px;
		display: flex;
		flex-direction: column;
		gap: 6px;
		z-index: 20;
	}
	.map-control-btn {
		width: 44px;
		height: 44px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		background: var(--g-card);
		border: 1px solid var(--g-rule);
		border-radius: 8px;
		box-shadow: var(--g-shadow-2, 0 2px 6px rgba(26, 26, 24, 0.12));
		cursor: pointer;
		color: var(--g-ink);
		padding: 0;
	}
	.map-control-btn:hover {
		background: var(--g-card);
		border-color: var(--g-ink-faint);
	}
	.map-control-btn:focus-visible {
		outline: 2px solid var(--g-ink);
		outline-offset: 2px;
	}
</style>
