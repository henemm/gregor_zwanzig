<script lang="ts">
	// BrandIcon — kanonisches Berg+Blitz-Bildmark.
	// 1:1 portiert aus docs/design-requests/issue_15_atomic_design/spec/brand-kit.jsx.
	// Bergkamm in --g-ink, Blitz in --g-accent. Scharfe miter-Joins (alpine Gewitter-DNA).
	interface Props {
		size?: 'sm' | 'md' | 'lg' | number;
		color?: string;
		accent?: string;
	}

	let { size = 'md', color = 'var(--g-ink)', accent = 'var(--g-accent)' }: Props = $props();

	const SIZES: Record<string, number> = { sm: 18, md: 24, lg: 32 };
	const px = $derived(typeof size === 'number' ? size : (SIZES[size] ?? SIZES.md));
	// Stroke-Width proportional zur Render-Groesse, mit Floor fuer Hairline-Schutz.
	const sw = $derived(Math.max(1.6, px / 12));
</script>

<svg
	width={px}
	height={px}
	viewBox="0 0 64 64"
	data-testid="brand-icon"
	aria-label="Gregor Zwanzig"
	style="display:inline-block;flex-shrink:0;vertical-align:middle"
>
	<!-- Blitz — Akzent-Orange, scharfe Spitzen -->
	<path d="M48 11 L41 23 L45 23 L43 29 L50 17 L46 17 Z" fill={accent} stroke-linejoin="miter" stroke-miterlimit="8" />
	<!-- Hauptkamm — vier Spitzen, miter-Joins -->
	<path d="M3 54 L18 22 L29 38 L38 26 L52 50 L61 54 Z" stroke={color} stroke-width={sw} stroke-linejoin="miter" stroke-linecap="square" stroke-miterlimit="8" fill="none" />
</svg>
