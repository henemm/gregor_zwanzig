// Issue #3097 (W11, Epic #3058) — Roh/Einfach-Umschalter je Zeile im
// Orte-Stundenverlauf.
// Spec: docs/specs/modules/feat_3097_orte_stundenverlauf_darstellung.md (AC-7)
//
// gz-eigenstaendig: der Stundenverlauf existiert nur im Ortsvergleich (Trip hat
// kein Pendant). Die Sichtbarkeit des Umschalters folgt DERSELBEN
// Faehigkeitsliste wie der Ausblick (`outlookFriendlyCapable`, Frontend-Haelfte
// von `app.metric_catalog.OUTLOOK_FRIENDLY_CAPABLE`): genau diese Groessen
// verzweigt `_friendly_hour_text` im Backend. Temperatur und Gewitter haben
// keine Einfachform und bekommen keinen Umschalter.
//
// Kein Browser-/SvelteKit-Import — lauffaehig unter node --experimental-strip-types.

import { outlookFriendlyCapable } from '../shared/weather-metrics-tab/outlookFriendlyCapability.ts';

/** Hat diese Groesse im Stundenverlauf eine Einfachform? */
export function hourlyFriendlyCapable(metricId: string): boolean {
	return outlookFriendlyCapable(metricId);
}

/**
 * `friendlyMap` fuer die Reihenfolge-Liste des Stundenverlaufs: nur Groessen mit
 * Einfachform erscheinen (sonst kein Umschalter), Wert `true` = Einfach,
 * fehlender Eintrag in `formats` = Roh (`display_config.hourly_metric_formats`).
 */
export function buildHourlyFriendlyMap(
	metricIds: readonly string[],
	formats: Record<string, boolean> | null | undefined
): Record<string, boolean> {
	const map: Record<string, boolean> = {};
	for (const id of metricIds) {
		if (hourlyFriendlyCapable(id)) map[id] = formats?.[id] === true;
	}
	return map;
}
