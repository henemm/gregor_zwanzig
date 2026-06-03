// Issue #568 — Startseite-Redesign (Cockpit + Planungs-/Leerzustand).
// Spec: docs/specs/modules/issue_568_home_redesign.md
//
// Pure-Function-Helfer für die neuen Cockpit-Views auf der Startseite.
// Keine Mocks, keine Seiteneffekte — testbar via node --test.
//
// Hinweis: setupStep*-Funktionen lesen Felder, die im aktuellen Typsystem
// (Trip / ComparePreset) noch nicht alle deklariert sind (z.B. layout_mode,
// ideal_values, subscriptions). Sie greifen daher defensiv über einen
// Record-Cast zu, damit die Helper auch dann arbeiten, wenn das Backend
// ein zusätzliches Feld liefert. Die TS-Signaturen Trip/ComparePreset
// bleiben weiterhin die nominale API.

import type { Trip, ComparePreset } from '../types.ts';
import { tripStatus } from './tripStatus.ts';

export type SetupStep = { label: string; done: boolean };

/**
 * Fortschritt in Prozent (0–100, gerundet auf Integer).
 * 0/0 → 0 (kein Division-by-zero).
 */
export function dayProgress(dayX: number, dayY: number): number {
	if (!dayY || dayY <= 0) return 0;
	return Math.round((dayX / dayY) * 100);
}

/**
 * Sortiert die Stage-Datumsstrings einer Tour aufsteigend (ISO-Datum =
 * lexikographisch == chronologisch). Leerer Output, wenn nichts gesetzt.
 */
function stageDates(trip: Trip): string[] {
	return (trip.stages ?? [])
		.map((s) => s?.date)
		.filter((d): d is string => typeof d === 'string' && d.length >= 10)
		.map((d) => d.slice(0, 10))
		.sort();
}

/**
 * Setup-Schritte für einen Trip (in fester Reihenfolge):
 *   1. Route   — done wenn stages.length >= 1
 *   2. Etappen — done wenn ≥1 Stage mit gesetztem `date`
 *   3. Wetter  — done wenn display_config.metrics?.length > 0
 *   4. Layout  — done wenn display_config.preset_name oder channel_layouts gesetzt
 *   5. Reports — done wenn morning_enabled || evening_enabled
 *
 * F001-Fix (Adversary): Wetter-Metriken liegen in display_config.metrics,
 * nicht in report_config.metrics. layout_mode existiert nicht — stattdessen
 * display_config.preset_name / channel_layouts als Proxy für "Layout konfiguriert".
 */
export function setupStepTrip(trip: Trip): SetupStep[] {
	const stages = trip.stages ?? [];
	const dc = trip.display_config ?? {};
	const dcMetrics = Array.isArray(dc.metrics) ? dc.metrics : [];
	const hasMetrics = dcMetrics.length > 0;
	const hasLayout =
		dc.preset_name != null || dc.channel_layouts != null || dc.channel_layouts_per_report != null;

	const rc = trip.report_config ?? {};
	const morning = rc.morning_enabled === true;
	const evening = rc.evening_enabled === true;

	return [
		{ label: 'Route', done: stages.length >= 1 },
		{
			label: 'Etappen',
			done: stages.some((s) => typeof s?.date === 'string' && s.date.length > 0)
		},
		{ label: 'Wetter', done: hasMetrics },
		{ label: 'Layout', done: hasLayout },
		{ label: 'Reports', done: morning || evening }
	];
}

/**
 * Setup-Schritte für einen ComparePreset (in fester Reihenfolge):
 *   1. Vergleich  — immer done (Entwurf existiert)
 *   2. Orte       — done wenn location_ids.length >= 2
 *   3. Idealwerte — done wenn display_config.ideal_ranges nicht leer
 *   4. Layout     — done wenn display_config.channel_layouts gesetzt
 *   5. Versand    — done wenn report_config.morning_enabled || evening_enabled
 *
 * F002-Fix (Adversary): Orte liegen in location_ids (string[]), nicht locations.
 * Idealwerte und Layout in display_config; Versand in report_config.
 */
export function setupStepCompare(preset: ComparePreset): SetupStep[] {
	const locCount = Array.isArray(preset.location_ids) ? preset.location_ids.length : 0;

	const dc = (preset.display_config ?? {}) as Record<string, unknown>;
	const idealRanges = dc['ideal_ranges'];
	const hasIdealValues =
		idealRanges != null &&
		typeof idealRanges === 'object' &&
		!Array.isArray(idealRanges) &&
		Object.keys(idealRanges as Record<string, unknown>).length > 0;

	const hasLayout = dc['channel_layouts'] != null || dc['preset_name'] != null;

	const rc = (preset as unknown as Record<string, unknown>)['report_config'];
	const rcObj = rc && typeof rc === 'object' && !Array.isArray(rc)
		? (rc as Record<string, unknown>)
		: {};
	const hasActiveSend =
		rcObj['morning_enabled'] === true || rcObj['evening_enabled'] === true;

	return [
		{ label: 'Vergleich', done: true },
		{ label: 'Orte', done: locCount >= 2 },
		{ label: 'Idealwerte', done: hasIdealValues },
		{ label: 'Layout', done: hasLayout },
		{ label: 'Versand', done: hasActiveSend }
	];
}

/** Lokales ISO-Datum (YYYY-MM-DD, Tageskorn). */
function isoDay(now: Date): string {
	const y = now.getFullYear();
	const m = String(now.getMonth() + 1).padStart(2, '0');
	const d = String(now.getDate()).padStart(2, '0');
	return `${y}-${m}-${d}`;
}

/**
 * Nächste geplante Tour: erster Trip mit Status != 'aktiv' und Start-Datum
 * ≥ heute, sortiert nach frühestem Startdatum. Null, wenn nichts passt.
 */
export function nextPlannedTrip(trips: Trip[], now: Date): Trip | null {
	const list = trips ?? [];
	const today = isoDay(now);

	let best: Trip | null = null;
	let bestStart: string | null = null;

	for (const t of list) {
		if (tripStatus(t, now) === 'aktiv') continue;
		const dates = stageDates(t);
		const start = dates[0];
		if (!start || start < today) continue;
		if (bestStart === null || start < bestStart) {
			bestStart = start;
			best = t;
		}
	}

	return best;
}

/**
 * Erster unvollständiger Vergleich (mind. ein Setup-Schritt offen).
 * Null, wenn alle Presets vollständig konfiguriert sind oder die Liste leer.
 */
export function firstIncompleteCompare(presets: ComparePreset[]): ComparePreset | null {
	for (const p of presets ?? []) {
		const steps = setupStepCompare(p);
		if (steps.some((s) => !s.done)) return p;
	}
	return null;
}

/**
 * Gibt den ersten Trip zurück, dessen Zeitraum heute enthält (status === 'aktiv').
 * Verwendet tripStatus() aus './tripStatus.ts'.
 */
export function liveTrip(trips: Trip[], now: Date): Trip | null {
	for (const t of trips ?? []) {
		if (tripStatus(t, now) === 'aktiv') return t;
	}
	return null;
}

/**
 * Berechnet den nächsten Versand-Zeitstempel aus dem Preset-Schedule.
 * - 'daily': heute um hour_from wenn noch nicht vorbei, sonst morgen
 * - 'weekly': nächster passender Wochentag (preset.weekday, 0=Montag) um hour_from
 * - 'manual': null
 * - fehlende Felder: null
 */
export function deriveNextSend(preset: ComparePreset, now: Date): Date | null {
	if (!preset || preset.schedule === 'manual') return null;
	const hourFrom = preset.hour_from;
	if (hourFrom == null) return null;

	if (preset.schedule === 'daily') {
		// Heute um hour_from wenn noch nicht vorbei, sonst morgen
		const candidate = new Date(now.getFullYear(), now.getMonth(), now.getDate(), hourFrom, 0, 0, 0);
		if (now < candidate) return candidate;
		// Morgen
		const tomorrow = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, hourFrom, 0, 0, 0);
		return tomorrow;
	}

	if (preset.schedule === 'weekly') {
		const targetWeekday = preset.weekday; // 0=Montag
		if (targetWeekday == null) return null;
		// JS: 0=Sonntag, 1=Montag... convert: preset 0=Mon → JS 1=Mon
		const jsWeekday = (targetWeekday + 1) % 7;
		const nowJsDay = now.getDay();
		let daysUntil = (jsWeekday - nowJsDay + 7) % 7;
		// If same day, check if hour has passed
		if (daysUntil === 0) {
			const candidate = new Date(now.getFullYear(), now.getMonth(), now.getDate(), hourFrom, 0, 0, 0);
			if (now < candidate) return candidate;
			daysUntil = 7;
		}
		return new Date(now.getFullYear(), now.getMonth(), now.getDate() + daysUntil, hourFrom, 0, 0, 0);
	}

	return null;
}
