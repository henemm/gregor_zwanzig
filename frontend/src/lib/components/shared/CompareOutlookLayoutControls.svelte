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
		toggleCompareMetricKey
	} from './weather-metrics-tab/compareMetricOrder.ts';
	import { splitChannelMetricsForDisplay } from './weather-metrics-tab/channelMetricLayouts.ts';
	import { outlookFriendlyCapable } from './weather-metrics-tab/outlookFriendlyCapability.ts';

	// Issue #1720 S1: flache Props statt `CompareWizardState`-Bindung — dasselbe
	// Bauteil bedient jetzt Ortsvergleich UND Trip (parametrisiert statt
	// kopiert, Trip/Compare-Teilungs-Invariante). Der Speicher-Weg bleibt wie
	// bisher AUSSERHALB: der Vergleich schreibt in den wiz-State, der Trip in
	// seinen `$state` + `scheduleAutoSave()`.
	interface Props {
		/** `null` = nie eingestellt (nichts abgewaehlt), `[]` = bewusst leer. */
		metricKeys: string[] | null;
		/** Issue #1848 A3: die Grundauswahl der FLAECHE — die Ausgangsmenge,
		 *  aus der der Ausblick nur noch ABWAEHLEN darf (ADR-0050 Regel 1/2,
		 *  loest ADR-0053 Punkt 1 ab). Der Ortsvergleich reicht seine
		 *  Katalog-Schluessel durch (`temp_max_c`), der Trip seine Kennungen
		 *  (`temperature`) — beide Vokabulare werden hier auf die Kennung
		 *  normalisiert. `null`/leer = kein Maximum bekannt (D4): Verhalten
		 *  wie vor A3. */
		grundauswahl?: string[] | null;
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
		/** Issue #2049: Roh/Einfach je Groesse (`true` = Einfach), gespeichert
		 *  in `display_config.outlook_metric_formats`. `null`/fehlend = nie
		 *  eingestellt, also durchgaengig Roh. */
		metricFormats?: Record<string, boolean> | null;
		/** Neue Roh/Einfach-Zuordnung nach oben melden. OHNE diesen Prop
		 *  erscheint KEIN Umschalter — eine Flaeche, die die Einstellung nicht
		 *  speichern kann, darf sie auch nicht anbieten (sonst genau der
		 *  wirkungslose Schalter, der #2049 ausgeloest hat). */
		onMetricFormats?: (formats: Record<string, boolean>) => void;
	}
	let {
		metricKeys, catalog, onMetricKeys, onOutlookCommit,
		title = '3-Tages-Ausblick', enabled = true, onEnabledChange,
		showEmailOnlyHint = true, grundauswahl = null,
		metricFormats = null, onMetricFormats
	}: Props = $props();

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

	// Issue #1848 A3: die Grundauswahl der Flaeche, uebersetzt in das Vokabular
	// des Ausblicks (KENNUNGEN seit A2). Die Zuordnung Katalog-Schluessel ->
	// Kennung kommt aus DEMSELBEN gruppierten Katalog wie die Beschriftungen
	// (`groupCompareCatalog`), nicht aus einer zweiten Tabelle. Groessen ohne
	// Ausblick-Katalogzeile (kein Tageswert, z. B. `confidence`) fallen heraus:
	// sie erscheinen weder in der aktiven Liste noch in der „Aus"-Gruppe
	// (AC-5, Spec „Known Limitations").
	const grundauswahlKennungen = $derived.by(() => {
		if (grundauswahl === null) return null;
		const kennungJeSchluessel: Record<string, string> = {};
		for (const group of groupCompareCatalog(catalog)) {
			for (const option of group.options) kennungJeSchluessel[option.key] = group.metric_id;
		}
		const gesehen = new Set<string>();
		const kennungen: string[] = [];
		for (const eintrag of grundauswahl) {
			const id = kennungJeSchluessel[eintrag] ?? eintrag;
			if (gesehen.has(id) || !outlookMetricById[id]) continue;
			gesehen.add(id);
			kennungen.push(id);
		}
		return kennungen;
	});

	// Issue #1848 A3 (AC-12): DIESELBE Mengenrechnung wie die Kanal-Reiter —
	// `splitChannelMetricsForDisplay(Grundauswahl, Auswahl)`, kein zweiter
	// Algorithmus. `metricKeys === null` (nie eingestellt) heisst „nichts
	// abgewaehlt": die Auswahl IST die Grundauswahl. Ohne bekannte
	// Grundauswahl (Altbestand/Katalog nicht geladen) bleibt es beim Verhalten
	// vor A3 (ADR-0050 D4: kein Maximum -> nicht schneiden).
	const ausblickSpalten = $derived.by(() => {
		const grund = grundauswahlKennungen;
		if (grund === null || grund.length === 0) {
			return { active: materializeOutlookMetricKeys(metricKeys), off: [] as string[] };
		}
		return splitChannelMetricsForDisplay(grund, metricKeys ?? grund);
	});
	const materializedOutlookKeys = $derived(ausblickSpalten.active);
	const offOutlookKeys = $derived(ausblickSpalten.off);

	/** Abwaehlen („Aus") und Zurueckholen („Ein") sind dieselbe Operation auf
	 *  derselben Liste — nur die Richtung unterscheidet sich. Materialisiert
	 *  wird ZWINGEND aus derselben Quelle wie die Anzeige (#1366 F001);
	 *  Zurueckholen haengt die Groesse ans Ende an (Trip-Muster, #1359 AC-2)
	 *  und schreibt ausschliesslich in `outlook_metrics`, nie in die
	 *  Grundauswahl (AC-9). */
	function toggleOutlookKey(key: string): void {
		onMetricKeys(toggleCompareMetricKey(materializedOutlookKeys, key));
		onOutlookCommit?.();
	}

	function onOutlookRemove(key: string): void {
		toggleOutlookKey(key);
	}

	function onOutlookRestore(key: string): void {
		toggleOutlookKey(key);
	}

	function handleOutlookDndReorder(newOrder: string[]): void {
		onMetricKeys(newOrder);
		onOutlookCommit?.();
	}

	// Issue #2049: der Roh/Einfach-Umschalter des Ausblicks. Bis hierher war er
	// eine Attrappe (leere `friendlyMap`, No-Op-Handler) — ein Klick veraenderte
	// nichts. Named functions statt Inline-Closures (Safari-Factory-Muster).
	const outlookFriendlyMap = $derived(metricFormats ?? {});

	function onOutlookMode(id: string, useIndicator: boolean): void {
		// Read-Modify-Write auf der bestehenden Zuordnung: ein Umschalten darf
		// die Einstellung der anderen Groessen nicht verlieren.
		onMetricFormats?.({ ...outlookFriendlyMap, [id]: useIndicator });
		onOutlookCommit?.();
	}

	// Sichtbar ist der Umschalter nur, wo er auch wirkt: DIESELBE Liste, gegen
	// die der Backend-Formatierer verzweigt (AC-4). Kann die Flaeche die
	// Einstellung nicht speichern (kein `onMetricFormats`), erscheint gar
	// keiner — der Zustand vor dieser Aenderung.
	function outlookModeCapable(id: string): boolean {
		return onMetricFormats !== undefined && outlookFriendlyCapable(id);
	}
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
<!-- Issue #1848 A3 (Block A, Issue #2029): die zweite Kaestchenliste entfaellt
     ERSATZLOS. Der Ausblick verhaelt sich ab hier exakt wie E-Mail, Telegram
     und SMS: Ausgangsmenge ist die Grundauswahl der Flaeche, abgewaehlt wird
     ueber den „Aus"-Knopf der Reihenfolge-Liste, zurueckgeholt ueber die
     „Aus"-Gruppe darunter (ADR-0050 Regel 4 — loest AC-13 aus fix_1719_s3 ab,
     deren Begruendung genau diese Kaestchen waren).

     DERSELBE geteilte Reihenfolge-Baustein wie bei Uebersicht und
     Stundenverlauf (WeatherV2Reihenfolge, ADR-0024) — kein Compare-Eigenbau.
     activeChannel="email": der Ausblick existiert nur in der E-Mail
     (render_compare_email), analog der Begruendung im Stundenverlauf-Block. -->
<div data-testid="compare-layout-outlook-metrics">
	{#if materializedOutlookKeys.length > 0 || offOutlookKeys.length > 0}
		{#if showEmailOnlyHint}
			<p class="outlook-email-hint" data-testid="compare-layout-outlook-email-only-hint">
				Erscheint nur in der E-Mail.
			</p>
		{/if}
		<Card padding={0} style="margin-top: 6px">
			<WeatherV2Reihenfolge
				primaryColumns={materializedOutlookKeys}
				metricById={outlookMetricById}
				friendlyMap={outlookFriendlyMap}
				activeChannel="email"
				highlight={null}
				onRemove={onOutlookRemove}
				onDndReorder={handleOutlookDndReorder}
				onMode={onOutlookMode}
				modeCapable={outlookModeCapable}
				offColumns={offOutlookKeys}
				onRestore={onOutlookRestore}
				kuerzelById={outlookKuerzelById}
			/>
		</Card>
	{/if}
</div>

<style>
	.outlook-email-hint {
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		line-height: 1.5;
		margin: 10px 0 0;
	}
</style>
