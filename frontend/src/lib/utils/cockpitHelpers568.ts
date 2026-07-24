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
 *   3. Wertebereiche — done wenn display_config.ideal_ranges nicht leer
 *      (Issue #1231 Slice 6: Label „Idealwerte" -> „Wertebereiche", Datenfeld unverändert)
 *   4. Layout     — done wenn display_config.active_metrics nicht leer (Nutzer hat
 *      im Wetter-Metriken-Tab tatsächlich Metriken ausgewählt)
 *   5. Versand    — done wenn report_config.morning_enabled || evening_enabled
 *
 * F002-Fix (Adversary): Orte liegen in location_ids (string[]), nicht locations.
 * Idealwerte und Layout in display_config; Versand in report_config.
 *
 * F006-Fix (Adversary, #1351 Fix-Loop): channel_layouts/preset_name sind seit
 * #1351 (AC-6) kein Compare-Feld mehr und werden vom Editor nie gesetzt — als
 * Fortschritts-Signal wären sie ab sofort dauerhaft leer. active_metrics ist
 * der Tab, den der Nutzer tatsächlich bedient (analog Trip-Schritt „Wetter").
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

	const activeMetrics = dc['active_metrics'];
	const hasLayout = Array.isArray(activeMetrics) && activeMetrics.length > 0;

	const rc = (preset as unknown as Record<string, unknown>)['report_config'];
	const rcObj = rc && typeof rc === 'object' && !Array.isArray(rc)
		? (rc as Record<string, unknown>)
		: {};
	const hasActiveSend =
		rcObj['morning_enabled'] === true || rcObj['evening_enabled'] === true;

	return [
		{ label: 'Vergleich', done: true },
		{ label: 'Orte', done: locCount >= 2 },
		{ label: 'Wertebereiche', done: hasIdealValues },
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

/** Eine aufgeloeste Versand-Uhrzeit (Stunde/Minute) eines aktiven Slots. */
export type SlotTime = { hour: number; minute: number };

/** Parst "HH:MM:SS" / "HH:MM" → {hour, minute}; null bei unbrauchbarem Wert. */
function parseSlotTime(raw: string | undefined): SlotTime | null {
	const m = /^(\d{1,2}):(\d{2})/.exec(raw ?? '');
	if (!m) return null;
	const hour = Number(m[1]);
	const minute = Number(m[2]);
	if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return null;
	return { hour, minute };
}

/**
 * Loest die AKTIVEN Versand-Slots eines Presets auf — Anzeige-seitiges
 * Gegenstueck zu `resolve_preset_slots` in
 * `src/services/compare_slot_scheduler.py` (Issue #1268 / AC-9). Beide muessen
 * deckungsgleich bleiben: Anzeige und tatsaechlicher Versand duerfen nicht
 * auseinanderlaufen.
 *
 * Migrations-Fallback (identisch zur Python-Referenz): fehlt `morning_time`
 * komplett, ist das Preset "nie migriert" — dann entscheidet der Alt-Wert von
 * `schedule` ueber die Intention: `daily_evening` → Abend-Slot 18:00, alles
 * andere → Morgen-Slot 06:00 (verhaltensidentisch zum frueheren 06:00-Cron).
 */
export function resolvePresetSlots(preset: ComparePreset): SlotTime[] {
	if (preset.morning_time == null) {
		return (preset.schedule as string) === 'daily_evening'
			? [{ hour: 18, minute: 0 }]
			: [{ hour: 6, minute: 0 }];
	}

	const slots: SlotTime[] = [];
	const morning = parseSlotTime(preset.morning_time);
	if ((preset.morning_enabled ?? true) && morning) slots.push(morning);
	const evening = parseSlotTime(preset.evening_time ?? '18:00:00');
	if ((preset.evening_enabled ?? false) && evening) slots.push(evening);
	return slots;
}

/**
 * Die fuer Anzeige-Labels massgebliche Versandzeit: der frueheste aktive Slot.
 * `null`, wenn kein Slot aktiv ist (dann zeigt die Oberflaeche keine Uhrzeit).
 *
 * Issue #1268 (AC-10): EINE Ableitung fuer alle Flaechen, die eine Versandzeit
 * anzeigen — Vergleichs-Kachel (`presetTileScheduleLabel`) und Startseiten-Hero
 * (`routes/+page.svelte`). Beide lasen zuvor `hour_from` und zeigten bei neu
 * angelegten Vergleichen "tägl. 00" bzw. "· 00:00". Bewusst hier und nicht als
 * Kopie: die Slot-Semantik darf nur an einer Stelle leben.
 */
export function primarySendSlot(preset: ComparePreset): SlotTime | null {
	const slots = resolvePresetSlots(preset);
	if (slots.length === 0) return null;
	return slots.reduce((a, b) => (a.hour * 60 + a.minute <= b.hour * 60 + b.minute ? a : b));
}

/**
 * Berechnet den naechsten Versand-Zeitstempel aus den echten Versand-Slots.
 * - 'daily': naechster bevorstehender aktiver Slot (heute, sonst morgen)
 * - 'weekly': naechster passender Wochentag (preset.weekday, 0=Montag) zur Slot-Zeit
 * - 'manual': null
 * - kein aktiver Slot: null
 *
 * Issue #1268 (AC-9): liest NICHT mehr `hour_from` — das war der Start des
 * Bewertungs-Zeitfensters, nicht die Versandzeit (Anzeige log: 09:00 statt
 * 07:00). Versand-Wahrheit sind `morning_time`/`evening_time` (types.ts:304).
 */
export function deriveNextSend(preset: ComparePreset, now: Date): Date | null {
	if (!preset || preset.schedule === 'manual') return null;
	const slots = resolvePresetSlots(preset);
	if (slots.length === 0) return null;

	const at = (dayOffset: number, slot: SlotTime): Date =>
		new Date(now.getFullYear(), now.getMonth(), now.getDate() + dayOffset, slot.hour, slot.minute, 0, 0);

	const earliest = (candidates: Date[]): Date =>
		candidates.reduce((a, b) => (a <= b ? a : b));

	if (preset.schedule === 'daily' || (preset.schedule as string) === 'daily_evening') {
		// Heute, sofern der Slot noch bevorsteht — sonst derselbe Slot morgen.
		return earliest(slots.map((s) => (now < at(0, s) ? at(0, s) : at(1, s))));
	}

	if (preset.schedule === 'weekly') {
		const targetWeekday = preset.weekday; // 0=Montag
		if (targetWeekday == null) return null;
		// JS: 0=Sonntag, 1=Montag... convert: preset 0=Mon → JS 1=Mon
		const jsWeekday = (targetWeekday + 1) % 7;
		const daysUntil = (jsWeekday - now.getDay() + 7) % 7;
		return earliest(
			slots.map((s) =>
				// Am Zieltag selbst zaehlt nur ein noch bevorstehender Slot,
				// sonst erst in einer Woche.
				daysUntil === 0 && now >= at(0, s) ? at(7, s) : at(daysUntil, s)
			)
		);
	}

	return null;
}
