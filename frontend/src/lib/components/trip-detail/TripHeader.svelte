<script lang="ts">
	// Issue #302 — Trip-Detail Header (Soll-Mockup).
	// Spec: docs/specs/modules/issue_302_trip_detail_page.md §3.
	//
	// #2837 S1 (ADR-0110): Hülle um den geteilten HubKopf (Leiste + Titelblock, wie beim
	// Ortsvergleich). Trip-eigen bleiben nur Datum (eyebrow), Kürzel (namePrefix), Status mit
	// „Tag x von y" (status-Snippet in der Titelzeile) und km/Hm (Mobil-Kacheln entfallen, #2980 AC-19).
	// Senden/Kebab/Meldungen reicht die Seite durch; der Kopf ruft keine API.
	import type { Snippet } from 'svelte';
	import StatusSchild from '$lib/components/shared/status-schild/StatusSchild.svelte';
	import HubKopf from '$lib/components/shared/hub-kopf/HubKopf.svelte';
	import { api } from '$lib/api.js';
	import { formatDateRange } from '$lib/utils/tripHero';
	import { computeTripStats } from '$lib/utils/tripStats';
	import { deriveTripStatus } from '$lib/utils/tripStatus';
	import { ACTIVITY_TYPE_OPTIONS, type Trip } from '$lib/types';
	import { baueTripSpeicherung, speichereKopfFeld } from '$lib/components/shared/tripSpeicherung';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import { t, tn, locale, type MessageKey } from '$lib/i18n';

	// i18n F9: Aktivitaetsnamen je Sprache (Kennungen unveraendert).
	const AKTIVITAET: Record<string, MessageKey> = {
		trekking: 'trip.aktivitaet.trekking',
		skitour: 'trip.aktivitaet.skitour',
		hochtour: 'trip.aktivitaet.hochtour',
		klettersteig: 'trip.aktivitaet.klettersteig',
		mtb: 'trip.aktivitaet.mtb',
		fahrrad_15: 'trip.aktivitaet.fahrrad_15',
		fahrrad_20: 'trip.aktivitaet.fahrrad_20',
		fahrrad_25: 'trip.aktivitaet.fahrrad_25'
	};

	interface Props {
		trip: Trip;
		// onStatusChange ist obsolet — Pause/Archive haben die Komponente verlassen.
		// Prop bleibt zur Backward-Compatibility, wird nicht mehr ausgelöst.
		onStatusChange?: (updated: Trip) => void;
		onTripUpdate?: (updated: Trip) => void;
		now?: Date;
		/** Issue #758: SaveStatus controller — der Speicher-Chip kommt seit #2284 S2 vom SubscriptionHeader. */
		saveController?: SaveStatus;
		/** #2837 S1: Leiste des HubKopf — Senden öffnet nur den Dialog der Seite. */
		sendLabel?: string;
		onSend?: () => void;
		sendDisabled?: boolean;
		actions?: Array<{ id: string; label: string; danger?: boolean }>;
		onSelect?: (id: string) => void;
		mobil?: boolean;
		onSheetOpen?: () => void;
		meldungen?: Snippet;
	}

	let {
		trip, onTripUpdate, now = new Date(), saveController,
		sendLabel, onSend, sendDisabled = false, actions = [], onSelect, mobil = false, onSheetOpen, meldungen
	}: Props = $props();

	// Issue #2284 S2 — Name, Region und Aktivität speichert der geteilte Baustein
	// über diese Funktion. Rumpf = NUR das Eigenfeld (kein Spread des Seiten-Trips,
	// Fehlerklasse #2375/#2381); Schlüssel je Feld, damit ein 412-Konflikt je Feld
	// genau einen „Nochmal speichern"-Eintrag hat (#1433). Ausgänge: Erfolg ⇒
	// onTripUpdate + schliessen; 412 ⇒ erfüllt ohne schliessen (Retry schließt);
	// sonst wirft es und der Baustein zeigt die Meldung.
	async function onSaveField(field: 'name' | 'region' | 'profile', value: string, schliessen: () => void): Promise<void> {
		const rumpf = field === 'name' ? { name: value } : field === 'region' ? { region: value } : { activity: value };
		const schluessel = field === 'name' ? 'kopf-name' : field === 'region' ? 'kopf-region' : 'kopf-profil';
		const speichern = baueTripSpeicherung<Trip>(api, trip.id, rumpf, (updated) => {
			onTripUpdate?.(updated);
			schliessen();
		}, schluessel);
		await speichereKopfFeld(speichern, saveController);
	}

	const stats = $derived(computeTripStats(trip));
	// i18n F9: tripHero-Helfer lesen die Sprache per tr() — `$locale` haelt die Ableitung reaktiv.
	const dateRange = $derived.by(() => (void $locale, formatDateRange(trip)));

	// #2913 Scheibe c2 (Mockup): Eyebrow „Trip · Region" über dem Titel, Meta-Zeile
	// „Datum · N Etappen · km · ↑m" darunter; Zahlen locale-formatiert (DE „31,5", EN „31.5").
	// Ohne Region nur „Trip" (kein verwaister Trenner).
	const eyebrowText = $derived(trip.region ? $t('aktionen.kopf.eyebrow_trip', { region: trip.region }) : $t('listen.typ.trip'));
	const metaTeile = $derived.by(() => {
		const loc = $locale === 'en' ? 'en-GB' : 'de-DE';
		const km = new Intl.NumberFormat(loc, { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(stats.kmTotal);
		const m = new Intl.NumberFormat(loc, { maximumFractionDigits: 0 }).format(Math.round(stats.ascentM));
		return [dateRange, $tn('listen.anzahl.etappen', trip.stages?.length ?? 0), `${km} km`, `↑${m} m`].filter((x) => x !== '');
	});
	const aktivitaeten = $derived(ACTIVITY_TYPE_OPTIONS.map((o) => ({ value: o.value, label: $t(AKTIVITAET[o.value]) })));
	// #2837 S1b: Profil in der Titel-Unterzeile wie beim Vergleich („— ✎ · Trekking"); ohne Aktivität kein Zusatz.
	const profileLabel = $derived(aktivitaeten.find((o) => o.value === trip.activity)?.label);
	// #2837 S1b: Zustand für das geteilte StatusSchild.
	const tripStatus = $derived(deriveTripStatus(trip, now));
	// #2913 c2: „Aktivieren" im Entwurf — ein Trip wird aktiv, sobald seine Etappen Daten tragen,
	// deshalb führt der Link in den Reiter Etappen (Muster „Setup abschließen" des Vergleichs).
	const AKTIVIEREN_ZIEL = '?tab=etappen';

	// #2980 AC-19 (PO-Entscheidung 13.11.2026, ADR-0118): die Handy-Kennzahlenzeile
	// „Etappe · Briefing · Start in" (#416) entfällt ersatzlos; die Meta-Zeile bleibt.
</script>

<header class="trip-header">
	<HubKopf
		context="route"
		parent={{ label: $t('listen.trips.titel'), href: '/trips' }}
		crumb={trip.name}
		sendLabel={sendLabel ?? $t('aktionen.kopf.test_schicken')}
		{onSend}
		{sendDisabled}
		{actions}
		{onSelect}
		{mobil}
		{onSheetOpen}
		{meldungen}
		leisteTestid="trip-detail-breadcrumb-bar"
		name={trip.name}
		region={trip.region}
		profile={trip.activity}
		profileOptions={aktivitaeten}
		{profileLabel}
		regionMaxLength={60}
		testidPrefix="trip"
		titleTestid="trip-detail-h1"
		titleSize={38}
		{saveController}
		{onSaveField}
		{eyebrowText}
		{metaTeile}
		aktivierenHref={tripStatus === 'draft' ? AKTIVIEREN_ZIEL : undefined}
	>
		{#snippet namePrefix()}
			{#if trip.shortcode}<span class="h1-shortcode">{trip.shortcode}</span> ·&nbsp;{/if}
		{/snippet}
		{#snippet status()}
			<StatusSchild status={tripStatus} testid="trip-detail-status-badge" />
		{/snippet}
	</HubKopf>
</header>

<style>
	/* #2837 S1 (Adversary F001): Abstände und Unterkante trägt allein der HubKopf — die Hülle
	   legt keinen eigenen Rand, Abstand oder Linie um ihn (Parität zum Ortsvergleich). */
	.h1-shortcode {
		font-family: var(--g-font-mono, ui-monospace, monospace);
		color: var(--g-accent-deep); /* #2879: Accent als Text = accent-deep (20 px ist kein großer Text, 6,77:1) */
	}
</style>
