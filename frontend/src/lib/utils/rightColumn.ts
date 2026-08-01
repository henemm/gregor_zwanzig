// Epic #135 Step 5 — Pure-Function-Helper fuer die rechte Spalte im Trip-Detail
// Overview-Tab (Issues #158 + #159).
//
// Spec: docs/specs/modules/epic_135_step5_right_column.md §1.
//
// Issue #207: Nutzt jetzt die strukturierten Interfaces `Aggregation`,
// `WeatherConfig`, `ReportConfig` aus `$lib/types` — keine Casts auf
// `Record<string, unknown>` mehr. Defensive Runtime-Checks bleiben drin, weil
// das Backend `map[string]interface{}` schickt und Tests bewusst Off-Spec-Werte
// (Non-String, Non-Boolean) reinkippen, um Fallback-Pfade zu beweisen.

import type { Trip } from '$lib/types';

const TEMPLATE_LABELS: Record<string, string> = {
	wandern: 'Wandern',
	wintersport: 'Wintersport',
	skitouren: 'Skitouren',
	'alpen-trekking': 'Alpen-Trekking',
	radtour: 'Radtour',
	wassersport: 'Wassersport',
	allgemein: 'Allgemein',
	summer_trekking: 'Sommer-Trekking',
};

const DEFAULT_LABEL = 'Standard-Metriken';

export function getPresetLabel(trip: Trip): string {
	const savedKey = trip.display_config?.preset_name;
	if (savedKey && savedKey in TEMPLATE_LABELS) {
		return TEMPLATE_LABELS[savedKey];
	}
	const profile = trip.aggregation?.profile;
	if (profile === 'wintersport') return 'Wintersport-Standard';
	if (profile === 'wandern') return 'Wandern-Standard';
	if (profile === 'summer_trekking') return 'Sommer-Trekking-Standard';
	if (profile === 'allgemein') return DEFAULT_LABEL;
	return DEFAULT_LABEL;
}

/**
 * Issue #173 — Liefert den aktiv ausgewaehlten Preset-Template-Key fuer die
 * PresetRow-Liste in `WeatherMetricsTab`. Single Source of Truth: das
 * persistierte `display_config.preset_name` (Issue #206).
 *
 * - String mit Inhalt -> Template-Key (z.B. "skitouren")
 * - Leer / undefined / Non-String -> null (keine PresetRow ist aktiv)
 */
export function getActivePreset(trip: Trip): string | null {
	const key: unknown = trip.display_config?.preset_name;
	return typeof key === 'string' && key.length > 0 ? key : null;
}

export interface ReportSchedule {
	morning?: string;
	evening?: string;
	morning_enabled: boolean;
	evening_enabled: boolean;
	alertOnChanges: boolean;
	enabled: boolean;
}

export function getReportSchedule(trip: Trip): ReportSchedule {
	const rc = trip.report_config;
	if (!rc) return { enabled: false, morning_enabled: false, evening_enabled: false, alertOnChanges: false };
	// Defensive Runtime-Checks: Backend kann Off-Spec-Werte liefern.
	const morningTime: unknown = rc.morning_time;
	const eveningTime: unknown = rc.evening_time;
	return {
		enabled: rc.enabled === true,
		morning_enabled: rc.morning_enabled === true,
		evening_enabled: rc.evening_enabled === true,
		morning: typeof morningTime === 'string' ? morningTime : undefined,
		evening: typeof eveningTime === 'string' ? eveningTime : undefined,
		alertOnChanges: rc.alert_on_changes === true
	};
}

