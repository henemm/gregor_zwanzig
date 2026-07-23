// Issue #1106 — Katalog der waehlbaren Stundenverlauf-Metriken (Compare-Mail).
// Spec: docs/specs/modules/issue_1106_hourly_metrics_config.md
//
// IDs muessen 1:1 mit den Keys aus FRONTEND_TO_HOURLY_METRIC_ID in
// src/output/renderers/compare_hourly_metric_ids.py uebereinstimmen -- sonst
// verwirft der Resolver die Auswahl (unbekannte IDs -> None -> Default "alle").
// Eigenstaendiges Vokabular, kein Reuse von compareMetricDefs.ts (Rohwerte pro
// Stunde != Aggregate der Uebersichtstabelle).

export interface HourlyMetricDef {
	key: string;
	label: string;
	// Issue #1335 Scheibe 1, Adversary-Fund F002: reines Merge-Signal (z.B.
	// Windrichtung) -- wird beim "leere Auswahl -> volle Default-Menge
	// materialisieren"-Schritt (CompareHourlyLayoutControls.svelte) NICHT
	// automatisch mit aufgenommen. Ohne dieses Flag würde ein Bestandsnutzer,
	// der nie "Windrichtung" angehakt hat, durch bloßes Toggeln einer ANDEREN
	// Metrik ungewollt den serverseitigen Windrichtungs-Merge aktivieren
	// (_should_merge_wind_dir in compare_html.py). Nur explizites eigenes
	// Anhaken aktiviert die Metrik -- der Toggle bleibt sichtbar (AC-8).
	defaultOff?: boolean;
}

// Anzeige-Reihenfolge der Checkboxen im Editor UND (seit Issue #1335 Scheibe 1)
// die Auswahl-Reihenfolge der Spalten in der Mail -- der Renderer
// (_visible_hour_metrics in compare_html.py) folgt jetzt der Reihenfolge der
// Nutzer-Auswahl statt einer fest verdrahteten HOUR_METRICS-Deklarations-
// reihenfolge.
export const ALL_HOURLY_METRICS: HourlyMetricDef[] = [
	{ key: 'temp_c', label: 'Temperatur' },
	{ key: 'wind_chill_c', label: 'Gefühlte Temperatur' },
	{ key: 'wind_kmh', label: 'Wind' },
	{ key: 'gust_kmh', label: 'Böen' },
	{ key: 'precip_mm', label: 'Niederschlag' },
	{ key: 'uv_index', label: 'UV-Index' },
	{ key: 'thunder_level', label: 'Gewitter-Risiko' },
	{ key: 'pop_pct', label: 'Regenwahrscheinlichkeit' },
	{ key: 'visibility_m', label: 'Sicht' },
	// Issue #1335 Scheibe 1: reines Merge-Signal (keine eigene Mail-Spalte) --
	// wird bei Auswahl zusammen mit 'wind_kmh' als Kompass-Text in die
	// Wind-Zelle gemergt (analog Trip-Muster should_merge_wind_dir).
	// defaultOff: siehe HourlyMetricDef-Kommentar -- kein stiller Auto-Einschluss.
	{ key: 'wind_dir_deg', label: 'Windrichtung', defaultOff: true }
];

// Die beim "leere Auswahl = alle sichtbar"-Default materialisierte Menge --
// schließt defaultOff-Einträge (reine Merge-Signale) aus (Issue #1335 F002).
export const DEFAULT_HOURLY_METRIC_KEYS: string[] = ALL_HOURLY_METRICS.filter(
	(m) => !m.defaultOff
).map((m) => m.key);

/**
 * Reine Toggle-Funktion für die Stundenverlauf-Metrikauswahl. Materialisiert
 * bei leerer Auswahl NUR die Default-Menge (nicht den vollen Katalog inkl.
 * defaultOff-Einträgen) und wendet dann den Toggle an. Geteilt zwischen Hub
 * und Anlege-Seite über CompareHourlyLayoutControls.svelte (Issue #1335
 * Scheibe 1, Adversary-Fund F002).
 */
export function applyHourlyMetricToggle(
	currentKeys: string[],
	key: string,
	checked: boolean
): string[] {
	const materialized =
		currentKeys.length === 0 ? [...DEFAULT_HOURLY_METRIC_KEYS] : [...currentKeys];
	if (checked) {
		if (!materialized.includes(key)) materialized.push(key);
	} else {
		const idx = materialized.indexOf(key);
		if (idx >= 0) materialized.splice(idx, 1);
	}
	return materialized;
}
