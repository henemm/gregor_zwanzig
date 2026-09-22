<script lang="ts">
	// Issue #517 — CompareTabs: 6-Tab-Orchestrator für /compare/[id] Detail-Seite.
	//
	// Tabs: Übersicht · Orte · Wertebereiche · Layout · Versand · Vorschau
	// Issue #1231, Slice 6 (Begriffs-Konsistenz): Label „Idealwerte" -> „Wertebereiche",
	// `value`-Schlüssel unverändert (`idealwerte`). Reine Lesenansicht, keine
	// funktionale CorridorEditor-Migration hier (bleibt späterer Scope).
	//
	// URL-Sync via history.replaceState (?tab=VALUE), kein Hash wie TripTabs.
	// Mobile (<900px): scrollbare Pill-Tabs analog TripTabs.svelte.
	//
	// Spec: docs/specs/modules/issue_517_compare_hub.md

	import { Dot, Pill, Btn, Eyebrow, Card, SectionH } from '$lib/components/atoms';
	import CompareChannelSwitch from '$lib/components/molecules/CompareChannelSwitch.svelte';
	// Issue #1270: CompareBriefingPreview-Mount entfernt — er wurde nie mit
	// profile/data gemountet und rendert darum bedingungslos die Missing-Box
	// „Vorschau-Daten nicht verfügbar." (KB-2). Die Kanal-Anzeige läuft jetzt
	// direkt über die beiden Anzeige-Hüllen (ADR-0011).
	import CompareChatBubble from '$lib/components/molecules/CompareChatBubble.svelte';
	import CompareSmsPreview from '$lib/components/molecules/CompareSmsPreview.svelte';
	import CompareLocationRow from '$lib/components/molecules/CompareLocationRow.svelte';
	import VersandTab from '$lib/components/shared/VersandTab.svelte';
	// Epic #1273 S1: geteilter Save-Chip (position:fixed) + SaveStatus-Typ/Helper.
	import SaveIndicator from '$lib/components/ui/SaveIndicator.svelte';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import { extractMessage } from '$lib/stores/saveStatusStore.svelte';
	import {
		deriveStatusWithScheduleOverride,
		presetBriefingTimesLabel,
		formatLastSent,
		formatNextSend,
		channelNamesLabel,
		presetChannels,
		presetProfileLabel,
		STATUS_MAP
	} from '$lib/components/compare/subscriptionHelpers.js';
	import { deriveNextSend } from '$lib/utils/cockpitHelpers568.js';
	import type { ComparePreset, Location, Group } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { setContext, onMount } from 'svelte';
	// Issue #1256 Scheibe 6 (AC-14/15/16/31/32/33/34): Orte-Tab-Drag +
	// eingebetteter CorridorEditor im Idealwerte-Tab.
	import SortableList from '$lib/components/shared/dnd/SortableList.svelte';
	import DragHandle from '$lib/components/shared/dnd/DragHandle.svelte';
	import CorridorEditor from '$lib/components/shared/corridor-editor/CorridorEditor.svelte';
	// Issue #1256 Scheibe 8 (AC-22): mobile Spiegelung der Idealwerte-Inline-
	// Edit-Parität, Muster TripTabs.svelte:198-202.
	import CorridorEditorMobile from '$lib/components/shared/corridor-editor/CorridorEditorMobile.svelte';
	// Issue #1258 Scheibe 5 (AC-19): geteilter Alarme-Organism im 7. Hub-Tab.
	import AlarmeTab from '$lib/components/shared/AlarmeTab.svelte';
	// Issue #2276 S6c: EIN Buendel-Bauer fuer alle drei Vergleichs-Mounts.
	import { alarmePropsAus } from './alarmePropsAus.ts';
	// Issue #1311 (C1 von Epic #1301): geteilter Wetter-Metriken-Tab (Grundauswahl,
	// vergleich-Kontext) — analog Alarme-/Versand-Bridge oben.
	import WeatherMetricsTab from '$lib/components/shared/WeatherMetricsTab.svelte';
	import {
		hydrateWeatherMetricsFromPreset,
		hydrateChannelActiveMetricsFromPreset,
		hydrateDayWindowFromPreset,
		hydrateLayoutFieldsFromPreset,
		wetterMetrikenHydrationAbgeschlossen
	} from '../shared/weather-metrics-tab/weatherMetricsCompareSave.ts';
	// Issue #1373 (S2 Scheibe B, Fix-Runde 1): die Metrik-Auswahl liegt im
	// Speicherformat Größe + Auswertung — die Hydration dieses Reiters muss die
	// Katalogantwort (Übersetzung auf Auswahl-Schlüssel) abwarten, BEVOR sie den
	// Dirty-Check-Grundzustand aufnimmt. Geteilter Promise-Cache: eine Anfrage
	// pro Seiten-Load für alle Verbraucher.
	import { loadCompareSelectionEntries } from '../shared/corridor-editor/compareMetricCatalogLoader.ts';
	import type { CompareSelectionEntry } from '../shared/weather-metrics-tab/compareMetricSelection.ts';
	// Issue #1299/#1291/#1287 (C2 von Epic #1301): Stundenverlauf-Steuerung im
	// Hub-Layout-Tab — geteiltes ChannelToggle-Bedienelement + eigenstaendiges
	// Compare-Vokabular (kein Reuse von compareMetricDefs.ts).
	import ChannelToggle from '$lib/components/shared/ChannelToggle.svelte';
	// Epic #1301 Scheibe F2a: Stundenverlauf-Steuerung als geteilte Komponente
	// (Hub + Anlege-Seite /compare/new). Inline-Markup + Handler wanderten dorthin.
	import { CompareWizardState } from './compareWizardState.svelte';
	import {
		hydrateWizardStateFromPreset,
		buildHubPutPayload,
		snapshotForRollback,
		buildToggleActivePutPayload,
		hydrateAlarmFieldsFromPreset,
		hubActivationBanner,
		createPutQueue
	} from './compareHubWizardBridge.ts';
	// Issue #2276 S5: der Versand-Reiter speichert selbst — Snapshot, Diff-Gate,
	// Nutzlast und Rollback liegen im geteilten Baustein; hier bleibt nur die
	// Hydration des Wizard-Zustands vor dem Mount.
	import { hydrateVersandFieldsFromPreset } from '../shared/versandVergleichSpeicherung.ts';
	import { sichereSelbstSpeichererVorReiterwechsel } from '../shared/corridor-editor/wertebereicheVergleichSpeicherung.ts';
	import { groupLocations } from './locationHelpers.js';
	import { COMPARE_TABS, resolveCompareTab } from './compareTabsResolve.js';

	interface Props {
		preset: ComparePreset;
		locations: Location[];
		initialTab?: string;
		/** Staging-Fund SF-2 (CRITICAL, AC-37): der Hub haelt seinen eigenen
		 * `localSchedule`-Zustand (Aktivierungs-Karte), waehrend die Header-
		 * Status-Pille in `compare/[id]/+page.svelte` weiterhin `data.preset`
		 * liest (nur via `invalidateAll()` im Kebab-Pfad aktualisiert) — ohne
		 * diesen Callback bleibt die Pille nach einem Pausieren/Aktivieren aus
		 * der Aktivierungs-Karte auf dem alten Status stehen, bis ein Reload
		 * erfolgt. Wird nach erfolgreichem PUT mit dem neuen `schedule` aufgerufen. */
		onScheduleChange?: (schedule: string) => void;
		/** Epic #1273 S1: geteilter Hub-SaveStatus-Controller (aus der Routen-
		 * Ebene). Orte/Wertebereiche/Versand/Aktiv-Status treiben ihn weiterhin
		 * manuell (setSaving/setSaved/setError/markPristine), NICHT via
		 * schedule() — die Netzwerk-Serialisierung bleibt bei hubPutQueue.
		 * Ausnahme seit Issue #2276 S2: der Alarme-Reiter (`AlarmeTab`) speichert
		 * selbst ueber saveController.schedule() (analog dem Trip-Zweig), s.
		 * shared/alarmeVergleichSpeicherung.ts. */
		saveController?: SaveStatus;
	}

	let { preset, locations, initialTab = 'uebersicht', onScheduleChange, saveController }: Props =
		$props();

	// Epic #1273 S3: TABS/VALID_VALUES/resolve() liegen jetzt in
	// compareTabsResolve.ts (Adversary-Fund F001 — echter Funktionsaufruf statt
	// Datei-Grep für AC-3 testbar), Verhalten unverändert.
	const TABS = COMPARE_TABS;
	function resolve(value: string): string {
		return resolveCompareTab(value);
	}

	let activeTab = $state<string>('uebersicht');
	$effect(() => {
		activeTab = resolve(initialTab);
	});

	// Issue #1256 Scheibe 8 (AC-22): Viewport-Weiche fuer den Monitoring-
	// Streifen (Desktop-5-Stat-Leiste vs. mobiles 4-Stat-2×2) und den
	// Idealwerte-Tab (CorridorEditor vs. CorridorEditorMobile) — Muster
	// TripTabs.svelte:117-124.
	let isMobileViewport = $state(false);
	onMount(() => {
		const mq = window.matchMedia('(max-width: 899px)');
		isMobileViewport = mq.matches;
		const onChange = (e: MediaQueryListEvent) => { isMobileViewport = e.matches; };
		mq.addEventListener('change', onChange);
		return () => mq.removeEventListener('change', onChange);
	});

	async function handleValueChange(value: string): Promise<void> {
		// Issue #2276 S2/S3 (TripTabs-Muster): eine ausstehende Aenderung eines
		// selbst speichernden Reiters (Alarme, Wertebereiche) vor dem Verlassen
		// senden — beide teilen den EINEN Speicher-Platz des Controllers.
		await sichereSelbstSpeichererVorReiterwechsel(activeTab, value, saveController);
		activeTab = value;
		if (typeof window !== 'undefined') {
			const url = new URL(window.location.href);
			url.searchParams.set('tab', value);
			history.replaceState(history.state, '', url.toString());
		}
	}

	// Tab-Daten ──────────────────────────────────────────────────────────────────

	const status = $derived(deriveStatusWithScheduleOverride(preset, localSchedule));
	const statusInfo = $derived(STATUS_MAP[status]);

	// Issue #1229 Fix-Loop 1 (F001/F002): "Nächster Versand" aus dem berechneten
	// Zeitstempel ableiten statt aus dem Rhythmus-Label (presetScheduleLabel enthält
	// einen rohen hour_from–hour_to-Bereich, den AC-4 im Versand-Tab verbietet).
	// Muster identisch zu CompareStatusRow.svelte.
	const now = new Date();
	const nextSend = $derived(deriveNextSend(preset, now));
	const versandSummaryText = $derived(
		`Briefings ${presetBriefingTimesLabel(preset)} · nächster Versand ${formatNextSend(nextSend)}.`
	);

	// Issue #1256 Scheibe 3 AC-6: Kanal-Namen statt Kanal-Anzahl in der
	// Übersicht-"Kanäle"-Stat (Soll: screen-compare-detail.jsx:147-150).
	const channelsLabel = $derived(channelNamesLabel(preset));

	// Issue #1256 S8c (AC-4): SummaryCard-Titel "Keine Kanäle" statt "—"
	// (Soll: screen-compare-detail.jsx:169) — abweichender Leerfall von channelsLabel.

	// Issue #1256 S8c (AC-6/AC-7): lesbares Profil-Label statt rohem preset.profil
	// (Soll: JSX:163) — Fallback auf den rohen Wert, falls das Mapping leer
	// zurueckgibt (unbekanntes Profil, kein leerer Titel).
	const profileLabel = $derived(presetProfileLabel(preset.profil) || preset.profil);

	// Issue #1256 Scheibe 6 Fix-Loop 2 (F005, Adversary CRITICAL): EINE lokale,
	// mutable Read-Modify-Write-Baseline fuer BEIDE S6-Speicherpfade (Orte +
	// Idealwerte). Das `preset`-Prop bleibt sonst auf den Lade-Zeitpunkt
	// eingefroren (aktualisiert nur nach togglePause()/invalidateAll() im
	// Parent, routes/compare/[id]/+page.svelte:76) — ein zweiter S6-PUT im
	// selben Seitenbesuch wuerde sonst den ersten Edit still rueckgaengig
	// machen, weil buildHubPutPayload nicht-editierte Felder aus genau dieser
	// Baseline defaultet. Wird nach JEDEM erfolgreichen S6-PUT aus dem
	// Response-Body aufgefrischt (internal/handler/compare_preset.go:390
	// liefert das gespeicherte Preset zurueck — writeJSON(w, 200, updated)).
	// Uebersicht-/Vorschau-Tab lesen bewusst weiterhin `preset` direkt
	// (bekannte, akzeptierte Stale-Anzeige, s. Fix-Vorgabe Scope).
	let currentPreset = $state<ComparePreset>(snapshotForRollback(preset));

	// Fix-Loop 1 (F002, Adversary CRITICAL): EINE gemeinsame Serialisierungs-
	// Queue fuer ALLE Hub-PUT-Pfade (Orte/Idealwerte/Versand/Toggle-Active) —
	// verhindert, dass zwei schnell aufeinanderfolgende Aktionen (z. B. eine
	// Versand-Aenderung gefolgt vom Aktivieren-Klick) zwei parallele
	// api.put()-Aufrufe mit derselben, noch veralteten currentPreset-Baseline
	// ausloesen (compareHubWizardBridge.ts: createPutQueue).
	const hubPutQueue = createPutQueue();

	// Issue #1256 Scheibe 6 (AC-14/15/31/32): lokaler, optimistischer Orte-Zustand.
	// Startet aus currentPreset.location_ids, wird bei Drag/Entfernen/Hinzufügen
	// sofort im UI aktualisiert und per PUT persistiert (Rollback bei Fehler).
	let currentLocationIds = $state<string[]>([...currentPreset.location_ids]);
	const orteCount = $derived(currentLocationIds.length);
	// Fix-Loop 2 (F003-Analogie): zuletzt ERFOLGREICH persistierter Orte-Stand,
	// analog zur Snapshot-Baseline der selbst speichernden Reiter — nur
	// so kann persistPickedIds beim Rollback auf den Stand NACH einem zuvor
	// in der Queue bereits erfolgreichen Edit zurueckfallen statt auf einen
	// aelteren, beim Funktionsaufruf gelesenen Stand.
	let lastPersistedLocationIds: string[] = [...currentLocationIds];

	// Orts-Auflösung: location_ids → locations[] (mit elevation_m für CompareLocationRow).
	// allLocationsForAdd ergänzt Orte, die per Inline-Add-Panel neu hinzugefügt
	// wurden und daher noch nicht im gefilterten `locations`-Prop stecken.
	const locationById = $derived.by(() => {
		const map = new Map<string, Location>();
		for (const l of locations) map.set(l.id, l);
		for (const l of allLocationsForAdd) if (!map.has(l.id)) map.set(l.id, l);
		return map;
	});
	const resolvedLocations = $derived(
		currentLocationIds.map((id, idx) => ({
			rank: idx + 1,
			loc: locationById.get(id)
		}))
	);

	// Issue #1272: DnD-State/Sync/Flip liegen jetzt im geteilten SortableList
	// (ADR-0024). Vertrag: onDndReorder(newOrder) — nur bei finalize.
	async function handleOrteDndReorder(newOrder: string[]): Promise<void> {
		await persistPickedIds(newOrder);
	}

	function orteItemLabel(id: string, i: number): string {
		return `${i + 1}. ${locationById.get(id)?.name ?? id}`;
	}

	async function removeLocation(locId: string): Promise<void> {
		await persistPickedIds(currentLocationIds.filter((id) => id !== locId));
	}

	async function persistPickedIds(newIds: string[]): Promise<void> {
		currentLocationIds = newIds;
		// Epic #1273 S1: der try/catch liegt INNERHALB des enqueue-Closures und
		// faengt den Fehler dort ab — der aeussere await wirft nie. Damit
		// setError() ueberhaupt erreichbar wird, den gefangenen Fehler in einer
		// ausserhalb deklarierten `failure`-Variable festhalten.
		let failure: unknown = null;
		saveController?.setSaving();
		// Fix-Loop 1 (F002): Payload-Bau innerhalb des enqueueten fn, damit
		// currentPreset erst zur tatsaechlichen Ausfuehrungszeit gelesen wird
		// (frisch aus einer evtl. vorher in der Queue gelaufenen PUT-Response).
		// Fix-Loop 2 (F003-Analogie): Rollback-Baseline (lastPersistedLocationIds)
		// ebenfalls erst HIER lesen — s. Begruendung an der Deklaration oben.
		const updated = await hubPutQueue.enqueue(async () => {
			try {
				const { url, body } = buildHubPutPayload(currentPreset, { pickedIds: newIds });
				const result = await api.put<ComparePreset>(url, body);
				// Fix-Loop 2 (F005): Baseline aus dem Response-Body auffrischen —
				// der PUT-Handler liefert das tatsaechlich gespeicherte Preset zurueck.
				lastPersistedLocationIds = newIds;
				return result;
			} catch (e) {
				console.error('[CompareTabs] Orte-Persistenz fehlgeschlagen, Rollback:', e);
				currentLocationIds = lastPersistedLocationIds;
				failure = e;
				return null;
			}
		});
		if (updated) {
			currentPreset = updated;
			saveController?.setSaved();
		} else if (failure) {
			saveController?.setError(extractMessage(failure));
		}
	}

	// Inline-Add-Panel (AC-31): bespoke, kein Trip-Pendant (dokumentierte
	// Ausnahme, Programm-Spec Z.430-432). Lazy Fetch erst bei Panel-Öffnung
	// (S5-Muster), keine unbedingte Ladung beim Tab-/Seiten-Mount (S4-F001).
	let addPanelOpen = $state(false);
	let addPanelLoadStarted = false;
	let allLocationsForAdd = $state<Location[]>([]);
	let groupsForAdd = $state<Group[]>([]);

	async function toggleAddPanel(): Promise<void> {
		addPanelOpen = !addPanelOpen;
		if (!addPanelOpen || addPanelLoadStarted) return;
		addPanelLoadStarted = true;
		try {
			const [locs, groups] = await Promise.all([
				api.get<Location[]>('/api/locations'),
				api.get<Group[]>('/api/groups')
			]);
			allLocationsForAdd = locs;
			groupsForAdd = groups;
		} catch (e) {
			console.error('[CompareTabs] Orts-Bibliothek konnte nicht geladen werden:', e);
		}
	}

	const addPanelGroups = $derived.by(() => {
		const notPicked = allLocationsForAdd.filter((l) => !currentLocationIds.includes(l.id));
		const { sections, ungrouped } = groupLocations(notPicked, groupsForAdd);
		const result: [string, Location[]][] = [];
		for (const s of sections) if (s.locations.length > 0) result.push([s.group.name, s.locations]);
		if (ungrouped.length > 0) result.push(['Weitere', ungrouped]);
		return result;
	});

	async function addLocationToCompare(locId: string): Promise<void> {
		await persistPickedIds([...currentLocationIds, locId]);
	}

	// Issue #1256 Scheibe 6 (AC-16/33/34): geteilter CorridorEditor im
	// Idealwerte-Tab statt Bespoke-Liste — Bridge hydratisiert die 6 Felder,
	// die der Organism im vergleich-Kontext aus dem Wizard-State liest
	// (Entscheidung 1, C0: 0 Zeilen Diff im Organism selbst).
	const wizardState = new CompareWizardState();
	setContext('compare-wizard-state', wizardState);
	let idealwerteHydrated = $state(false);
	// Issue #1373 (S2 Scheibe B, Fix-Runde 1): dritte Hydrationsstelle mit
	// derselben Wurzel — auch hier wird die Katalogantwort abgewartet, BEVOR
	// hydriert und der Grundzustand aufgenommen wird. Ohne Aufloesung traefe das
	// ✕-Entfernen einer Metrik-Zeile die Auswahl nicht mehr.
	let idealwerteHydrating = false;

	async function hydrateIdealwerteTab(): Promise<void> {
		const catalog = await loadCompareSelectionEntries().catch(() => []);
		// Fix-Loop 2 (F005): aus currentPreset statt preset hydrieren, damit ein
		// vorheriger Orte-Edit in derselben Sitzung nicht ueberschrieben wird.
		const hydrated = hydrateWizardStateFromPreset(currentPreset, catalog);
		wizardState.isEditMode = hydrated.isEditMode;
		wizardState.corridors = hydrated.corridors;
		wizardState.activityProfile = hydrated.activityProfile;
		wizardState.idealRanges = hydrated.idealRanges;
		if (hydrated.activeMetricKeys !== null) wizardState.activeMetricKeys = hydrated.activeMetricKeys;
		wizardState.metricAlertLevels = hydrated.metricAlertLevels;
		idealwerteHydrated = true;
	}

	$effect(() => {
		if (activeTab !== 'idealwerte' || idealwerteHydrated || idealwerteHydrating) return;
		idealwerteHydrating = true;
		void hydrateIdealwerteTab().finally(() => {
			idealwerteHydrating = false;
		});
	});

	// Issue #2276 S3: der Wertebereiche-Reiter speichert selbst (CorridorEditor/
	// Mobile -> shared/corridor-editor/wertebereicheVergleichSpeicherung.ts) —
	// EIN Speicherweg, kein Wrapper und kein fensterweiter pointerup-Auffang mehr.
	// Queue und Basis-Rueckmeldung als benannte Funktionen durchgereicht.
	function reiheHubSchreibvorgangEin<T>(fn: () => Promise<T>): Promise<T> {
		return hubPutQueue.enqueue(fn);
	}
	function uebernehmeHubAntwort(updated: ComparePreset): void {
		currentPreset = updated;
	}

	// Issue #1256 Scheibe 7 (AC-35/36): eingebetteter VersandTab (context="vergleich")
	// im Versand-Tab — gleicher `wizardState`/gleiche `currentPreset`-Baseline wie
	// die Nachbar-Reiter. Seit #2276 S5 speichert der Reiter selbst (Baseline +
	// Diff-Gate in shared/versandVergleichSpeicherung.ts); hier bleibt nur die
	// Hydration, die `wizardState` VOR dem Mount befuellt.
	let versandHydrated = $state(false);

	$effect(() => {
		if (activeTab !== 'versand' || versandHydrated) return;
		// F005-Muster: aus currentPreset hydrieren, damit ein vorheriger
		// Orte-/Idealwerte-Edit in derselben Sitzung nicht ueberschrieben wird.
		const hydrated = hydrateVersandFieldsFromPreset(currentPreset);
		wizardState.sendEmail = hydrated.sendEmail;
		wizardState.sendTelegram = hydrated.sendTelegram;
		wizardState.sendSms = hydrated.sendSms;
		wizardState.morningEnabled = hydrated.morningEnabled;
		wizardState.morningTime = hydrated.morningTime;
		wizardState.eveningEnabled = hydrated.eveningEnabled;
		wizardState.eveningTime = hydrated.eveningTime;
		wizardState.endDate = hydrated.endDate;
		wizardState.alertCooldownMinutes = hydrated.alertCooldownMinutes;
		wizardState.alertQuietFrom = hydrated.alertQuietFrom;
		wizardState.alertQuietTo = hydrated.alertQuietTo;
		versandHydrated = true;
	});

	// Issue #1258 Scheibe 5 (AC-19, AC-29, H2/H3): eingebetteter AlarmeTab
	// (context="vergleich") im 7. Hub-Tab — analog Idealwerte-/Versand-Bridge
	// oben (gleicher `wizardState`/gleiche `currentPreset`-Baseline). Seit
	// #2276 S2 speichert der Reiter selbst (Baseline + Diff-Gate in
	// shared/alarmeVergleichSpeicherung.ts). H3: der Alarme-Tab kann
	// als ERSTER Tab geoeffnet werden (Deep-Link `?tab=alarme`) — der
	// Hydrations-Effekt hydriert deshalb ALLE Alarm-Felder eigenstaendig ueber
	// `hydrateAlarmFieldsFromPreset` (statt sich auf einen bereits gelaufenen
	// idealwerte-/versand-Effekt zu verlassen).
	let alarmeHydrated = $state(false);
	// Issue #1373 (S2 Scheibe B, Fix-Runde 1): derselbe Grund wie beim
	// Wetter-Metriken-Reiter unten — `hydrateAlarmFieldsFromPreset` hydriert
	// `activeMetricKeys` mit (#1320, sonst zeigt die Empfindlichkeits-Tabelle
	// bei Deep-Link `?tab=alarme` faelschlich "keine Metriken"), und das braucht
	// die Katalogantwort zur Uebersetzung des Speicherformats.
	let alarmeHydrating = false;
	// #1435 E1a-2: derselbe geladene Katalog speist die Empfindlichkeits-Tabelle
	// (Alarm-Zeilen aus dem Register). Als $state festgehalten und als Prop
	// durchgereicht — der Modul-Getter waere nicht reaktiv.
	let alarmeCatalog = $state<CompareSelectionEntry[]>([]);

	async function hydrateAlarmeTab(): Promise<void> {
		const catalog = await loadCompareSelectionEntries().catch(() => []);
		alarmeCatalog = catalog;
		// F005-Muster: aus currentPreset hydrieren, damit ein vorheriger
		// Orte-/Idealwerte-/Versand-Edit in derselben Sitzung nicht
		// ueberschrieben wird (H3: eigenstaendige Hydration ALLER Alarm-Felder,
		// setzt KEINEN vorherigen idealwerte-/versand-Effekt voraus).
		hydrateAlarmFieldsFromPreset(wizardState, currentPreset, catalog);
		alarmeHydrated = true;
	}

	$effect(() => {
		if (activeTab !== 'alarme' || alarmeHydrated || alarmeHydrating) return;
		alarmeHydrating = true;
		void hydrateAlarmeTab().finally(() => {
			alarmeHydrating = false;
		});
	});

	// Issue #1311 (C1) / Issue #2276 S4: eingebetteter WeatherMetricsTab
	// (context="vergleich") im Hub-Tab "Wetter-Metriken" — analog Alarme-/
	// Idealwerte-Bridge oben. Seit S4 speichert der Reiter SELBST (Baseline +
	// Diff-Gate + kombinierte Wetter-Metriken/Layout-Orchestrierung liegen in
	// WeatherMetricsTab.svelte/weatherMetricsCompareSave.ts) — CompareTabs
	// traegt nur noch die BEIDEN Hydrations-Flags (der Reiter bedient zwei
	// Domaenen, die zu unterschiedlichen Zeitpunkten fertig laden koennen,
	// AC-3) und mountet WeatherMetricsTab ERST, wenn
	// `wetterMetrikenHydrationAbgeschlossen()` beide meldet — die Orchestrierung
	// entsteht dann per `untrack()` INNERHALB von WeatherMetricsTab bereits
	// gegen die vollstaendig hydrierte Baseline (kein PUT ohne Nutzergeste).
	let wetterMetrikenHydrated = $state(false);
	let wetterMetrikenHydrating = false;
	let layoutHydrated = $state(false);
	let layoutHydrating = false;
	const wetterMetrikenLayoutHydrationBereit = $derived(
		wetterMetrikenHydrationAbgeschlossen({ wetterMetrikenHydrated, layoutHydrated })
	);

	async function hydrateWetterMetrikenTab(): Promise<void> {
		// Katalogfehler darf den Reiter nicht unbenutzbar machen: ohne Katalog
		// bleibt die gespeicherte Auswahl unveraendert stehen (verlustfreier
		// Durchlauf, heutiges Verhalten fuer unbekannte Schluessel).
		const catalog = await loadCompareSelectionEntries().catch(() => []);
		wizardState.activeMetricKeys = hydrateWeatherMetricsFromPreset(currentPreset, catalog);
		// Issue #1703 Scheibe 8: Kanal-Overrides aus DEMSELBEN geladenen Katalog —
		// ohne sie zeigte jeder Kanal-Reiter nach dem Neuladen wieder die
		// Grundauswahl (AC-S8-4/AC-S8-6/AC-S8-11).
		wizardState.channelActiveMetricKeys = hydrateChannelActiveMetricsFromPreset(
			currentPreset,
			catalog
		);
		// D2-Fix-Loop 2 (AC-6): officialAlertsEnabled beim Erst-Oeffnen
		// mit-hydrieren (analog hydrateAlarmFieldsFromPreset) — sonst zeigt der
		// Toggle bei einem Deep-Link ?tab=wetter-metriken den Klassen-Default
		// (true) statt des echten Preset-Werts.
		wizardState.officialAlertsEnabled = currentPreset.official_alerts_enabled ?? true;
		// Issue #1361/#1372 S1b: Tagesfenster mit-hydrieren (analog oben) —
		// sonst zeigt ein Deep-Link ?tab=wetter-metriken den Wizard-Default
		// statt des echten Preset-Werts.
		const dayWindow = hydrateDayWindowFromPreset(currentPreset);
		wizardState.dayWindowStartHour = dayWindow.dayWindowStartHour;
		wizardState.dayWindowEndHour = dayWindow.dayWindowEndHour;
		wetterMetrikenHydrated = true;
	}

	$effect(() => {
		if (activeTab !== 'wetter-metriken' || wetterMetrikenHydrated || wetterMetrikenHydrating) return;
		wetterMetrikenHydrating = true;
		void hydrateWetterMetrikenTab().finally(() => {
			wetterMetrikenHydrating = false;
		});
	});

	// Issue #1299/#1291/#1287 (C2) / Issue #2276 S4: eingebetteter Stundenverlauf-
	// /Ausblick-Bereich — teilt sich den Reiter "Wetter-Metriken" mit der
	// Domaene oben, eigene Hydrations-Baseline (kann zeitversetzt fertig
	// werden, AC-3).
	//
	// Issue #1361/#1368: die Hydration wartet jetzt auf die Katalogantwort — die
	// Ausblick-Auswahl liegt im Neuformat (Groesse + Auswertung) und ist ohne
	// Katalog nicht auf Auswahl-Schluessel aufloesbar. Ohne das Abwarten stuende
	// im Dirty-Check-Grundzustand die Rohform (Scheindiff + Ruecksetzen auf die
	// Rohform, Adversary-Befund F001 aus #1373). Die Anfrage ist geteilt
	// zwischengespeichert (compareMetricCatalogLoader) — kein zweiter Abruf.
	async function hydrateLayoutTab(): Promise<void> {
		const catalog = await loadCompareSelectionEntries().catch(() => []);
		const hydrated = hydrateLayoutFieldsFromPreset(currentPreset, catalog);
		wizardState.hourlyMetricKeys = hydrated.hourlyMetricKeys;
		wizardState.hourlyEnabled = hydrated.hourlyEnabled;
		wizardState.outlookMetricKeys = hydrated.outlookMetricKeys;
		// Issue #2049: Roh/Einfach je Ausblick-Groesse, aus derselben Hydration.
		wizardState.outlookMetricFormats = hydrated.outlookMetricFormats ?? null;
		wizardState.outlookEnabled = hydrated.outlookEnabled;
		layoutHydrated = true;
	}

	$effect(() => {
		if (activeTab !== 'wetter-metriken' || layoutHydrated || layoutHydrating) return;
		layoutHydrating = true;
		void hydrateLayoutTab().finally(() => {
			layoutHydrating = false;
		});
	});

	const idealRanges = $derived(
		preset.display_config?.ideal_ranges as
			| Record<string, { min: number; max: number; unit?: string }>
			| undefined
	);

	// Issue #1360 (Scheibe S1a von Epic #1372): CHANNEL_COLS/channels/
	// layoutLocationNames/layoutChipNamesFor sind ersatzlos entfallen. Sie
	// speisten ausschliesslich die Karte "Übersicht pro Kanal" des aufgeloesten
	// Layout-Reiters und wendeten ein SPALTEN-Budget des Trips auf ORTE an — im
	// Ortsvergleich sachlich falsch: alle drei Kanaele geben ALLE Orte aus
	// (gekappt werden Metrikwerte je Ort bzw. die Nachrichtenlaenge).

	// Issue #1256 S8c (AC-1/AC-2): Layout-Tab-Limit-Pillen, statisch nach
	// JSX-Vorbild (screen-compare-detail.jsx:247, mobile: :150) — keine neue
	// Datenquelle, SMS-Pille mobil ohne "· 0".
	// Issue #1360: LAYOUT_LIMIT_PILLS(_MOBILE) ersatzlos entfernt — die Pillen
	// behaupteten eine Orts-Kappung je Kanal ("Telegram · max 8"), die es im
	// Ortsvergleich nicht gibt (AC-4).

	// ── Vorschau-Tab (Issue #514, #582) ─────────────────────────────────────────
	let previewChannel = $state<'email' | 'sms' | 'telegram'>('email');
	// Issue #1256 S8b (AC-2, Rest-Inventur R1): Kanal-Liste fuer den Umschalter
	// kommt aus der Preset-Konfiguration statt hart ['email','sms'] — dieselbe
	// Ableitungsquelle wie channelNamesLabel (S3 AC-6), nur auf die von
	// CompareChannelSwitch erwarteten Kleinschreib-Keys projiziert (kein neues
	// Ableitungs-Duplikat).
	const previewConfiguredChannels = $derived(presetChannels(preset).map((c) => c.toLowerCase()));
	let emailView = $state('desktop');
	let previewHtml = $state('');
	// Issue #1270 (ADR-0011): Telegram/SMS kommen fertig gerendert aus dem
	// Backend — das Frontend rendert Kanal-Inhalte nicht nach.
	let previewTelegram = $state('');
	let previewSms = $state('');
	let previewSmsCount = $state(0);
	let previewLoading = $state(false);
	let previewError = $state<string | null>(null);
	let sendQueued = $state(false);
	let sendLoading = $state(false);
	let sendError = $state<string | null>(null);

	// Issue #1270 (AC-1/AC-2/AC-7): EIN Abruf auf /api/preview/compare/{id}
	// liefert alle Kanäle aus EINEM ComparisonEngine-Lauf über die echten Orte
	// des Presets. Vorher hing der Tab am Validator-Stub
	// (/api/_validator/compare-email-preview, #464), der einen hartcodierten
	// "Vorschau-Ort" rendert — der Endpoint selbst bleibt für den externen
	// Validator bestehen, nur dieser Tab hängt um.
	//
	// AC-7: `previewChannel` wird hier bewusst NICHT gelesen — der Effect hängt
	// nur an Tab + Preset-ID + Orte-Anzahl. Ein Kanalwechsel löst damit keinen
	// neuen Request aus, er schaltet nur die Anzeige der bereits geladenen
	// Payloads um. Vorbild: AlertPreviewCard.svelte:34-44.
	$effect(() => {
		if (activeTab !== 'vorschau') return;
		if (preset.location_ids.length === 0) return;
		const presetId = preset.id;
		previewHtml = '';
		previewTelegram = '';
		previewSms = '';
		previewSmsCount = 0;
		previewError = null;
		previewLoading = true;
		api
			.post<{
				subject: string;
				email_html: string;
				telegram: string;
				sms: string;
				sms_char_count: number;
			}>(`/api/preview/compare/${presetId}`, {})
			.then((r) => {
				previewHtml = r.email_html;
				previewTelegram = r.telegram;
				previewSms = r.sms;
				previewSmsCount = r.sms_char_count;
			})
			.catch((e: unknown) => {
				previewError =
					e && typeof e === 'object' && 'error' in e
						? String((e as { error: unknown }).error)
						: e instanceof Error
							? e.message
							: 'Vorschau konnte nicht geladen werden';
			})
			.finally(() => {
				previewLoading = false;
			});
	});

	async function handleSend() {
		if (sendLoading) return;
		sendLoading = true;
		sendError = null;
		sendQueued = false;
		try {
			await api.post(`/api/compare/presets/${preset.id}/send`, {});
			sendQueued = true;
		} catch (e: unknown) {
			const body = e as { detail?: string; error?: string };
			sendError = body?.detail ?? body?.error ?? 'Versand fehlgeschlagen';
		} finally {
			sendLoading = false;
		}
	}

	// Issue #527/#558 + #631 — Pause/Aktivieren mit Schedule-Gedächtnis (persistiert).
	// previousSchedule initialisiert aus Backend-Feld (überlebt Reload).
	let previousSchedule = $state<string>(
		preset.previous_schedule || ((preset.schedule && preset.schedule !== 'manual') ? preset.schedule : 'daily')
	);
	let localSchedule = $state<string>(preset.schedule ?? 'manual');

	// Liefert true/false statt zu werfen — der Hub-eigene CTA-Klick ignoriert
	// den Rueckgabewert (fire-and-forget wie bisher), der Kebab-Delegations-
	// pfad (toggleActiveFromParent, s.u.) braucht ihn dagegen, um seine eigene
	// `pauseError`-Anzeige in compare/[id]/+page.svelte zu steuern.
	async function handleToggleActive(): Promise<boolean> {
		const isPausing = localSchedule !== 'manual';
		if (isPausing) previousSchedule = localSchedule;
		const next = isPausing ? 'manual' : previousSchedule;
		// Issue #2276 S2/S3: ausstehende Aenderung der selbst speichernden Reiter
		// (Alarme, Wertebereiche) vorab senden — unabhaengig vom aktiven Reiter,
		// weil der Kebab auch von anderen Reitern aus pausiert (S3 AC-6).
		await saveController?.flush();
		// Epic #1273 S1: einziger der 5 Handler mit try/catch AUSSERHALB des
		// enqueue-Closures — ein echter Fehler propagiert normal, daher direktes
		// Wrapping ohne `failure`-Variable.
		saveController?.setSaving();
		try {
			// Fix-Loop 3 (F007, Adversary CRITICAL): Payload aus currentPreset
			// bauen (nicht der eingefrorenen preset-Prop) und die Baseline nach
			// Erfolg auffrischen — identisches Muster wie persistPickedIds
			// (F005), da dies einer von mehreren PUT-Pfaden im selben
			// Komponenten-Scope ist.
			// Fix-Loop 1 (F002): Payload-Bau innerhalb des enqueueten fn, damit
			// currentPreset erst zur Ausfuehrungszeit gelesen wird — verhindert
			// den Race mit dem Versand-Speicherweg im selben Versand-Tab.
			currentPreset = await hubPutQueue.enqueue(async () => {
				const { url, body } = buildToggleActivePutPayload(currentPreset, next, previousSchedule);
				return api.put<ComparePreset>(url, body);
			});
			localSchedule = next;
			// Staging-Fund SF-2: Elternkomponente ueber den neuen Schedule
			// informieren, damit die Header-Status-Pille (andere Status-Quelle,
			// s. Props-Kommentar) mitzieht, ohne dass wir hier invalidateAll()
			// aufrufen (wuerde die eingefrorene-Prop-/currentPreset-Baseline-
			// Architektur mit frisch geladenen `data` kollidieren lassen).
			onScheduleChange?.(next);
			saveController?.setSaved();
			return true;
		} catch (e) {
			console.error('[CompareTabs] toggleActive failed:', e);
			saveController?.setError(extractMessage(e));
			return false;
		}
	}

	/**
	 * Staging-Fund F004 (CRITICAL): Delegations-Einstiegspunkt fuer den
	 * Hub-Header-Kebab (compare/[id]/+page.svelte togglePause) — der Kebab
	 * rief bislang einen EIGENSTAENDIGEN fetch-Pfad mit vollem Objekt-Spread
	 * aus dem (potenziell veralteten) `data.preset` auf, komplett AUSSERHALB
	 * der `hubPutQueue`/`currentPreset`-Baseline dieser Komponente. Je nach
	 * Reihenfolge fuehrte das zu zwei Datenverlust-Varianten (Adversary-Proben
	 * probe_kebab_vs_hub_stale_data.mjs / probe_kebab_vs_hub_reverse.mjs):
	 * ein Hub-Edit (Orte/Idealwerte/Versand) konnte vom Kebab-Toggle
	 * ueberschrieben werden ODER umgekehrt. Der Kebab ruft jetzt (per
	 * `bind:this` durch CompareDetail durchgereicht) exakt denselben
	 * `handleToggleActive`-Pfad auf wie die Aktivierungs-Karte im
	 * Versand-Tab — EIN Schreibweg fuer Pausieren/Aktivieren, unabhaengig
	 * davon, von wo er ausgeloest wird.
	 */
	export function toggleActiveFromParent(): Promise<boolean> {
		return handleToggleActive();
	}

	// Staging-Fund F004 Robustheits-Zusatz (defensiv, KEIN aktuell
	// reproduzierbarer Bug): falls `preset` durch einen ECHTEN Prop-
	// Referenzwechsel aktualisiert wird (z. B. ein kuenftig wieder
	// eingefuehrter invalidateAll()-Pfad ausserhalb dieser Komponente — nach
	// F004 gibt es im Compare-Hub aktuell KEINEN solchen Pfad mehr, dieser
	// Effekt ist Verteidigung gegen zukuenftige Regressionen), synchronisiert
	// dieser Effekt `currentPreset` und setzt die Lazy-Hydration-Flags
	// zurueck. Alle Hub-Edits sind event-diskretisiert UND ueber `hubPutQueue`
	// serialisiert persistiert — ein frischer Prop-Stand traegt daher immer
	// den Server-Superset (nie einen Stand, der einen bereits bestaetigten
	// Hub-Edit rueckgaengig macht). Reagiert NUR auf `preset` (die Prop),
	// NICHT auf `currentPreset` selbst — interne PUT-Updates von
	// `currentPreset` aendern `preset` nicht und loesen diesen Effekt daher
	// nicht aus.
	$effect(() => {
		currentPreset = snapshotForRollback(preset);
		idealwerteHydrated = false;
		versandHydrated = false;
		alarmeHydrated = false;
		wetterMetrikenHydrated = false;
		layoutHydrated = false;
	});
</script>

<!-- Epic #1273 S1: geteilter Save-Chip (position:fixed, daher Mount-Stelle frei),
     analog TripHeader.svelte:194-195. -->
{#if saveController}
	<SaveIndicator controller={saveController} />
{/if}

<div class="compare-tabs" data-testid="compare-detail-tab-list">
	<!-- Tab-Leiste — custom buttons mit Underline-Indikator (Issue #582) -->
	<div class="compare-tabs-bar" style="display: flex; gap: 0">
		{#each TABS as t}
			{@const on = activeTab === t.value}
			<button
				onclick={() => handleValueChange(t.value)}
				data-testid="compare-detail-tab-{t.value}"
				style="padding: 12px 16px; cursor: pointer; font-size: 13px; font-weight: {on ? 600 : 500}; background: transparent; border: none; font-family: var(--g-font-sans); color: {on ? 'var(--g-ink)' : 'var(--g-ink-3)'}; border-bottom: {on ? '2px solid var(--g-accent)' : '2px solid transparent'}; margin-bottom: -1px; display: flex; align-items: center; gap: 7px"
			>
				{t.label}
				{#if t.value === 'orte'}
					<span style="font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 3px; background: var(--g-paper-deep); color: var(--g-ink-3); font-family: var(--g-font-mono)">{orteCount}</span>
				{/if}
			</button>
		{/each}
	</div>

	<!-- Tab-Inhalte — Wrapper mit Padding nach JSX-Vorlage (Issue #582) -->
	<div class="compare-tabs-content" style="position: relative; max-width: 1320px">

	{#if activeTab === 'uebersicht'}
		<div data-testid="compare-detail-panel-uebersicht">
			<div style="display: flex; flex-direction: column; gap: 22px">
				<!-- Monitoring-Streifen — Issue #1256 Scheibe 8 (AC-22): mobil 4-Stat-2×2
				     statt 5-Stat-Desktop-Leiste (Soll: screen-compare-detail-mobile.jsx:79-85) -->
				{#if isMobileViewport}
					<div data-testid="compare-detail-monitoring-mobile" class="hub-mobile-grid">
						<Card padding={14}>
							<div class="hub-mobile-stat-label">Status</div>
							<div class="hub-mobile-stat-value">
								<!-- Issue #1256 S8c (AC-8): Kurzform statt Langform (Soll: screen-compare-detail-mobile.jsx:81). -->
								{#if status === 'active'}
									<span class="hub-mobile-stat-inline"><Dot tone="good" size={7}/>Läuft autom.</span>
								{:else if status === 'draft'}
									<span class="hub-mobile-stat-inline"><Dot tone="neutral" size={7}/>Entwurf</span>
								{:else}
									<span class="hub-mobile-stat-inline"><Dot tone="neutral" size={7}/>Pausiert</span>
								{/if}
							</div>
						</Card>
						<Card padding={14}>
							<div class="hub-mobile-stat-label">Nächster Versand</div>
							<div class="hub-mobile-stat-value">{formatNextSend(nextSend)}</div>
						</Card>
						<Card padding={14}>
							<div class="hub-mobile-stat-label">Zuletzt raus</div>
							<div class="hub-mobile-stat-value">{formatLastSent(preset.letzter_versand)}</div>
						</Card>
						<Card padding={14}>
							<div class="hub-mobile-stat-label">Kanäle</div>
							<div class="hub-mobile-stat-value" data-testid="compare-detail-stat-kanaele-mobile">
								{#if channelsLabel === '—'}
									—
								{:else}
									<span class="hub-mobile-stat-inline"><Dot tone="good" size={7}/>{channelsLabel}</span>
								{/if}
							</div>
						</Card>
					</div>
				{:else}
				<Card padding={0} style="overflow: hidden">
					<div style="padding: 18px 24px; display: flex; align-items: center; gap: 40px; flex-wrap: wrap">
						<!-- Status -->
						<div>
							<div style="font-size: 10px; color: var(--g-ink-4); letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 5px; font-family: var(--g-font-mono)">Status</div>
							<div style="font-size: 14px; color: var(--g-ink); font-weight: 500">
								{#if status === 'active'}
									<span style="display: inline-flex; align-items: center; gap: 7px"><Dot tone="good" size={7}/> Läuft automatisch</span>
								{:else if status === 'draft'}
									<span style="display: inline-flex; align-items: center; gap: 7px"><Dot tone="neutral" size={7}/> Entwurf · nicht aktiv</span>
								{:else}
									<span style="display: inline-flex; align-items: center; gap: 7px"><Dot tone="neutral" size={7}/> Pausiert</span>
								{/if}
							</div>
						</div>
						<!-- Nächster Versand -->
						<div>
							<div style="font-size: 10px; color: var(--g-ink-4); letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 5px; font-family: var(--g-font-mono)">Nächster Versand</div>
							<div style="font-size: 14px; color: var(--g-ink); font-weight: 500">{formatNextSend(nextSend)}</div>
						</div>
						<!-- Briefings -->
						<div>
							<div style="font-size: 10px; color: var(--g-ink-4); letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 5px; font-family: var(--g-font-mono)">Briefings</div>
							<div data-testid="compare-detail-stat-briefings" style="font-size: 14px; color: var(--g-ink); font-weight: 500">{presetBriefingTimesLabel(preset)}</div>
						</div>
						<!-- Zuletzt raus -->
						<div>
							<div style="font-size: 10px; color: var(--g-ink-4); letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 5px; font-family: var(--g-font-mono)">Zuletzt raus</div>
							<div style="font-size: 14px; color: var(--g-ink); font-weight: 500">{formatLastSent(preset.letzter_versand)}</div>
						</div>
						<!-- Kanäle — Issue #1256 Scheibe 3 AC-6: Namen statt Anzahl (Soll: screen-compare-detail.jsx:147-150) -->
						<div>
							<div style="font-size: 10px; color: var(--g-ink-4); letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 5px; font-family: var(--g-font-mono)">Kanäle</div>
							<div data-testid="compare-detail-stat-kanaele" style="font-size: 14px; color: var(--g-ink); font-weight: 500">
								{#if channelsLabel === '—'}
									—
								{:else}
									<span style="display: inline-flex; align-items: center; gap: 7px">
										<Dot tone="good" size={7}/>
										{channelsLabel}
									</span>
								{/if}
							</div>
						</div>
					</div>
				</Card>
				{/if}

				<!-- 2×2 SummaryCard-Grid (Desktop) / Chevron-Summary-Stack (Mobil) —
				     Issue #1256 S8c (AC-3..AC-7, Soll Mobil:
				     screen-compare-detail-mobile.jsx:87-93,276-293). -->
				{#snippet summaryChevron()}
					<span class="hub-summary-row-chevron" aria-hidden="true">
						<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>
					</span>
				{/snippet}
				{#if isMobileViewport}
					<div class="hub-summary-stack-mobile" data-testid="compare-detail-summary-mobile">
						<button type="button" class="hub-summary-row-mobile" data-testid="hub-summary-row-mobile" onclick={() => handleValueChange('orte')}>
							<span class="hub-summary-row-body">
								<span class="hub-summary-row-eyebrow">Orte</span>
								<span class="hub-summary-row-title">{resolvedLocations.length} Kandidaten</span>
								<span class="hub-summary-row-desc">{resolvedLocations.slice(0, 2).map(({loc}) => loc?.name ?? '—').join(' · ')}{resolvedLocations.length > 2 ? ` +${resolvedLocations.length - 2}` : ''}</span>
							</span>
							{@render summaryChevron()}
						</button>
						<button type="button" class="hub-summary-row-mobile" data-testid="hub-summary-row-mobile" onclick={() => handleValueChange('idealwerte')}>
							<span class="hub-summary-row-body">
								<span class="hub-summary-row-eyebrow">Wertebereiche</span>
								<span class="hub-summary-row-title">{profileLabel}</span>
								<span class="hub-summary-row-desc">{Object.keys(idealRanges ?? {}).length} Metriken · Markierung, kein Score</span>
							</span>
							{@render summaryChevron()}
						</button>
						<!-- Issue #1360: Übersichts-Zeile "Layout" entfaellt — sie sprang auf
						     den aufgeloesten Reiter und behauptete eine Orts-Kappung je Kanal. -->
						<button type="button" class="hub-summary-row-mobile" data-testid="hub-summary-row-mobile" onclick={() => handleValueChange('versand')}>
							<span class="hub-summary-row-body">
								<span class="hub-summary-row-eyebrow">Versand</span>
								<span class="hub-summary-row-title">{status === 'draft' ? 'Nicht geplant' : presetBriefingTimesLabel(preset)}</span>
								<span class="hub-summary-row-desc">{status === 'draft' ? 'Aktivierung offen' : `Briefings ${presetBriefingTimesLabel(preset)}`}</span>
							</span>
							{@render summaryChevron()}
						</button>
					</div>
				{:else}
				<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px">
					<Card padding={20} style="display: flex; flex-direction: column">
						<div style="display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 4px">
							<Eyebrow>Orte</Eyebrow>
							<button onclick={() => handleValueChange('orte')} style="background: none; border: none; cursor: pointer; padding: 0; font-size: 12px; font-weight: 600; color: var(--g-accent-deep); font-family: var(--g-font-sans)">Bearbeiten →</button>
						</div>
						<div style="font-size: 16px; font-weight: 600; margin-bottom: 8px; letter-spacing: -0.01em">{preset.location_ids.length} Kandidaten</div>
						<!-- Issue #1256 S8c (AC-3): "+N weitere" bei >3 Orten (Soll: jsx:159). -->
						<div style="font-size: 13px; color: var(--g-ink-2); line-height: 1.6">{resolvedLocations.slice(0, 3).map(({loc}) => loc?.name ?? '—').join(' · ')}{resolvedLocations.length > 3 ? ` +${resolvedLocations.length - 3} weitere` : ''}</div>
					</Card>

					<Card padding={20} style="display: flex; flex-direction: column">
						<div style="display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 4px">
							<Eyebrow>Wertebereiche</Eyebrow>
							<button onclick={() => handleValueChange('idealwerte')} style="background: none; border: none; cursor: pointer; padding: 0; font-size: 12px; font-weight: 600; color: var(--g-accent-deep); font-family: var(--g-font-sans)">Bearbeiten →</button>
						</div>
						<!-- Issue #1256 S8c (AC-6): presetProfileLabel statt rohem preset.profil. -->
						<div style="font-size: 16px; font-weight: 600; margin-bottom: 8px; letter-spacing: -0.01em">{profileLabel}</div>
						<div style="font-size: 13px; color: var(--g-ink-2); line-height: 1.6">{Object.keys(idealRanges ?? {}).length} Metriken mit Idealbereich — im Briefing pro Wert markiert. Kein Score, kein Ranking.</div>
					</Card>

					<!-- Issue #1360 (AC-4): Karte "Layout pro Kanal" entfaellt. Sie sprang auf
					     den aufgeloesten Reiter und behauptete "Engere Kanäle zeigen
					     automatisch weniger Spalten" — im Ortsvergleich unwahr: alle drei
					     Kanaele geben ALLE Orte aus. -->

					<Card padding={20} style="display: flex; flex-direction: column">
						<div style="display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 4px">
							<Eyebrow>Versand</Eyebrow>
							<button data-testid="compare-hub-versand-edit" onclick={() => handleValueChange('versand')} style="background: none; border: none; cursor: pointer; padding: 0; font-size: 12px; font-weight: 600; color: var(--g-accent-deep); font-family: var(--g-font-sans)">Bearbeiten →</button>
						</div>
						<!-- Issue #1256 S8c (AC-5): Draft-Sonderfall (Soll: jsx:175-177). -->
						<div style="font-size: 16px; font-weight: 600; margin-bottom: 8px; letter-spacing: -0.01em">{status === 'draft' ? 'Noch nicht geplant' : presetBriefingTimesLabel(preset)}</div>
						<div style="font-size: 13px; color: var(--g-ink-2); line-height: 1.6">{status === 'draft' ? 'Briefing-Uhrzeiten im Tab Versand festlegen.' : versandSummaryText}</div>
					</Card>
				</div>
				{/if}

				<!-- Verifikations-Hinweis -->
				<div style="display: flex; align-items: center; gap: 14px; padding: 14px 18px; background: var(--g-card); border: 1px solid var(--g-rule); border-left: 3px solid var(--g-accent); border-radius: var(--g-r-3)">
					<div style="font-size: 13px; color: var(--g-ink-2); flex: 1; line-height: 1.5">
						Gelesen wird das Briefing unterwegs im Postfach — nicht hier. Der Tab <strong>Vorschau</strong> dient nur zum Prüfen der Konfiguration.
					</div>
					<Btn variant="ghost" size="sm" onclick={() => handleValueChange('vorschau')}>Vorschau prüfen →</Btn>
				</div>
			</div>
		</div>
	{/if}

	{#if activeTab === 'orte'}
		<div class="tab-panel" data-testid="compare-detail-panel-orte">
			<!-- Issue #1256 S8c (AC-9): Section-Rahmen ueber SectionH-Atom + Card
			     um Liste UND Footer (Soll Desktop: jsx:197-216; Soll Mobil: CDM:110).
			     Fix-Loop 1 (F002): mobil ueber `eyebrow` statt `title` — kompakter
			     CDM_SectionH-Look (Soll: screen-compare-detail-mobile.jsx:267-274). -->
			{#if isMobileViewport}
				<SectionH eyebrow="Verglichene Orte">
					{#snippet right()}
						<span class="hub-section-hint">ziehen zum Sortieren</span>
					{/snippet}
				</SectionH>
			{:else}
				<SectionH title="Verglichene Orte">
					{#snippet right()}
						<span class="hub-section-hint">Reihenfolge = Spalten im Briefing · ziehen zum Sortieren</span>
					{/snippet}
				</SectionH>
			{/if}
			<Card padding={0} style="overflow: hidden">
				{#if resolvedLocations.length === 0}
					<p class="empty-state" style="padding: 0 16px">Noch keine Orte ausgewählt.</p>
				{:else}
					<SortableList
						items={currentLocationIds}
						onDndReorder={handleOrteDndReorder}
						ariaLabel="Verglichene Orte, Reihenfolge"
						itemLabel={orteItemLabel}
						flipDurationMs={150}
						zoneClass="hub-orte-list"
					>
						{#snippet row(id: string, i: number)}
							{@const loc = locationById.get(id)}
							{#if loc}
								<div class="hub-orte-row" class:alt={i % 2 === 1} data-testid="hub-orte-row" data-loc-id={id}>
									<DragHandle />
									<div class="hub-orte-row-body"><CompareLocationRow {loc} index={i + 1} /></div>
									<button
										type="button"
										class="hub-orte-remove-btn"
										data-testid="hub-orte-remove"
										title="Entfernen"
										onclick={() => removeLocation(id)}
									>✕</button>
								</div>
							{/if}
						{/snippet}
					</SortableList>
				{/if}
				<div style="padding: 14px">
					<Btn variant="ghost" size="sm" data-testid="hub-orte-add" onclick={toggleAddPanel}>Ort hinzufügen</Btn>
				</div>
			</Card>
			{#if addPanelOpen}
				<div class="hub-add-panel" data-testid="hub-orte-panel">
					{#if addPanelGroups.length === 0}
						<p class="empty-state">Keine weiteren gespeicherten Orte verfügbar.</p>
					{:else}
						{#each addPanelGroups as [groupName, groupLocs] (groupName)}
							<div class="hub-add-group">
								<div class="hub-add-group-header">{groupName} · {groupLocs.length}</div>
								{#each groupLocs as loc (loc.id)}
									<button type="button" class="hub-add-item" onclick={() => addLocationToCompare(loc.id)}>＋ {loc.name}</button>
								{/each}
							</div>
						{/each}
					{/if}
				</div>
			{/if}
		</div>
	{/if}

	{#if activeTab === 'wetter-metriken'}
		<div class="tab-panel" data-testid="compare-detail-panel-wetter-metriken">
			{#if wetterMetrikenLayoutHydrationBereit}
				<!-- Issue #2276 S4: der Reiter speichert selbst (saveController,
				     Hub-Queue, Basis-Rueckmeldung, EINE kombinierte Wetter-Metriken/
				     Layout-Orchestrierung in WeatherMetricsTab.svelte) — kein Wrapper
				     und keine getrennten Commit-Funktionen mehr. Gemountet wird ERST,
				     wenn BEIDE Domaenen hydriert sind (wetterMetrikenLayoutHydrationBereit,
				     AC-3), damit die Orchestrierung gegen eine vollstaendige Baseline
				     entsteht. -->
				<WeatherMetricsTab
					context="vergleich"
					wiz={wizardState}
					preset={currentPreset}
					{saveController}
					enqueueHubWrite={reiheHubSchreibvorgangEin}
					onCompareUpdate={uebernehmeHubAntwort}
				/>
			{/if}
		</div>
	{/if}

	{#if activeTab === 'idealwerte'}
		<div class="tab-panel" data-testid="compare-detail-panel-idealwerte">
			{#if idealwerteHydrated}
				<!-- Issue #1256 Scheibe 8 (AC-22): mobile Spiegelung, Muster TripTabs.svelte.
				     Issue #2276 S3: der Reiter speichert selbst (saveController, Hub-Queue,
				     Basis-Rueckmeldung) — kein Wrapper mehr. -->
				{#if isMobileViewport}
					<!-- Mobil: dieselbe Verdrahtung wie der Desktop-Zweig. -->
					<CorridorEditorMobile context="vergleich" preset={currentPreset} {saveController} enqueueHubWrite={reiheHubSchreibvorgangEin} onCompareUpdate={uebernehmeHubAntwort} />
				{:else}
					<!-- Desktop. -->
					<CorridorEditor context="vergleich" preset={currentPreset} {saveController} enqueueHubWrite={reiheHubSchreibvorgangEin} onCompareUpdate={uebernehmeHubAntwort} />
				{/if}
			{/if}
		</div>
	{/if}

	<!-- Issue #1360 (Scheibe S1a von Epic #1372): das Layout-Panel ist
	     ersatzlos entfallen. Seine einzige wirksame Einstellung (Stundenverlauf)
	     liegt jetzt im Reiter "Wetter-Metriken" oben — inklusive ihres
	     Bubble-Wrappers `.hub-layout-hourly-wrap`, damit der Speicherweg
	     (Round-Trip-Spread ueber flushPendingLayoutSave) mitwandert. Alles
	     uebrige (Karte "Übersicht pro Kanal", Limit-Pillen, CompareLayoutRow)
	     war bedienlose Attrappe mit sachlich falscher Kappungs-Aussage. -->

	{#if activeTab === 'alarme'}
		<div class="tab-panel" data-testid="compare-detail-panel-alarme">
			{#if alarmeHydrated}
				<!-- Issue #2276 S2: der Reiter speichert selbst (saveController,
				     Hub-Queue, Basis-Rueckmeldung) — kein Wrapper mehr. -->
				<AlarmeTab
					context="vergleich"
					{...alarmePropsAus(wizardState)}
					catalog={alarmeCatalog}
					preset={currentPreset}
					{saveController}
					enqueueHubWrite={(fn) => hubPutQueue.enqueue(fn)}
					onCompareUpdate={(updated) => {
						currentPreset = updated;
					}}
				/>
			{/if}
		</div>
	{/if}

	{#if activeTab === 'versand'}
		<div class="tab-panel" data-testid="compare-detail-panel-versand">
			{#if versandHydrated}
				<!-- Issue #2276 S5: der Reiter speichert selbst (saveController,
				     Hub-Queue, Basis-Rueckmeldung) — kein Wrapper mehr. Der
				     reaktive $effect in VersandTab.svelte beobachtet alle 10
				     Versandfelder und ersetzt damit auch das historische
				     Wrapper-`onclick` fuer „Bis auf Weiteres" (F001). -->
				<VersandTab
					context="vergleich"
					wiz={wizardState}
					activation={hubActivationCard}
					preset={currentPreset}
					{saveController}
					enqueueHubWrite={(fn) => hubPutQueue.enqueue(fn)}
					onCompareUpdate={(updated) => {
						currentPreset = updated;
					}}
				/>
			{/if}
		</div>
	{/if}

	{#snippet hubActivationCard()}
		{@const banner = hubActivationBanner(status)}
		<Card padding={20} style="border-left: 3px solid {banner.border}" data-testid="compare-hub-activation-card">
			<div style="display: flex; align-items: center; gap: 9px; margin-bottom: 10px">
				<Dot tone={banner.dotTone} size={8} />
				<span style="font-size: 15px; font-weight: 600">{banner.statusLabel}</span>
			</div>
			<div style="font-size: 13px; color: var(--g-ink-2); line-height: 1.55; margin-bottom: 16px">{banner.text}</div>
			<Btn
				variant={status === 'active' ? 'ghost' : 'primary'}
				size="md"
				style="width: 100%; justify-content: center"
				data-testid="compare-hub-activation-cta"
				onclick={handleToggleActive}
			>
				{banner.cta}
			</Btn>
			<div style="margin-top: 10px">
				{#if sendQueued}
					<p class="send-success" data-testid="compare-send-success-versand">
						Briefing wurde zur Zustellung vorgemerkt.
					</p>
				{:else}
					<Btn
						variant="quiet"
						size="sm"
						style="width: 100%; justify-content: center"
						disabled={sendLoading}
						onclick={handleSend}
						data-testid="compare-hub-activation-testsend"
					>
						{sendLoading ? 'Wird gesendet…' : 'Test-Briefing jetzt senden'}
					</Btn>
				{/if}
				{#if sendError !== null}
					<p class="send-error">{sendError}</p>
				{/if}
			</div>
		</Card>
	{/snippet}

	{#if activeTab === 'vorschau'}
		<div data-testid="compare-detail-panel-vorschau">
			{#if preset.location_ids.length === 0}
				<div style="padding: 32px; text-align: center; color: var(--g-ink-3); font-size: 13px">
					Noch keine Orte konfiguriert — Tab <strong>Orte</strong> besuchen um Kandidaten hinzuzufügen.
				</div>
			{:else}
			<!-- Verifikations-Hinweis (Issue #582) -->
			<div style="display: flex; align-items: center; gap: 14px; padding: 13px 18px; background: var(--g-card); border: 1px solid var(--g-rule); border-left: 3px solid var(--g-accent); border-radius: var(--g-r-3); margin-bottom: 20px">
				<Eyebrow style="flex-shrink: 0">Vorschau · Prüfung</Eyebrow>
				<div style="font-size: 13px; color: var(--g-ink-2); flex: 1; line-height: 1.5">
					So sieht dein Briefing aus — gelesen wird es unterwegs im Postfach, nicht hier.
				</div>
				<Btn variant="ghost" size="sm" onclick={handleSend} disabled={sendLoading}>
					{sendLoading ? 'Wird gesendet…' : 'Test-Briefing senden'}
				</Btn>
			</div>

			{#if sendQueued}
				<p style="font-size: 0.875rem; color: var(--g-success, #16a34a); margin: 0 0 12px" data-testid="compare-send-success">
					Briefing wurde zur Zustellung vorgemerkt.
				</p>
			{/if}
			{#if sendError !== null}
				<p style="font-size: 0.875rem; color: var(--g-danger, #dc2626); margin: 0 0 12px" data-testid="compare-send-error">{sendError}</p>
			{/if}

			<!-- Kanal-Umschalter + Email-View-Toggle (Issue #582) -->
			<div style="display: flex; align-items: center; gap: 16px; margin-bottom: 20px; flex-wrap: wrap">
				<CompareChannelSwitch
					value={previewChannel}
					onChange={(v: string) => (previewChannel = v as 'email' | 'sms' | 'telegram')}
					channels={previewConfiguredChannels}
				/>
				{#if previewChannel === 'email'}
					<div style="display: inline-flex; background: var(--g-paper-deep); border: 1px solid var(--g-rule); border-radius: var(--g-r-2); padding: 3px; gap: 2px; margin-left: 12px">
						{#each [['desktop', 'Desktop-Inbox'], ['iphone', 'iPhone-Mail']] as [v, l]}
							<button onclick={() => (emailView = v)} style="padding: 7px 13px; border: none; cursor: pointer; border-radius: 4px; font-size: 12.5px; font-family: var(--g-font-sans); font-weight: {emailView === v ? 600 : 500}; background: {emailView === v ? 'var(--g-card)' : 'transparent'}; box-shadow: {emailView === v ? 'var(--g-shadow-1)' : 'none'}; color: {emailView === v ? 'var(--g-ink)' : 'var(--g-ink-3)'}">
								{l}
							</button>
						{/each}
					</div>
				{/if}
				{#if !previewConfiguredChannels.includes(previewChannel)}
					<!-- AC-3 (Soll: screen-compare-detail.jsx:365-369): gewählter Kanal ist
					     im Preset nicht konfiguriert — Beispiel-Render bleibt sichtbar,
					     Hinweis läuft neben dem Umschalter statt die Render-Fläche zu leeren. -->
					<span class="mono" data-testid="compare-preview-channel-not-configured" style="font-size: 11px; color: var(--g-ink-4); letter-spacing: 0.04em">
						Kanal nicht konfiguriert · Beispiel-Render
					</span>
				{/if}
			</div>

			<!-- Render-Fläche -->
			<div style="padding: {previewChannel === 'email' && emailView === 'desktop' ? '24px' : '0'}; background: {previewChannel === 'email' && emailView === 'desktop' ? 'var(--g-paper-deep)' : 'transparent'}; border-radius: var(--g-r-3)">
				{#if previewLoading}
					<p style="font-size: 0.875rem; color: var(--g-ink-3); margin: 0" data-testid="compare-preview-loading">
						Vorschau wird geladen…
					</p>
				{:else if previewError !== null}
					<p style="font-size: 0.875rem; color: var(--g-danger, #dc2626); margin: 0" data-testid="compare-preview-error">{previewError}</p>
				{:else if previewChannel === 'email' && previewHtml !== ''}
					<div style="width: 680px; max-width: 100%;">
						<iframe
							data-testid="compare-preview-iframe"
							srcdoc={previewHtml}
							sandbox="allow-same-origin"
							title="E-Mail-Vorschau"
							style="width: 100%; min-height: 500px; border: 0; display: block"
						></iframe>
					</div>
				{:else if previewChannel === 'telegram' && previewTelegram !== ''}
					<!-- Issue #1270 (AC-2): echte Telegram-Vorschau statt Platzhalter-Copy.
					     Text kommt fertig aus dem Backend (ADR-0011), die Bubble ist reine Hülle. -->
					<div data-testid="compare-preview-telegram">
						<CompareChatBubble text={previewTelegram} />
					</div>
				{:else if previewChannel === 'sms' && previewSms !== ''}
					<!-- Issue #1270 (AC-2): echte SMS-Vorschau statt Platzhalter-Copy. -->
					<div data-testid="compare-preview-sms">
						<CompareSmsPreview text={previewSms} charCount={previewSmsCount} />
					</div>
				{:else}
					<!-- Ehrlicher Leerfall statt stiller Leere (KB-2/#1269): das Backend
					     lieferte für diesen Kanal keinen Inhalt. -->
					<p style="font-size: 0.875rem; color: var(--g-ink-3); margin: 0" data-testid="compare-preview-empty">
						Für diesen Kanal hat das Briefing keinen Inhalt geliefert.
					</p>
				{/if}
			</div>
			{/if}
		</div>
	{/if}

	</div>
</div>

<style>
	/* Tab-Leiste: Segmented entfernt — custom buttons in Template (Issue #582) */

	.tab-panel {
		padding: 1.5rem 0;
	}


	.empty-state {
		font-size: 0.875rem;
		color: var(--g-ink-3);
		padding: 1rem 0;
	}


	.compare-tabs-content {
		padding: 28px 40px 80px;
	}

	@media (max-width: 899px) {
		/* Mobile: Tab-Leiste horizontal scrollbar. Fix-Loop 1 (Fresh-Eyes-Fund,
		   S8): Regel fehlte, "Versand"/"Vorschau" waren auf 390px unerreichbar.
		   Muster 1:1 TripTabs.svelte:330-352 (dort selbst ein Fresh-Eyes-Fund
		   #1231 S6) — Rand-Fade statt hartem Abschnitt. */
		.compare-tabs-bar {
			overflow-x: auto;
			white-space: nowrap;
			scrollbar-width: none;
			-ms-overflow-style: none;
			scroll-snap-type: x mandatory;
			scroll-padding-inline: 12px;
			mask-image: linear-gradient(to right, transparent, black 16px, black calc(100% - 16px), transparent);
			-webkit-mask-image: linear-gradient(to right, transparent, black 16px, black calc(100% - 16px), transparent);
		}
		.compare-tabs-bar::-webkit-scrollbar {
			display: none;
		}
		.compare-tabs-bar button {
			flex-shrink: 0;
			white-space: nowrap;
			scroll-snap-align: start;
		}

		/* Issue #1256 Scheibe 8 (AC-22): CompareTabs wird jetzt ueber die
		   Ein-Mount-Strategie auch mobil gerendert — schmaleres Padding statt
		   des Desktop-Werts (Ist-Befund Analyse). */
		.compare-tabs-content {
			padding: 16px 16px 60px;
		}
	}

	/* ── Vorschau-Tab (Issue #514) — Design nach HubPreview ─────────────────── */
	.send-success {
		font-size: 0.875rem;
		color: var(--g-success, #16a34a);
		margin: 0;
	}
	.send-error {
		font-size: 0.875rem;
		color: var(--g-danger, #dc2626);
		margin: 0;
	}

	@media (max-width: 899px) {
	}

	/* ── Issue #526 — Übersicht-Tab ─────────────────────────────────────────── */



	@media (max-width: 899px) {
	}

	/* ── Issue #1256 Scheibe 6 — Hub-Orte-Tab (Drag/Entfernen/Add-Panel) ──── */
	.hub-orte-row {
		display: flex;
		align-items: center;
		background: transparent;
	}
	.hub-orte-row.alt {
		background: var(--g-paper-deep);
	}
	.hub-orte-row :global(.drag-handle) {
		padding-left: 16px;
	}
	.hub-orte-row-body {
		flex: 1;
		min-width: 0;
	}
	.hub-orte-remove-btn {
		margin-right: 14px;
		width: 32px;
		height: 32px;
		flex-shrink: 0;
		border: 1px solid var(--g-rule-soft);
		border-radius: var(--g-r-2, 6px);
		background: transparent;
		color: var(--g-ink-3);
		cursor: pointer;
	}
	.hub-add-panel {
		margin-top: 12px;
		padding: 14px 16px;
		background: var(--g-card);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3, 10px);
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		gap: 16px;
	}
	.hub-add-group-header {
		font-family: var(--g-font-mono);
		font-size: 10px;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--g-ink-3);
		font-weight: 600;
		padding-bottom: 8px;
		margin-bottom: 4px;
		border-bottom: 1px solid var(--g-rule-soft);
	}
	.hub-add-item {
		display: block;
		width: 100%;
		text-align: left;
		padding: 6px 8px;
		background: transparent;
		border: none;
		border-radius: var(--g-r-2, 4px);
		font-size: 12.5px;
		color: var(--g-ink);
		cursor: pointer;
	}
	.hub-add-item:hover {
		background: var(--g-accent-tint);
	}

	/* Issue #1256 Scheibe 8 (AC-22) — mobiler 4-Stat-2×2-Monitoring-Block */
	.hub-mobile-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
	}
	.hub-mobile-stat-label {
		font-size: 10px;
		color: var(--g-ink-4);
		letter-spacing: 0.16em;
		text-transform: uppercase;
		margin-bottom: 5px;
		font-family: var(--g-font-mono);
	}
	.hub-mobile-stat-value {
		font-size: 14px;
		color: var(--g-ink);
		font-weight: 500;
	}
	.hub-mobile-stat-inline {
		display: inline-flex;
		align-items: center;
		gap: 7px;
	}

	/* Issue #1256 S8c — Layout-/Orte-Tab Section-Hint (AC-1/AC-2/AC-9). */
	.hub-section-hint {
		font-family: var(--g-font-mono);
		font-size: 11px;
		color: var(--g-ink-3);
		letter-spacing: 0.03em;
	}

	/* Issue #1256 S8c (AC-1/AC-2) — Layout-Tab Limit-Pillen. */

	/* Issue #1256 S8c (AC-9) — Orte-Liste im Card-Rahmen: Trenner nur unter der Liste. */
	/* :global, weil `hub-orte-list` als zoneClass an SortableList durchgereicht
	   wird und dort den Scope-Hash dieser Komponente nicht traegt (#1272). */
	:global(.hub-orte-list) {
		border-bottom: 1px solid var(--g-rule-soft);
	}

	/* Issue #1256 S8c (AC-7) — mobiler Chevron-Summary-Stack (Soll:
	   screen-compare-detail-mobile.jsx:276-293). */
	.hub-summary-stack-mobile {
		background: var(--g-card);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3, 10px);
		overflow: hidden;
	}
	.hub-summary-row-mobile {
		display: flex;
		align-items: center;
		gap: 12px;
		width: 100%;
		text-align: left;
		padding: 13px 14px;
		background: transparent;
		border: none;
		border-top: 1px solid var(--g-rule-soft);
		cursor: pointer;
	}
	.hub-summary-stack-mobile .hub-summary-row-mobile:first-child {
		border-top: none;
	}
	.hub-summary-row-body {
		flex: 1;
		min-width: 0;
	}
	.hub-summary-row-eyebrow {
		display: block;
		font-family: var(--g-font-mono);
		font-size: 9px;
		color: var(--g-ink-4);
		letter-spacing: 0.12em;
		text-transform: uppercase;
		margin-bottom: 3px;
	}
	.hub-summary-row-title {
		display: block;
		font-size: 14.5px;
		font-weight: 600;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.hub-summary-row-desc {
		display: block;
		font-size: 12px;
		color: var(--g-ink-3);
		margin-top: 2px;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.hub-summary-row-chevron {
		flex-shrink: 0;
		color: var(--g-ink-4);
		display: flex;
	}
</style>
