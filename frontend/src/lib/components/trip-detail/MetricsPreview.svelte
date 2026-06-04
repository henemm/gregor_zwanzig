<script lang="ts">
	import type { Trip } from '$lib/types';

	interface Props {
		trip: Trip;
	}
	let { trip }: Props = $props();

	const ALL_METRICS = [
		'temp', 'feels_like', 'humidity', 'wind_speed', 'wind_gust', 'wind_dir',
		'rain', 'rain_prob', 'thunder', 'cape', 'snowfall', 'precip_type',
		'cloud_cover', 'low_clouds', 'mid_clouds', 'high_clouds', 'visibility',
		'sunshine', 'uv', 'pressure', 'freezing_level', 'snow_depth', 'fresh_snow',
		'soil_temp', 'radiation'
	];

	const activeMetrics = $derived.by(() => {
		const config = trip.display_config;
		if (!config) return new Set<string>();
		const metrics = config.metrics ?? [];
		return new Set(
			(metrics as Array<{ metric_id?: string; enabled?: boolean }>)
				.filter((m) => m.enabled !== false && m.metric_id)
				.map((m) => m.metric_id as string)
		);
	});

	const presetName = $derived(trip.display_config?.preset_name);
	const activeCount = $derived(activeMetrics.size);
</script>

<div style="display: flex; flex-wrap: wrap; gap: 6px; padding: 4px 0;">
	{#each ALL_METRICS as metric}
		{@const isActive = activeMetrics.has(metric)}
		<span
			style="
				font-size: 11px;
				font-family: var(--g-font-mono, ui-monospace, monospace);
				padding: 3px 8px;
				border-radius: 3px;
				{isActive
					? 'background: var(--g-ink); color: var(--g-paper);'
					: 'background: transparent; border: 1px solid var(--g-rule); color: var(--g-ink-4); opacity: 0.6;'}
			"
		>{metric}</span>
	{/each}
</div>
{#if activeCount > 0 || presetName}
	<div style="font-size: 12px; color: var(--g-ink-3); margin-top: 8px;">
		{activeCount} aktiv{#if presetName} · {presetName}{/if}
	</div>
{/if}
