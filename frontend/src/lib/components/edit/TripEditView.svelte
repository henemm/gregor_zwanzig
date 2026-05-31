<script lang="ts">
	import type { Trip, Stage, AlertRule, ReportConfig } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { goto } from '$app/navigation';
	import EditRouteSection from './EditRouteSection.svelte';
	import EditStagesPanelNew from './EditStagesPanelNew.svelte';
	import WeatherSummaryCard from './WeatherSummaryCard.svelte';
	import EditReportConfigSection from './EditReportConfigSection.svelte';
	import { AlertRulesEditor } from '$lib/components/organisms';
	import { Segmented } from '$lib/components/atoms';
	import { normalizeAlertMetric } from '$lib/utils/alertMetricLabels';
	import { stripSuggested } from '$lib/utils/waypointEditor';
	import { computeTripStats } from '$lib/utils/tripStats';
	import { formatDateRange } from '$lib/utils/tripHero';
	import { getReportSchedule } from '$lib/utils/rightColumn';

	interface Props {
		trip: Trip;
	}
	let { trip }: Props = $props();

	// State: tiefe Kopie damit Cancel ohne Persistenz auch State verwirft
	let tripName = $state(trip.name);
	let stages: Stage[] = $state(JSON.parse(JSON.stringify(trip.stages ?? [])));
	// Issue #345 / AC-2: display_config wird in dieser Maske NICHT mehr bearbeitet
	// (Wetter-Tab ist der einzige Editor). Kein UI-State, kein Neu-Bauen — der Save
	// reicht den geladenen trip.display_config unverändert durch (Read-Modify-Write).
	let reportConfig: ReportConfig | undefined = $state(
		trip.report_config ? JSON.parse(JSON.stringify(trip.report_config)) : undefined
	);
	let alertRules: AlertRule[] = $state(
		Array.isArray(trip.alert_rules)
			? (JSON.parse(JSON.stringify(trip.alert_rules)) as AlertRule[]).map(r => ({
					...r,
					metric: normalizeAlertMetric(r.metric) ?? r.metric,
				}))
			: []
	);

	type TabId = 'route' | 'etappen' | 'wetter' | 'reports' | 'alarmregeln';
	let activeTab: TabId = $state('etappen');

	let saveError: string | null = $state(null);
	let saving = $state(false);

	// Statistiken (derived, damit bei stages/alertRules-Updates aktualisiert)
	const stats = $derived(computeTripStats(trip));
	const dateRange = $derived(formatDateRange(trip));
	const reportSchedule = $derived(getReportSchedule(trip));

	const tabOptions = $derived([
		{ value: 'route',       label: 'Route',                              testid: 'edit-tab-route' },
		{ value: 'etappen',     label: `Etappen ${stats.stages}`,            testid: 'edit-tab-etappen' },
		{ value: 'wetter',      label: 'Wetter',                             testid: 'edit-tab-wetter' },
		{ value: 'reports',     label: 'Reports',                            testid: 'edit-tab-reports' },
		{ value: 'alarmregeln', label: `Alarmregeln ${alertRules.length}`,   testid: 'edit-tab-alarmregeln' },
	]);

	// Factory Pattern fuer Handler (Safari-Closure-Binding-Schutz, siehe CLAUDE.md)
	function makeSaveHandler() {
		return async function doSave() {
			saveError = null;
			saving = true;
			try {
				const updated: Trip = {
					...trip,
					name: tripName,
					// Issue #296-FE: transientes `suggested`-Flag nicht persistieren.
					stages: stripSuggested(stages),
					// Issue #345 / AC-2: display_config unverändert aus dem geladenen trip
					// durchreichen (via `...trip` bereits enthalten) — KEIN Überschreiben
					// der im Wetter-Tab gesetzten Buckets/Horizonte.
					report_config: reportConfig,
					alert_rules: alertRules,
				};
				await api.put(`/api/trips/${trip.id}`, updated);
				goto('/trips');
			} catch (e: unknown) {
				saveError = (e as { detail?: string })?.detail
					?? (e as { error?: string })?.error
					?? (e instanceof Error ? e.message : 'Speichern fehlgeschlagen');
			} finally {
				saving = false;
			}
		};
	}

	function makeCancelHandler() {
		return function doCancel() {
			goto('/trips');
		};
	}

	function makeTabSelectHandler() {
		return function doSelect(v: string) {
			activeTab = v as TabId;
		};
	}

	const onSave = makeSaveHandler();
	const onCancel = makeCancelHandler();
	const onTabSelect = makeTabSelectHandler();
</script>

<div data-testid="trip-edit-view" class="max-w-5xl mx-auto p-4">
	<!-- Breadcrumb -->
	<nav data-testid="edit-breadcrumb"
		class="text-xs uppercase tracking-wider text-muted-foreground mb-3">
		<a href="/trips" class="hover:underline">MEINE TOUREN</a>
		<span> · TRIP BEARBEITEN</span>
	</nav>

	<!-- Header: H1 + Buttons oben rechts -->
	<div data-testid="edit-header" class="flex items-start justify-between mb-4 gap-4">
		<h1 data-testid="edit-trip-title" class="text-2xl font-semibold">
			{trip.name}
		</h1>
		<div data-testid="edit-header-actions" class="flex gap-2 items-center shrink-0">
			<button
				type="button"
				data-testid="edit-cancel-btn"
				class="inline-flex items-center justify-center rounded-md border border-input bg-background px-4 min-h-[44px] text-sm font-medium hover:bg-accent hover:text-accent-foreground disabled:opacity-50"
				onclick={onCancel}
				disabled={saving}
			>
				Abbrechen
			</button>
			<button
				type="button"
				data-testid="edit-save-btn"
				class="inline-flex items-center justify-center rounded-md bg-primary px-4 min-h-[44px] text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
				onclick={onSave}
				disabled={saving}
			>
				{saving ? 'Speichere…' : 'Speichern'}
			</button>
		</div>
	</div>

	<!-- Horizontale Tabs via Segmented -->
	<div data-testid="edit-tabs" class="mb-4">
		<Segmented options={tabOptions} selected={activeTab} onselect={onTabSelect} />
	</div>

	<!-- Statistik-Karte (immer sichtbar, unabhängig vom Tab) -->
	<div data-testid="edit-stats-card"
		class="flex flex-wrap items-center gap-x-3 gap-y-1 p-3 rounded-md border bg-card text-sm mb-4">
		<span data-testid="edit-stats-distance">{stats.kmTotal.toFixed(1)} km</span>
		<span aria-hidden="true">·</span>
		<span data-testid="edit-stats-ascent">↑{stats.ascentM} m</span>
		<span aria-hidden="true">·</span>
		<span data-testid="edit-stats-daterange">{dateRange}</span>
		<span aria-hidden="true">·</span>
		<span data-testid="edit-stats-days">{stats.stages} Tage</span>
		{#if reportSchedule.enabled}
			<span data-testid="edit-stats-reports-badge"
				class="ml-auto inline-flex items-center rounded-full bg-primary/10 text-primary px-2 py-0.5 text-xs uppercase tracking-wider">
				REPORTS KONFIGURIERT
			</span>
		{/if}
	</div>

	<!-- Tab-Inhalte -->
	<div data-testid="edit-tab-content">
		{#if activeTab === 'route'}
			<EditRouteSection bind:tripName bind:stages mode="edit" />
		{:else if activeTab === 'etappen'}
			<EditStagesPanelNew bind:stages />
		{:else if activeTab === 'wetter'}
			<WeatherSummaryCard displayConfig={trip.display_config} tripId={trip.id} />
		{:else if activeTab === 'reports'}
			<EditReportConfigSection bind:reportConfig mode="edit" />
		{:else if activeTab === 'alarmregeln'}
			<AlertRulesEditor bind:rules={alertRules} />
		{/if}
	</div>

	<!-- Fehleranzeige -->
	{#if saveError}
		<div data-testid="edit-save-error"
			class="mt-4 p-3 rounded bg-destructive/10 text-destructive text-sm">
			{saveError}
		</div>
	{/if}
</div>
