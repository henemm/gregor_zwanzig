<script lang="ts">
	// Epic #135 Step 4 (Issue #157) — Stage-Detail-Row.
	// Spec: docs/specs/modules/epic_135_step4_left_column.md §5.
	//
	// Native <button> mit onclick={onSelect} — Safari-tauglich, da onSelect
	// bereits in StageList pro Stage gebunden wird.

	import type { Stage, StageWeatherResult } from '$lib/types';
	import { computeHeaderStats } from '$lib/components/email-preview/headerStats';
	import { Pill } from '$lib/components/ui/pill';
	import { WIcon } from '$lib/components/ui/wicon/index.js';
	import { wmoToWIconKind } from '$lib/utils/weatherUtils.js';

	interface Props {
		stage: Stage;
		index: number;
		code: string;
		selected: boolean;
		active: boolean;
		onSelect: () => void;
		now?: Date;
		weatherData?: StageWeatherResult | null;
	}

	let {
		stage,
		index: _index, // wird derzeit nicht im Markup gebraucht, Spec-Kontrakt
		code,
		selected,
		active,
		onSelect,
		now: _now = new Date(),
		weatherData = null
	}: Props = $props();

	const riskTone = $derived(
		weatherData?.risk === 'green'
			? ('success' as const)
			: weatherData?.risk === 'yellow'
				? ('warning' as const)
				: weatherData?.risk === 'red'
					? ('danger' as const)
					: null
	);

	const riskLabel = $derived(
		weatherData?.risk === 'green'
			? 'Gering'
			: weatherData?.risk === 'yellow'
				? 'Mittel'
				: weatherData?.risk === 'red'
					? 'Hoch'
					: null
	);

	const stats = $derived(computeHeaderStats(stage));
	const wptCount = $derived(stage.waypoints?.length ?? 0);

	// Lokaler Date-Helper — deutsches Kurzformat "DD.MM."
	function formatDate(iso: string | undefined | null): string {
		if (!iso) return '';
		const clean = iso.split('T')[0];
		const parts = clean.split('-');
		if (parts.length < 3) return '';
		const [, m, d] = parts;
		return `${d}.${m}.`;
	}

	const dateLabel = $derived(formatDate(stage.date));
</script>

<button
	type="button"
	data-testid="trip-stage-row-{stage.id}"
	data-selected={selected ? 'true' : 'false'}
	data-active={active ? 'true' : 'false'}
	class="g-card stage-row"
	onclick={onSelect}
>
	<header class="stage-row-header">
		<Pill
			tone={active ? 'accent' : 'default'}
			data-testid="trip-stage-row-code-{stage.id}"
			class="stage-code-pill"
		>
			{code}
		</Pill>
		<span class="eyebrow">{dateLabel}</span>
		{#if riskTone && riskLabel}
			<Pill
				tone={riskTone}
				data-testid="trip-stage-row-risk-{stage.id}"
				class="risk-pill"
			>
				{riskLabel}
			</Pill>
		{/if}
	</header>

	<h3 class="stage-row-title">{stage.name}</h3>

	<dl class="stat-strip">
		<div>
			<dt class="eyebrow">Distanz</dt>
			<dd>{stats.distanceKm.toFixed(1)} km</dd>
		</div>
		<div>
			<dt class="eyebrow">Aufstieg</dt>
			<dd>{stats.ascentM} Hm</dd>
		</div>
		<div>
			<dt class="eyebrow">Abstieg</dt>
			<dd>{stats.descentM} Hm</dd>
		</div>
		<div>
			<dt class="eyebrow">Wegpunkte</dt>
			<dd>{wptCount}</dd>
		</div>
	</dl>

	{#if weatherData?.weather_summary}
		{@const ws = weatherData.weather_summary}
		<div class="weather-strip" data-testid="trip-stage-row-weather-{stage.id}">
			<WIcon kind={wmoToWIconKind(ws.wmo_code, ws.is_day)} size={18} />
			{#if ws.temp_min_c != null && ws.temp_max_c != null}
				<span class="eyebrow">{Math.round(ws.temp_min_c)}–{Math.round(ws.temp_max_c)} °C</span>
			{/if}
			{#if ws.wind_max_kmh != null}
				<span class="eyebrow">Wind {Math.round(ws.wind_max_kmh)} km/h</span>
			{/if}
			{#if ws.precip_mm != null && ws.precip_mm > 0}
				<span class="eyebrow">{ws.precip_mm.toFixed(1)} mm</span>
			{/if}
		</div>
	{/if}
</button>

<style>
	.stage-row {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		width: 100%;
		text-align: left;
		padding: 0.75rem 1rem;
		border-radius: 0.5rem;
		background: var(--g-surface-1, transparent);
		border: 1px solid var(--g-ink-faint);
		cursor: pointer;
	}
	.stage-row[data-selected='true'] {
		border-color: var(--g-accent);
		box-shadow: 0 0 0 1px var(--g-accent);
	}
	.stage-row-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.stage-row-header :global(.risk-pill) {
		margin-left: auto;
	}
	.weather-strip {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
		padding-top: 0.25rem;
	}
	.stage-row-title {
		font-size: 1rem;
		font-weight: 600;
		line-height: 1.2;
		margin: 0;
	}
	.eyebrow {
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: 0.6875rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--g-ink-muted);
	}
	.stat-strip {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 0.5rem;
		margin: 0;
	}
	.stat-strip > div {
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
	}
	.stat-strip dt {
		margin: 0;
	}
	.stat-strip dd {
		margin: 0;
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--g-ink, inherit);
	}
	:global(.stage-code-pill) {
		display: inline-block;
		padding: 0.125rem 0.5rem;
		border-radius: 9999px;
		background: var(--g-surface-2, rgba(0, 0, 0, 0.05));
		font-size: 0.75rem;
		font-weight: 600;
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
	}
	:global(.stage-code-pill[data-tone='accent']) {
		background: var(--g-accent);
		color: white;
	}
</style>
