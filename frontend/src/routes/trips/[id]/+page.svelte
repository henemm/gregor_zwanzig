<script lang="ts">
	// Issue #302 — Danger-Zone unter den Tabs (Spec §6).
	// Pause/Archive/Delete-Logik ist aus TripHeader hierhergewandert; Headerbuttons
	// (Briefing-Vorschau, Bearbeiten, Test-Briefing) leben in der neuen Header-Komponente.
	import { page } from '$app/state';
	import { browser } from '$app/environment';
	import { goto, beforeNavigate } from '$app/navigation';
	import { TripHeader } from '$lib/components/organisms';
	import { TripTabs } from '$lib/components/trip-detail';
	import { Btn, TopoBg } from '$lib/components/atoms';
	import { ConfirmDialog } from '$lib/components/molecules';
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
	let testBriefingLoading = $state(false);
	let testBriefingStatus = $state<'idle' | 'ok' | 'error'>('idle');
	let testBriefingMessage = $state<string | null>(null);
	let testBriefingTimer: ReturnType<typeof setTimeout> | undefined;
	let testBriefingMenuOpen = $state(false);

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
		const body: Record<string, boolean> = {};
		if (paused !== undefined) body.paused = paused;
		if (archived !== undefined) body.archived = archived;
		errorMsg = null; // Issue #1059: alten Fehler beim Start eines neuen Versuchs zurücksetzen
		isLoading = true;
		try {
			// Issue #1433: offene Speichervorgaenge zuerst abschliessen — danach PATCH,
			// dann GET (statt den ETag zu verwerfen, was den naechsten Schreibvorgang
			// unbedingt machte).
			await tripSaveCtl.flush();
			const laufend = tripSaveCtl.laufendeSpeicherung;
			if (laufend) await laufend;
			const res = await fetch(`/api/trips/${trip.id}/state`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(body)
			});
			if (!res.ok) {
				// Issue #1059: 4xx/5xx-Übersetzung analog handleTestBriefing — nutzerverständliche
				// Meldung statt rohem Statuscode-String.
				// Issue #1065: HTTP-Fehler direkt setzen und return, damit der catch-Block
				// nur für echte Netzwerk-Ausnahmen (fetch wirft) erreicht wird.
				let detail: string | undefined;
				try {
					const errBody = await res.json();
					detail = errBody?.detail;
				} catch {
					/* kein JSON-Body */
				}
				if (res.status >= 500) {
					console.error(`Status-Update fehlgeschlagen: HTTP ${res.status}`, detail);
					errorMsg = 'Aktion fehlgeschlagen — Serverfehler, bitte später erneut versuchen.';
				} else if (detail) {
					errorMsg = detail;
				} else {
					errorMsg = 'Aktion fehlgeschlagen, bitte später erneut versuchen.';
				}
				return;
			}
			const updated: Trip = await res.json();
			errorMsg = null;
			trip = await uebernehmeNachStatusAenderung(updated);
		} catch (e) {
			console.error(e);
			// Issue #1065: echter Netzwerkfehler (kein HTTP-Response) → generische Meldung.
			errorMsg = 'Aktion fehlgeschlagen — bitte Verbindung prüfen.';
		} finally {
			isLoading = false;
		}
	}

	function handlePauseClick(): void {
		const nextPaused = status !== 'paused';
		void sendStateUpdate(nextPaused, undefined);
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
			const res = await fetch(`/api/trips/${trip.id}`, { method: 'DELETE' });
			if (!res.ok) {
				// Issue #1059: 4xx/5xx-Übersetzung analog sendStateUpdate.
				// Issue #1065: HTTP-Fehler direkt setzen und return; catch nur für
				// echte Netzwerk-Ausnahmen.
				let detail: string | undefined;
				try {
					const errBody = await res.json();
					detail = errBody?.detail;
				} catch {
					/* kein JSON-Body */
				}
				if (res.status >= 500) {
					console.error(`Löschen fehlgeschlagen: HTTP ${res.status}`, detail);
					errorMsg = 'Aktion fehlgeschlagen — Serverfehler, bitte später erneut versuchen.';
				} else if (detail) {
					errorMsg = detail;
				} else {
					errorMsg = 'Aktion fehlgeschlagen, bitte später erneut versuchen.';
				}
				return;
			}
			void goto('/trips');
		} catch (e) {
			console.error(e);
			// Issue #1065: echter Netzwerkfehler (kein HTTP-Response) → generische Meldung.
			errorMsg = 'Aktion fehlgeschlagen — bitte Verbindung prüfen.';
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

	async function handleTestBriefing(reportType: 'morning' | 'evening'): Promise<void> {
		testBriefingMenuOpen = false;
		clearTimeout(testBriefingTimer);
		testBriefingLoading = true;
		testBriefingStatus = 'idle';
		try {
			const res = await fetch(`/api/trips/${trip.id}/send?report_type=${reportType}`, {
				method: 'POST'
			});
			if (res.ok) {
				testBriefingStatus = 'ok';
				testBriefingMessage = null;
			} else {
				testBriefingStatus = 'error';
				let detail: string | undefined;
				try {
					const body = await res.json();
					detail = body?.detail;
				} catch {
					/* kein JSON-Body */
				}
				if (res.status >= 500) {
					// AC-1/AC-3: Serverfehler → handlungsleitende Meldung, roher detail wird
					// NICHT angezeigt; Statuscode + Rohtext werden observierbar geloggt.
					console.error(`Test-Briefing fehlgeschlagen: HTTP ${res.status}`, detail);
					testBriefingMessage = 'Versand fehlgeschlagen — Serverfehler, bitte später erneut versuchen.';
				} else if (detail) {
					testBriefingMessage = detail; // AC-2: qualifizierte 4xx-Meldung bleibt
				} else {
					testBriefingMessage = 'Versand fehlgeschlagen — bitte später erneut versuchen.';
				}
			}
		} catch (e) {
			console.error(e);
			testBriefingStatus = 'error';
			testBriefingMessage = 'Versand fehlgeschlagen — bitte später erneut versuchen.';
		} finally {
			testBriefingLoading = false;
		}
		clearTimeout(testBriefingTimer);
		testBriefingTimer = setTimeout(() => { testBriefingStatus = 'idle'; }, 4000);
	}
</script>

<svelte:head><title>{trip.name} — Gregor Zwanzig</title></svelte:head>

<main style="position: relative; overflow: hidden;">
	<TopoBg opacity={0.14} />
	<div class="breadcrumb-bar" data-testid="trip-detail-breadcrumb-bar">
		<div class="mono breadcrumb-path" style="font-size: 11px; color: var(--g-ink-3); letter-spacing: 0.06em;">
			<span style="opacity: 0.6;">Trips</span>
			<span style="margin: 0 8px;">/</span>
			<span style="color: var(--g-ink);">{trip.shortcode ?? trip.name}</span>
		</div>
		<div class="breadcrumb-actions">
			<Btn variant="ghost" size="sm" onclick={handlePauseClick} disabled={isLoading || status === 'archived'}>
				{status === 'paused' ? 'Fortsetzen' : 'Pausieren'}
			</Btn>
			<Btn variant="ghost" size="sm" onclick={handleArchiveClick} disabled={isLoading}>
				{status === 'archived' ? 'Reaktivieren' : 'Archivieren'}
			</Btn>
			<div class="test-briefing-wrap">
				<!-- #2284 S2 (Entscheidung 15): mobil kurze Beschriftung, damit der Knopf in die Zeile von
				     Pausieren/Archivieren passt; der zugängliche Name bleibt vollständig. -->
				<Btn
					variant="accent"
					size="sm"
					data-testid="test-briefing-menu-toggle"
					aria-label={testBriefingLoading ? 'Wird gesendet…' : 'Test-Briefing senden'}
					onclick={() => { testBriefingMenuOpen = !testBriefingMenuOpen; }}
					disabled={testBriefingLoading}
				>
					{#if testBriefingLoading}Wird gesendet…{:else}Test-Briefing<span class="hidden desktop:inline">&nbsp;senden</span>{/if}
				</Btn>
				{#if testBriefingMenuOpen}
					<div
						class="test-briefing-menu"
						style="position: absolute; top: calc(100% + 4px); left: 0; z-index: 20; display: flex; flex-direction: column; gap: 4px; padding: 6px; background: var(--g-card, #ffffff); border: 1px solid var(--g-line, #d8d4ca); border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.12);"
					>
						<Btn
							variant="ghost"
							size="sm"
							data-testid="test-briefing-option-morning"
							onclick={() => handleTestBriefing('morning')}
						>
							Morgen
						</Btn>
						<Btn
							variant="ghost"
							size="sm"
							data-testid="test-briefing-option-evening"
							onclick={() => handleTestBriefing('evening')}
						>
							Abend
						</Btn>
					</div>
				{/if}
			</div>
			{#if testBriefingStatus === 'ok'}
				<span data-testid="test-briefing-success" style="font-size: 12px; color: var(--g-success, #2e7d32);">Test-Briefing gesendet!</span>
			{:else if testBriefingStatus === 'error'}
				<span data-testid="test-briefing-error" style="font-size: 12px; color: var(--g-error, #c62828);">{testBriefingMessage ?? 'Fehler beim Senden'}</span>
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
	description="Dieser Schritt löscht den Trip dauerhaft und kann nicht rückgängig gemacht werden."
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
	.breadcrumb-actions {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
	}
	.test-briefing-wrap {
		position: relative;
		display: inline-block;
	}
	/* #2284 S2 (AC-13): mobil 44-px-Tippflächen ohne Layout-Höhe — der negative Rand
	   gleicht die zusätzliche Höhe aus, die Zeile bleibt so hoch wie vorher. */
	@media (max-width: 899px) {
		.test-briefing-wrap {
			display: flex;
		}
		.breadcrumb-actions > :global([data-slot='btn']),
		.test-briefing-wrap > :global([data-slot='btn']) {
			min-height: 44px;
			min-width: 44px;
			margin-block: -8px;
		}
	}
</style>
