<script lang="ts">
	// Issue #491 — Compare-Preset Detail-Seite.
	// Issue #493 — Mobile-Responsive: TopBar + SubscriptionActionSheet.
	// Issue #1256 Scheibe 8 (AC-22, Ein-Mount-Strategie): der mobile Bespoke-
	// Block (2×2-5-Karten-Grid + flache Standort-Liste) entfaellt — CompareDetail
	// wird jetzt GENAU EINMAL gemountet und versorgt Desktop UND Mobile; die
	// Viewport-Umschaltung (4-Stat-2×2 statt 5-Stat-Leiste, CorridorEditorMobile
	// im Idealwerte-Tab) passiert INNERHALB von CompareTabs (matchMedia).
	import { Btn, BackLink } from '$lib/components/atoms';
	import { ConfirmDialog } from '$lib/components/molecules';
	import CompareDetail from '$lib/components/compare/CompareDetail.svelte';
	import CompareStatusPill from '$lib/components/compare/CompareStatusPill.svelte';
	import SubscriptionKebab from '$lib/components/molecules/SubscriptionKebab.svelte';
	import SendConfirmDialog from '$lib/components/molecules/SendConfirmDialog.svelte';
	import SubscriptionActionSheet from '$lib/components/mobile/SubscriptionActionSheet.svelte';
	import { subscriptionActions } from '$lib/components/shared/subscriptionActions.js';
	import { deleteSubscription, sendSubscription, setArchived, SubscriptionExecError } from '$lib/components/shared/subscriptionExec.js';
	import {
		deriveStatusWithScheduleOverride,
		presetProfileLabel,
		isRuntimeExceeded
	} from '$lib/components/compare/subscriptionHelpers.js';
	import { page } from '$app/state';
	import { browser } from '$app/environment';
	import { goto, beforeNavigate } from '$app/navigation';
	import { createSaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import { sichereAusstehendeSpeicherung } from '$lib/stores/ausstehendeSpeicherungSichern';
	import { getContext, onMount } from 'svelte';
	import { AKTIVE_SPEICHERUNG, type SpeicherAnmeldestelle } from '$lib/stores/aktiveSpeicherung';
	import {
		inhaltsFassung,
		starteNachladenNachEntladen,
		vergleichNachladeQuelle
	} from '$lib/stores/nachEntladenNachladen';
	import { api, getMitFassung } from '$lib/api';
	import { baueSpeicherung, speichereKopfFeld } from '$lib/components/shared/tripSpeicherung';
	import { adoptEtagBeiSeitenaufbau, adoptEtagFromPageLoad } from '$lib/etagRegistry';
	import { ACTIVITY_PROFILE_OPTIONS, type ComparePreset } from '$lib/types';
	import SubscriptionHeader from '$lib/components/shared/subscription-header/SubscriptionHeader.svelte';
	import MoreHorizontalIcon from '@lucide/svelte/icons/more-horizontal';
	// Issue #2659 (i18n F10): Texte aus dem Katalog — Aktionen/Senden wortgleich zum Trip-Hub
	// (aktionen.*). Fehler ohne Server-Text halten nur den Schluessel (Sprachwechsel ohne Neuladen).
	import { locale, t, tn, type MessageKey } from '$lib/i18n';

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
	async function uebernehmeFrischenVergleich(): Promise<void> {
		try {
			const frisch = await getMitFassung<ComparePreset>(`/api/compare/presets/${data.preset.id}`);
			if (!frisch.inRegistry || hubSaveCtl.hasPending || hubSaveCtl.state !== 'idle') return;
			tabNachUebernahme = new URL(window.location.href).searchParams.get('tab');
			currentPreset = frisch.daten;
			uebernommeneFassung += 1;
		} catch {
			/* kein Neuaufbau: der Reiter zeigt bereits die gespeicherte Eingabe */
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
	$effect(() => {
		void data;
		scheduleOverride = null;
	});
	function handleScheduleChange(schedule: string): void {
		scheduleOverride = schedule;
	}

	let status = $derived(deriveStatusWithScheduleOverride(currentPreset, scheduleOverride));
	// Issue #1250 Scheibe 3 (AC-12): Hub-Hinweis, wenn Auto-Pause wegen
	// ueberschrittenem end_date gegriffen hat.
	let runtimeExceeded = $derived(isRuntimeExceeded(currentPreset));
	// Adversary-Finding F001: geguardetes Profil-Label für die mobile Kontext-
	// Unterzeile (Muster SubscriptionCard.svelte) — leer bei unbekanntem/fehlendem profil.
	// Issue #2659 (i18n F10): Profilnamen je Sprache (`$locale`/`$t`), Kennungen unveraendert.
	let profileLabel = $derived((void $locale, presetProfileLabel(currentPreset.profil)));
	const profileOptions = $derived(
		ACTIVITY_PROFILE_OPTIONS.map((o) => ({ value: o.value, label: $t(`bausteine.profil.${o.value}` as MessageKey) }))
	);

	// Issue #2284 S1 — Speicherweg des geteilten Kopfs (SubscriptionHeader).
	// KRITISCH (#2375/#2381): NUR das eigene Feld senden ({ name } / { profil } /
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
		region: (v: string) => ({ display_config: { region: v } }),
		profile: (v: string) => ({ profil: v })
	};
	const KOPF_SCHLUESSEL = { name: 'kopf-name', region: 'kopf-region', profile: 'kopf-profil' };
	async function onSaveField(field: 'name' | 'region' | 'profile', value: string, schliessen: () => void): Promise<void> {
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
	let sendDialogOpen = $state(false);
	const lifecycle = $derived(currentPreset.archived_at != null ? 'archived' : status);
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
	let sendMsg = $state<string | null>(null);
	let sendKey = $state<MessageKey | null>(null);
	/** Meldung unter dem Kopf: Server-Text (`text`) oder Katalogschluessel (`key`). */
	function meldung(text: string | null, key: MessageKey | null): void {
		sendMsg = text;
		sendKey = text ? null : key;
	}

	async function handleTestSend() {
		isSending = true;
		meldung(null, null);
		try {
			// Issue #2124/#2280: geteilter Laufzustand (compare:<id>) + Klassifikation,
			// einheitlicher Ausloeser -> POST /api/briefings/{id}/send?kind=vergleich.
			const o = await sendSubscription('vergleich', currentPreset.id);
			meldung(o.message || null, o.kind === 'ok' ? 'vergleich.hub.test_gesendet' : null);
		} finally {
			isSending = false;
		}
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
		isPausing = false;
	}

	// Issue #2214: Bestaetigungsdialog fuer 'Loeschen' (State analog trips/[id]).
	let deleteDialogOpen = $state(false);
	let isDeleting = $state(false);

	function handleAction(id: string) {
		// Epic #1273 S3: kein 'edit'/'setup' im Hub; die Aktionen stammen aus
		// subscriptionActions('vergleich', status, 'hub') (Issue #2278).
		if (id === 'pause' || id === 'resume') {
			// 'pause' und 'resume' sind dieselbe Toggle-Aktion.
			void togglePause();
		} else if (id === 'archive') {
			void archivePreset();
		} else if (id === 'unarchive') {
			void unarchivePreset();
		} else if (id === 'delete') {
			// Issue #2214: erst Rueckfrage (ConfirmDialog, wie Trip-Hub), kein Sofort-DELETE.
			deleteDialogOpen = true;
		}
	}

	function handleDeleteCancel(): void {
		deleteDialogOpen = false;
	}

	function handleDeleteDialogOpenChange(open: boolean): void {
		deleteDialogOpen = open;
	}

	async function handleDeleteConfirm(): Promise<void> {
		deleteDialogOpen = false;
		await deletePreset();
	}

	async function archivePreset() {
		try {
			await setArchived('vergleich', currentPreset.id, true);
			window.location.href = '/compare';
		} catch (e) {
			fehlerMeldung(e, 'vergleich.hub.archivieren_fehler');
		}
	}

	// Nutzerverstaendliche Meldung: 4xx mit Server-Detail, sonst der feste Text (5xx/Netz).
	function fehlerMeldung(e: unknown, key: MessageKey): void {
		meldung(e instanceof SubscriptionExecError && e.status < 500 && e.detail ? e.detail : null, key);
	}

	async function unarchivePreset() {
		try {
			await setArchived('vergleich', currentPreset.id, false);
			window.location.reload();
		} catch (e) {
			fehlerMeldung(e, 'vergleich.hub.reaktivieren_fehler');
		}
	}

	async function deletePreset() {
		isDeleting = true;
		try {
			await deleteSubscription('vergleich', currentPreset.id);
			window.location.href = '/compare';
		} catch (e) {
			fehlerMeldung(e, 'vergleich.hub.delete_fehler');
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

<!-- Hub-Kopf (#491, #493, #582; #2284 S1): EIN Markup für Desktop und Mobil.
     Seiten-Chrome (Breadcrumb Desktop, BackLink Mobil, Aktionen) bleibt hier;
     Name/Region/Profil liefert der geteilte SubscriptionHeader. -->
<div class="flex flex-col gap-4 p-4 desktop:block desktop:pt-[22px] desktop:px-10 desktop:pb-0 desktop:[border-bottom:1px_solid_var(--g-rule)]" style="position: relative">
	<!-- Breadcrumb (Issue #582 + Bug #589). Issue #1256 S8c (AC-10): genau 2 Krümel. -->
	<div class="hidden desktop:flex" style="align-items: center; gap: 8px; margin-bottom: 12px">
		<a href="/compare" style="font-size: 11px; font-family: var(--g-font-mono); letter-spacing: 0.1em; text-transform: uppercase; color: var(--g-ink-3); text-decoration: none" class="breadcrumb-link">{$t('listen.vergleiche.titel').toUpperCase()}</a>
		<span style="color: var(--g-ink-4); font-size: 11px">/</span>
		<span style="font-size: 11px; font-family: var(--g-font-mono); letter-spacing: 0.1em; text-transform: uppercase; color: var(--g-ink-4)">{$t('vergleich.hub.krumel')}</span>
	</div>
	<div class="desktop:hidden"><BackLink href="/compare" label={$t('listen.archiv.vergleiche')} ariaLabel={$t('aktionen.zurueck_uebersicht')} /></div>

	<div class="flex items-start gap-2 desktop:gap-6 desktop:justify-between">
		<SubscriptionHeader
			kind="vergleich"
			name={currentPreset.name}
			region={currentPreset.display_config?.region as string | undefined}
			profile={currentPreset.profil}
			{profileOptions}
			{profileLabel}
			regionMaxLength={60}
			testidPrefix="compare-hub"
			{onSaveField}
			saveController={hubSaveCtl}
		>
			{#snippet eyebrow()}
				<!-- Issue #1256 S8c (AC-12): Eyebrow nur mobil. -->
				<span class="mono block desktop:hidden" style="font-size: 11px; color: var(--g-ink-muted); letter-spacing: 0.12em; text-transform: uppercase; line-height: 1;">{$t('vergleich.hub.eyebrow')}</span>
			{/snippet}
			{#snippet badges()}
				<span class="flex-shrink-0"><CompareStatusPill {status} /></span>
				{#if runtimeExceeded}
					<span data-testid="runtime-exceeded-hint" class="flex-shrink-0 text-[11px] desktop:text-xs" style="font-weight: 600; color: var(--g-bad)">{$t('vergleich.hub.laufzeit_ueberschritten')}</span>
				{/if}
			{/snippet}
			{#snippet meta()}
				<!-- Orte-Anzahl je Viewport aus derselben Quelle wie vor #2284 S1:
				     Desktop zählte die gespeicherten IDs, Mobil die aufgelösten Orte
				     (weichen ab, wenn ein Ort gelöscht/nicht auflösbar ist). Getrennte
				     testids je Viewport, damit jede Kopf-testid genau einmal im DOM steht (AC-8). -->
				<span data-testid="compare-hub-orte-anzahl-desktop" class="hidden desktop:inline">{' · '}{$tn('listen.anzahl.orte', currentPreset.location_ids.length)}</span>
				<span data-testid="compare-hub-orte-anzahl-mobil" class="desktop:hidden">{' · '}{$tn('listen.anzahl.orte', data.locations.length)}</span>
			{/snippet}
		</SubscriptionHeader>

		<!-- Senden/Setup auf allen Breiten sichtbar (AC-3/AC-12, wie im Trip-Hub); mobil sitzt der Kebab daneben.
		     mt-[25px] = Eyebrow (9px) + gap-4 (16px): Knopf steht auf Höhe der Namenszeile. -->
		<div class="flex items-center mt-[25px] desktop:mt-0" style="gap: 8px; flex-shrink: 0">
			{#if status === 'draft'}
				<Btn variant="primary" class="min-h-[44px] desktop:min-h-0" onclick={() => { window.location.href = `?tab=wetter-metriken#versand`; }}>{$t('vergleich.hub.setup_abschliessen')}</Btn>
			{:else}
				<!-- Senden ist der Primaerknopf und oeffnet den Sende-Dialog (AC-3/AC-12) -->
				<Btn variant="primary" class="min-h-[44px] desktop:min-h-0" data-testid="subscription-hub-send" onclick={() => (sendDialogOpen = true)} disabled={isSending || lifecycle === 'archived'}>
					{isSending ? $t('aktionen.wird_gesendet') : $t('aktionen.senden')}
				</Btn>
			{/if}
			{#if !mobil}
				<SubscriptionKebab data-testid="subscription-kebab" actions={hubAktionen} onSelect={handleAction} />
			{/if}
			{#if mobil}
				<button
					type="button"
					class="flex flex-shrink-0 items-center justify-center min-h-[44px] min-w-[44px] rounded-md"
					data-testid="subscription-kebab"
					aria-label={$t('aktionen.weitere')}
					onclick={() => (actionSheetOpen = true)}
				>
					<MoreHorizontalIcon size={20} />
				</button>
			{/if}
		</div>
	</div>

	<!-- sendMsg/pauseError wie bisher nur Desktop (mobil: Aktions-Sheet). -->
	{#if sendMsg || sendKey}
		<div class="hidden desktop:flex" style="font-size: 14px; color: var(--g-ink-3); margin-bottom: 8px">{sendKey ? $t(sendKey) : sendMsg}</div>
	{/if}
	{#if pauseError}
		<div class="hidden desktop:flex" style="font-size: 14px; color: var(--g-bad); margin-bottom: 8px">{$t('listen.meldung.status_fehlgeschlagen')}</div>
	{/if}
</div>

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

<!-- Issue #2278 AC-3: Senden erst nach Bestaetigung, Ziel aus dem Konto-Profil des angemeldeten Nutzers. -->
<SendConfirmDialog
	open={sendDialogOpen}
	kind="vergleich"
	profile={data.profile}
	subscription={currentPreset}
	running={isSending}
	onConfirm={() => { sendDialogOpen = false; void handleTestSend(); }}
	onCancel={() => (sendDialogOpen = false)}
/>

<!-- Issue #2214: Loeschen erst nach Bestaetigung (Muster trips/[id]/+page.svelte). -->
<ConfirmDialog
	open={deleteDialogOpen}
	title={$t('vergleich.hub.delete_titel')}
	description={$t('listen.dialog.unwiderruflich', { name: currentPreset.name })}
	confirmLabel={$t('aktionen.delete')}
	confirmVariant="destructive"
	data-testid="compare-detail-delete-confirm-dialog"
	cancelTestid="compare-detail-delete-confirm-cancel"
	confirmTestid="compare-detail-delete-confirm-yes"
	disabled={isDeleting}
	onConfirm={handleDeleteConfirm}
	onCancel={handleDeleteCancel}
	onOpenChange={handleDeleteDialogOpenChange}
/>

<style>
	.breadcrumb-link:hover {
		text-decoration: underline;
	}
</style>

