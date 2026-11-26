// Hydrations-Helfer des Ortsvergleichs für Wetter-Metriken, Tagesfenster und
// Stundenverlauf (Issue #1311 C1, #1299 C2, #2276 S4). Gespeichert wird seit
// #2794/#3020 über den WetterTab- und den Zustellungs-Speicherer; der frühere
// kombinierte Wetter-Metriken/Layout-Speicherweg samt Snapshot-, Nutzlast- und
// Rollback-Funktionen ist mit #3389 entfernt.
//
// Kein Browser-/SvelteKit-Import — lauffaehig unter node --experimental-strip-types.

import type { ComparePreset } from '../../../types.ts';
import { rehydrateActiveMetrics } from '../../compare/compareEditorLoad.ts';
// Issue #1373 (S2 Scheibe B): Übersetzungsquelle für das Speicherformat der
// Metrik-Auswahl (Größe + Auswertung) — die geladene Katalogantwort.
import { registeredCompareMetricCatalog, type CompareSelectionEntry } from './compareMetricSelection.ts';

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
 *
 * Issue #1373 (S2 Scheibe B, Fix-Runde 1): `catalog` ist die geladene Antwort
 * von GET /api/compare/metrics — nur damit kann eine im neuen Format
 * (Größe + Auswertung) gespeicherte Auswahl auf Auswahl-Schlüssel
 * zurückgeführt werden. Der Aufrufer MUSS die Antwort abwarten, bevor er
 * hydriert und den Dirty-Check-Grundzustand aufnimmt (sonst Scheindiff und
 * Rücksetzen auf die Rohform, Adversary-Befund F001). Default = der bereits
 * registrierte Katalog, damit bestehende Aufrufer unverändert funktionieren.
 * #3047 J1/#3061 (AC-13): fehlendes `active_metrics` -> `null` („nie eingestellt"), nie die Vorgabeliste.
 */
export function hydrateWeatherMetricsFromPreset(
	preset: ComparePreset,
	catalog: CompareSelectionEntry[] = registeredCompareMetricCatalog()
): string[] | null {
	const displayConfig = (preset.display_config as Record<string, unknown>) ?? {};
	const rehydrated = rehydrateActiveMetrics(displayConfig.active_metrics, catalog);
	return rehydrated ? rehydrated.activeMetricKeys : null;
}

// Issue #3298: die Lese-Naht der Kanal-Auswahl (`hydrateChannelActiveMetricsFromPreset`)
// ist entfallen — das Backend liefert den Altschluessel nicht mehr (ADR-0124).

/** Das persistenzrelevante Layout-Feld (Stundenverlauf). Issue #1299/#1291/#1287
 * (Scheibe C2 von Epic #1301). Issue #3298: Stundenverlauf-/Ausblick-Auswahl und
 * Ausblick-Schalter entfallen (ADR-0124, `placements`). */
interface LayoutSnapshot {
	hourlyEnabled: boolean;
}

/**
 * Issue #1299/C2: Erst-Oeffnungs-Hydration fuer den Hub-Layout-Teil, analog
 * `hydrateVersandFieldsFromPreset` — liest nur noch `preset.hourly_enabled`
 * (#3298: keine Altfelder).
 */
export function hydrateLayoutFieldsFromPreset(preset: ComparePreset): LayoutSnapshot {
	return { hourlyEnabled: preset.hourly_enabled ?? true };
}

/** AC-3-Gate: der Hub nimmt den Grundzustand erst auf, wenn BEIDE
 *  Katalog-Ladevorgaenge (Wetter-Metriken-Auswahl, Stundenverlauf/Ausblick)
 *  abgeschlossen sind — sonst erschiene die spaeter eintreffende zweite
 *  Hydration als Nutzeraenderung (Kontext-Dokument Abschnitt 1.2/4.2). */
export function wetterMetrikenHydrationAbgeschlossen(p: {
	wetterMetrikenHydrated: boolean;
	layoutHydrated: boolean;
}): boolean {
	return p.wetterMetrikenHydrated && p.layoutHydrated;
}
