<script lang="ts">
	// CompareHourlyLayoutControls — geteilte Stundenverlauf-Steuerung des
	// Ortsvergleich-Layout-Tabs (Toggle + Metrik-Auswahl + Reihenfolge). Epic
	// #1301 Scheibe F2a; Reihenfolge-Block Issue #1361 Befund 4/5 (S1-Rest von
	// Epic #1372).
	// Spec: docs/specs/modules/feat_1301_f2a_compare_new_trip_pattern.md § AC-7
	//
	// Extrahiert 1:1 aus dem Hub-Inline-Markup CompareTabs.svelte:1349-1373 (+ den
	// Handlern isHourlyMetricActive/makeHourlyMetricHandler :707-727). Genutzt vom
	// Hub UND von der Anlege-Seite (/compare/new) — verhindert die Dreifach-Kopie
	// der Metrik-Liste (Anti-Hand-Kopie, {#each ALL_HOURLY_METRICS}).
	//
	// Der Commit-Wrapper (.hub-layout-hourly-wrap mit onchange/onclick am
	// Hub-PUT-Queue bzw. der lokale saveNewPreset-Pfad der Anlege-Seite) bleibt
	// AUSSERHALB dieser Komponente — hier wird nur der reine wiz-State mutiert,
	// die Persistenz-Kopplung liegt beim jeweiligen Aufrufer (Trip/Compare-
	// Teilungs-Invariante: geteilt ist die Steuerung, nicht der Speicher-Weg).
	// AUSNAHME (Issue #1361, wie schon #1359 fuer die Uebersichts-Reihenfolge):
	// eine Ziehgeste unterdrueckt im Browser oft das nachfolgende click/change,
	// der Bubble-Wrapper wuerde dann NIE feuern -- deshalb loest onDndReorder
	// hier zusaetzlich den optionalen `onHourlyCommit`-Callback direkt aus.
	// Safari-Factory-Pattern für alle Handler (CLAUDE.md).

	import { SectionH, Card } from '$lib/components/atoms';
	import ChannelToggle from '$lib/components/shared/ChannelToggle.svelte';
	import WeatherV2Reihenfolge from './weather-metrics-tab/WeatherV2Reihenfolge.svelte';
	import type { MetricEntry } from '../trip-detail/metricsEditor.ts';
	import {
		ALL_HOURLY_METRICS,
		DEFAULT_HOURLY_METRIC_KEYS,
		applyHourlyMetricToggle,
		orderableHourlyMetricKeys,
		applyHourlyReorder
	} from '../compare/compareHourlyMetricDefs.ts';
	import type { CompareWizardState } from '../compare/compareWizardState.svelte';

	interface Props {
		wiz: CompareWizardState;
		/** Issue #1361 Befund 4: direkter Speicherausloeser nach einer
		 *  Ziehgeste in der Reihenfolge-Liste -- analog `onCompareCommit` in
		 *  WeatherMetricsTab (#1359). Ohne Uebergabe (z.B. Anlege-Seite) bleibt
		 *  die Mutation lokal im wiz-State, gespeichert wird dort erst mit
		 *  `saveNewPreset()`. */
		onHourlyCommit?: () => void;
	}
	let { wiz, onHourlyCommit }: Props = $props();

	// Leere Auswahl = „Default aktiv" (Renderer-Default). Reine Merge-Signale
	// (defaultOff, z.B. Windrichtung) zaehlen dabei NICHT zum Default -- sonst
	// waere die Checkbox faelschlich als aktiv dargestellt, obwohl der Merge im
	// leeren Auswahl-Zustand serverseitig nicht greift (Issue #1335 F002).
	const materializedHourlyKeys = $derived(
		wiz.hourlyMetricKeys.length === 0 ? DEFAULT_HOURLY_METRIC_KEYS : wiz.hourlyMetricKeys
	);

	function isHourlyMetricActive(key: string): boolean {
		return materializedHourlyKeys.includes(key);
	}

	function makeHourlyMetricHandler(key: string) {
		return function handleHourlyMetric(checked: boolean): void {
			wiz.hourlyMetricKeys = applyHourlyMetricToggle(wiz.hourlyMetricKeys, key, checked);
		};
	}

	function handleEnabledToggle(checked: boolean): void {
		wiz.hourlyEnabled = checked;
	}

	// ── Issue #1361 Befund 4: Reihenfolge-Block ──────────────────────────────
	// Merge-only Metriken (wind_dir_deg) fliegen aus der sortierbaren Liste --
	// s. orderableHourlyMetricKeys-Kommentar. Sie bleiben oben im An/Aus-Katalog
	// unveraendert bedienbar (AC-5, keine Regression).
	const orderableHourlyKeys = $derived(orderableHourlyMetricKeys(materializedHourlyKeys));

	const hourlyMetricById = $derived.by(() => {
		const map: Record<string, MetricEntry> = {};
		for (const m of ALL_HOURLY_METRICS) map[m.key] = { id: m.key, label: m.label } as MetricEntry;
		return map;
	});

	function onHourlyRemove(key: string): void {
		makeHourlyMetricHandler(key)(false);
		onHourlyCommit?.();
	}

	function handleHourlyDndReorder(newOrder: string[]): void {
		wiz.hourlyMetricKeys = applyHourlyReorder(materializedHourlyKeys, newOrder);
		onHourlyCommit?.();
	}

	// Roh/Einfach-Umschalter gibt es im Stundenverlauf nicht (eigenstaendiges
	// Vokabular, s. compareHourlyMetricDefs.ts -- keine der Keys ist in
	// INDICATOR_MAP, indicatorCapable() ist fuer sie durchgaengig false; die
	// Segmented-Steuerung wird also nie gerendert). Named function statt
	// Inline-Closure im Markup (Safari-Factory-Muster).
	function noopHourlyMode(): void {}
</script>

<SectionH title="Stundenverlauf" />
<ChannelToggle
	label="Stundenverlauf"
	checked={wiz.hourlyEnabled}
	onchange={handleEnabledToggle}
	testid="compare-layout-hourly-enabled-toggle"
/>
<div
	data-testid="compare-layout-hourly-metrics"
	style="display: flex; flex-direction: column; gap: 8px; margin-top: 10px"
>
	{#each ALL_HOURLY_METRICS as metric (metric.key)}
		<ChannelToggle
			label={metric.label}
			checked={isHourlyMetricActive(metric.key)}
			onchange={makeHourlyMetricHandler(metric.key)}
			testid={`compare-layout-hourly-metric-${metric.key}`}
		/>
	{/each}
</div>

<!-- Issue #1361 Befund 4/5 (korrigiert nach Gegencheck, s. Team-Lead-Fund):
     DERSELBE geteilte Reihenfolge-Baustein wie oben bei den Uebersichts-
     Groessen (WeatherMetricsTab.svelte, WeatherV2Reihenfolge) -- kein
     Compare-Eigenbau (Trip/Compare-Teilungs-Invariante).

     activeChannel="email" -- BEWUSST, keine Schnittlinie: hourly_metrics wird
     ausschliesslich an render_compare_email uebergeben (comparison.py:230-242).
     render_compare_telegram (comparison.py:360) kennt nur enabled_metrics/
     preset_name, keinerlei Stundendaten-Bezug; SMS hat max_table_cols: 0, gar
     keine Tabelle. Der Stundenverlauf existiert also NUR in der E-Mail -- eine
     "ab hier von Telegram gekappt"-Linie waere eine Falschaussage (die 8er-
     CHANNEL_LIMITS-Grenze gilt fuer die Uebersichts-Metriken, nicht fuer den
     Stundenverlauf) und wuerde die mit #1360 AC-4 gerade beseitigte Fehlerklasse
     (Flaeche behauptet Kanal-Kappung ohne reale Grundlage) an dieser Stelle neu
     einfuehren -- Verstoss gegen Invariante 1 des Epics. NICHT nachruesten,
     ohne diese Faktenlage zu widerlegen. -->
{#if orderableHourlyKeys.length > 0}
	<p class="hourly-email-hint" data-testid="compare-layout-hourly-email-only-hint">
		Erscheint nur in der E-Mail.
	</p>
	<Card padding={0} style="margin-top: 6px">
		<WeatherV2Reihenfolge
			primaryColumns={orderableHourlyKeys}
			metricById={hourlyMetricById}
			friendlyMap={{}}
			activeChannel="email"
			highlight={null}
			onRemove={onHourlyRemove}
			onDndReorder={handleHourlyDndReorder}
			onMode={noopHourlyMode}
		/>
	</Card>
{/if}

<style>
	.hourly-email-hint {
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		line-height: 1.5;
		margin: 10px 0 0;
	}
</style>
