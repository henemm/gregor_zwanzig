<script lang="ts">
	// WaypointPin — SVG-Pin-Marker (Kreis + Zahl + spitzer Fuß) für Wegpunkt-Editor.
	// Spec: docs/specs/modules/epic_137_wegpunkt_editor.md
	//
	// Issue #522: Der gestrichelte `suggested`-Branch wurde entfernt (toter Code
	// nach Issue #503 — alle Wegpunkte sind gleichwertig). Komponente bleibt für
	// zukünftige Leaflet Custom Marker bestehen.

	interface Props {
		index: number;
		active?: boolean;
		onclick?: () => void;
		size?: 'sm' | 'md';
	}

	let { index, active = false, onclick, size = 'md' }: Props = $props();

	const dim = $derived(size === 'sm' ? { w: 14, h: 20, r: 5, fs: 6 } : { w: 20, h: 28, r: 7, fs: 9 });

	function handleKeydown(e: KeyboardEvent): void {
		if (onclick && (e.key === 'Enter' || e.key === ' ')) {
			e.preventDefault();
			onclick();
		}
	}
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<g
	style={active ? 'filter: drop-shadow(0 0 3px var(--g-accent))' : undefined}
	role={onclick ? 'button' : undefined}
	tabindex={onclick ? 0 : undefined}
	aria-label={onclick ? `Wegpunkt ${index}` : undefined}
	onclick={onclick}
	onkeydown={onclick ? handleKeydown : undefined}
	style:cursor={onclick ? 'pointer' : 'default'}
>
	<!-- Standard: filled ink-strong -->
	<path
		d="M{dim.w / 2},{dim.h} C{dim.w / 2},{dim.h - dim.r * 0.7} {dim.w},{dim.h / 2} {dim.w},{dim.r} A{dim.r},{dim.r} 0 1 0 0,{dim.r} C0,{dim.h / 2} {dim.w / 2},{dim.h - dim.r * 0.7} {dim.w / 2},{dim.h} Z"
		fill="var(--g-ink-strong)"
	/>
	<text
		x={dim.w / 2}
		y={dim.r + 0.35 * dim.r}
		text-anchor="middle"
		dominant-baseline="middle"
		font-size={dim.fs}
		font-family="var(--g-font-ui)"
		fill="white"
		font-weight="600"
	>{index}</text>
</g>
