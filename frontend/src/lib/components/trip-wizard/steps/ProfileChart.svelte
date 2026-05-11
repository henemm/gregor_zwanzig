<script lang="ts">
	// ProfileChart — SVG-Hoehenprofil mit Pin-Markern (Sub-Spec #163 §5).
	//
	// Default 360x120, Padding 8px allseits → innere Zeichenflaeche 344x104.
	// Polyline + ein <circle r=5> pro Wegpunkt.
	//
	// Pin-Style:
	//   - suggested === true:  stroke=warning, dasharray=3,3, fill=white, stroke-width=2
	//   - sonst (bestaetigt):  stroke=ink-strong, fill=ink-strong
	//
	// Edge-Cases (Spec §8d/e):
	//   - 0 Wegpunkte  → keine Polyline, keine Pins (leere Zeichenflaeche)
	//   - 1 Wegpunkt   → einzelner Pin mittig (kein Polyline-Stroke)
	//   - elevation_m gleich (max == min) → alle Punkte auf Mittellinie
	//
	// ARIA: aria-label `Hoehenprofil mit ${N} Wegpunkten`.

	import type { Stage, Waypoint } from '$lib/types';

	interface Props {
		stage: Stage;
		width?: number;
		height?: number;
	}

	let { stage, width = 360, height = 120 }: Props = $props();

	const padding = 8;

	const waypoints = $derived(stage.waypoints);
	const n = $derived(waypoints.length);

	interface PinPos {
		x: number;
		y: number;
		wp: Waypoint;
	}

	function computePositions(wps: Waypoint[], w: number, h: number): PinPos[] {
		if (wps.length === 0) return [];
		const innerW = w - 2 * padding;
		const innerH = h - 2 * padding;
		const elevations = wps.map((wp) => wp.elevation_m ?? 0);
		const minElev = Math.min(...elevations);
		const maxElev = Math.max(...elevations);
		const range = maxElev - minElev;
		return wps.map((wp, i) => {
			const x = wps.length === 1 ? padding + innerW / 2 : padding + (i / (wps.length - 1)) * innerW;
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

	const positions = $derived(computePositions(waypoints, width, height));

	const polylinePoints = $derived(
		positions.length >= 2 ? positions.map((p) => `${p.x},${p.y}`).join(' ') : ''
	);
</script>

<svg
	data-testid="trip-wizard-step3-profile-chart"
	{width}
	{height}
	viewBox="0 0 {width} {height}"
	role="img"
	aria-label="Hoehenprofil mit {n} Wegpunkten"
	class="border border-[var(--g-ink-faint)]/20 rounded bg-white/40"
>
	{#if polylinePoints}
		<polyline
			points={polylinePoints}
			fill="none"
			stroke="var(--g-ink-faint)"
			stroke-width="1.5"
		/>
	{/if}
	{#each positions as p (p.wp.id)}
		{#if p.wp.suggested === true}
			<circle
				cx={p.x}
				cy={p.y}
				r="5"
				stroke="var(--g-warning)"
				stroke-dasharray="3,3"
				stroke-width="2"
				fill="white"
			/>
		{:else}
			<circle cx={p.x} cy={p.y} r="5" stroke="var(--g-ink-strong)" fill="var(--g-ink-strong)" />
		{/if}
	{/each}
</svg>
