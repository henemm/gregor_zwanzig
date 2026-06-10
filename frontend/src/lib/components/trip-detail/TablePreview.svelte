<script lang="ts">
	// Epic #138 Issue #176 — Live-Vorschau der Tabellen-Spalten basierend auf
	// aktivierten Metriken. 4 statische Beispiel-Zeilen.
	// Issue #343 — Umbau auf drei Mini-Tabellen (heute / morgen / uebermorgen),
	//              gefiltert per horizonsMap[id][day]. CSS-Grid stapelt < 1100 px.
	// Spec: docs/specs/modules/epic_138_174_178_metriken_ui.md §5
	//       docs/specs/modules/issue_343_horizon_chip_ui.md §4
	import { Eyebrow } from '$lib/components/atoms';
	import type { Horizons, MetricEntry } from '$lib/types';
	import { HORIZONS_ALL } from '$lib/types';

	type MetricCatalog = Record<string, MetricEntry[]>;
	type Day = 'today' | 'tomorrow' | 'day_after';

	interface Props {
		catalog: MetricCatalog;
		enabledMap: Record<string, boolean>;
		friendlyMap: Record<string, boolean>;
		horizonsMap: Record<string, Horizons>;
		categoryOrder: string[];
		indicatorCapable: (id: string) => boolean;
	}

	let { catalog, enabledMap, friendlyMap, horizonsMap, categoryOrder, indicatorCapable }: Props = $props();

	const DAYS: readonly Day[] = ['today', 'tomorrow', 'day_after'] as const;
	const DAY_LABEL: Record<Day, string> = {
		today: 'HEUTE',
		tomorrow: 'MORGEN',
		day_after: 'ÜBERMORGEN',
	};

	// Beispieldatenzeilen (statisch, repräsentativ für einen Tagesverlauf).
	// Pro Tag identische Sample-Stunden 09/12/15/18 (Spec §4).
	const SAMPLE_ROWS: Array<Record<string, string>> = [
		{ label: '09:00', temperature: '14°C', wind_chill: '11°C', wind: '23 km/h', gust: '38 km/h', wind_direction: 'SW', precipitation: '0,2 mm', rain_probability: '15%', thunder: 'keins', cape: 'niedrig', snowfall_limit: '2400 m', precip_type: 'Regen', cloud_total: 'teilw. bew.', cloud_low: 'klar', cloud_mid: 'klar', cloud_high: 'klar', visibility: 'gut', sunshine: 'hell', uv_index: '4', pressure: '1013 hPa', freezing_level: '3100 m', snow_depth: '0 cm', fresh_snow: '0 cm', humidity: '62%', dewpoint: '7°C' },
		{ label: '12:00', temperature: '18°C', wind_chill: '16°C', wind: '31 km/h', gust: '52 km/h', wind_direction: 'W', precipitation: '0,0 mm', rain_probability: '5%', thunder: 'keins', cape: 'niedrig', snowfall_limit: '3200 m', precip_type: '–', cloud_total: 'klar', cloud_low: 'klar', cloud_mid: 'klar', cloud_high: 'klar', visibility: 'gut', sunshine: 'hell', uv_index: '6', pressure: '1011 hPa', freezing_level: '3400 m', snow_depth: '0 cm', fresh_snow: '0 cm', humidity: '48%', dewpoint: '6°C' },
		{ label: '15:00', temperature: '16°C', wind_chill: '13°C', wind: '45 km/h', gust: '68 km/h', wind_direction: 'W', precipitation: '1,8 mm', rain_probability: '55%', thunder: 'mittel', cape: 'mittel', snowfall_limit: '2800 m', precip_type: 'Regen', cloud_total: 'bewölkt', cloud_low: 'teilw. bew.', cloud_mid: 'bewölkt', cloud_high: 'bedeckt', visibility: 'eingeschränkt', sunshine: 'wechselhaft', uv_index: '2', pressure: '1007 hPa', freezing_level: '2900 m', snow_depth: '0 cm', fresh_snow: '0 cm', humidity: '78%', dewpoint: '12°C' },
		{ label: '18:00', temperature: '12°C', wind_chill: '9°C', wind: '28 km/h', gust: '44 km/h', wind_direction: 'NW', precipitation: '4,2 mm', rain_probability: '75%', thunder: 'hoch', cape: 'hoch', snowfall_limit: '2200 m', precip_type: 'Regen', cloud_total: 'bedeckt', cloud_low: 'bewölkt', cloud_mid: 'bedeckt', cloud_high: 'bedeckt', visibility: 'schlecht', sunshine: 'bedeckt', uv_index: '1', pressure: '1003 hPa', freezing_level: '2400 m', snow_depth: '0 cm', fresh_snow: '0 cm', humidity: '88%', dewpoint: '10°C' },
	];

	function orderedCategories(): string[] {
		const cats = Object.keys(catalog);
		return categoryOrder
			.filter((c) => cats.includes(c))
			.concat(cats.filter((c) => !categoryOrder.includes(c)));
	}

	function allActiveColumns(): MetricEntry[] {
		const cols: MetricEntry[] = [];
		for (const cat of orderedCategories()) {
			for (const m of catalog[cat] ?? []) {
				if (enabledMap[m.id]) cols.push(m);
			}
		}
		return cols;
	}

	function visibleCols(day: Day): MetricEntry[] {
		return allActiveColumns().filter((m) => {
			const h = horizonsMap[m.id] ?? HORIZONS_ALL;
			return h[day];
		});
	}

	function cellValue(metricId: string, row: Record<string, string>): string {
		return row[metricId] ?? '–';
	}

	function cellMode(metricId: string): 'indicator' | 'raw' {
		if (indicatorCapable(metricId) && friendlyMap[metricId]) return 'indicator';
		return 'raw';
	}
</script>

<section data-testid="weather-metrics-table-preview" class="table-preview">
	<header class="table-preview-header">
		<h4>Tabellen-Vorschau</h4>
		<span class="hint">Beispiel-Daten · zeigt nur aktivierte Spalten pro Tag</span>
	</header>
	<div class="grid-three">
		{#each DAYS as day}
			{@const cols = visibleCols(day)}
			<div class="day-table" data-testid="table-preview-day-{day}">
				{#if cols.length === 0}
					<div class="caption-empty">
						<Eyebrow>{DAY_LABEL[day]} — 0 METRIKEN</Eyebrow>
					</div>
					<div class="empty-day">
						<p>Keine Metriken für diesen Horizont aktiviert.</p>
					</div>
				{:else}
					<div class="table-wrap">
						<table data-day={day}>
							<caption>
								<Eyebrow>{DAY_LABEL[day]} — {cols.length} METRIKEN</Eyebrow>
							</caption>
							<thead>
								<tr>
									<th class="th-time">Zeit</th>
									{#each cols as col}
										<th data-testid="table-preview-th-{day}-{col.id}">
											<div class="col-name">{col.label}</div>
											{#if col.unit}
												<div class="col-unit">{col.unit}</div>
											{/if}
											{#if indicatorCapable(col.id) && friendlyMap[col.id]}
												<span class="th-suffix">·einfach</span>
											{/if}
										</th>
									{/each}
								</tr>
							</thead>
							<tbody>
								{#each SAMPLE_ROWS as row, rowIdx}
									<tr>
										<td class="td-time">{row.label}</td>
										{#each cols as col}
											<td
												data-testid="table-preview-cell-{day}-{col.id}-{rowIdx}"
												data-mode={cellMode(col.id)}
												class:indicator-cell={cellMode(col.id) === 'indicator'}
											>{cellValue(col.id, row)}</td>
										{/each}
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
			</div>
		{/each}
	</div>
</section>

<style>
	.table-preview {
		margin-top: var(--g-s-6);
		padding: var(--g-s-4);
		border: 1px solid var(--g-ink-faint);
		border-radius: var(--g-radius-md);
		background: var(--g-surface-1);
	}
	.table-preview-header {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: var(--g-s-3);
		margin-bottom: var(--g-s-3);
	}
	.table-preview-header h4 {
		margin: 0;
		font-size: var(--g-text-md);
		font-weight: 600;
	}
	.hint {
		font-size: var(--g-text-xs);
		color: var(--g-ink-muted);
	}
	.grid-three {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
		gap: var(--g-s-6);
	}
	.day-table {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-2);
	}
	caption {
		caption-side: top;
		text-align: left;
		padding: 0 0 var(--g-s-2) 0;
	}
	.caption-empty {
		padding: 0 0 var(--g-s-1) 0;
	}
	.empty-day {
		padding: var(--g-s-3);
		border: 1px dashed var(--g-ink-faint);
		border-radius: var(--g-radius-sm);
		color: var(--g-ink-muted);
		font-size: var(--g-text-xs);
	}
	.empty-day p {
		margin: 0;
	}
	.table-wrap {
		overflow-x: auto;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: var(--g-text-xs);
	}
	th, td {
		text-align: left;
		padding: var(--g-s-1) var(--g-s-2);
		border-bottom: 1px solid var(--g-ink-faint);
		white-space: nowrap;
	}
	th {
		font-weight: 600;
		color: var(--g-ink-muted);
	}
	.col-name {
		font-weight: 600;
	}
	.col-unit {
		font-size: var(--g-text-xs);
		color: var(--g-ink-muted);
		font-weight: 400;
	}
	.th-suffix {
		font-style: italic;
		font-weight: 400;
		color: var(--g-ink-muted);
		margin-left: var(--g-s-1);
		font-size: var(--g-text-xs);
	}
	.td-time {
		font-weight: 500;
		color: var(--g-ink);
	}
	.indicator-cell {
		font-style: italic;
		color: var(--g-accent-deep);
	}
</style>
