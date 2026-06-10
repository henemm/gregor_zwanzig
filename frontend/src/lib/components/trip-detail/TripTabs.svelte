<script lang="ts">
	import { goto } from '$app/navigation';
	import { Segmented } from '$lib/components/atoms';
	import HubOverview from './HubOverview.svelte';
	import BriefingScheduleTab from './BriefingScheduleTab.svelte';
	import WeatherMetricsTab from './WeatherMetricsTab.svelte';
	import AlertsTab from '$lib/components/alerts-tab/AlertsTab.svelte';
	import BriefingsTab from '$lib/components/briefings-tab/BriefingsTab.svelte';
	import {
		EmailIframe,
		SmsPhoneFrame,
		defaultReportType,
		type ReportType
	} from '$lib/components/preview';
	import type { Trip, Stage } from '$lib/types';
	import EditStagesSection from '../edit/EditStagesSection.svelte';

	interface Badges {
		overview?: number;
		stages?: number;
		weather?: number;
		briefings?: number;
		alerts?: number;
		preview?: number;
	}

	interface Props {
		initialTab?: string;
		badges?: Badges;
		trip?: Trip;
		onTripUpdate?: (updated: Trip) => void;
	}

	let { initialTab = 'overview', badges: badgesProp = {}, trip, onTripUpdate }: Props = $props();

	// Lokale Kopie der Etappen für den Stages-Tab (EditStagesSection braucht $bindable).
	let localStages = $state<Stage[]>(trip?.stages ?? []);

	// Issue #302 — Auto-Badges aus Trip ableiten (Etappenanzahl + enabled Alerts).
	// Explizite Werte in der `badges` Prop ueberschreiben die Auto-Ableitung.
	const badges = $derived<Badges>({
		stages: badgesProp.stages ?? trip?.stages?.length ?? 0,
		alerts: badgesProp.alerts ?? (trip?.alert_rules ?? []).filter((r) => r.enabled).length,
		overview: badgesProp.overview,
		weather: badgesProp.weather,
		briefings: badgesProp.briefings,
		preview: badgesProp.preview
	});

	// Issue #529 — Kanonische Tab-Namen aus nav-map.jsx (Single Source of Truth):
	//   weather   -> "Wetter-Metriken" (war: "Wetter-Briefing")
	//   briefings -> "Briefing-Zeitplan" (war: "Reports & Kanäle")
	//   alerts    -> "Alerts" (war: "Alarmregeln")
	// `value`-Schlüssel bleiben unverändert — URL-Parameter und Test-IDs nicht betroffen.
	const TABS = [
		{ value: 'overview', label: 'Übersicht' },
		{ value: 'stages', label: 'Etappen & Wegpunkte' },
		{ value: 'weather', label: 'Wetter-Metriken' },
		{ value: 'briefings', label: 'Briefing-Zeitplan' },
		{ value: 'alerts', label: 'Alerts' },
		{ value: 'preview', label: 'Vorschau' }
	] as const;

	const PLACEHOLDERS: Record<string, string> = {
		overview: 'Inhalt folgt mit Issue #154 (Hero) + #156 (Höhenprofil) + #157 (Stage-Liste)',
		stages: 'Inhalt folgt mit Epic #137 (Wegpunkt-Editor)',
		preview: 'Inhalt folgt mit Issue #189 (Vorschau-Integration)'
	};

	const segmentedOptions = $derived(
		TABS.map(tab => ({
			value: tab.value,
			label: tab.label,
			badge: (badges[tab.value] ?? 0) >= 1 ? badges[tab.value] : undefined,
			testid: `trip-detail-tab-${tab.value}`,
			badge_testid: `trip-detail-tab-badge-${tab.value}`,
		}))
	);

	const VALID_VALUES: readonly string[] = TABS.map((t) => t.value);

	function resolve(value: string): string {
		return VALID_VALUES.includes(value) ? value : 'overview';
	}

	// Default 'overview'; $effect setzt sofort beim Mount den korrekten Tab
	// und synchronisiert bei späteren initialTab-Prop-Änderungen
	// (z.B. hash-only navigation ohne Re-Mount).
	let activeTab = $state<string>('overview');
	let previewType = $state<ReportType>(defaultReportType());
	// Issue #483: Vorschau-Tab startet im Demo-Modus (Fixture-Daten), damit
	// die Vorschau auch dann zuverlässig funktioniert, wenn der Trip in der
	// Vergangenheit liegt oder die OpenMeteo-API gerade nicht erreichbar ist.
	let demoMode = $state(true);

	$effect(() => {
		activeTab = resolve(initialTab);
	});

	function handleValueChange(value: string): void {
		activeTab = value;
		// Issue #516: kanonisches URL-Modell — ?tab=<value> statt #hash.
		// replaceState verhindert History-Spam; noScroll + keepFocus erhalten
		// die Keyboard-Navigation und Scroll-Position.
		void goto(`?tab=${value}`, { replaceState: true, noScroll: true, keepFocus: true });
	}
</script>

<div class="trip-tabs" data-testid="trip-detail-tab-list">
	<Segmented options={segmentedOptions} selected={activeTab} onselect={handleValueChange} />
	{#each TABS as tab}
		{#if activeTab === tab.value}
			<div data-testid="trip-detail-panel-{tab.value}">
				{#if tab.value === 'overview' && trip}
					<HubOverview {trip} onJump={handleValueChange} />
				{:else if tab.value === 'stages'}
					{#if trip}
						<EditStagesSection bind:stages={localStages} tripId={trip.id} showSave={true} />
					{/if}
				{:else if tab.value === 'weather' && trip}
					<WeatherMetricsTab {trip} {onTripUpdate} />
				{:else if tab.value === 'alerts' && trip}
					<AlertsTab {trip} />
				{:else if tab.value === 'briefings' && trip}
					<BriefingScheduleTab {trip} {onTripUpdate} />
				{:else if tab.value === 'preview' && trip}
					<div class="preview-shell">
						{#if demoMode}
							<div class="demo-banner" role="status" data-testid="preview-demo-banner">
								<span>Vorschau mit Beispieldaten.</span>
								<button
									type="button"
									class="demo-banner-action"
									onclick={() => (demoMode = false)}
									data-testid="preview-demo-disable"
								>
									Echte Wetterdaten laden
								</button>
							</div>
						{/if}
						<div class="preview-controls" data-testid="preview-controls">
							<label>
								<input type="radio" bind:group={previewType} value="morning" /> Morgen
							</label>
							<label>
								<input type="radio" bind:group={previewType} value="evening" /> Abend
							</label>
						</div>
						<div class="preview-grid">
							<EmailIframe tripId={trip.id} type={previewType} demo={demoMode} />
							<SmsPhoneFrame tripId={trip.id} type={previewType} demo={demoMode} />
						</div>
					</div>
				{:else}
					<p class="p-4 text-sm">{PLACEHOLDERS[tab.value]}</p>
				{/if}
			</div>
		{/if}
	{/each}
</div>

<style>
	.trip-tabs :global([data-slot="segmented"]) {
		display: flex;
		border-bottom: 1px solid var(--g-ink-faint);
	}
	.trip-tabs :global([data-slot="segmented-item"]) {
		position: relative;
		padding: 0.5rem 1rem;
		font-size: 0.875rem;
		font-weight: 500;
		border-bottom: 2px solid transparent;
		background: transparent;
		color: var(--g-ink);
		cursor: pointer;
	}
	/* Override: app.css setzt data-active="true" global auf ink-Hintergrund (WeatherConfigDialog).
	   TripTabs braucht transparenten Hintergrund + ink-Text, nur Unterstrichen. */
	.trip-tabs :global([data-slot="segmented-item"][data-active="true"]) {
		background: transparent;
		color: var(--g-ink);
	}
	.trip-tabs :global([data-slot="segmented-item"][data-state='active']) {
		border-bottom-color: var(--g-accent);
	}
	.trip-tabs :global([data-slot="segmented-badge"]) {
		display: inline-block;
		margin-left: 0.375rem;
		padding: 0.125rem 0.375rem;
		border-radius: 9999px;
		background: var(--g-accent);
		color: white;
		font-size: 0.75rem;
		font-weight: 600;
	}
	.preview-shell {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		padding: 1rem;
	}
	.demo-banner {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 0.625rem 0.875rem;
		background: var(--g-warning-soft, #fef3c7);
		color: var(--g-ink, #1a1a18);
		border: 1px solid var(--g-warning, #f59e0b);
		border-radius: var(--g-r-2, 0.5rem);
		font-size: 0.875rem;
	}
	.demo-banner-action {
		flex-shrink: 0;
		padding: 0.375rem 0.75rem;
		background: var(--g-ink, #1a1a18);
		color: var(--g-paper, #f6f4ee);
		border: 0;
		border-radius: var(--g-r-1, 0.375rem);
		font-size: 0.8125rem;
		font-weight: 500;
		cursor: pointer;
	}
	.demo-banner-action:hover {
		background: var(--g-ink-strong, #000);
	}
	.preview-controls {
		display: flex;
		gap: 1.25rem;
		font-size: 0.875rem;
		color: var(--g-ink, #1a1a18);
	}
	.preview-controls label {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		cursor: pointer;
	}
	.preview-grid {
		display: grid;
		gap: 1.5rem;
		grid-template-columns: minmax(0, 1fr) 360px;
		align-items: start;
	}
	@media (max-width: 960px) {
		.preview-grid {
			grid-template-columns: 1fr;
		}
	}
	@media (max-width: 899px) {
		/* Scrollbares Tab-Band */
		.trip-tabs :global([data-slot="segmented"]) {
			overflow-x: auto;
			white-space: nowrap;
			scrollbar-width: none;
			-ms-overflow-style: none;
			scroll-snap-type: x mandatory;
		}
		.trip-tabs :global([data-slot="segmented"])::-webkit-scrollbar {
			display: none;
		}

		/* Pill-Trigger: einzeilig, nicht schrumpfbar */
		.trip-tabs :global([data-slot="segmented-item"]) {
			white-space: nowrap;
			flex-shrink: 0;
			scroll-snap-align: start;
			border-bottom: none;
			border-radius: var(--g-radius-pill, 99rem);
			padding: 0.375rem 0.875rem;
		}

		/* Aktiver Pill: gefüllt mit Akzentfarbe */
		.trip-tabs :global([data-slot="segmented-item"][data-state='active']) {
			background: var(--g-accent);
			color: var(--g-paper, #f6f4ee);
			border-bottom-color: transparent;
		}
	}
</style>
