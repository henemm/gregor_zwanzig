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

/**
 * Issue #1719 Scheibe S3 (AC-8/AC-12, ADR-0050 Regel 1/2): teilt die
 * Kanal-Reihenfolge in "aktiv" (sortierbar) und "aus" (wieder einschaltbar).
 *
 * `active` wird defensiv gegen `globalPrimary` gefiltert — eine Metrik, die
 * global nicht (mehr) aktiv ist, darf über einen stale Kanal-Override nicht
 * als "aktiv" zurückkommen. `off` = `globalPrimary` MINUS `active`
 * (Reihenfolge wie in `globalPrimary`). Eine global abgewählte Metrik
 * erscheint damit in KEINER der beiden Listen — ein Kanal kann sie nicht
 * zurückholen, es gibt für sie gar keinen Kanal-Eintrag.
 */
export function splitChannelMetricsForDisplay(
	globalPrimary: string[],
	channelPrimary: string[]
): { active: string[]; off: string[] } {
	const globalSet = new Set(globalPrimary);
	const active = channelPrimary.filter((id) => globalSet.has(id));
	const activeSet = new Set(active);
	const off = globalPrimary.filter((id) => !activeSet.has(id));
	return { active, off };
}

/**
 * Issue #1719 Scheibe S3 (AC-10, Persistenz-Fix — "der wichtigste Test der
 * Scheibe"): serialisiert JEDEN nicht-`null`-Eintrag aus `channelBuckets`,
 * nicht nur einen ausgezeichneten "aktiven" Kanal. Ohne diesen Fix geht eine
 * Durchschreibung (globale Abwahl -> alle Kanal-Overrides) beim Speichern
 * verloren, sobald der Nutzer nicht im editierten Kanal-Reiter steht
 * (Kontext-Dokument Abschnitt 10.1) — eine neue ADR-0050-Regel-3-Verletzung,
 * eingebaut von der Scheibe, die sie beheben soll.
 *
 * `channelBuckets[ch] === null` (nie editierter Kanal) lässt den Wert aus
 * `prevLayouts` unverändert — der Datenverlust-Schutz aus #1575 bleibt
 * gewahrt (`config_merge.go` ersetzt `channel_layouts` als GANZES, es gehen
 * also MEHR Kanäle mit, nie weniger). Mutiert `prevLayouts` nicht.
 */
export function mergeAllChannelLayoutsForSave(
	prevLayouts: ChannelLayouts | undefined,
	channelBuckets: Record<ChannelId, ChannelOverride | null>,
	buildMetrics: (override: ChannelOverride) => WeatherConfigMetric[]
): ChannelLayouts {
	let next: ChannelLayouts = { ...(prevLayouts ?? {}) };
	for (const ch of ['email', 'telegram', 'sms'] as ChannelId[]) {
		const override = channelBuckets[ch];
		if (override === null) continue;
		next = { ...next, [ch]: buildMetrics(override) };
	}
	return next;
}
