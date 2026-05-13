<script lang="ts">
	// Epic #135 Step 4 (Issue #156) — Multi-Stage SVG-Hoehenprofil.
	// Spec: docs/specs/modules/epic_135_step4_left_column.md §3.
	//
	// SVG mit ViewBox 0 0 1000 220:
	//   - Active-Stage-Fill: <rect> mit fill=var(--g-accent), opacity=0.15
	//   - Selected-Stage-Outline: <rect fill="none" stroke=var(--g-accent)>
	//   - Polyline der Profilpunkte
	//   - Hit-Areas (transparente <rect>) pro Stage mit onclick
	//   - Stage-Code-Labels unter Profil
	//
	// Safari-Kompatibilitaet: Named-Function-Factory `makeStageClickHandler(id)`
	// statt Inline-Arrows mit Loop-Variable.

	import type { Trip } from '$lib/types';
	import {
		buildProfilePoints,
		computeStageBoundaries,
		getActiveStageId
	} from '$lib/utils/fullProfile';

	interface Props {
		trip: Trip;
		selectedStageId: string | null;
		onSelectStage: (id: string) => void;
		now?: Date;
	}

	let {
		trip,
		selectedStageId,
		onSelectStage,
		now = new Date()
	}: Props = $props();

	// ViewBox-Konstanten
	const VB_WIDTH = 1000;
	const VB_HEIGHT = 220;
	const PROFILE_HEIGHT = 180; // obere Profil-Flaeche
	const LABEL_Y = 205; // y-Position der Stage-Labels

	const points = $derived(buildProfilePoints(trip));
	const boundaries = $derived(computeStageBoundaries(trip));
	const activeStageId = $derived(getActiveStageId(trip, now));

	// Maximale x-Distanz aller Punkte und Boundaries (Boundaries decken auch
	// Stages ohne Waypoints ab, deshalb beide Quellen einbeziehen).
	const xMax = $derived.by(() => {
		let m = 0;
		for (const p of points) if (p.x > m) m = p.x;
		for (const b of boundaries) if (b.xEnd > m) m = b.xEnd;
		return m;
	});

	const yRange = $derived.by(() => {
		if (points.length === 0) return { min: 0, max: 0, pad: 50 };
		let min = points[0].y;
		let max = points[0].y;
		for (const p of points) {
			if (p.y < min) min = p.y;
			if (p.y > max) max = p.y;
		}
		const range = max - min;
		const pad = range === 0 ? 50 : range * 0.05;
		return { min, max, pad };
	});

	function scaleX(x: number): number {
		if (xMax <= 0) return 0;
		return (x / xMax) * VB_WIDTH;
	}

	function scaleY(y: number): number {
		const { min, max, pad } = yRange;
		const lo = min - pad;
		const hi = max + pad;
		const range = hi - lo;
		if (range <= 0) return PROFILE_HEIGHT / 2;
		return PROFILE_HEIGHT - ((y - lo) / range) * PROFILE_HEIGHT;
	}

	const polylinePoints = $derived(
		points.map((p) => `${scaleX(p.x)},${scaleY(p.y)}`).join(' ')
	);

	const activeBoundary = $derived(
		activeStageId === null
			? null
			: (boundaries.find((b) => b.stageId === activeStageId) ?? null)
	);

	const selectedBoundary = $derived(
		selectedStageId === null
			? null
			: (boundaries.find((b) => b.stageId === selectedStageId) ?? null)
	);

	const showSvg = $derived(boundaries.length > 0);

	// Safari-Closure-Factory: pro stageId einen benannten Handler erzeugen.
	function makeStageClickHandler(id: string) {
		return function onStageClick() {
			onSelectStage(id);
		};
	}
</script>

<div data-testid="trip-full-profile" class="trip-full-profile">
	{#if !showSvg}
		<p data-testid="trip-full-profile-empty" class="empty">Keine Etappen geplant</p>
	{:else}
		<svg
			viewBox="0 0 {VB_WIDTH} {VB_HEIGHT}"
			preserveAspectRatio="none"
			role="img"
			aria-label="Hoehenprofil aller Etappen"
		>
			<!-- Active-Stage-Fill -->
			{#if activeBoundary}
				<rect
					x={scaleX(activeBoundary.xStart)}
					y={0}
					width={Math.max(1, scaleX(activeBoundary.xEnd) - scaleX(activeBoundary.xStart))}
					height={PROFILE_HEIGHT}
					fill="var(--g-accent)"
					opacity="0.15"
				/>
			{/if}

			<!-- Selected-Stage-Outline -->
			{#if selectedBoundary}
				<rect
					x={scaleX(selectedBoundary.xStart)}
					y={0}
					width={Math.max(1, scaleX(selectedBoundary.xEnd) - scaleX(selectedBoundary.xStart))}
					height={PROFILE_HEIGHT}
					fill="none"
					stroke="var(--g-accent)"
					stroke-width="2"
				/>
			{/if}

			<!-- Polyline -->
			{#if points.length >= 2}
				<polyline
					points={polylinePoints}
					fill="none"
					stroke="currentColor"
					stroke-width="1.5"
				/>
			{:else if points.length === 1}
				<circle
					cx={scaleX(points[0].x)}
					cy={scaleY(points[0].y)}
					r="2"
					fill="currentColor"
				/>
			{/if}

			<!-- Hit-Areas pro Stage -->
			{#each boundaries as b (b.stageId)}
				<!-- svelte-ignore a11y_click_events_have_key_events -->
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<rect
					data-testid="trip-full-profile-stage-{b.stageId}"
					role="button"
					tabindex="0"
					aria-label="Etappe {b.code} auswaehlen"
					x={scaleX(b.xStart)}
					y={0}
					width={Math.max(1, scaleX(b.xEnd) - scaleX(b.xStart))}
					height={PROFILE_HEIGHT}
					fill="transparent"
					pointer-events="all"
					style="cursor: pointer"
					onclick={makeStageClickHandler(b.stageId)}
				/>
			{/each}

			<!-- Stage-Code-Labels -->
			{#each boundaries as b (b.stageId)}
				{@const mid = scaleX((b.xStart + b.xEnd) / 2)}
				<text
					data-testid="trip-full-profile-label-{b.stageId}"
					x={mid}
					y={LABEL_Y}
					text-anchor="middle"
					font-size="14"
					fill="currentColor"
				>
					{b.code}
				</text>
			{/each}
		</svg>
	{/if}
</div>

<style>
	.trip-full-profile {
		width: 100%;
	}
	.trip-full-profile svg {
		width: 100%;
		height: 200px;
		display: block;
		color: var(--g-ink, currentColor);
	}
	.empty {
		padding: 1rem;
		color: var(--g-ink-faint, #6b7280);
		font-size: 0.875rem;
	}
</style>
