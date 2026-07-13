<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { Segmented } from '$lib/components/atoms';
	import HubOverview from './HubOverview.svelte';
	import BriefingScheduleTab from './BriefingScheduleTab.svelte';
	import WeatherMetricsTab from './WeatherMetricsTab.svelte';
	// Issue #1231: CorridorEditor(Mobile) ersetzt AlertsTab auf Desktop + Mobile.
	// Import von AlertsTab entfernt (Slice 5) — Datei bleibt vorerst bestehen
	// (Aufraeumen inkl. AlertMetricLevelTable/-Row ist Slice-6-Thema, s. Spec).
	import CorridorEditor from '$lib/components/shared/corridor-editor/CorridorEditor.svelte';
	import CorridorEditorMobile from '$lib/components/shared/corridor-editor/CorridorEditorMobile.svelte';
	import BriefingsTab from '$lib/components/briefings-tab/BriefingsTab.svelte';
	import {
		EmailIframe,
		SmsPhoneFrame,
		defaultReportType,
		type ReportType
	} from '$lib/components/preview';
	import type { Trip, Stage } from '$lib/types';
	import EditStagesSection from '../edit/EditStagesSection.svelte';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import { api } from '$lib/api.js';
	import type { ActivityType } from '$lib/types.js';
	import Select from '$lib/components/ui/select/Select.svelte';

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
		/** Issue #758: SaveStatus controller from +page.svelte — shared across all tabs. */
		saveController?: SaveStatus;
	}

	let { initialTab = 'overview', badges: badgesProp = {}, trip, onTripUpdate, saveController }: Props = $props();

	// Lokale Kopie der Etappen für den Stages-Tab (EditStagesSection braucht $bindable).
	let localStages = $state<Stage[]>(trip?.stages ?? []);
	let activityType = $state<ActivityType | undefined>(trip?.activity);

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
	//   weather   -> "Inhalt" (war: "Wetter-Metriken")
	//   briefings -> "Versand" (war: "Briefing-Zeitplan")
	//   alerts    -> "Alerts" (war: "Alarmregeln")
	// Issue #736 — Reiter-Reorganisation: Labels umbenannt, value-Schlüssel unverändert.
	// Issue #1231, Slice 6 (AC-16) — CorridorEditor vereint Alerts + Idealwerte:
	//   weather -> "Wetter-Metriken" (war: "Inhalt"), alerts -> "Wertebereiche" (war: "Alerts").
	// `value`-Schlüssel bleiben unverändert — URL-Parameter und Test-IDs nicht betroffen.
	const TABS = [
		{ value: 'overview', label: 'Übersicht' },
		{ value: 'stages', label: 'Etappen & Wegpunkte' },
		{ value: 'weather', label: 'Wetter-Metriken' },
		{ value: 'briefings', label: 'Versand' },
		{ value: 'alerts', label: 'Wertebereiche' },
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

	// Issue #1231, Slice 3: Desktop/Mobile-Weiche fuer den Wertebereiche-Tab,
	// analog TripNewEditor.svelte (899px-Breakpoint, Issue #932).
	let isMobileViewport = $state(false);
	onMount(() => {
		const mq = window.matchMedia('(max-width: 899px)');
		isMobileViewport = mq.matches;
		const onChange = (e: MediaQueryListEvent) => { isMobileViewport = e.matches; };
		mq.addEventListener('change', onChange);
		return () => mq.removeEventListener('change', onChange);
	});

	async function handleValueChange(value: string): Promise<void> {
		// Issue #953: Ausstehenden Alerts-Auto-Save vor dem Tab-Wechsel flushen,
		// statt einen irreführenden „Änderungen gehen verloren"-Dialog zu zeigen
		// (die Änderung wird ohnehin gespeichert). onTripUpdate synchronisiert
		// den Parent-State, damit der Wert beim Re-Mount erhalten bleibt.
		// Issue #1117: Flush-Guard symmetrisch auf den Inhalt-Tab ('weather')
		// erweitert — der neue „Amtliche Warnungen"-Schalter nutzt denselben
		// debounce-Auto-Save; ohne Flush könnte ein sehr schneller Tab-Wechsel den
		// frisch gemounteten Alerts-Tab kurzzeitig den alten Wert zeigen lassen.
		// Issue #1232 Scheibe 1 (Adversary-Fund F001): 'briefings' ergänzt — die
		// komplette Alert-Zustellung (official_alerts_enabled/-triggers, Cooldown,
		// Stille Stunden) lebt jetzt im Versand-Tab (VersandTab.svelte). Ohne
		// diesen Flush würde ein schneller Wechsel weg vom Versand-Tab den
		// debounced Save verwerfen, und WeatherMetricsTab (Issue #1117, eigener
		// Schalter für dasselbe Feld) könnte beim nächsten dortigen Save den
		// veralteten Snapshot zurückschreiben (Regression).
		if (
			(activeTab === 'alerts' || activeTab === 'weather' || activeTab === 'briefings') &&
			value !== activeTab &&
			saveController?.hasPending
		) {
			await saveController.flush();
		}
		activeTab = value;
		// Issue #516: kanonisches URL-Modell — ?tab=<value> statt #hash.
		// replaceState verhindert History-Spam; noScroll + keepFocus erhalten
		// die Keyboard-Navigation und Scroll-Position.
		void goto(`?tab=${value}`, { replaceState: true, noScroll: true, keepFocus: true });
	}

	async function handleActivityChange(e: Event) {
		const val = (e.target as HTMLSelectElement).value as ActivityType;
		activityType = val || undefined;
		if (!trip) return;
		const updated = await api.put<Trip>(`/api/trips/${trip.id}`, { activity: activityType });
		onTripUpdate?.(updated);
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
						<div style="display: flex; align-items: center; gap: 8px; padding: 12px 16px; border-bottom: 1px solid var(--g-rule-soft);">
							<label for="activity-select-stages" style="font-size: 11px; font-family: var(--g-font-mono); color: var(--g-ink-3); letter-spacing: 0.06em; white-space: nowrap;">AKTIVITÄT</label>
							<Select
								id="activity-select-stages"
								data-testid="edit-activity-dropdown"
								value={activityType ?? ''}
								onchange={handleActivityChange}
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
						<EditStagesSection bind:stages={localStages} tripId={trip.id} showSave={true} {onTripUpdate} {saveController} activityType={activityType} />
					{/if}
				{:else if tab.value === 'weather' && trip}
					<WeatherMetricsTab {trip} {onTripUpdate} {saveController} />
				{:else if tab.value === 'alerts' && trip}
					{#if isMobileViewport}
						<CorridorEditorMobile context="route" {trip} {onTripUpdate} {saveController} />
					{:else}
						<CorridorEditor {trip} {onTripUpdate} {saveController} />
					{/if}
				{:else if tab.value === 'briefings' && trip}
					<BriefingScheduleTab {trip} {onTripUpdate} {saveController} onJump={handleValueChange} />
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
		/* Scrollbares Tab-Band. Issue #1231 Slice 6 (Fresh-Eyes-Fund): Rand-Fade
		   statt hartem Abschnitt — signalisiert, dass links/rechts weitere Tabs
		   folgen, ohne Scroll-Indikator-Widget. */
		.trip-tabs :global([data-slot="segmented"]) {
			overflow-x: auto;
			white-space: nowrap;
			scrollbar-width: none;
			-ms-overflow-style: none;
			scroll-snap-type: x mandatory;
			scroll-padding-inline: 12px;
			mask-image: linear-gradient(to right, transparent, black 16px, black calc(100% - 16px), transparent);
			-webkit-mask-image: linear-gradient(to right, transparent, black 16px, black calc(100% - 16px), transparent);
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
