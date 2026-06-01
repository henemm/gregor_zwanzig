<script lang="ts">
	// ProfileEditor — SVG-Hoehenprofil 360x140, Padding 8px (Zeichenflaeche 344x124).
	//
	// Analog zu ProfileChart.svelte (Wizard Step 3), erweitert um:
	//   - Gridlines bei 25%, 50%, 75% der Zeichenflaeche-Hoehe
	//   - Klickbare Pins: onclick ruft onWaypointActivate(waypoint.id) auf
	//   - Aktiver Pin: r=7 statt r=5
	//
	// Pin-Style:
	//   - fill=ink-strong, stroke=ink-strong, stroke-width=2
	//   - aktiv: r=7
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
		// Issue #296-FE: nur im Trip-Editor gesetzt. Klick auf die Profil-Flaeche
		// fuegt einen Wegpunkt ein (fraction 0..1 entlang Profil-x). Detail-View
		// gibt das Prop NICHT → keine Regression.
		onProfileAdd?: (fraction: number) => void;
	}

	let { stage, activeWaypointId, onWaypointActivate, onProfileAdd }: Props = $props();

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
		return function handleWaypointClick(e: MouseEvent) {
			// Issue #296-FE: Pin-Klick aktiviert nur, fuegt NICHT hinzu — verhindert,
			// dass der darunterliegende Flaechen-Click (onProfileAdd) mitfeuert.
			e.stopPropagation();
			onWaypointActivate(waypointId);
		};
	}

	function makeWaypointKeyHandler(waypointId: string) {
		return function handleWaypointKey(e: KeyboardEvent) {
			if (e.key === 'Enter' || e.key === ' ') onWaypointActivate(waypointId);
		};
	}

	// Issue #296-FE: Klick auf die Profil-Flaeche → fraction 0..1 entlang x.
	// Nur aktiv wenn onProfileAdd gesetzt ist (Trip-Editor). Factory-Pattern
	// (Safari-Closure-Schutz, siehe CLAUDE.md / WaypointsPanel-Vorbild).
	function makeProfileAddHandler() {
		return function handleProfileAdd(e: MouseEvent) {
			if (!onProfileAdd) return;
			const svg = (e.currentTarget as SVGElement).ownerSVGElement
				?? (e.currentTarget as SVGSVGElement);
			const rect = svg.getBoundingClientRect();
			// clientX → SVG-Userspace-x (viewBox 0..svgW skaliert auf rect.width).
			const scaleX = rect.width > 0 ? svgW / rect.width : 1;
			const svgX = (e.clientX - rect.left) * scaleX;
			const raw = (svgX - padding) / innerW;
			const fraction = Math.min(1, Math.max(0, raw));
			onProfileAdd(fraction);
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
	<!-- Issue #296-FE: transparente Klick-Flaeche zum Hinzufuegen (nur im Editor). -->
	{#if onProfileAdd}
		<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
		<rect
			data-testid="profile-add-area"
			x="0"
			y="0"
			width={svgW}
			height={svgH}
			fill="transparent"
			onclick={makeProfileAddHandler()}
			style="cursor: copy;"
		/>
	{/if}

	<!-- Gridlines bei 25%, 50%, 75% der Zeichenflaeche-Hoehe -->
	<!-- audit:exempt — dekorativ -->
	<line
		stroke="var(--g-ink-faint)"
		x1={padding}
		y1={padding + innerH * 0.25}
		x2={svgW - padding}
		y2={padding + innerH * 0.25}
		stroke-dasharray="2,4"
		stroke-width="0.5"
	/>
	<!-- audit:exempt — dekorativ -->
	<line
		stroke="var(--g-ink-faint)"
		x1={padding}
		y1={padding + innerH * 0.5}
		x2={svgW - padding}
		y2={padding + innerH * 0.5}
		stroke-dasharray="2,4"
		stroke-width="0.5"
	/>
	<!-- audit:exempt — dekorativ -->
	<line
		stroke="var(--g-ink-faint)"
		x1={padding}
		y1={padding + innerH * 0.75}
		x2={svgW - padding}
		y2={padding + innerH * 0.75}
		stroke-dasharray="2,4"
		stroke-width="0.5"
	/>

	{#if polylinePoints}
		<polyline
			points={polylinePoints}
			fill="none"
			stroke="var(--g-ink-muted)"
			stroke-width="1.5"
		/>
	{/if}

	{#each positions as p (p.wp.id)}
		{@const isActive = p.wp.id === activeWaypointId}
		<circle
			cx={p.x}
			cy={p.y}
			r={isActive ? 7 : 5}
			fill="var(--g-ink-strong)"
			stroke="var(--g-ink-strong)"
			stroke-width="2"
			onclick={makeWaypointClickHandler(p.wp.id)}
			onkeydown={makeWaypointKeyHandler(p.wp.id)}
			role="button"
			tabindex="0"
			aria-label="Wegpunkt {p.wp.name}"
			style="cursor: pointer;"
		/>
	{/each}
</svg>
