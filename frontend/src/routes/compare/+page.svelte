<script lang="ts">
	// Issue #455 — Compare-Hauptbühne: 3-Spalten-Layout (Rail | Hauptbereich | Sidepanel).
	// Spec: docs/specs/modules/issue_455_compare_main_stage.md

	import { goto, invalidateAll } from '$app/navigation';
	import { today } from '$lib/components/trip-wizard/wizardHelpers.js';
	import { groupLocations } from '$lib/components/compare/locationHelpers.js';
	import { api } from '$lib/api.js';
	import { toCompareProfile } from '$lib/types.js';
	import type { ActivityProfile, CompareResult, CompareMetrics, CompareRow, RankingEntry, Location, Group } from '$lib/types.js';
	import LocationsRail from '$lib/components/compare/LocationsRail.svelte';
	import PresetHeader from '$lib/components/compare/PresetHeader.svelte';
	import RecommendationBanner from '$lib/components/compare/RecommendationBanner.svelte';
	import CompareMatrix from '$lib/components/compare/CompareMatrix.svelte';
	import HourlyMatrix from '$lib/components/compare/HourlyMatrix.svelte';
	import AutoReportsOverview from '$lib/components/compare/AutoReportsOverview.svelte';
	import NewLocationWizard from '$lib/components/compare/NewLocationWizard.svelte';

	let { data } = $props();
	let locations: Location[] = $state(data.locations ?? []);
	let groups: Group[] = $state(data.groups ?? []);

	let selectedIds: string[]        = $state([]);
	let openGroups: Set<string>      = $state(new Set());
	let compareDate: string          = $state(today());
	let twStart: number              = $state(9);
	let twEnd: number                = $state(16);
	let forecastHours: number        = $state(48);
	let activityProfile: ActivityProfile = $state('allgemein');
	let result: CompareResult | null = $state(null);
	let loading: boolean             = $state(false);
	let error: string | null         = $state(null);
	let wizardOpen: boolean          = $state(false);

	let groupedLocations = $derived(groupLocations(locations, groups));
	let allSelected = $derived(selectedIds.length === locations.length && locations.length > 0);
	let matrixRows: CompareRow[] = $derived.by(() => {
		if (!result) return [];
		return result.ranking.map((r, i) => ({
			location_id: r.location_id,
			score: r.score,
			rank: i + 1,
			metrics: (result!.matrix.find((m) => m.location_id === r.location_id)?.metrics ?? {}) as CompareMetrics,
		}));
	});
	let topEntry: RankingEntry | null = $derived.by(() => result?.ranking?.[0] ?? null);

	// Event-Handler für LocationsRail
	function handleToggleAll() {
		selectedIds = allSelected ? [] : locations.map((l) => l.id);
	}
	function handleToggleLocation(id: string) {
		selectedIds = selectedIds.includes(id)
			? selectedIds.filter((x) => x !== id)
			: [...selectedIds, id];
	}
	function handleToggleGroup(id: string) {
		const next = new Set(openGroups);
		if (next.has(id)) {
			next.delete(id);
		} else {
			next.add(id);
		}
		openGroups = next;
	}
	function handleToggleGroupSelection(id: string) {
		const inGroup = locations.filter((l) => l.group_id === id).map((l) => l.id);
		const allIn = inGroup.every((x) => selectedIds.includes(x));
		selectedIds = allIn
			? selectedIds.filter((x) => !inGroup.includes(x))
			: [...new Set([...selectedIds, ...inGroup])];
	}
	function handleShowWeather(_id: string) {
		/* no-op: Wetter-Route leitet zurück */
	}
	function handleEditLocation(_loc: Location) {
		goto('/locations');
	}
	function handleNewLocation() {
		wizardOpen = true;
	}
	async function handleGroupCreated(_group: Group) {
		await invalidateAll();
	}
	function handleSaveBriefing() {
		goto('/compare/new');
	}

	async function runComparison() {
		if (selectedIds.length < 2) return;
		error = null;
		loading = true;
		try {
			result = await api.post<CompareResult>('/api/compare/run', {
				location_ids: selectedIds,
				date_from:    compareDate,
				date_to:      compareDate,
				hour_from:    twStart,
				hour_to:      twEnd,
				profile:      toCompareProfile(activityProfile),
			});
		} catch (e) {
			error = (e as { error?: string }).error ?? 'Vergleich fehlgeschlagen';
		} finally {
			loading = false;
		}
	}
</script>

<!-- Desktop: 3-Spalten-Grid -->
<div
	class="hidden desktop:grid h-full gap-4 p-4"
	style="grid-template-columns: 320px 1fr 320px"
	data-testid="compare-main-stage"
>
	<!-- Linke Spalte: Standort-Rail -->
	<LocationsRail
		{locations}
		{groups}
		{selectedIds}
		{groupedLocations}
		{openGroups}
		{allSelected}
		onToggleAll={handleToggleAll}
		onToggleLocation={handleToggleLocation}
		onToggleGroup={handleToggleGroup}
		onToggleGroupSelection={handleToggleGroupSelection}
		onShowWeather={handleShowWeather}
		onEditLocation={handleEditLocation}
		onNewLocation={handleNewLocation}
		onGroupCreated={handleGroupCreated}
	/>

	<!-- Mittlere Spalte: Vergleichsbereich -->
	<div class="flex flex-col gap-4 overflow-y-auto" data-testid="compare-center">
		<PresetHeader
			bind:compareDate
			bind:twStart
			bind:twEnd
			bind:forecastHours
			bind:activityProfile
			locationCount={selectedIds.length}
			{loading}
			onrun={runComparison}
			onsavebriefing={handleSaveBriefing}
		/>

		{#if selectedIds.length < 2 && !result}
			<div
				class="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground"
				data-testid="compare-empty-hint"
			>
				Wähle mindestens 2 Orte aus, um den Vergleich zu starten.
			</div>
		{/if}

		{#if error}
			<div
				class="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive"
				data-testid="compare-error"
			>
				{error}
			</div>
		{/if}

		{#if topEntry}
			<RecommendationBanner
				{topEntry}
				{locations}
			/>
		{/if}

		{#if matrixRows.length}
			<CompareMatrix
				rows={matrixRows}
				{locations}
				profile={activityProfile}
			/>
		{/if}

		{#if result?.stunden_verlauf?.length}
			<HourlyMatrix
				stunden_verlauf={result.stunden_verlauf}
				{locations}
			/>
		{/if}
	</div>

	<!-- Rechte Spalte: Auto-Briefings Sidepanel -->
	<div class="overflow-y-auto" data-testid="compare-sidebar">
		<AutoReportsOverview presets={data.presets} />
	</div>
</div>

<!-- Mobile-Fallback -->
<div
	class="desktop:hidden p-6 text-center text-sm text-muted-foreground"
	data-testid="compare-mobile-fallback"
>
	<p>Orts-Vergleich ist auf dem Desktop verfügbar.</p>
</div>

<!-- Neuen Standort anlegen -->
{#if wizardOpen}
	<NewLocationWizard
		{locations}
		{groups}
		onsave={(loc: Location) => {
			locations = [...locations, loc];
			wizardOpen = false;
		}}
		oncancel={() => {
			wizardOpen = false;
		}}
	/>
{/if}
