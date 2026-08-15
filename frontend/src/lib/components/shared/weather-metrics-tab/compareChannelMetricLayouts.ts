// compareChannelMetricLayouts.ts — Issue #1703 Scheibe 8: kanal-eigene
// Metrik-Auswahl der UEBERSICHTSTABELLE im Ortsvergleich
// (context="vergleich"), Compare-Pendant zu `channelMetricLayouts.ts`.
//
// Spec: docs/specs/modules/feat_1703_s8_compare_kanal_tabs.md (Abschnitt 3+4)
//
// Bewusst SCHLANKER als das Trip-Modul: Compare speichert je Kanal nur EINE
// geordnete Auswahlliste (`string[]`), keine Buckets und keine Friendly-Map —
// das Compare-Speicherformat kennt kein `enabled`-Feld. „Aus in diesem Kanal"
// ist damit reine Anzeige (splitChannelMetricsForDisplay), kein gespeicherter
// Zustand.
//
// `splitChannelMetricsForDisplay()` wird NICHT nachgebaut — sie ist bereits
// generisch ueber `string[]` (channelMetricLayouts.ts:92-101) und wird vom
// Vergleichs-Editor direkt aus dem Trip-Modul importiert.

import type { ChannelId } from '$lib/components/shared/layout-tab/ltChannels';
import {
	normalizeStoredActiveMetrics,
	registeredCompareMetricCatalog,
	toStoredActiveMetrics,
	type CompareSelectionEntry,
	type StoredActiveMetric
} from './compareMetricSelection.ts';

/** Die drei Kanaele des Compare-Briefings (ADR-0049: kein Premium-SMS —
 *  im Ortsvergleich ist Premium-SMS reiner Alarm-Kanal, #1745). */
export const COMPARE_CHANNEL_IDS: ChannelId[] = ['email', 'telegram', 'sms'];

/** Kanal-Overrides der Uebersicht: `null` = nie editiert (folgt der
 *  Grundauswahl), `[]` = bewusste Leerauswahl fuer diesen Kanal. */
export type CompareChannelActiveMetrics = Record<ChannelId, string[] | null>;

/** Startzustand ohne jeden Override — alle drei Kanaele folgen der Grundauswahl. */
export function emptyCompareChannelActiveMetrics(): CompareChannelActiveMetrics {
	return { email: null, telegram: null, sms: null };
}

/**
 * Lese-Naht: `display_config.channel_active_metrics` -> Auswahl-Schluessel je
 * Kanal. Ein FEHLENDER Kanal-Key bleibt `null` (nie editiert), ein
 * vorhandenes leeres Array bleibt `[]` (bewusste Leerauswahl, AC-S8-11) —
 * dieselbe „fehlend != leer"-Semantik wie `active_metrics` selbst
 * (#1191/#1366). Die Uebersetzung Alt-/Neuformat -> Schluessel macht
 * unveraendert `normalizeStoredActiveMetrics()`, verlustfrei (#1373).
 */
export function compareChannelActiveMetricsFromStored(
	stored: Record<string, StoredActiveMetric[]> | undefined,
	catalog: CompareSelectionEntry[] = registeredCompareMetricCatalog()
): CompareChannelActiveMetrics {
	const result = emptyCompareChannelActiveMetrics();
	if (!stored || typeof stored !== 'object') return result;
	for (const ch of COMPARE_CHANNEL_IDS) {
		if (stored[ch] === undefined) continue;
		result[ch] = normalizeStoredActiveMetrics(stored[ch], catalog) ?? [];
	}
	return result;
}

/**
 * Schreib-Naht (AC-S8-10, Gegenprobe M4/M5): serialisiert JEDEN nicht-`null`-
 * Eintrag, nicht nur den zuletzt sichtbaren Kanal-Reiter — Compare-Pendant zu
 * `mergeAllChannelLayoutsForSave` (Trip-Lehre #1719 S3).
 *
 * `internal/handler/config_merge.go:11-22` ersetzt jeden display_config-
 * Top-Level-Key als GANZES und loescht nie einen Key. Daraus folgen zwei
 * Pflichten: (1) nie editierte Kanaele muessen aus `prevStored` mitreisen,
 * sonst gehen sie lautlos verloren (BUG-DATALOSS-GR221-Muster); (2) eine
 * bewusst geleerte Auswahl muss als `[]` mitreisen — ein weggelassener
 * Schluessel laesst serverseitig den ALTEN Stand stehen (M5).
 *
 * Mutiert `prevStored` nicht.
 */
export function mergeAllCompareChannelActiveMetricsForSave(
	prevStored: Record<string, StoredActiveMetric[]> | undefined,
	channelOverrides: CompareChannelActiveMetrics,
	catalog: CompareSelectionEntry[] = registeredCompareMetricCatalog()
): Record<string, StoredActiveMetric[]> {
	let next: Record<string, StoredActiveMetric[]> = { ...(prevStored ?? {}) };
	for (const ch of COMPARE_CHANNEL_IDS) {
		const override = channelOverrides?.[ch];
		// `== null` deckt „nie editiert" (null) UND ein fehlendes Feld (undefined)
		// ab; `[]` faellt bewusst NICHT darunter und wird serialisiert.
		if (override == null) continue;
		next = { ...next, [ch]: toStoredActiveMetrics(override, catalog) };
	}
	return next;
}

/**
 * Copy-on-write-Startpunkt des ersten Kanal-Edits: Klon der globalen
 * Reihenfolge. Das Array darf NICHT mit der Grundauswahl geteilt werden —
 * sonst veraenderte ein SMS-Edit die globale Auswahl und damit alle anderen
 * Kanaele mit (Vorbild `startChannelOverride`, channelMetricLayouts.ts:67).
 */
export function startCompareChannelOverride(globalKeys: readonly string[]): string[] {
	return [...globalKeys];
}
