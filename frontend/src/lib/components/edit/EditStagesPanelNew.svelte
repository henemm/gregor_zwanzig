<script lang="ts">
	// EditStagesPanelNew — Tab-Inhalt "Etappen & Wegpunkte" (Issue #503).
	// Spec: docs/specs/modules/issue_503_etappen_waypoints.md (Option B von Claude Design)
	//
	// Architektur: Karte + Höhenprofil + Wegpunkt-Sidebar als Tab-Inhalt (kein eigener
	// Screen, keine 6. Tab-Position). Page-Chrome (Speichern/Abbrechen) liegt in
	// TripEditView; dieses Panel kümmert sich nur um den Editor-Kern.
	//
	// Wichtige Änderungen ggü. #296-FE:
	//   - MapCanvas (Leaflet/OpenTopoMap) ist eingebunden
	//   - Layout: grid 1fr / 360px (links Karte+Profil-Cards, rechts Wegpunkte)
	//   - KI/Auto/Manuell-Unterscheidung entfernt — alle Wegpunkte gleichwertig
	//   - ProfileEditor.onProfileAdd fügt einen Wegpunkt ohne KI-Markierung ein

	import EtappenStrip from '$lib/components/trip-detail/waypoints/EtappenStrip.svelte';
	import MapCanvas from '$lib/components/trip-detail/waypoints/MapCanvas.svelte';
	import ProfileEditor from '$lib/components/trip-detail/waypoints/ProfileEditor.svelte';
	import WaypointCard from '$lib/components/trip-detail/waypoints/WaypointCard.svelte';
	import PauseStageView from '$lib/components/trip-detail/waypoints/PauseStageView.svelte';
	import MapControl from './MapControl.svelte';
	import ProfileSheetEmbedded from './ProfileSheetEmbedded.svelte';
	import StageSelectSheet from './StageSelectSheet.svelte';
	import StageDateField from './StageDateField.svelte';
	import StageTimeField from './StageTimeField.svelte';
	import { addDays, computeCascadeDelta } from './cascade.ts';
	import { Eyebrow, Btn, Dot, Pill } from '$lib/components/atoms';
	import { computeArrivalTimes, activityToSpeed } from '$lib/utils/naismith';
	import { interpolateWaypoint } from '$lib/utils/waypointEditor';
	import type { ActivityType, Stage, Trip, Waypoint } from '$lib/types';
	import { api } from '$lib/api.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import type { SaveFn, SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import { browser } from '$app/environment';

	interface Props {
		stages: Stage[];
		tripId?: string;
		showSave?: boolean;
		activityType?: ActivityType;
		onTripUpdate?: (updated: Trip) => void;
		/** Issue #758: SaveStatus controller from +page.svelte. When provided, removes explicit save button. */
		saveController?: SaveStatus;
	}
	let { stages = $bindable(), tripId, showSave = true, activityType, onTripUpdate, saveController }: Props = $props();

	let saving = $state(false);
	let saveSuccess = $state(false);
	let saveError = $state<string | null>(null);
	let addModeHint = $state(false);
	// Bug #708 — Etappen-Löschen mit Bestätigungs-Dialog (kein sofortiges Löschen)
	let pendingRemoveStageId = $state<string | null>(null);
	let mobileSnap = $state<'collapsed' | 'peek' | 'half' | 'full'>('half');
	let mobileSizeKey = $state(0);
	let stageSheetOpen = $state(false);

	// Issue #963 — Map-First-Reorder: `.mobile-editor` sitzt jetzt (per CSS `order`,
	// s. Style-Block) direkt unter der Tab-Leiste. Seine Höhe wird zur Laufzeit
	// berechnet (Mount + resize/orientationchange) aus der gemessenen Oberkante
	// (Breadcrumb/TripHeader/Tab-Leiste davor) UND der reservierten BottomNav-Zone
	// (64px + Safe-Area) darunter.
	//
	// Adversary-Fund F004 (Fix-Loop 3, CRITICAL): ein simples CSS
	// `max(FLOOR, calc(100dvh - offset - BottomNav))` schießt über die BottomNav-
	// Zone hinaus, sobald `calc(...)` positiv, aber kleiner als FLOOR ist — das
	// passiert bereits im STANDARD-Viewport 390×844 bei langen Trip-Namen (kein
	// Rand-Fall!), weil ein längerer TripHeader-Titel die Oberkante weiter nach
	// unten schiebt. Deshalb wird die Höhe hier bewusst in JS bedingt berechnet
	// statt blind zu clampen:
	//   - Ist genug Platz da (available > 0): exakt diesen Wert nutzen — er endet
	//     per Definition an der BottomNav-Oberkante, kann sie also nie überdecken.
	//   - Ist gar kein Platz da (available ≤ 0, z.B. Querformat auf schmalen
	//     Handys/sehr kurzer Portrait-Viewport, F001/F002): Fallback auf
	//     MOBILE_EDITOR_MIN_HEIGHT_PX — dort ist die BottomNav wegen des riesigen
	//     Chrome-Offsets ohnehin schon nicht ohne Scrollen erreichbar (Known
	//     Limitations in der Spec), ein Floor macht das nicht schlimmer.
	let mobileEditorEl = $state<HTMLDivElement | null>(null);
	let mobileEditorHeightPx = $state(400);
	// F002: 45% Freiraum oberhalb des 'half'-Sheets (Default-Snap) = 90px bei
	// 200px Floor, komfortabel über der `add-waypoint`-Unterkante (56px, +34px Marge).
	const MOBILE_EDITOR_MIN_HEIGHT_PX = 200;
	const BOTTOM_NAV_HEIGHT_PX = 64; // app.css `.mobile-scroll-pad` padding-bottom (ohne Safe-Area)

	// Liest `env(safe-area-inset-bottom)` als px-Zahl aus (Notch-Geräte) — CSS
	// `env()` ist in JS nicht direkt abfragbar, daher kurzzeitige Mess-Sonde.
	function getSafeAreaBottomPx(): number {
		const probe = document.createElement('div');
		probe.style.cssText =
			'position:fixed;bottom:0;left:0;height:env(safe-area-inset-bottom);width:0;visibility:hidden;pointer-events:none;';
		document.body.appendChild(probe);
		const h = probe.getBoundingClientRect().height;
		probe.remove();
		return h;
	}

	$effect(() => {
		if (!browser || !mobileEditorEl) return;
		const el = mobileEditorEl;
		function measure(): void {
			const offset = el.getBoundingClientRect().top;
			const available = window.innerHeight - offset - BOTTOM_NAV_HEIGHT_PX - getSafeAreaBottomPx();
			mobileEditorHeightPx = available > 0 ? available : MOBILE_EDITOR_MIN_HEIGHT_PX;
		}
		measure();
		window.addEventListener('resize', measure);
		window.addEventListener('orientationchange', measure);
		return () => {
			window.removeEventListener('resize', measure);
			window.removeEventListener('orientationchange', measure);
		};
	});

	// Bug #1375 Fix-Loop 1 (Staging-Befund): der auf Mobil fixierte Kaskaden-Banner
	// darf die Kartensteuerelemente (#963: `top:12px` im Kartenblock) NIE verdecken.
	// Auf Staging steht mehr Chrome über der Karte, dadurch rutschten Pille und
	// Wegpunkt-Button genau in das Band am unteren Rand, das der Banner belegte —
	// beide lagen formal im Ausschnitt, waren real aber unklickbar.
	// Regel: passt der Banner ÜBER die Steuerelemente (Unterkante 8px über deren
	// Oberkante, Oberkante noch unter der TopAppBar), wird er dort verankert; sonst
	// bleibt er unten über der BottomNav — dann liegt der Kartenblock nämlich im
	// oberen Bildschirmbereich und die Steuerelemente sind weit vom unteren Rand
	// entfernt. Damit ist Überlappungsfreiheit in beiden Fällen konstruktiv
	// garantiert, unabhängig von Chrome-Höhe und Scrollposition.
	const MAP_CONTROLS_TOP_PX = 12; // .stage-switcher-pill / .map-control: top:12px
	const CASCADE_GAP_PX = 8;
	const TOP_APP_BAR_PX = 56; // app.css `.mobile-scroll-pad` padding-top
	let cascadeEl = $state<HTMLDivElement | null>(null);
	let cascadeBottomPx = $state(BOTTOM_NAV_HEIGHT_PX + CASCADE_GAP_PX);

	$effect(() => {
		if (!browser || !mobileEditorEl || !cascadeEl) return;
		const mapEl = mobileEditorEl;
		const bannerEl = cascadeEl;
		function place(): void {
			const controlsTop = mapEl.getBoundingClientRect().top + MAP_CONTROLS_TOP_PX;
			const bannerBottomY = controlsTop - CASCADE_GAP_PX;
			const fitsAbove = bannerBottomY - bannerEl.offsetHeight >= TOP_APP_BAR_PX;
			cascadeBottomPx = fitsAbove
				? window.innerHeight - bannerBottomY
				: BOTTOM_NAV_HEIGHT_PX + CASCADE_GAP_PX + getSafeAreaBottomPx();
		}
		place();
		window.addEventListener('resize', place);
		window.addEventListener('orientationchange', place);
		// Capture-Phase: fängt auch das Scrollen des `main`-Containers (nicht window).
		window.addEventListener('scroll', place, true);
		return () => {
			window.removeEventListener('resize', place);
			window.removeEventListener('orientationchange', place);
			window.removeEventListener('scroll', place, true);
		};
	});

	async function save(): Promise<Trip | null> {
		if (!tripId) return null;
		saving = true;
		saveError = null;
		try {
			const updatedTrip = await api.put<Trip>(`/api/trips/${tripId}`, { stages: stages });
			saveSuccess = true;
			setTimeout(() => { saveSuccess = false; }, 3000);
			onTripUpdate?.(updatedTrip);
			return updatedTrip;
		} catch (e: unknown) {
			saveError = e instanceof Error ? e.message : 'Speichern fehlgeschlagen';
			return null;
		} finally {
			saving = false;
		}
	}

	// Issue #758: Auto-Save via controller (when saveController is provided).
	// Issue #1376: `init` kommt vom Flush beim Verlassen der Seite und trägt dort
	// `{ keepalive: true }` — ohne das bricht der Browser den Request beim
	// Entladen ab und die Datumsänderung wäre still verloren.
	function buildStagesSave(): SaveFn {
		const currentStages = stages;
		return async (init) => {
			const updatedTrip = await api.put<Trip>(`/api/trips/${tripId}`, { stages: currentStages }, init);
			onTripUpdate?.(updatedTrip);
		};
	}
	function scheduleSave(): void {
		if (!saveController || !tripId) return;
		saveController.schedule(buildStagesSave());
	}
	// Bug #1389: zurückgestellter Speichervorgang — feuert NICHT von selbst,
	// sondern erst mit der Antwort auf die Kaskaden-Rückfrage (bzw. beim
	// Verlassen der Seite via beforeNavigate-Flush, damit nichts verlorengeht).
	function deferSave(): void {
		if (!saveController || !tripId) return;
		saveController.defer(buildStagesSave());
	}

	// Pausentag = Etappe ohne Wegpunkte (Spec-Definition §5/AC-10).
	const isPause = (s: Stage): boolean => s.waypoints.length === 0;

	let activeStageId = $state<string>(
		stages.find((s) => !isPause(s))?.id ?? stages[0]?.id ?? ''
	);
	let activeWaypointId = $state<string | null>(null);

	const activeStage = $derived(stages.find((s) => s.id === activeStageId) ?? null);
	const activeIsPause = $derived(activeStage ? isPause(activeStage) : false);
	const activeStageIndex = $derived(stages.findIndex((s) => s.id === activeStageId));
	const prevStage = $derived(activeStageIndex > 0 ? stages[activeStageIndex - 1] : null);
	const nextStage = $derived(
		activeStageIndex >= 0 && activeStageIndex < stages.length - 1
			? stages[activeStageIndex + 1]
			: null
	);
	// Issue #674 — Speed aus activityType ableiten (Fahrrad/Wanderer-Default).
	const arrivals = $derived(
		activeStage
			? computeArrivalTimes(activeStage, activeStage.start_time, activityToSpeed(activityType))
			: []
	);

	const newId = (): string => crypto.randomUUID().slice(0, 8);

	// Issue #498 — Kaskaden-Strip: bei Tourstart-Verschiebung Folge-Etappen mitnehmen?
	interface CascadeState {
		days: number;
		count: number;
		done: boolean;
		// Bug #1389 Adversary F005 (CRITICAL): die UNVERÄNDERLICHE Grundlage der
		// Rechnung, festgehalten beim Aufstellen der Rückfrage. Vorher verschob
		// applyCascade() aus dem laufend mutierten Zustand heraus — jeder erneute
		// Aufruf addierte den Versatz nochmal. Genau ein Wiederholungs-Klick nach
		// einem fehlgeschlagenen Schreibvorgang reichte dafür (Funkloch-Alltag der
		// Zielgruppe). Mit „Grundlage + Versatz" liefert jeder Aufruf dasselbe
		// Ergebnis; der Fehlerpfad braucht dadurch gar keine Rücknahme, die selbst
		// wieder scheitern könnte.
		/** Datum von Etappe 1, BEVOR der Nutzer es angefasst hat. */
		baseFirstDate: string;
		/** Datum je Folge-Etappe (id → ISO), bevor irgendetwas verschoben wurde. */
		baseDates: Record<string, string>;
	}
	let cascade = $state<CascadeState | null>(null);
	// Bug #1389 Adversary F004: läuft gerade eine Kaskaden-Anwendung? Dient als
	// Reentrancy-Riegel in applyCascade() UND schaltet den Knopf ab, damit die
	// Oberfläche einen zweiten Tipp gar nicht erst anbietet.
	let cascadeBusy = $state(false);

	// Bug #1389 F005: Momentaufnahme der Folge-Etappen-Daten (id → ISO). Etappen
	// ohne Datum (frisch angelegt) bleiben draußen und damit unangetastet.
	function snapshotFollowUpDates(): Record<string, string> {
		const snap: Record<string, string> = {};
		stages.forEach((s, i) => {
			if (i > 0 && s.date) snap[s.id] = s.date;
		});
		return snap;
	}

	function handleDateChange(stageId: string, newDate: string): void {
		const idx = stages.findIndex((s) => s.id === stageId);
		if (idx < 0) return;
		const oldDate = stages[idx].date;

		// Datum + dateOverridden-Flag setzen, ohne andere Stages anzufassen.
		stages = stages.map((s, i) =>
			i === idx ? { ...s, date: newDate, dateOverridden: true } : s,
		);

		// Kaskaden-Vorschlag nur bei erster Etappe und gültigem altem Datum.
		if (idx === 0 && oldDate) {
			// Bug #1389 F005: Solange eine Rückfrage offen ist, bleibt ihre Grundlage
			// stehen. Ändert der Nutzer das Datum ein zweites Mal, BEVOR er geantwortet
			// hat, wäre `oldDate` nur der Zwischenstand — der Versatz käme zu klein
			// heraus. Gerechnet wird deshalb immer gegen das Ausgangsdatum.
			const open = cascade !== null && !cascade.done;
			const baseFirstDate = open ? cascade!.baseFirstDate : oldDate;
			const baseDates = open ? cascade!.baseDates : snapshotFollowUpDates();
			const delta = computeCascadeDelta(baseFirstDate, newDate);
			if (delta !== 0 && stages.length > 1) {
				cascade = { days: delta, count: stages.length - 1, done: false, baseFirstDate, baseDates };
				// Bug #1389: NICHT sofort speichern. Vorher ging hier ein Auto-Save
				// (700ms) mit dem Stand „Etappe 1 neu, Folge-Etappen ALT" los, während
				// der Nutzer die Rückfrage noch las. Beantwortet er sie später als
				// 700ms, sind zwei Schreibvorgänge unterwegs — das Backend ersetzt die
				// Etappen komplett und kennt keine Reihenfolge, bei asymmetrischer
				// Netz-Laufzeit (Funkloch/Netzwechsel/Retry) gewinnt der veraltete.
				// Geschrieben wird jetzt erst mit der Antwort: applyCascade() (alle
				// Etappen) bzw. dismissCascade() (nur Etappe 1) — genau EIN PUT.
				// Der zurückgestellte Stand bleibt `hasPending`, damit beforeNavigate
				// ihn beim Verlassen/Neuladen der Seite noch schreibt (Bezug #1376).
				deferSave();
				return;
			} else {
				cascade = null; // F001: stalen Cascade zurücksetzen wenn delta=0
			}
		}
		// Keine Kaskade (mittlere Etappe / Pausentag / Δ=0): sofort auto-speichern.
		if (saveController) scheduleSave(); else void save();
	}

	// Issue #675 — Startzeit je Etappe setzen (keine Kaskade, strikt pro Etappe).
	function handleStartTimeChange(stageId: string, newTime: string): void {
		const idx = stages.findIndex((s) => s.id === stageId);
		if (idx < 0) return;
		stages = stages.map((s, i) =>
			i === idx
				? newTime === ''
					? { ...s, start_time: undefined }
					: { ...s, start_time: newTime }
				: s,
		);
		// Issue #1010 — fehlender Save-Trigger: ohne dies wird eine reine
		// Startzeit-Änderung nie gespeichert (einziger Handler ohne Auto-Save).
		if (saveController) scheduleSave(); else void save();
	}

	async function applyCascade(): Promise<void> {
		// Bug #1389 Adversary F004: Reentrancy-Riegel, synchron VOR jedem `await`.
		// `cascade.done` wird erst nach dem ersten `await` gesetzt — zwei Tipps im
		// selben JS-Tick (auf dem Handy alltäglich) kamen deshalb beide durch die
		// Eingangsprüfung und verschoben die Folge-Etappen ZWEIMAL (belegt: s2 landete
		// auf +42 statt +21 Tagen). Seit `await settle()` (F002) klafft dieses Fenster
		// bis zu SETTLE_TIMEOUT_MS auseinander statt nur die Dauer eines PUT, deshalb
		// muss der Riegel hier stehen und nicht am ersten Netzwerk-Aufruf.
		if (cascadeBusy) return;
		if (!cascade || cascade.done) return;
		// Adversary MEDIUM: den Zustand hier festhalten. `dismissCascade()` kann im
		// selben Tick `cascade = null` setzen; ein späteres `{ ...cascade, done: true }`
		// ergäbe dann `{}` und der Erfolgsbanner stünde ohne Anzahl und Tageszahl da
		// („Folge-Etappen verschoben · alle Daten um Tage angepasst.").
		const active = cascade;
		cascadeBusy = true;
		try {
			// Bug #1389 F005: aus der festgehaltenen Grundlage rechnen, NICHT aus dem
			// aktuellen (womöglich schon verschobenen) Stand. Dadurch ist der Aufruf
			// idempotent: ein Wiederholungs-Klick nach einem Fehlschlag — oder zehn —
			// führt immer zum selben Ergebnis.
			const days = active.days;
			const base = active.baseDates;
			stages = stages.map((s, i) => {
				if (i === 0) return s;
				const from = base[s.id];
				if (!from) return s;
				return { ...s, date: addDays(from, days), dateOverridden: true };
			});
			if (saveController) {
				// Issue #1376: den noch offenen Debounce aus handleDateChange verwerfen —
				// er trägt einen veralteten Schnappschuss (nur erste Etappe verschoben)
				// und würde das gleich folgende Kaskaden-Ergebnis wieder überschreiben,
				// sobald er verzögert oder beim Verlassen der Seite feuert.
				saveController.cancel();
				// Bug #1389 (Gürtel und Hosenträger): `cancel()` stoppt nur einen noch
				// nicht ausgelösten Speichervorgang. Ist wider Erwarten doch schon einer
				// im Netz unterwegs, muss darauf GEWARTET werden — sonst entscheidet die
				// Netz-Laufzeit, welcher Stand am Ende persistiert ist.
				// Adversary F002: `setSaving()` bewusst VOR dem Warten — sonst stünde die
				// Anzeige während des (auf SETTLE_TIMEOUT_MS gedeckelten) Wartens auf
				// „Gespeichert ✓" bzw. „Nicht gespeichert" und die Oberfläche wirkte
				// eingefroren. `settle()` gibt nach dem Deckel auf und schreibt trotzdem.
				saveController.setSaving();
				await saveController.settle();
				// Flush immediately (cascade = user intent, no debounce needed).
				const currentStages = stages;
				try {
					const updatedTrip = await api.put<Trip>(`/api/trips/${tripId!}`, { stages: currentStages });
					saveController.setSaved();
					onTripUpdate?.(updatedTrip);
					cascade = { ...active, done: true };
				} catch (e: unknown) {
					const msg = e instanceof Error ? e.message : 'Speichern fehlgeschlagen';
					// Bug #1389 F006 (Spiegelfall): `cancel()` oben hat den zurückgestellten
					// Speichervorgang abgeräumt. Ohne Neu-Anmeldung hätte weder
					// `beforeNavigate` noch der Reiterwechsel etwas zu retten — die
					// Datumsänderung ginge beim Wegnavigieren still verloren. Gerettet wird
					// die geäußerte Absicht (alle mitverschieben); der Schreibvorgang war
					// nur fehlgeschlagen. Reihenfolge beachtet: `deferSave()` setzt den
					// Zustand auf `dirty`, deshalb MUSS `setError()` danach kommen, sonst
					// verschwindet die Fehlermeldung.
					deferSave();
					saveController.setError(msg);
				}
			} else {
				const result = await save();
				if (result !== null) {
					cascade = { ...active, done: true };
				}
			}
		} finally {
			cascadeBusy = false;
		}
	}

	function dismissCascade(): void {
		// „Nur diese Etappe" ist die ANTWORT auf die Rückfrage — erst jetzt wird
		// geschrieben. Beim „Schließen" des Erfolgs-Streifens (cascade.done) gibt es
		// nichts zu speichern, dann bleibt es beim reinen Ausblenden.
		//
		// Adversary F004: läuft gerade eine Kaskaden-Anwendung, hier NICHT
		// dazwischenfunken — sonst kämpfen zwei Schreibvorgänge gegeneinander. Ein
		// Doppeltipp auf diesen Knopf selbst ist unkritisch: die Funktion ist
		// synchron und nullt `cascade` vor jeder Weitergabe (Nachweis e2e AC-10).
		if (cascadeBusy) return;
		const open = cascade !== null && !cascade.done;
		const base = cascade?.baseDates;
		cascade = null;
		if (!open) return;

		// Bug #1389 F006: UNBEDINGT schreiben, unabhängig vom Zustand der Steuerung.
		// Ein fehlgeschlagener Kaskaden-Versuch hat den zurückgestellten
		// Speichervorgang bereits abgeräumt (applyCascade → cancel()) UND die
		// Folge-Etappen lokal schon verschoben. Das bisherige `flush()` lief dann
		// ins Leere: Der Nutzer sah sein neues Datum im Feld, hatte bewusst
		// entschieden — und gespeichert war nichts. Deshalb: Folge-Etappen aus der
		// Grundlage zurücksetzen, Etappe 1 behält ihr neues Datum, ein Schreibvorgang.
		if (base) {
			stages = stages.map((s, i) => {
				if (i === 0) return s;
				const from = base[s.id];
				return from && s.date !== from ? { ...s, date: from } : s;
			});
		}
		if (saveController) {
			saveController.cancel();
			void saveController.doSave(buildStagesSave());
		} else {
			void save();
		}
	}

	// EtappenStrip-Handler
	function handleStagesReorder(reordered: Stage[]): void {
		stages = reordered;
	}
	function handleStageActivate(stageId: string): void {
		if (stageId === activeStageId) return;
		activeStageId = stageId;
		activeWaypointId = null;
		addModeHint = false;
	}
	function handlePauseInsert(afterIndex: number): void {
		const newPause: Stage = { id: newId(), name: 'Pausentag', date: '', waypoints: [] };
		const updated = [...stages];
		updated.splice(afterIndex + 1, 0, newPause);
		stages = updated;
	}
	// Bug #708 — Etappe entfernen: erst Dialog zeigen, dann per confirmRemoveStage löschen.
	function confirmRemoveStage(): void {
		if (!pendingRemoveStageId) return;
		const stageId = pendingRemoveStageId;
		stages = stages.filter(s => s.id !== stageId);
		if (activeStageId === stageId) {
			activeStageId = stages[0]?.id ?? '';
		}
		pendingRemoveStageId = null;
	}
	function handleAddStage(): void {
		const newStage: Stage = { id: newId(), name: 'Neue Etappe', date: '', waypoints: [] };
		stages = [...stages, newStage];
	}

	// Profil-Klick → interpolierten Wegpunkt einfügen.
	// Issue #503: KEIN suggested-Flag mehr — alle Wegpunkte sind gleichwertig.
	function handleProfileAdd(fraction: number): void {
		if (!activeStage) return;
		const { lat, lon, elevation_m, insertAfterIndex } = interpolateWaypoint(
			activeStage.waypoints,
			fraction
		);
		const newWp: Waypoint = {
			id: newId(),
			name: 'Neuer Punkt',
			lat,
			lon,
			elevation_m
		};
		stages = stages.map((s) => {
			if (s.id !== activeStage.id) return s;
			const wps = [...s.waypoints];
			wps.splice(insertAfterIndex + 1, 0, newWp);
			return { ...s, waypoints: wps };
		});
		activeWaypointId = newWp.id;
		addModeHint = false;
	}

	function handleWaypointActivate(waypointId: string): void {
		activeWaypointId = waypointId;
	}

	function handleMapClick(lat: number, lon: number): void {
		if (!activeStage || activeIsPause) return;
		const stage = activeStage;
		const newWp: Waypoint = { id: newId(), name: '', lat, lon, elevation_m: 0 };
		stages = stages.map((s) =>
			s.id !== stage.id ? s : { ...s, waypoints: [...s.waypoints, newWp] }
		);
		activeWaypointId = newWp.id;
		// Bug #1194 — fehlender Save-Trigger: ohne dies wird ein per Kartentipp
		// angelegter Wegpunkt nie gespeichert und geht bei Reload verloren.
		if (saveController) scheduleSave(); else void save();
	}

	// Waypoint-Mutations (Factory-Pattern fuer WaypointCard-Callbacks).
	// Issue #503: nur noch Umbenennen + Löschen — kein Confirm/Reject mehr.
	function makeActivateHandler(waypointId: string) {
		return function handleActivate() {
			activeWaypointId = waypointId;
		};
	}
	function handleStageRename(stageId: string, currentName: string): void {
		const newName = prompt('Etappenname:', currentName);
		if (!newName?.trim()) return;
		stages = stages.map((s) => (s.id !== stageId ? s : { ...s, name: newName.trim() }));
		if (saveController) scheduleSave(); else void save();
	}

	function makeRenameHandler(stageId: string, waypointId: string) {
		return function handleRename() {
			const newName = prompt('Neuer Name:');
			if (!newName) return;
			stages = stages.map((s) =>
				s.id !== stageId
					? s
					: {
							...s,
							waypoints: s.waypoints.map((w) => (w.id !== waypointId ? w : { ...w, name: newName }))
						}
			);
		};
	}
	function makeDeleteHandler(stageId: string, waypointId: string) {
		return function handleDelete() {
			stages = stages.map((s) =>
				s.id !== stageId ? s : { ...s, waypoints: s.waypoints.filter((w) => w.id !== waypointId) }
			);
		};
	}
</script>

<div data-testid="edit-stages-panel" class="flex flex-col gap-4">
	<!-- EtappenStrip (volle Breite, eigene Navigations-Achse) -->
	<EtappenStrip
		{stages}
		{activeStageId}
		onStagesReorder={handleStagesReorder}
		onStageActivate={handleStageActivate}
		onPauseInsert={handlePauseInsert}
		onRemoveStage={(id) => { pendingRemoveStageId = id; }}
		onAddStage={handleAddStage}
	/>

	{#if activeStage && !activeIsPause}
		<!-- Issue #963: Map-First-Reorder — auf Mobil per CSS `order` (Style-Block)
		     direkt unter die Tab-Leiste vorgezogen, vor EtappenStrip/Etappen-Header/
		     Cascade-Strip. Höhe = JS-berechnet aus gemessener Oberkante + BottomNav-
		     Reservierung, siehe $effect + MOBILE_EDITOR_MIN_HEIGHT_PX/BOTTOM_NAV_HEIGHT_PX
		     (F001/F002/F004). -->
		<div
			class="mobile-editor"
			data-testid="mobile-editor"
			bind:this={mobileEditorEl}
			style="height: {mobileEditorHeightPx}px"
		>
			<div class="mobile-map-wrap" style="position:relative;width:100%;height:100%;z-index:0">
				{#key activeStageId}
					<MapCanvas
						stage={activeStage}
						{activeWaypointId}
						onWaypointActivate={handleWaypointActivate}
						onMapClick={handleMapClick}
						sizeKey={mobileSizeKey}
						fillHeight={true}
					/>
				{/key}
				<!-- EtappenSwitcher-Pill oben links (AC-3/AC-4) -->
				<button
					type="button"
					class="stage-switcher-pill"
					data-testid="stage-switcher-pill"
					onclick={() => { stageSheetOpen = true; }}
				>
					{activeStageIndex + 1} / {stages.length} · {activeStage.name}
				</button>
				<MapControl onAddWaypoint={() => { addModeHint = true; }} />
			</div>
			<ProfileSheetEmbedded
				stage={activeStage}
				{activeWaypointId}
				snapPosition={mobileSnap}
				onWaypointActivate={handleWaypointActivate}
				onProfileAdd={handleProfileAdd}
				onSnapChange={(snap) => { mobileSnap = snap; mobileSizeKey++; }}
			/>
			{#if stageSheetOpen}
				<StageSelectSheet
					{stages}
					activeIndex={activeStageIndex}
					open={true}
					onSelect={(i) => { handleStageActivate(stages[i].id); stageSheetOpen = false; }}
					onClose={() => { stageSheetOpen = false; }}
				/>
			{/if}
		</div>
	{/if}

	{#if activeStage}
		{#if activeIsPause}
			<PauseStageView
				stage={activeStage}
				{prevStage}
				{nextStage}
				onDateChange={(newDate) => handleDateChange(activeStage!.id, newDate)}
			/>
		{:else}
			<!-- Issue #585: Inhaltsbereich mit Padding 20/40/60 + maxWidth 1480 -->
			<div style="position:relative; padding:20px 40px 60px; max-width:1480px;">
			<!-- Etappen-Header mit editierbarem Datum (Issue #498) -->
			<div class="flex items-start justify-between gap-8">
				<div class="min-w-0 flex-1">
					<Eyebrow>Etappe · {activeStage.code ?? ''}</Eyebrow>
					<div class="flex items-center gap-2">
						<p style="font-size:32px; font-weight:600; letter-spacing:-0.02em;" class="truncate">{activeStage.name}</p>
						<button
							onclick={() => handleStageRename(activeStage!.id, activeStage!.name)}
							style="flex-shrink:0; color:var(--g-ink-3); padding:4px; border-radius:4px; background:none; border:none; cursor:pointer; line-height:1;"
							title="Etappenname ändern"
							aria-label="Etappenname ändern"
						><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg></button>
					</div>
					<div style="font-size:14px; color:var(--g-ink-3); margin-top:4px; max-width:680px;">
						Wegpunkte sind <strong style="color:var(--g-ink)">Wetterscheiden</strong> — Punkte, an denen sich Höhe, Exposition oder Geländekammer ändert. Aus der GPX sind {activeStage.waypoints.length} Wegpunkte entstanden — du kannst sie umbenennen, verschieben, löschen oder eigene ergänzen.
					</div>
				</div>
				<div class="stage-header-fields">
					<StageDateField
						value={activeStage.date}
						isFirst={activeStageIndex === 0}
						onchange={(newDate) => handleDateChange(activeStage!.id, newDate)}
					/>
					<StageTimeField
						value={activeStage.start_time}
						onchange={(newTime) => handleStartTimeChange(activeStage!.id, newTime)}
					/>
				</div>
			</div>

			{#if cascade && activeStageIndex === 0}
				{#if !cascade.done}
					<div
						class="cascade-prompt"
						data-testid="cascade-strip"
						bind:this={cascadeEl}
						style="--gz-cascade-bottom: {cascadeBottomPx}px"
					>
						<p>
							<strong
								>Tourstart um {cascade.days > 0 ? '+' : ''}{cascade.days}
								{Math.abs(cascade.days) === 1 ? 'Tag' : 'Tage'} verschoben.</strong
							>
							Sollen die {cascade.count} Folge-Etappen um denselben Betrag mitverschoben werden?
						</p>
						<!-- Bug #1389 F004: während der Verarbeitung nicht erneut auslösbar
						     und sichtbar im Wartezustand. Der Riegel in applyCascade() ist
						     die Absicherung; hier soll der zweite Tipp gar nicht erst
						     angeboten werden. -->
						<div class="cascade-actions">
							<Btn variant="accent" size="sm" onclick={applyCascade} disabled={cascadeBusy}>
								{cascadeBusy ? 'Wird verschoben …' : 'Alle mitverschieben'}
							</Btn>
							<Btn variant="outline" size="sm" onclick={dismissCascade} disabled={cascadeBusy}>Nur diese Etappe</Btn>
						</div>
					</div>
				{:else}
					<div
						class="cascade-done"
						data-testid="cascade-done"
						bind:this={cascadeEl}
						style="--gz-cascade-bottom: {cascadeBottomPx}px"
					>
						<Dot tone="success" />
						<span>
							<strong>{cascade.count} Folge-Etappen verschoben</strong> · alle Daten um
							{cascade.days > 0 ? '+' : ''}{cascade.days}
							{Math.abs(cascade.days) === 1 ? 'Tag' : 'Tage'} angepasst.
						</span>
						<Btn variant="ghost" size="sm" onclick={dismissCascade}>Schließen</Btn>
					</div>
				{/if}
			{/if}

			<!-- Issue #503: Grid 1fr / 360px — Karte+Profil links, Wegpunkte rechts -->
			<div class="editor-grid" data-testid="editor-grid">
				<!-- Linke Spalte: Karte-Card + Profil-Card -->
				<div class="editor-left">
					<!-- Karten-Card (Leaflet/OpenTopoMap) -->
					<div class="editor-card" data-testid="map-card">
						<div class="editor-card-header">
							<Eyebrow>Karte · OpenTopoMap (OSM + SRTM)</Eyebrow>
							<Pill tone="ghost">Topo</Pill>
						</div>
						{#key activeStageId}
						<MapCanvas
							stage={activeStage}
							{activeWaypointId}
							onWaypointActivate={handleWaypointActivate}
						/>
					{/key}
					</div>

					{#if addModeHint}
						<div class="add-mode-hint" role="status" data-testid="add-mode-hint">
							<span>Klicke im Höhenprofil, um einen Wegpunkt einzufügen</span>
							<button class="add-mode-hint-close" aria-label="Hinweis schließen" onclick={() => { addModeHint = false; }}>×</button>
						</div>
					{/if}

					<!-- Profil-Card (Höhenprofil) -->
					<div class="editor-card editor-card--padded" data-testid="profile-card">
						<div class="editor-card-header editor-card-header--inline">
							<Eyebrow>Höhenprofil · synchron mit Karte</Eyebrow>
						</div>
						<ProfileEditor
							stage={activeStage}
							{activeWaypointId}
							onWaypointActivate={handleWaypointActivate}
							onProfileAdd={handleProfileAdd}
						/>
					</div>
				</div>

				<!-- Rechte Spalte: Wegpunkt-Sidebar-Card -->
				<div class="editor-card editor-sidebar" data-testid="waypoint-sidebar">
					<div class="editor-card-header sidebar-header">
						<div>
							<Eyebrow>Wegpunkte</Eyebrow>
							<div class="sidebar-count">{activeStage.waypoints.length} insgesamt</div>
						</div>
						<Btn variant="ghost" size="sm" data-testid="waypoint-add-on-route-btn" onclick={() => { addModeHint = true; }}>
							+ auf Route
						</Btn>
					</div>
					<div class="sidebar-list">
						{#each activeStage.waypoints as waypoint, i (waypoint.id)}
							<WaypointCard
								{waypoint}
								index={i}
								active={waypoint.id === activeWaypointId}
								arrival={arrivals[i] ?? null}
								onActivate={makeActivateHandler(waypoint.id)}
								onRename={makeRenameHandler(activeStage.id, waypoint.id)}
								onDelete={makeDeleteHandler(activeStage.id, waypoint.id)}
							/>
						{/each}
						{#if activeStage.waypoints.length === 0}
							<p class="sidebar-empty">Keine Wegpunkte.</p>
						{/if}
					</div>
				</div>
			</div>
			</div><!-- /Issue #585 content wrapper -->
		{/if}
	{/if}

	{#if showSave && !saveController}
		<div class="save-bar">
			<Btn variant="primary" size="sm" onclick={save} disabled={saving || !tripId}>
				{saving ? 'Speichern …' : 'Etappen speichern'}
			</Btn>
			{#if saveSuccess}<span class="save-ok">Gespeichert ✓</span>{/if}
			{#if saveError}<span class="save-err">{saveError}</span>{/if}
		</div>
	{/if}
</div>

<!-- Bug #708 — Bestätigungs-Dialog für Etappen-Löschen -->
<Dialog.Root
	open={pendingRemoveStageId !== null}
	onOpenChange={(open) => { if (!open) pendingRemoveStageId = null; }}
>
	<Dialog.Content>
		<Dialog.Header>
			<Dialog.Title>Etappe löschen</Dialog.Title>
			<Dialog.Description>
				Möchtest du „{stages.find(s => s.id === pendingRemoveStageId)?.name ?? ''}" wirklich löschen? Diese Aktion kann nicht rückgängig gemacht werden.
			</Dialog.Description>
		</Dialog.Header>
		<Dialog.Footer>
			<Btn variant="outline" data-testid="cancel-delete-stage" onclick={() => { pendingRemoveStageId = null; }}>Abbrechen</Btn>
			<Btn variant="destructive" data-testid="confirm-delete-stage" onclick={confirmRemoveStage}>Löschen</Btn>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>

<style>
	/* Issue #675 — Startzeit-Feld neben Datum-Feld im Header */
	.stage-header-fields {
		display: inline-flex;
		align-items: flex-end;
		gap: 8px;
	}

	/* Issue #498 — Cascade-Strip (Tourstart-Verschiebung Folge-Etappen?) */
	.cascade-prompt,
	.cascade-done {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 10px 14px;
		background: var(--g-accent-tint);
		border: 1px solid var(--g-rule);
		border-left: 3px solid var(--g-accent-deep);
		border-radius: 4px;
		font-size: 13px;
		color: var(--g-ink);
	}
	.cascade-prompt p {
		flex: 1;
		margin: 0;
	}
	.cascade-actions {
		display: flex;
		gap: 6px;
		flex-shrink: 0;
	}
	.cascade-done span {
		flex: 1;
	}

	/* Issue #503 — Grid-Layout: Karte+Profil links (1fr), Wegpunkte rechts (360px). */
	.editor-grid {
		display: grid;
		grid-template-columns: 1fr 360px;
		gap: 24px;
		align-items: start;
	}
	.editor-left {
		display: flex;
		flex-direction: column;
		gap: 16px;
		min-width: 0;
	}

	/* Issue #503 — Karten-/Profil-/Wegpunkt-Cards (weiße Surface, hoher Kontrast). */
	.editor-card {
		background: var(--g-card, #ffffff);
		border: 1px solid var(--g-ink-faint);
		border-radius: var(--g-radius-md, 6px);
		overflow: hidden;
		box-shadow: var(--g-shadow-1, 0 1px 3px rgba(0, 0, 0, 0.08));
	}
	.editor-card--padded {
		padding-bottom: 8px;
	}
	.editor-card-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 12px 18px;
		border-bottom: 1px solid var(--g-ink-faint);
	}
	.editor-card-header--inline {
		border-bottom: none;
		padding-bottom: 4px;
	}

	.editor-sidebar {
		display: flex;
		flex-direction: column;
		min-height: 0;
	}
	.sidebar-header {
		gap: 12px;
	}
	.sidebar-count {
		font-size: 14px;
		font-weight: 600;
		color: var(--g-ink);
		margin-top: 2px;
	}
	.sidebar-list {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding: 4px 6px 8px;
		overflow-y: auto;
	}
	.sidebar-empty {
		padding: 14px;
		font-size: var(--g-text-sm, 13px);
		color: var(--g-ink-muted);
		margin: 0;
	}

	/* Issue #542: Mobile-Editor — Vollbild-Karte + Bottom-Sheet */
	.mobile-editor {
		display: none;
		position: relative;
	}

	.stage-switcher-pill {
		position: absolute;
		top: 12px;
		left: 12px;
		z-index: 20;
		padding: 6px 14px;
		background: var(--g-card);
		border: 1px solid var(--g-rule);
		border-radius: 20px;
		box-shadow: var(--g-shadow-2, 0 2px 6px rgba(26, 26, 24, 0.12));
		font-size: 13px;
		font-weight: 600;
		color: var(--g-ink);
		cursor: pointer;
		white-space: nowrap;
		font-family: var(--g-font-mono, 'JetBrains Mono', monospace);
	}

	/* Mobile: zeige Mobile-Editor, verstecke Desktop-Grid.
	   Issue #963 — Map-First-Reorder: `order:-1` zieht `.mobile-editor` innerhalb
	   des flex-col-Containers (`edit-stages-panel`) vor EtappenStrip/Etappen-Header/
	   Cascade-Strip, ohne die DOM-Reihenfolge (und damit die Desktop-Darstellung)
	   zu verändern — auf Desktop bleibt `.mobile-editor` ohnehin `display:none`. */
	@media (max-width: 899px) {
		.mobile-editor {
			display: block;
			order: -1;
		}
		.editor-grid {
			display: none;
		}
		/* Bug #1375 — Kaskaden-Rückfrage auf Mobil sichtbar halten.
		   Der Streifen steckt im Inhalts-Wrapper (padding 20/40/60), der als
		   regulärer Flex-Block hinter der per `order:-1` vorgezogenen Karte
		   einsortiert wird — er landete dadurch bei y≈1300px, weit unter dem
		   844px-Viewport, und wurde nie gesehen. Statt den DOM umzubauen (das
		   verschöbe den Desktop-Ort) wird er auf Mobil zum fixen Banner:
		   unabhängig von der Scrollposition im Bildschirmausschnitt.
		   Fix-Loop 1 (Staging-Befund): die Unterkante liefert `--gz-cascade-bottom`
		   aus dem Platzierungs-$effect oben — der Banner weicht den Karten-
		   steuerelementen (#963, top:12px) nach oben aus, statt sie zu verdecken.
		   Der Fallback-Wert gilt nur, falls das Skript (noch) nicht gemessen hat. */
		.cascade-prompt,
		.cascade-done {
			position: fixed;
			left: 8px;
			right: 8px;
			bottom: var(--gz-cascade-bottom, calc(72px + env(safe-area-inset-bottom)));
			z-index: 62; /* über Bottom-Sheet (61) und BottomNav (50) */
			flex-direction: column;
			align-items: stretch;
			/* --g-accent-tint ist transluzent (8%) — über der Karte unlesbar. */
			background: var(--g-card);
			box-shadow: 0 6px 20px rgba(26, 26, 24, 0.18);
		}
	}
	.save-bar {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding-top: 0.5rem;
	}
	.save-ok {
		font-size: 0.875rem;
		color: var(--g-success);
	}
	.save-err {
		font-size: 0.875rem;
		color: var(--g-danger, #b34a2a);
	}

	/* Bug #524 — Info-Strip „+ auf Route" Klick-Hinweis */
	.add-mode-hint {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 6px 12px;
		background: var(--g-surface-2, #f0ede8);
		border-left: 3px solid var(--g-accent);
		font-size: 13px;
		color: var(--g-ink-2);
		margin-bottom: 4px;
		border-radius: 3px;
	}
	.add-mode-hint-close {
		background: none;
		border: none;
		cursor: pointer;
		font-size: 16px;
		line-height: 1;
		color: var(--g-ink-3);
		padding: 0 4px;
	}
</style>
