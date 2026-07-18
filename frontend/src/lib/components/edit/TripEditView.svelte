<script lang="ts">
	import type { Trip, Stage, AlertRule, ReportConfig, ActivityType } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import Select from '$lib/components/ui/select/Select.svelte';
	import { goto } from '$app/navigation';
	import EditRouteSection from './EditRouteSection.svelte';
	// Issue #587: WeatherMetricsTab ersetzt WeatherSummaryCard im Wetter-Tab
	import WeatherMetricsTab from '$lib/components/shared/WeatherMetricsTab.svelte';
	import EditReportConfigSection from './EditReportConfigSection.svelte';
	import { AlertRulesEditor } from '$lib/components/organisms';
	import EtappenStrip from '$lib/components/trip-detail/waypoints/EtappenStrip.svelte';
	import EditStagesPanelNew from './EditStagesPanelNew.svelte';
	import { normalizeAlertMetric } from '$lib/utils/alertMetricLabels';
	import { computeTripStats } from '$lib/utils/tripStats';
	import { formatDateRange } from '$lib/utils/tripHero';
	import { getReportSchedule } from '$lib/utils/rightColumn';

	interface Props {
		trip: Trip;
	}
	let { trip }: Props = $props();

	// State: tiefe Kopie damit Cancel ohne Persistenz auch State verwirft
	let tripName = $state(trip.name);
	let activityType = $state<ActivityType | undefined>(trip.activity);
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
	const activeAlertChannels = $derived(
		(['email', 'telegram', 'sms'] as const).filter(
			(c) => reportConfig?.[`send_${c}` as 'send_email' | 'send_telegram' | 'send_sms']
		)
	);

	// Tab options without inline counts — badges rendered as separate elements
	const tabOptions = $derived([
		{ id: 'route',       label: 'Route',                  badge: '',                           accent: false },
		{ id: 'etappen',     label: 'Etappen & Wegpunkte',    badge: String(stats.stages),         accent: false },
		{ id: 'wetter',      label: 'Wetter',                 badge: '',                           accent: false },
		{ id: 'reports',     label: 'Reports',                badge: '',                           accent: false },
		{ id: 'alarmregeln', label: 'Alarmregeln',            badge: String(alertRules.length),    accent: true },
	]);

	// Factory Pattern fuer Handler (Safari-Closure-Binding-Schutz, siehe CLAUDE.md)
	function makeSaveHandler() {
		return async function doSave() {
			saveError = null;
			saving = true;
			try {
				await api.put(`/api/trips/${trip.id}`, {
					name: tripName,
					activity: activityType,
					stages: stages,
					report_config: reportConfig,
					alert_rules: alertRules,
				});
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

<div data-testid="trip-edit-view" style="position: relative; padding: 0;">
	<!-- Breadcrumb -->
	<nav data-testid="edit-breadcrumb" class="mono" style="font-size: 11px; color: var(--g-ink-3); padding: 16px 40px; border-bottom: 1px solid var(--g-rule-soft); letter-spacing: 0.06em;">
		<span style="opacity: 0.6;">Trips</span> / <span style="opacity: 0.6;">{trip.shortcode ?? (trip as Trip & { shortCode?: string }).shortCode ?? trip.name}</span> / <span>Bearbeiten</span>
	</nav>

	<!-- Header: H1 + Buttons oben rechts -->
	<div data-testid="edit-header" style="display: flex; align-items: flex-start; justify-content: space-between; padding: 20px 40px 16px; gap: 16px; flex-wrap: wrap;">
		<h1 data-testid="edit-trip-title" style="font-size: 24px; font-weight: 600; margin: 0;">
			{trip.name}
		</h1>
		<div data-testid="edit-header-actions" style="display: flex; gap: 8px; align-items: center; flex-shrink: 0;">
			<button
				type="button"
				data-testid="edit-cancel-btn"
				style="padding: 10px 16px; border-radius: 6px; border: 1px solid var(--g-rule); background: transparent; font-size: 14px; font-weight: 500; cursor: pointer;"
				onclick={onCancel}
				disabled={saving}
			>
				Abbrechen
			</button>
			<button
				type="button"
				data-testid="edit-save-btn"
				style="padding: 10px 16px; border-radius: 6px; border: none; background: var(--g-ink); color: var(--g-paper); font-size: 14px; font-weight: 500; cursor: pointer;"
				onclick={onSave}
				disabled={saving}
			>
				{saving ? 'Speichere…' : 'Speichern'}
			</button>
		</div>
	</div>

	<!-- Stats-Karte (GESAMT / ZEITRAUM) -->
	<div data-testid="edit-stats-card" style="display: flex; gap: 32px; padding: 18px 40px; border-bottom: 1px solid var(--g-rule-soft); align-items: center; background: var(--g-card); margin-bottom: 0;">
		<div>
			<div style="font-size: 10px; font-family: var(--g-font-mono); color: var(--g-ink-3); letter-spacing: 0.08em; margin-bottom: 4px;">GESAMT</div>
			<div style="font-size: 18px; font-weight: 600;" data-testid="edit-stats-distance">{stats.kmTotal.toFixed(1)} km · ↑{stats.ascentM} m</div>
		</div>
		<div>
			<div style="font-size: 10px; font-family: var(--g-font-mono); color: var(--g-ink-3); letter-spacing: 0.08em; margin-bottom: 4px;">ZEITRAUM</div>
			<div style="font-size: 18px; font-weight: 600;" data-testid="edit-stats-daterange">{dateRange} · {stats.stages} Tage</div>
		</div>
		<div style="margin-left: auto; display: flex; align-items: center; gap: 12px;">
			<div style="display: flex; align-items: center; gap: 8px;">
				<label for="activity-select" style="font-size: 10px; font-family: var(--g-font-mono); color: var(--g-ink-3); letter-spacing: 0.08em;">AKTIVITÄT</label>
				<Select
					id="activity-select"
					data-testid="edit-activity-dropdown"
					value={activityType ?? ''}
					onchange={(e) => { activityType = (e.target as HTMLSelectElement).value as ActivityType || undefined; }}
					style="font-size: 13px;"
				>
					<option value="trekking">Trekking</option>
					<option value="skitour">Skitour</option>
					<option value="hochtour">Hochtour</option>
					<option value="klettersteig">Klettersteig</option>
					<option value="mtb">MTB</option>
					<option value="fahrrad_15">Fahrrad (15 km/h)</option>
					<option value="fahrrad_20">Fahrrad (20 km/h)</option>
					<option value="fahrrad_25">Fahrrad (25 km/h)</option>
				</Select>
			</div>
			{#if reportSchedule.enabled}
				<span data-testid="edit-stats-reports-badge" style="font-size: 10px; font-family: var(--g-font-mono); letter-spacing: 0.08em; padding: 4px 10px; border-radius: 99px; border: 1px solid var(--g-ink-3); color: var(--g-ink-3);">REPORTS KONFIGURIERT</span>
			{/if}
		</div>
	</div>

	<!-- Tab-Leiste (eigene Implementierung analog JSX TripEditTabBar) -->
	<div data-testid="edit-tabs" style="border-bottom: 1px solid var(--g-rule); padding: 0 40px; display: flex; gap: 0;">
		{#each tabOptions as tab}
			<button
				type="button"
				data-testid="edit-tab-{tab.id}"
				onclick={() => (activeTab = tab.id as TabId)}
				style="padding: 12px 16px; cursor: pointer; font-size: 13px; font-weight: {activeTab === tab.id ? 600 : 500}; color: {activeTab === tab.id ? 'var(--g-ink)' : 'var(--g-ink-3)'}; border: none; background: transparent; border-bottom: {activeTab === tab.id ? '2px solid var(--g-accent)' : '2px solid transparent'}; margin-bottom: -1px; display: inline-flex; align-items: center; gap: 6px;"
			>
				{tab.label}
				{#if tab.badge}
					<span data-testid="edit-tab-badge-{tab.id}" style="font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 3px; background: {tab.accent ? 'var(--g-accent)' : 'var(--g-paper-deep)'}; color: {tab.accent ? '#fff' : 'var(--g-ink-3)'}; font-family: var(--g-font-mono);">{tab.badge}</span>
				{/if}
			</button>
		{/each}
	</div>

	<!-- Tab-Inhalte -->
	<div data-testid="edit-tab-content">
		{#if activeTab === 'route'}
			<EditRouteSection bind:tripName bind:stages mode="edit" />
		{:else if activeTab === 'etappen'}
			<EditStagesPanelNew bind:stages tripId={trip.id} showSave={false} activityType={activityType} />
		{:else if activeTab === 'wetter'}
			<WeatherMetricsTab {trip} />
		{:else if activeTab === 'reports'}
			<EditReportConfigSection bind:reportConfig mode="edit" />
		{:else if activeTab === 'alarmregeln'}
			<AlertRulesEditor bind:rules={alertRules} activeChannels={activeAlertChannels} />
		{/if}
	</div>

	<!-- Fehleranzeige -->
	{#if saveError}
		<div data-testid="edit-save-error"
			style="margin: 16px 40px; padding: 12px; border-radius: 6px; background: rgba(179,74,42,0.1); color: var(--g-danger, #b34a2a); font-size: 14px;">
			{saveError}
		</div>
	{/if}
</div>
