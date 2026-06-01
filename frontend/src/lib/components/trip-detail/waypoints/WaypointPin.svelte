<script lang="ts">
	// WaypointPin — SVG-Pin-Marker (Kreis + Zahl + spitzer Fuß) für Wegpunkt-Editor.
	// Spec: docs/specs/modules/epic_137_wegpunkt_editor.md

	interface Props {
		index: number;
		active?: boolean;
		suggested?: boolean;
		onclick?: () => void;
		size?: 'sm' | 'md';
	}

	let { index, active = false, suggested = false, onclick, size = 'md' }: Props = $props();

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
	aria-label={onclick ? (suggested ? `Vorgeschlagener Wegpunkt ${index}` : `Wegpunkt ${index}`) : undefined}
	onclick={onclick}
	onkeydown={onclick ? handleKeydown : undefined}
	style:cursor={onclick ? 'pointer' : 'default'}
>
	{#if suggested}
		<!-- Suggested: dashed warning border, white fill -->
		<path
			d="M{dim.w / 2},{dim.h} C{dim.w / 2},{dim.h - dim.r * 0.7} {dim.w},{dim.h / 2} {dim.w},{dim.r} A{dim.r},{dim.r} 0 1 0 0,{dim.r} C0,{dim.h / 2} {dim.w / 2},{dim.h - dim.r * 0.7} {dim.w / 2},{dim.h} Z"
			stroke="var(--g-warn)"
			stroke-width="1.5"
			stroke-dasharray="4,3"
			fill="white"
		/>
		<text
			x={dim.w / 2}
			y={dim.r + 0.35 * dim.r}
			text-anchor="middle"
			dominant-baseline="middle"
			font-size={dim.fs}
			font-family="var(--g-font-ui)"
			fill="var(--g-warn)"
			font-weight="600"
		>{index}</text>
	{:else}
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
	{/if}
</g>
