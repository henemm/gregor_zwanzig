<script lang="ts">
	import type { Location, ForecastResponse } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import { weatherEmoji, degToCardinal } from '$lib/utils/weatherEmoji.js';

	let { data } = $props();

	let locations: Location[] = $state(data.locations);
	let selectedId = $state('');
	let hours = $state('48');
	let forecast: ForecastResponse | null = $state(null);
	let loading = $state(false);
	let error: string | null = $state(null);

	function formatTime(ts: string): string {
		return new Date(ts).toLocaleTimeString('de-AT', { hour: '2-digit', minute: '2-digit' });
	}

	function formatDate(ts: string): string {
		return new Date(ts).toLocaleDateString('de-AT', { weekday: 'short', day: '2-digit', month: '2-digit' });
	}

	async function loadForecast() {
		error = null;
		if (!selectedId) {
			error = 'Bitte Location wählen';
			return;
		}
		const loc = locations.find((l) => l.id === selectedId);
		if (!loc) return;

		loading = true;
		forecast = null;
		try {
			forecast = await api.get<ForecastResponse>(
				`/api/forecast?lat=${loc.lat}&lon=${loc.lon}&hours=${hours}`
			);
		} catch (e: unknown) {
			error = (e as { error?: string })?.error ?? 'Fehler beim Laden der Wetterdaten';
		} finally {
			loading = false;
		}
	}

	let prevDate = $state('');
</script>

<div class="space-y-4">
	<h1 class="text-2xl font-bold">Wetter</h1>

	<div class="flex items-end gap-3">
		<div>
			<label for="location-select" class="mb-1 block text-sm font-medium">Location</label>
			<select
				id="location-select"
				name="location-select"
				bind:value={selectedId}
				class="flex h-8 w-56 rounded-lg border border-input bg-transparent px-2.5 py-1 text-base transition-colors focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-3"
			>
				<option value="">— Location wählen —</option>
				{#each locations as loc}
					<option value={loc.id}>{loc.name}</option>
				{/each}
			</select>
		</div>

		<div>
			<label for="hours-select" class="mb-1 block text-sm font-medium">Stunden</label>
			<select
				id="hours-select"
				name="hours-select"
				bind:value={hours}
				class="flex h-8 w-24 rounded-lg border border-input bg-transparent px-2.5 py-1 text-base transition-colors focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-3"
			>
				<option value="24">24h</option>
				<option value="48">48h</option>
				<option value="72">72h</option>
				<option value="120">120h</option>
				<option value="240">240h</option>
			</select>
		</div>

		<Button onclick={loadForecast} disabled={loading}>
			{loading ? 'Lädt…' : 'Laden'}
		</Button>
	</div>

	{#if error}
		<p class="text-sm text-destructive">{error}</p>
	{/if}

	{#if forecast}
		<p class="text-xs text-muted-foreground" data-testid="forecast-meta">
			{forecast.meta.provider} · {forecast.meta.model} · {forecast.timezone}
		</p>

		<div class="max-h-[70vh] overflow-y-auto">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head>Zeit</Table.Head>
						<Table.Head>Symbol</Table.Head>
						<Table.Head>Temp</Table.Head>
						<Table.Head>Precip</Table.Head>
						<Table.Head>Wind</Table.Head>
						<Table.Head>Böen</Table.Head>
						<Table.Head>Richtung</Table.Head>
						<Table.Head>Wolken</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each forecast.data as dp, i}
						{@const dateStr = formatDate(dp.ts)}
						{@const showDate = dateStr !== (i > 0 ? formatDate(forecast.data[i - 1].ts) : '')}
						{#if showDate}
							<Table.Row>
								<Table.Cell colspan={8} class="bg-muted/50 py-1 text-xs font-medium">
									{dateStr}
								</Table.Cell>
							</Table.Row>
						{/if}
						<Table.Row>
							<Table.Cell class="text-sm">{formatTime(dp.ts)}</Table.Cell>
							<Table.Cell>{weatherEmoji(dp.wmo_code, dp.is_day, dp.dni_wm2, dp.cloud_total_pct)}</Table.Cell>
							<Table.Cell class="text-sm">{dp.t2m_c != null ? dp.t2m_c.toFixed(1) + '°' : '—'}</Table.Cell>
							<Table.Cell class="text-sm">{dp.precip_1h_mm != null && dp.precip_1h_mm > 0 ? dp.precip_1h_mm.toFixed(1) + ' mm' : '—'}</Table.Cell>
							<Table.Cell class="text-sm">{dp.wind10m_kmh != null ? Math.round(dp.wind10m_kmh) + ' km/h' : '—'}</Table.Cell>
							<Table.Cell class="text-sm">{dp.gust_kmh != null ? Math.round(dp.gust_kmh) + ' km/h' : '—'}</Table.Cell>
							<Table.Cell class="text-sm">{degToCardinal(dp.wind_direction_deg)}</Table.Cell>
							<Table.Cell class="text-sm">{dp.cloud_total_pct != null ? dp.cloud_total_pct + '%' : '—'}</Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
	{/if}
</div>
