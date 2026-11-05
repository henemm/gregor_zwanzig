// Issue #180 — Alert-Konfigurator: Schwellwert-Tabelle Helper.
//
// Spec: docs/specs/modules/issue_180_alert_metric_table.md
//
// Pure-Function Helpers, getrennt von der Svelte-Komponente, damit sie
// unter `node --test` ohne Svelte-Compiler laufen koennen.
//
// Inhalt:
//  - METRIC_DEFAULTS:    Default-Schwellwerte pro AlertMetric (Alarm-Vorschau).
//  - ALERTABLE_METRICS:  alarmfaehige Metriken in Anzeige-Reihenfolge.
//  - levelToThreshold(), thresholdTitle(): Schwellen-Text der Stufen-Tabelle.
//
// Issue #1895 S4: die Umrechner des toten Regel-Editors (Row-State, Modus
// „Absolut/Delta/Beides", Preset-Migration, Katalog-Mapping) sind entfernt
// (ADR-0043); `alert_rules` selbst und seine Leser gehen an #2793.

import type { AlertMetric, SensLevel } from '../../types.ts';
import { tr } from '../../i18n/index.ts';
// Fix #1435 Etappe E4: einzige Quelle der Preset-Schwellwerte, erzeugt von
// scripts/generate_alert_preset_table.py aus src/services/alert_preset.py.
import rawPresetThresholds from '../../generated/alertPresetThresholds.generated.json' with { type: 'json' };

export const METRIC_DEFAULTS: Record<AlertMetric, number> = {
	wind_gust: 50,
	precipitation_sum: 10,
	thunder_level: 1,
	snow_line: 2000,
	temperature_min: -5,
	temperature_max: 35,
	temperature_change: 10,
	wind_change: 20,
	precipitation_change: 5,
	// Issue #846: 4 neue Metriken (Epic #813 Slice 3) — Fallback-Defaults
	fresh_snow: 8,
	cape: 600,
	visibility: 1000,
	humidity: 15,
	// Issue #946: Nullgradgrenze (freezing_level).
	freezing_level: 200,
	// Issue #1468: Beginn-Verschiebung in Stunden (Fallback-Defaults).
	thunder_onset: 1,
	precipitation_heavy_onset: 1,
};

// Issue #846 / Fix #1435 Etappe E4: Preset-Schwellwert-Tabelle wird aus der
// generierten Datei abgeleitet (Quelle: `_PRESET_TABLE`,
// `src/services/alert_preset.py` -- eingecheckte Kopie
// `frontend/src/lib/generated/alertPresetThresholds.generated.json`,
// erzeugt von `scripts/generate_alert_preset_table.py`). Nicht mehr als
// Literal pflegen -- Werte aendern heisst: Python-Quelle aendern, Skript
// erneut laufen lassen. Nur noch intern fuer levelToThreshold() (#1895 S4).
type PresetName = 'deaktiviert' | 'entspannt' | 'standard' | 'sensibel';

type GeneratedPresetEntry = {
	kind: 'delta' | 'threshold_crossing';
	entspannt: number;
	standard: number;
	sensibel: number;
};

const _RAW_PRESETS = rawPresetThresholds as Record<string, GeneratedPresetEntry>;

// Die generierte Quelle fuehrt nur die 12 tatsaechlich alarmfaehigen
// Backend-Groessen (kein snow_line, kein humidity -- beide seit
// ADR-0019/#889 tot bzw. abgeschafft) -- der Typ verlangt darum nicht mehr
// alle 14 AlertMetric-Schluessel. `levelToThreshold()` behandelt einen
// fehlenden Schluessel bereits korrekt (gibt null zurueck).
const METRIC_PRESETS: Record<
	PresetName,
	Partial<Record<AlertMetric, number>> | null
> = {
	deaktiviert: null,
	entspannt: Object.fromEntries(
		Object.entries(_RAW_PRESETS).map(([metric, entry]) => [metric, entry.entspannt]),
	) as Partial<Record<AlertMetric, number>>,
	standard: Object.fromEntries(
		Object.entries(_RAW_PRESETS).map(([metric, entry]) => [metric, entry.standard]),
	) as Partial<Record<AlertMetric, number>>,
	sensibel: Object.fromEntries(
		Object.entries(_RAW_PRESETS).map(([metric, entry]) => [metric, entry.sensibel]),
	) as Partial<Record<AlertMetric, number>>,
};

// ─── Issue #864/#859: Per-Metrik-Alert-Levels ─────────────────────────────

export type { SensLevel }; // re-export from types.ts

/** Alertable Metriken in Anzeige-Reihenfolge.
 * Issue #959: snow_line ist keine separat wählbare Alert-Metrik mehr — die
 * Nullgradgrenze wird ausschließlich über freezing_level konfiguriert. */
export const ALERTABLE_METRICS: readonly AlertMetric[] = [
	'wind_gust',
	'precipitation_sum',
	'thunder_level',
	'temperature_min',
	'temperature_max',
	'temperature_change',
	'wind_change',
	'precipitation_change',
	'fresh_snow',
	'cape',
	'visibility',
	'humidity',
	'freezing_level',
	// Issue #1468: Beginn-Verschiebung von Gewitter und Starkregen.
	'thunder_onset',
	'precipitation_heavy_onset',
];

/** Metriken die THRESHOLD_CROSSING verwenden (absoluter Schwellwert, nicht Delta).
 * Fix #1435 Etappe E4: aus dem `kind`-Feld der generierten Datei abgeleitet
 * statt als zweite Handkopie gepflegt. */
export const THRESHOLD_CROSSING_METRICS: ReadonlySet<AlertMetric> = new Set(
	Object.entries(_RAW_PRESETS)
		.filter(([, entry]) => entry.kind === 'threshold_crossing')
		.map(([metric]) => metric as AlertMetric),
);

const _METRIC_UNITS: Record<AlertMetric, string> = {
	wind_gust: 'km/h',
	precipitation_sum: 'mm',
	thunder_level: '',
	snow_line: 'm',
	temperature_min: '°C',
	temperature_max: '°C',
	temperature_change: '°C',
	wind_change: 'km/h',
	precipitation_change: 'mm',
	fresh_snow: 'cm',
	cape: 'J/kg',
	visibility: 'm',
	humidity: '%',
	freezing_level: 'm',
	// Issue #1468: die Schwelle ist eine Verschiebung, gemessen in Stunden.
	thunder_onset: 'h',
	precipitation_heavy_onset: 'h',
};

/**
 * Gibt den Schwellwert-Text für Metrik+Stufe zurück.
 * Delta-Metriken: "Δ ≥ X unit"; THRESHOLD_CROSSING: "< X unit"; off: null.
 */
export function levelToThreshold(metric: AlertMetric, level: SensLevel): string | null {
	if (level === 'off') return null;
	const presetData = METRIC_PRESETS[level as PresetName];
	if (!presetData) return null;
	const value = presetData[metric];
	if (value === undefined) return null;
	const unit = _METRIC_UNITS[metric] ?? '';
	if (THRESHOLD_CROSSING_METRICS.has(metric)) {
		return unit ? `< ${value} ${unit}` : `< ${value}`;
	}
	// Issue #1592 Scheibe C3 (AC-9): die CAPE-Delta-Schwelle wird seit C3
	// modell-/gebietsabhängig umgerechnet (Backend:
	// `app.model_registry.cape_delta_threshold_jkg`) -- die Zahl bleibt aber
	// eine ÄNDERUNGSschwelle ("Δ ≥"), kein absoluter Grenzwert (das würde sie
	// optisch mit THRESHOLD_CROSSING-Metriken wie Sicht verwechselbar machen).
	// Die Tilde markiert die Näherung; die Erklärung sitzt im `title`-Attribut
	// der Zelle (s. `thresholdTitle()`), nicht im knappen Zellentext selbst.
	// Nur CAPE, alle anderen Metriken unverändert.
	if (metric === 'cape') {
		return unit ? `Δ ≥ ~${value} ${unit}` : `Δ ≥ ~${value}`;
	}
	return unit ? `Δ ≥ ${value} ${unit}` : `Δ ≥ ${value}`;
}

/**
 * Erklärender `title`-Hinweis für die Schwellenzelle -- aktuell nur für CAPE
 * (Issue #1592 Scheibe C3, AC-9): die angezeigte Zahl ist ein Richtwert, der
 * je Wettermodell und Gebiet umgerechnet wird. Alle anderen Metriken haben
 * KEIN `title` (Regressions-Invariante, s. AlertMetricLevelRow.svelte).
 */
export function thresholdTitle(metric: AlertMetric): string | undefined {
	if (metric === 'cape') {
		return tr('alarme.richtwert'); // #2656: aktuelle Sprache; Aufrufer im Markup lesen $locale
	}
	return undefined;
}
