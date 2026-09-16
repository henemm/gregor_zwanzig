<script lang="ts">
	// BrandIconSquare — Square-Variante fuer Favicon, Avatar, App-Icon.
	// Dieselbe gefuellte Silhouette wie BrandIcon, nur auf einer
	// Hintergrundflaeche. 1:1 portiert aus brand-kit.jsx.
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

	const radius = $derived(bleed ? 0 : Math.max(2, size / 14));
</script>

<div
	style="width:{size}px;height:{size}px;background:{bg};color:{color};border-radius:{radius}px;position:relative;overflow:hidden;display:inline-block;flex-shrink:0"
>
	<svg viewBox="0 0 64 64" width={size} height={size} preserveAspectRatio="xMidYMid meet">
		<path d="M3 54 L18 22 L29 38 L38 26 L52 50 L61 54 Z" fill={color} />
		<g transform="translate(45.5,20) scale(1.35) translate(-45.5,-20)">
			<path d="M48 11 L41 23 L45 23 L43 29 L50 17 L46 17 Z" fill={accent} />
		</g>
	</svg>
</div>
