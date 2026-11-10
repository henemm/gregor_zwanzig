// weatherMetricsSavePayload.ts — Issue #2422 S2a Fix-Loop 1 (Adversary-Funde
// F003/F004): reine, exportierte Bausteine fuer die Speichern-Payload des
// Trip-Editors (context="route" — kein Compare-Pendant, der Ortsvergleich
// hat einen eigenen Speicherweg ueber `channel_active_metrics`, K10 der
// Spec docs/specs/modules/fix_2422_s2a_editor_gleich_gespeichert.md).
//
// Vorher lag die Bestand-AUSWAHL (`display_config.metrics` bzw.
// `display_config.channel_layouts[channel]`) direkt inline in
// WeatherMetricsTab.svelte — Mutation M5 (Adversary-Protokoll,
// docs/artifacts/fix-2422-s2-editor-gleich-gespeichert/adversary-dialog.md)
// zeigte, dass KEIN Kern-Test faengt, wenn die Komponente den Bestand
// weglaesst oder den falschen Kanal-Bestand nachschlaegt — die einzige
// Bewachung war der (staging-only, nicht in der CI-Ampel laufende) E2E-Test.
// Diese Datei zieht die Auswahl-Logik in reine TS-Funktionen, die ohne
// Svelte/DOM direkt per node:test gepruft werden koennen (F003).
//
// M6 (sms_threshold-Bereinigung entfernt) zeigte denselben Befund fuer die
// Threshold-Bereinigung (F004) — dieselbe Datei buendelt deshalb beide
// Zusicherungen fuer die GLOBALE Metrik-Liste in einer Funktion.

import {
	buildWeatherConfigMetrics,
	type Buckets,
	type BucketWeatherConfigMetric,
	type Horizons,
	type MetricCatalog,
} from '$lib/components/trip-detail/metricsEditor';
import type { ChannelOverride } from './channelMetricLayouts';
import { klon } from '../wetter-tab/klon.ts';
import type { ChannelId } from '$lib/components/shared/layout-tab/ltChannels';

/** Minimale Bestand-Form — nur die fuer die Auswahl noetigen Felder, damit
 * diese Funktionen ohne den vollen `Trip`-Typ (Svelte-Proxy) testbar sind. */
export interface DisplayConfigBestand {
	metrics?: ReadonlyArray<{ metric_id: string }> | null;
	channel_layouts?: Partial<Record<ChannelId, ReadonlyArray<{ metric_id: string }>>> | null;
}

/**
 * Fix #2422 S2a (K8, Adversary-Fund F003+F004): baut die GLOBALE
 * `display_config.metrics`-Liste fuer den Save.
 *
 * - Bestand-Auswahl: `displayConfig.metrics` (Read-Modify-Write statt
 *   Replace, CLAUDE.md #102) — eine weggelassene oder falsch ausgewaehlte
 *   Bestandsliste ist HIER, in einer reinen Funktion, per node:test bewacht.
 * - sms_threshold: ein gesetzter Editor-Wert ueberschreibt den Bestand; ist
 *   er leer/ungueltig, bleibt der Bestandswert unveraendert (#2792 S1c-3).
 */
export function buildGlobalMetricsForSave(
	displayConfig: DisplayConfigBestand | null | undefined,
	buckets: Buckets,
	friendlyMap: Record<string, boolean>,
	horizonsMap: Record<string, Horizons>,
	catalog: MetricCatalog,
	smsThresholds: Record<string, string>,
	smsThresholdMetricIds: readonly string[],
): BucketWeatherConfigMetric[] {
	const bestand = displayConfig?.metrics ?? [];
	const baseMetrics = buildWeatherConfigMetrics(buckets, friendlyMap, horizonsMap, catalog, bestand);
	return baseMetrics.map((m) => {
		if (!smsThresholdMetricIds.includes(m.metric_id)) return m;
		const rawThr = smsThresholds[m.metric_id];
		const parsed = rawThr !== undefined && rawThr !== '' ? parseFloat(rawThr) : null;
		if (parsed !== null && !isNaN(parsed)) {
			return { ...m, sms_threshold: parsed };
		}
		// #2792 S1c-3 (AC-24): Regler gesperrt — leer/ungueltig heisst „nicht
		// angefasst", der per RMW-Merge mitgebrachte Bestandswert bleibt (#102).
		return m;
	});
}

/**
 * Fix #2422 S2a (K8, Adversary-Fund F003): baut die Metrik-Liste fuer EINEN
 * Kanal-Layout-Eintrag (`display_config.channel_layouts[channel]`).
 *
 * Bestand-Auswahl ist an `channel` gebunden — ein Aufruf mit dem falschen
 * Kanal (oder ganz ohne Bestand) liefert nachweislich andere Werte als der
 * korrekte Aufruf; per node:test bewacht (siehe __tests__).
 */
export function buildChannelMetricsForSave(
	displayConfig: DisplayConfigBestand | null | undefined,
	channel: ChannelId,
	override: ChannelOverride,
	horizonsMap: Record<string, Horizons>,
	catalog: MetricCatalog,
): BucketWeatherConfigMetric[] {
	const bestand = displayConfig?.channel_layouts?.[channel] ?? [];
	return buildWeatherConfigMetrics(override.buckets, override.friendlyMap, horizonsMap, catalog, bestand);
}

/**
 * Issue #2792 S1a (AC-14): Profil-Ampel, die beim Anwenden einer Vorlage nach
 * `display_config.ampel` geht. Eigene Vorlage: Kopie ihrer Ampel samt
 * `alarm_ab` (Bestand ohne Ampel = Vorlage „allgemein"). Eingebaute Vorlage:
 * nur die Vorlagen-ID, damit fruehere Abweichungen nicht weiterwirken.
 * Zustellung und Etappen fasst das nie an (Spec §2).
 */
export function ampelBeimAnwenden(
	userPreset: { ampel?: Record<string, unknown> | null } | undefined,
	vorlageId: string,
): Record<string, unknown> {
	// Fix-Loop 3 #2794 (C1): `userPreset` stammt aus `$state` (Proxy) — structuredClone wirft dort.
	if (userPreset) return klon(userPreset.ampel ?? { template: 'allgemein' });
	return { template: vorlageId };
}
