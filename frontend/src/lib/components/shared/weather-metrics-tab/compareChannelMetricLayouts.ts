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
	type CompareSelectionEntry,
	type StoredActiveMetric
} from './compareMetricSelection.ts';

/** Die drei Metrik-Kanaele des Compare-Briefings. Premium-SMS ist seit #2275
 *  auch Versandkanal des Vergleichs-Briefings, traegt aber den SMS-Inhalt und
 *  hat deshalb keine eigene Metrik-Auswahl (ADR-0049). */
export const COMPARE_CHANNEL_IDS: ChannelId[] = ['email', 'telegram', 'sms']; // ADR-0049: nur Metrik-Kanäle

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

// Issue #3276 (Spec-AC-38): die Schreib-Naht `mergeAllCompareChannelActiveMetricsForSave`
// ist entfallen — der Ortsvergleich sendet `channel_active_metrics` nicht mehr
// (Altschluessel, Tabelle „Was steht wo" ist die Quelle, ADR-0124).

/**
 * Copy-on-write-Startpunkt des ersten Kanal-Edits: Klon der globalen
 * Reihenfolge. Das Array darf NICHT mit der Grundauswahl geteilt werden —
 * sonst veraenderte ein SMS-Edit die globale Auswahl und damit alle anderen
 * Kanaele mit (Vorbild `startChannelOverride`, channelMetricLayouts.ts:67).
 */
export function startCompareChannelOverride(globalKeys: readonly string[]): string[] {
	return [...globalKeys];
}

/** Die gespeicherten Kanal-Listen des Vergleichs, die eine globale Umschaltung
 *  beruehrt (`null`/`undefined` = nie eingestellt, folgt der Grundauswahl).
 *  Issue #3276: Ausblick-/Stundenverlauf-Listen fuehrt der Vergleich nicht mehr. */
export interface CompareGespeicherteListen {
	channelActive: CompareChannelActiveMetrics | null | undefined;
}

/**
 * #3047 T3 Orte (AC-10, Konzept einstellungen_neu.md §5 Punkt 6/8): Folgen der
 * globalen Umschaltung von `metric` (Auswahl-Schluessel) fuer die bereits
 * gespeicherten Kanal-Listen -- Compare-Seite von `toggleGlobalMetric` (Trip).
 *  - ABWAHL (`wasOn`): wie seit #1703 S8 (ADR-0050 Regel 3) sofort aus jeder
 *    gespeicherten Kanal-Liste.
 *  - EINWAHL: hinten an jede gespeicherte Kanal-Liste. Bestehende Folge und
 *    Abwahlen bleiben.
 * Unveraenderte Listen behalten ihre Referenz (Aufrufer erkennt „nichts zu tun").
 */
export function compareToggleFolgen(
	metric: string,
	wasOn: boolean,
	listen: CompareGespeicherteListen
): CompareGespeicherteListen {
	return { channelActive: kanalFolgen(listen.channelActive, metric, wasOn) };
}

function kanalFolgen(
	channelActive: CompareChannelActiveMetrics | null | undefined,
	metric: string,
	wasOn: boolean
): CompareChannelActiveMetrics | null | undefined {
	if (!channelActive) return channelActive;
	const next = { ...channelActive };
	let changed = false;
	for (const ch of COMPARE_CHANNEL_IDS) {
		const override = next[ch];
		if (override == null || override.includes(metric) !== wasOn) continue;
		next[ch] = wasOn ? override.filter((id) => id !== metric) : [...override, metric];
		changed = true;
	}
	return changed ? next : channelActive;
}
