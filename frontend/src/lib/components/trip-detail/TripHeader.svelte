<script lang="ts">
	// Issue #302 — Trip-Detail Header (Soll-Mockup).
	// Spec: docs/specs/modules/issue_302_trip_detail_page.md §3.
	//
	// #2837 S1 (ADR-0110): Hülle um den geteilten HubKopf (Leiste + Titelblock, wie beim
	// Ortsvergleich). Trip-eigen bleiben nur Datum (eyebrow), Kürzel (namePrefix), Status mit
	// „Tag x von y" (status-Snippet in der Titelzeile), km/Hm und die Mobil-Kacheln.
	// Senden/Kebab/Meldungen reicht die Seite durch; der Kopf ruft keine API.
	import type { Snippet } from 'svelte';
	import StatusSchild from '$lib/components/shared/status-schild/StatusSchild.svelte';
	import HubKopf from '$lib/components/shared/hub-kopf/HubKopf.svelte';
	import { api } from '$lib/api.js';
	import { formatDateRange } from '$lib/utils/tripHero';
	import { computeTripStats } from '$lib/utils/tripStats';
	import { deriveTripStatus, todayStageIndex } from '$lib/utils/tripStatus';
	import { getReportSchedule } from '$lib/utils/rightColumn';
	import Stat from '$lib/components/molecules/Stat.svelte';
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

	// Issue #416 — Mobile Kennzahlen-Kacheln (sichtbar nur ≤ 899px).
	// Spec: docs/specs/modules/issue_416_mobile_trip_kennzahlen.md
	const etappeValue = $derived((() => {
		const total = trip.stages?.length ?? 0;
		if (total === 0) return '—';
		const s = deriveTripStatus(trip, now);
		if (s === 'active') {
			const idx = todayStageIndex(trip, now);
			return idx >= 0 ? `${idx + 1}/${total}` : `—/${total}`;
		}
		if (s === 'archived' || s === 'finished') return `${total}/${total}`;
		return `—/${total}`;
	})());

	const briefingValue = $derived((() => {
		const sched = getReportSchedule(trip);
		if (!sched.enabled) return '—';
		if (sched.morning_enabled && sched.morning) return sched.morning.slice(0, 5);
		if (sched.evening_enabled && sched.evening) return sched.evening.slice(0, 5);
		return '—';
	})());

	const startLabel = $derived((() => {
		const s = deriveTripStatus(trip, now);
		if (s === 'planned') return $t('trip.kopf.start_in');
		if (s === 'active') return $t('trip.kopf.tag_label');
		return $t('trip.kopf.status');
	})());

	const startValue = $derived((() => {
		const s = deriveTripStatus(trip, now);
		if (s === 'planned') {
			const dates = (trip.stages ?? [])
				.map((st) => st.date)
				.filter((d): d is string => !!d)
				.sort();
			if (!dates.length) return '—';
			const firstDay = new Date(dates[0] + 'T00:00:00');
			const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
			const diff = Math.ceil((firstDay.getTime() - today.getTime()) / 86_400_000);
			return diff > 0 ? $t('trip.kopf.tage_bis', { tage: diff }) : '—';
		}
		if (s === 'active') {
			const idx = todayStageIndex(trip, now);
			return idx >= 0 ? $t('trip.kopf.tag', { tag: idx + 1 }) : '—';
		}
		return '—';
	})());


</script>

<header class="trip-header">
	<HubKopf
		context="route"
		parent={{ label: $t('listen.trips.titel'), href: '/trips' }}
		crumb={trip.shortcode ?? trip.name}
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
		<!-- Whitelist (Entscheidung 8): Mobil-Kacheln im Titelblock, über der Unterkante des HubKopf. -->
		{#snippet unten()}
			<div class="mobile-metrics" data-testid="trip-header-mobile-metrics">
				<div data-testid="metric-etappe">
					<Stat label={$t('trip.kopf.etappe')} value={etappeValue} size="sm" mono />
				</div>
				<div data-testid="metric-briefing">
					<Stat label={$t('trip.kopf.briefing')} value={briefingValue} size="sm" mono />
				</div>
				<div data-testid="metric-start">
					<Stat label={startLabel} value={startValue} size="sm" mono />
				</div>
			</div>
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
	.mobile-metrics {
		display: none;
	}
	@media (max-width: 899px) {
		.mobile-metrics {
			display: flex;
			gap: var(--g-s-3);
			padding-top: var(--g-s-2);
		}
	}
</style>
