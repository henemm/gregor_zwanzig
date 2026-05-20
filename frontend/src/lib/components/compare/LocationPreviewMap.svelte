<script lang="ts">
	// Issue #266 — Mini-Map-Vorschau für NewLocationWizard Schritt 1.
	// Spec: docs/specs/modules/issue_266_location_preview_map.md

	import { TopoBg } from '$lib/components/ui/topo';

	interface Props {
		lat: number;
		lon: number;
	}

	let { lat, lon }: Props = $props();
</script>

<div
	class="relative overflow-hidden rounded border border-[var(--g-ink-faint)]/20"
	style="width:240px; height:150px;"
>
	<TopoBg opacity={0.4} />

	<svg
		viewBox="0 0 240 150"
		width="240"
		height="150"
		class="absolute inset-0"
		pointer-events="none"
		role="img"
		aria-label="Kartenvorschau"
	>
		<!-- Zentrierter Accent-Pin: Teardrop-Pfad (20×28px), Spitze bei y=75 (Bildmitte) -->
		<!-- transform: Pin-Breite 20 → x=110 (= 120 - 10), Pin-Höhe 28 → y=47 (= 75 - 28) -->
		<path
			d="M10,28 C10,23.1 20,14 20,7 A7,7 0 1 0 0,7 C0,14 10,23.1 10,28 Z"
			fill="var(--g-accent)"
			transform="translate(110, 47)"
		/>
	</svg>

	<p class="absolute bottom-1 left-2 text-[10px] text-muted-foreground font-mono">
		{lat.toFixed(4)}, {lon.toFixed(4)}
	</p>
</div>
