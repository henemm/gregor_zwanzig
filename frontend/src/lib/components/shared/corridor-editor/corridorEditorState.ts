// corridorEditorState.ts — Issue #1231, Slice 3: reine Logik fuer
// CorridorEditor context="route" (Trip-Editor · Alerts-Tab-Ersatz).
//
// Spec: docs/specs/modules/issue_1231_korridor_editor.md
// Metrik-Pool route = die 6 AlertableMetrics (internal/model/trip.go).
// Labels/Einheiten/Skalen aus der JSX-Referenz (CORRIDOR_SEED/POOL.route),
// verbindlich per Spec § "CorridorEditor / CorridorEditorMobile". Zwei
// Metriken haben dort kein Route-Pendant (temperature_max, snow_line) — s.
// Deviations im Rueckmeldungs-Text des Slice-3-Auftrags.
//
// AC-3: confidence_pct (selectable=false) darf hier nie auftauchen — trivial
// erfuellt, da ROUTE_METRIC_DEFS eine fest verdrahtete 6er-Liste ist.

import type { Corridor, SensLevel, WeatherConfigMetric } from '$lib/types';

export interface RouteMetricDef {
	metric: string;
	label: string;
	unit: string;
	scale: [number, number];
	step: number;
	note?: string;
	defaultMin: number | null;
	defaultMax: number | null;
}

// Reihenfolge = Anzeige-Reihenfolge (deterministisch, C1: nur Anzeige, kein Rang).
export const ROUTE_METRIC_DEFS: RouteMetricDef[] = [
	{ metric: 'wind_gust', label: 'Böen', unit: 'km/h', scale: [0, 120], step: 5, note: 'Grat-kritisch', defaultMin: null, defaultMax: 70 },
	{ metric: 'precipitation_sum', label: 'Niederschlag', unit: 'mm/h', scale: [0, 20], step: 1, note: 'Nässe / Rutschgefahr', defaultMin: null, defaultMax: 5 },
	{ metric: 'temperature_min', label: 'Temperatur Min', unit: '°C', scale: [-20, 20], step: 1, note: 'Frost-Grenze', defaultMin: -5, defaultMax: null },
	{ metric: 'temperature_max', label: 'Temperatur Max', unit: '°C', scale: [-20, 30], step: 1, note: 'Hitze-Grenze', defaultMin: null, defaultMax: 28 },
	{ metric: 'thunder_level', label: 'Gewitter', unit: '%', scale: [0, 100], step: 5, note: 'Abbruch bei Gewitter', defaultMin: null, defaultMax: 40 },
	{ metric: 'snow_line', label: 'Schneefallgrenze', unit: 'm', scale: [500, 3000], step: 100, note: 'Schnee statt Regen', defaultMin: 1500, defaultMax: null },
];

const ROUTE_METRIC_DEF_BY_ID = new Map(ROUTE_METRIC_DEFS.map((m) => [m.metric, m]));

export const ROUTE_CTX_DEFAULTS = { notify: true, mark: false };

export interface CorridorRowState {
	metric: string;
	label: string;
	unit: string;
	scale: [number, number];
	step: number;
	note?: string;
	min: number | null;
	max: number | null;
	notify: boolean;
	mark: boolean;
	// Slice 4 (vergleich): 'ordinal' = 3-Stufen-Band (Gewitter) statt Zahlen-Slider.
	// Fehlt (route-Zeilen) -> wird wie 'range' behandelt.
	kind?: 'range' | 'ordinal';
	ordinalLabels?: string[];
	// Slice 4 Fakten-Korrektur (Team-Lead): nur die 10 Compare-Alarm-Keys haben
	// eine notify-Bruecke zum Δ-Wächter (compare_alert.py). Die uebrigen 4
	// reinen Vergleichs-Metriken (snow_depth_cm, sunny_hours_h, cloud_avg_pct,
	// uv_index_max) sind "nur Markieren" — notify bleibt fuer sie wirkungslos.
	// Fehlt (route-Zeilen) -> als capable (true) behandelt.
	alarmCapable?: boolean;
}

// Issue #1311 (C1, #1293-Wurzelfix): Namensraum-Bruecke Katalog-Metrik-ID
// (GET /api/metrics, z.B. "gust","precipitation","temperature","thunder",
// "snowfall_limit") -> ROUTE_METRIC_DEFS.metric (AlertMetric-Werte, z.B.
// "wind_gust"). NICHT identisch mit alertMetricTable.ts::CATALOG_TO_ALERT_METRICS
// (dessen Ausgabe ist auf die 13 Delta-Alarm-Metriken gefiltert und fuehrt
// "snow_line" seit #959 nicht mehr) — eine eigene, kleine Mapping-Konstante
// verhindert, dass der Korridor "Schneefallgrenze" nach diesem Fix nie mehr
// im Pool erscheinen kann.
const ROUTE_CORRIDOR_CATALOG_IDS: Record<string, string[]> = {
	gust: ['wind_gust'],
	precipitation: ['precipitation_sum'],
	temperature: ['temperature_min', 'temperature_max'],
	thunder: ['thunder_level'],
	snowfall_limit: ['snow_line'],
};

/**
 * Baut Zeilen aus trip.corridors[] (route-Namensraum) + verbleibenden Pool fuer "+ Metrik".
 *
 * Issue #1311 (C1, #1293-Wurzelfix): `activeCatalogMetrics` (optional) filtert
 * `poolLeft` auf die Metriken, die im geteilten Wetter-Metriken-Tab aktiv
 * sind — ohne Parameter bleibt das Alt-Verhalten (alle 6) fuer etwaige
 * weitere Aufrufer erhalten. `rows` (bereits als Korridor gespeicherte
 * Zeilen) werden NIE gefiltert (AC-9: kein stiller Datenverlust bei
 * De-Selektion einer bereits konfigurierten Metrik).
 */
export function buildRoutePool(
	corridors: Corridor[],
	activeCatalogMetrics?: WeatherConfigMetric[]
): {
	rows: CorridorRowState[];
	poolLeft: RouteMetricDef[];
} {
	const present = new Map(corridors.map((c) => [c.metric, c]));
	const allowed = activeCatalogMetrics
		? new Set(
				activeCatalogMetrics
					.filter((m) => m.enabled)
					.flatMap((m) => ROUTE_CORRIDOR_CATALOG_IDS[m.metric_id] ?? [])
			)
		: null;
	const rows: CorridorRowState[] = [];
	const poolLeft: RouteMetricDef[] = [];
	for (const def of ROUTE_METRIC_DEFS) {
		const c = present.get(def.metric);
		if (c) {
			rows.push({
				metric: def.metric, label: def.label, unit: def.unit, scale: def.scale, step: def.step, note: def.note,
				min: c.range[0], max: c.range[1], notify: c.notify, mark: c.mark,
			});
		} else if (allowed === null || allowed.has(def.metric)) {
			poolLeft.push(def);
		}
	}
	return { rows, poolLeft };
}

/** Fuegt eine Zeile aus dem Pool hinzu, mit Kontext-Defaults fuer notify/mark. */
export function addRow(
	rows: CorridorRowState[],
	poolLeft: RouteMetricDef[],
	metric: string,
	ctxDefaults: { notify: boolean; mark: boolean } = ROUTE_CTX_DEFAULTS
): { rows: CorridorRowState[]; poolLeft: RouteMetricDef[] } {
	const def = ROUTE_METRIC_DEF_BY_ID.get(metric);
	if (!def) return { rows, poolLeft };
	const newRow: CorridorRowState = {
		metric: def.metric, label: def.label, unit: def.unit, scale: def.scale, step: def.step, note: def.note,
		min: def.defaultMin, max: def.defaultMax, notify: ctxDefaults.notify, mark: ctxDefaults.mark,
	};
	return { rows: [...rows, newRow], poolLeft: poolLeft.filter((m) => m.metric !== metric) };
}

export function removeRow(rows: CorridorRowState[], metric: string): CorridorRowState[] {
	return rows.filter((r) => r.metric !== metric);
}

export function patchRow(
	rows: CorridorRowState[],
	metric: string,
	patch: Partial<Pick<CorridorRowState, 'min' | 'max' | 'notify' | 'mark'>>
): CorridorRowState[] {
	return rows.map((r) => (r.metric === metric ? { ...r, ...patch } : r));
}

/**
 * AC-12: mind. eine Grenze ist Pflicht — beidseitig offen blockt das
 * Speichern. Fehlermeldungen nennen das deutsche Anzeige-Label (row.label,
 * z.B. "Böen"), nicht den internen Bezeichner (Fresh-Eyes-Fund: Lokalisierung).
 */
export function validateCorridorRows(rows: CorridorRowState[]): { valid: boolean; errors: string[] } {
	const errors = rows.filter((r) => r.min == null && r.max == null).map((r) => r.label);
	return { valid: errors.length === 0, errors };
}

/**
 * Sync-Bruecke notify <-> metric_alert_levels (PO-A, AC-10): `notify` ist nur
 * ein an/aus-Schalter auf den bestehenden Δ-Wächter. `false` setzt "off";
 * `true` restauriert die zuletzt bekannte Stufe aus den ORIGINAL geladenen
 * Levels (nicht aus einem laufenden Zwischenstand), Default "standard".
 */
export function deriveMetricAlertLevel(
	notify: boolean,
	metric: string,
	originalLevels: Record<string, SensLevel | undefined>
): SensLevel {
	if (!notify) return 'off';
	const prev = originalLevels[metric];
	return prev && prev !== 'off' ? prev : 'standard';
}

/**
 * Read-Modify-Write-Payload fuer den Save: corridors[] + gemergte
 * metric_alert_levels. `removedMetrics` (F002-Fix, Adversary-Finding): Zeilen,
 * die in dieser Session per "✕ entfernen" entfernt wurden — deren Level muss
 * explizit auf "off" gesetzt werden (Zeile entfernen = Warnung aus), sonst
 * warnt der Δ-Wächter unsichtbar mit der alten Stufe weiter. Ist die Metrik
 * inzwischen wieder als Zeile vorhanden (erneut hinzugefuegt), gewinnt die
 * normale Ableitung ueber `rows`.
 */
export function buildCorridorSavePayload(
	rows: CorridorRowState[],
	originalLevels: Record<string, SensLevel | undefined> | undefined,
	removedMetrics: string[] = []
): { corridors: Corridor[]; metric_alert_levels: Record<string, SensLevel> } {
	const merged: Record<string, SensLevel> = { ...(originalLevels as Record<string, SensLevel>) };
	for (const m of removedMetrics) {
		if (!rows.some((r) => r.metric === m)) merged[m] = 'off';
	}
	for (const r of rows) {
		merged[r.metric] = deriveMetricAlertLevel(r.notify, r.metric, originalLevels ?? {});
	}
	return {
		corridors: rows.map((r) => ({ metric: r.metric, range: [r.min, r.max], notify: r.notify, mark: r.mark })),
		metric_alert_levels: merged,
	};
}

// ════════════════════════════════════════════════════════════════════════
// Issue #1231, Slice 4: CorridorEditor context="vergleich" (Compare-Editor ·
// Idealwerte-Tab-Ersatz, ersetzt Step3Idealwerte.svelte).
//
// Fakten-Korrektur (Team-Lead, nach Erstlieferung): Metrik-Pool vergleich =
// ALLE 14 ALL_METRICS, NICHT nur die 10 alarmfaehigen Compare-Summary-Keys.
// Grund: Die Slice-2-Migration hat ideal_ranges JEDER Metrik zu Corridors
// migriert (nicht nach Alarm-Faehigkeit gefiltert) — ein 10er-Katalog wuerde
// bestehende Corridor-Eintraege (z.B. sunny_hours_h) beim Laden aus rows UND
// poolLeft verlieren und sie beim naechsten Speichern endgueltig loeschen
// (BUG-DATALOSS-Klasse, CLAUDE.md). Nur die notify-Bruecke zum Δ-Wächter
// (compare_alert.py::_SUMMARY_KEY_TO_CATALOG_ID) bleibt auf 10 Metriken
// beschraenkt — die uebrigen 4 sind reine "mark"-Metriken (alarmCapable=false).
// AC-3: confidence_pct ist in ALL_METRICS nie enthalten — trivial erfuellt.
//
// Issue #1350 Teil 3: der Katalog (inzwischen 25 Metriken) kommt nicht mehr
// aus dem geloeschten ALL_METRICS-Import, sondern aus GET /api/compare/metrics
// (compareMetricCatalogLoader.ts::buildCompareMetricDefs) — die
// Funktionen unten nehmen `defs` deshalb als explizites Argument statt einer
// Modul-Konstante. Siehe docs/specs/modules/compare_metric_ssot_final.md.
// ════════════════════════════════════════════════════════════════════════

export interface CompareMetricDef {
	metric: string;
	label: string;
	unit: string;
	scale: [number, number];
	step: number;
	kind: 'range' | 'ordinal';
	ordinalLabels?: string[];
	defaultMin: number | null;
	defaultMax: number | null;
	// notify-Bruecke zum Δ-Wächter existiert nur fuer diese 10 Metriken
	// (compare_alert.py::_SUMMARY_KEY_TO_CATALOG_ID) — die uebrigen 4 sind
	// reine Vergleichs-/Anzeige-Metriken ohne Alarm-Anbindung.
	alarmCapable: boolean;
}

// Issue #1350 Teil 3 (D1 Hybrid): alarmCapable kommt jetzt aus dem Backend-
// Katalog (compare_metric_catalog.py) statt aus einer FE-Liste — die
// ehemalige _COMPARE_ALARM_KEYS-Konstante entfaellt ersatzlos.

export const ORDINAL_ENUM = ['NONE', 'MED', 'HIGH'] as const;

/** Inverse von ORDINAL_ENUM — fuer den Wizard-Prefill (IDEAL_DEFAULTS.thunder_level_max ist ein Enum-String). */
function enumToOrdinal(s: string): number | null {
	const idx = (ORDINAL_ENUM as readonly string[]).indexOf(s);
	return idx >= 0 ? idx : null;
}

// Issue #1350 Teil 3 (D1 Hybrid, Spec Punkt 3): dünne FE-UX-Tabelle bleibt
// bewusst FE-seitig (Praezedenz: Trip/ROUTE_METRIC_DEFS haelt Startwerte
// ebenfalls FE-seitig) — Default-Von/Bis je Metrik beim "+ Metrik
// hinzufuegen": aus IDEAL_DEFAULTS uebernommen, wo vorhanden; Metriken ohne
// Profil-Default (die 4 seit #1191 alarmfaehigen
// temp_min_c/gust_max_kmh/cape_max_jkg/freezing_level_m sowie sunny_hours_h,
// das in KEINEM der 4 Profile einen Default hat) bekommen einen literalen,
// an route/JSX angelehnten Sinnwert. Wird jetzt von
// compareMetricCatalogLoader.ts::buildCompareMetricDefs() gelesen (Import),
// nicht mehr von einer Modul-Konstante COMPARE_METRIC_DEFS.
export const _COMPARE_DEFAULTS: Record<string, { defaultMin: number | null; defaultMax: number | null }> = {
	temp_max_c: { defaultMin: 15, defaultMax: 35 },
	temp_min_c: { defaultMin: -5, defaultMax: null },
	wind_max_kmh: { defaultMin: 0, defaultMax: 50 },
	gust_max_kmh: { defaultMin: null, defaultMax: 70 },
	precip_sum_mm: { defaultMin: 0, defaultMax: 5 },
	thunder_level_max: { defaultMin: null, defaultMax: 0 }, // NONE
	visibility_min_m: { defaultMin: 2000, defaultMax: 10000 },
	snow_new_sum_cm: { defaultMin: 5, defaultMax: 50 },
	cape_max_jkg: { defaultMin: null, defaultMax: 500 },
	freezing_level_m: { defaultMin: 1500, defaultMax: null },
	snow_depth_cm: { defaultMin: 30, defaultMax: 200 }, // WINTERSPORT-Default
	cloud_avg_pct: { defaultMin: 0, defaultMax: 60 }, // WINTERSPORT-Default
	uv_index_max: { defaultMin: 0, defaultMax: 8 }, // SUMMER_TREKKING-Default
	sunny_hours_h: { defaultMin: 4, defaultMax: null }, // kein Profil-Default vorhanden — Sinnwert
};

// Issue #1350 Teil 3 (Spec Punkt 6, weatherMetricsCompareSave.ts): Legacy-
// Default "active_metrics=null -> alle Metriken aktiv" braucht eine
// SYNCHRONE Key-Liste ohne Fetch. Reine Key-Liste (keine Labels/Skalen),
// Reihenfolge = compare_metric_catalog.py::COMPARE_METRIC_CATALOG.
export const COMPARE_METRIC_KEYS: string[] = [
	'snow_depth_cm', 'snow_new_sum_cm', 'sunny_hours_h', 'wind_max_kmh',
	'cloud_avg_pct', 'visibility_min_m', 'precip_sum_mm', 'uv_index_max', 'temp_max_c',
	'thunder_level_max', 'temp_min_c', 'gust_max_kmh', 'cape_max_jkg', 'freezing_level_m',
	'pop_max_pct', 'wind_direction_deg', 'wind_chill_min_c', 'wind_chill_max_c',
	'humidity_avg_pct', 'dewpoint_avg_c', 'snowfall_limit_m', 'precip_type_dominant',
	'cloud_low_avg_pct', 'cloud_mid_avg_pct', 'cloud_high_avg_pct', 'pressure_avg_hpa',
];

// Issue #1350 Teil 3 (D3): Profil-Feature zieht aus dem geloeschten
// compareMetricDefs.ts hierher um — natuerlicher, einziger verbleibender Ort.
export type ProfileKey = 'WINTERSPORT' | 'ALPINE_TOURING' | 'SUMMER_TREKKING' | 'ALLGEMEIN';

export interface IdealRange {
	min?: number | null;
	max?: number | string | null; // string fuer enum (NONE/MED/HIGH)
}

// Reduziert auf {key,label} (D3): Konsumenten lesen ausschliesslich m.key/m.label
// (verifiziert in CompareNewEditor.svelte + buildComparePrefillRows unten).
// Werte 1:1 aus den ehemaligen MetricDef-Objekten uebernommen.
export const PROFILE_METRICS_WITH_SCALES: Record<ProfileKey, { key: string; label: string }[]> = {
	WINTERSPORT: [
		{ key: 'snow_depth_cm', label: 'Schneehöhe' },
		{ key: 'snow_new_sum_cm', label: 'Neuschnee' },
		{ key: 'sunny_hours_h', label: 'Sonnenstunden' },
		{ key: 'wind_max_kmh', label: 'Windspitzen' },
		{ key: 'cloud_avg_pct', label: 'Bewölkung Ø' },
	],
	ALPINE_TOURING: [
		{ key: 'snow_new_sum_cm', label: 'Neuschnee' },
		{ key: 'visibility_min_m', label: 'Sichtweite min' },
		{ key: 'wind_max_kmh', label: 'Windspitzen' },
	],
	SUMMER_TREKKING: [
		{ key: 'precip_sum_mm', label: 'Niederschlag' },
		{ key: 'thunder_level_max', label: 'Gewitter' },
		{ key: 'wind_max_kmh', label: 'Windspitzen' },
		{ key: 'uv_index_max', label: 'UV-Index max' },
		{ key: 'visibility_min_m', label: 'Sichtweite min' },
	],
	ALLGEMEIN: [
		{ key: 'temp_max_c', label: 'Temperatur max' },
		{ key: 'wind_max_kmh', label: 'Windspitzen' },
		{ key: 'precip_sum_mm', label: 'Niederschlag' },
		{ key: 'visibility_min_m', label: 'Sichtweite min' },
	],
};

export const IDEAL_DEFAULTS: Record<ProfileKey, Record<string, IdealRange>> = {
	WINTERSPORT: {
		snow_depth_cm: { min: 30, max: 200 },
		snow_new_sum_cm: { min: 5, max: 50 },
		wind_max_kmh: { min: 0, max: 40 },
		cloud_avg_pct: { min: 0, max: 60 },
	},
	ALPINE_TOURING: {
		snow_new_sum_cm: { min: 0, max: 10 },
		visibility_min_m: { min: 2000, max: 10000 },
		wind_max_kmh: { min: 0, max: 50 },
	},
	SUMMER_TREKKING: {
		precip_sum_mm: { min: 0, max: 3 },
		thunder_level_max: { max: 'NONE' },
		wind_max_kmh: { min: 0, max: 35 },
		uv_index_max: { min: 0, max: 8 },
	},
	ALLGEMEIN: {
		temp_max_c: { min: 15, max: 35 },
		wind_max_kmh: { min: 0, max: 50 },
		precip_sum_mm: { min: 0, max: 5 },
	},
};

export const VERGLEICH_CTX_DEFAULTS = { notify: false, mark: true };

/**
 * Baut Zeilen aus preset.corridors[] (vergleich-Namensraum) + Rest als Pool.
 * Analog buildRoutePool. Issue #1350 Teil 3: `defs` kommt jetzt vom Aufrufer
 * (async aus GET /api/compare/metrics geladen) statt aus einer Modul-Konstante.
 *
 * F003-Fix (Adversary CRITICAL): Corridor-Eintraege mit einer Metrik-ID
 * AUSSERHALB von `defs` (z.B. ein zukuenftig entferntes Feld, ein
 * Tippfehler-Import o.ae.) werden NICHT verworfen, sondern in
 * `unknownCorridors` gesammelt — reiner Pass-Through, keine UI-Zeile, aber
 * `buildCompareCorridorSavePayload` haengt sie unveraendert an `corridors[]`
 * an (kein stiller Datenverlust beim naechsten Speichern).
 */
export function buildComparePool(corridors: Corridor[], defs: CompareMetricDef[]): {
	rows: CorridorRowState[];
	poolLeft: CompareMetricDef[];
	unknownCorridors: Corridor[];
} {
	const remaining = new Map(corridors.map((c) => [c.metric, c]));
	const rows: CorridorRowState[] = [];
	const poolLeft: CompareMetricDef[] = [];
	for (const def of defs) {
		const c = remaining.get(def.metric);
		if (c) {
			rows.push({
				metric: def.metric, label: def.label, unit: def.unit, scale: def.scale, step: def.step,
				min: c.range[0], max: c.range[1], notify: c.notify, mark: c.mark,
				kind: def.kind, ordinalLabels: def.ordinalLabels, alarmCapable: def.alarmCapable,
			});
			remaining.delete(def.metric);
		} else {
			poolLeft.push(def);
		}
	}
	return { rows, poolLeft, unknownCorridors: [...remaining.values()] };
}

/**
 * Fuegt eine Zeile aus dem vergleich-Pool hinzu. Analog addRow, andere Def-Quelle.
 * Issue #1350 Teil 3: `defs` kommt jetzt vom Aufrufer statt aus einer Modul-Konstante.
 *
 * F002-Fix (Adversary CRITICAL): `wasActive` = war die Metrik beim Mount
 * bereits in `active_metrics` aktiv (Bestand ohne Corridor-Eintrag, z.B.
 * Legacy-Preset vor der Migration). Ein "+ Metrik hinzufuegen"-Klick darf
 * einen laufenden Alarm NICHT stillschweigend deaktivieren — die Metrik war
 * ja bereits alarm-aktiv, der Klick fuegt nur die Corridor-Zeile (Anzeige/
 * mark) hinzu. Nur eine wirklich NEUE (bisher inaktive) Metrik bekommt den
 * Kontext-Default (VERGLEICH_CTX_DEFAULTS.notify=false).
 */
export function addCompareRow(
	rows: CorridorRowState[],
	poolLeft: CompareMetricDef[],
	metric: string,
	defs: CompareMetricDef[],
	ctxDefaults: { notify: boolean; mark: boolean } = VERGLEICH_CTX_DEFAULTS,
	wasActive: boolean = false
): { rows: CorridorRowState[]; poolLeft: CompareMetricDef[] } {
	const def = defs.find((d) => d.metric === metric);
	if (!def) return { rows, poolLeft };
	// Nicht-alarmfaehige Metriken koennen nie "Warnen" — notify bleibt fest false,
	// unabhaengig von wasActive (defensiv, s. alarmCapable-Invariante oben).
	const notify = def.alarmCapable ? (wasActive || ctxDefaults.notify) : false;
	const newRow: CorridorRowState = {
		metric: def.metric, label: def.label, unit: def.unit, scale: def.scale, step: def.step,
		min: def.defaultMin, max: def.defaultMax,
		notify, mark: ctxDefaults.mark,
		kind: def.kind, ordinalLabels: def.ordinalLabels, alarmCapable: def.alarmCapable,
	};
	return { rows: [...rows, newRow], poolLeft: poolLeft.filter((m) => m.metric !== metric) };
}

/**
 * Wizard-Create-Prefill (Team-Lead-Korrektur, PO-Linie „nichts Neues erfinden
 * — wie heute"): Step3Idealwerte befuellte im Create-Wizard automatisch aus
 * dem Aktivitaetsprofil (PROFILE_METRICS_WITH_SCALES + IDEAL_DEFAULTS,
 * activeMetricKeys = alle Profil-Metriken). Nur fuer den leeren Create-Fall
 * aufgerufen (CorridorEditor.svelte: !ws.isEditMode && corridors.length===0).
 * Issue #1350 Teil 3: `defs` kommt jetzt vom Aufrufer statt aus einer Modul-Konstante.
 *
 * notify=alarmCapable (spiegelt das heutige Verhalten: ein frisch erzeugtes
 * Preset setzt `active_metrics` = Profil-Metriken, das war frueher die
 * einzige Alarm-Filter-Quelle fuer die 10 Alarm-Keys — die 4 reinen
 * Vergleichs-Metriken konnten nie alarmieren). mark=true fuer alle (jede
 * Profil-Metrik hatte im alten Editor einen Idealwert-Slider).
 */
export function buildComparePrefillRows(profileKey: ProfileKey, defs: CompareMetricDef[]): CorridorRowState[] {
	const defById = new Map(defs.map((d) => [d.metric, d]));
	const profileMetrics = PROFILE_METRICS_WITH_SCALES[profileKey] ?? PROFILE_METRICS_WITH_SCALES.ALLGEMEIN;
	const defaults = IDEAL_DEFAULTS[profileKey] ?? {};
	const rows: CorridorRowState[] = [];
	for (const m of profileMetrics) {
		const def = defById.get(m.key);
		if (!def) continue;
		const idealDefault = defaults[m.key];
		let min = def.defaultMin;
		let max = def.defaultMax;
		if (idealDefault) {
			if (def.kind === 'ordinal') {
				if (typeof idealDefault.max === 'string') max = enumToOrdinal(idealDefault.max) ?? max;
			} else {
				if (typeof idealDefault.min === 'number') min = idealDefault.min;
				if (typeof idealDefault.max === 'number') max = idealDefault.max;
			}
		}
		rows.push({
			metric: def.metric, label: def.label, unit: def.unit, scale: def.scale, step: def.step,
			min, max, notify: def.alarmCapable, mark: true,
			kind: def.kind, ordinalLabels: def.ordinalLabels, alarmCapable: def.alarmCapable,
		});
	}
	return rows;
}

/**
 * Dual-Write-Save-Payload (Kern von Slice 4): `mark` spiegelt in
 * `display_config.ideal_ranges` (heutiges Format je Metrik-Kind unveraendert:
 * {min?,max?} fuer Zahlen, {max:'NONE'|'MED'|'HIGH'} fuer Gewitter — offene
 * Seite wird weggelassen wie heute). `notify` spiegelt in
 * `display_config.active_metrics`/`metric_alert_levels` (Sync-Bruecke analog
 * `buildCorridorSavePayload` oben, wiederverwendet via `deriveMetricAlertLevel`).
 *
 * #1191 HART: `activeMetricKeys` ist die pure Ableitung aus `rows.notify` —
 * wenn ALLE Zeilen notify=false sind, bleibt das Ergebnis `[]` (bewusst leer,
 * keine Heuristik reaktiviert etwas). Eintraege ohne Zeile in DIESER Session
 * (z.B. noch nicht geladen) bleiben per RMW erhalten — nur Metriken mit einer
 * `rows`-Zeile werden ueberschrieben/entfernt, und `notify` wirkt sich NUR bei
 * `alarmCapable!==false` auf active_metrics/metric_alert_levels aus (die 4
 * reinen Vergleichs-Metriken kennt die Δ-Wächter-Bruecke nicht).
 *
 * F003-Fix (Adversary CRITICAL): `unknownCorridors` (aus `buildComparePool`)
 * werden unveraendert an `corridors[]` angehaengt — Pass-Through fuer
 * Metrik-IDs ausserhalb von COMPARE_METRIC_DEFS, kein stiller Datenverlust.
 */
export function buildCompareCorridorSavePayload(
	rows: CorridorRowState[],
	removedMetrics: string[],
	original: {
		idealRanges: Record<string, IdealRange>;
		activeMetricKeys: string[];
		metricAlertLevels: Record<string, SensLevel | undefined> | undefined;
	},
	unknownCorridors: Corridor[] = []
): {
	corridors: Corridor[];
	idealRanges: Record<string, IdealRange>;
	activeMetricKeys: string[];
	metricAlertLevels: Record<string, SensLevel>;
} {
	const idealRanges: Record<string, IdealRange> = { ...original.idealRanges };
	const activeSet = new Set(original.activeMetricKeys);
	const metricAlertLevels: Record<string, SensLevel> = {
		...(original.metricAlertLevels as Record<string, SensLevel>),
	};

	for (const m of removedMetrics) {
		if (rows.some((r) => r.metric === m)) continue; // erneut hinzugefuegt -> normale Ableitung gewinnt
		delete idealRanges[m];
		activeSet.delete(m);
		metricAlertLevels[m] = 'off';
	}

	for (const r of rows) {
		// mark -> ideal_ranges
		if (!r.mark) {
			delete idealRanges[r.metric];
		} else if (r.kind === 'ordinal') {
			if (r.max != null) idealRanges[r.metric] = { max: ORDINAL_ENUM[r.max] };
			else delete idealRanges[r.metric]; // keine Legacy-Repraesentation fuer min-only
		} else {
			const range: IdealRange = {};
			if (r.min != null) range.min = r.min;
			if (r.max != null) range.max = r.max;
			idealRanges[r.metric] = range;
		}
		// Issue #1311 (C1): notify steuert NICHT MEHR active_metrics — das
		// gehoert seit C1 exklusiv dem Wetter-Metriken-Tab (activeSet bleibt
		// unveraendert, reiner Pass-Through von original.activeMetricKeys minus
		// removedMetrics-Bereinigung oben). notify behaelt seine Alarm-Funktion
		// (metric_alert_levels) unveraendert — NUR fuer die 10 alarmfaehigen
		// Metriken (defensiv: r.alarmCapable===false ignoriert notify komplett,
		// die Alarm-Bruecke kennt diese Metriken nicht).
		if (r.alarmCapable === false) continue;
		metricAlertLevels[r.metric] = deriveMetricAlertLevel(r.notify, r.metric, original.metricAlertLevels ?? {});
	}

	return {
		corridors: [
			...rows.map((r): Corridor => ({ metric: r.metric, range: [r.min, r.max], notify: r.notify, mark: r.mark })),
			...unknownCorridors,
		],
		idealRanges,
		activeMetricKeys: [...activeSet],
		metricAlertLevels,
	};
}

// --- Band-Drag (PO-Vorgabe: Geste muss funktionieren, nicht nur angedeutet
// sein — Port aus corridor-editor.jsx::CorridorBand). Testbarer Kern:
// Pointer-Position -> Wert. Die DOM-Event-Verdrahtung (pointerdown/-move/-up,
// setPointerCapture) bleibt duenn in CorridorEditor.svelte.

/** Bildet eine Pointer-clientX-Position auf einen Track-Wert ab (geclamped auf `scale`, gesnapt auf `step`). */
export function valueAtPointer(
	clientX: number,
	trackLeft: number,
	trackWidth: number,
	scale: [number, number],
	step: number
): number {
	const [lo, hi] = scale;
	const span = hi - lo || 1;
	const t = Math.max(0, Math.min(1, (clientX - trackLeft) / (trackWidth || 1)));
	const raw = lo + t * span;
	return Math.round(raw / step) * step;
}

/** Verhindert, dass der min-Griff den max-Griff ueberholt (und umgekehrt) — Gegenseite=null (offen) clampt nicht. */
export function clampDragValue(side: 'min' | 'max', rawValue: number, min: number | null, max: number | null): number {
	if (side === 'min') return max != null ? Math.min(rawValue, max) : rawValue;
	return min != null ? Math.max(rawValue, min) : rawValue;
}

/**
 * F003 (Adversary, LOW): dieselbe Crossing-Schutz-Logik wie `clampDragValue`,
 * aber null-sicher fuer den manuellen Zahleneingabe-Pfad (CorridorBound) —
 * `null` (Grenze wird geoeffnet) bleibt unveraendert, nur numerische Werte
 * werden geclampt. Bewusste Abweichung von der JSX-Referenz, die diese
 * Luecke im manuellen Eingabepfad noch hat: funktionale Korrektheit
 * schlägt Bug-Treue.
 */
export function clampBoundInput(
	value: number | null,
	side: 'min' | 'max',
	row: Pick<CorridorRowState, 'min' | 'max'>
): number | null {
	if (value == null) return null;
	return clampDragValue(side, value, row.min, row.max);
}

/**
 * F001-Fix (Adversary HIGH, Slice 5, CorridorEditorMobile.openBound): Zielwert
 * beim Oeffnen einer Grenze (Stepper "offen · + Grenze") — 25%/75%-Fallback
 * auf der Skala, auf `step` gerundet, DANACH durch denselben Crossing-Clamp
 * wie der Stepper-/Manuell-Eingabepfad (clampDragValue) — sonst kann der
 * Fallback die bereits gesetzte Gegenseite ueberholen (Repro: scale=[0,20],
 * max=1 bereits gesetzt, min oeffnen -> ungeclampt waere min=5 > max=1,
 * "mark" zeigt danach lautlos nie mehr gruen).
 */
export function openBoundValue(
	row: Pick<CorridorRowState, 'scale' | 'step' | 'min' | 'max'>,
	side: 'min' | 'max'
): number {
	const [lo, hi] = row.scale;
	const fallback = side === 'min' ? lo + (hi - lo) * 0.25 : lo + (hi - lo) * 0.75;
	const rounded = Math.round(fallback / row.step) * row.step;
	return clampDragValue(side, rounded, row.min, row.max);
}

/**
 * F005 (Staging-Adversary, HIGH, AC-12-Rest): reine Entscheidung, welche
 * Aktion die duenne DOM-Verdrahtung auf dem BESTEHENDEN saveController
 * ausloesen muss — "schedule" bei gueltigem Zustand, "dirty" bei AC-12-
 * Verletzung (verhindert, dass der Save-Indikator faelschlich "Gespeichert ✓"
 * vom letzten erfolgreichen Save zeigt, waehrend gleichzeitig der
 * Fehlerbanner sichtbar ist).
 */
export function saveGateDecision(rows: CorridorRowState[]): 'schedule' | 'dirty' {
	return validateCorridorRows(rows).valid ? 'schedule' : 'dirty';
}
