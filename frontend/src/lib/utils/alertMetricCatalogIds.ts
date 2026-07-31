// #1401 Scheibe B, Teil 2 — Zuordnung AlertMetric → Metrik-Register-ID
// (src/app/metric_catalog.py). Spec:
//   docs/specs/modules/fix_1401b_register_stundenverlauf_alarme.md
//
// Reine Dokumentation der Herkunft + Grundlage des Vollstaendigkeits-Tests:
// die Alarm-Beschriftungen selbst stehen statisch in alertMetricLabels.ts
// (bewusst kein Laufzeit-Abruf, s. Spec "Implementation Details" Teil 2).

import type { AlertMetric } from '$lib/types';

export const ALERT_METRIC_TO_CATALOG_ID: Partial<Record<AlertMetric, string>> = {
	wind_gust: 'gust',
	precipitation_sum: 'precipitation',
	thunder_level: 'thunder',
	snow_line: 'snowfall_limit',
	cape: 'cape',
	visibility: 'visibility',
	humidity: 'humidity',
	freezing_level: 'freezing_level',
	fresh_snow: 'fresh_snow',
	// Zwei Auswertungen derselben Register-Groesse — die Unterscheidung traegt
	// der label_de-Text ("Temperatur (Minimum)"/"(Maximum)"), nicht die ID.
	temperature_min: 'temperature',
	temperature_max: 'temperature'
};

/**
 * Aenderungs-Groessen: sie beschreiben den Sprung einer Groesse zwischen zwei
 * Zeitpunkten und haben deshalb keine eigene Entsprechung im Register.
 *
 * Bewusst NICHT identisch mit `DELTA_ONLY_METRICS`
 * (alert-rules-editor/alertRuleDefaults.ts): dort geht es um den zulaessigen
 * Regel-Modus, weshalb `thunder_level` dazugehoert — hier geht es um die
 * Herkunft der Beschriftung, und `thunder_level` hat mit "thunder" eine
 * gueltige Register-Entsprechung.
 */
export const NON_CATALOG_ALERT_METRICS: ReadonlySet<AlertMetric> = new Set<AlertMetric>([
	'temperature_change',
	'wind_change',
	'precipitation_change'
]);
