<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import MTabBar from '$lib/components/mobile/MTabBar.svelte';
	import HubOverview from './HubOverview.svelte';
	import BriefingScheduleTab from './BriefingScheduleTab.svelte';
	import AlarmeScheduleTab from './AlarmeScheduleTab.svelte';
	import WeatherMetricsTab from '$lib/components/shared/WeatherMetricsTab.svelte';
	// Issue #1231: CorridorEditor(Mobile) ersetzt AlertsTab auf Desktop + Mobile.
	// Import von AlertsTab entfernt (Slice 5) — Datei bleibt vorerst bestehen
	// (Aufraeumen inkl. AlertMetricLevelTable/-Row ist Slice-6-Thema, s. Spec).
	import CorridorEditor from '$lib/components/shared/corridor-editor/CorridorEditor.svelte';
	import CorridorEditorMobile from '$lib/components/shared/corridor-editor/CorridorEditorMobile.svelte';
	import {
		EmailIframe,
		SmsPhoneFrame,
		defaultReportType,
		type ReportType
	} from '$lib/components/preview';
	import type { Trip, Stage } from '$lib/types';
	import type { MetricCatalog } from './metricsEditor.ts';
	import EditStagesSection from '../edit/EditStagesSection.svelte';
	import { subscriptionTabs, resolveTab, bereinigteTabAdresse } from '../shared/subscriptionTabs.ts';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';

	// Issue #2287: Badge-Schluessel = Reiter-Kennungen (gemeinsame Tabelle).
	interface Badges {
		uebersicht?: number;
		etappen?: number;
		'wetter-metriken'?: number;
		versand?: number;
		wertebereiche?: number;
		alarme?: number;
		vorschau?: number;
	}

	interface Props {
		initialTab?: string;
		badges?: Badges;
		trip?: Trip;
		onTripUpdate?: (updated: Trip) => void;
		/** Issue #758: SaveStatus controller from +page.svelte — shared across all tabs. */
		saveController?: SaveStatus;
		/** Feature #1435 Etappe E3a: aus +page.server.ts durchgereicht, nur an
		 *  HubOverview weitergegeben — keine eigene Logik hier. */
		metricsCatalog?: MetricCatalog | null;
	}

	let {
		initialTab = 'uebersicht',
		badges: badgesProp = {},
		trip,
		onTripUpdate,
		saveController,
		metricsCatalog = null
	}: Props = $props();

	// Lokale Kopie der Etappen für den Stages-Tab (EditStagesSection braucht $bindable).
	let localStages = $state<Stage[]>(trip?.stages ?? []);
	// Issue #2284 S2: die Aktivität wird im Hub-Kopf geändert — hier reaktiv lesen.
	const activityType = $derived(trip?.activity);

	// Issue #302 — Auto-Badges aus Trip ableiten (Etappenanzahl + enabled Alerts).
	// Explizite Werte in der `badges` Prop ueberschreiben die Auto-Ableitung.
	const badges = $derived<Badges>({
		etappen: badgesProp.etappen ?? trip?.stages?.length ?? 0,
		wertebereiche: badgesProp.wertebereiche ?? (trip?.alert_rules ?? []).filter((r) => r.enabled).length,
		uebersicht: badgesProp.uebersicht,
		'wetter-metriken': badgesProp['wetter-metriken'],
		versand: badgesProp.versand,
		alarme: badgesProp.alarme,
		vorschau: badgesProp.vorschau
	});

	// Issue #529 — Kanonische Tab-Namen aus nav-map.jsx (Single Source of Truth):
	//   weather   -> "Inhalt" (war: "Wetter-Metriken")
	//   briefings -> "Versand" (war: "Briefing-Zeitplan")
	//   alerts    -> "Alerts" (war: "Alarmregeln")
	// Issue #736 — Reiter-Reorganisation: Labels umbenannt, value-Schlüssel unverändert.
	// Issue #1231, Slice 6 (AC-16) — CorridorEditor vereint Alerts + Idealwerte:
	//   weather -> "Wetter-Metriken" (war: "Inhalt"), alerts -> "Wertebereiche" (war: "Alerts").
	// Issue #1258 Scheibe S3 (D1) — Konvergenz mit dem Compare-Zielbild: Reihenfolge
	// an … → Wertebereiche → Alarme → Versand angeglichen (war: briefings VOR alerts),
	// neuer Tab "alarme" (geteilter AlarmeTab, context="route") zwischen
	// Wertebereiche und Versand eingefuegt.
	// Issue #2287: Tabelle und Kennungen kommen aus der GEMEINSAMEN Reiter-Tabelle
	// (shared/subscriptionTabs.ts) — dieselben Kennungen wie im Ortsvergleich-Hub.
	const TABS = subscriptionTabs('trip').map((t) => ({ value: t.id, label: t.label }));

	const PLACEHOLDERS: Record<string, string> = {
		uebersicht: 'Inhalt folgt mit Issue #154 (Hero) + #156 (Höhenprofil) + #157 (Stage-Liste)',
		etappen: 'Inhalt folgt mit Epic #137 (Wegpunkt-Editor)',
		vorschau: 'Inhalt folgt mit Issue #189 (Vorschau-Integration)'
	};

	const segmentedOptions = $derived(
		TABS.map(tab => ({
			value: tab.value,
			label: tab.label,
			badge: (badges[tab.value as keyof Badges] ?? 0) >= 1 ? badges[tab.value as keyof Badges] : undefined,
			testid: `trip-detail-tab-${tab.value}`,
			badge_testid: `trip-detail-tab-badge-${tab.value}`,
		}))
	);

	// Default 'uebersicht'; $effect setzt sofort beim Mount den korrekten Tab
	// und synchronisiert bei späteren initialTab-Prop-Änderungen
	// (z.B. hash-only navigation ohne Re-Mount).
	let activeTab = $state<string>('uebersicht');
	let previewType = $state<ReportType>(defaultReportType());
	// Issue #483: Vorschau-Tab startet im Demo-Modus (Fixture-Daten), damit
	// die Vorschau auch dann zuverlässig funktioniert, wenn der Trip in der
	// Vergangenheit liegt oder die OpenMeteo-API gerade nicht erreichbar ist.
	let demoMode = $state(true);

	// Issue #2287 (E4): Alt-/kind-fremde Kennung → Adresszeile EINMAL per replaceState
	// auf die neue Kennung; unbekannte Kennung → Parameter `tab` entfernt. Danach ist
	// die Kennung neu → kein erneutes Umschreiben (keine Schleife).
	$effect(() => {
		const r = resolveTab('trip', initialTab);
		activeTab = r.tab;
		if (typeof window === 'undefined') return;
		const ziel = bereinigteTabAdresse(window.location.href, r);
		if (ziel !== null) void goto(ziel, { replaceState: true, noScroll: true, keepFocus: true });
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
		// Issue #2287: Literale auf die gemeinsamen Kennungen umgestellt
		// (alerts→wertebereiche, weather→wetter-metriken, briefings→versand, stages→etappen).
		// Issue #1117: Flush-Guard symmetrisch auf den Inhalt-Tab (Wetter-Metriken)
		// erweitert — der neue „Amtliche Warnungen"-Schalter nutzt denselben
		// debounce-Auto-Save; ohne Flush könnte ein sehr schneller Tab-Wechsel den
		// frisch gemounteten Alerts-Tab kurzzeitig den alten Wert zeigen lassen.
		// Issue #1232 Scheibe 1 (Adversary-Fund F001): Versand ergänzt — die
		// komplette Alert-Zustellung (official_alerts_enabled/-triggers, Cooldown,
		// Stille Stunden) lebt jetzt im Versand-Tab (VersandTab.svelte). Ohne
		// diesen Flush würde ein schneller Wechsel weg vom Versand-Tab den
		// debounced Save verwerfen, und WeatherMetricsTab (Issue #1117, eigener
		// Schalter für dasselbe Feld) könnte beim nächsten dortigen Save den
		// veralteten Snapshot zurückschreiben (Regression).
		// Issue #1258 Scheibe S3 (D5): 'alarme' ergänzt — die Alert-Zustellung
		// zog aus dem Versand-Tab in den neuen Alarme-Tab um, derselbe
		// Flush-Guard gilt jetzt dort.
		// Bug #1389 (Adversary F001): Etappen ergänzt — der Etappen-Reiter nutzt
		// denselben Controller und kennt seit #1389 zusätzlich zurückgestellte
		// Speichervorgänge (offene Kaskaden-Rückfrage, `defer()`). Deren Rettung
		// hing hier allein am `beforeNavigate`-Haken der Seite, also implizit.
		// Explizit ist besser: die Asymmetrie wäre genau die Abhängigkeit, die
		// beim nächsten Framework-Update still kippt.
		if (
			(activeTab === 'wertebereiche' || activeTab === 'wetter-metriken' || activeTab === 'versand' || activeTab === 'alarme' || activeTab === 'etappen') &&
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
</script>

<div class="trip-tabs" data-testid="trip-detail-tab-list">
	<!-- Mobile Usability Paket 2 (Spec mobile_tab_leisten_mtabbar): geteilter
	     Baustein — Band + Fade + scrollIntoView + A11y + 44px-Trigger. Die
	     Unterline-Desktop-Optik lebt ebenfalls im Baustein (AP-006: kein
	     divergierendes Tab-CSS mehr hier). -->
	<MTabBar
		items={segmentedOptions}
		active={activeTab}
		onChange={(v) => void handleValueChange(v)}
		ariaLabel="Tour-Detail"
	/>
	{#each TABS as tab}
		{#if activeTab === tab.value}
			<div data-testid="trip-detail-panel-{tab.value}">
				{#if tab.value === 'uebersicht' && trip}
					<HubOverview {trip} onJump={handleValueChange} {metricsCatalog} />
				{:else if tab.value === 'etappen'}
					{#if trip}
						<EditStagesSection bind:stages={localStages} tripId={trip.id} showSave={true} {onTripUpdate} {saveController} activityType={activityType} />
					{/if}
				{:else if tab.value === 'wetter-metriken' && trip}
					<WeatherMetricsTab {trip} {onTripUpdate} {saveController} />
				{:else if tab.value === 'wertebereiche' && trip}
					{#if isMobileViewport}
						<CorridorEditorMobile context="route" {trip} {onTripUpdate} {saveController} />
					{:else}
						<CorridorEditor {trip} {onTripUpdate} {saveController} />
					{/if}
				{:else if tab.value === 'alarme' && trip}
					<AlarmeScheduleTab {trip} {onTripUpdate} {saveController} {metricsCatalog} />
				{:else if tab.value === 'versand' && trip}
					<BriefingScheduleTab {trip} {onTripUpdate} {saveController} onJump={handleValueChange} />
				{:else if tab.value === 'vorschau' && trip}
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
</style>
