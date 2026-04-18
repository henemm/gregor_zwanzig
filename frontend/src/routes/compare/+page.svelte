<script lang="ts">
	import type { Location } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import LocationForm from '$lib/components/LocationForm.svelte';

	let { data } = $props();

	let locations: Location[] = $state(data.locations);
	let selectedIds = $state<string[]>(locations.map((l) => l.id));
	let allSelected = $state(true);
	let targetDate = $state(new Date().toISOString().slice(0, 10));
	let twStart = $state(9);
	let twEnd = $state(16);
	let forecastHours = $state(48);
	let activityProfile = $state('allgemein');
	let loading = $state(false);
	let error = $state('');
	let result: CompareResult | null = $state(null);
	let showNewLocDialog = $state(false);

	async function handleNewLocSave(loc: Location) {
		try {
			await api.post<Location>('/api/locations', loc);
			locations = [...locations, loc];
			selectedIds = [...selectedIds, loc.id];
			allSelected = selectedIds.length === locations.length;
			showNewLocDialog = false;
		} catch (e: unknown) {
			// LocationForm handles its own errors
		}
	}

	interface CompareLocation {
		id: string;
		name: string;
		elevation_m: number | null;
		score: number;
		error: string | null;
		snow_depth_cm: number | null;
		snow_new_cm: number | null;
		temp_min: number | null;
		temp_max: number | null;
		wind_max: number | null;
		wind_direction_avg: number | null;
		gust_max: number | null;
		wind_chill_min: number | null;
		cloud_avg: number | null;
		sunny_hours: number | null;
		above_low_clouds: boolean;
		hourly?: HourlyPoint[];
	}

	interface HourlyPoint {
		ts: string;
		t2m_c: number | null;
		wind10m_kmh: number | null;
		gust_kmh: number | null;
		precip_1h_mm: number | null;
		cloud_total_pct: number | null;
		wmo_code: number | null;
		is_day: number | null;
	}

	interface CompareResult {
		target_date: string;
		time_window: [number, number];
		created_at: string;
		winner: { id: string; name: string; score: number } | null;
		locations: CompareLocation[];
	}

	function toggleAll() {
		allSelected = !allSelected;
		selectedIds = allSelected ? locations.map((l) => l.id) : [];
	}

	function toggleLocation(id: string) {
		if (selectedIds.includes(id)) {
			selectedIds = selectedIds.filter((i) => i !== id);
		} else {
			selectedIds = [...selectedIds, id];
		}
		allSelected = selectedIds.length === locations.length;
	}

	function degToCompass(deg: number | null): string {
		if (deg == null) return '-';
		const dirs = ['N', 'NO', 'O', 'SO', 'S', 'SW', 'W', 'NW'];
		return dirs[Math.round(deg / 45) % 8];
	}

	function fmt(val: number | null | undefined, suffix: string = '', decimals: number = 0): string {
		if (val == null) return '-';
		return `${val.toFixed(decimals)}${suffix}`;
	}

	function bestIdx(vals: (number | null)[], higherIsBetter: boolean): number {
		let best = -1;
		let bestVal: number | null = null;
		for (let i = 0; i < vals.length; i++) {
			if (vals[i] == null) continue;
			if (bestVal == null || (higherIsBetter ? vals[i]! > bestVal : vals[i]! < bestVal)) {
				bestVal = vals[i];
				best = i;
			}
		}
		return best;
	}

	async function runComparison() {
		if (selectedIds.length === 0) {
			error = 'Mindestens eine Location auswählen';
			return;
		}
		if (twStart >= twEnd) {
			error = 'Zeitfenster Start muss vor Ende liegen';
			return;
		}
		error = '';
		loading = true;
		result = null;

		try {
			const ids = allSelected ? '*' : selectedIds.join(',');
			const params = new URLSearchParams({
				location_ids: ids,
				target_date: targetDate,
				time_window_start: String(twStart),
				time_window_end: String(twEnd),
				forecast_hours: String(forecastHours),
				activity_profile: activityProfile
			});
			const res = await fetch(`/api/compare?${params}`);
			if (!res.ok) {
				const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
				throw new Error(err.detail ?? err.error ?? `HTTP ${res.status}`);
			}
			result = await res.json();
		} catch (e: unknown) {
			error = (e as Error).message ?? 'Fehler beim Vergleich';
		} finally {
			loading = false;
		}
	}

	// Computed: valid locations (no error, sorted by score)
	let validLocs = $derived(result?.locations.filter((l) => !l.error) ?? []);
	let errorLocs = $derived(result?.locations.filter((l) => l.error) ?? []);
</script>

<div class="flex gap-6">
	<!-- Sidebar: Desktop only -->
	<aside class="hidden w-60 shrink-0 space-y-4 border-r pr-4 md:block">
		<h2 class="text-sm font-semibold">Meine Orte</h2>
		<label class="flex items-center gap-2 text-sm">
			<input type="checkbox" checked={allSelected} onchange={toggleAll}
				class="h-4 w-4 rounded border-input" />
			Alle ({locations.length})
		</label>
		<div class="space-y-1">
			{#each locations as loc}
				<label class="flex items-center gap-1.5 text-sm">
					<input type="checkbox" checked={selectedIds.includes(loc.id)}
						onchange={() => toggleLocation(loc.id)}
						class="h-3.5 w-3.5 rounded border-input" />
					{loc.name}
				</label>
			{/each}
		</div>
		<Button variant="outline" size="sm" class="w-full" onclick={() => showNewLocDialog = true}>
			Neuer Ort
		</Button>
	</aside>

	<!-- Content -->
	<div class="min-w-0 flex-1 space-y-6">
	<h1 class="text-2xl font-bold">Orts-Vergleich</h1>

	<!-- Controls -->
	<Card.Root>
		<Card.Header>
			<Card.Title>Einstellungen</Card.Title>
		</Card.Header>
		<Card.Content class="space-y-4">
			<!-- Location Selection: Mobile only -->
			<div class="md:hidden">
				<p class="mb-2 text-sm font-medium">Locations</p>
				<label class="mb-1 flex items-center gap-2 text-sm">
					<input type="checkbox" checked={allSelected} onchange={toggleAll}
						class="h-4 w-4 rounded border-input" />
					Alle ({locations.length})
				</label>
				<div class="mt-1 flex flex-wrap gap-2">
					{#each locations as loc}
						<label class="flex items-center gap-1.5 text-sm">
							<input type="checkbox" checked={selectedIds.includes(loc.id)}
								onchange={() => toggleLocation(loc.id)}
								class="h-3.5 w-3.5 rounded border-input" />
							{loc.name}
						</label>
					{/each}
				</div>
			</div>

			<!-- Date + Time Window + Hours -->
			<div class="grid grid-cols-2 gap-4 md:grid-cols-4">
				<div>
					<label for="cmp-date" class="text-sm font-medium">Datum</label>
					<input id="cmp-date" type="date" bind:value={targetDate}
						class="mt-1 block w-full rounded-md border px-3 py-2 text-sm" />
				</div>
				<div>
					<label for="cmp-start" class="text-sm font-medium">Von (Uhr)</label>
					<select id="cmp-start" bind:value={twStart}
						class="mt-1 block w-full rounded-md border px-3 py-2 text-sm">
						{#each Array.from({ length: 24 }, (_, i) => i) as h}
							<option value={h}>{String(h).padStart(2, '0')}:00</option>
						{/each}
					</select>
				</div>
				<div>
					<label for="cmp-end" class="text-sm font-medium">Bis (Uhr)</label>
					<select id="cmp-end" bind:value={twEnd}
						class="mt-1 block w-full rounded-md border px-3 py-2 text-sm">
						{#each Array.from({ length: 24 }, (_, i) => i) as h}
							<option value={h}>{String(h).padStart(2, '0')}:00</option>
						{/each}
					</select>
				</div>
				<div>
					<label for="cmp-hours" class="text-sm font-medium">Forecast</label>
					<select id="cmp-hours" bind:value={forecastHours}
						class="mt-1 block w-full rounded-md border px-3 py-2 text-sm">
						<option value={24}>24h</option>
						<option value={48}>48h</option>
						<option value={72}>72h</option>
					</select>
				</div>
			</div>

			<!-- Activity Profile -->
			<div>
				<label for="cmp-profile" class="text-sm font-medium">Aktivitätsprofil</label>
				<select id="cmp-profile" bind:value={activityProfile}
					class="mt-1 block w-full rounded-md border px-3 py-2 text-sm">
					<option value="allgemein">Allgemein</option>
					<option value="wintersport">Wintersport</option>
					<option value="wandern">Wandern</option>
				</select>
			</div>

			<Button onclick={runComparison} disabled={loading}>
				{loading ? 'Lädt...' : 'Vergleichen'}
			</Button>
		</Card.Content>
	</Card.Root>

	{#if error}
		<p class="text-sm text-destructive">{error}</p>
	{/if}

	{#if loading}
		<Card.Root>
			<Card.Content class="py-12 text-center text-muted-foreground">
				Wetterdaten werden geladen... Das kann bis zu 30 Sekunden dauern.
			</Card.Content>
		</Card.Root>
	{/if}

	<!-- Results -->
	{#if result && !loading}
		<!-- Winner -->
		{#if result.winner}
			<Card.Root class="border-green-300 bg-green-50">
				<Card.Content class="py-4">
					<p class="text-lg font-semibold text-green-800">
						Empfehlung: {result.winner.name}
					</p>
					<p class="text-sm text-green-700">
						Score: <strong>{result.winner.score}</strong> |
						{new Date(result.target_date).toLocaleDateString('de-AT', { weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric' })} |
						{result.time_window[0]}:00 – {result.time_window[1]}:00
					</p>
				</Card.Content>
			</Card.Root>
		{/if}

		<!-- Comparison Table -->
		{#if validLocs.length > 0}
			{@const scores = validLocs.map(l => l.score)}
			{@const snowDepths = validLocs.map(l => l.snow_depth_cm)}
			{@const snowNews = validLocs.map(l => l.snow_new_cm)}
			{@const winds = validLocs.map(l => l.wind_max)}
			{@const gusts = validLocs.map(l => l.gust_max)}
			{@const windChills = validLocs.map(l => l.wind_chill_min)}
			{@const sunnyHrs = validLocs.map(l => l.sunny_hours)}
			{@const clouds = validLocs.map(l => l.cloud_avg)}
			{@const bestScore = bestIdx(scores, true)}
			{@const bestSnow = bestIdx(snowDepths, true)}
			{@const bestNewSnow = bestIdx(snowNews, true)}
			{@const bestWind = bestIdx(winds, false)}
			{@const bestGust = bestIdx(gusts, false)}
			{@const bestWC = bestIdx(windChills, true)}
			{@const bestSun = bestIdx(sunnyHrs, true)}
			{@const bestCloud = bestIdx(clouds, false)}

			<Card.Root>
				<Card.Header>
					<Card.Title>Vergleich</Card.Title>
				</Card.Header>
				<Card.Content class="overflow-x-auto">
					<Table.Root>
						<Table.Header>
							<Table.Row>
								<Table.Head class="w-36">Metrik</Table.Head>
								{#each validLocs as loc, i}
									<Table.Head class="text-center">
										<span class="mr-1 rounded bg-primary px-1.5 py-0.5 text-xs text-primary-foreground">#{i + 1}</span>
										{loc.name}
									</Table.Head>
								{/each}
							</Table.Row>
						</Table.Header>
						<Table.Body>
							<!-- Score -->
							<Table.Row>
								<Table.Cell class="font-medium">Score</Table.Cell>
								{#each validLocs as loc, i}
									<Table.Cell class="text-center {i === bestScore ? 'bg-green-50 font-semibold text-green-700' : ''}">
										{loc.score}
									</Table.Cell>
								{/each}
							</Table.Row>
							<!-- Snow Depth -->
							<Table.Row>
								<Table.Cell class="font-medium">Schneehöhe</Table.Cell>
								{#each validLocs as loc, i}
									<Table.Cell class="text-center {i === bestSnow ? 'bg-green-50 font-semibold text-green-700' : ''}">
										{fmt(loc.snow_depth_cm, 'cm')}
									</Table.Cell>
								{/each}
							</Table.Row>
							<!-- New Snow -->
							<Table.Row>
								<Table.Cell class="font-medium">Neuschnee</Table.Cell>
								{#each validLocs as loc, i}
									<Table.Cell class="text-center {i === bestNewSnow && loc.snow_new_cm && loc.snow_new_cm > 0 ? 'bg-green-50 font-semibold text-green-700' : ''}">
										{loc.snow_new_cm && loc.snow_new_cm > 0 ? `+${fmt(loc.snow_new_cm, 'cm')}` : '-'}
									</Table.Cell>
								{/each}
							</Table.Row>
							<!-- Wind/Gusts -->
							<Table.Row>
								<Table.Cell class="font-medium">Wind/Böen</Table.Cell>
								{#each validLocs as loc, i}
									<Table.Cell class="text-center {i === bestWind ? 'bg-green-50 font-semibold text-green-700' : ''}">
										{loc.wind_max != null && loc.gust_max != null
											? `${fmt(loc.wind_max)}/${fmt(loc.gust_max)} ${degToCompass(loc.wind_direction_avg)}`
											: loc.wind_max != null
												? `${fmt(loc.wind_max)} ${degToCompass(loc.wind_direction_avg)}`
												: '-'}
									</Table.Cell>
								{/each}
							</Table.Row>
							<!-- Wind Chill -->
							<Table.Row>
								<Table.Cell class="font-medium">Temperatur (gefühlt)</Table.Cell>
								{#each validLocs as loc, i}
									<Table.Cell class="text-center {i === bestWC ? 'bg-green-50 font-semibold text-green-700' : ''}">
										{fmt(loc.wind_chill_min, '°C')}
									</Table.Cell>
								{/each}
							</Table.Row>
							<!-- Sunny Hours -->
							<Table.Row>
								<Table.Cell class="font-medium">Sonnenstunden</Table.Cell>
								{#each validLocs as loc, i}
									<Table.Cell class="text-center {i === bestSun && loc.sunny_hours && loc.sunny_hours > 0 ? 'bg-green-50 font-semibold text-green-700' : ''}">
										{loc.sunny_hours != null ? (loc.sunny_hours === 0 ? '0h' : `~${loc.sunny_hours}h`) : '-'}
									</Table.Cell>
								{/each}
							</Table.Row>
							<!-- Clouds -->
							<Table.Row>
								<Table.Cell class="font-medium">Bewölkung</Table.Cell>
								{#each validLocs as loc, i}
									<Table.Cell class="text-center {i === bestCloud ? 'bg-green-50 font-semibold text-green-700' : ''}">
										{loc.cloud_avg != null ? `${loc.cloud_avg}%${loc.above_low_clouds ? '*' : ''}` : '-'}
									</Table.Cell>
								{/each}
							</Table.Row>
						</Table.Body>
					</Table.Root>
					<p class="mt-2 text-xs text-muted-foreground">
						Grün = bester Wert | Temperatur = gefühlt (Wind Chill) | * = über tiefen Wolken
					</p>
				</Card.Content>
			</Card.Root>
		{/if}

		<!-- Error Locations -->
		{#if errorLocs.length > 0}
			<Card.Root class="border-amber-300">
				<Card.Header>
					<Card.Title class="text-amber-700">Fehler bei {errorLocs.length} Location(s)</Card.Title>
				</Card.Header>
				<Card.Content>
					{#each errorLocs as loc}
						<p class="text-sm"><strong>{loc.name}:</strong> {loc.error}</p>
					{/each}
				</Card.Content>
			</Card.Root>
		{/if}
	{/if}
	</div>
</div>

<!-- New Location Dialog -->
<Dialog.Root
	open={showNewLocDialog}
	onOpenChange={(open) => { if (!open) showNewLocDialog = false; }}
>
	<Dialog.Content class="max-h-[80vh] max-w-lg overflow-y-auto">
		<Dialog.Header>
			<Dialog.Title>Neue Location</Dialog.Title>
		</Dialog.Header>
		{#if showNewLocDialog}
			<LocationForm
				onsave={handleNewLocSave}
				oncancel={() => showNewLocDialog = false}
			/>
		{/if}
	</Dialog.Content>
</Dialog.Root>
