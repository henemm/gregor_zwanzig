// channelMetricLayouts.ts — Issue #1575 Scheibe 3: kanal-eigene Metrik-Auswahl
// im Trip-Editor (context="route").
//
// Spec: docs/specs/modules/fix_1575_channel_metric_selection.md (Teil 2)

import type { ChannelLayouts, WeatherConfigMetric } from '$lib/types';
import type { ChannelId } from '$lib/components/shared/layout-tab/ltChannels';
import type { Buckets } from '$lib/components/trip-detail/metricsEditor';

export interface ChannelOverride {
	buckets: Buckets;
	friendlyMap: Record<string, boolean>;
}

/**
 * Setzt den Kanal-Eintrag von `channel` auf `metrics` und laesst alle anderen
 * Kanaele unberuehrt.
 *
 * `internal/handler/config_merge.go` mergt `display_config` nur shallow auf
 * oberster Schluesselebene — wer beim Speichern nur den aktiven Kanal sendet,
 * loescht die uebrigen lautlos (BUG-DATALOSS-GR221-Muster). `metrics === null`
 * bedeutet: dieser Kanal wurde nie editiert und bekommt keinen eigenen
 * Eintrag, damit die Backend-Kaskade weiter auf die globale Auswahl faellt.
 */
export function mergeChannelLayoutsForSave(
	prevLayouts: ChannelLayouts | undefined,
	channel: ChannelId,
	metrics: WeatherConfigMetric[] | null
): ChannelLayouts {
	const next: ChannelLayouts = { ...(prevLayouts ?? {}) };
	if (metrics === null) return next;
	next[channel] = metrics;
	return next;
}

/**
 * Baut den Kanal-Eintrag aus einer gespeicherten `channel_layouts[kanal]`-Liste
 * zurueck, damit ein editierter Reiter nach dem Reload seine eigene Auswahl
 * zeigt (AC-4/AC-5). Der Trip-Editor kennt kein Detail-Bucket (#587) — alles
 * Aktive landet in `primary`.
 */
export function channelOverrideFromMetrics(
	metrics: WeatherConfigMetric[],
	catalogIds: string[],
	fallbackFriendly: Record<string, boolean>
): ChannelOverride {
	const active = metrics
		.filter((m) => m.enabled)
		.slice()
		.sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
	const activeIds = new Set(active.map((m) => m.metric_id));
	const friendlyMap = { ...fallbackFriendly };
	for (const m of metrics) {
		if (m.use_friendly_format !== undefined) friendlyMap[m.metric_id] = m.use_friendly_format;
	}
	return {
		buckets: {
			primary: active.map((m) => m.metric_id),
			secondary: [],
			off: catalogIds.filter((id) => !activeIds.has(id))
		},
		friendlyMap
	};
}

/** Startpunkt eines Kanal-Eintrags: tiefe Kopie der globalen Auswahl (AC-2). */
export function startChannelOverride(
	buckets: Buckets,
	friendlyMap: Record<string, boolean>
): ChannelOverride {
	return {
		buckets: {
			primary: [...buckets.primary],
			secondary: [...buckets.secondary],
			off: [...buckets.off]
		},
		friendlyMap: { ...friendlyMap }
	};
}
