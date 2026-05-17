<script lang="ts">
	// ProfileEditor — SVG-Hoehenprofil 360x140, Padding 8px (Zeichenflaeche 344x124).
	//
	// Analog zu ProfileChart.svelte (Wizard Step 3), erweitert um:
	//   - Gridlines bei 25%, 50%, 75% der Zeichenflaeche-Hoehe
	//   - Klickbare Pins: onclick ruft onWaypointActivate(waypoint.id) auf
	//   - Aktiver Pin: r=7 statt r=5
	//
	// Pin-Style:
	//   - suggested === true:  stroke=warning, dasharray=3,3, fill=white, stroke-width=2
	//   - bestaetigt:         fill=ink-strong, stroke=ink-strong
	//   - aktiv:              r=7
	//
	// Edge-Cases (wie ProfileChart §8d/e):
	//   - 0 Wegpunkte  → keine Polyline, keine Pins
	//   - 1 Wegpunkt   → Pin mittig (kein Polyline-Stroke)
	//   - elevation_m gleich (max == min) → alle Punkte auf Mittellinie
	//
	// ARIA: aria-label `Hoehenprofil mit ${N} Wegpunkten`.

	import type { Stage, Waypoint } from '$lib/types';

	interface Props {
		stage: Stage;
		activeWaypointId: string | null;
		onWaypointActivate: (waypointId: string) => void;
	}

	let { stage, activeWaypointId, onWaypointActivate }: Props = $props();

	const padding = 8;
	const svgW = 360;
	const svgH = 140;
	const innerW = svgW - 2 * padding; // 344
	const innerH = svgH - 2 * padding; // 124

	const waypoints = $derived(stage.waypoints);
	const n = $derived(waypoints.length);

	interface PinPos {
		x: number;
		y: number;
		wp: Waypoint;
	}

	function computePositions(wps: Waypoint[]): PinPos[] {
		if (wps.length === 0) return [];
		const elevations = wps.map((wp) => wp.elevation_m ?? 0);
		const minElev = Math.min(...elevations);
		const maxElev = Math.max(...elevations);
		const range = maxElev - minElev;
		return wps.map((wp, i) => {
			const x =
				wps.length === 1 ? padding + innerW / 2 : padding + (i / (wps.length - 1)) * innerW;
			let y: number;
			if (range === 0) {
				y = padding + innerH / 2;
			} else {
				const elev = wp.elevation_m ?? minElev;
				y = padding + (1 - (elev - minElev) / range) * innerH;
			}
			return { x, y, wp };
		});
	}

	const positions = $derived(computePositions(waypoints));

	const polylinePoints = $derived(
		positions.length >= 2 ? positions.map((p) => `${p.x},${p.y}`).join(' ') : ''
	);

	function makeWaypointClickHandler(waypointId: string) {
		return function handleWaypointClick() {
			onWaypointActivate(waypointId);
		};
	}

	function makeWaypointKeyHandler(waypointId: string) {
		return function handleWaypointKey(e: KeyboardEvent) {
			if (e.key === 'Enter' || e.key === ' ') onWaypointActivate(waypointId);
		};
	}
</script>

<svg
	data-testid="profile-editor"
	width={svgW}
	height={svgH}
	viewBox="0 0 {svgW} {svgH}"
	role="img"
	aria-label="Höhenprofil mit {n} Wegpunkten"
	class="border border-[var(--g-ink-faint)]/20 rounded bg-white/40 w-full"
>
	<!-- Gridlines bei 25%, 50%, 75% der Zeichenflaeche-Hoehe -->
	<line
		x1={padding}
		y1={padding + innerH * 0.25}
		x2={svgW - padding}
		y2={padding + innerH * 0.25}
		stroke="var(--g-ink-faint)"
		stroke-dasharray="2,4"
		stroke-width="0.5"
	/>
	<line
		x1={padding}
		y1={padding + innerH * 0.5}
		x2={svgW - padding}
		y2={padding + innerH * 0.5}
		stroke="var(--g-ink-faint)"
		stroke-dasharray="2,4"
		stroke-width="0.5"
	/>
	<line
		x1={padding}
		y1={padding + innerH * 0.75}
		x2={svgW - padding}
		y2={padding + innerH * 0.75}
		stroke="var(--g-ink-faint)"
		stroke-dasharray="2,4"
		stroke-width="0.5"
	/>

	{#if polylinePoints}
		<polyline
			points={polylinePoints}
			fill="none"
			stroke="var(--g-ink-faint)"
			stroke-width="1.5"
		/>
	{/if}

	{#each positions as p (p.wp.id)}
		{@const isActive = p.wp.id === activeWaypointId}
		{@const isSuggested = p.wp.suggested === true}
		<circle
			cx={p.x}
			cy={p.y}
			r={isActive ? 7 : 5}
			fill={isSuggested ? 'white' : 'var(--g-ink-strong)'}
			stroke={isSuggested ? 'var(--g-warning)' : 'var(--g-ink-strong)'}
			stroke-width="2"
			stroke-dasharray={isSuggested ? '3,3' : undefined}
			onclick={makeWaypointClickHandler(p.wp.id)}
			onkeydown={makeWaypointKeyHandler(p.wp.id)}
			role="button"
			tabindex="0"
			aria-label="Wegpunkt {p.wp.name}"
			style="cursor: pointer;"
		/>
	{/each}
</svg>
