<script lang="ts">
	// Issue #517 — CompareTabs: 6-Tab-Orchestrator für /compare/[id] Detail-Seite.
	//
	// Tabs (#1743): Übersicht · Orte · Wetter-Metriken (mit Versand-Abschnitt #versand) · Wertebereiche · Alarme
	// Issue #1231, Slice 6 (Begriffs-Konsistenz): Label „Idealwerte" -> „Wertebereiche",
	// Issue #2287: Kennung jetzt `wertebereiche` (gemeinsam mit dem Trip-Hub). Reine Lesenansicht, keine
	// funktionale CorridorEditor-Migration hier (bleibt späterer Scope).
	//
	// URL-Sync via history.replaceState (?tab=VALUE), kein Hash wie TripTabs.
	// Mobile (<900px): scrollbare Pill-Tabs analog TripTabs.svelte.
	//
	// Spec: docs/specs/modules/issue_517_compare_hub.md

	import { Dot, Pill, Btn, Card, SectionH } from '$lib/components/atoms';
	import CompareLocationRow from '$lib/components/molecules/CompareLocationRow.svelte';
	// Issue #1743: Wetter-Metriken und Versand in EINEM geteilten Baustein (Anker #versand).
	import WetterMetrikenVersandPanel from '$lib/components/shared/WetterMetrikenVersandPanel.svelte';
	// Issue #2682: die Übersicht ist der geteilte Baustein (context="vergleich").
	import HubUebersicht from '$lib/components/shared/hub-uebersicht/HubUebersicht.svelte';
	// SaveStatus-Typ/Helper (der Chip selbst kommt seit #2284 S2 vom SubscriptionHeader).
	import type { SaveFn, SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import { extractMessage } from '$lib/stores/saveStatusStore.svelte';
	import { merkeNutzlast, wendeNutzlastAn } from '$lib/stores/nutzlastStand';
	import { deriveStatusWithScheduleOverride, STATUS_MAP } from '$lib/components/compare/subscriptionHelpers.js';
	import type { ComparePreset, Location, Group } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { onMount } from 'svelte';
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
	import { corridorPropsAus } from './corridorPropsAus.ts';
	import { versandPropsAus } from './versandPropsAus.ts';
	import { wetterMetrikenPropsAus } from './wetterMetrikenPropsAus.ts';
	// Issue #1311 (C1 von Epic #1301): geteilter Wetter-Metriken-Tab (Grundauswahl,
	// vergleich-Kontext) — seit #1743 ueber WetterMetrikenVersandPanel eingebettet.
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
	import { hydrateHubFieldsFromPreset, hydrateAlarmFieldsFromPreset } from './compareHubHydration.ts';
	import { buildComparePresetPartialPayload } from './compareEditorSave.ts';
	import {
		snapshotForRollback,
		buildToggleActivePutPayload,
		statusZielNutzlast,
		hubActivationBanner,
		createPutQueue
	} from './compareHubPersistenz.ts';
	import {
		baueSpeicherung,
		mitKonfliktSchluessel,
		speichereOderMeldeKonflikt,
		type PutClient
	} from '../shared/tripSpeicherung.ts';
	// Issue #2276 S5: der Versand-Reiter speichert selbst — Snapshot, Diff-Gate,
	// Nutzlast und Rollback liegen im geteilten Baustein; hier bleibt nur die
	// Hydration des Wizard-Zustands vor dem Mount.
	import { hydrateVersandFieldsFromPreset } from '../shared/versandVergleichSpeicherung.ts';
	import { sichereSelbstSpeichererVorReiterwechsel } from '../shared/corridor-editor/wertebereicheVergleichSpeicherung.ts';
	import { groupLocations } from './locationHelpers.js';
	import { subscriptionTabs, resolveTab, bereinigteTabAdresse, versandSprungStart } from '../shared/subscriptionTabs.ts';
	import MTabBar from '$lib/components/mobile/MTabBar.svelte';

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

	// `saveController = undefined`: ausdruecklicher Default (semantisch gleich) — ein Hub
	// ohne Controller ruft den Flush-Guard mit `undefined` (no-op), nie mit einer
	// ungebundenen Variablen.
	let { preset, locations, initialTab = 'uebersicht', onScheduleChange, saveController = undefined }: Props =
		$props();

	// Issue #2287: Tabelle und Aufloesung kommen aus der GEMEINSAMEN Reiter-Tabelle
	// (shared/subscriptionTabs.ts) — dieselben Kennungen wie im Trip-Hub; die
	// fruehere compareTabsResolve.ts (RETIRED_TABS) geht darin auf.
	// Issue #2283: synchron aus initialTab — SSR und erster Render zeigen sofort den
	// richtigen Reiter (der $effect unten bereinigt nur noch die Adresszeile).
	// svelte-ignore state_referenced_locally -- bewusst nur der Startwert; spaetere
	// initialTab-Aenderungen setzt der $effect unten.
	let activeTab = $state<string>(resolveTab('vergleich', initialTab).tab);
	// Issue #1743: jede Erhoehung laesst den Baustein zum Versand-Abschnitt scrollen
	// (der Baustein mountet erst nach der Versand-Hydration, s. Template). Startwert aus
	// der Alt-Kennung; ein direkter Link mit `#versand` liest der Baustein beim Mount.
	// svelte-ignore state_referenced_locally -- bewusst nur der Startwert.
	// Startwert auch aus einem direkten Link mit `#versand`; jeder Reiterwechsel ohne
	// Anker setzt ihn auf 0 — ein spaeterer Remount des Bausteins scrollt nicht.
	let versandSprung = $state(versandSprungStart(resolveTab('vergleich', initialTab)));
	// E4: Alt-/kind-fremde Kennung → Adresszeile EINMAL per replaceState auf die neue
	// Kennung; unbekannte Kennung → Parameter `tab` entfernt. Keine Schleife: danach
	// ist die Kennung neu, und history.replaceState aendert `initialTab` nicht.
	// Issue #1743: `versand`/`briefings` → `?tab=wetter-metriken#versand`.
	$effect(() => {
		const r = resolveTab('vergleich', initialTab);
		activeTab = r.tab;
		if (typeof window === 'undefined') return;
		const ziel = bereinigteTabAdresse(window.location.href, r);
		if (ziel !== null) history.replaceState(history.state, '', ziel);
	});

	// Tab-Leisten-Items für den MTabBar-Baustein — Orte mit Zähler-Badge.
	const compareBarItems = $derived(
		subscriptionTabs('vergleich').map((t) => ({
			value: t.id,
			label: t.label,
			testid: `compare-detail-tab-${t.id}`,
			badge: t.id === 'orte' ? orteCount : undefined
		}))
	);

	// Issue #1256 Scheibe 8 (AC-22): Viewport-Weiche fuer den Orte-Rahmen und den
	// Idealwerte-Tab (CorridorEditor vs. CorridorEditorMobile) — Muster
	// TripTabs.svelte:117-124. Die Weiche der Übersicht lebt seit #2682 im
	// geteilten Baustein shared/hub-uebersicht/HubUebersicht.svelte.
	let isMobileViewport = $state(false);
	onMount(() => {
		const mq = window.matchMedia('(max-width: 899px)');
		isMobileViewport = mq.matches;
		const onChange = (e: MediaQueryListEvent) => { isMobileViewport = e.matches; };
		mq.addEventListener('change', onChange);
		return () => mq.removeEventListener('change', onChange);
	});

	async function handleValueChange(value: string, anchor: 'versand' | null = null): Promise<void> {
		// Issue #2276 S2/S3 (TripTabs-Muster): eine ausstehende Aenderung eines
		// selbst speichernden Reiters (Alarme, Wertebereiche) vor dem Verlassen
		// senden — beide teilen den EINEN Speicher-Platz des Controllers.
		await sichereSelbstSpeichererVorReiterwechsel(activeTab, value, saveController);
		activeTab = value;
		versandSprung = anchor === 'versand' ? versandSprung + 1 : 0;
		if (typeof window !== 'undefined') {
			const url = new URL(window.location.href);
			url.searchParams.set('tab', value);
			// #1743: Sprungziel als Hash; ein Reiterwechsel ohne Anker verwirft den alten.
			url.hash = anchor ?? '';
			history.replaceState(history.state, '', url.toString());
		}
	}

	// Tab-Daten ──────────────────────────────────────────────────────────────────

	// Issue #2276 S6g (svelte-check-Fund, AC-10): VOR ihrer ersten Nutzung in
	// `status` unten deklariert (Nutzung-vor-Deklaration im Modul-Scope der
	// Instanz) — Verhalten von `status`/`statusInfo` bleibt unveraendert, reine
	// Reihenfolge-Korrektur. Issue #527/#558 + #631: Pause/Aktivieren-Zustand.
	let localSchedule = $state<string>(preset.schedule ?? 'manual');
	const status = $derived(deriveStatusWithScheduleOverride(preset, localSchedule));
	const statusInfo = $derived(STATUS_MAP[status]);

	// Issue #2682: „Nächster Versand" (Issue #1969, Backend-Wert, neu geladen nach jedem
	// erfolgreichen Speichern ueber `saveController.savedAt`), Kanal-Namen, Profil-Label und
	// Briefing-Zeiten der Übersicht leitet der geteilte Baustein HubUebersicht ab
	// (shared/hub-uebersicht/hubUebersichtModell.ts).

	// Issue #1256 Scheibe 6 Fix-Loop 2 (F005, Adversary CRITICAL): EINE lokale,
	// mutable Read-Modify-Write-Baseline fuer BEIDE S6-Speicherpfade (Orte +
	// Idealwerte). Das `preset`-Prop bleibt sonst auf den Lade-Zeitpunkt
	// eingefroren (aktualisiert nur nach togglePause()/invalidateAll() im
	// Parent, routes/compare/[id]/+page.svelte:76) — ein zweiter S6-PUT im
	// selben Seitenbesuch wuerde sonst den ersten Edit still rueckgaengig
	// machen, weil ein Voll-Spread nicht-editierte Felder aus genau dieser
	// Baseline defaultet (seit #2375 senden Orte/Status nur ihre Eigenfelder). Wird nach JEDEM erfolgreichen S6-PUT aus dem
	// Response-Body aufgefrischt (internal/handler/compare_preset.go:390
	// liefert das gespeicherte Preset zurueck — writeJSON(w, 200, updated)).
	// Uebersicht-/Vorschau-Tab lesen bewusst weiterhin `preset` direkt
	// (bekannte, akzeptierte Stale-Anzeige, s. Fix-Vorgabe Scope).
	let currentPreset = $state<ComparePreset>(snapshotForRollback(preset));

	// Fix-Loop 3 (#1433, F201): Hydrationsquelle der Reiter ist dieser Stand. Bei einem 412
	// wird er lokal um die abgelehnte Eigenfeld-Nutzlast fortgeschrieben (Seitenstand =
	// Server ⊕ ausstehende Nutzlasten) — so liest ein ERSTMALS geoeffneter Reiter (z. B.
	// Versand, teilt Abkuehlzeit/Ruhezeit mit Alarme) die Eingabe und setzt `wizardState`
	// nicht auf den Altstand zurueck. Bewusst NUR dieser interne Stand, nicht die Seiten-
	// Prop `preset`: deren Wechsel loest den Effekt unten aus, der die Hydrations-Flags
	// zuruecksetzt und den OFFENEN Reiter ueber seine Eingabe neu hydrieren wuerde.
	$effect(() => saveController?.registriereAbgelehnt((nutzlast) => {
		currentPreset = wendeNutzlastAn(currentPreset, nutzlast);
	}));

	// Fix-Loop 1 (F002, Adversary CRITICAL): EINE gemeinsame Serialisierungs-
	// Queue fuer ALLE Hub-PUT-Pfade (Orte/Idealwerte/Versand/Toggle-Active) —
	// verhindert, dass zwei schnell aufeinanderfolgende Aktionen (z. B. eine
	// Versand-Aenderung gefolgt vom Aktivieren-Klick) zwei parallele
	// api.put()-Aufrufe mit derselben, noch veralteten currentPreset-Baseline
	// ausloesen (compareHubPersistenz.ts: createPutQueue).
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

	// Issue #1433 Fix-Loop: der PUT-Weg der Schreiber ausserhalb von `schedule` (Orte,
	// Status) laeuft durch die Hub-Queue — auch, wenn „Nochmal speichern" die Funktion
	// spaeter direkt aufruft (F002: nie zwei Hub-PUTs parallel).
	function hubPut<T>(pfad: string, rumpf: unknown, init: RequestInit | undefined): Promise<T> {
		return hubPutQueue.enqueue(() => api.put<T>(pfad, rumpf, init));
	}
	const hubClient: PutClient = { put: hubPut };

	// Issue #1433 Fix-Loop (F805): Ortsliste des offenen 'orte'-Konflikts — die sendet
	// „Nochmal speichern". Ziel eines Rollbacks bei Nicht-412, solange der Konflikt offen ist.
	let offeneOrteIds: string[] | null = null;

	async function persistPickedIds(newIds: string[]): Promise<void> {
		currentLocationIds = newIds;
		saveController?.setSaving();
		// Issue #2375: nur das Eigenfeld. Issue #1433 Fix-Loop: eigener Eintrag 'orte' —
		// bei 412 „Nochmal speichern" statt Sackgasse.
		const { url, body } = buildComparePresetPartialPayload(currentPreset.id, { location_ids: newIds });
		const speichern = baueSpeicherung<ComparePreset>(hubClient, url, body, (result) => {
			// Fix-Loop 2 (F005): Baseline aus der Server-Antwort auffrischen.
			lastPersistedLocationIds = newIds;
			offeneOrteIds = null;
			currentPreset = result;
		}, 'orte');
		try {
			if ((await speichereOderMeldeKonflikt(speichern, saveController)) === 'gespeichert') {
				saveController?.setSaved();
			} else {
				// 'konflikt': KEIN Rollback (Falle 1) — B sieht die Liste, die der Retry sendet.
				offeneOrteIds = newIds;
			}
		} catch (e) {
			console.error('[CompareTabs] Orte-Persistenz fehlgeschlagen, Rollback:', e);
			// F805: bei offenem Konflikt zurueck auf dessen Liste (= was der Retry sendet).
			const offen = saveController?.state === 'conflict' ? offeneOrteIds : null;
			currentLocationIds = offen ?? lastPersistedLocationIds;
			saveController?.setError(extractMessage(e));
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
		const hydrated = hydrateHubFieldsFromPreset(currentPreset, catalog);
		wizardState.isEditMode = hydrated.isEditMode;
		wizardState.corridors = hydrated.corridors;
		wizardState.activityProfile = hydrated.activityProfile;
		wizardState.idealRanges = hydrated.idealRanges;
		if (hydrated.activeMetricKeys !== null) wizardState.activeMetricKeys = hydrated.activeMetricKeys;
		wizardState.metricAlertLevels = hydrated.metricAlertLevels;
		idealwerteHydrated = true;
	}

	$effect(() => {
		if (activeTab !== 'wertebereiche' || idealwerteHydrated || idealwerteHydrating) return;
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
	// — gleicher `wizardState`/gleiche `currentPreset`-Baseline wie die Nachbar-Reiter.
	// Seit #2276 S5 speichert der Abschnitt selbst (Baseline + Diff-Gate in
	// shared/versandVergleichSpeicherung.ts); hier bleibt nur die Hydration, die
	// `wizardState` VOR dem Mount befuellt. Issue #1743: der Versand-Abschnitt steht
	// unten im Reiter Wetter-Metriken — die Hydration haengt an diesem Reiter.
	let versandHydrated = $state(false);

	$effect(() => {
		if (activeTab !== 'wetter-metriken' || versandHydrated) return;
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
	// Wertebereiche-/Versand-Effekt zu verlassen).
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
		// setzt KEINEN vorherigen Wertebereiche-/Versand-Effekt voraus).
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

	// Issue #527/#558 + #631 — Pause/Aktivieren mit Schedule-Gedächtnis (persistiert).
	// previousSchedule initialisiert aus Backend-Feld (überlebt Reload).
	let previousSchedule = $state<string>(
		preset.previous_schedule || ((preset.schedule && preset.schedule !== 'manual') ? preset.schedule : 'daily')
	);

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
		// Issue #1433: bei offenem Konflikt ein No-op (der Konflikt endet nur per Retry).
		saveController?.setSaving();
		const pfad = `/api/compare/presets/${currentPreset.id}`;
		const gemerkt = previousSchedule;
		// Issue #1433 Fix-Loop: eigener Eintrag 'status' fuer „Nochmal speichern".
		const speichern: SaveFn = mitKonfliktSchluessel(async (init) => {
			const antwort = await hubPutQueue.enqueue(async () => {
				// F002: Nutzlast erst in der Queue bauen. Falle 2: beim Retry aus dem FRISCH
				// geholten Stand ableiten — der gemerkte `previous_schedule` kann veraltet sein.
				const body = saveController?.imWiederholen
					? statusZielNutzlast(await api.get<ComparePreset>(pfad), next, gemerkt)
					: buildToggleActivePutPayload(currentPreset, next, gemerkt).body;
				merkeNutzlast(speichern, body);
				return api.put<ComparePreset>(pfad, body, init);
			});
			currentPreset = antwort;
			localSchedule = antwort.schedule ?? next;
			if (antwort.previous_schedule) previousSchedule = antwort.previous_schedule;
			// Staging-Fund SF-2: die Header-Status-Pille (andere Status-Quelle) zieht mit.
			onScheduleChange?.(localSchedule);
		}, 'status');
		try {
			if ((await speichereOderMeldeKonflikt(speichern, saveController)) === 'gespeichert') {
				saveController?.setSaved();
			}
			// 'konflikt': die Konfliktanzeige uebernimmt — kein eigener Fehlertext im Kebab.
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

<div class="compare-tabs" data-testid="compare-detail-tab-list">
	<!-- Tab-Leiste — geteilter MTabBar-Baustein (Mobile Usability Paket 2,
	     Spec mobile_tab_leisten_mtabbar, Iteration 2). Ersetzt das handgebaute
	     compare-tabs-bar-Markup + das 1:1-kopierte Mobil-CSS (AP-006-Drift).
	     size="sm" haelt die Compare-Optik (13px, 12/16px, neutraler Badge);
	     Test-IDs bleiben. -->
	<MTabBar
		items={compareBarItems}
		active={activeTab}
		onChange={(v) => void handleValueChange(v)}
		ariaLabel="Vergleich-Detail"
		size="sm"
	/>

	<!-- Tab-Inhalte — Wrapper mit Padding nach JSX-Vorlage (Issue #582) -->
	<div class="compare-tabs-content" style="position: relative; max-width: 1320px">

	{#if activeTab === 'uebersicht'}
		<div data-testid="compare-detail-panel-uebersicht">
			<!-- Issue #2682: geteilter Baustein (Kennzahlen, Orte-/Wertebereiche-/Versand-Karten bzw.
			     mobile Pfeil-Zeilen, Versand-Historie). `status` traegt das lokale Pausieren/
			     Aktivieren, `orte` die aufgeloesten Orte dieser Sitzung. -->
			<HubUebersicht
				context="vergleich"
				{preset}
				{status}
				orte={resolvedLocations}
				{saveController}
				onJump={handleValueChange}
			/>
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
			{#if wetterMetrikenLayoutHydrationBereit && versandHydrated}
				<!-- Issue #2276 S4: der Reiter speichert selbst (saveController,
				     Hub-Queue, Basis-Rueckmeldung, EINE kombinierte Wetter-Metriken/
				     Layout-Orchestrierung in WeatherMetricsTab.svelte) — kein Wrapper
				     und keine getrennten Commit-Funktionen mehr. Gemountet wird ERST,
				     wenn BEIDE Domaenen hydriert sind (wetterMetrikenLayoutHydrationBereit,
				     AC-3), damit die Orchestrierung gegen eine vollstaendige Baseline
				     entsteht.
				     Issue #1743: geteilter Baustein mit Versand-Abschnitt (#versand) samt
				     Aktivierungs-Karte; er mountet zusaetzlich erst nach der Versand-
				     Hydration (versandHydrated) — nie mit Platzhalterwerten (AC-9). -->
				<WetterMetrikenVersandPanel
					context="vergleich"
					{...wetterMetrikenPropsAus(wizardState)}
					versand={versandPropsAus(wizardState)}
					vergleichTelegramStyle={wizardState.telegramStyle ?? 'rich'}
					activation={hubActivationCard}
					preset={currentPreset}
					{saveController}
					enqueueHubWrite={reiheHubSchreibvorgangEin}
					onCompareUpdate={uebernehmeHubAntwort}
					{versandSprung}
				/>
			{/if}
		</div>
	{/if}

	{#if activeTab === 'wertebereiche'}
		<div class="tab-panel" data-testid="compare-detail-panel-wertebereiche">
			{#if idealwerteHydrated}
				<!-- Issue #1256 Scheibe 8 (AC-22): mobile Spiegelung, Muster TripTabs.svelte.
				     Issue #2276 S3: der Reiter speichert selbst (saveController, Hub-Queue,
				     Basis-Rueckmeldung) — kein Wrapper mehr. -->
				{#if isMobileViewport}
					<!-- Mobil: dieselbe Verdrahtung wie der Desktop-Zweig. -->
					<CorridorEditorMobile context="vergleich" {...corridorPropsAus(wizardState)} preset={currentPreset} {saveController} enqueueHubWrite={reiheHubSchreibvorgangEin} onCompareUpdate={uebernehmeHubAntwort} />
				{:else}
					<!-- Desktop. -->
					<CorridorEditor context="vergleich" {...corridorPropsAus(wizardState)} preset={currentPreset} {saveController} enqueueHubWrite={reiheHubSchreibvorgangEin} onCompareUpdate={uebernehmeHubAntwort} />
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

	<!-- Issue #1743: das eigene Versand-Panel entfaellt — der Versand-Abschnitt steht
	     im Reiter Wetter-Metriken (WetterMetrikenVersandPanel oben). -->

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
		</Card>
	{/snippet}

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
		/* Tab-Band-Regeln (Fade/Snap) leben im MTabBar-Baustein — das frueher
		   1:1 aus TripTabs.svelte kopierte Mobil-CSS der compare-tabs-bar ist
		   mit der Umstellung (Spec mobile_tab_leisten_mtabbar, Iteration 2)
		   ersatzlos entfernt (AP-006). */

		/* Issue #1256 Scheibe 8 (AC-22): CompareTabs wird jetzt ueber die
		   Ein-Mount-Strategie auch mobil gerendert — schmaleres Padding statt
		   des Desktop-Werts (Ist-Befund Analyse). */
		.compare-tabs-content {
			padding: 16px 16px 60px;
		}
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
		font-size: 11px;
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
</style>
