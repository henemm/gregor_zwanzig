<script lang="ts">
	// Issue #251 — HourlyMatrix: Stunden-Verlauf der Top-3 Locations.
	//
	// Spec: docs/specs/modules/issue_251_compare_main_stage.md §5

	import type { CompareRow, ForecastDataPoint, Location } from '$lib/types.js';
	import { Pill } from '$lib/components/ui/pill/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import { weatherEmoji } from '$lib/utils/weatherEmoji.js';

	interface Props {
		hourly: Record<string, ForecastDataPoint[]>;
		locations: Location[];
		rows: CompareRow[];
	}

	let { hourly, locations, rows }: Props = $props();

	let locById = $derived(new Map(locations.map((l) => [l.id, l])));

	let topSections = $derived(
		rows
			.slice(0, 3)
			.filter((r) => Array.isArray(hourly[r.location_id]) && hourly[r.location_id].length > 0)
			.map((r, idx) => ({
				rank: idx + 1,
				row: r,
				name: locById.get(r.location_id)?.name ?? r.location_id,
				points: hourly[r.location_id],
			}))
	);

	function formatTime(ts: string): string {
		return new Date(ts).toLocaleTimeString('de-AT', { hour: '2-digit', minute: '2-digit' });
	}

	function fmtNum(v: number | null | undefined, decimals = 0): string {
		if (v == null) return '—';
		return v.toFixed(decimals);
	}

	function thunderTone(level: string | null | undefined): 'success' | 'warning' | 'danger' {
		if (level === 'HIGH') return 'danger';
		if (level === 'MED') return 'warning';
		return 'success';
	}

	function thunderLabel(level: string | null | undefined): string {
		if (level === 'HIGH') return 'Hoch';
		if (level === 'MED') return 'Mittel';
		return 'Kein';
	}
</script>

<Card.Root data-testid="compare-hourly-matrix">
	<Card.Header>
		<Card.Title>Stunden-Verlauf (Top 3)</Card.Title>
	</Card.Header>
	<Card.Content class="space-y-3">
		{#each topSections as section}
			<details
				data-testid="compare-hourly-section"
				data-rank={section.rank}
				open={section.rank === 1}
				class="rounded-md border"
			>
				<summary class="flex cursor-pointer items-center gap-2 px-3 py-2 text-sm font-medium">
					<span class="rounded bg-primary px-1.5 py-0.5 text-xs text-primary-foreground">
						#{section.rank}
					</span>
					<span>{section.name}</span>
				</summary>
				<div class="overflow-x-auto px-3 pb-3">
					<table class="w-full text-xs">
						<thead>
							<tr class="text-left text-muted-foreground">
								<th class="py-1 pr-2">Zeit</th>
								<th class="py-1 pr-2"></th>
								<th class="py-1 pr-2">Temp</th>
								<th class="py-1 pr-2">Wind</th>
								<th class="py-1 pr-2">Böen</th>
								<th class="py-1 pr-2">Regen</th>
								<th class="py-1 pr-2">Risiko</th>
							</tr>
						</thead>
						<tbody>
							{#each section.points as p}
								<tr class="border-t">
									<td class="py-1 pr-2">{formatTime(p.ts)}</td>
									<td class="py-1 pr-2">
										{weatherEmoji(p.wmo_code, p.is_day, p.dni_wm2, p.cloud_total_pct)}
									</td>
									<td class="py-1 pr-2">{fmtNum(p.t2m_c, 1)}°</td>
									<td class="py-1 pr-2">{fmtNum(p.wind10m_kmh)}</td>
									<td class="py-1 pr-2">{fmtNum(p.gust_kmh)}</td>
									<td class="py-1 pr-2">{fmtNum(p.precip_1h_mm, 1)}</td>
									<td class="py-1 pr-2">
										<Pill tone={thunderTone(p.thunder_level)} class="px-2 py-0.5 text-[10px] rounded-full">
											{thunderLabel(p.thunder_level)}
										</Pill>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</details>
		{/each}
	</Card.Content>
</Card.Root>
