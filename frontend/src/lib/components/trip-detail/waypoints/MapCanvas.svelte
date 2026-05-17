<script lang="ts">
	import { buildMapPositions } from '$lib/utils/waypointEditor';
	import { TopoBg } from '$lib/components/ui/topo';
	import WaypointPin from './WaypointPin.svelte';
	import type { Stage } from '$lib/types';

	interface Props {
		stage: Stage;
		activeWaypointId: string | null;
		onWaypointActivate: (waypointId: string) => void;
	}
	let { stage, activeWaypointId, onWaypointActivate }: Props = $props();

	let zoomLevel = $state(1.0);
	let showTopo = $state(true);

	const positions = $derived(buildMapPositions(stage, 400, 300));
	const polylinePoints = $derived(
		positions.length >= 2 ? positions.map((p) => `${p.x},${p.y}`).join(' ') : ''
	);

	function handleZoomIn(): void {
		zoomLevel = Math.min(3.0, zoomLevel + 0.25);
	}
	function handleZoomOut(): void {
		zoomLevel = Math.max(0.5, zoomLevel - 0.25);
	}
	function handleLayerToggle(): void {
		showTopo = !showTopo;
	}
	function makeWaypointClickHandler(waypointId: string) {
		return function handleWaypointClick() {
			onWaypointActivate(waypointId);
		};
	}
	function makeWaypointKeyHandler(waypointId: string) {
		return function handleWaypointKey(e: KeyboardEvent) {
			if (e.key === 'Enter' || e.key === ' ') {
				onWaypointActivate(waypointId);
			}
		};
	}
</script>

<div
	data-testid="map-canvas"
	class="relative rounded border border-[var(--g-ink-faint)]/20 overflow-hidden"
	style="width:400px;height:300px;"
>
	{#if showTopo}
		<TopoBg />
	{/if}

	<svg
		viewBox="0 0 400 300"
		width="400"
		height="300"
		class="absolute inset-0"
		style="transform: scale({zoomLevel}); transform-origin: center;"
		role="img"
		aria-label="Karte für Etappe {stage.name} mit {positions.length} Wegpunkten"
	>
		{#if polylinePoints}
			<polyline
				points={polylinePoints}
				fill="none"
				stroke="var(--g-accent)"
				stroke-width="2"
				stroke-linejoin="round"
				stroke-linecap="round"
			/>
		{/if}

		{#each positions as pos, i (pos.waypointId)}
			{@const wp = stage.waypoints.find((w) => w.id === pos.waypointId)}
			{@const isActive = pos.waypointId === activeWaypointId}
			{@const isSuggested = wp?.suggested === true}
			<g
				data-testid="map-waypoint-pin-{i}"
				transform="translate({pos.x - 10},{pos.y - 28})"
			>
				<WaypointPin
					index={i + 1}
					active={isActive}
					suggested={isSuggested}
					onclick={makeWaypointClickHandler(pos.waypointId)}
				/>
			</g>
		{/each}
	</svg>

	<div class="absolute top-2 right-2 flex flex-col gap-1">
		<button
			data-testid="map-zoom-in"
			onclick={handleZoomIn}
			aria-label="Heranzoomen"
			class="rounded bg-white/80 px-2 py-1 text-sm shadow hover:bg-white"
		>+</button>
		<button
			data-testid="map-zoom-out"
			onclick={handleZoomOut}
			aria-label="Herauszoomen"
			class="rounded bg-white/80 px-2 py-1 text-sm shadow hover:bg-white"
		>−</button>
	</div>
	<button
		data-testid="map-layer-toggle"
		onclick={handleLayerToggle}
		class="absolute bottom-2 right-2 rounded bg-white/80 px-2 py-1 text-xs shadow hover:bg-white"
		aria-label={showTopo ? 'Auf Standardkarte wechseln' : 'Auf Topokarte wechseln'}
	>
		{showTopo ? 'Sat' : 'Topo'}
	</button>
</div>
