<script lang="ts">
	import { SectionH, Card, Btn, Eyebrow } from '$lib/components/atoms';
	import FullProfile from './FullProfile.svelte';
	import TripStageRow from './TripStageRow.svelte';
	import ReportLine from './ReportLine.svelte';
	import ChannelDot from './ChannelDot.svelte';
	import type { Trip } from '$lib/types';
	import { fetchStageRisk, type StageRisk } from '$lib/utils/stageRisk';
	// Feature #1435 Etappe E3a: Wetter-Metriken-Block. `metricsCatalog` kommt
	// ausschließlich als Prop aus der Server-Naht (+page.server.ts) — kein
	// eigener Fetch, kein $effect (AC-5, Fehlerklasse #1320).
	import { resolveTripMetricsOverviewState } from '$lib/components/shared/trip-metrics/tripActiveMetricNames';
	import type { MetricCatalog } from './metricsEditor.ts';

	interface Props {
		trip: Trip;
		onJump?: (tab: string) => void;
		metricsCatalog?: MetricCatalog | null;
	}
	let { trip, onJump, metricsCatalog = null }: Props = $props();

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

	function makeJumpHandler(tab: string) {
		return function doJump() {
			onJump?.(tab);
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
				<Btn variant="ghost" size="sm" onclick={makeJumpHandler('stages')}>Im Editor öffnen →</Btn>
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
		     wichtigste Einstellung einer Tour, deshalb erste Karte. Vier sich
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
			<Btn variant="ghost" size="sm" onclick={makeJumpHandler('weather')}>Wetter-Metriken bearbeiten →</Btn>
		</Card>

		<Card padding={18}>
			<Eyebrow style="margin-bottom: 10px;">Briefings laufen</Eyebrow>
			<ReportLine kind="morning" time="06:00" channels={['email', 'telegram']} active />
			<ReportLine kind="evening" time="18:00" channels={['email']} active />
			<ReportLine kind="alert" time="bei Δ" channels={['telegram']} active alert />
			<div style="margin-top: 12px;">
				<Btn variant="ghost" size="sm" onclick={makeJumpHandler('briefings')}>Zeitplan bearbeiten →</Btn>
			</div>
		</Card>

		<Card padding={18}>
			<Eyebrow style="margin-bottom: 10px;">Alerts (letzte 7 Tage)</Eyebrow>
			<p style="font-size: 13px; color: var(--g-ink-2); margin: 0 0 12px;">Keine aktuellen Alerts.</p>
			<Btn variant="ghost" size="sm" onclick={makeJumpHandler('alerts')}>Alle Alerts →</Btn>
		</Card>

		<Card padding={18} style="background: var(--g-card-alt);">
			<Eyebrow style="margin-bottom: 10px;">Vorschau</Eyebrow>
			<p style="font-size: 13px; color: var(--g-ink-2); margin: 0 0 12px;">Wie sieht das nächste Briefing aus?</p>
			<Btn variant="primary" size="sm" onclick={makeJumpHandler('preview')}>Vorschau öffnen</Btn>
		</Card>
	</div>
</div>

<style>
	.hub-overview {
		position: relative;
		padding: 32px 40px 60px;
		display: grid;
		grid-template-columns: 1fr 380px;
		gap: 32px;
		max-width: 1480px;
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
			padding: 20px 16px 48px;
			gap: 24px;
		}
	}
</style>
