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

import type { Corridor, SensLevel } from '$lib/types';

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
}

/** Baut Zeilen aus trip.corridors[] (route-Namensraum) + verbleibenden Pool fuer "+ Metrik". */
export function buildRoutePool(corridors: Corridor[]): {
	rows: CorridorRowState[];
	poolLeft: RouteMetricDef[];
} {
	const present = new Map(corridors.map((c) => [c.metric, c]));
	const rows: CorridorRowState[] = [];
	const poolLeft: RouteMetricDef[] = [];
	for (const def of ROUTE_METRIC_DEFS) {
		const c = present.get(def.metric);
		if (c) {
			rows.push({
				metric: def.metric, label: def.label, unit: def.unit, scale: def.scale, step: def.step, note: def.note,
				min: c.range[0], max: c.range[1], notify: c.notify, mark: c.mark,
			});
		} else {
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

/** AC-12: mind. eine Grenze ist Pflicht — beidseitig offen blockt das Speichern. */
export function validateCorridorRows(rows: CorridorRowState[]): { valid: boolean; errors: string[] } {
	const errors = rows.filter((r) => r.min == null && r.max == null).map((r) => r.metric);
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
