<script lang="ts">
	// Issue #302 — Danger-Zone unter den Tabs (Spec §6).
	// Pause/Archive/Delete-Logik ist aus TripHeader hierhergewandert; Headerbuttons
	// (Briefing-Vorschau, Bearbeiten, Test-Briefing) leben in der neuen Header-Komponente.
	import { page } from '$app/state';
	import { browser } from '$app/environment';
	import { goto, beforeNavigate } from '$app/navigation';
	import { TripHeader } from '$lib/components/organisms';
	import { TripTabs } from '$lib/components/trip-detail';
	import { Btn, TopoBg, BackLink } from '$lib/components/atoms';
	import { ConfirmDialog } from '$lib/components/molecules';
	import SendConfirmDialog from '$lib/components/molecules/SendConfirmDialog.svelte';
	import SubscriptionKebab from '$lib/components/molecules/SubscriptionKebab.svelte';
	import SubscriptionActionSheet from '$lib/components/mobile/SubscriptionActionSheet.svelte';
	import EllipsisVerticalIcon from '@lucide/svelte/icons/ellipsis-vertical';
	import { subscriptionActions, subscriptionLifecycle } from '$lib/components/shared/subscriptionActions';
	import {
		deleteSubscription,
		sendSubscription,
		setArchived,
		setPaused,
		SubscriptionExecError
	} from '$lib/components/shared/subscriptionExec';
	import { deriveTripStatus } from '$lib/utils/tripStatus';
	import type { Trip } from '$lib/types';
	import { createSaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import { sichereAusstehendeSpeicherung } from '$lib/stores/ausstehendeSpeicherungSichern';
	import { adoptEtagBeiSeitenaufbau, adoptEtagFromPageLoad, istKonflikt } from '$lib/etagRegistry';
	import { getMitFassung } from '$lib/api';
	import { getContext, onMount } from 'svelte';
	import { AKTIVE_SPEICHERUNG, type SpeicherAnmeldestelle } from '$lib/stores/aktiveSpeicherung';
	import { starteNachladenNachEntladen, tripNachladeQuelle } from '$lib/stores/nachEntladenNachladen';
	import { wendeNutzlastAn } from '$lib/stores/nutzlastStand';

	let { data } = $props();

	// Trip in lokales $state heben, damit Status-Updates (Pause/Archive)
	// reaktiv ohne Page-Reload sichtbar werden.
	let trip = $state<Trip>(data.trip);

	// Issue #1395 S3: den Stempel aus der Server-Naht in die Registry uebernehmen.
	// Ab hier traegt jeder Schreibvorgang auf diese Trip automatisch `If-Match`.
	// Fehlt er, bleibt die Registry leer und alles laeuft wie vor dieser Scheibe.
	//
	// ACHTUNG: bewusst NUR von `data` abhaengig (`data.trip.id`, nicht das lokale
	// `trip`). Das lokale `trip` wird von sendStateUpdate() neu gesetzt — haenge
	// der Effekt daran, liefe er direkt NACH dem GET dort erneut und
	// legte den laengst veralteten Stempel aus dem Seitenaufbau wieder ab. Genau
	// den selbstgebauten Konflikt soll AC-5 verhindern. `adoptEtagFromPageLoad`
	// setzt zusaetzlich nur, solange fuer diese Trip noch nichts bekannt ist —
	// ein erneutes `load()` neben einem laufenden Speichervorgang duerfte sonst
	// einen aelteren Stand zurueckschreiben (dieselbe Klasse wie F001).
	// Fix-Loop 1 (#1433, F003): ein frischer Seitenaufbau (Navigation weg und zurueck)
	// liefert Trip und Stempel gemeinsam und beendet einen offenen Konflikt dieser
	// Trip — bewusst im Skript-Kopf (einmal je Instanz), nicht im Effekt.
	const seitenaufbauStempelUebernommen = browser && data.etag ? adoptEtagBeiSeitenaufbau(data.trip.id, data.etag) : false;
	$effect(() => {
		if (data.etag) adoptEtagFromPageLoad(data.trip.id, data.etag);
	});

	// Issue #758: SaveStatus-Controller — eine Instanz pro Trip-Seite (kein Singleton!).
	const tripSaveCtl = createSaveStatus({ typ: 'trip', id: trip.id });

	// Issue #758: Flush ausstehender Auto-Saves vor Navigation (AC-5).
	// Issue #2316 Scheibe A: die Logik lebt jetzt geteilt mit /compare/[id] in
	// sichereAusstehendeSpeicherung() (dünne Hülle hier).
	// Issue #2317 Baustein 3: mit Kennung — beim Entladen entsteht der Nachlade-Merker.
	beforeNavigate((navigation) =>
		sichereAusstehendeSpeicherung(navigation, tripSaveCtl, goto, { typ: 'trip', id: trip.id })
	);

	// Issue #2317 Baustein 2: SaveStatus an der Anmeldestelle des Layouts melden,
	// damit „Aktualisieren" eine ausstehende Speicherung vorher abschliesst.
	const speicherAnmeldestelle = getContext<SpeicherAnmeldestelle | undefined>(AKTIVE_SPEICHERUNG);

	// Issue #2317 Baustein 3: die Reiter uebernehmen `trip` nur beim Mount in
	// lokale Zustaende. Nach einer Uebernahme per Nachladen werden sie deshalb
	// ueber diesen Zaehler neu aufgebaut ({#key} unten), sonst bliebe die
	// sichtbare Zahl auf dem alten Stand. Den ETag der uebernommenen Fassung hat
	// api.ts beim Nachlade-GET bereits in die Registry gelegt.
	let uebernommeneFassung = $state(0);

	// Fix-Loop 1 (#1433, F001/AC-19): „Nochmal speichern" gibt den per GET geholten Trip
	// an die Seite, BEVOR es die Eintraege erneut sendet (Trip und Stempel gemeinsam);
	// Fix-Loop 2 (F101): bei 'geholt' NUR `trip` setzen, KEIN Neuaufbau — die Reiter leiten
	// ihren editierbaren Zustand nur beim Mount aus `trip` ab; ein Neuaufbau liesse die
	// Eingabe aus der Liste und den sichtbaren Reiter auseinanderlaufen (zwei Wahrheiten).
	// Neuaufbau erst nach vollem Erfolg ('wiederholt', `trip` kommt dann aus den Antworten).
	const abmeldenUebernahme = tripSaveCtl.registriereUebernahme((stand, phase) => {
		if (phase === 'geholt') {
			trip = stand as Trip;
			return;
		}
		uebernommeneFassung += 1;
	});

	// Fix-Loop 3 (#1433, F201): EINE Wahrheit. Seitenstand = letzter Serverstand ⊕ ausstehende
	// Eigenfeld-Nutzlasten der Liste. Bei einem 412 wird `trip` lokal mit der abgelehnten
	// Nutzlast fortgeschrieben (kein Stempelwechsel); ein spaeter (wieder) gemounteter Reiter
	// liest sie beim Mount, ein bereits offener Reiter aendert sich nicht (liest nur beim Mount).
	const abmeldenAbgelehnt = tripSaveCtl.registriereAbgelehnt((nutzlast) => {
		trip = wendeNutzlastAn(trip, nutzlast);
	});

	onMount(() => {
		const mq = window.matchMedia('(max-width: 899px)');
		const mqUpdate = () => (mobil = mq.matches);
		mqUpdate();
		mq.addEventListener('change', mqUpdate);
		const abmelden = speicherAnmeldestelle?.anmelden(tripSaveCtl);
		const nachladen = starteNachladenNachEntladen<Trip>({
			kennung: { typ: 'trip', id: trip.id },
			ctl: tripSaveCtl,
			ausgelieferteFassung: data.etag,
			holen: tripNachladeQuelle<Trip>(trip.id),
			uebernehmen: (stand) => {
				trip = stand;
				uebernommeneFassung += 1;
			}
		});
		return () => {
			mq.removeEventListener('change', mqUpdate);
			abmelden?.();
			abmeldenUebernahme();
			abmeldenAbgelehnt();
			nachladen.stoppen();
		};
	});

	// Issue #516 — Initial-Tab aus ?tab=…-Query (kanonisches Schema, kein #hash mehr).
	// $derived bleibt reaktiv falls user navigation triggert.
	const initialTab = $derived(page.url.searchParams.get('tab') ?? 'uebersicht');

	const now = new Date();
	const status = $derived(deriveTripStatus(trip, now));

	let archiveDialogOpen = $state(false);
	let deleteDialogOpen = $state(false);
	let isLoading = $state(false);
	let errorMsg = $state<string | null>(null);
	let sendDialogOpen = $state(false);
	let sendLoading = $state(false);
	let sendStatus = $state<'idle' | 'ok' | 'error'>('idle');
	let sendMessage = $state<string | null>(null);
	let sendTimer: ReturnType<typeof setTimeout> | undefined;
	// Lebenszyklus-Menue: Desktop = Dropdown, Mobil = Aktionsblatt (surface 'hub'), Issue #2278 AC-12.
	let sheetOpen = $state(false);
	let mobil = $state(false);
	const lifecycle = $derived(subscriptionLifecycle('trip', trip, now));

	/**
	 * Issue #1433: nach PATCH /state (liefert keinen Stempel, S2 AC-15) wird der Trip
	 * frisch geholt; `trip` und ETag kommen gemeinsam aus der GET-Antwort. Bei offenem
	 * Konflikt wird NICHTS adoptiert (der lokale Stand traegt die abgelehnte Eingabe),
	 * nur der neue Status wird uebernommen. Der ETag bleibt dann der alte.
	 */
	async function uebernehmeNachStatusAenderung(updated: Trip): Promise<Trip> {
		if (istKonflikt(trip.id)) {
			return { ...trip, paused_at: updated.paused_at, archived_at: updated.archived_at };
		}
		let frisch: Awaited<ReturnType<typeof getMitFassung<Trip>>>;
		try {
			frisch = await getMitFassung<Trip>(`/api/trips/${trip.id}`);
		} catch {
			// der PATCH ist durch — scheitert nur der GET, bleibt die PATCH-Antwort
			return updated;
		}
		// `inRegistry === false`: ein anderer Vorgang hat den Eintrag waehrend des GET
		// veraendert — der Stempel dieser Antwort passt nicht mehr, also auch ihr
		// Trip nicht (nie nur eines von beiden uebernehmen).
		return frisch.inRegistry ? frisch.daten : updated;
	}

	async function sendStateUpdate(paused: boolean | undefined, archived: boolean | undefined): Promise<void> {
		errorMsg = null; // Issue #1059: alten Fehler beim Start eines neuen Versuchs zurücksetzen
		isLoading = true;
		try {
			// Issue #1433: offene Speichervorgaenge zuerst abschliessen — danach PATCH,
			// dann GET (statt den ETag zu verwerfen, was den naechsten Schreibvorgang
			// unbedingt machte).
			await tripSaveCtl.flush();
			const laufend = tripSaveCtl.laufendeSpeicherung;
			if (laufend) await laufend;
			// Issue #2278: Schreibweg ueber den geteilten Adapter (PATCH /state); Fehler tragen Status + Detail.
			const antwort: unknown =
				paused !== undefined
					? await setPaused('trip', trip.id, paused)
					: await setArchived('trip', trip.id, archived === true);
			const updated = antwort as Trip;
			errorMsg = null;
			trip = await uebernehmeNachStatusAenderung(updated);
		} catch (e) {
			errorMsg = aktionsFehler(e);
		} finally {
			isLoading = false;
		}
	}

	// Issue #1059/#1065: nutzerverstaendliche Meldung — 5xx generisch, 4xx mit Server-Detail, sonst Netzfehler.
	function aktionsFehler(e: unknown): string {
		if (e instanceof SubscriptionExecError) {
			if (e.status >= 500) {
				console.error(`Aktion fehlgeschlagen: HTTP ${e.status}`, e.detail);
				return 'Aktion fehlgeschlagen — Serverfehler, bitte später erneut versuchen.';
			}
			return e.detail ?? 'Aktion fehlgeschlagen, bitte später erneut versuchen.';
		}
		console.error(e);
		return 'Aktion fehlgeschlagen — bitte Verbindung prüfen.';
	}

	function handleArchiveClick(): void {
		archiveDialogOpen = true;
	}

	function handleArchiveCancel(): void {
		archiveDialogOpen = false;
	}

	function handleArchiveConfirm(): void {
		const nextArchived = status !== 'archived';
		archiveDialogOpen = false;
		void sendStateUpdate(undefined, nextArchived);
	}

	function handleArchiveDialogOpenChange(open: boolean): void {
		archiveDialogOpen = open;
	}

	function handleDeleteClick(): void {
		deleteDialogOpen = true;
	}

	function handleDeleteCancel(): void {
		deleteDialogOpen = false;
	}

	async function handleDeleteConfirm(): Promise<void> {
		errorMsg = null; // Issue #1059: alten Fehler beim Start eines neuen Versuchs zurücksetzen
		isLoading = true;
		try {
			await deleteSubscription('trip', trip.id);
			void goto('/trips');
		} catch (e) {
			errorMsg = aktionsFehler(e);
		} finally {
			isLoading = false;
			deleteDialogOpen = false;
		}
	}

	function handleDeleteDialogOpenChange(open: boolean): void {
		deleteDialogOpen = open;
	}

	function handleStatusChange(updated: Trip): void {
		trip = updated;
	}

	function handleTripUpdate(updated: Trip): void {
		trip = updated;
	}

	// Senden: erst nach Bestaetigung im Sende-Dialog (AC-3/AC-4); Berichtsart aus der Wahl.
	async function handleSendConfirm(berichtsart: 'morning' | 'evening' | undefined): Promise<void> {
		sendDialogOpen = false;
		clearTimeout(sendTimer);
		sendLoading = true;
		sendStatus = 'idle';
		try {
			// Issue #2124: geteilter Laufzustand (trip:<id>) + Klassifikation.
			const o = await sendSubscription('trip', trip.id, { reportType: berichtsart });
			if (o.kind === 'ok') {
				sendStatus = 'ok';
				sendMessage = null;
			} else {
				sendStatus = 'error';
				sendMessage = o.message;
			}
		} finally {
			sendLoading = false;
		}
		sendTimer = setTimeout(() => { sendStatus = 'idle'; }, 4000);
	}

	// Lebenszyklus-Menue (Desktop-Dropdown und mobiles Blatt): Pausieren/Fortsetzen schreiben ueber den
	// Hub-Schreiber (flusht offene Speicherungen, ETag #1433); Archivieren/Loeschen fragen zurueck.
	function handleHubAction(id: string): void {
		if (id === 'pause') void sendStateUpdate(true, undefined);
		else if (id === 'resume') void sendStateUpdate(false, undefined);
		else if (id === 'archive' || id === 'unarchive') handleArchiveClick();
		else if (id === 'delete') handleDeleteClick();
	}
</script>

<svelte:head><title>{trip.name} — Gregor Zwanzig</title></svelte:head>

<main style="position: relative; overflow: hidden;">
	<TopoBg opacity={0.14} />
	<div class="breadcrumb-bar" data-testid="trip-detail-breadcrumb-bar">
		<!-- #2347 S4 (KA-11): mobiler Zurück-Pfeil zur Liste wie im Vergleich-Hub
		     (BackLink ariaLabel „Zurück zur Übersicht"); nur ≤899px, ohne Zeilenhöhe. -->
		<div class="back-mobil"><BackLink href="/trips" label="" ariaLabel="Zurück zur Übersicht" /></div>
		<div class="mono breadcrumb-path" style="font-size: 11px; color: var(--g-ink-3); letter-spacing: 0.06em;">
			<a href="/trips" class="g-link-tap" style="opacity: 0.6; color: inherit; text-decoration: none;">Trips</a>
			<span style="margin: 0 8px;">/</span>
			<span style="color: var(--g-ink);">{trip.shortcode ?? trip.name}</span>
		</div>
		<div class="hub-actions">
			<!-- Senden ist der Primaerknopf und oeffnet den Sende-Dialog (AC-12) -->
			<Btn
				variant="accent"
				size="sm"
				data-testid="subscription-hub-send"
				onclick={() => { sendDialogOpen = true; }}
				disabled={sendLoading || lifecycle === 'archived' || lifecycle === 'draft'}
			>
				{sendLoading ? 'Wird gesendet…' : 'Senden'}
			</Btn>
			{#if mobil}
				<button
					type="button"
					data-testid="subscription-kebab"
					aria-label="Weitere Aktionen"
					title="Weitere Aktionen"
					onclick={() => { sheetOpen = true; }}
					style="display: inline-flex; align-items: center; justify-content: center; width: 44px; height: 44px; background: transparent; border: none; cursor: pointer; color: var(--g-ink-2);"
				>
					<EllipsisVerticalIcon size={18} />
				</button>
			{:else}
				<SubscriptionKebab
					data-testid="subscription-kebab"
					actions={subscriptionActions('trip', lifecycle, 'hub')}
					onSelect={handleHubAction}
				/>
			{/if}
			{#if sendStatus === 'ok'}
				<span data-testid="test-briefing-success" style="font-size: 12px; color: var(--g-success, #2e7d32);">Briefing gesendet!</span>
			{:else if sendStatus === 'error'}
				<span data-testid="test-briefing-error" style="font-size: 12px; color: var(--g-error, #c62828);">{sendMessage ?? 'Fehler beim Senden'}</span>
			{/if}
			{#if errorMsg}
				<span data-testid="trip-detail-action-error" style="font-size: 12px; color: var(--g-error, #c62828);">{errorMsg}</span>
			{/if}
		</div>
	</div>
	<TripHeader {trip} {now} onStatusChange={handleStatusChange} onTripUpdate={handleTripUpdate} saveController={tripSaveCtl} />
	{#key uebernommeneFassung}
		<TripTabs
			{initialTab}
			badges={{}}
			{trip}
			onTripUpdate={handleTripUpdate}
			saveController={tripSaveCtl}
			metricsCatalog={data.metricsCatalog}
		/>
	{/key}
</main>

<ConfirmDialog
	open={archiveDialogOpen}
	title={status === 'archived' ? 'Trip reaktivieren?' : 'Trip archivieren?'}
	description={status === 'archived'
		? 'Der Trip wird aus dem Archiv zurückgeholt und ist wieder aktiv.'
		: 'Archivierte Trips erhalten keine Briefings mehr.'}
	confirmLabel={status === 'archived' ? 'Reaktivieren' : 'Archivieren'}
	confirmVariant="primary"
	data-testid="trip-detail-archive-confirm-dialog"
	cancelTestid="trip-detail-archive-confirm-cancel"
	confirmTestid="trip-detail-archive-confirm-yes"
	disabled={isLoading}
	onConfirm={handleArchiveConfirm}
	onCancel={handleArchiveCancel}
	onOpenChange={handleArchiveDialogOpenChange}
/>

<ConfirmDialog
	open={deleteDialogOpen}
	title="Trip endgültig löschen?"
	description={`„${trip.name}“ wird dauerhaft gelöscht. Dieser Schritt kann nicht rückgängig gemacht werden.`}
	confirmLabel="Löschen"
	confirmVariant="destructive"
	data-testid="trip-detail-delete-confirm-dialog"
	cancelTestid="trip-detail-delete-confirm-cancel"
	confirmTestid="trip-detail-delete-confirm-yes"
	disabled={isLoading}
	onConfirm={handleDeleteConfirm}
	onCancel={handleDeleteCancel}
	onOpenChange={handleDeleteDialogOpenChange}
/>

<SendConfirmDialog
	open={sendDialogOpen}
	kind="trip"
	profile={data.profile}
	subscription={trip}
	running={sendLoading}
	onConfirm={handleSendConfirm}
	onCancel={() => { sendDialogOpen = false; }}
/>

<SubscriptionActionSheet
	open={sheetOpen}
	onClose={() => { sheetOpen = false; }}
	kind="trip"
	status={lifecycle}
	surface="hub"
	name={trip.name}
	onAction={handleHubAction}
/>

<style>
	.breadcrumb-bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 10px 40px;
		border-bottom: 1px solid var(--g-rule-soft);
		gap: 16px;
		flex-wrap: wrap;
	}
	.hub-actions {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
	}
	.back-mobil {
		display: none;
	}
		/* #2284 S2 (AC-13): mobil 44-px-Tippflaechen ohne Layout-Hoehe. */
	@media (max-width: 899px) {
		/* #2347 S4 (KA-11): 36-px-Pfeil mit negativem Block-Rand — die Zeile bleibt
		   so hoch wie bisher (Etappen-Liste oben ≤ 474 px, trip-hub-kopf-region AC-13). */
		.back-mobil {
			display: flex;
			flex-shrink: 0;
			margin-block: -8px;
			margin-right: -12px;
		}
		/* #2278 (AC-13): Pfad kuerzt mit Ellipsis statt "Senden" + Kebab in eine zweite Zeile zu schieben
		   (390 px, langer Name: +33 px Kopfhoehe). Der volle Name steht im Titel darunter. */
		.breadcrumb-path {
			flex: 1 1 0;
			min-width: 0;
			white-space: nowrap;
			overflow: hidden;
			text-overflow: ellipsis;
		}
		.hub-actions > :global([data-slot='btn']) {
			min-height: 44px;
			min-width: 44px;
			margin-block: -8px;
		}
	}
</style>
