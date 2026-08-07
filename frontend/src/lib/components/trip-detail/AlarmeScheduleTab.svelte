<script lang="ts">
	// AlarmeScheduleTab — Issue #1258 Scheibe S3 (D4): duenner Trip-Container
	// analog BriefingScheduleTab.svelte. Bettet den geteilten AlarmeTab
	// (context="route") ein und berechnet NUR die route-spezifischen
	// Initialwerte aus dem Trip (Metrik-Levels, Korridor-Zaehler, Kanal-
	// Rekonstruktion) — der Container haelt KEINE eigene Persistenz-Quelle
	// mehr.
	//
	// Adversary Fix-Loop 1, F001: Kanal-Toggle und Metrik-Level-Aenderung
	// hatten hier je einen eigenen Debounce-Save-Aufruf (auf demselben
	// saveController), neben dem EINEN $effect in AlarmeTab.svelte — alle
	// drei teilten sich denselben Ein-Slot-Debounce
	// (saveStatusStore.svelte.ts:67-72), zwei Aenderungen aus verschiedenen
	// Quellen im 700ms-Fenster verwarfen die erste Payload still
	// (Datenverlust). Fix: Kanaele und Metrik-Level sind jetzt Teil der EINEN
	// konsolidierten Payload in AlarmeTab.svelte — dieser Container liefert
	// nur noch Initialwerte, keine zweite Schreibquelle mehr.
	//
	// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md
	//   (Implementation Details Abschnitt 9 "S3-Detail-Festlegungen", D4, AC-13..15)
	// Kontext: docs/context/feat-1258-s3-trip-alarme-tab.md

	import AlarmeTab from '$lib/components/shared/AlarmeTab.svelte';
	import { reconstructTripAlertChannels } from '../shared/alarme-tab/tripChannelReconstruction.ts';
	import { deriveActiveAlertMetricsForTrip } from '../shared/alarme-tab/tripAlertMetricsFromCatalog.ts';
	import type { Trip, AlertMetric, SensLevel } from '$lib/types';
	import type { MetricCatalog } from './metricsEditor.ts';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';

	interface Props {
		trip: Trip;
		onTripUpdate?: (updated: Trip) => void;
		saveController?: SaveStatus;
		/** Fix #1544/#1545: der in TripTabs bereits geladene Metrik-Katalog —
		 *  kein eigener Abruf. */
		metricsCatalog?: MetricCatalog | null;
	}
	let { trip, onTripUpdate, saveController, metricsCatalog = null }: Props = $props();

	// ── (c) Metrik-Level-Tabelle: Initialwert aus display_config.metric_alert_levels ──
	// Fix #1544/#1545 (AC-6, Falle 4): UNGEFILTERTER Passthrough. Diese Quelle
	// speist den Speicherweg, der `metric_alert_levels` vollstaendig ersetzt —
	// wuerde sie mitgefiltert, verloere jede gerade nicht angezeigte Groesse
	// beim naechsten Speichern ihre Stufe. Getrennt von `activeMetrics`.
	const metricLevels = $derived(
		(trip.display_config?.metric_alert_levels ?? {}) as Record<AlertMetric, SensLevel>
	);
	// Fix #1544/#1545: Zeilen aus Auswahl x Register statt aus den persistierten
	// Schluesseln (Fehlerklassen 1-3). Rechnet hier im Container, damit der
	// geteilte AlarmeTab im `route`-Zweig unveraendert nur `activeMetrics` liest.
	const activeMetrics = $derived(
		deriveActiveAlertMetricsForTrip(trip.display_config?.metrics, metricsCatalog ?? {})
	);

	// ── (d) Kanaele: AC-15 Ist-Zustand-Rekonstruktion als Initialwert ──────────
	const existingChannels = $derived(reconstructTripAlertChannels(trip));
</script>

<div class="alarme-schedule-tab">
	<AlarmeTab
		context="route"
		{trip}
		{onTripUpdate}
		{saveController}
		{activeMetrics}
		{metricLevels}
		{existingChannels}
		existingChannelThresholds={trip.alert_channel_thresholds}
	/>
</div>
