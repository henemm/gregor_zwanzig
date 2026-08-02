<script lang="ts">
	// CompareHourlyLayoutControls — geteilte Stundenverlauf-Steuerung des
	// Ortsvergleich-Layout-Tabs (Toggle + Metrik-Auswahl + Reihenfolge). Epic
	// #1301 Scheibe F2a; Reihenfolge-Block Issue #1361 Befund 4/5 (S1-Rest von
	// Epic #1372).
	// Spec: docs/specs/modules/feat_1406b_stundenverlauf_katalog.md § AC-1/AC-11
	//
	// Issue #1406 Scheibe B: der Auswahl-Block schoepft aus DERSELBEN
	// Katalogantwort wie Uebersicht (#1411) und Ausblick (Scheibe A) —
	// `groupCompareCatalog(catalog)` statt der frueheren flachen Zehnerliste
	// `ALL_HOURLY_METRICS`. Da der Stundenverlauf strukturell keine
	// Mehrfach-Auswertung je Groesse kennt (ein Rohwert pro Stunde hat nur eine
	// Darstellung), ergibt jede Gruppe genau EINE Zeile — der Ein-Options-Zweig
	// des geteilten Musters. Gespeichert wird die Katalog-ID (`group.metric_id`),
	// NICHT ein Auswertungs-Schluessel wie `temp_max_c`, den der Stunden-
	// Aufloeser gar nicht kennt.
	//
	// Der Commit-Wrapper (.hub-layout-hourly-wrap mit onchange/onclick am
	// Hub-PUT-Queue bzw. der lokale saveNewPreset-Pfad der Anlege-Seite) bleibt
	// AUSSERHALB dieser Komponente — hier wird nur der reine wiz-State mutiert,
	// die Persistenz-Kopplung liegt beim jeweiligen Aufrufer (Trip/Compare-
	// Teilungs-Invariante: geteilt ist die Steuerung, nicht der Speicher-Weg).
	// AUSNAHME (Issue #1361): eine Ziehgeste unterdrueckt im Browser oft das
	// nachfolgende click/change, der Bubble-Wrapper wuerde dann NIE feuern --
	// deshalb loest onDndReorder zusaetzlich `onHourlyCommit` direkt aus.
	// Safari-Factory-Pattern für alle Handler (CLAUDE.md).

	import { SectionH, Card } from '$lib/components/atoms';
	import ChannelToggle from '$lib/components/shared/ChannelToggle.svelte';
	import WeatherV2Reihenfolge from './weather-metrics-tab/WeatherV2Reihenfolge.svelte';
	import { groupCompareCatalog } from './weather-metrics-tab/compareAggregationGrouping.ts';
	import type { CompareAggregationGroup } from './weather-metrics-tab/compareAggregationGrouping.ts';
	import type { CompareSelectionEntry } from './weather-metrics-tab/compareMetricSelection.ts';
	import type { MetricEntry } from '../trip-detail/metricsEditor.ts';
	import {
		materializeHourlyMetricKeys,
		applyHourlyMetricToggleFromState,
		orderableHourlyMetricKeys,
		applyHourlyReorder
	} from '../compare/compareHourlyMetricDefs.ts';
	import type { CompareWizardState } from '../compare/compareWizardState.svelte';

	interface Props {
		wiz: CompareWizardState;
		/** Bereits geladene Antwort von GET /api/compare/metrics — dieselbe
		 *  Liste wie Uebersichts-Grundauswahl und Ausblick (kein zweiter Abruf,
		 *  kein zweites Vokabular). Leer/nicht geladen: der Auswahl-Block bleibt
		 *  leer, Schalter und Hinweis bleiben bedienbar. */
		catalog?: CompareSelectionEntry[];
		/** Issue #1361 Befund 4: direkter Speicherausloeser nach einer
		 *  Ziehgeste in der Reihenfolge-Liste. Ohne Uebergabe (Anlege-Seite)
		 *  bleibt die Mutation lokal im wiz-State. */
		onHourlyCommit?: () => void;
	}
	let { wiz, onHourlyCommit, catalog = [] }: Props = $props();

	const hourlyGroups = $derived(groupCompareCatalog(catalog));

	// Vorgabemenge („nie eingestellt") und Merge-Signale kommen aus der
	// Katalogantwort, nicht aus einer Frontend-Liste (#1406 B, AC-10) — damit
	// Renderer (HOURLY_DEFAULT_METRIC_IDS) und Bedienflaeche nachweisbar
	// dieselbe Vorgabe haben.
	const defaultHourlyKeys = $derived(
		hourlyGroups.filter((g) => g.hourly_default).map((g) => g.metric_id)
	);
	const mergeOnlyHourlyKeys = $derived(
		hourlyGroups
			.filter((g) => g.hourly_merge_only)
			.flatMap((g) => [g.metric_id, ...g.hourly_legacy_keys])
	);

	// „Nie eingestellt" (`null`) = Vorgabemenge. Eine bewusst geleerte Auswahl
	// (`[]`) bleibt leer — Issue #1366 F001: Anzeige UND Umschalt-Handler nutzen
	// ZWINGEND dieselbe Materialisierung, sonst driften beide auseinander.
	const materializedHourlyKeys = $derived(
		materializeHourlyMetricKeys(wiz.hourlyMetricKeys, defaultHourlyKeys)
	);

	/** AC-4 (Bestandsschutz): ein vor #1406 B gespeicherter Kurzschluessel
	 *  (`temp_c`) gehoert zur Zeile seiner Groesse (`temperature`) — sonst
	 *  zeigte der Editor das Kaestchen leer, waehrend die Mail die Spalte
	 *  weiterhin bringt, und der naechste Speichervorgang wuerfe die Auswahl
	 *  weg. Die Kurzschluessel kommen aus der Katalogantwort. */
	function isHourlyMetricActive(group: CompareAggregationGroup): boolean {
		if (materializedHourlyKeys.includes(group.metric_id)) return true;
		return group.hourly_legacy_keys.some((k) => materializedHourlyKeys.includes(k));
	}

	function makeHourlyMetricHandler(group: CompareAggregationGroup) {
		return function handleHourlyMetric(): void {
			wiz.hourlyMetricKeys = applyHourlyMetricToggleFromState(
				wiz.hourlyMetricKeys,
				group.metric_id,
				!isHourlyMetricActive(group),
				defaultHourlyKeys,
				group.hourly_legacy_keys
			);
		};
	}

	function handleEnabledToggle(checked: boolean): void {
		wiz.hourlyEnabled = checked;
	}

	// ── Issue #1361 Befund 4: Reihenfolge-Block ──────────────────────────────
	// Merge-only Groessen (Windrichtung) fliegen aus der sortierbaren Liste --
	// sie erzeugen nie eine eigene Spalte. Sie bleiben oben im An/Aus-Katalog
	// unveraendert bedienbar (AC-5, keine Regression).
	const orderableHourlyKeys = $derived(
		orderableHourlyMetricKeys(materializedHourlyKeys, mergeOnlyHourlyKeys)
	);

	// Beschriftung der Reihenfolge-Liste: Registername je Groesse. Die
	// historischen Kurzschluessel zeigen auf denselben Namen, damit ein
	// Alt-Vergleich vor dem ersten Speichern keine nackten Kennungen zeigt.
	const hourlyMetricById = $derived.by(() => {
		const map: Record<string, MetricEntry> = {};
		// Issue #1453 (AC-7): die beiden uebrigen Namensformen stehen an den
		// flachen Katalog-Eintraegen, nicht an der nach Groesse gruppierten
		// Sicht — deshalb hier ueber `metric_id` zurueckgeschlagen statt
		// `CompareAggregationGroup` um zwei Felder zu erweitern, die die
		// Gruppierung selbst nicht braucht.
		const formsByMetricId = new Map(catalog.map((e) => [e.metric_id ?? e.metric, e]));
		for (const group of hourlyGroups) {
			const forms = formsByMetricId.get(group.metric_id);
			const col_label = forms?.col_label;
			const sms_code = forms?.sms_code;
			map[group.metric_id] = {
				id: group.metric_id, label: group.label, col_label, sms_code
			} as MetricEntry;
			for (const legacy of group.hourly_legacy_keys)
				map[legacy] = {
					id: legacy, label: group.label, col_label, sms_code
				} as MetricEntry;
		}
		return map;
	});

	function onHourlyRemove(key: string): void {
		const group = hourlyGroups.find(
			(g) => g.metric_id === key || g.hourly_legacy_keys.includes(key)
		);
		if (!group) return;
		makeHourlyMetricHandler(group)();
		onHourlyCommit?.();
	}

	function handleHourlyDndReorder(newOrder: string[]): void {
		wiz.hourlyMetricKeys = applyHourlyReorder(
			materializedHourlyKeys,
			newOrder,
			mergeOnlyHourlyKeys
		);
		onHourlyCommit?.();
	}

	// Roh/Einfach-Umschalter gibt es im Stundenverlauf nicht (indicatorCapable()
	// ist fuer diese Kennungen durchgaengig false; die Segmented-Steuerung wird
	// also nie gerendert). Named function statt Inline-Closure im Markup
	// (Safari-Factory-Muster).
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
	<!-- Eine Zeile je Wettergroesse aus derselben Katalogantwort wie Uebersicht
	     und Ausblick. AC-11: eine ausgenommene Groesse („Sonnenstunden") steht
	     SICHTBAR da, nicht anwaehlbar und mit Begruendung — nicht kommentarlos
	     fehlend. Zustand und Begruendung kommen aus den Katalogdaten, nicht aus
	     einer Frontend-Sonderregel. -->
	{#each groupCompareCatalog(catalog) as group (group.metric_id)}
		<label
			class="hourly-metric-row"
			class:disabled={!group.hourly_selectable}
			data-testid={`compare-layout-hourly-metric-${group.metric_id}`}
		>
			<input
				type="checkbox"
				checked={isHourlyMetricActive(group)}
				disabled={!group.hourly_selectable}
				onchange={makeHourlyMetricHandler(group)}
			/>
			<span>{group.label}</span>
			{#if !group.hourly_selectable && group.hourly_not_selectable_reason}
				<span
					class="hourly-metric-reason"
					data-testid={`compare-layout-hourly-reason-${group.metric_id}`}
				>{group.hourly_not_selectable_reason}</span>
			{/if}
		</label>
	{/each}
</div>

<!-- Issue #1361 Befund 4/5: DERSELBE geteilte Reihenfolge-Baustein wie oben bei
     den Uebersichts-Groessen (WeatherMetricsTab.svelte, WeatherV2Reihenfolge)
     -- kein Compare-Eigenbau (Trip/Compare-Teilungs-Invariante).

     activeChannel="email" -- BEWUSST, keine Schnittlinie: hourly_metrics wird
     ausschliesslich an render_compare_email uebergeben (comparison.py).
     render_compare_telegram kennt keinerlei Stundendaten-Bezug; SMS hat
     max_table_cols: 0, gar keine Tabelle. Der Stundenverlauf existiert also NUR
     in der E-Mail -- eine "ab hier von Telegram gekappt"-Linie waere eine
     Falschaussage (die 8er-CHANNEL_LIMITS-Grenze gilt fuer die Uebersichts-
     Metriken, nicht fuer den Stundenverlauf) und wuerde die mit #1360 AC-4
     gerade beseitigte Fehlerklasse neu einfuehren. NICHT nachruesten, ohne
     diese Faktenlage zu widerlegen. -->
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
	.hourly-metric-row {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: var(--g-text-sm);
		color: var(--g-ink);
	}
	.hourly-metric-row.disabled {
		color: var(--g-ink-muted);
	}
	.hourly-metric-reason {
		font-size: var(--g-text-xs, 12px);
		color: var(--g-ink-muted);
		line-height: 1.4;
	}
</style>
