<script lang="ts">
	// Issue #251 — CompareMatrix: Vergleichsmatrix mit Best-Value-Markierung und Mini-Bars.
	//
	// Spec: docs/specs/modules/issue_251_compare_main_stage.md §4

	import type { ActivityProfile, CompareMetrics, CompareRow, Location } from '$lib/types.js';
	import { toCompareProfile } from '$lib/types.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import * as Table from '$lib/components/ui/table/index.js';

	interface Props {
		rows: CompareRow[];
		locations: Location[];
		profile: ActivityProfile;
	}

	let { rows, locations, profile }: Props = $props();

	type MetricDef = {
		label: string;
		key: keyof CompareMetrics;
		higherIsBetter: boolean;
		unit: string;
		decimals: number;
	};

	const PROFILE_METRICS: Record<string, MetricDef[]> = {
		WINTERSPORT: [
			{ label: 'Schneehöhe',    key: 'snow_depth_cm',    higherIsBetter: true,  unit: 'cm',   decimals: 0 },
			{ label: 'Neuschnee',     key: 'snow_new_sum_cm',  higherIsBetter: true,  unit: 'cm',   decimals: 1 },
			{ label: 'Sonnenstunden', key: 'sunny_hours_h',     higherIsBetter: true,  unit: 'h',    decimals: 1 },
			{ label: 'Wind max.',     key: 'wind_max_kmh',     higherIsBetter: false, unit: 'km/h', decimals: 0 },
			{ label: 'Bewölkung',     key: 'cloud_avg_pct',    higherIsBetter: false, unit: '%',    decimals: 0 },
		],
		ALPINE_TOURING: [
			{ label: 'Neuschnee',  key: 'snow_new_sum_cm',  higherIsBetter: true,  unit: 'cm',   decimals: 1 },
			{ label: 'Sicht min.', key: 'visibility_min_m', higherIsBetter: true,  unit: 'm',    decimals: 0 },
			{ label: 'Wind max.',  key: 'wind_max_kmh',     higherIsBetter: false, unit: 'km/h', decimals: 0 },
		],
		SUMMER_TREKKING: [
			{ label: 'Niederschlag', key: 'precip_sum_mm',     higherIsBetter: false, unit: 'mm',   decimals: 1 },
			{ label: 'Gewitter',     key: 'thunder_level_max', higherIsBetter: false, unit: '',     decimals: 0 },
			{ label: 'Wind max.',    key: 'wind_max_kmh',      higherIsBetter: false, unit: 'km/h', decimals: 0 },
			{ label: 'UV-Index',     key: 'uv_index_max',      higherIsBetter: false, unit: '',     decimals: 1 },
			{ label: 'Sicht min.',   key: 'visibility_min_m',  higherIsBetter: true,  unit: 'm',    decimals: 0 },
		],
		ALLGEMEIN: [
			{ label: 'Temp. max.',   key: 'temp_max_c',       higherIsBetter: true,  unit: '°C',   decimals: 1 },
			{ label: 'Wind max.',    key: 'wind_max_kmh',     higherIsBetter: false, unit: 'km/h', decimals: 0 },
			{ label: 'Niederschlag', key: 'precip_sum_mm',    higherIsBetter: false, unit: 'mm',   decimals: 1 },
			{ label: 'Sicht min.',   key: 'visibility_min_m', higherIsBetter: true,  unit: 'm',    decimals: 0 },
		],
	};

	const THUNDER_MAP: Record<string, number> = { NONE: 0, MED: 1, HIGH: 2 };

	let metrics = $derived(PROFILE_METRICS[toCompareProfile(profile)] ?? PROFILE_METRICS.ALLGEMEIN);
	let locById = $derived(new Map(locations.map((l) => [l.id, l])));

	function numericValue(raw: number | string | null | undefined): number | null {
		if (raw == null) return null;
		if (typeof raw === 'number') return raw;
		const mapped = THUNDER_MAP[raw];
		return mapped != null ? mapped : null;
	}

	function displayValue(raw: number | string | null | undefined, unit: string, decimals: number): string {
		if (raw == null) return '—';
		if (typeof raw === 'string') {
			return unit ? `${raw} ${unit}`.trim() : raw;
		}
		return `${raw.toFixed(decimals)}${unit ? ' ' + unit : ''}`.trim();
	}

	/** Index der Zelle mit dem besten Wert für die Zeile (-1 wenn keine Werte vorhanden). */
	function bestIndex(values: (number | null)[], higherIsBetter: boolean): number {
		let bestIdx = -1;
		let bestVal: number | null = null;
		for (let i = 0; i < values.length; i++) {
			const v = values[i];
			if (v == null) continue;
			if (bestVal == null || (higherIsBetter ? v > bestVal : v < bestVal)) {
				bestVal = v;
				bestIdx = i;
			}
		}
		return bestIdx;
	}

	/** Mini-Bar-Breite (0–100) für `value` relativ zu allen `values` der Zeile. */
	function barWidth(value: number | null, values: (number | null)[], higherIsBetter: boolean): number {
		if (value == null) return 0;
		const numeric = values.filter((v): v is number => v != null);
		if (numeric.length === 0) return 0;
		const max = Math.max(...numeric);
		const min = Math.min(...numeric);
		if (higherIsBetter) {
			if (max <= 0) return 0;
			return Math.max(2, Math.round((value / max) * 100));
		}
		// niedriger ist besser: invertieren
		if (max === 0) return 100;
		// Bar zeigt wie gut der Wert ist (= wie nah am Minimum)
		if (max === min) return 100;
		const pct = (1 - (value - min) / (max - min)) * 100;
		return Math.max(2, Math.round(pct));
	}
</script>

<Card.Root data-testid="compare-matrix">
	<Card.Header>
		<Card.Title>Vergleich</Card.Title>
	</Card.Header>
	<Card.Content class="overflow-x-auto">
		<Table.Root>
			<Table.Header>
				<Table.Row>
					<Table.Head class="w-40 sticky left-0 z-10 bg-card">Metrik</Table.Head>
					{#each rows as row, i}
						{@const loc = locById.get(row.location_id)}
						<Table.Head class="text-center">
							<span class="mr-1 rounded bg-primary px-1.5 py-0.5 text-xs text-primary-foreground">
								#{i + 1}
							</span>
							{loc?.name ?? row.location_id}
						</Table.Head>
					{/each}
				</Table.Row>
			</Table.Header>
			<Table.Body>
				{#each metrics as metric}
					{@const rawValues = rows.map((r) => r.metrics[metric.key] as number | string | null | undefined)}
					{@const numericValues = rawValues.map((v) => numericValue(v))}
					{@const best = bestIndex(numericValues, metric.higherIsBetter)}
					<Table.Row data-testid="compare-matrix-row">
						<Table.Cell class="font-medium sticky left-0 z-10 bg-card">{metric.label}</Table.Cell>
						{#each rows as row, i}
							{@const raw = rawValues[i]}
							{@const num = numericValues[i]}
							{@const isBest = i === best && num != null}
							<Table.Cell
								data-testid="compare-matrix-cell"
								data-location-id={row.location_id}
								data-best={isBest ? 'true' : undefined}
								class={isBest ? 'best-value text-center' : 'text-center'}
							>
								<div class="value-text">
									{#if isBest}
										<span data-testid="compare-matrix-best" class="best-marker">
											{displayValue(raw, metric.unit, metric.decimals)}
										</span>
									{:else}
										{displayValue(raw, metric.unit, metric.decimals)}
									{/if}
								</div>
								{#if num != null}
									<div
										data-testid="compare-matrix-minibar"
										class="mini-bar mt-1"
										style="width: {barWidth(num, numericValues, metric.higherIsBetter)}%"
									></div>
								{/if}
							</Table.Cell>
						{/each}
					</Table.Row>
				{/each}
			</Table.Body>
		</Table.Root>
		<p class="mt-2 text-xs text-muted-foreground">
			Grün markiert = bester Wert je Zeile · Mini-Bars zeigen das relative Verhältnis innerhalb der Zeile.
		</p>
	</Card.Content>
</Card.Root>

<style>
	:global([data-best='true']) {
		background-color: color-mix(in oklab, var(--g-good) 12%, transparent);
	}
	:global(.best-value .best-marker) {
		color: var(--g-good);
		font-weight: 600;
	}
	:global(.mini-bar) {
		height: 4px;
		border-radius: 2px;
		background: var(--g-accent);
		opacity: 0.45;
		min-width: 2px;
		display: block;
	}
</style>
