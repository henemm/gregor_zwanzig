<script lang="ts">
	// Epic #138 Issue #176 — Live-Vorschau der Tabellen-Spalten basierend auf
	// aktivierten Metriken. 4 statische Beispiel-Zeilen.
	// Spec: docs/specs/modules/epic_138_174_178_metriken_ui.md §5

	interface MetricEntry {
		id: string;
		label: string;
		unit: string;
		category: string;
		default_enabled: boolean;
		has_friendly_format: boolean;
	}
	type MetricCatalog = Record<string, MetricEntry[]>;

	interface Props {
		catalog: MetricCatalog;
		enabledMap: Record<string, boolean>;
		friendlyMap: Record<string, boolean>;
		categoryOrder: string[];
		indicatorCapable: (id: string) => boolean;
	}

	let { catalog, enabledMap, friendlyMap, categoryOrder, indicatorCapable }: Props = $props();

	// Beispieldatenzeilen (statisch, repräsentativ für einen Tagesverlauf)
	const SAMPLE_ROWS: Array<Record<string, string>> = [
		{ label: 'Mo 09:00', temperature: '14°C', wind_chill: '11°C', wind: '23 km/h', gust: '38 km/h', wind_direction: 'SW', precipitation: '0,2 mm', rain_probability: '15%', thunder: 'keins', cape: 'niedrig', snowfall_limit: '2400 m', precip_type: 'Regen', cloud_total: 'teilw. bew.', cloud_low: 'klar', cloud_mid: 'klar', cloud_high: 'klar', visibility: 'gut', sunshine: 'hell', uv_index: '4', pressure: '1013 hPa', freezing_level: '3100 m', snow_depth: '0 cm', fresh_snow: '0 cm', humidity: '62%', dewpoint: '7°C', confidence: '87%' },
		{ label: 'Mo 12:00', temperature: '18°C', wind_chill: '16°C', wind: '31 km/h', gust: '52 km/h', wind_direction: 'W', precipitation: '0,0 mm', rain_probability: '5%', thunder: 'keins', cape: 'niedrig', snowfall_limit: '3200 m', precip_type: '–', cloud_total: 'klar', cloud_low: 'klar', cloud_mid: 'klar', cloud_high: 'klar', visibility: 'gut', sunshine: 'hell', uv_index: '6', pressure: '1011 hPa', freezing_level: '3400 m', snow_depth: '0 cm', fresh_snow: '0 cm', humidity: '48%', dewpoint: '6°C', confidence: '91%' },
		{ label: 'Mo 15:00', temperature: '16°C', wind_chill: '13°C', wind: '45 km/h', gust: '68 km/h', wind_direction: 'W', precipitation: '1,8 mm', rain_probability: '55%', thunder: 'mittel', cape: 'mittel', snowfall_limit: '2800 m', precip_type: 'Regen', cloud_total: 'bewölkt', cloud_low: 'teilw. bew.', cloud_mid: 'bewölkt', cloud_high: 'bedeckt', visibility: 'eingeschränkt', sunshine: 'wechselhaft', uv_index: '2', pressure: '1007 hPa', freezing_level: '2900 m', snow_depth: '0 cm', fresh_snow: '0 cm', humidity: '78%', dewpoint: '12°C', confidence: '74%' },
		{ label: 'Mo 18:00', temperature: '12°C', wind_chill: '9°C', wind: '28 km/h', gust: '44 km/h', wind_direction: 'NW', precipitation: '4,2 mm', rain_probability: '75%', thunder: 'hoch', cape: 'hoch', snowfall_limit: '2200 m', precip_type: 'Regen', cloud_total: 'bedeckt', cloud_low: 'bewölkt', cloud_mid: 'bedeckt', cloud_high: 'bedeckt', visibility: 'schlecht', sunshine: 'bedeckt', uv_index: '1', pressure: '1003 hPa', freezing_level: '2400 m', snow_depth: '0 cm', fresh_snow: '0 cm', humidity: '88%', dewpoint: '10°C', confidence: '68%' },
	];

	// Aktive Metriken in CATEGORY_ORDER-Reihenfolge
	const activeColumns = $derived.by(() => {
		const cols: MetricEntry[] = [];
		const cats = Object.keys(catalog);
		const order = categoryOrder.filter((c) => cats.includes(c)).concat(
			cats.filter((c) => !categoryOrder.includes(c))
		);
		for (const cat of order) {
			for (const m of catalog[cat] ?? []) {
				if (enabledMap[m.id]) cols.push(m);
			}
		}
		return cols;
	});

	function cellValue(metricId: string, row: Record<string, string>): string {
		return row[metricId] ?? '–';
	}

	function cellMode(metricId: string): 'indicator' | 'raw' {
		if (indicatorCapable(metricId) && friendlyMap[metricId]) return 'indicator';
		return 'raw';
	}
</script>

<div data-testid="weather-metrics-table-preview" class="table-preview">
	<div class="table-preview-header">
		<h4>Tabellen-Vorschau</h4>
		<span class="hint">Beispiel-Daten · zeigt nur aktivierte Spalten</span>
	</div>
	<div class="table-wrap">
		<table>
			<thead>
				<tr>
					<th class="th-time">Zeit</th>
					{#each activeColumns as col}
						<th data-testid="table-preview-th-{col.id}">
							{col.label}
							{#if indicatorCapable(col.id) && friendlyMap[col.id]}
								<span class="th-suffix">·skala</span>
							{/if}
						</th>
					{/each}
				</tr>
			</thead>
			<tbody>
				{#each SAMPLE_ROWS as row, rowIdx}
					<tr>
						<td class="td-time">{row.label}</td>
						{#each activeColumns as col}
							<td
								data-testid="table-preview-cell-{col.id}-{rowIdx}"
								data-mode={cellMode(col.id)}
								class:indicator-cell={cellMode(col.id) === 'indicator'}
							>{cellValue(col.id, row)}</td>
						{/each}
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</div>

<style>
	.table-preview {
		margin-top: 1.5rem;
		padding: 1rem;
		border: 1px solid var(--g-border, #ddd);
		border-radius: 6px;
		background: var(--g-surface-alt, #fafafa);
	}
	.table-preview-header {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 0.75rem;
		margin-bottom: 0.75rem;
	}
	.table-preview-header h4 {
		margin: 0;
		font-size: 0.9375rem;
		font-weight: 600;
	}
	.hint {
		font-size: 0.75rem;
		color: var(--g-ink-faint, #888);
	}
	.table-wrap {
		overflow-x: auto;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.8125rem;
	}
	th, td {
		text-align: left;
		padding: 0.35rem 0.5rem;
		border-bottom: 1px solid var(--g-border, #eee);
		white-space: nowrap;
	}
	th {
		font-weight: 600;
		color: var(--g-ink-faint, #555);
	}
	.th-suffix {
		font-style: italic;
		font-weight: 400;
		color: var(--g-ink-faint, #888);
		margin-left: 0.25rem;
		font-size: 0.7rem;
	}
	.td-time {
		font-weight: 500;
		color: var(--g-ink, #333);
	}
	.indicator-cell {
		font-style: italic;
		color: var(--g-accent, #c45a2a);
	}
</style>
