<script lang="ts">
	// Issue #491 — Compare-Preset Detail-Seite.
	// Issue #493 — Mobile-Responsive: TopBar + SubscriptionActionSheet.
	// Issue #1256 Scheibe 8 (AC-22, Ein-Mount-Strategie): der mobile Bespoke-
	// Block (2×2-5-Karten-Grid + flache Standort-Liste) entfaellt — CompareDetail
	// wird jetzt GENAU EINMAL gemountet und versorgt Desktop UND Mobile; die
	// Viewport-Umschaltung (4-Stat-2×2 statt 5-Stat-Leiste, CorridorEditorMobile
	// im Idealwerte-Tab) passiert INNERHALB von CompareTabs (matchMedia).
	import CompareDetail from '$lib/components/compare/CompareDetail.svelte';
	import StatusSchild from '$lib/components/shared/status-schild/StatusSchild.svelte';
	import {
		aboKanaele,
		RUECKMELDUNG_MS,
		testAlarmErgebnis,
		testErgebnis,
		type Berichtsart,
		type TestKanal
	} from '$lib/components/molecules/testSchickenModell';
	import SubscriptionActionSheet from '$lib/components/mobile/SubscriptionActionSheet.svelte';
	import { subscriptionActions } from '$lib/components/shared/subscriptionActions.js';
	import { deleteSubscription, sendSubscription, sendTestAlarm, setArchived } from '$lib/components/shared/subscriptionExec.js';
	import { erfolgsText, fehlerText } from '$lib/components/shared/kebabBestaetigung.js';
	import { aktivierungsUebernahme, fehltFuerAktivierung, hinweisFuer, zielFuer } from '$lib/components/shared/entwurfAktivieren';
	import { erstelleAktivierungsWechsel } from '$lib/components/shared/aktivierungsWechsel.svelte';
	import {
		deriveStatusWithScheduleOverride,
		isRuntimeExceeded,
		compareFilterStatus
	} from '$lib/components/compare/subscriptionHelpers.js';
	import { page } from '$app/state';
	import { browser } from '$app/environment';
	import { goto, beforeNavigate } from '$app/navigation';
	import { createSaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import { sichereAusstehendeSpeicherung } from '$lib/stores/ausstehendeSpeicherungSichern';
	import { getContext, onMount, untrack } from 'svelte';
	import { AKTIVE_SPEICHERUNG, type SpeicherAnmeldestelle } from '$lib/stores/aktiveSpeicherung';
	import {
		inhaltsFassung,
		starteNachladenNachEntladen,
		vergleichNachladeQuelle
	} from '$lib/stores/nachEntladenNachladen';
	import { api, getMitFassung } from '$lib/api';
	import { baueSpeicherung, speichereKopfFeld } from '$lib/components/shared/tripSpeicherung';
	import { adoptEtagBeiSeitenaufbau, adoptEtagFromPageLoad } from '$lib/etagRegistry';
	import type { ComparePreset } from '$lib/types';
	import HubKopf from '$lib/components/shared/hub-kopf/HubKopf.svelte';
	import type { TripStatus } from '$lib/utils/tripStatus';
	// Issue #2659 (i18n F10): Texte aus dem Katalog — Aktionen/Senden wortgleich zum Trip-Hub
	// (aktionen.*). Fehler ohne Server-Text halten nur den Schluessel (Sprachwechsel ohne Neuladen).
	import { locale, t, tn } from '$lib/i18n';

	let { data } = $props();

	// Epic #1273 S2, Adversary-Fund (live gegen Staging, nicht durch Code-
	// Lesung auffindbar): `data` aus $props() ist NICHT tief-reaktiv fuer
	// Nested-Mutation — `data.preset = updated` erzeugte zwar eine neue
	// Objekt-Referenz, aber KEIN {@const}/$derived, das `currentPreset.X` liest,
	// hat das reaktiv mitbekommen (bewiesen: Name/Region "funktionierten" nur
	// zufaellig, weil der isEditingX-Toggle denselben Zweig neu mountet und
	// dabei `currentPreset.name` frisch auswertet — die Aktivitaetsprofil-
	// Kacheln haben keinen solchen Toggle und blieben sichtbar auf dem alten
	// Wert stehen, obwohl der PUT serverseitig erfolgreich war). Fix: echter
	// $state-Spiegel, exakt das Muster aus CompareTabs.svelte (`currentPreset
	// = $state<ComparePreset>(preset)` + Resync-$effect auf Prop-Referenz).
	let currentPreset = $state(data.preset);
	// Issue #2375: Seitenaufbau-ETag uebernehmen (Trip-Muster trips/[id]/+page.svelte),
	// damit schon der ERSTE Schreibvorgang nach dem Laden `If-Match` traegt.
	// Bewusst nur von `data` abhaengig, nicht vom lokalen `currentPreset`.
	// Fix-Loop 1 (#1433, F003): frischer Seitenaufbau beendet einen offenen Konflikt (Paritaet zum Trip).
	const seitenaufbauStempelUebernommen = browser && data.etag ? adoptEtagBeiSeitenaufbau(data.preset.id, data.etag) : false;
	$effect(() => {
		if (data.etag) adoptEtagFromPageLoad(data.preset.id, data.etag);
	});
	$effect(() => {
		currentPreset = data.preset;
	});

	// Epic #1273 S1: SaveStatus-Controller fuer den Hub — eine Instanz pro
	// Compare-Detail-Seite (kein Singleton!), analog tripSaveCtl in
	// routes/trips/[id]/+page.svelte:22. Wird an CompareDetail/CompareTabs
	// durchgereicht. Die meisten Commit-Handler (Orte/Wertebereiche/Versand/
	// Aktiv-Status) treiben ihn weiterhin manuell (nicht via schedule()); der
	// Alarme-Reiter speichert seit Issue #2276 S2 selbst ueber
	// saveController.schedule() (analog dem Trip-Zweig), siehe
	// shared/alarmeVergleichSpeicherung.ts.
	// Issue #2276 S2: mit Kennung — ein 412 wird zu „Nochmal speichern“ (conflict).
	const hubSaveCtl = createSaveStatus({ typ: 'vergleich', id: data.preset.id });

	// Issue #2316 Scheibe A (AC-9): derselbe Speicher-Wächter wie /trips/[id] —
	// vorher hatte der Hub gar keinen beforeNavigate-Wächter, eine getippte,
	// noch nicht committete Änderung ging beim Neuladen verloren.
	// Issue #2317 Baustein 3: mit Kennung — beim Entladen entsteht der Nachlade-Merker.
	beforeNavigate((navigation) =>
		sichereAusstehendeSpeicherung(navigation, hubSaveCtl, goto, { typ: 'vergleich', id: currentPreset.id })
	);

	// Issue #2317 Baustein 2: Anmeldung an der Anmeldestelle des Layouts (wie /trips/[id]).
	const speicherAnmeldestelle = getContext<SpeicherAnmeldestelle | undefined>(AKTIVE_SPEICHERUNG);

	// Issue #2317 Baustein 3: derselbe Nachlade-Baustein wie /trips/[id]. Ohne
	// ETag im Seitenaufbau vergleicht er den Inhalt. Die Reiter (CompareTabs,
	// Idealwerte) hydrieren ihren Zustand nur einmal aus `preset` — nach einer
	// Uebernahme wird CompareDetail deshalb neu aufgebaut ({#key} unten), mit dem
	// gerade offenen Reiter (CompareTabs schreibt ihn per replaceState in die
	// Adresse, an SvelteKits `page.url` vorbei).
	let uebernommeneFassung = $state(0);
	let tabNachUebernahme = $state<string | null>(null);

	// Fix-Loop 1 (#1433, F001/AC-20): „Nochmal speichern" gibt den per GET geholten
	// Vergleich an die Seite, BEVOR es die Eintraege erneut sendet (Paritaet zu
	// /trips/[id]); der Hub baut sich danach neu auf, mit dem offenen Reiter.
	// Fix-Loop 2 (F101): anders als beim Trip wird `currentPreset` bei 'geholt' NICHT gesetzt —
	// CompareTabs.svelte:717 hydriert den offenen Reiter reaktiv auf jede neue `preset`-
	// Referenz neu und wuerde die sichtbare Eingabe mit dem GET-Stand ueberschreiben. Die
	// AC-19-Uebernahme erfolgt in Compare erst nach vollem Retry-Erfolg ('wiederholt'):
	// dann frisch holen (der GET-Stand von vorher enthielte die gerade gesendeten Felder
	// nicht) und den Hub neu aufbauen. Scheitert dieser GET, bleibt der Hub unangetastet.
	const abmeldenUebernahme = hubSaveCtl.registriereUebernahme((_stand, phase) => {
		if (phase === 'wiederholt') void uebernehmeFrischenVergleich();
	});

	// Fix-Loop 3 (F207): der GET braucht Zeit. Kam danach etwas Neues (ausstehende/laufende
	// Eingabe, anderer Speichervorgang ⇒ Stempel der Registry hat gewechselt), ist der
	// geholte Stand AELTER als der Stempel — dann KEIN Neuaufbau (nie nur eines von beiden;
	// Muster `uebernehmeNachStatusAenderung` der Trip-Seite).
	// #3442: liefert, ob der frische Stand übernommen wurde (Archivieren/Reaktivieren auf der Seite).
	// #3443: `nurWenn` (Entwurf) übernimmt nur einen Stand, der die Aktivierung bewirkt.
	async function uebernehmeFrischenVergleich(nurWenn: ((frisch: ComparePreset) => boolean) | null = null): Promise<boolean> {
		try {
			const frisch = await getMitFassung<ComparePreset>(`/api/compare/presets/${data.preset.id}`);
			if (!frisch.inRegistry || hubSaveCtl.hasPending || hubSaveCtl.state !== 'idle') return false;
			if (nurWenn && !nurWenn(frisch.daten)) return false;
			tabNachUebernahme = new URL(window.location.href).searchParams.get('tab');
			currentPreset = frisch.daten;
			uebernommeneFassung += 1;
			return true;
		} catch {
			/* kein Neuaufbau: der Reiter zeigt bereits die gespeicherte Eingabe */
			return false;
		}
	}

	onMount(() => {
		const abmelden = speicherAnmeldestelle?.anmelden(hubSaveCtl);
		const nachladen = starteNachladenNachEntladen<ComparePreset>({
			kennung: { typ: 'vergleich', id: data.preset.id },
			ctl: hubSaveCtl,
			ausgelieferteFassung: inhaltsFassung(data.preset),
			holen: vergleichNachladeQuelle<ComparePreset>(data.preset.id),
			uebernehmen: (stand) => {
				tabNachUebernahme = new URL(window.location.href).searchParams.get('tab');
				currentPreset = stand;
				uebernommeneFassung += 1;
			}
		});
		return () => {
			abmelden?.();
			abmeldenUebernahme();
			nachladen.stoppen();
		};
	});

	// Staging-Fund SF-2 (CRITICAL, AC-37): der Hub (CompareTabs) haelt fuer die
	// Aktivierungs-Karte einen eigenen `localSchedule`-Zustand und PUT-Pfad
	// (ohne invalidateAll() — das wuerde die dortige eingefrorene-Prop-Baseline
	// mit frisch geladenen `data` kollidieren lassen). Diese Header-Status-Pille
	// las bislang AUSSCHLIESSLICH `data.preset`, das nur der Kebab-Pfad
	// (togglePause -> invalidateAll()) aktualisiert — nach einem Pausieren/
	// Aktivieren aus der Karte blieb die Pille auf dem alten Status stehen.
	// `scheduleOverride` wird vom CompareTabs-Callback gesetzt und verwirft
	// sich selbst, sobald `data` durch einen echten Reload (invalidateAll)
	// neu ankommt — die dann gelieferten Server-Daten sind wieder autoritativ.
	let scheduleOverride = $state<string | null>(null);
	// #3442 (AC-5/AC-10): Archiv-Status nach Archivieren/Reaktivieren aus dem Menü, Muster wie scheduleOverride.
	let archivOverride = $state<boolean | null>(null);
	$effect(() => {
		void data;
		scheduleOverride = null;
		archivOverride = null;
	});
	const archiviert = $derived(archivOverride ?? currentPreset.archived_at != null);
	function handleScheduleChange(schedule: string): void {
		scheduleOverride = schedule;
	}

	let status = $derived(deriveStatusWithScheduleOverride(currentPreset, scheduleOverride));
	// #2913 Scheibe c2 (AC-5): Status-Pill mit allen fünf Zuständen wie beim Trip — archiviert
	// (archived_at), fertig (Enddatum vor heute, Regel wie compareFilterStatus), sonst wie bisher.
	let kopfStatus: TripStatus = $derived(
		archiviert
			? 'archived'
			: status !== 'draft' && compareFilterStatus(currentPreset) === 'fertig'
				? 'finished'
				: status
	);
	// #2913 c2 (AC-4): Eyebrow „Orte · Region", Meta „N Orte · Briefing HH:MM" (#3438: ohne
	// „Vergleichstabelle", Mockup Fassung 4, ADR-0124 Nr. 10). Ohne Region nur „Orte" (wie beim Trip).
	const kopfRegion = $derived((currentPreset.display_config?.region as string | undefined) || '');
	const kopfEyebrow = $derived(kopfRegion ? $t('aktionen.kopf.eyebrow_orte', { region: kopfRegion }) : $t('aktionen.kopf.eltern_orte'));
	const metaTeile = $derived.by(() => {
		const p = currentPreset;
		const teile = [$tn('listen.anzahl.orte', p.location_ids.length)];
		if (p.morning_enabled && p.morning_time) teile.push($t('aktionen.kopf.morgen_briefing', { zeit: p.morning_time.slice(0, 5) }));
		else if (p.evening_enabled && p.evening_time) teile.push($t('aktionen.kopf.abend_briefing', { zeit: p.evening_time.slice(0, 5) }));
		return teile;
	});
	// Issue #1250 Scheibe 3 (AC-12): Hub-Hinweis, wenn Auto-Pause wegen
	// ueberschrittenem end_date gegriffen hat.
	let runtimeExceeded = $derived(isRuntimeExceeded(currentPreset));
	// Issue #2284 S1 — Speicherweg des geteilten Kopfs (SubscriptionHeader).
	// #2796 S4a (ADR-0108 P3): keine Profil-Auswahl mehr im Kopf, kein Speicherweg `profil`
	// aus dem Hub — die Vorlage (Reiter Wetter) ersetzt das Profil; `profil` bleibt gespeichert.
	// KRITISCH (#2375/#2381): NUR das eigene Feld senden ({ name } /
	// { display_config: { region } }), KEIN Spread von currentPreset — der Go-Handler
	// mergt fehlende Felder als „unveraendert"; ein Spread der (hier veralteten)
	// Seiten-Kopie schriebe Reiter-Werte anderer Tabs/desselben Tabs zurueck. Nach Erfolg
	// currentPreset MIT NEUER OBJEKT-REFERENZ ersetzen (Resync in CompareTabs, AC-5).
	// Issue #1433: eigener Konflikt-Eintrag je Kopf-Feld; ein 412 geht an den Controller
	// („Nochmal speichern", Muster TripHeader) — sonst Sackgasse, weil das alte If-Match
	// bis zum Retry stehen bleibt.
	// Vertrag mit dem Baustein — drei Ausgaenge:
	//   (a) gespeichert            ⇒ `schliessen()` (Feld zu), Promise erfuellt
	//   (b) 412 an den Controller  ⇒ Promise erfuellt OHNE `schliessen()`: Feld bleibt offen,
	//       keine eigene Meldung; `schliessen()` folgt, wenn „Nochmal speichern" gelingt
	//   (c) jeder andere Fehler    ⇒ wirft, der Baustein zeigt die Meldung am Feld
	const KOPF_RUMPF = {
		name: (v: string) => ({ name: v }),
		region: (v: string) => ({ display_config: { region: v } })
	};
	const KOPF_SCHLUESSEL = { name: 'kopf-name', region: 'kopf-region' };
	// Die Signatur bleibt die des Kopfs (Feld-Typ inkl. 'profile'); ohne Auswahlliste ruft
	// der Kopf 'profile' nie auf — ein solcher Aufruf ist ein Programmierfehler.
	async function onSaveField(field: 'name' | 'region' | 'profile', value: string, schliessen: () => void): Promise<void> {
		if (field === 'profile') throw new Error('profile is not saved from the comparison header (#2796)');
		const pfad = `/api/compare/presets/${currentPreset.id}`;
		const speichern = baueSpeicherung<ComparePreset>(api, pfad, KOPF_RUMPF[field](value), (updated) => {
			// Waehrend „Nochmal speichern" NICHT uebernehmen: eine neue `preset`-Referenz baut
			// die Reiter in CompareTabs neu auf, ueber Eingaben, die der Retry gleich noch
			// sendet (F101). Der Neuaufbau folgt nach vollem Erfolg ('wiederholt').
			if (!hubSaveCtl.imWiederholen) currentPreset = updated;
			schliessen();
		}, KOPF_SCHLUESSEL[field]);
		await speichereKopfFeld(speichern, hubSaveCtl);
	}

	// Issue #517 — ?tab=-Query-Parameter lesen und an CompareDetail/CompareTabs weitergeben.
	const initialTab = $derived(page.url.searchParams.get('tab') ?? 'uebersicht');

	let actionSheetOpen = $state(false);
	// Issue #2278 AC-12: Lebenszyklus-Menue wie beim Trip — Desktop = Dropdown, Mobil = Aktionsblatt.
	let mobil = $state(false);
	const lifecycle = $derived(archiviert ? 'archived' : status);
	// Issue #2659 (i18n F10): Aktionsliste je Sprache (wortgleich zum Trip-Hub, aktionen.*).
	const hubAktionen = $derived.by(() => (void $locale, subscriptionActions('vergleich', lifecycle, 'hub')));
	onMount(() => {
		const mq = window.matchMedia('(max-width: 899px)');
		const update = () => (mobil = mq.matches);
		update();
		mq.addEventListener('change', update);
		return () => mq.removeEventListener('change', update);
	});

	// Issue #528 — Status-abhängige Header-Primäraktion.
	let isSending = $state(false);
	let sendStatus = $state<'idle' | 'ok' | 'error'>('idle');
	let sendMsg = $state<string | null>(null);
	let sendTimer: ReturnType<typeof setTimeout> | undefined = undefined;
	// #3442: Meldung einer Menü-Aktion als Text aus kebabBestaetigung (wie im Trip-Hub); `aktionOk` färbt sie.
	let aktionMsg = $state<string | null>(null);
	let aktionOk = $state(false);
	function meldung(text: string | null, ok = false): void {
		aktionMsg = text;
		aktionOk = ok;
	}
	// #3443: Reiter wie Orte speichern am Seitenstand vorbei — im Entwurf nach jedem erfolgreichen Speichern
	// den gespeicherten Stand prüfen und nur übernehmen, wenn er aktiviert (Pill, Knopf, „Aktiviert …“ ohne Neuladen).
	$effect(() => {
		if (hubSaveCtl.savedAt) untrack(() => { const pruefe = aktivierungsUebernahme(lifecycle); if (pruefe) void uebernehmeFrischenVergleich(pruefe); });
	});
	// #3443: Wechsel Entwurf → aktiv (nach dem Speichern der Orte) meldet „Aktiviert …“ mit dem ersten Briefing.
	erstelleAktivierungsWechsel(
		() => ({ context: 'vergleich', id: currentPreset.id, lifecycle: lifecycle }),
		(p) => api.get(p),
		(text) => meldung(text, true)
	);
	// #3443: „Aktivieren“ (Kopf-Knopf und Kebab) schreibt nichts — nennt, was fehlt, und öffnet den Reiter Orte.
	function handleAktivieren(): void {
		const teile = fehltFuerAktivierung('vergleich', currentPreset);
		const hinweis = hinweisFuer(teile);
		if (!hinweis) return;
		meldung(hinweis, true);
		const ziel = zielFuer('vergleich', teile);
		if (ziel) void goto(ziel, { noScroll: true, keepFocus: true });
	}
	// Gewählte Menü-Aktion: Pausieren/Fortsetzen teilen den Toggle-Weg, die Meldung unterscheidet sie.
	let gewaehlt = '';

	// #3440: Menü „Test schicken ▾“ wie im Trip-Hub — der Klick auf eine Kanalzeile ist die Auslösung.
	async function handleTest(wahl: { kanal: TestKanal; berichtsart: Berichtsart }): Promise<void> {
		clearTimeout(sendTimer);
		isSending = true;
		sendStatus = 'idle';
		try {
			// Issue #2124/#2280: geteilter Laufzustand (compare:<id>) + Klassifikation,
			// einheitlicher Ausloeser -> POST /api/briefings/{id}/send?kind=vergleich[&channel=].
			const o = await sendSubscription('vergleich', currentPreset.id, {
				channel: wahl.kanal === 'alle' ? undefined : wahl.kanal
			});
			const r = testErgebnis({
				context: 'vergleich',
				wahl,
				ergebnis: o,
				profil: data.profile,
				abo: aboKanaele('vergleich', currentPreset),
				jetzt: new Date()
			});
			sendStatus = r.ok ? 'ok' : 'error';
			sendMsg = r.text;
		} finally {
			isSending = false;
		}
		sendTimer = setTimeout(() => { sendStatus = 'idle'; }, RUECKMELDUNG_MS);
	}

	// #3441: Eintrag „Test-Alarm“ wie im Trip-Hub (derselbe Weg, dieselbe Rückmeldung).
	async function handleErweiterung(id: string): Promise<void> {
		if (id !== 'test-alarm' || isSending) return;
		clearTimeout(sendTimer);
		isSending = true;
		sendStatus = 'idle';
		try {
			const r = testAlarmErgebnis({ ergebnis: await sendTestAlarm('vergleich', currentPreset.id), jetzt: new Date() });
			sendStatus = r.ok ? 'ok' : 'error';
			sendMsg = r.text;
		} finally {
			isSending = false;
		}
		sendTimer = setTimeout(() => { sendStatus = 'idle'; }, RUECKMELDUNG_MS);
	}

	let isPausing = $state(false);
	let pauseError = $state(false);

	// Staging-Fund F004 (CRITICAL): kein eigenstaendiger fetch-Pfad mit vollem
	// Objekt-Spread aus `data.preset` mehr (Datenverlust-Risiko in BEIDE
	// Richtungen gegenueber Hub-internen Edits, s. Adversary-Proben
	// probe_kebab_vs_hub_stale_data.mjs / probe_kebab_vs_hub_reverse.mjs) —
	// delegiert stattdessen an denselben `handleToggleActive`-Pfad, den auch
	// die Aktivierungs-Karte im Versand-Tab nutzt (hubPutQueue + currentPreset-
	// Baseline). Kein invalidateAll() mehr noetig: die Pille zieht ueber
	// `onScheduleChange`/`scheduleOverride` mit (s. SF-2-Kommentar oben).
	let compareDetailRef: ReturnType<typeof CompareDetail> | undefined = $state();

	async function togglePause() {
		isPausing = true;
		pauseError = false;
		// Adversary Runde 6 (LOW): Ref-Fallback analog CompareDetail.svelte:24 —
		// ein (noch) undefined `compareDetailRef` faellt jetzt auf denselben
		// Fehlerpfad zurueck statt still (ohne pauseError) zu enden.
		const ok = (await compareDetailRef?.toggleActiveFromParent()) ?? false;
		if (!ok) pauseError = true;
		else meldung(erfolgsText(gewaehlt), true); // #3442 AC-11; Misserfolg bleibt die bisherige Meldung
		isPausing = false;
	}

	let isDeleting = $state(false);

	function handleAction(id: string) {
		// Epic #1273 S3: kein 'edit'/'setup' im Hub; die Aktionen stammen aus
		// subscriptionActions('vergleich', status, 'hub') (Issue #2278).
		// #3442: Archivieren/Loeschen kommen erst nach der Rueckfrage im Menue an.
		gewaehlt = id;
		meldung(null);
		if (id === 'activate') handleAktivieren();
		else if (id === 'pause' || id === 'resume') {
			// 'pause' und 'resume' sind dieselbe Toggle-Aktion.
			void togglePause();
		} else if (id === 'archive') {
			void archivePreset();
		} else if (id === 'unarchive') {
			void unarchivePreset();
		} else if (id === 'delete') {
			void deletePreset();
		}
	}

	// #3442 (AC-5/AC-10): Archivieren/Reaktivieren bleiben auf der Seite. Offene Eingaben zuerst sichern,
	// danach den frischen Stand samt Stempel übernehmen (kein Konflikt-Banner); scheitert das, nur den Status.
	async function archivePreset() {
		try {
			await setArchived('vergleich', currentPreset.id, true);
			nachArchivWechsel('archive');
		} catch (e) {
			meldung(fehlerText('archive', e));
		}
	}

	async function unarchivePreset() {
		try {
			await setArchived('vergleich', currentPreset.id, false);
			nachArchivWechsel('unarchive');
		} catch (e) {
			meldung(fehlerText('unarchive', e));
		}
	}

	// Status sofort über `archivOverride` (kein neues `currentPreset`, das offene Eingaben der Reiter
	// überschriebe); der GET holt den neuen Stempel (PATCH /state ändert ihn) und, wenn nichts offen ist,
	// den frischen Stand — so entsteht beim nächsten Speichern kein Konflikt-Banner.
	function nachArchivWechsel(id: 'archive' | 'unarchive'): void {
		archivOverride = id === 'archive';
		meldung(erfolgsText(id), true);
		void uebernehmeFrischenVergleich();
	}

	async function deletePreset() {
		isDeleting = true;
		try {
			await deleteSubscription('vergleich', currentPreset.id);
			window.location.href = '/compare';
		} catch (e) {
			meldung(fehlerText('delete', e));
		} finally {
			isDeleting = false;
		}
	}
</script>

<!-- Issue #2131 — eigener Seitentitel wie bei der Trip-Ansicht
     (trips/[id]/+page.svelte). Ohne ihn traegt das Dokument nur den
     Platzhalter aus app.html, und die Offline-Uebersicht listet jeden
     Ortsvergleich als „Gregor Zwanzig". -->
<svelte:head><title>{`${currentPreset.name} — ${$t('bausteine.marke.name')}`}</title></svelte:head>

<!-- Hub-Kopf (#491, #493, #582; #2284 S1; #2837 S1, ADR-0110): der geteilte HubKopf trägt
     Leiste (Pfad, Zurück-Pfeil mobil, Senden bzw. im Entwurf „Setup abschließen", Kebab,
     Meldungen) und Titelblock — derselbe Baustein wie im Trip-Hub. Vergleich-eigen bleiben
     Status samt Laufzeit-Hinweis und die Orte-Anzahl (Whitelist, Spec Entscheidung 8). -->
<!-- Status-Snippet ausserhalb des HubKopf-Tags: ein gleichnamiges Kind-Snippet `status` verdeckte dort
     die Seiten-Variable `status` (auch in den Attributen). -->
{#snippet statusBadge()}
	<span class="flex-shrink-0"><StatusSchild status={kopfStatus} testid="trip-detail-status-badge" /></span>
	{#if runtimeExceeded}
		<span data-testid="runtime-exceeded-hint" class="flex-shrink-0 text-[11px] desktop:text-xs" style="font-weight: 600; color: var(--g-bad)">{$t('vergleich.hub.laufzeit_ueberschritten')}</span>
	{/if}
{/snippet}
<!-- Kein eigener Wrapper: Abstand und Unterkante (Linie --g-rule, #582) trägt der HubKopf (Adversary F001). -->
	<HubKopf
		context="vergleich"
		parent={{ label: $t('aktionen.kopf.eltern_orte'), href: '/compare' }}
		crumb={currentPreset.name}
		sendLabel={status === 'draft' ? $t('vergleich.hub.setup_abschliessen') : isSending ? $t('aktionen.wird_gesendet') : $t('aktionen.kopf.test_schicken')}
		sendMode={status === 'draft' ? 'setup' : 'senden'}
		onSetup={() => { window.location.href = `?tab=zustellung#versand`; }}
		onTest={handleTest}
		testProfil={data.profile}
		onErweiterung={handleErweiterung}
		testAlarmLaeuft={isSending}
		sendDisabled={isSending || lifecycle === 'archived'}
		actions={hubAktionen}
		onSelect={handleAction}
		{mobil}
		onSheetOpen={() => (actionSheetOpen = true)}
		name={currentPreset.name}
		region={currentPreset.display_config?.region as string | undefined}
		regionMaxLength={60}
		testidPrefix="compare-hub"
		titleSize={38}
		{onSaveField}
		saveController={hubSaveCtl}
		status={statusBadge}
		eyebrowText={kopfEyebrow}
		{metaTeile}
		onAktivieren={status === 'draft' ? handleAktivieren : undefined}
	>
		{#snippet meldungen()}
			<!-- #2837 S1: Meldungen wie beim Trip in jeder Breite (keine Whitelist-Ausnahme). -->
			<!-- #3440: Rückmeldung wie im Trip-Hub (testids, 5 s, Fehler rot). -->
			{#if sendStatus === 'ok'}
				<span data-testid="test-schicken-ok" style="font-size: 12px; color: var(--g-success)">{sendMsg}</span>
			{:else if sendStatus === 'error'}
				<span data-testid="test-schicken-fehler" style="font-size: 12px; color: var(--g-bad)">{sendMsg}</span>
			{/if}
			{#if aktionMsg}
				<span data-testid={aktionOk ? 'hub-aktion-meldung' : 'compare-hub-aktion-fehler'} style="font-size: 12px; color: {aktionOk ? 'var(--g-success)' : 'var(--g-bad)'}">{aktionMsg}</span>
			{/if}
			{#if pauseError}
				<span style="font-size: 12px; color: var(--g-bad)">{$t('listen.meldung.status_fehlgeschlagen')}</span>
			{/if}
		{/snippet}
	</HubKopf>

<!-- Issue #1256 Scheibe 8 (AC-22, Ein-Mount-Strategie): CompareDetail wird
     GENAU EINMAL gemountet (weder im Desktop- noch im Mobile-Block oben) —
     versorgt beide Viewports, vermeidet Doppel-Fetches/doppelte
     hubPutQueue-Instanzen/doppelte testids (S4-F001-/S7-F004-Fehlerklasse).
     CompareTabs schaltet Monitoring-Streifen + Idealwerte-Tab intern via
     isMobileViewport (matchMedia) um. -->
{#key uebernommeneFassung}
	<CompareDetail
		preset={currentPreset}
		locations={data.locations}
		initialTab={tabNachUebernahme ?? initialTab}
		onScheduleChange={handleScheduleChange}
		saveController={hubSaveCtl}
		bind:this={compareDetailRef}
	/>
{/key}

<!-- Bottom-Sheet für mobile Aktionen (#493) -->
<SubscriptionActionSheet
	open={actionSheetOpen}
	onClose={() => (actionSheetOpen = false)}
	kind="vergleich"
	status={lifecycle}
	surface="hub"
	onAction={handleAction}
	name={currentPreset.name}
/>
