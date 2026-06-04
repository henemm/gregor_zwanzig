<script lang="ts">
	// Issue #577 — QuickAction: ASCII-Glyphen durch Inline-SVG ersetzt.
	// Kanonische Quelle: claude-code-handoff/current/jsx/molecules.jsx::QuickActionGlyph
	//
	// Issue #568 — QuickAction-Molecule (Startseite-Cockpit).
	// Spec: docs/specs/modules/issue_568_home_redesign.md
	//
	// Anchor-based Navigations-Kachel mit Glyph + Label + Sub + Chevron.
	// Mobile Touch-Target ≥ 44 px (AC-7). Kein onClick, direkter href.

	interface Props {
		glyph: string;
		label: string;
		sub: string;
		href: string;
		tone?: 'default' | 'accent';
		size?: 'md' | 'lg';
		class?: string;
	}

	let {
		glyph,
		label,
		sub,
		href,
		tone = 'default',
		size = 'md',
		class: className = ''
	}: Props = $props();

	const isAccent = $derived(tone === 'accent');
	const isLarge = $derived(size === 'lg');

	// Touch-Target: md = 44 px (Mobile-Minimum, AC-7), lg = 56 px.
	const minH = $derived(isLarge ? '56px' : '44px');
	const padY = $derived(isLarge ? '14px' : '10px');

	const svgSize = $derived(isLarge ? 21 : 19);
	const svgColor = $derived(isAccent ? 'var(--g-accent-deep)' : 'var(--g-ink)');
</script>

<a
	class={className}
	{href}
	data-tone={tone}
	data-size={size}
	style:display="flex"
	style:align-items="center"
	style:gap="var(--g-s-3)"
	style:min-height={minH}
	style:padding="{padY} 14px"
	style:background="var(--g-card)"
	style:border="1px solid var(--g-rule-soft)"
	style:border-radius="var(--g-r-3)"
	style:color="var(--g-ink)"
	style:text-decoration="none"
	style:transition="border-color 150ms ease"
>
	<span
		style:display="inline-flex"
		style:align-items="center"
		style:justify-content="center"
		style:width="32px"
		style:height="32px"
		style:flex-shrink="0"
		style:border-radius="var(--g-r-2)"
		style:background={isAccent ? 'var(--g-accent-tint)' : 'var(--g-paper-deep)'}
	>
		{#if glyph === 'pause'}
		<svg width={svgSize} height={svgSize} viewBox="0 0 24 24" fill="none" stroke={svgColor} stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
			<rect x="7" y="5" width="3.4" height="14" rx="1"/>
			<rect x="13.6" y="5" width="3.4" height="14" rx="1"/>
		</svg>
		{:else if glyph === 'metrics'}
		<svg width={svgSize} height={svgSize} viewBox="0 0 24 24" fill="none" stroke={svgColor} stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
			<path d="M4 8h10M18 8h2M4 16h2M10 16h10"/>
			<circle cx="16" cy="8" r="2.2"/>
			<circle cx="8" cy="16" r="2.2"/>
		</svg>
		{:else if glyph === 'clock'}
		<svg width={svgSize} height={svgSize} viewBox="0 0 24 24" fill="none" stroke={svgColor} stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
			<circle cx="12" cy="12" r="8.5"/>
			<path d="M12 7.5V12l3 2"/>
		</svg>
		{:else if glyph === 'bell'}
		<svg width={svgSize} height={svgSize} viewBox="0 0 24 24" fill="none" stroke={svgColor} stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
			<path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6z"/>
			<path d="M10 19a2 2 0 0 0 4 0"/>
		</svg>
		{:else if glyph === 'send'}
		<svg width={svgSize} height={svgSize} viewBox="0 0 24 24" fill="none" stroke={svgColor} stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
			<path d="M21 4L3 11l6 2.5L11.5 20 21 4z"/>
			<path d="M9 13.5L21 4"/>
		</svg>
		{:else if glyph === 'eye'}
		<svg width={svgSize} height={svgSize} viewBox="0 0 24 24" fill="none" stroke={svgColor} stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
			<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/>
			<circle cx="12" cy="12" r="2.6"/>
		</svg>
		{:else}
		<!-- route (default) -->
		<svg width={svgSize} height={svgSize} viewBox="0 0 24 24" fill="none" stroke={svgColor} stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
			<circle cx="6" cy="6" r="2.2"/>
			<circle cx="18" cy="18" r="2.2"/>
			<path d="M6 8.5v3a4 4 0 0 0 4 4h0a4 4 0 0 1 4-4 4 4 0 0 0 4-4"/>
		</svg>
		{/if}
	</span>

	<span style:flex="1" style:min-width="0" style:display="flex" style:flex-direction="column" style:gap="2px">
		<span
			style:font-size="var(--g-text-sm)"
			style:font-weight="600"
			style:line-height="1.25"
			style:color="var(--g-ink)"
			style:white-space="nowrap"
			style:overflow="hidden"
			style:text-overflow="ellipsis"
		>{label}</span>
		<span
			style:font-size="var(--g-text-xs)"
			style:line-height="1.3"
			style:color="var(--g-ink-3)"
			style:white-space="nowrap"
			style:overflow="hidden"
			style:text-overflow="ellipsis"
		>{sub}</span>
	</span>

	<span
		style:font-family="var(--g-font-mono)"
		style:font-size="var(--g-text-sm)"
		style:color="var(--g-ink-3)"
		style:flex-shrink="0"
		aria-hidden="true"
	>›</span>
</a>

<style>
	a:hover {
		border-color: var(--g-accent) !important;
	}
	a:focus-visible {
		outline: 2px solid var(--g-accent);
		outline-offset: 2px;
	}
</style>
