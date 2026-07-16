// Issue #1269 Fix-Loop 2 (Adversary F001, Staging-Fund): Mount-Kanonisierung
// des Compare-Layout-Tabs (Buckets -> ChannelLayouts-Roundtrip via
// buildWeatherConfigMetrics, s. CompareEditor.svelte `ltBuildLayouts()`) darf
// nicht als Nutzeränderung zählen — analog `reportConfigChangedByUser`
// (shared/reportConfigDirty.ts), aber für die Layout-Datenform
// (Record<channel, WeatherConfigMetric[]>) statt report_config.
//
// Prinzip: nur die für den Nutzer SICHTBAREN/wirksamen Eigenschaften der
// AKTIVEN (enabled) Metriken zählen — Bucket, Reihenfolge, Format,
// Horizonte. Deaktivierte ("off") Metriken tragen keine bedeutungsvolle
// Reihenfolge/Konfiguration; ihr exaktes Roundtrip-Format ist reine
// Kanonisierungs-Deatil, keine Nutzerabsicht. Robust unabhängig von
// Reaktivitäts-Timing, weil rein wertbasiert (keine Zeitstempel/Reihenfolge-
// Annahmen über WANN verglichen wird).

import { HORIZONS_ALL, type ChannelLayouts, type WeatherConfigMetric } from '$lib/types';

function normalizeChannel(metrics: WeatherConfigMetric[] | undefined): string {
	const enabledOnly = (metrics ?? [])
		.filter((m) => m.enabled)
		.map((m) => ({
			metric_id: m.metric_id,
			bucket: m.bucket ?? 'primary',
			order: m.order ?? 0,
			use_friendly_format: m.use_friendly_format ?? true,
			// Issue #343: fehlende horizons defaulten beim Laden auf HORIZONS_ALL
			// (s. CompareEditor.svelte ltHorizonsMapForChannel) — derselbe Default
			// hier, sonst wertet die Materialisierung als Aenderung.
			horizons: m.horizons ?? HORIZONS_ALL
		}))
		.sort((a, b) => (a.bucket === b.bucket ? a.order - b.order : a.bucket.localeCompare(b.bucket)));
	return JSON.stringify(enabledOnly);
}

const CHANNELS = ['email', 'telegram', 'sms'] as const;

/**
 * Entscheidet, ob sich ChannelLayouts gegenüber der Baseline WIRKLICH
 * (nutzerseitig) geändert haben. Reine Funktion, keine Seiteneffekte.
 */
export function channelLayoutsChangedByUser(
	baseline: ChannelLayouts | null | undefined,
	current: ChannelLayouts | null | undefined
): boolean {
	if (!baseline && !current) return false;
	for (const ch of CHANNELS) {
		if (normalizeChannel(baseline?.[ch]) !== normalizeChannel(current?.[ch])) return true;
	}
	return false;
}
