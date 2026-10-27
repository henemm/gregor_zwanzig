// Issue #2049 — Faehigkeitsliste des Roh/Einfach-Umschalters im 3-Tages-Ausblick.
//
// Frontend-Haelfte von `app.metric_catalog.OUTLOOK_FRIENDLY_CAPABLE`. Die
// Sichtbarkeit des Umschalters (hier) und die Formatierungsverzweigung
// (Backend) muessen dieselbe Menge benutzen, sonst zeigt eine Groesse einen
// sichtbaren, aber wirkungslosen Umschalter — genau der Bug, der #2049
// ausgeloest hat. `outlookFriendlyCapabilityDrift.test.ts` liest die
// LIVE-Backend-Liste per `uv run python3` und vergleicht sie mit dieser Kopie
// in beide Richtungen.
//
// `indicatorCapable()` (trip-detail/metricsEditor.ts) ist hier NICHT der
// richtige Waechter: jene Liste beschreibt die Stundentabelle der Mail und
// kennt die Ausblick-Semantik nicht (sie fuehrt `thunder`/`cape`, die im
// Ausblick keine Einfach-Form haben, und ihre Wortskalen sind andere).

export const OUTLOOK_FRIENDLY_CAPABLE: readonly string[] = [
	'wind_direction',
	'cloud_total',
	'cloud_low',
	'cloud_mid',
	'cloud_high',
	'wind',
	'gust',
	'precipitation',
	'rain_probability',
	'sunshine'
];

const CAPABLE_SET = new Set(OUTLOOK_FRIENDLY_CAPABLE);

/** Hat diese Groesse im Ausblick eine Einfach-Form? */
export function outlookFriendlyCapable(metricId: string): boolean {
	return CAPABLE_SET.has(metricId);
}
