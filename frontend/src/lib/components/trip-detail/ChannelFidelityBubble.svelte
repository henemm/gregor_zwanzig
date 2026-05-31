<script lang="ts">
	// Issue #496 — Schicht 2 (Telegram/Signal): Chat-Bubble in Original-Breite.
	// Mono-Tabelle bis Spalten-Limit, Rest in Detail-Zeile. Status-Banner
	// (ok/warn) erklaert die Konsequenz.
	import { applyChannel, CHANNEL_COL_BUDGET, type MetricEntry } from './metricsEditor.ts';

	interface Props {
		channelId: 'telegram' | 'signal';
		primary: string[];
		secondary: string[];
		metricById: Record<string, MetricEntry>;
		shortById: Record<string, string>;
	}
	let { channelId, primary, secondary, metricById, shortById }: Props = $props();

	const SAMPLE_BY_ID: Record<string, string> = {
		temperature: '11,6', wind_chill: '8', humidity: '78', dewpoint: '4',
		wind: '12', gust: '30', wind_direction: 'NO',
		precipitation: '0', rain_probability: '53', thunder: '0', cape: '0',
		snowfall_limit: '2400', precip_type: '—',
		cloud_total: '80', cloud_low: '30', cloud_mid: '45', cloud_high: '70',
		visibility: 'gut', sunshine: '35', uv_index: '3', pressure: '1018',
		freezing_level: '2400', snow_depth: '0', fresh_snow: '0', confidence: '85',
	};
	const SAMPLE_HOURS: Record<string, [string, string, string]> = {
		temperature: ['8,2', '11,0', '9,9'],
		wind_chill:  ['7,1', '8,1', '8,4'],
		wind:        ['5',   '12',  '4'],
		gust:        ['12',  '24',  '11'],
		rain_probability: ['8', '53', '63'],
		precipitation:    ['0', '3,2', '0,2'],
		thunder:     ['0',   '5',   '0'],
		cloud_total: ['70',  '95',  '85'],
		visibility:  ['1,2', '3,5', '2,4'],
		uv_index:    ['0,4', '2,0', '2,4'],
		humidity:    ['78',  '88',  '83'],
		wind_direction: ['NE', 'SE', 'NE'],
		freezing_level: ['2.310', '2.530', '2.450'],
		dewpoint:    ['4',   '6',   '5'],
	};
	const HOURS = ['08', '12', '15'];

	const bubbleW = $derived(channelId === 'signal' ? 272 : 330);
	const accent = $derived(channelId === 'signal' ? '#3a76f0' : '#2aabee');
	const maxCols = $derived(CHANNEL_COL_BUDGET[channelId]);
	const channelLabel = $derived(channelId === 'signal' ? 'Signal' : 'Telegram');

	const layout = $derived(applyChannel(primary, secondary, maxCols));

	function shortOf(id: string): string {
		return shortById[id] ?? metricById[id]?.label.slice(0, 5) ?? id.slice(0, 5);
	}
	function labelOf(id: string): string {
		return metricById[id]?.label ?? id;
	}
	function sampleFor(id: string, hi: number): string {
		const arr = SAMPLE_HOURS[id];
		if (arr) return arr[hi];
		return SAMPLE_BY_ID[id] ?? '—';
	}

	const headLine = $derived(
		'h     ' + layout.inTable.map((id) => shortOf(id).slice(0, 5).padEnd(6, ' ')).join(''),
	);
	const dataLines = $derived(
		HOURS.map((h, hi) =>
			h.padEnd(6, ' ') + layout.inTable.map((id) => sampleFor(id, hi).slice(0, 5).padEnd(6, ' ')).join(''),
		),
	);
	const detailIds = $derived(layout.detail);
</script>

<div class="fidelity" data-testid="channel-fidelity-{channelId}">
	<div class="chat">
		<div class="bubble" style:max-width="{bubbleW}px" style:border-left-color={accent}>
			<div class="meta">
				<span class="avatar" style:background={accent} aria-hidden="true">
					{channelId === 'signal' ? '▲' : '✈'}
				</span>
				<span class="sender">Gregor Zwanzig</span>
			</div>
			<div class="title mono">KHW 03 · Morgen 06:00</div>
			<pre class="mono mini-table">{headLine}
{dataLines.join('\n')}</pre>
			{#if detailIds.length > 0}
				<div class="detail-row">
					<span class="detail-eyebrow mono">DETAIL</span>
					{detailIds.map((id) => `${labelOf(id)} ${SAMPLE_BY_ID[id] ?? '—'}`).join(' · ')}
				</div>
			{/if}
			<div class="ts mono">06:00 ✓✓</div>
		</div>
	</div>

	{#if layout.demoted > 0}
		<div class="banner warn">
			<strong>{layout.demoted} {layout.demoted === 1 ? 'Spalte rutscht' : 'Spalten rutschen'} in die Detail-Zeile:</strong>
			{primary.slice(maxCols).map((id) => labelOf(id)).join(', ')}.
			Die ersten {maxCols} bleiben Tabelle.
		</div>
	{:else}
		<div class="banner ok">
			Alle {primary.length} Spalten passen in das {channelLabel}-Limit ({maxCols}). Nichts rutscht.
		</div>
	{/if}
</div>

<style>
	.fidelity {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-3);
	}
	.chat {
		background: #e9e6dc;
		border-radius: var(--g-r-3, 16px);
		padding: var(--g-s-4);
		display: flex;
	}
	.bubble {
		background: #fff;
		border-radius: 4px 14px 14px 14px;
		border-left: 3px solid;
		padding: var(--g-s-3);
		display: flex;
		flex-direction: column;
		gap: 6px;
		color: var(--g-ink);
	}
	.meta {
		display: flex;
		align-items: center;
		gap: 6px;
		font-size: var(--g-text-xs);
		color: var(--g-ink-muted);
	}
	.avatar {
		width: 18px;
		height: 18px;
		border-radius: 50%;
		color: #fff;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 10px;
	}
	.sender {
		font-weight: 600;
		color: var(--g-ink);
	}
	.title {
		font-size: var(--g-text-xs);
		font-weight: 700;
	}
	.mini-table {
		background: #f6f4ee;
		padding: 6px 8px;
		border-radius: 6px;
		font-size: 10px;
		line-height: 1.5;
		overflow-x: auto;
		white-space: pre;
		margin: 0;
		color: var(--g-ink);
	}
	.detail-row {
		font-size: 10px;
		color: var(--g-ink-muted);
		line-height: 1.5;
		font-style: italic;
	}
	.detail-eyebrow {
		font-size: 9px;
		font-style: normal;
		text-transform: uppercase;
		letter-spacing: var(--g-track-caps);
		font-weight: 600;
		margin-right: 4px;
		color: var(--g-ink);
	}
	.ts {
		font-size: 10px;
		color: var(--g-ink-muted);
		align-self: flex-end;
	}
	.banner {
		padding: var(--g-s-2) var(--g-s-3);
		border-radius: var(--g-radius-sm);
		font-size: var(--g-text-xs);
		line-height: 1.5;
	}
	.banner.warn {
		background: color-mix(in srgb, var(--g-warning) 10%, transparent);
		border-left: 3px solid var(--g-warning);
		color: var(--g-ink);
	}
	.banner.ok {
		background: color-mix(in srgb, var(--g-success, #2f7d4f) 10%, transparent);
		border-left: 3px solid var(--g-success, #2f7d4f);
		color: var(--g-ink);
	}
</style>
