<script lang="ts">
	// CompareOutlookLayoutControls — geteilte 3-Tages-Ausblick-Steuerung des
	// Ortsvergleichs (Toggle + Metrik-Auswahl + Reihenfolge).
	// Issue #1361 Befund 2 / #1368, S3 Scheibe A von Epic #1372.
	// Spec: docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md
	//
	// Struktureller Zwilling zu CompareHourlyLayoutControls.svelte (Toggle +
	// Liste + geteilter WeatherV2Reihenfolge-Baustein, ADR-0024). Der Metrik-
	// Pool ist hier aber DERSELBE Katalog wie bei den Uebersichts-Groessen
	// (GET /api/compare/metrics) — der Ausblick liest seine Tageswerte aus
	// derselben SegmentWeatherSummary, kein eigenes Vokabular (#1373).
	//
	// Der Commit-Wrapper (Hub-PUT-Queue bzw. lokaler saveNewPreset-Pfad) bleibt
	// AUSSERHALB — hier wird nur der wiz-State mutiert (Trip/Compare-Teilungs-
	// Invariante: geteilt ist die Steuerung, nicht der Speicher-Weg). Wie beim
	// Stundenverlauf loest eine Ziehgeste zusaetzlich `onOutlookCommit` direkt
	// aus (Browser unterdruecken danach oft das nachfolgende click/change).
	// Safari-Factory-Pattern für alle Handler (CLAUDE.md).

	import { SectionH, Card } from '$lib/components/atoms';
	import ChannelToggle from '$lib/components/shared/ChannelToggle.svelte';
	import WeatherV2Reihenfolge from './weather-metrics-tab/WeatherV2Reihenfolge.svelte';
	import type { MetricEntry } from '../trip-detail/metricsEditor.ts';
	import type { CompareSelectionEntry } from './weather-metrics-tab/compareMetricSelection.ts';
	import {
		materializeOutlookMetricKeys,
		toggleOutlookMetricKeyFromState
	} from './weather-metrics-tab/compareMetricOrder.ts';
	import type { CompareWizardState } from '../compare/compareWizardState.svelte';

	interface Props {
		wiz: CompareWizardState;
		/** Bereits geladene Antwort von GET /api/compare/metrics — dieselbe
		 *  Liste wie die Uebersichts-Grundauswahl (kein zweiter Abruf). */
		catalog: CompareSelectionEntry[];
		/** Direkter Speicherausloeser nach einer Ziehgeste, analog
		 *  `onHourlyCommit`. Ohne Uebergabe (Anlege-Seite) bleibt die Mutation
		 *  lokal im wiz-State. */
		onOutlookCommit?: () => void;
	}
	let { wiz, catalog, onOutlookCommit }: Props = $props();

	// „Nie eingestellt" (`null`) = die heutigen sieben Ausblick-Spalten; eine
	// bewusst geleerte Auswahl (`[]`) bleibt leer und laesst den Block ganz
	// entfallen (AC-8). Anzeige UND Umschalt-Handler nutzen ZWINGEND dieselbe
	// Materialisierung (Issue #1366 F001).
	const materializedOutlookKeys = $derived(materializeOutlookMetricKeys(wiz.outlookMetricKeys));

	function isOutlookMetricActive(key: string): boolean {
		return materializedOutlookKeys.includes(key);
	}

	function makeOutlookMetricHandler(key: string) {
		return function handleOutlookMetric(): void {
			wiz.outlookMetricKeys = toggleOutlookMetricKeyFromState(wiz.outlookMetricKeys, key);
		};
	}

	function handleEnabledToggle(checked: boolean): void {
		wiz.outlookEnabled = checked;
	}

	const outlookMetricById = $derived.by(() => {
		const map: Record<string, MetricEntry> = {};
		// Issue #1401 (A1): Auswertung als eigenes Element mitgeben.
		for (const e of catalog)
			map[e.metric] = {
				id: e.metric, label: e.label, aggregation_label: e.aggregation_label
			} as MetricEntry;
		return map;
	});

	function onOutlookRemove(key: string): void {
		makeOutlookMetricHandler(key)();
		onOutlookCommit?.();
	}

	function handleOutlookDndReorder(newOrder: string[]): void {
		wiz.outlookMetricKeys = newOrder;
		onOutlookCommit?.();
	}

	// Roh/Einfach-Umschalter gibt es im Vergleich nicht (indicatorCapable() ist
	// fuer die Compare-Metrik-IDs durchgaengig false). Named function statt
	// Inline-Closure im Markup (Safari-Factory-Muster).
	function noopOutlookMode(): void {}
</script>

<SectionH title="3-Tages-Ausblick" />
<ChannelToggle
	label="3-Tages-Ausblick"
	checked={wiz.outlookEnabled}
	onchange={handleEnabledToggle}
	testid="compare-layout-outlook-enabled-toggle"
/>
<div
	data-testid="compare-layout-outlook-metrics"
	style="display: flex; flex-direction: column; gap: 8px; margin-top: 10px"
>
	{#each catalog as entry (entry.metric)}
		<label class="outlook-metric-row" data-testid={`compare-layout-outlook-metric-${entry.metric}`}>
			<input
				type="checkbox"
				checked={isOutlookMetricActive(entry.metric)}
				onchange={makeOutlookMetricHandler(entry.metric)}
			/>
			<span>{entry.label}</span>
			<!-- Issue #1401 (A1): Auswertung daneben, nicht im Namen. -->
			{#if entry.aggregation_label}
				<span class="outlook-aggregation" data-testid={`compare-layout-outlook-aggregation-${entry.metric}`}>{entry.aggregation_label}</span>
			{/if}
		</label>
	{/each}
</div>

<!-- DERSELBE geteilte Reihenfolge-Baustein wie bei Uebersicht und
     Stundenverlauf (WeatherV2Reihenfolge, ADR-0024) — kein Compare-Eigenbau.
     activeChannel="email": der Ausblick existiert nur in der E-Mail
     (render_compare_email), analog der Begruendung im Stundenverlauf-Block. -->
{#if materializedOutlookKeys.length > 0}
	<p class="outlook-email-hint" data-testid="compare-layout-outlook-email-only-hint">
		Erscheint nur in der E-Mail.
	</p>
	<Card padding={0} style="margin-top: 6px">
		<WeatherV2Reihenfolge
			primaryColumns={materializedOutlookKeys}
			metricById={outlookMetricById}
			friendlyMap={{}}
			activeChannel="email"
			highlight={null}
			onRemove={onOutlookRemove}
			onDndReorder={handleOutlookDndReorder}
			onMode={noopOutlookMode}
		/>
	</Card>
{/if}

<style>
	.outlook-email-hint {
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		line-height: 1.5;
		margin: 10px 0 0;
	}
	.outlook-metric-row {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: var(--g-text-sm);
		color: var(--g-ink);
	}
	/* Issue #1401: Auswertung als eigenes, abgesetztes Element. */
	.outlook-aggregation {
		font-size: 11px;
		color: var(--g-ink-3);
		background: var(--g-paper);
		border: 1px solid var(--g-rule-soft);
		border-radius: 3px;
		padding: 0 5px;
		white-space: nowrap;
	}
</style>
