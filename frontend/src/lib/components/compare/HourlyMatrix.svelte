<script lang="ts">
	// Issue #251/#455 — HourlyMatrix: Stunden-Verlauf der Top-3 Locations.
	// Issue #454: stunden_verlauf[] (StundenVerlaufEntry) statt hourly-Record.

	import type { StundenVerlaufEntry, Location } from '$lib/types.js';
	import { Pill } from '$lib/components/ui/pill/index.js';
	import * as Card from '$lib/components/ui/card/index.js';

	interface Props {
		stunden_verlauf: StundenVerlaufEntry[];
		locations: Location[];
	}

	let { stunden_verlauf, locations }: Props = $props();

	let locById = $derived(new Map(locations.map((l) => [l.id, l])));

	let topSections = $derived(
		stunden_verlauf
			.slice(0, 3)
			.filter((e) => e.hours.length > 0)
			.map((e, idx) => ({
				rank: idx + 1,
				entry: e,
				name: locById.get(e.location_id)?.name ?? e.location_id,
			}))
	);

	function fmtNum(v: unknown, decimals = 0): string {
		if (v == null) return '—';
		return (v as number).toFixed(decimals);
	}

	function thunderTone(level: unknown): 'success' | 'warning' | 'danger' {
		if (level === 'HIGH') return 'danger';
		if (level === 'MED') return 'warning';
		return 'success';
	}

	function thunderLabel(level: unknown): string {
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
								<th class="py-1 pr-2 sticky left-0 z-10 bg-card">Zeit</th>
								<th class="py-1 pr-2">Temp</th>
								<th class="py-1 pr-2">Wind</th>
								<th class="py-1 pr-2">Böen</th>
								<th class="py-1 pr-2">Regen</th>
								<th class="py-1 pr-2">Risiko</th>
							</tr>
						</thead>
						<tbody>
							{#each section.entry.hours as h}
								<tr class="border-t">
									<td class="py-1 pr-2 sticky left-0 z-10 bg-card">{h.hour}:00</td>
									<td class="py-1 pr-2">{fmtNum(h.values['t2m_c'], 1)}°</td>
									<td class="py-1 pr-2">{fmtNum(h.values['wind10m_kmh'])}</td>
									<td class="py-1 pr-2">{fmtNum(h.values['gust_kmh'])}</td>
									<td class="py-1 pr-2">{fmtNum(h.values['precip_1h_mm'], 1)}</td>
									<td class="py-1 pr-2">
										<Pill tone={thunderTone(h.values['thunder_level'])} class="px-2 py-0.5 text-[10px] rounded-full">
											{thunderLabel(h.values['thunder_level'])}
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
