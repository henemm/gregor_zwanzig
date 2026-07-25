// Issue #1269 (a): Mount-Kanonisierung (z.B. EditReportConfigSection.svelte /
// VersandTab.svelte schreiben beim Mounten Zeiten HH:MM -> HH:MM:SS und
// materialisieren fehlende Default-Felder) darf NICHT als Nutzeränderung
// gezählt werden. Geteilter Baustein fuer Trip UND Ortsvergleich (CLAUDE.md
// Trip/Compare-Teilungs-Invariante) — statt in jeder Flaeche eigene
// "geaendert?"-Logik zu bauen.
//
// Prinzip: nur Felder, die in BEIDEN Seiten vorhanden sind, werden
// (nach Normalisierung) verglichen. Neu materialisierte Default-Felder
// (nur in `current`, nicht in `baseline`) zaehlen NICHT als Aenderung — genau
// das ist die Mount-Kanonisierung. Ein Feld, das in `baseline` vorhanden war
// und in `current` fehlt, wird konservativ als Aenderung gewertet
// (Robustheits-Invariante: im Zweifel "dirty", s. Spec).
//
// Issue #1361/#1372 S1b, Adversary Runde 3/4: ein Feld, das ein Trip NIE
// gesetzt hat (z.B. `day_window_start_hour`), existiert im geladenen
// `report_config` gar nicht — waehlt der Nutzer zum ersten Mal einen Wert,
// saehe eine Vereinigungs-basierte Pruefung hier "veraendert". Ein Versuch,
// das ueber diese allgemeine Funktion zu loesen (Iteration ueber die
// Vereinigung beider Schluesselmengen), wurde WIEDER VERWORFEN (Runde 4,
// Tech-Lead-Entscheidung 2026-07-25): der skip-Zweig von
// `scheduleAutoSave()` ruft bei verweigerter Nutzergeste
// `saveController.setDirty()` -- das erzeugte ein falsches "Nicht
// gespeichert" beim bloszen Oeffnen JEDES Bestandstrips (Mount-Kanonisierung
// meldet nach der Vereinigungs-Regel faelschlich "geaendert"). Der
// tragfaehige Weg fuer neue, zunaechst leere Felder ist der AUSDRUECKLICHE
// Pfad: der Aufrufer setzt `userTouched`/loest `scheduleAutoSave()` direkt
// aus der echten DOM-Geste aus (Muster: die SMS-Schwellwert-Felder in
// WeatherMetricsTab.svelte) — diese Funktion hier entscheidet dann gar
// nicht mehr mit. Bei einem kuenftigen neuen optionalen Feld: dem
// ausdruecklichen Pfad folgen, NICHT diese Funktion erneut auf Vereinigung
// umstellen.
//
// Wiederverwendet `toHHMMSS` statt Zeitformat-Logik zu duplizieren.

import { toHHMMSS } from '$lib/utils/time';
import type { ReportConfig } from '$lib/types';

function normalizeValue(v: unknown): unknown {
	if (typeof v === 'string') return toHHMMSS(v) ?? v;
	if (Array.isArray(v)) return v.map(normalizeValue);
	return v;
}

function valuesEqual(a: unknown, b: unknown): boolean {
	const na = normalizeValue(a);
	const nb = normalizeValue(b);
	if (Array.isArray(na) && Array.isArray(nb)) {
		return na.length === nb.length && na.every((x, i) => valuesEqual(x, nb[i]));
	}
	return na === nb;
}

/**
 * Entscheidet, ob sich eine ReportConfig gegenüber der Baseline WIRKLICH
 * (nutzerseitig) geändert hat. Reine Funktion, keine Seiteneffekte.
 */
export function reportConfigChangedByUser(
	baseline: ReportConfig | undefined,
	current: ReportConfig | undefined
): boolean {
	if (!baseline && !current) return false;
	if (!baseline || !current) return true;
	const baselineRecord = baseline as Record<string, unknown>;
	const currentRecord = current as Record<string, unknown>;
	for (const key of Object.keys(baselineRecord)) {
		if (baselineRecord[key] === undefined) continue;
		if (!(key in currentRecord)) return true;
		if (!valuesEqual(baselineRecord[key], currentRecord[key])) return true;
	}
	return false;
}
