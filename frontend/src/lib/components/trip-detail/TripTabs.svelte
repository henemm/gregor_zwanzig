<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import MTabBar from '$lib/components/mobile/MTabBar.svelte';
	import HubOverview from './HubOverview.svelte';
	// Issue #2682: Übersicht = geteilter Baustein; HubOverview ist die Trip-Hauptfläche darin.
	import HubUebersicht from '$lib/components/shared/hub-uebersicht/HubUebersicht.svelte';
	import AlarmeScheduleTab from './AlarmeScheduleTab.svelte';
	// Issue #1743: Wetter-Metriken und Versand in EINEM geteilten Baustein (Anker #versand).
	import WetterMetrikenVersandPanel from '$lib/components/shared/WetterMetrikenVersandPanel.svelte';
	// Issue #1231: CorridorEditor(Mobile) ersetzt AlertsTab auf Desktop + Mobile.
	// Import von AlertsTab entfernt (Slice 5) — Datei bleibt vorerst bestehen
	// (Aufraeumen inkl. AlertMetricLevelTable/-Row ist Slice-6-Thema, s. Spec).
	import CorridorEditor from '$lib/components/shared/corridor-editor/CorridorEditor.svelte';
	import CorridorEditorMobile from '$lib/components/shared/corridor-editor/CorridorEditorMobile.svelte';
	import type { Trip, Stage } from '$lib/types';
	import type { MetricCatalog } from './metricsEditor.ts';
	import EditStagesSection from '../edit/EditStagesSection.svelte';
	import { subscriptionTabs, resolveTab, bereinigteTabAdresse, versandSprungStart } from '../shared/subscriptionTabs.ts';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';

	// Issue #2287: Badge-Schluessel = Reiter-Kennungen (gemeinsame Tabelle).
	interface Badges {
		uebersicht?: number;
		etappen?: number;
		'wetter-metriken'?: number;
		wertebereiche?: number;
		alarme?: number;
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
		alarme: badgesProp.alarme
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
		etappen: 'Inhalt folgt mit Epic #137 (Wegpunkt-Editor)'
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
	// Issue #1743: jede Erhoehung laesst den Baustein zum Versand-Abschnitt scrollen.
	// Startwert aus der Alt-Kennung (`versand`/`briefings` tragen den Anker) oder aus
	// einem direkten Link mit `#versand` (beim Laden gelesen). Jeder Reiterwechsel ohne
	// Anker setzt ihn auf 0 — ein spaeterer Remount des Bausteins scrollt nicht.
	// svelte-ignore state_referenced_locally -- bewusst nur der Startwert.
	let versandSprung = $state(versandSprungStart(resolveTab('trip', initialTab)));

	// Issue #2287 (E4): Alt-/kind-fremde Kennung → Adresszeile EINMAL per replaceState
	// auf die neue Kennung; unbekannte Kennung → Parameter `tab` entfernt. Danach ist
	// die Kennung neu → kein erneutes Umschreiben (keine Schleife).
	// Issue #1743: `versand`/`briefings` → `?tab=wetter-metriken#versand`.
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

	async function handleValueChange(value: string, anchor: 'versand' | null = null): Promise<void> {
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
		// Issue #1743: kein eigener Reiter `versand` mehr — der Versand-Abschnitt gehoert
		// zu `wetter-metriken`; ein Fremd-Besitzer-Slot wurde schon beim schedule()
		// gesendet, der Flush hier sendet den verbliebenen (beide Besitzer).
		if (
			(activeTab === 'wertebereiche' || activeTab === 'wetter-metriken' || activeTab === 'alarme' || activeTab === 'etappen') &&
			value !== activeTab &&
			saveController?.hasPending
		) {
			await saveController.flush();
		}
		activeTab = value;
		versandSprung = anchor === 'versand' ? versandSprung + 1 : 0;
		// Issue #516: kanonisches URL-Modell — ?tab=<value> statt #hash.
		// replaceState verhindert History-Spam; noScroll + keepFocus erhalten
		// die Keyboard-Navigation und Scroll-Position. #1743: Sprungziel als Hash.
		const hash = anchor ? `#${anchor}` : '';
		void goto(`?tab=${value}${hash}`, { replaceState: true, noScroll: true, keepFocus: true });
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
					<div class="trip-uebersicht">
						<HubUebersicht context="route" {trip} onJump={handleValueChange}>
							{#snippet children(naechstesBriefing)}
								<HubOverview {trip} onJump={handleValueChange} {metricsCatalog} nextBriefing={naechstesBriefing} />
							{/snippet}
						</HubUebersicht>
					</div>
				{:else if tab.value === 'etappen'}
					{#if trip}
						<EditStagesSection bind:stages={localStages} tripId={trip.id} showSave={true} {onTripUpdate} {saveController} activityType={activityType} />
					{/if}
				{:else if tab.value === 'wetter-metriken' && trip}
					<WetterMetrikenVersandPanel context="route" {trip} {onTripUpdate} {saveController} onJump={handleValueChange} {versandSprung} />
				{:else if tab.value === 'wertebereiche' && trip}
					{#if isMobileViewport}
						<CorridorEditorMobile context="route" {trip} {onTripUpdate} {saveController} />
					{:else}
						<CorridorEditor {trip} {onTripUpdate} {saveController} />
					{/if}
				{:else if tab.value === 'alarme' && trip}
					<AlarmeScheduleTab {trip} {onTripUpdate} {saveController} {metricsCatalog} />
				{:else}
					<p class="p-4 text-sm">{PLACEHOLDERS[tab.value]}</p>
				{/if}
			</div>
		{/if}
	{/each}
</div>

<style>
	/* Issue #2682: Rand der Trip-Übersicht (vorher am HubOverview-Raster). */
	.trip-uebersicht {
		position: relative;
		padding: 32px 40px 60px;
		max-width: 1480px;
	}
	@media (max-width: 899px) {
		.trip-uebersicht {
			padding: 20px 16px 48px;
		}
	}
</style>
