<script lang="ts">
	// BrandIcon — kanonisches Berg+Blitz-Bildmark.
	// 1:1 portiert aus docs/design-requests/issue_15_atomic_design/spec/brand-kit.jsx.
	// Gefuellte Bergsilhouette in --g-ink, Blitz in --g-accent, 1,35x vergroessert
	// um seinen Schwerpunkt (45.5, 20). Scharfe Spitzen (alpine Gewitter-DNA).
	interface Props {
		size?: 'sm' | 'md' | 'lg' | number;
		color?: string;
		accent?: string;
	}

	let { size = 'md', color = 'var(--g-ink)', accent = 'var(--g-accent)' }: Props = $props(); // audit:exempt — Icon-Farbe (§1.4.11)

	const SIZES: Record<string, number> = { sm: 18, md: 24, lg: 32 };
	const px = $derived(typeof size === 'number' ? size : (SIZES[size] ?? SIZES.md));
</script>

<svg
	width={px}
	height={px}
	viewBox="0 0 64 64"
	data-testid="brand-icon"
	aria-label="Gregor Zwanzig"
	style="display:inline-block;flex-shrink:0;vertical-align:middle"
>
	<!-- Hauptkamm — gefuellte Silhouette, vier Spitzen -->
	<path d="M3 54 L18 22 L29 38 L38 26 L52 50 L61 54 Z" fill={color} />
	<!-- Blitz — Akzent-Orange, ueber der Silhouette, 1,35x -->
	<g transform="translate(45.5,20) scale(1.35) translate(-45.5,-20)">
		<path d="M48 11 L41 23 L45 23 L43 29 L50 17 L46 17 Z" fill={accent} />
	</g>
</svg>
