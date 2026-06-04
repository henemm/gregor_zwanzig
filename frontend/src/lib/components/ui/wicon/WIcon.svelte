<script lang="ts">
	// Issue #577 — WIcon: Lucide-Imports entfernt, 8 custom Inline-SVG-Cases.
	// Kanonische Quelle: claude-code-handoff/current/jsx/atoms.jsx::WIcon
	//
	// Spec: docs/specs/modules/issue_577_atoms_design_fidelity.md
	import type { WIconKind } from '$lib/utils/weatherUtils.js';

	interface Props {
		kind?: WIconKind;
		size?: number;
		color?: string;
		class?: string;
	}

	let {
		kind = 'cloud',
		size = 20,
		color = 'currentColor',
		class: className = ''
	}: Props = $props();
</script>

{#if kind === 'sun'}
<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width="1.5" stroke-linecap="round" class={className} aria-hidden="true">
	<circle cx="12" cy="12" r="3.5"/>
	<path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4l1.4-1.4M17 7l1.4-1.4"/>
</svg>
{:else if kind === 'cloud'}
<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width="1.5" stroke-linejoin="round" class={className} aria-hidden="true">
	<path d="M7 17h10a4 4 0 0 0 0.5-7.97A6 6 0 0 0 6.1 11 4 4 0 0 0 7 17z"/>
</svg>
{:else if kind === 'rain'}
<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class={className} aria-hidden="true">
	<path d="M7 14h10a4 4 0 0 0 0.5-7.97A6 6 0 0 0 6.1 8 4 4 0 0 0 7 14z"/>
	<path d="M9 17l-1 3M13 17l-1 3M17 17l-1 3"/>
</svg>
{:else if kind === 'thunder'}
<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class={className} aria-hidden="true">
	<path d="M7 14h10a4 4 0 0 0 0.5-7.97A6 6 0 0 0 6.1 8 4 4 0 0 0 7 14z"/>
	<path d="M12 14l-2 4h3l-2 4"/>
</svg>
{:else if kind === 'snow'}
<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width="1.5" stroke-linecap="round" class={className} aria-hidden="true">
	<path d="M12 3v18M5 7l14 10M5 17l14-10"/>
</svg>
{:else if kind === 'wind'}
<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width="1.5" stroke-linecap="round" class={className} aria-hidden="true">
	<path d="M3 8h11a3 3 0 1 0-3-3M3 12h16a3 3 0 1 1-3 3M3 16h9"/>
</svg>
{:else if kind === 'moon'}
<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width="1.5" stroke-linejoin="round" class={className} aria-hidden="true">
	<path d="M20 14a8 8 0 1 1-10-10 6 6 0 0 0 10 10z"/>
</svg>
{:else if kind === 'headlamp'}
<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" class={className} aria-hidden="true">
	<rect x="7" y="9" width="10" height="6" rx="1.5"/>
	<path d="M17 12l4-1.5v3L17 12zM9 9V7a3 3 0 0 1 6 0v2"/>
</svg>
{/if}
