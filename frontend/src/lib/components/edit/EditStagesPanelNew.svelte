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
	import StageDateField from './StageDateField.svelte';
	import StageTimeField from './StageTimeField.svelte';
	import { computeCascadeDelta, consecutiveDates, formatDeDate } from './cascade.ts';
	import { Eyebrow, Btn, Dot, Pill } from '$lib/components/atoms';
	import { computeArrivalTimes, activityToSpeed } from '$lib/utils/naismith';
	import { interpolateWaypoint } from '$lib/utils/waypointEditor';
	import type { ActivityType, Stage, Trip, Waypoint } from '$lib/types';
	import { api } from '$lib/api.js';
	import { baueTripSpeicherung } from '$lib/components/shared/tripSpeicherung';
	import { merkeNutzlast } from '$lib/stores/nutzlastStand';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import type { SaveFn, SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import { onMount } from 'svelte';
	// Mobile Usability Paket 1 (Spec mobile_stages_tab_listen_only, Iteration 1):
	// PO-Entscheid F5 (2026-09-22, Variante B) — Karte + Höhenprofil entfallen
	// auf Mobile ersatzlos. Der Mobile-Zweig rendert Desktop-Hinweis + Liste.
	import SortableList from '$lib/components/shared/dnd/SortableList.svelte';
	import DragHandle from '$lib/components/shared/dnd/DragHandle.svelte';
	import StageCardM from '$lib/components/mobile/StageCardM.svelte';
	import { fetchStageRisk, type StageRisk } from '$lib/utils/stageRisk';

	interface Props {
		stages: Stage[];
		tripId?: string;
		showSave?: boolean;
		activityType?: ActivityType;
		onTripUpdate?: (updated: Trip) => void;
		/** Issue #758: SaveStatus controller from +page.svelte. When provided, removes explicit save button. */
		saveController?: SaveStatus;
		/** Unten belegte Hoehe (px, ohne Safe-Area); fehlt ⇒ schwebende BottomNav. */
		bottomReservePx?: number;
	}
	let { stages = $bindable(), tripId, showSave = true, activityType, onTripUpdate, saveController, bottomReservePx }: Props = $props();

	let saving = $state(false);
	let saveSuccess = $state(false);
	let saveError = $state<string | null>(null);
	let addModeHint = $state(false);
	// Bug #708 — Etappen-Löschen mit Bestätigungs-Dialog (kein sofortiges Löschen)
	let pendingRemoveStageId = $state<string | null>(null);

	// Mobile Usability Paket 1 — Viewport-Weiche für den Listen-only-Zweig.
	// Muster: TripTabs.svelte (matchMedia 899px). Desktop-Zweig unverändert.
	let isMobileViewport = $state(false);
	onMount(() => {
		const mq = window.matchMedia('(max-width: 899px)');
		isMobileViewport = mq.matches;
		const onChange = (e: MediaQueryListEvent) => { isMobileViewport = e.matches; };
		mq.addEventListener('change', onChange);
		return () => mq.removeEventListener('change', onChange);
	});

	// F7: pro Etappen-Karte aufklappbare Wegpunkt-Zeilen — eine Karte offen,
	// Tap auf dieselbe klappt wieder zu.
	let expandedStageId = $state<string | null>(null);
	function toggleStageExpanded(stageId: string): void {
		expandedStageId = expandedStageId === stageId ? null : stageId;
	}

	// F3: „+ Etappe" öffnet die Wahl Etappe/Pausentag (ersetzt den
	// Desktop-Hover-Gap PauseInsertGap, der mobil nicht bedienbar war).
	// Der Pausentag bekommt bewusst KEINEN Namen: isPauseStage() erkennt
	// „leer + keine Wegpunkte" als Pause, einen Namen wie 'Pausentag'
	// dagegen nicht (#559-Ausnahme) — die Karte rendert den Titel selbst.
	let addChoiceOpen = $state(false);
	function handleMobileAddPause(): void {
		if (cascadeBusy) return;
		stages = [...stages, { id: newId(), name: '', date: '', waypoints: [] }];
	}

	// Risiko-Ampel je Etappe für die StageCardM (lazy, fail-soft) — gleiche
	// Datenquelle wie HubOverview/TripStageRow (#1223), kein eigener Endpoint.
	let stageRisk: Record<string, StageRisk> = $state({});
	$effect(() => {
		if (!tripId) return;
		const id = tripId;
		fetchStageRisk(id).then((m) => {
			if (id === tripId) stageRisk = m;
		});
	});

	// SortableList (ADR-0024) meldet ID-Reihenfolgen; der Streifen arbeitet
	// mit Stage[]. Adapter — die Sortier-Logik selbst bleibt unverändert.
	function handleMobileReorder(newOrder: string[]): void {
		const byId = new Map(stages.map((s) => [s.id, s]));
		const reordered = newOrder.map((id) => byId.get(id)).filter((s): s is Stage => !!s);
		if (reordered.length === stages.length) handleStagesReorder(reordered);
	}


	// Bug #1393 R4: `payload` erlaubt applyCascade(), einen NOCH NICHT übernommenen
	// Stand zu schreiben und ihn erst nach Bestätigung in `stages` zu heben.
	async function save(payload: Stage[] = stages): Promise<Trip | null> {
		if (!tripId) return null;
		saving = true;
		saveError = null;
		try {
			const updatedTrip = await api.put<Trip>(`/api/trips/${tripId}`, { stages: payload });
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
	// Bug #1393 R6-F001: der Stand wird ERST BEIM AUSLÖSEN gelesen, nicht beim
	// Anmelden eingefangen. Ein zurückgestellter Vorgang liegt beliebig lange
	// herum (er feuert nur bei der Antwort auf die Rückfrage oder beim Verlassen
	// der Seite) — mit einer Kopie von damals schrieb er einen veralteten Stand
	// und drehte ein inzwischen bestätigtes Kaskadenergebnis wieder zurück.
	// Änderung liegt komplett in dieser Funktion; der Speicher-Regler
	// (`SaveStatus`) bleibt unangetastet, andere Nutzer sind nicht betroffen.
	function buildStagesSave(): SaveFn {
		// Rumpf als Funktion: `stages` wird erst beim Ausloesen gelesen (R6-F001).
		return baueTripSpeicherung<Trip>(
			api, tripId!, () => ({ stages }), (updatedTrip) => onTripUpdate?.(updatedTrip), 'etappen'
		);
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

	// Issue #498 / Bug #1393 — Kaskaden-Strip: Etappen HINTER der bearbeiteten
	// lückenlos durchdatieren? Die Rückfrage kommt bei JEDER Etappe (vorher nur
	// bei der ersten — wer Etappe 2, 3 oder 7 umdatierte, bekam gar keine).
	interface CascadeState {
		done: boolean;
		// Bug #1390: die Rückfrage gehört zu einer IDENTITÄT, nicht zu einer Position.
		// Vorher hing ihre Sichtbarkeit an `activeStageIndex === 0` — zog der Nutzer
		// die bearbeitete Etappe im Streifen von Platz 1 weg, während die Rückfrage
		// noch offen war, verschwand sie ersatzlos: beide Knöpfe unerreichbar, die
		// Entscheidung weiter offen, der Anzeiger dauerhaft auf „Nicht gespeichert".
		/** Etappe, deren Datum die Rückfrage ausgelöst hat. */
		stageId: string;
		// Bug #1389 Adversary F005 (CRITICAL): die UNVERÄNDERLICHE Grundlage der
		// Rechnung, festgehalten beim Aufstellen der Rückfrage. Vorher rechnete
		// applyCascade() aus dem laufend mutierten Zustand — ein Wiederholungs-Klick
		// nach einem Fehlschlag addierte den Versatz nochmal (Funkloch-Alltag der
		// Zielgruppe). Bug #1393: diese Grundlage ist jetzt NUR NOCH der Anker —
		// Etappe + gewähltes Datum. Die Zieldaten sind Anker+1, Anker+2, … und
		// hängen an nichts sonst, deshalb ist die Rechnung von sich aus idempotent.
		//
		// Bug #1393 Runde 4: hier standen zuvor `applied` (was optimistisch
		// geschrieben wurde) und `touched` (was der Nutzer selbst angefasst hat).
		// Beide gab es nur, um einen halbfertigen lokalen Zustand wieder
		// einzufangen. Seit applyCascade() nicht mehr optimistisch schreibt, gibt es
		// keinen solchen Zustand — und damit auch nichts zu buchhalten.
		/** Datum der bearbeiteten Etappe, BEVOR der Nutzer es angefasst hat. */
		baseFirstDate: string;
		/** Bug #1393: das GEWÄHLTE Datum — Anker, ab dem durchdatiert wird. */
		anchorDate: string;
	}
	let cascade = $state<CascadeState | null>(null);
	// Bug #1389 Adversary F004: Reentrancy-Riegel für applyCascade() — schaltet
	// zugleich den Knopf ab, damit ein zweiter Tipp gar nicht erst angeboten wird.
	let cascadeBusy = $state(false);
	// Bug #1393 R6-F002: Obergrenze für den Kaskaden-Schreibvorgang. `cascadeBusy`
	// sperrt die baulichen Änderungen am Etappen-Streifen; ohne Deckel bliebe der
	// Streifen gesperrt, solange die Antwort ausbleibt — im Funkloch also für die
	// restliche Lebensdauer der Seite, genau dort, wo die Zielgruppe unterwegs ist.
	// Der Deckel sitzt bewusst am Schreibvorgang selbst (AbortController) statt nur
	// an der Sperre: so hängt danach auch kein Request mehr im Hintergrund, der
	// später doch noch einschlägt und einen inzwischen überholten Stand festschreibt.
	// 15 s liegt weit über jeder normalen Antwortzeit.
	const CASCADE_WRITE_TIMEOUT_MS = 15_000;
	// Bug #1390: sichtbar, solange es die auslösende Etappe noch gibt — unabhängig
	// davon, an welcher Position sie steht und welche Etappe gerade aktiv ist. Eine
	// ausstehende Entscheidung muss erreichbar bleiben.
	const cascadeVisible = $derived(!!cascade && stages.some((s) => s.id === cascade!.stageId));
	// Bug #1393: Etappen HINTER `idx` mit Datum, in ihrer Reihenfolge — die
	// Reihenfolge IST die Rechnung (erste = Anker+1, jede weitere einen Tag
	// später). Etappen ohne Datum bleiben draußen: sie bleiben ohne Datum und
	// verbrauchen keinen Tag.
	function followersAfter(idx: number): string[] {
		return stages.slice(idx + 1).filter((s) => s.date).map((s) => s.id);
	}
	// Bug #1393 Adversary F001/F002: LIVE aus der aktuellen Liste abgeleitet, NICHT
	// beim Aufstellen der Rückfrage eingefroren. Eine eingefrorene Liste ging an
	// jeder Änderung vorbei, die der Nutzer vor seiner Antwort noch macht: eine
	// gelöschte Folge-Etappe hinterließ eine Lücke (Anker+2 statt Anker+1), und
	// eine vor den Anker gezogene Etappe bekam trotzdem ihr späteres Datum — sie
	// stand dann vorne und trug das SPÄTESTE Datum. Die Etappenreihenfolge steuert,
	// welcher Tag welche Vorhersage bekommt; das darf nicht auseinanderlaufen.
	const cascadeFollowers = $derived.by(() => {
		if (!cascade) return [];
		const idx = stages.findIndex((s) => s.id === cascade!.stageId);
		return idx < 0 ? [] : followersAfter(idx);
	});
	// Benannt wird, was WIRKLICH betroffen ist — Etappen davor und solche ohne
	// Datum zählen nicht mit.
	const cascadeCount = $derived(cascadeFollowers.length);
	const cascadeCountText = $derived(
		cascadeCount === 1 ? 'die folgende Etappe' : `die ${cascadeCount} folgenden Etappen`,
	);
	// Datum, das die erste Folge-Etappe bekäme — aus derselben Rechnung wie
	// applyCascade(), damit Ankündigung und Ergebnis nicht auseinanderlaufen.
	const cascadeFirstDate = $derived.by(() => {
		if (!cascade) return '';
		const targets = consecutiveDates(cascade.anchorDate, cascadeFollowers);
		return formatDeDate(targets[cascadeFollowers[0]] ?? '');
	});

	function handleDateChange(stageId: string, newDate: string): void {
		const idx = stages.findIndex((s) => s.id === stageId);
		if (idx < 0) return;
		const oldDate = stages[idx].date;

		// Datum + dateOverridden-Flag setzen, ohne andere Stages anzufassen.
		stages = stages.map((s, i) =>
			i === idx ? { ...s, date: newDate, dateOverridden: true } : s,
		);

		// Bug #1389 F005 / #1390: gehört zu DIESER Etappe (Identität, nicht Position —
		// nach einem Umsortieren steht auf Platz 0 womöglich eine andere) eine
		// unbeantwortete Rückfrage? Dann bleibt ihre Grundlage stehen, sonst wäre
		// `oldDate` beim zweiten Umdatieren nur der Zwischenstand.
		const open = cascade !== null && !cascade.done && cascade.stageId === stageId;
		// Bug #1393: KEIN `idx === 0`-Gate mehr — gefragt wird bei jeder Etappe mit
		// gültigem altem Datum. Bug #1390 F001/F002: bei offener Rückfrage bleibt die
		// Grundlage stehen, sonst rechnete eine zweite Korrektur gegen den
		// Zwischenstand und der Banner bliebe auf dem veralteten Stand.
		if (oldDate) {
			const baseFirstDate = open ? cascade!.baseFirstDate : oldDate;
			const delta = computeCascadeDelta(baseFirstDate, newDate);
			// Nichts dahinter (letzte Etappe, oder dahinter nur Etappen ohne Datum)?
			// Dann gibt es nichts zu entscheiden — eine Rückfrage über null betroffene
			// Etappen wäre eine Zumutung ohne Inhalt. Still speichern.
			if (delta !== 0 && followersAfter(idx).length > 0) {
				// Bug #1393 R4-F002: eine noch offene Rückfrage zu einer ANDEREN Etappe
				// wurde bisher still von dieser hier ersetzt — die erste Entscheidung
				// verfiel unbeantwortet und ihr zurückgestellter Schreibvorgang blieb
				// liegen. Sie wird jetzt als „Nur diese Etappe" beantwortet UND
				// geschrieben; das ist die konservative Lesart und verliert nichts.
				if (!open) dismissCascade();
				cascade = { stageId, done: false, baseFirstDate, anchorDate: newDate };
				// Bug #1389: NICHT sofort speichern. Der frühere 700ms-Auto-Save trug den
				// Stand „Etappe 1 neu, Folge-Etappen ALT"; bei Antwort nach >700ms waren
				// zwei Schreibvorgänge unterwegs und der veraltete konnte gewinnen (das
				// Backend ersetzt die Etappen komplett, ohne Reihenfolge-Garantie).
				// Geschrieben wird erst mit der Antwort — genau EIN PUT. Der zurückgestellte
				// Stand bleibt `hasPending` für beforeNavigate (Bezug #1376).
				deferSave();
				return;
			} else if (open) {
				// F001: die eigene, jetzt gegenstandslose Rückfrage abräumen (Δ=0 —
				// der Nutzer ist auf das Ausgangsdatum zurück). Bug #1393: nur die
				// EIGENE — seit jede Etappe fragt, hinge sonst die offene Entscheidung
				// einer anderen Etappe mit dran und verschwände ungeantwortet.
				cascade = null;
			}
		}
		// Keine Kaskade (letzte Etappe / nichts dahinter / Δ=0): sofort auto-speichern.
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
		// `cascade.done` fällt erst nach dem ersten `await` — zwei Tipps im selben
		// Tick kamen beide durch und verschoben ZWEIMAL (s2 auf +42 statt +21).
		if (cascadeBusy) return;
		if (!cascade || cascade.done) return;
		// Adversary MEDIUM: Zustand festhalten. `dismissCascade()` kann im selben Tick
		// `cascade = null` setzen; `{ ...cascade, done: true }` ergäbe dann `{}` und der
		// Erfolgsbanner stünde ohne Anzahl und Tageszahl da.
		const active = cascade;
		cascadeBusy = true;
		try {
			// Bug #1389 F005: aus der festgehaltenen Grundlage rechnen, NICHT aus dem
			// (womöglich schon verschobenen) Stand — dadurch ist der Aufruf idempotent.
			// Bug #1393: Zieldaten sind Anker+1, +2, … — lückenlos statt „gleicher
			// Versatz". Bug #1390: id-basiert; die auslösende Etappe steht nicht in der
			// Liste und bleibt dadurch von selbst unangetastet, egal an welcher
			// Position sie inzwischen steht. F001/F002: die Liste wird JETZT gelesen,
			// damit sie der Etappenfolge entspricht, die der Nutzer vor sich sieht.
			const targets = consecutiveDates(active.anchorDate, cascadeFollowers);
			// Bug #1393 R4-F001: NICHT optimistisch übernehmen. Der neue Stand wird
			// berechnet und geschrieben; in `stages` wandert er erst, wenn der Server
			// ihn bestätigt hat. Vorher entstand bei jedem Fehlschlag ein halbfertiger
			// lokaler Zustand, den zwei Merker (`applied`, `touched`) und eine
			// Rücknahme wieder einfangen mussten — und der dabei mal das Original, mal
			// die eigene Eingabe des Nutzers verschluckte. Jetzt gibt es nichts
			// zurückzunehmen: was nicht bestätigt ist, wurde nie angezeigt.
			//
			// Bug #1393 R5-F001: die Zieldaten werden auf die LEBENDE Liste angewandt,
			// nicht auf einen vorab eingefrorenen Rumpf — sonst machte eine Änderung
			// des Nutzers an der Liste die Zuweisung danach wieder zunichte (eine
			// gelöschte Etappe kehrte zurück, im Backend wie in der Anzeige).
			const withTargets = (list: Stage[]): Stage[] =>
				list.map((s) => (targets[s.id] ? { ...s, date: targets[s.id], dateOverridden: true } : s));
			if (saveController) {
				// Issue #1376: den offenen Debounce aus handleDateChange verwerfen — er
				// trägt einen veralteten Schnappschuss und überschriebe sonst das gleich
				// folgende Kaskaden-Ergebnis.
				saveController.cancel();
				saveController.setSaving();
				// Flush immediately (cascade = user intent, no debounce needed).
				const ctrl = new AbortController();
				const capTimer = setTimeout(() => ctrl.abort(), CASCADE_WRITE_TIMEOUT_MS);
				try {
					const updatedTrip = await api.put<Trip>(
						`/api/trips/${tripId!}`,
						{ stages: withTargets(stages) },
						{ signal: ctrl.signal },
					);
					stages = withTargets(stages);
					cascade = { ...active, done: true };
					// Bug #1393 R6-F001 (zweite Schicht): hat der Nutzer WÄHREND des
					// Schreibens etwas geändert, liegt dafür ein zurückgestellter Vorgang
					// an. Dann wäre „gespeichert" gelogen — und die Server-Antwort trägt
					// den Stand VOR seiner Änderung; nach oben durchgereicht schriebe der
					// Elternteil sie über die Bindung (`trip = updated`) wieder zurück und
					// die Eingabe wäre still weg. Also: dirty lassen, den vorgemerkten
					// Vorgang die Wahrheit schreiben lassen — er liest den aktuellen Stand.
					if (saveController.hasPending) {
						saveController.setDirty();
					} else {
						saveController.setSaved();
						onTripUpdate?.(updatedTrip);
					}
				} catch (e: unknown) {
					if ((e as { status?: number })?.status === 412) {
						// Issue #1433 Fix-Loop: Konflikt statt Sackgasse. Das alte If-Match bleibt bis
						// „Nochmal speichern" stehen — ein zurueckgestellter Vorgang scheiterte sonst
						// immer wieder. Die Kaskade ist die Antwort des Nutzers: sie bleibt stehen
						// (Seitenstand = Server ⊕ ausstehende Nutzlast) und der Eintrag 'etappen' liest
						// beim Retry den lebenden Stand. Kein `init` (das Abbruch-Signal gilt nur hier).
						stages = withTargets(stages);
						cascade = { ...active, done: true };
						saveController.meldeKonflikt(merkeNutzlast(buildStagesSave(), { stages }), e);
						return;
					}
					// R6-F002: der Abbruch nach der Obergrenze braucht eine Meldung, die
					// erklärt, was los ist — „Speichern fehlgeschlagen" allein sagt dem
					// Nutzer im Funkloch nichts.
					const msg = ctrl.signal.aborted
						? 'Zeitüberschreitung beim Speichern — bitte erneut versuchen.'
						: e instanceof Error
							? e.message
							: 'Speichern fehlgeschlagen';
					// Bug #1389 F006 (Spiegelfall): `cancel()` oben hat den zurückgestellten
					// Save abgeräumt — ohne Neu-Anmeldung fänden `beforeNavigate` und
					// Reiterwechsel nichts vor, die Datumsänderung an der bearbeiteten
					// Etappe ginge still verloren. R4: gerettet wird genau diese Änderung
					// (der lokale Stand), nicht mehr eine unbestätigte Kaskade.
					// Reihenfolge: `deferSave()` setzt `dirty`, deshalb MUSS `setError()`
					// danach kommen.
					deferSave();
					saveController.setError(msg);
				} finally {
					clearTimeout(capTimer);
				}
			} else {
				const result = await save(withTargets(stages));
				if (result !== null) {
					stages = withTargets(stages);
					cascade = { ...active, done: true };
				}
			}
		} finally {
			cascadeBusy = false;
		}
	}

	function dismissCascade(): void {
		// „Nur diese Etappe" ist die ANTWORT — erst jetzt wird geschrieben. Beim
		// „Schließen" des Erfolgs-Streifens (cascade.done) gibt es nichts zu speichern.
		// Adversary F004: läuft eine Kaskaden-Anwendung, hier NICHT dazwischenfunken —
		// sonst kämpfen zwei Schreibvorgänge. Ein Doppeltipp auf diesen Knopf ist
		// unkritisch: synchron, `cascade` wird vor jeder Weitergabe genullt (e2e AC-10).
		if (cascadeBusy) return;
		const open = cascade !== null && !cascade.done;
		cascade = null;
		if (!open) return;

		// Bug #1389 F006: UNBEDINGT schreiben. Ein fehlgeschlagener Kaskaden-Versuch
		// hat den zurückgestellten Save abgeräumt (applyCascade → cancel()) — das
		// frühere `flush()` lief ins Leere und speicherte nichts.
		//
		// Bug #1393 R4: hier stand eine Rücknahme, die einfangen musste, was
		// applyCascade() lokal schon verändert hatte. Seit dort nichts mehr
		// optimistisch übernommen wird, ist der lokale Stand IMMER der bestätigte
		// plus die Änderungen des Nutzers — es gibt nichts zurückzunehmen. „Nur
		// diese Etappe" schreibt genau das, was der Nutzer vor sich sieht.
		if (saveController) {
			saveController.cancel();
			void saveController.doSave(buildStagesSave());
		} else {
			void save();
		}
	}

	// Bug #1393 F001/F002: fällt die LETZTE Folge-Etappe weg — gelöscht oder vor
	// den Anker gezogen —, hat die Rückfrage keinen Inhalt mehr: beide Antworten
	// führten zum selben Ergebnis. Sie stehenzulassen hieße, eine Entscheidung
	// über null Etappen zu verlangen und den zurückgestellten Speichervorgang
	// liegenzulassen. Also wie „Nur diese Etappe" behandeln — wegräumen UND
	// schreiben (Bug #1389 F006: nie still verwerfen).
	function settleMootCascade(): void {
		if (cascade && !cascade.done && cascadeFollowers.length === 0) dismissCascade();
	}

	// EtappenStrip-Handler
	// Bug #1393 R5-F001: bauliche Änderungen (Umsortieren, Löschen, Hinzufügen)
	// sind gesperrt, solange eine Antwort auf die Rückfrage geschrieben wird. Der
	// Streifen ist dabei sichtbar gesperrt (`locked`), diese Riegel sind die
	// zweite Linie für Tastatur- und Programmwege. Sonst fällt der gerade
	// abgeschickte Stand gegen die Liste auseinander, die der Nutzer vor sich hat.
	function handleStagesReorder(reordered: Stage[]): void {
		if (cascadeBusy) return;
		// Bug #1393 R2-F002: hier NICHT über die Rückfrage entscheiden. Der Streifen
		// meldet jede Zwischenposition während des Ziehens; streifte die Karte
		// unterwegs die letzte Stelle, wurde die Rückfrage mitten in der Geste als
		// „Nur diese Etappe" beantwortet und geschrieben — die Absicht des Nutzers
		// stillschweigend umgedeutet, noch bevor er die Maus losließ. Bewertet wird
		// erst beim Ablegen (`onReorderEnd`).
		stages = reordered;
	}
	function handleReorderEnd(): void {
		settleMootCascade();
	}
	function handleStageActivate(stageId: string): void {
		if (stageId === activeStageId) return;
		activeStageId = stageId;
		activeWaypointId = null;
		addModeHint = false;
	}
	function handlePauseInsert(afterIndex: number): void {
		if (cascadeBusy) return; // R5-F001
		const newPause: Stage = { id: newId(), name: 'Pausentag', date: '', waypoints: [] };
		const updated = [...stages];
		updated.splice(afterIndex + 1, 0, newPause);
		stages = updated;
	}
	// Bug #708 — Etappe entfernen: erst Dialog zeigen, dann per confirmRemoveStage löschen.
	function confirmRemoveStage(): void {
		if (cascadeBusy) return; // R5-F001
		if (!pendingRemoveStageId) return;
		const stageId = pendingRemoveStageId;
		stages = stages.filter(s => s.id !== stageId);
		if (activeStageId === stageId) {
			activeStageId = stages[0]?.id ?? '';
		}
		// Bug #1390: verschwindet die auslösende Etappe, ist die Rückfrage
		// gegenstandslos — sonst bliebe eine Leiche stehen, deren „Alle
		// mitverschieben" Etappen wegen einer nicht mehr existierenden Änderung
		// verschöbe. Der zurückgestellte Speichervorgang trägt noch den Stand VOR dem
		// Löschen (er würde die Etappe wiederauferstehen lassen) und wird deshalb mit
		// dem aktuellen Stand neu aufgesetzt statt verworfen — verwerfen wäre der
		// stille Datenverlust aus F006.
		if (cascade?.stageId === stageId) {
			cascade = null;
		} else {
			// Bug #1393 F001: eine FOLGE-Etappe ist verschwunden. Die Rückfrage bleibt
			// gültig — sie zählt und rechnet live weiter, es entsteht keine Lücke.
			// Nur wenn dadurch gar nichts mehr dahinter liegt, ist sie gegenstandslos.
			settleMootCascade();
		}
		// Bug #1393 R5: das Neu-Anmelden gilt für JEDE gelöschte Etappe, nicht nur für
		// die auslösende. Ein zurückgestellter Speichervorgang (etwa nach einem
		// fehlgeschlagenen Kaskaden-Versuch) trägt sonst weiter den Stand VOR dem
		// Löschen und lässt die Etappe beim nächsten Flush wiederauferstehen.
		if (saveController?.hasPending) deferSave();
		pendingRemoveStageId = null;
	}
	function handleAddStage(): void {
		if (cascadeBusy) return; // R5-F001
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

<!-- Bug #1390: EIN Kaskaden-Banner fuer beide Etappen-Ansichten. Als Snippet,
     weil der Inhaltsbereich fuer Wander-Etappen und die PauseStageView getrennte
     Zweige sind — stand der Streifen nur im Wander-Zweig, verschwand die offene
     Rueckfrage beim Anklicken eines Pausentags genauso wie beim Umsortieren. -->
{#snippet cascadeBanner()}
	{#if cascade && cascadeVisible}
		{#if !cascade.done}
			<div
				class="cascade-prompt"
				data-testid="cascade-strip"
			>
				<!-- Bug #1393: kein „Trip-Start" mehr (es kann jede Etappe sein) und kein
				     „derselbe Betrag" (es wird lückenlos durchdatiert). -->
				<p>
					<strong>Diese Etappe liegt jetzt am {formatDeDate(cascade.anchorDate)}.</strong>
					{cascadeCount === 1 ? 'Soll' : 'Sollen'}
					{cascadeCountText} lückenlos anschließen, ab {cascadeFirstDate}?
				</p>
				<!-- Bug #1389 F004: während der Verarbeitung nicht erneut auslösbar.
				     Der Riegel in applyCascade() ist die eigentliche Absicherung. -->
				<div class="cascade-actions">
					<Btn variant="accent" size="sm" onclick={applyCascade} disabled={cascadeBusy}>
						{cascadeBusy ? 'Wird angepasst …' : 'Lückenlos anschließen'}
					</Btn>
					<Btn variant="outline" size="sm" onclick={dismissCascade} disabled={cascadeBusy}>Nur diese Etappe</Btn>
				</div>
			</div>
		{:else}
			<div
				class="cascade-done"
				data-testid="cascade-done"
			>
				<Dot tone="success" />
				<span>
					<strong>Lückenlos neu datiert</strong> · {cascadeCountText}, ab {cascadeFirstDate}.
				</span>
				<Btn variant="ghost" size="sm" onclick={dismissCascade}>Schließen</Btn>
			</div>
		{/if}
	{/if}
{/snippet}

<div data-testid="edit-stages-panel" class="flex flex-col gap-4">
	{#if isMobileViewport}
		<!-- Mobile Usability Paket 1 (PO-Entscheid F5, 2026-09-22): Listen-only.
		     Karte/Profil/Sheet entfallen ersatzlos; Hinweis + vertikale Liste.
		     F2: Kaskaden-Banner rendert als normale Zeile über der Liste —
		     kein position:fixed mehr (Karten-Viewport existiert nicht mehr). -->
		<div class="mobile-stages" data-testid="mobile-stages-list">
			<div class="desktop-hint" data-testid="desktop-hint">
				<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 8v5M12 16h.01"/></svg>
				<p><strong>Karte &amp; Höhenprofil</strong> sind am Desktop verfügbar. Das Gesamt-Höhenprofil bleibt im Übersichts-Tab.</p>
			</div>
			<div class="mobile-list-head">
				<span class="mobile-list-eyebrow">{stages.length} Etappen · ziehen zum Sortieren</span>
				<!-- F3: „+ Etappe" öffnet die Wahl Etappe/Pausentag (ersetzt den
				     Desktop-Hover-Gap, der mobil nicht bedienbar war). Die Wahl
				     steht als eigene Zeile im Fluss — nichts überlappt, keine
				     Koordinaten-Races beim Tap. -->
				<button
					type="button"
					class="mobile-add-btn"
					data-testid="mobile-add-stage"
					aria-expanded={addChoiceOpen}
					onclick={() => { addChoiceOpen = !addChoiceOpen; }}
					disabled={cascadeBusy}
				>
					+ Etappe
				</button>
			</div>
			{#if addChoiceOpen}
				<div class="mobile-add-choice" data-testid="mobile-add-choice" role="menu">
					<button type="button" role="menuitem" onclick={() => { handleAddStage(); addChoiceOpen = false; }}>Etappe</button>
					<button type="button" role="menuitem" onclick={() => { handleMobileAddPause(); addChoiceOpen = false; }}>Pausentag</button>
				</div>
			{/if}
			{@render cascadeBanner()}
			<SortableList
				items={stages.map((s) => s.id)}
				onDndReorder={handleMobileReorder}
				onDndReorderEnd={handleReorderEnd}
				ariaLabel="Etappen, Reihenfolge"
				itemLabel={(id, i) => `${i + 1}. ${stages.find((s) => s.id === id)?.name || 'Pausentag'}`}
				zoneClass="stage-cardm-zone"
				flipDurationMs={150}
			>
				{#snippet row(id: string, i: number)}
					{@const stage = stages.find((s) => s.id === id)}
					{#if stage}
						<!-- F7: Tap auf die Karte klappt die Wegpunkt-Zeilen auf/zu. -->
						<div
							class="stage-cardm-row"
							data-testid="stage-cardm-row"
							role="button"
							tabindex="0"
							aria-expanded={expandedStageId === stage.id}
							onclick={() => toggleStageExpanded(stage.id)}
							onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleStageExpanded(stage.id); } }}
						>
							<DragHandle />
							<StageCardM
								{stage}
								index={i}
								risk={stageRisk[stage.id]}
								open={expandedStageId === stage.id}
								{activityType}
								isFirst={i === 0}
								onDateChange={(d) => handleDateChange(stage.id, d)}
							/>
						</div>
					{/if}
				{/snippet}
			</SortableList>
		</div>
	{:else}
	<!-- EtappenStrip (volle Breite, eigene Navigations-Achse) -->
	<EtappenStrip
		{stages}
		{activeStageId}
		onStagesReorder={handleStagesReorder}
		onReorderEnd={handleReorderEnd}
		locked={cascadeBusy}
		onStageActivate={handleStageActivate}
		onPauseInsert={handlePauseInsert}
		onRemoveStage={(id) => { if (!cascadeBusy) pendingRemoveStageId = id; }}
		onAddStage={handleAddStage}
	/>

	{#if activeStage}
		{#if activeIsPause}
			{@render cascadeBanner()}
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

			{@render cascadeBanner()}

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
			<!-- Bug #1393 R5-F002: NICHT `onclick={save}` — der Browser übergäbe das
			     Klick-Ereignis als `payload` und schriebe `{ stages: <MouseEvent> }`. -->
			<Btn variant="primary" size="sm" onclick={() => save()} disabled={saving || !tripId}>
				{saving ? 'Speichern …' : 'Etappen speichern'}
			</Btn>
			{#if saveSuccess}<span class="save-ok">Gespeichert ✓</span>{/if}
			{#if saveError}<span class="save-err">{saveError}</span>{/if}
		</div>
	{/if}
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
			<Btn variant="destructive" data-testid="confirm-delete-stage" onclick={confirmRemoveStage} disabled={cascadeBusy}>Löschen</Btn>
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

	/* Issue #498 — Cascade-Strip (Trip-Start-Verschiebung Folge-Etappen?) */
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

	/* ── Mobile Usability Paket 1 — Listen-only-Mobile-Zweig ──
	   Desktop-Hinweis bewusst NEUTRAL (--g-card-alt/--g-rule, kein Accent):
	   reine Info ohne Call-to-Action (Charter §6, AP-015), statisch. */
	.mobile-stages {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-3);
		padding: var(--g-s-3) var(--g-s-4) var(--g-s-4);
	}
	.desktop-hint {
		display: flex;
		align-items: flex-start;
		gap: var(--g-s-3);
		padding: var(--g-s-3);
		background: var(--g-card-alt);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3);
		color: var(--g-ink-3);
		font-size: var(--g-text-sm);
		line-height: 1.45;
	}
	.desktop-hint p {
		margin: 0;
		color: var(--g-ink-2);
	}
	.mobile-list-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--g-s-3);
	}
	.mobile-list-eyebrow {
		font-family: var(--g-font-mono);
		font-size: var(--g-text-xs);
		font-weight: 600;
		letter-spacing: var(--g-track-caps);
		text-transform: uppercase;
		color: var(--g-ink-muted);
	}
	.mobile-add-btn {
		min-height: 44px;
		padding: 0 var(--g-s-4);
		background: transparent;
		border: 1px dashed var(--g-rule);
		border-radius: var(--g-r-3);
		color: var(--g-ink-3);
		font-family: var(--g-font-mono);
		font-size: var(--g-text-xs);
		font-weight: 600;
		letter-spacing: var(--g-track-wide);
		text-transform: uppercase;
		cursor: pointer;
	}
	.mobile-add-btn:hover {
		border-color: var(--g-accent);
		color: var(--g-accent);
	}
	/* F3 — Wahl Etappe/Pausentag als eigene Zeile im Fluss (nicht überlappend). */
	.mobile-add-choice {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--g-s-2);
	}
	.mobile-add-choice button {
		min-height: 44px;
		padding: 0 var(--g-s-4);
		background: var(--g-card);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3);
		text-align: center;
		font-size: var(--g-text-sm);
		font-weight: 500;
		color: var(--g-ink);
		cursor: pointer;
	}
	.mobile-add-choice button:hover {
		border-color: var(--g-accent);
		color: var(--g-accent);
	}
	.stage-cardm-row {
		display: flex;
		align-items: stretch;
		gap: var(--g-s-2);
	}
	.stage-cardm-row :global(.drag-handle) {
		align-self: stretch;
		min-width: 44px;
		min-height: 44px;
	}
	.stage-cardm-row :global(.stage-cardm) {
		flex: 1;
		min-width: 0;
	}
</style>
