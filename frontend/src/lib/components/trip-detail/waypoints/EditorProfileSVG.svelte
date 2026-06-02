<script lang="ts">
	// EditorProfileSVG — vereinfachtes 343x70px Hoehenprofil fuer Mobile-Editor.
	// Spec: docs/specs/modules/wegpunkt_editor_handoff.md (AC-6)
	//
	// Identische Signatur wie ProfileEditor.svelte:
	//   - stage, onProfileAdd(fraction), selectedIndex
	// Vereinfachte Darstellung:
	//   - SVG 343x70 (passend zum Mobile-Sheet)
	//   - Polyline aus Wegpunkt-Hoehendaten
	//   - Wegpunkt-Pins als kleine Kreise
	//   - Klick auf Flaeche -> onProfileAdd(fraction = clickX / 343)

	import type { Stage, Waypoint } from '$lib/types';

	interface Props {
		stage: Stage;
		onProfileAdd?: (fraction: number) => void;
		selectedIndex?: number;
	}

	let { stage, onProfileAdd = undefined, selectedIndex = -1 }: Props = $props();

	const SVG_W = 343;
	const SVG_H = 70;
	const PAD = 6;
	const INNER_W = SVG_W - 2 * PAD; // 331
	const INNER_H = SVG_H - 2 * PAD; // 58

	interface PinPos {
		x: number;
		y: number;
		wp: Waypoint;
		idx: number;
	}

	function computePositions(wps: Waypoint[]): PinPos[] {
		if (wps.length === 0) return [];
		const elevations = wps.map((wp) => wp.elevation_m ?? 0);
		const minElev = Math.min(...elevations);
		const maxElev = Math.max(...elevations);
		const range = maxElev - minElev;
		return wps.map((wp, i) => {
			const x =
				wps.length === 1 ? PAD + INNER_W / 2 : PAD + (i / (wps.length - 1)) * INNER_W;
			let y: number;
			if (range === 0) {
				y = PAD + INNER_H / 2;
			} else {
				const elev = wp.elevation_m ?? minElev;
				y = PAD + (1 - (elev - minElev) / range) * INNER_H;
			}
			return { x, y, wp, idx: i };
		});
	}

	const waypoints = $derived(stage.waypoints);
	const positions = $derived(computePositions(waypoints));
	const polylinePoints = $derived(
		positions.length >= 2 ? positions.map((p) => `${p.x},${p.y}`).join(' ') : ''
	);

	function makeProfileAddHandler() {
		return function handleProfileAdd(e: MouseEvent) {
			if (!onProfileAdd) return;
			const svg = (e.currentTarget as SVGElement).ownerSVGElement
				?? (e.currentTarget as SVGSVGElement);
			const rect = svg.getBoundingClientRect();
			const scaleX = rect.width > 0 ? SVG_W / rect.width : 1;
			const svgX = (e.clientX - rect.left) * scaleX;
			const raw = svgX / SVG_W;
			const fraction = Math.min(1, Math.max(0, raw));
			onProfileAdd(fraction);
		};
	}
</script>

<svg
	data-testid="editor-profile-svg"
	width={SVG_W}
	height={SVG_H}
	viewBox="0 0 {SVG_W} {SVG_H}"
	role="img"
	aria-label="Höhenprofil mit {waypoints.length} Wegpunkten"
	class="editor-profile-svg"
>
	{#if onProfileAdd}
		<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions a11y_no_noninteractive_element_interactions -->
		<rect
			data-testid="editor-profile-add-area"
			x="0"
			y="0"
			width={SVG_W}
			height={SVG_H}
			fill="transparent"
			role="button"
			tabindex="-1"
			aria-label="Wegpunkt einfügen"
			onclick={makeProfileAddHandler()}
			style="cursor: copy;"
		/>
	{/if}

	{#if polylinePoints}
		<polyline
			points={polylinePoints}
			fill="none"
			stroke="var(--g-ink-muted)"
			stroke-width="1.5"
		/>
	{/if}

	{#each positions as p (p.wp.id)}
		{@const isActive = p.idx === selectedIndex}
		<circle
			cx={p.x}
			cy={p.y}
			r={isActive ? 5 : 3.5}
			fill="var(--g-ink-strong)"
			stroke="var(--g-ink-strong)"
			stroke-width="1.5"
			aria-label="Wegpunkt {p.wp.name}"
		/>
	{/each}
</svg>

<style>
	.editor-profile-svg {
		background: var(--g-card);
		border: 1px solid var(--g-rule);
		border-radius: 4px;
		display: block;
		width: 100%;
		max-width: 343px;
		height: 70px;
	}
</style>
