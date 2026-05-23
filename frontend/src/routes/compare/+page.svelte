<script lang="ts">
	// Issue #251 — Compare-Hauptbühne (Frontend).
	//
	// Spec: docs/specs/modules/issue_251_compare_main_stage.md
	// API: POST /api/compare/run (Go-Engine, Issue #250) ersetzt GET /api/compare (Python-Proxy)

	import type {
		Location,
		Group,
		Subscription,
		ForecastResponse,
		ActivityProfile,
		CompareResult,
	} from '$lib/types.js';
	import { toCompareProfile } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { invalidateAll } from '$app/navigation';
	import { Btn } from '$lib/components/ui/btn/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import SubscriptionForm from '$lib/components/SubscriptionForm.svelte';
	import LocationForm from '$lib/components/LocationForm.svelte';
	import LocationsRail from '$lib/components/compare/LocationsRail.svelte';
	import NewLocationWizard from '$lib/components/compare/NewLocationWizard.svelte';
	import { groupLocations } from '$lib/components/compare/locationHelpers.js';
	import PresetHeader from '$lib/components/compare/PresetHeader.svelte';
	import RecommendationBanner from '$lib/components/compare/RecommendationBanner.svelte';
	import CompareMatrix from '$lib/components/compare/CompareMatrix.svelte';
	import HourlyMatrix from '$lib/components/compare/HourlyMatrix.svelte';
	import CompareSubscriptionsPanel from '$lib/components/compare/CompareSubscriptionsPanel.svelte';
	import { WIcon } from '$lib/components/ui/wicon/index.js';
	import { wmoToWIconKind } from '$lib/utils/weatherUtils.js';
	import { Select } from '$lib/components/ui/select';

	let { data } = $props();

	let locations: Location[] = $state(data.locations);
	let groups: Group[] = $state(data.groups ?? []);
	let subscriptions: Subscription[] = $state(data.subscriptions ?? []);
	let selectedIds = $state<string[]>(locations.map((l) => l.id));

	// Nach invalidateAll() (Location-Edit, Gruppen-Anlegen) liefert SvelteKit ein
	// frisches `data`. Lokalen State synchronisieren, ohne die aktuelle Auswahl zu
	// verlieren (nur noch existierende IDs behalten).
	$effect(() => {
		locations = data.locations;
		groups = data.groups ?? [];
		subscriptions = data.subscriptions ?? [];
	});

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
	let showLocationsSheet = $state(false);
	let editingLocation = $state<Location | null>(null);
	let locationEditOpen = $state(false);

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
		if (loc.group_id && !openGroups.has(loc.group_id)) {
			openGroups = new Set([...openGroups, loc.group_id]);
		}
		showNewLocDialog = false;
	}

	function handleEditLocation(loc: Location) {
		editingLocation = loc;
		locationEditOpen = true;
	}

	// Read-Modify-Write: bestehende Location-Felder bleiben erhalten, nur das
	// vom Edit-Dialog gelieferte vollstaendige Objekt (inkl. group_id) wird per
	// PUT persistiert. Danach invalidateAll() holt den frischen Stand vom Backend.
	async function handleLocationSave(updated: Location) {
		try {
			await api.put<Location>(`/api/locations/${updated.id}`, updated);
			locationEditOpen = false;
			editingLocation = null;
			await invalidateAll();
		} catch (e: unknown) {
			const body = e as { detail?: string; error?: string };
			error = body?.detail ?? body?.error ?? 'Fehler beim Speichern der Location';
		}
	}

	function handleGroupCreated(group: Group) {
		// Neue Gruppe sofort aufgeklappt anzeigen (sonst rendert sie nach
		// invalidateAll() eingeklappt, da nicht in openGroups). Backend hat die
		// Gruppe persistiert; frischen Stand inkl. ggf. backfilled group_id-Migration
		// vom Server holen.
		openGroups = new Set([...openGroups, group.id]);
		invalidateAll();
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

	// Grouped locations for sidebar (Issue #301: Group-Entity via group_id).
	let groupedLocations = $derived(groupLocations(locations, groups));

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

	// AC-9: initial alle Gruppen aufgeklappt (Set der group.id).
	let openGroups = $state<Set<string>>(new Set(groups.map((g) => g.id)));

	function toggleGroup(groupId: string) {
		const next = new Set(openGroups);
		if (next.has(groupId)) {
			next.delete(groupId);
		} else {
			next.add(groupId);
		}
		openGroups = next;
	}

	function toggleGroupSelection(groupId: string) {
		const section = groupedLocations.sections.find((s) => s.group.id === groupId);
		const groupLocs = section?.locations ?? [];
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
	<div class="hidden desktop:flex shrink-0">
		<LocationsRail
			{locations}
			{groups}
			{selectedIds}
			{groupedLocations}
			{openGroups}
			{allSelected}
			onToggleAll={toggleAll}
			onToggleLocation={toggleLocation}
			onToggleGroup={toggleGroup}
			onToggleGroupSelection={toggleGroupSelection}
			onShowWeather={showWeather}
			onEditLocation={handleEditLocation}
			onNewLocation={() => (showNewLocDialog = true)}
			onGroupCreated={handleGroupCreated}
		/>
	</div>

	<!-- Content -->
	<div class="min-w-0 flex-1 space-y-6">
		<h1 class="text-2xl font-bold">Orts-Vergleich</h1>

		<div data-testid="compare-mobile-chip-row" class="desktop:hidden space-y-2">
			{#if locations.length > 0}
				<div class="flex gap-2 overflow-x-auto pb-1">
					{#each locations.filter((l) => allSelected || selectedIds.includes(l.id)) as loc}
						<button
							class="shrink-0 rounded-full border border-border bg-muted px-3 py-1 text-xs"
							onclick={() => toggleLocation(loc.id)}
						>
							{loc.name} ×
						</button>
					{/each}
				</div>
			{/if}
			<Btn
				data-testid="compare-mobile-open-sheet"
				variant="outline"
				size="sm"
				onclick={() => (showLocationsSheet = true)}
			>
				Orte wählen ({allSelected ? locations.length : selectedIds.length})
			</Btn>
		</div>

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
						<Select
							bind:value={weatherHours}
							class="w-24"
						>
							<option value="24">24h</option>
							<option value="48">48h</option>
							<option value="72">72h</option>
							<option value="120">120h</option>
						</Select>
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
											<Table.Cell><WIcon kind={wmoToWIconKind(row.wmo_code, row.is_day)} size={14} /></Table.Cell>
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
			<CompareSubscriptionsPanel
				{subscriptions}
				onsavebriefing={() => (showSaveAsSubDialog = true)}
			/>
		{/if}
	</div>
</div>

<!-- Mobile: Locations Bottom-Sheet -->
{#if showLocationsSheet}
	<div
		class="fixed inset-0 z-[70] bg-black/50 desktop:hidden"
		onclick={() => (showLocationsSheet = false)}
		role="presentation"
	></div>
	<div
		data-testid="compare-locations-sheet"
		class="fixed bottom-0 left-0 right-0 z-[75] desktop:hidden rounded-t-2xl border-t overflow-y-auto"
		style="background: var(--g-paper-deep); border-color: var(--g-rule-soft); padding-bottom: env(safe-area-inset-bottom); max-height: 85vh;"
		role="dialog"
		aria-modal="true"
		aria-label="Orte wählen"
	>
		<div class="flex justify-center pt-3 pb-1">
			<div class="w-10 h-1 rounded-full bg-muted-foreground/25"></div>
		</div>
		<div class="px-4 py-3">
			<LocationsRail
				{locations}
				{groups}
				{selectedIds}
				{groupedLocations}
				{openGroups}
				{allSelected}
				onToggleAll={toggleAll}
				onToggleLocation={toggleLocation}
				onToggleGroup={toggleGroup}
				onToggleGroupSelection={toggleGroupSelection}
				onShowWeather={(id) => { showLocationsSheet = false; showWeather(id); }}
				onEditLocation={(loc) => { showLocationsSheet = false; handleEditLocation(loc); }}
				onNewLocation={() => { showLocationsSheet = false; showNewLocDialog = true; }}
				onGroupCreated={handleGroupCreated}
			/>
		</div>
	</div>
{/if}

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
			{groups}
			onsave={handleNewLocSave}
			oncancel={() => (showNewLocDialog = false)}
		/>
	</Dialog.Content>
</Dialog.Root>

<!-- Location Edit Dialog (Issue #301: Klick auf Ortsname) -->
<Dialog.Root
	open={locationEditOpen}
	onOpenChange={(open) => {
		if (!open) {
			locationEditOpen = false;
			editingLocation = null;
		}
	}}
>
	<Dialog.Content class="max-h-[80vh] max-w-lg overflow-y-auto">
		<Dialog.Header>
			<Dialog.Title>Ort bearbeiten</Dialog.Title>
		</Dialog.Header>
		{#if editingLocation}
			<LocationForm
				location={editingLocation}
				{locations}
				{groups}
				onsave={handleLocationSave}
				oncancel={() => {
					locationEditOpen = false;
					editingLocation = null;
				}}
			/>
		{/if}
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
