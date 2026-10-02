// Issue #1433 — generische Teilfeld-Auswahl fuer ALLE Schreiber (Trip und
// Ortsvergleich). Jeder Reiter sendet nur die Schluessel, die er selbst bedient;
// alles andere bleibt unerwaehnt und damit serverseitig unangetastet (der Go-Merge
// ist einstufig: Top-Level-Schluessel ueberschreiben, geloescht wird nie).
// Spec: docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md §2, §3.
//
// Loeschsemantik: `[]`, `{}`, `""`, `false`, `0`, `null` werden GESENDET, nur
// `undefined` wird uebersprungen. Die Quelle bleibt unveraendert (Pick findet nur
// beim Senden statt).

export interface Eigenfelder {
	/** Top-Level-Schluessel */
	top?: readonly string[];
	/** Schluessel unter `display_config` */
	display?: readonly string[];
	/** Schluessel unter `report_config` */
	report?: readonly string[];
}

function waehle(
	quelle: Record<string, unknown> | undefined | null,
	keys: readonly string[] | undefined
): Record<string, unknown> {
	const out: Record<string, unknown> = {};
	if (!quelle || !keys) return out;
	for (const k of keys) {
		if (quelle[k] !== undefined) out[k] = quelle[k];
	}
	return out;
}

export function pickEigenfelder(
	quelle: Record<string, unknown>,
	auswahl: Eigenfelder
): Record<string, unknown> {
	const body = waehle(quelle, auswahl.top);
	const dc = waehle(quelle.display_config as Record<string, unknown> | undefined, auswahl.display);
	if (Object.keys(dc).length > 0) body.display_config = dc;
	const rc = waehle(quelle.report_config as Record<string, unknown> | undefined, auswahl.report);
	if (Object.keys(rc).length > 0) body.report_config = rc;
	return body;
}

// ── Feld-Eigentuemer der Trip-Reiter (Spec §2) ───────────────────────────────

/** §2.3 — `report_config`-Schluessel des Reiters Versand. */
export const VERSAND_REPORT_KEYS = [
	'enabled',
	'morning_enabled',
	'evening_enabled',
	'morning_time',
	'evening_time',
	'multi_day_trend_morning',
	'multi_day_trend_evening',
	'multi_day_trend_reports',
	'send_email',
	'send_telegram',
	'send_sms',
	'send_premium_sms',
	'telegram_style'
] as const;

/** §2.3 — `report_config`-Schluessel des Reiters Wetter-Metriken (Inhalt + Tagesfenster). */
export const WETTER_REPORT_KEYS = [
	'show_compact_summary',
	'wind_exposition_min_elevation_m',
	'show_stage_stats',
	'show_metrics_summary',
	'show_outlook',
	'email_format',
	'show_yesterday_comparison',
	'day_window_start_hour',
	'day_window_end_hour'
] as const;

/** §2.2 — `display_config`-Schluessel des Reiters Wetter-Metriken. */
export const WETTER_DISPLAY_KEYS = [
	'metrics',
	'channel_layouts',
	'preset_name',
	'telegram_kurzform',
	'outlook_metrics',
	'outlook_metric_formats'
] as const;
