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
	const norm = (s: WeatherMetricsSnapshot) => ({
		activeMetricKeys: [...s.activeMetricKeys].sort(),
		officialAlertsEnabled: s.officialAlertsEnabled
	});
	if (JSON.stringify(norm(current)) === JSON.stringify(norm(baseline))) return null;
	return buildHubPutPayload(preset, {
		activeMetricKeys: current.activeMetricKeys,
		officialAlertsEnabled: current.officialAlertsEnabled
	});
}
