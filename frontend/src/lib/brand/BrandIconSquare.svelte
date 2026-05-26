<script lang="ts">
	// BrandIconSquare — Square-Variante mit Nebenkante + Horizont.
	// Fuer Favicon, Avatar, App-Icon. 1:1 portiert aus brand-kit.jsx.
	interface Props {
		size?: number;
		color?: string;
		accent?: string;
		bg?: string;
		bleed?: boolean;
	}

	let {
		size = 96,
		color = 'var(--g-ink)',
		accent = 'var(--g-accent)', // audit:exempt — Icon-Farbe (§1.4.11)
		bg = 'var(--g-paper)',
		bleed = false
	}: Props = $props();

	const showSubLine = $derived(size >= 32);
	const showHorizon = $derived(size >= 28);
	const sw = $derived(Math.max(1.4, size / 36));
	const radius = $derived(bleed ? 0 : Math.max(2, size / 14));
</script>

<div
	style="width:{size}px;height:{size}px;background:{bg};color:{color};border-radius:{radius}px;position:relative;overflow:hidden;display:inline-block;flex-shrink:0"
>
	<svg viewBox="0 0 64 64" width={size} height={size} preserveAspectRatio="xMidYMid meet">
		<path d="M48 11 L41 23 L45 23 L43 29 L50 17 L46 17 Z" fill={accent} stroke-linejoin="miter" stroke-miterlimit="8" />
		<path d="M3 54 L18 22 L29 38 L38 26 L52 50 L61 54 Z" stroke={color} stroke-width={sw} stroke-linejoin="miter" stroke-linecap="square" stroke-miterlimit="8" fill="none" />
		{#if showSubLine}
			<path d="M3 54 L18 22 L25 32" stroke={color} stroke-width={sw} stroke-linejoin="miter" stroke-linecap="square" stroke-miterlimit="8" opacity="0.45" fill="none" />
		{/if}
		{#if showHorizon}
			<line x1="3" y1="58" x2="61" y2="58" stroke={color} stroke-width="1" opacity="0.3" />
		{/if}
	</svg>
</div>
