<script lang="ts">
	import { SectionH, Card, Btn, Eyebrow } from '$lib/components/atoms';
	import FullProfile from './FullProfile.svelte';
	import TripStageRow from './TripStageRow.svelte';
	import ReportLine from './ReportLine.svelte';
	import type { Trip } from '$lib/types';
	// Issue #2682: echte Briefing-/Alert-Kanäle (EINE Regel mit der Kanäle-Kennzahl der Übersicht).
	import { tripAlertKanaele, tripBriefingKanaele } from '../shared/hub-uebersicht/hubUebersichtModell.ts';
	import { fetchStageRisk, type StageRisk } from '$lib/utils/stageRisk';
	// Feature #1435 Etappe E3a: Wetter-Metriken-Block. `metricsCatalog` kommt
	// ausschließlich als Prop aus der Server-Naht (+page.server.ts) — kein
	// eigener Fetch, kein $effect (AC-5, Fehlerklasse #1320).
	import { resolveTripMetricsOverviewState } from '$lib/components/shared/trip-metrics/tripActiveMetricNames';
	import type { MetricCatalog } from './metricsEditor.ts';
	// Issue #1969 (AC-20): Karte „Briefings laufen" mit echten Zeiten statt 06:00/18:00.
	import { api } from '$lib/api.js';
	import { reportSlotAktiv } from '$lib/utils/reportSlotAktiv';
	import { erstelleNaechstesBriefingLader } from '../shared/versand-tab/naechstesBriefingLader.svelte.ts';
	import type { NextBriefing } from '$lib/components/shared/versand-tab/nextBriefingText';

	interface Props {
		trip: Trip;
		/** #1743: optionaler Anker im Ziel-Reiter (Versand-Abschnitt unter Wetter-Metriken). */
		onJump?: (tab: string, anchor?: 'versand') => void;
		metricsCatalog?: MetricCatalog | null;
		/** #1969: Backend-Wert (GET /api/next-briefings?trip_id=). Fehlt er, laedt die Karte ihn selbst. */
		nextBriefing?: NextBriefing | null;
	}
	let { trip, onJump, metricsCatalog = null, nextBriefing }: Props = $props();

	// Issue #1969: client-seitig nachladen, falls der Wert nicht hereingereicht wird
	// (geteilter Lader; SSR zeigt die Stunden ohne Zonenkuerzel).
	const naechstesBriefing = erstelleNaechstesBriefingLader(
		() => ({ context: 'route', id: trip?.id, extern: nextBriefing }),
		(p) => api.get(p)
	);
	const briefing = $derived(naechstesBriefing.wert);

	/** Slot-Stunde als „HH:00" (Versand nutzt nur die Stunde, Default 7/18 wie der Scheduler)
	 *  plus Zonenkuerzel aus dem Backend-Wert — nie aus der Browser-Zone. */
	function slotZeit(raw: string | undefined, standardStunde: number): string {
		const m = /^(\d{1,2}):/.exec(raw ?? '');
		const stunde = m ? Number(m[1]) : standardStunde;
		const hh = `${String(stunde).padStart(2, '0')}:00`;
		return briefing?.at && briefing.tz_abbr ? `${hh} (${briefing.tz_abbr})` : hh;
	}
	const morgenZeit = $derived(slotZeit(trip.report_config?.morning_time, 7));
	const abendZeit = $derived(slotZeit(trip.report_config?.evening_time, 18));
	// Issue #2682 (AC-9/AC-10): tatsaechlich eingestellte Kanaele statt fester Liste.
	const briefingKanaele = $derived(tripBriefingKanaele(trip));
	const alertKanaele = $derived(tripAlertKanaele(trip));

	const metricsState = $derived(
		metricsCatalog ? resolveTripMetricsOverviewState(trip.display_config?.metrics, metricsCatalog) : null
	);

	let selectedStageId = $state<string | null>(trip.stages?.[0]?.id ?? null);

	// Issue #1223 — Risiko-Ampel je Etappe, clientseitig/lazy im Cockpit-Tab.
	// Niemals im SSR-Home-Loader (Regel #386/#395).
	let stageRisk: Record<string, StageRisk> = $state({});

	$effect(() => {
		if (!trip?.id) return;
		const id = trip.id;
		fetchStageRisk(id).then((m) => {
			if (id === trip.id) stageRisk = m; // Stale-Guard (F003): spät auflösender Fetch für alten Trip nicht übernehmen
		});
	});

	// Kein `anchor?:` — die SSR-Pruefstaende strippen optionale Parameter nicht.
	function makeJumpHandler(tab: string, anchor: 'versand' | null = null) {
		return function doJump() {
			if (anchor) onJump?.(tab, anchor);
			else onJump?.(tab);
		};
	}

	function makeStageSelectHandler(id: string) {
		return function doSelect() {
			selectedStageId = id;
		};
	}
</script>

<div data-testid="hub-overview" class="hub-overview">
	<!-- Left column -->
	<div>
		<SectionH eyebrow="Etappen" title="Reihenfolge & Profil">
			{#snippet right()}
				<Btn variant="ghost" size="sm" onclick={makeJumpHandler('etappen')}>Im Editor öffnen →</Btn>
			{/snippet}
		</SectionH>

		<Card padding={20}>
			<FullProfile {trip} {selectedStageId} onSelectStage={(id) => (selectedStageId = id)} />
		</Card>

		{#each trip.stages ?? [] as stage, i}
			<TripStageRow
				{stage}
				index={i}
				active={stage.id === selectedStageId}
				onclick={makeStageSelectHandler(stage.id)}
				risk={stageRisk[stage.id] ?? null}
			/>
		{/each}
	</div>

	<!-- Right column -->
	<div style="display: flex; flex-direction: column; gap: 20px;">
		<!-- Feature #1435 Etappe E3a: Wetter-Metriken-Block — die inhaltlich
		     wichtigste Einstellung einer Trip, deshalb erste Karte. Vier sich
		     ausschließende Zweige in dieser Prüfreihenfolge: Katalog-Fehler ->
		     Altbestand -> Leerauswahl -> Auswahl (AC-4). -->
		<Card padding={18}>
			<Eyebrow style="margin-bottom: 10px;">Wetter-Metriken</Eyebrow>
			{#if !metricsCatalog}
				<p data-testid="hub-metrics-catalog-error" class="hub-metrics-text">
					Wetter-Metriken konnten nicht geladen werden.
				</p>
			{:else if metricsState?.kind === 'altbestand'}
				<p data-testid="hub-metrics-altbestand" class="hub-metrics-text">
					Noch nicht eingestellt — es gilt der Standardsatz.
				</p>
			{:else if metricsState?.kind === 'empty'}
				<p data-testid="hub-metrics-empty" class="hub-metrics-text">
					Keine Wettergrößen ausgewählt — das Briefing enthält keine Wettertabelle.
				</p>
			{:else}
				<p data-testid="hub-metrics-selected" class="hub-metrics-text hub-metrics-names">
					{metricsState?.names.join(', ')}{#if (metricsState?.unknownCount ?? 0) > 0}
						<span class="hub-metrics-unknown">
							· {metricsState?.unknownCount} {metricsState?.unknownCount === 1 ? 'Größe unbekannt' : 'Größen unbekannt'}
						</span>
					{/if}
				</p>
			{/if}
			<Btn variant="ghost" size="sm" onclick={makeJumpHandler('wetter-metriken')}>Wetter-Metriken bearbeiten →</Btn>
		</Card>

		<Card padding={18}>
			<Eyebrow style="margin-bottom: 10px;">Briefings laufen</Eyebrow>
			<ReportLine kind="morning" time={morgenZeit} channels={briefingKanaele} active={reportSlotAktiv(trip.report_config, 'morning')} />
			<ReportLine kind="evening" time={abendZeit} channels={briefingKanaele} active={reportSlotAktiv(trip.report_config, 'evening')} />
			<ReportLine kind="alert" time="bei Δ" channels={alertKanaele} active alert />
			<div style="margin-top: 12px;">
				<Btn variant="ghost" size="sm" onclick={makeJumpHandler('wetter-metriken', 'versand')}>Zeitplan bearbeiten →</Btn>
			</div>
		</Card>

		<!-- Issue #2682: die Versand-Historie steht im geteilten Baustein HubUebersicht (EIN Laden
		     mit „Zuletzt raus"); die Karte „Alerts (letzte 7 Tage)" mit Festtext ohne Datenquelle
		     entfaellt (AC-11) — Alarme bleiben ueber den Reiter Alarme erreichbar. -->
	</div>
</div>

<style>
	/* Issue #2682: Rand und Breite traegt die Einbindung (TripTabs .trip-uebersicht). */
	.hub-overview {
		position: relative;
		display: grid;
		grid-template-columns: 1fr 380px;
		gap: 32px;
	}
	.hub-overview > :global(*) {
		min-width: 0;
	}
	/* Feature #1435 Etappe E3a (AC-12, Fehlerklasse #1446): die Namensliste
	   bricht um, statt am Handy abgeschnitten zu werden — bewusst KEIN
	   viewport-abhaengiges display:none auf diesem Container. */
	.hub-metrics-text {
		font-size: 13px;
		color: var(--g-ink-2);
		margin: 0 0 12px;
		word-break: break-word;
		overflow-wrap: break-word;
	}
	.hub-metrics-names {
		white-space: normal;
	}
	.hub-metrics-unknown {
		color: var(--g-ink-3);
	}
	/* Mobile/Tablet: eine Spalte, kompakteres Padding — feste 380px-Spalte
	   sprengt sonst den Viewport (Höhenprofil + Etappenliste unlesbar). */
	@media (max-width: 899px) {
		.hub-overview {
			grid-template-columns: 1fr;
			gap: 24px;
		}
	}
</style>
