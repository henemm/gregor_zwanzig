<script lang="ts">
	import type { Trip, Stage, ForecastResponse } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { Btn } from '$lib/components/ui/btn';
	import { Button } from '$lib/components/ui/button/index.js';
	import ActiveTripCard from './_cockpit/ActiveTripCard.svelte';
	import StageStrip from './_cockpit/StageStrip.svelte';
	import BriefingsTimeline from './_cockpit/BriefingsTimeline.svelte';
	import AlertFeed from './_cockpit/AlertFeed.svelte';
	import BottomRow from './_cockpit/BottomRow.svelte';

	let { data } = $props();

	const today = new Date().toISOString().slice(0, 10);
	const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);

	function getTripStatus(trip: Trip): 'active' | 'upcoming' | 'archived' {
		const dates = trip.stages?.map((s: Stage) => s.date).filter(Boolean).sort() ?? [];
		if (!dates.length) return 'upcoming';
		if (dates[dates.length - 1] < today) return 'archived';
		if (dates[0] <= today) return 'active';
		return 'upcoming';
	}

	const activeTrip = $derived(
		(data.trips as Trip[]).find((t: Trip) =>
			t.stages?.some((s: Stage) => s.date === today)
		) ?? null
	);
	const todayStage = $derived(
		activeTrip?.stages?.find((s: Stage) => s.date === today) ?? null
	);
	const dayIndex = $derived(
		activeTrip ? activeTrip.stages.findIndex((s: Stage) => s.date === today) : -1
	);
	const tomorrowStage = $derived(
		activeTrip?.stages?.find((s: Stage) => s.date === tomorrow) ?? null
	);
	const archivedTrips = $derived(
		(data.trips as Trip[])
			.filter((t: Trip) => getTripStatus(t) === 'archived')
			.sort((a: Trip, b: Trip) => {
				const aLast = a.stages?.map((s: Stage) => s.date).filter(Boolean).sort().at(-1) ?? '';
				const bLast = b.stages?.map((s: Stage) => s.date).filter(Boolean).sort().at(-1) ?? '';
				return bLast.localeCompare(aLast);
			})
			.slice(0, 4)
	);

	// Datum-Formatierung für Topbar (DD. Month YYYY)
	const todayFormatted = new Date().toLocaleDateString('de-DE', {
		day: 'numeric',
		month: 'long',
		year: 'numeric'
	});

	// Forecast (client-seitig, non-blocking)
	let forecastData = $state<ForecastResponse | null>(null);
	let forecastStatus = $state<'idle' | 'loading' | 'ok' | 'error'>('idle');

	$effect(() => {
		if (!data.forecastCoords) return;
		forecastStatus = 'loading';
		api
			.get<ForecastResponse>(
				`/api/forecast?lat=${data.forecastCoords.lat}&lon=${data.forecastCoords.lon}&hours=24`
			)
			.then((r) => {
				forecastData = r;
				forecastStatus = 'ok';
			})
			.catch(() => {
				forecastStatus = 'error';
			});
	});

	const forecastSummary = $derived.by(() => {
		const pt = forecastData?.data?.[0];
		if (!pt) return null;
		return {
			temp: pt.t2m_c ?? null,
			wind: pt.wind10m_kmh ?? null,
			precip: pt.precip_1h_mm ?? null
		};
	});

	// Test-Briefing CTA — Safari-sicher: benannte Funktion
	let briefingStatus = $state<'idle' | 'loading' | 'ok' | 'error'>('idle');
	let briefingError = $state<string | null>(null);

	async function handleTestBriefing() {
		briefingStatus = 'loading';
		briefingError = null;
		try {
			await api.post('/api/scheduler/trip-reports', {});
			briefingStatus = 'ok';
			setTimeout(() => {
				briefingStatus = 'idle';
			}, 4000);
		} catch (e: unknown) {
			const body = e as { detail?: string; error?: string };
			briefingError = body?.detail ?? body?.error ?? 'Fehler beim Senden';
			briefingStatus = 'error';
		}
	}
</script>

<div class="space-y-6">
	<!-- Topbar -->
	<header
		data-testid="cockpit-topbar"
		class="flex items-center justify-between gap-4 flex-wrap"
	>
		<div>
			<p class="text-sm text-muted-foreground">{todayFormatted}</p>
			<h1 class="text-2xl font-bold">Guten Tag</h1>
		</div>
		<div class="flex items-center gap-2 flex-wrap">
			{#if briefingStatus === 'ok'}
				<span class="text-sm text-green-600">Gesendet</span>
			{/if}
			{#if briefingStatus === 'error' && briefingError}
				<span data-testid="briefing-error" class="text-sm text-destructive">
					{briefingError}
				</span>
			{/if}
			<Btn
				data-testid="cta-test-briefing"
				variant="outline"
				size="sm"
				onclick={handleTestBriefing}
				disabled={briefingStatus === 'loading'}
			>
				{#if briefingStatus === 'loading'}
					…
				{:else if briefingStatus === 'ok'}
					Gesendet
				{:else}
					Test-Briefing senden
				{/if}
			</Btn>
			<Button
				data-testid="cta-new-trip"
				href="/trips/new"
				size="sm"
			>
				Neuer Trip
			</Button>
		</div>
	</header>

	<!-- Hero: Aktiver Trip oder Leer-State -->
	{#if activeTrip && todayStage}
		<ActiveTripCard
			trip={activeTrip}
			{todayStage}
			{dayIndex}
			{forecastSummary}
			{forecastStatus}
		/>
		<StageStrip stages={activeTrip.stages} activeStageid={todayStage.id} />
	{:else}
		<div
			data-testid="no-active-trip"
			class="rounded-lg border bg-muted/30 p-8 text-center text-muted-foreground"
		>
			<p class="mb-4">Kein aktiver Trip heute.</p>
			<a href="/trips/new" class="text-primary underline underline-offset-2">
				Neuen Trip anlegen
			</a>
		</div>
	{/if}

	<!-- Briefings-Timeline -->
	<BriefingsTimeline schedulerStatus={data.schedulerStatus} />

	<!-- Alert-Feed -->
	<AlertFeed />

	<!-- Bottom-Row: Morgen-Vorschau + Archiv-Grid -->
	<BottomRow {tomorrowStage} {archivedTrips} />
</div>
