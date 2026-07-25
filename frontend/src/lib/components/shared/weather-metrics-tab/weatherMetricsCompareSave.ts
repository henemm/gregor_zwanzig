// Issue #1311, Scheibe C1 von Epic #1301 — Vergleich-Save-Zweig fuer den
// geteilten Wetter-Metriken-Tab: schlankes an/aus, kein Zwei-PUT-Trip-Muster.
//
// Spec: docs/specs/modules/compare_weather_metrics_tab.md
//   (Implementation Details Abschnitt 2, AC-2, AC-4)
//
// Kein Browser-/SvelteKit-Import — lauffaehig unter node --experimental-strip-types.

import type { ComparePreset } from '../../../types.ts';
import { buildHubPutPayload } from '../../compare/compareHubWizardBridge.ts';
import { rehydrateActiveMetrics } from '../../compare/compareEditorLoad.ts';
import { COMPARE_METRIC_KEYS } from '../corridor-editor/corridorEditorState.ts';

// Issue #1361/#1372 S1b — Trip-Default (day_window.py DAY_WINDOW_START_HOUR/
// _END_HOUR), geteilt zwischen Hydration und Neuanlage.
const DEFAULT_DAY_WINDOW_START_HOUR = 4;
const DEFAULT_DAY_WINDOW_END_HOUR = 19;

/** Tagesfenster-Hydration aus dem Preset — undefined/null (Alt-Preset) fällt
 * auf denselben Default (4/19) zurück wie der Renderer
 * (day_window.resolve_configured_window()), AC-4. */
export function hydrateDayWindowFromPreset(preset: ComparePreset): {
	dayWindowStartHour: number;
	dayWindowEndHour: number;
} {
	return {
		dayWindowStartHour: preset.day_window_start_hour ?? DEFAULT_DAY_WINDOW_START_HOUR,
		dayWindowEndHour: preset.day_window_end_hour ?? DEFAULT_DAY_WINDOW_END_HOUR
	};
}

/**
 * Erst-Oeffnungs-Hydration fuer den Vergleichs-Zweig: ein zuvor NIE
 * gespeichertes `active_metrics`-Feld (Legacy, AC-4) zeigt sich im Tab als
 * "alle Metriken aktiv" (deckt sich mit `resolve_enabled_metrics(None)` im
 * Renderpfad, der ohne Filter ALLE Metriken zeigt) — ohne das direkt zu
 * schreiben. Ein explizit gespeichertes (auch leeres) Array wird 1:1
 * uebernommen (#1191-Semantik, kein Legacy-Fallback fuer bewusste Leerauswahl).
 */
export function hydrateWeatherMetricsFromPreset(preset: ComparePreset): string[] {
	const displayConfig = (preset.display_config as Record<string, unknown>) ?? {};
	const rehydrated = rehydrateActiveMetrics(displayConfig.active_metrics as string[] | undefined);
	return rehydrated ? rehydrated.activeMetricKeys : [...COMPARE_METRIC_KEYS];
}

/**
 * D2-Fix-Loop 2 (AC-6, Staging-Befund BROKEN): der Amtliche-Warnungen-Toggle
 * ist fuer bestehende Vergleiche nur noch ueber diesen Hub-Tab erreichbar
 * (der Alarm-Tab-Toggle entfaellt mit D2) — der Snapshot traegt ihn deshalb
 * neben `activeMetricKeys`, damit ein reiner Toggle-Klick (ohne Metrik-
 * Aenderung) ebenfalls als dirty erkannt wird.
 * Spec: d2_1301_official_alerts_single_control.md § Punkt 6, AC-6.
 */
export interface WeatherMetricsSnapshot {
	activeMetricKeys: string[];
	officialAlertsEnabled: boolean;
	// Issue #1361/#1372 S1b: Tagesfenster — Teil desselben Snapshots, damit ein
	// reiner Von/Bis-Wechsel (ohne Metrik-/Toggle-Aenderung) ebenfalls als dirty
	// erkannt wird (analog officialAlertsEnabled oben).
	dayWindowStartHour: number;
	dayWindowEndHour: number;
}

/**
 * Diff-Guard analog `flushPendingVersandSave` (compareHubWizardBridge.ts):
 * liefert `null`, wenn sich weder Metrik-Auswahl noch Amtliche-Warnungen-
 * Toggle seit dem letzten persistierten Stand veraendert haben (kein
 * Schreiben ohne Nutzer-Geste, AC-4) — sonst den fertigen PUT-Payload ueber
 * den bestehenden RMW-Pfad (`buildHubPutPayload`).
 */
export function flushPendingWeatherMetricsSave(
	preset: ComparePreset,
	current: WeatherMetricsSnapshot,
	before: WeatherMetricsSnapshot | null
): { url: string; body: ComparePreset } | null {
	const baseline = before ?? current;
	// Issue #1359 Scheibe 1: KEIN `.sort()` mehr. Die Listenposition IST die
	// Metrik-Reihenfolge (kein eigenes order-Feld) — sortiert verglichen galten
	// zwei Listen mit derselben MENGE in anderer Reihenfolge als identisch,
	// `flushPendingWeatherMetricsSave` lieferte `null` und eine reine
	// Umsortierung wurde nie gespeichert. Die AC-4-Zusage "kein Schreiben ohne
	// Nutzer-Geste" bleibt gewahrt: der Guard entscheidet nur, OB ein
	// Unterschied vorliegt — ausgeloest wird weiterhin nur von einer echten
	// Geste (Checkbox-Toggle bzw. Drag-Ende).
	const norm = (s: WeatherMetricsSnapshot) => ({
		activeMetricKeys: [...s.activeMetricKeys],
		officialAlertsEnabled: s.officialAlertsEnabled,
		dayWindowStartHour: s.dayWindowStartHour,
		dayWindowEndHour: s.dayWindowEndHour
	});
	if (JSON.stringify(norm(current)) === JSON.stringify(norm(baseline))) return null;
	return buildHubPutPayload(preset, {
		activeMetricKeys: current.activeMetricKeys,
		officialAlertsEnabled: current.officialAlertsEnabled,
		dayWindowStartHour: current.dayWindowStartHour,
		dayWindowEndHour: current.dayWindowEndHour
	});
}
