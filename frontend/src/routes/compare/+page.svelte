<script lang="ts">
	// Issue #251 — Compare-Hauptbühne (Frontend).
	//
	// Spec: docs/specs/modules/issue_251_compare_main_stage.md
	// API: POST /api/compare/run (Go-Engine, Issue #250) ersetzt GET /api/compare (Python-Proxy)

	import type {
		Location,
		Subscription,
		ForecastResponse,
		ActivityProfile,
		CompareResult,
	} from '$lib/types.js';
	import { toCompareProfile } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { Btn } from '$lib/components/ui/btn/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import SubscriptionForm from '$lib/components/SubscriptionForm.svelte';
	import LocationsRail from '$lib/components/compare/LocationsRail.svelte';
	import NewLocationWizard from '$lib/components/compare/NewLocationWizard.svelte';
	import PresetHeader from '$lib/components/compare/PresetHeader.svelte';
	import RecommendationBanner from '$lib/components/compare/RecommendationBanner.svelte';
	import CompareMatrix from '$lib/components/compare/CompareMatrix.svelte';
	import HourlyMatrix from '$lib/components/compare/HourlyMatrix.svelte';
	import { weatherEmoji } from '$lib/utils/weatherEmoji.js';

	let { data } = $props();

	let locations: Location[] = $state(data.locations);
	let subscriptions: Subscription[] = $state(data.subscriptions ?? []);
	let selectedIds = $state<string[]>(locations.map((l) => l.id));

	const WEEKDAYS = ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'];

	function scheduleLabel(sub: Subscription): string {
		if (sub.schedule === 'daily_morning') return 'Täglich 07:00';
		if (sub.schedule === 'daily_evening') return 'Täglich 18:00';
		if (sub.schedule === 'weekly') return `Wöchentlich ${WEEKDAYS[sub.weekday ?? 0]}`;
		return sub.schedule;
	}

	function locationsLabel(sub: Subscription): string {
		if (!sub.locations || sub.locations.length === 0) return 'Alle Orte';
		return `${sub.locations.length} Orte`;
	}

	let allSelected = $state(true);
	let targetDate = $state(new Date().toISOString().slice(0, 10));
	let twStart = $state(9);
	let twEnd = $state(16);
	let forecastHours = $state(48);
	let activityProfile = $state<ActivityProfile>('allgemein');
	let profileManuallyOverridden = $state(false);
	let loading = $state(false);
	let error = $state('');
	let result: CompareResult | null = $state(null);
	let showNewLocDialog = $state(false);
	let showSaveAsSubDialog = $state(false);
	let saveSubError = $state<string | null>(null);

	let prefilledSub = $derived({
		id: '',
		name: '',
		enabled: true,
		schedule: 'daily_morning' as const,
		weekday: 0,
		time_window_start: twStart,
		time_window_end: twEnd,
		forecast_hours: forecastHours,
		top_n: 3,
		include_hourly: false,
		send_email: true,
		send_signal: false,
		send_telegram: false,
		locations: allSelected ? ['*'] : selectedIds,
		activity_profile: activityProfile,
	});

	async function handleSaveAsSub(sub: Subscription) {
		saveSubError = null;
		try {
			await api.post('/api/subscriptions', sub);
			subscriptions = [...subscriptions, sub];
			showSaveAsSubDialog = false;
		} catch (e: unknown) {
			const body = e as { detail?: string; error?: string };
			saveSubError = body?.detail ?? body?.error ?? 'Fehler beim Speichern';
		}
	}

	let weatherLocationId: string | null = $state(null);
	let weatherForecast: ForecastResponse | null = $state(null);
	let weatherLoading = $state(false);
	let weatherHours = $state('48');

	function formatTime(ts: string): string {
		return new Date(ts).toLocaleTimeString('de-AT', { hour: '2-digit', minute: '2-digit' });
	}

	function formatDate(ts: string): string {
		return new Date(ts).toLocaleDateString('de-AT', { weekday: 'short', day: '2-digit', month: '2-digit' });
	}

	async function showWeather(locId: string) {
		weatherLocationId = locId;
		weatherForecast = null;
		weatherLoading = true;
		const loc = locations.find((l) => l.id === locId);
		if (!loc) {
			weatherLoading = false;
			return;
		}
		try {
			weatherForecast = await api.get<ForecastResponse>(
				`/api/forecast?lat=${loc.lat}&lon=${loc.lon}&hours=${weatherHours}`
			);
		} catch {
			weatherForecast = null;
		} finally {
			weatherLoading = false;
		}
	}

	let weatherLocationName = $derived(
		weatherLocationId ? (locations.find((l) => l.id === weatherLocationId)?.name ?? '') : ''
	);

	function handleNewLocSave(loc: Location) {
		locations = [...locations, loc];
		selectedIds = [...selectedIds, loc.id];
		allSelected = selectedIds.length === locations.length;
		if (loc.group && !openGroups.has(loc.group)) {
			openGroups = new Set([...openGroups, loc.group]);
		}
		showNewLocDialog = false;
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

	async function runComparison() {
		if (!allSelected && selectedIds.length < 2) {
			error = 'Mindestens 2 Locations für den Vergleich auswählen';
			return;
		}
		error = '';
		loading = true;
		result = null;
		try {
			const ids = allSelected ? locations.map((l) => l.id) : [...selectedIds];
			result = await api.post<CompareResult>('/api/compare/run', {
				location_ids: ids,
				date: targetDate,
				profile: toCompareProfile(activityProfile),
			});
		} catch (e: unknown) {
			const body = e as { detail?: string; error?: string };
			error = body?.detail ?? body?.error ?? 'Fehler beim Vergleich';
		} finally {
			loading = false;
		}
	}

	// Grouped locations for sidebar
	let groupedLocations = $derived.by(() => {
		const groups = new Map<string, Location[]>();
		const ungrouped: Location[] = [];
		for (const loc of locations) {
			if (loc.group) {
				const list = groups.get(loc.group) ?? [];
				list.push(loc);
				groups.set(loc.group, list);
			} else {
				ungrouped.push(loc);
			}
		}
		return { groups, ungrouped };
	});

	// Issue #132 — Dominantes Profil der aktuell gewaehlten Locations bestimmen.
	// Ein Profil gilt als dominant, wenn es auf mehr als 50 % der profilierten
	// (nicht-'allgemein') gewaehlten Locations zutrifft.
	let dominantProfile = $derived.by((): ActivityProfile | null => {
		const ids = allSelected ? locations.map((l) => l.id) : selectedIds;
		const profiled = ids
			.map((id) => locations.find((l) => l.id === id)?.activity_profile)
			.filter((p): p is ActivityProfile => Boolean(p) && p !== 'allgemein');
		if (profiled.length === 0) return null;
		const counts = new Map<ActivityProfile, number>();
		for (const p of profiled) counts.set(p, (counts.get(p) ?? 0) + 1);
		const [top] = [...counts.entries()].sort((a, b) => b[1] - a[1]);
		return top[1] / profiled.length > 0.5 ? top[0] : null;
	});

	$effect(() => {
		if (!profileManuallyOverridden && dominantProfile && activityProfile !== dominantProfile) {
			activityProfile = dominantProfile;
		}
	});

	$effect(() => {
		selectedIds;
		allSelected;
		profileManuallyOverridden = false;
	});

	let openGroups = $state<Set<string>>(
		new Set(locations.filter((l) => l.group).map((l) => l.group!))
	);

	function toggleGroup(groupName: string) {
		const next = new Set(openGroups);
		if (next.has(groupName)) {
			next.delete(groupName);
		} else {
			next.add(groupName);
		}
		openGroups = next;
	}

	function toggleGroupSelection(groupName: string) {
		const groupLocs = groupedLocations.groups.get(groupName) ?? [];
		const allInGroup = groupLocs.every((l) => selectedIds.includes(l.id));
		if (allInGroup) {
			selectedIds = selectedIds.filter((id) => !groupLocs.some((l) => l.id === id));
		} else {
			const newIds = groupLocs.map((l) => l.id).filter((id) => !selectedIds.includes(id));
			selectedIds = [...selectedIds, ...newIds];
		}
		allSelected = selectedIds.length === locations.length;
	}
</script>

<div class="flex gap-6">
	<!-- Sidebar: Desktop only -->
	<LocationsRail
		{locations}
		{selectedIds}
		{groupedLocations}
		{openGroups}
		{allSelected}
		onToggleAll={toggleAll}
		onToggleLocation={toggleLocation}
		onToggleGroup={toggleGroup}
		onToggleGroupSelection={toggleGroupSelection}
		onShowWeather={showWeather}
		onNewLocation={() => (showNewLocDialog = true)}
	/>

	<!-- Content -->
	<div class="min-w-0 flex-1 space-y-6">
		<h1 class="text-2xl font-bold">Orts-Vergleich</h1>

		<PresetHeader
			bind:compareDate={targetDate}
			bind:twStart
			bind:twEnd
			bind:forecastHours
			bind:activityProfile
			locationCount={allSelected ? locations.length : selectedIds.length}
			{loading}
			onrun={runComparison}
			onsavebriefing={() => (showSaveAsSubDialog = true)}
			onprofilechange={() => (profileManuallyOverridden = true)}
		/>

		{#if error}
			<p class="text-sm text-destructive">{error}</p>
		{/if}

		{#if loading}
			<Card.Root>
				<Card.Content class="py-12 text-center text-muted-foreground">
					Wetterdaten werden geladen… Das kann bis zu 30 Sekunden dauern.
				</Card.Content>
			</Card.Root>
		{/if}

		<!-- Results -->
		{#if result && !loading}
			{#if result.winner && result.rows[0]}
				<RecommendationBanner
					winner={result.winner}
					winnerRow={result.rows[0]}
					{locations}
				/>
			{/if}

			{#if result.rows.length > 0}
				<CompareMatrix rows={result.rows} {locations} profile={activityProfile} />
			{/if}

			{#if result.hourly && Object.keys(result.hourly).length > 0}
				<HourlyMatrix hourly={result.hourly} {locations} rows={result.rows} />
			{/if}

			{#if !showSaveAsSubDialog}
				<div class="mt-4 flex justify-end">
					<Btn variant="outline" onclick={() => (showSaveAsSubDialog = true)}>
						Als Auto-Report speichern
					</Btn>
				</div>
			{/if}
		{/if}

		<!-- Weather Drill-Down -->
		{#if weatherLocationId}
			<Card.Root>
				<Card.Header>
					<Card.Title>Wetter: {weatherLocationName}</Card.Title>
				</Card.Header>
				<Card.Content class="space-y-4">
					<div class="flex items-center gap-3">
						<select
							bind:value={weatherHours}
							class="flex h-8 w-24 rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm"
						>
							<option value="24">24h</option>
							<option value="48">48h</option>
							<option value="72">72h</option>
							<option value="120">120h</option>
						</select>
						<Btn
							variant="primary"
							size="sm"
							onclick={() => showWeather(weatherLocationId!)}
							disabled={weatherLoading}
						>
							{weatherLoading ? 'Lädt…' : 'Laden'}
						</Btn>
						<Btn
							variant="ghost"
							size="sm"
							onclick={() => {
								weatherLocationId = null;
								weatherForecast = null;
							}}
						>
							← Zurück
						</Btn>
					</div>

					{#if weatherLoading}
						<p class="text-sm text-muted-foreground">Wetterdaten werden geladen…</p>
					{/if}

					{#if weatherForecast && !weatherLoading}
						<div class="overflow-x-auto">
							<Table.Root>
								<Table.Header>
									<Table.Row>
										<Table.Head>Zeit</Table.Head>
										<Table.Head></Table.Head>
										<Table.Head>Temp</Table.Head>
										<Table.Head>Wind</Table.Head>
										<Table.Head>Böen</Table.Head>
										<Table.Head>Regen</Table.Head>
										<Table.Head>Wolken</Table.Head>
									</Table.Row>
								</Table.Header>
								<Table.Body>
									{@const rows = weatherForecast.data ?? []}
									{#each rows as row, i}
										{@const dateStr = formatDate(row.ts)}
										{@const prevDateStr = i > 0 ? formatDate(rows[i - 1].ts) : ''}
										{#if dateStr !== prevDateStr}
											<Table.Row>
												<Table.Cell colspan={7} class="bg-muted/50 py-1 text-xs font-medium">
													{dateStr}
												</Table.Cell>
											</Table.Row>
										{/if}
										<Table.Row>
											<Table.Cell class="text-xs">{formatTime(row.ts)}</Table.Cell>
											<Table.Cell>{weatherEmoji(row.wmo_code, row.is_day)}</Table.Cell>
											<Table.Cell class="text-xs">
												{row.t2m_c != null ? `${row.t2m_c.toFixed(1)}°` : '-'}
											</Table.Cell>
											<Table.Cell class="text-xs">
												{row.wind10m_kmh != null ? `${Math.round(row.wind10m_kmh)}` : '-'}
											</Table.Cell>
											<Table.Cell class="text-xs">
												{row.gust_kmh != null ? `${Math.round(row.gust_kmh)}` : '-'}
											</Table.Cell>
											<Table.Cell class="text-xs">
												{row.precip_1h_mm != null && row.precip_1h_mm > 0
													? `${row.precip_1h_mm.toFixed(1)}`
													: '-'}
											</Table.Cell>
											<Table.Cell class="text-xs">
												{row.cloud_total_pct != null ? `${row.cloud_total_pct}%` : '-'}
											</Table.Cell>
										</Table.Row>
									{/each}
								</Table.Body>
							</Table.Root>
						</div>
						{#if weatherForecast.meta}
							<p class="text-xs text-muted-foreground" data-testid="forecast-meta">
								{weatherForecast.meta.provider} · {weatherForecast.meta.model}
							</p>
						{/if}
					{/if}
				</Card.Content>
			</Card.Root>
		{/if}

		<!-- Auto-Reports: show when no comparison active -->
		{#if !result && !loading && !weatherLocationId}
			<div class="space-y-3">
				<div class="flex items-center justify-between">
					<h2 class="text-lg font-semibold">Deine Auto-Reports</h2>
					<a href="/subscriptions" class="text-sm text-primary hover:underline">Verwalten &rarr;</a>
				</div>
				{#if subscriptions.length > 0}
					{#each subscriptions as sub}
						<Card.Root data-testid="auto-report-card">
							<Card.Content class="flex items-center justify-between py-3">
								<div>
									<p class="font-medium">{sub.name}</p>
									<p class="text-sm text-muted-foreground">
										{scheduleLabel(sub)} &middot; {locationsLabel(sub)}
									</p>
								</div>
								<Badge variant={sub.enabled ? 'default' : 'secondary'}>
									{sub.enabled ? 'An' : 'Aus'}
								</Badge>
							</Card.Content>
						</Card.Root>
					{/each}
				{:else}
					<p class="text-sm text-muted-foreground">Noch keine Auto-Reports konfiguriert.</p>
				{/if}
			</div>
		{/if}
	</div>
</div>

<!-- New Location Dialog -->
<Dialog.Root
	open={showNewLocDialog}
	onOpenChange={(open) => {
		if (!open) showNewLocDialog = false;
	}}
>
	<Dialog.Content class="max-h-[80vh] max-w-lg overflow-y-auto">
		<Dialog.Header>
			<Dialog.Title>Neue Location</Dialog.Title>
		</Dialog.Header>
		<NewLocationWizard
			{locations}
			onsave={handleNewLocSave}
			oncancel={() => (showNewLocDialog = false)}
		/>
	</Dialog.Content>
</Dialog.Root>

<!-- Save as Subscription Dialog -->
<Dialog.Root
	open={showSaveAsSubDialog}
	onOpenChange={(open) => {
		if (!open) {
			showSaveAsSubDialog = false;
			saveSubError = null;
		}
	}}
>
	<Dialog.Content class="max-h-[80vh] max-w-lg overflow-y-auto">
		<Dialog.Header>
			<Dialog.Title>Als Auto-Report speichern</Dialog.Title>
		</Dialog.Header>
		{#if saveSubError}
			<p class="mb-2 text-sm text-destructive">{saveSubError}</p>
		{/if}
		{#if showSaveAsSubDialog}
			<SubscriptionForm
				subscription={prefilledSub}
				{locations}
				onsave={handleSaveAsSub}
				oncancel={() => {
					showSaveAsSubDialog = false;
					saveSubError = null;
				}}
			/>
		{/if}
	</Dialog.Content>
</Dialog.Root>
