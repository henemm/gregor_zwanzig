<script lang="ts">
	// Issue #496 — Schicht 2 (Email): "echte" Vorschau in Original-Breite.
	// Desktop-Mail (HTML-Tabelle) und iPhone-Mail (gestapelt) per Pill-Tab.
	// Werte sind feste Beispiel-Hours (SAMPLE_HOURS), kein Live-Wetter.
	import type { MetricEntry } from './metricsEditor.ts';

	interface Props {
		primary: string[];
		secondary: string[];
		metricById: Record<string, MetricEntry>;
		shortById: Record<string, string>;
		mobile?: boolean;
	}
	let { primary, secondary, metricById, shortById, mobile = false }: Props = $props();

	// View-State: Anfangswert haengt von `mobile`-Prop ab; danach steuert der
	// Tab-Toggle. Svelte warnt hier vor "state_referenced_locally" — bewusst
	// in Kauf genommen: die Prop wird wirklich nur einmal zur Initialisierung
	// gelesen.
	// svelte-ignore state_referenced_locally
	let view = $state<'desktop' | 'iphone'>(mobile ? 'iphone' : 'desktop');

	const SAMPLE_BY_ID: Record<string, string> = {
		temperature: '11,6', wind_chill: '8', humidity: '78', dewpoint: '4',
		wind: '12', gust: '30', wind_direction: 'NO',
		precipitation: '0', rain_probability: '53', thunder: '0', cape: '0',
		snowfall_limit: '2400', precip_type: '—',
		cloud_total: '80', cloud_low: '30', cloud_mid: '45', cloud_high: '70',
		visibility: 'gut', sunshine: '35', uv_index: '3', pressure: '1018',
		freezing_level: '2400', snow_depth: '0', fresh_snow: '0',
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
</script>

<div class="fidelity" data-testid="channel-fidelity-email">
	<div class="tabs" role="tablist" aria-label="Mail-Ansicht">
		<button
			type="button"
			class="tab"
			class:active={view === 'desktop'}
			role="tab"
			aria-selected={view === 'desktop'}
			onclick={() => (view = 'desktop')}
		>Desktop-Mail</button>
		<button
			type="button"
			class="tab"
			class:active={view === 'iphone'}
			role="tab"
			aria-selected={view === 'iphone'}
			onclick={() => (view = 'iphone')}
		>iPhone-Mail</button>
	</div>

	{#if view === 'desktop'}
		<div class="mail-frame">
			<div class="chrome">
				<span class="chrome-l mono">MORGEN-BRIEFING</span>
				<span class="chrome-r mono">GREGOR ZWANZIG · EMAIL</span>
			</div>
			<div class="table-wrap">
				<table class="mail-table mono">
					<thead>
						<tr>
							<th>h</th>
							{#each primary as id}
								<th>{shortOf(id)}</th>
							{/each}
						</tr>
					</thead>
					<tbody>
						{#each HOURS as h, hi}
							<tr>
								<td class="hcol">{h}</td>
								{#each primary as id}
									<td>{sampleFor(id, hi)}</td>
								{/each}
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			{#if secondary.length > 0}
				<div class="detail-row">
					<span class="detail-eyebrow mono">DETAIL</span>
					{secondary.map((id) => `${labelOf(id)} ${SAMPLE_BY_ID[id] ?? '—'}`).join(' · ')}
				</div>
			{/if}
			<div class="footer-ok mono">
				✓ Email zeigt alle {primary.length} Spalten — nichts rutscht weg.
			</div>
		</div>
	{:else}
		<div class="iphone-row">
			<div class="iphone">
				<div class="status-bar mono">
					<span>06:01</span>
					<span>● ● ●</span>
				</div>
				<div class="iphone-screen">
					<div class="chrome">
						<span class="chrome-l mono">MORGEN-BRIEFING</span>
						<span class="chrome-r mono">EMAIL</span>
					</div>
					<div class="hours-stack">
						{#each HOURS as h, hi}
							<div class="hour-block">
								<div class="hour mono">{h}:00</div>
								<div class="pairs">
									{#each primary as id}
										<span class="pair mono">
											<span class="pair-label">{shortOf(id)}</span>
											<span class="pair-val">{sampleFor(id, hi)}</span>
										</span>
									{/each}
								</div>
							</div>
						{/each}
					</div>
				</div>
			</div>
			<div class="iphone-note">
				<p>
					Am iPhone rendert die Mail gestapelt — jede Stunde als eigener Block
					mit allen Werten inline. Auch viele Spalten bleiben lesbar.
				</p>
			</div>
		</div>
	{/if}
</div>

<style>
	.fidelity {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-3);
	}
	.tabs {
		display: flex;
		gap: var(--g-s-1);
	}
	.tab {
		font-family: inherit;
		font-size: var(--g-text-xs);
		padding: 4px 10px;
		border-radius: var(--g-radius-pill);
		border: 1px solid var(--g-rule-soft);
		background: transparent;
		color: var(--g-ink-muted);
		cursor: pointer;
		transition: background 120ms, color 120ms, border-color 120ms;
	}
	.tab:hover {
		background: var(--g-card);
	}
	.tab.active {
		background: var(--g-ink);
		color: var(--g-paper);
		border-color: var(--g-ink);
	}

	.mail-frame {
		border: 1px solid var(--g-rule-soft);
		border-radius: var(--g-radius-sm);
		background: var(--g-card);
		overflow: hidden;
	}
	.chrome {
		display: flex;
		justify-content: space-between;
		padding: var(--g-s-2) var(--g-s-3);
		background: var(--g-card-alt);
		border-bottom: 1px solid var(--g-rule-soft);
		font-size: 10px;
		letter-spacing: var(--g-track-caps);
		text-transform: uppercase;
		color: var(--g-ink-muted);
	}
	.table-wrap {
		overflow-x: auto;
		padding: var(--g-s-3);
	}
	.mail-table {
		font-size: var(--g-text-xs);
		border-collapse: collapse;
		font-variant-numeric: tabular-nums;
		min-width: 100%;
	}
	.mail-table th, .mail-table td {
		padding: 4px 8px;
		text-align: right;
		border-bottom: 1px solid var(--g-rule-soft);
		white-space: nowrap;
	}
	.mail-table th {
		color: var(--g-ink-muted);
		font-weight: 600;
		text-transform: lowercase;
	}
	.mail-table td.hcol, .mail-table th:first-child {
		text-align: left;
		color: var(--g-ink-muted);
	}
	.detail-row {
		padding: var(--g-s-2) var(--g-s-3);
		border-top: 1px dashed var(--g-rule-soft);
		font-size: var(--g-text-xs);
		color: var(--g-ink-muted);
		font-style: italic;
		line-height: 1.5;
	}
	.detail-eyebrow {
		font-size: 9px;
		font-style: normal;
		text-transform: uppercase;
		letter-spacing: var(--g-track-caps);
		margin-right: var(--g-s-1);
		color: var(--g-ink-muted);
	}
	.footer-ok {
		padding: var(--g-s-2) var(--g-s-3);
		border-top: 1px solid var(--g-rule-soft);
		background: color-mix(in srgb, var(--g-success, #2f7d4f) 8%, transparent);
		font-size: var(--g-text-xs);
		color: var(--g-success, #2f7d4f);
		font-weight: 600;
	}

	.iphone-row {
		display: flex;
		gap: var(--g-s-4);
		align-items: flex-start;
		flex-wrap: wrap;
	}
	.iphone {
		width: 300px;
		background: #1c1c1e;
		border-radius: 30px;
		padding: 9px;
		flex-shrink: 0;
	}
	.status-bar {
		display: flex;
		justify-content: space-between;
		padding: 4px 14px 6px;
		font-size: 10px;
		color: #fff;
	}
	.iphone-screen {
		background: #fff;
		border-radius: 24px;
		overflow: hidden;
	}
	.hours-stack {
		padding: var(--g-s-2);
		display: flex;
		flex-direction: column;
		gap: var(--g-s-2);
	}
	.hour-block {
		padding: var(--g-s-2);
		border-bottom: 1px solid var(--g-rule-soft);
	}
	.hour-block:last-child {
		border-bottom: 0;
	}
	.hour {
		font-weight: 700;
		font-size: var(--g-text-sm);
		margin-bottom: 4px;
		color: var(--g-ink);
	}
	.pairs {
		display: flex;
		flex-wrap: wrap;
		gap: 6px 10px;
		font-size: 11px;
		color: var(--g-ink);
	}
	.pair {
		display: inline-flex;
		gap: 4px;
	}
	.pair-label {
		color: var(--g-ink-muted);
	}
	.pair-val {
		font-weight: 600;
		font-variant-numeric: tabular-nums;
	}
	.iphone-note {
		max-width: 280px;
		font-size: var(--g-text-xs);
		color: var(--g-ink-muted);
		line-height: 1.6;
	}
</style>
