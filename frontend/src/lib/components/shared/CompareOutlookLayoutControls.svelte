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
	import { groupCompareCatalog } from './weather-metrics-tab/compareAggregationGrouping.ts';
	import type { MetricEntry } from '../trip-detail/metricsEditor.ts';
	import type { CompareSelectionEntry } from './weather-metrics-tab/compareMetricSelection.ts';
	import {
		materializeOutlookMetricKeys,
		toggleOutlookMetricKeyFromState
	} from './weather-metrics-tab/compareMetricOrder.ts';

	// Issue #1720 S1: flache Props statt `CompareWizardState`-Bindung — dasselbe
	// Bauteil bedient jetzt Ortsvergleich UND Trip (parametrisiert statt
	// kopiert, Trip/Compare-Teilungs-Invariante). Der Speicher-Weg bleibt wie
	// bisher AUSSERHALB: der Vergleich schreibt in den wiz-State, der Trip in
	// seinen `$state` + `scheduleAutoSave()`.
	interface Props {
		/** `null` = nie eingestellt (sieben feste Spalten), `[]` = bewusst leer. */
		metricKeys: string[] | null;
		/** Bereits geladene Antwort von GET /api/compare/metrics — dieselbe
		 *  Liste wie die Uebersichts-Grundauswahl (kein zweiter Abruf). */
		catalog: CompareSelectionEntry[];
		/** Neue Auswahl (Umschalten ODER Reihenfolge) nach oben melden. */
		onMetricKeys: (keys: string[]) => void;
		/** Direkter Speicherausloeser nach einer Ziehgeste, analog
		 *  `onHourlyCommit`. Ohne Uebergabe (Anlege-Seite) bleibt die Mutation
		 *  lokal beim Aufrufer. */
		onOutlookCommit?: () => void;
		/** Ueberschrift: Vergleich "3-Tages-Ausblick", Trip "3-Tages-Vorschau". */
		title?: string;
		/** Ein/Aus-Schalter — NUR der Vergleich uebergibt beides. Der Trip hat
		 *  mit `report_config.show_outlook` bereits einen Schalter; ein zweiter
		 *  waere eine widerspruechliche Bedienflaeche (#1720 S1, AC-13). */
		enabled?: boolean;
		onEnabledChange?: (checked: boolean) => void;
		/** Hinweis „Erscheint nur in der E-Mail" (#1720 S2, AC-6). Vorgabe
		 *  `true` haelt den Ortsvergleich unveraendert — dort erscheint der
		 *  Ausblick weiterhin nur in `render_compare_email()`. Der Trip
		 *  uebergibt `false`: seine Auswahl wirkt seit dieser Scheibe in
		 *  allen vier Ausgabeorten. */
		showEmailOnlyHint?: boolean;
	}
	let {
		metricKeys, catalog, onMetricKeys, onOutlookCommit,
		title = '3-Tages-Ausblick', enabled = true, onEnabledChange,
		showEmailOnlyHint = true
	}: Props = $props();

	// „Nie eingestellt" (`null`) = die heutigen sieben Ausblick-Spalten; eine
	// bewusst geleerte Auswahl (`[]`) bleibt leer und laesst den Block ganz
	// entfallen (AC-8). Anzeige UND Umschalt-Handler nutzen ZWINGEND dieselbe
	// Materialisierung (Issue #1366 F001).
	const materializedOutlookKeys = $derived(materializeOutlookMetricKeys(metricKeys));

	function isOutlookMetricActive(key: string): boolean {
		return materializedOutlookKeys.includes(key);
	}

	function makeOutlookMetricHandler(key: string) {
		return function handleOutlookMetric(): void {
			onMetricKeys(toggleOutlookMetricKeyFromState(metricKeys, key));
		};
	}

	function handleEnabledToggle(checked: boolean): void {
		onEnabledChange?.(checked);
	}

	// Issue #1848 A2: die Reihenfolge-/„Aus"-Karte arbeitet auf denselben
	// Eintraegen wie die Auswahl — also auf KENNUNGEN. Der Schluessel ist
	// deshalb `metric_id`, nicht mehr der Katalog-Schluessel; sonst faende
	// WeatherV2Reihenfolge zu keinem Eintrag eine Beschriftung. Bei mehreren
	// Auswertungen gewinnt die erste Katalogzeile der Groesse (gleiche
	// `label`/`col_label`/`sms_code`, es unterscheidet sich nur die
	// Auswertung — die traegt die Kennung nicht mehr).
	const outlookMetricById = $derived.by(() => {
		const map: Record<string, MetricEntry> = {};
		// Issue #1401 (A1): Auswertung als eigenes Element mitgeben.
		// Issue #1453 (AC-7): alle drei Namensformen mitgeben.
		for (const e of catalog) {
			const id = e.metric_id ?? e.metric;
			if (map[id]) continue;
			map[id] = {
				id, label: e.label, aggregation_label: e.aggregation_label,
				col_label: e.col_label, sms_code: e.sms_code
			} as MetricEntry;
		}
		return map;
	});

	// Issue #1719 S4: Kurzform-Marke = Register-Kuerzel (`sms_code`) — die
	// Vergleichs-SMS rendert aus `get_sms_code()`, nicht aus den
	// Trip-SMS-Tabellen.
	const outlookKuerzelById = $derived.by(() => {
		const map: Record<string, string[]> = {};
		// #1848 A2: nach Kennung geschluesselt, analog outlookMetricById.
		for (const e of catalog) {
			const id = e.metric_id ?? e.metric;
			if (e.sms_code && !map[id]) map[id] = [e.sms_code];
		}
		return map;
	});

	function onOutlookRemove(key: string): void {
		makeOutlookMetricHandler(key)();
		onOutlookCommit?.();
	}

	function handleOutlookDndReorder(newOrder: string[]): void {
		onMetricKeys(newOrder);
		onOutlookCommit?.();
	}

	// Roh/Einfach-Umschalter gibt es im Vergleich nicht (indicatorCapable() ist
	// fuer die Compare-Metrik-IDs durchgaengig false). Named function statt
	// Inline-Closure im Markup (Safari-Factory-Muster).
	function noopOutlookMode(): void {}
</script>

<SectionH {title} />
<!-- Issue #1720 S1 (AC-13): der Schalter erscheint NUR, wenn der Aufrufer ihn
     fuehrt. Der Trip laesst `onEnabledChange` weg — sein Ein/Aus liegt bereits
     in der Inhalt-/Versand-Karte (`report_config.show_outlook`). -->
{#if onEnabledChange}
	<ChannelToggle
		label="3-Tages-Ausblick"
		checked={enabled}
		onchange={handleEnabledToggle}
		testid="compare-layout-outlook-enabled-toggle"
	/>
{/if}
<div
	data-testid="compare-layout-outlook-metrics"
	style="display: flex; flex-direction: column; gap: 8px; margin-top: 10px"
>
	<!-- Issue #1406 Scheibe A (Epic #1372 S4b Scheibe 2): eine Zeile je
	     Wettergroesse (24 statt 26) — analog zur Vergleichs-Uebersicht seit
	     #1411 (WeatherMetricsTab.svelte:918-948).

	     Issue #1848 A2: EIN Kaestchen je Groesse, angehakt und umgeschaltet
	     ueber die KENNUNG (`group.metric_id`). Die frueheren Sonderzeilen fuer
	     Temperatur und gefuehlte Temperatur (je Auswertung ein eigenes
	     Kaestchen ueber AggregationMetricRow mode='multiple') entfallen: seit
	     A1 stehen Tief und Hoch in EINER Spannen-Zelle der Mail, und seit A2
	     laesst sich die Halbauswahl gar nicht mehr speichern. Zwei Kaestchen
	     wuerden etwas anderes versprechen, als herauskommt. Die Auswertung
	     bleibt sichtbar, wo sie eindeutig ist (eine Auswertung je Groesse). -->
	{#each groupCompareCatalog(catalog) as group (group.metric_id)}
		<label class="outlook-metric-row" data-testid={`compare-layout-outlook-metric-${group.metric_id}`}>
			<input
				type="checkbox"
				checked={isOutlookMetricActive(group.metric_id)}
				onchange={makeOutlookMetricHandler(group.metric_id)}
			/>
			<span>{group.label}</span>
			<!-- Issue #1401 (A1): Auswertung daneben, nicht im Namen. Bei
			     mehreren Auswertungen (Temperatur, gefuehlte Temperatur) traegt
			     die Zeile keine — die Kennung zeigt beide Tagesenden. -->
			{#if group.options.length === 1 && group.options[0].aggregation_label}
				<span class="outlook-aggregation" data-testid={`compare-layout-outlook-aggregation-${group.metric_id}`}>{group.options[0].aggregation_label}</span>
			{/if}
		</label>
	{/each}
</div>

<!-- DERSELBE geteilte Reihenfolge-Baustein wie bei Uebersicht und
     Stundenverlauf (WeatherV2Reihenfolge, ADR-0024) — kein Compare-Eigenbau.
     activeChannel="email": der Ausblick existiert nur in der E-Mail
     (render_compare_email), analog der Begruendung im Stundenverlauf-Block. -->
{#if materializedOutlookKeys.length > 0}
	{#if showEmailOnlyHint}
		<p class="outlook-email-hint" data-testid="compare-layout-outlook-email-only-hint">
			Erscheint nur in der E-Mail.
		</p>
	{/if}
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
			kuerzelById={outlookKuerzelById}
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
