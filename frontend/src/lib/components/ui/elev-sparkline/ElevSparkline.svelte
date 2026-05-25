<script lang="ts">
	interface Props {
		data: number[];
		width?: number;
		height?: number;
		active?: boolean;
		// Issue #371: optionale stroke/fill/showArea-Props (additiv).
		// Defaults erhalten das bestehende Verhalten (currentColor, keine Flaeche).
		stroke?: string;
		fill?: string;
		showArea?: boolean;
	}

	let {
		data,
		width = 120,
		height = 24,
		active = false,
		stroke = 'currentColor',
		fill = 'rgba(196,90,42,0.10)',
		showArea = false
	}: Props = $props();

	const padding = 2;

	let polyline = $derived(
		(() => {
			const finite = data.filter((v) => Number.isFinite(v));
			if (finite.length === 0) return '';
			const min = Math.min(...finite);
			const max = Math.max(...finite);
			const range = max - min || 1;
			return finite
				.map((v, i) => {
					const x = (i / Math.max(finite.length - 1, 1)) * width;
					const y =
						max === min
							? height / 2
							: padding + ((max - v) / range) * (height - 2 * padding);
					return `${x},${y}`;
				})
				.join(' ');
		})()
	);

	// Issue #371: Flaeche schliesst Polyline-Punkte nach unten zur Baseline.
	let areaPoints = $derived(polyline ? `${polyline} ${width},${height} 0,${height}` : '');
</script>

<svg
	data-slot="elev-sparkline"
	data-active={active}
	{width}
	{height}
	viewBox="0 0 {width} {height}"
	aria-hidden="true"
>
	{#if polyline}
		{#if showArea}
			<polygon points={areaPoints} fill={fill} stroke="none" />
		{/if}
		<polyline
			points={polyline}
			fill="none"
			stroke={stroke}
			stroke-width="1.5"
			stroke-linejoin="round"
			stroke-linecap="round"
		/>
	{/if}
</svg>
