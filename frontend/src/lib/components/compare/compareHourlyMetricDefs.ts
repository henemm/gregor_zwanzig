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
 * Reine Toggle-Funktion für die Stundenverlauf-Metrikauswahl. Arbeitet direkt
 * auf der uebergebenen (ggf. leeren) Liste -- eine leere Auswahl ist seit
 * Issue #1366 (AC-8) eine bewusste Nutzerwahl und wird NICHT mehr durch die
 * volle Default-Menge ersetzt, bevor der Toggle greift (sonst erzeugt ein
 * Klick aus "nichts" "Vorgabe minus eins" statt "genau die eine Spalte").
 * Geteilt zwischen Hub und Anlege-Seite über CompareHourlyLayoutControls.svelte
 * (Issue #1335 Scheibe 1, Adversary-Fund F002).
 */
export function applyHourlyMetricToggle(
	currentKeys: string[],
	key: string,
	checked: boolean
): string[] {
	const materialized = [...currentKeys];
	if (checked) {
		if (!materialized.includes(key)) materialized.push(key);
	} else {
		const idx = materialized.indexOf(key);
		if (idx >= 0) materialized.splice(idx, 1);
	}
	return materialized;
}

/**
 * Issue #1366 Adversary-Fund F001: EINZIGE Materialisierungs-Stelle fuer
 * "nie eingestellt" (`null`) -> Vorgabemenge. Eine bewusst geleerte Auswahl
 * (`[]`) bleibt unveraendert leer -- nur `null` (Editor-Zustand seit dieser
 * Aenderung, s. CompareWizardState.hourlyMetricKeys) loest die Default-Menge
 * aus. Anzeige (isHourlyMetricActive) UND Umschalt-Handler (s.u.) muessen
 * ZWINGEND dieselbe Funktion nutzen -- vorher wichen beide Stellen in
 * CompareHourlyLayoutControls.svelte voneinander ab (Anzeige materialisierte,
 * der Handler arbeitete auf der rohen Liste), was aus "eine von neun Spalten
 * abwaehlen" faelschlich eine komplette Leerauswahl machte.
 */
export function materializeHourlyMetricKeys(keys: string[] | null): string[] {
	return keys === null ? DEFAULT_HOURLY_METRIC_KEYS : keys;
}

/**
 * Issue #1366 F001: der Umschalt-Handler-Pfad, wie ihn
 * CompareHourlyLayoutControls.svelte tatsaechlich aufruft -- materialisiert
 * zuerst (analog Anzeige), toggelt danach auf der materialisierten Liste.
 * Ohne diesen Umweg ueber die materialisierte Liste erzeugte ein Klick aus
 * "nie eingestellt" (Anzeige zeigt alle 9 an) die leere Liste statt "8 von 9"
 * -- Regression, s. Adversary-Dialog Runde 1, docs/artifacts/
 * fix-1366-leerauswahl-heisst-leer/adversary-dialog.md.
 */
export function applyHourlyMetricToggleFromState(
	currentKeys: string[] | null,
	key: string,
	checked: boolean
): string[] {
	return applyHourlyMetricToggle(materializeHourlyMetricKeys(currentKeys), key, checked);
}

/**
 * Issue #1361 Befund 4/5: filtert reine Merge-Signale (aktuell nur
 * `wind_dir_deg`, `defaultOff: true`) aus einer Liste aktiver Stundenverlauf-
 * Metrik-Keys heraus. Merge-Signale erzeugen NIE eine eigene Mail-Spalte
 * (FRONTEND_TO_HOURLY_METRIC_ID-Kommentar: kein Eintrag in `HOUR_METRICS`,
 * `_should_merge_wind_dir` prueft nur Mitgliedschaft, nicht Position) --
 * eine Listenposition in der Reihenfolge-Ansicht waere fuer sie also eine
 * Falschaussage. Sie bleiben in der bestehenden An/Aus-Auswahl unveraendert
 * sichtbar (keine Regression, s. CompareHourlyLayoutControls.svelte).
 */
export function orderableHourlyMetricKeys(keys: string[]): string[] {
	const mergeOnly = new Set(ALL_HOURLY_METRICS.filter((m) => m.defaultOff).map((m) => m.key));
	return keys.filter((k) => !mergeOnly.has(k));
}

/**
 * Issue #1361 Befund 4: baut die neue vollstaendige `hourlyMetricKeys`-Liste
 * nach einer Ziehgeste in der Reihenfolge-Ansicht. `newOrder` ist die neue
 * Reihenfolge der SORTIERBAREN Teilmenge (s. orderableHourlyMetricKeys) --
 * Merge-only Keys (falls im materialisierten Bestand aktiv) werden
 * unveraendert uebernommen und ans Ende gestellt, da ihre Position fuer den
 * Renderer wirkungslos ist (s. orderableHourlyMetricKeys-Kommentar).
 */
export function applyHourlyReorder(materializedKeys: string[], newOrder: string[]): string[] {
	const orderable = new Set(orderableHourlyMetricKeys(materializedKeys));
	const mergeOnlyActive = materializedKeys.filter((k) => !orderable.has(k));
	return [...newOrder, ...mergeOnlyActive];
}
