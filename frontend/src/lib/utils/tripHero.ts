// Pure-Functions fuer Trip-Hero (Issue #154, Epic #135 Step 3).
// Spec: docs/specs/modules/epic_135_step3_trip_hero.md
//
// Alle Funktionen sind seiteneffektfrei und arbeiten auf Tages-Granularitaet
// in lokaler Zeit. KEIN toLocaleString — explizite deutsche Monatsnamen-Map
// fuer deterministische Tests (Node-Test-Runner laeuft ohne ICU-Locale).

import type { Trip } from '../types.ts';
import { deriveTripStatus } from './tripStatus.ts';

const MONTH_NAMES_DE = [
	'Januar',
	'Februar',
	'März',
	'April',
	'Mai',
	'Juni',
	'Juli',
	'August',
	'September',
	'Oktober',
	'November',
	'Dezember'
] as const;

function daysBetween(a: Date, b: Date): number {
	const aDay = new Date(a.getFullYear(), a.getMonth(), a.getDate());
	const bDay = new Date(b.getFullYear(), b.getMonth(), b.getDate());
	return Math.round((bDay.getTime() - aDay.getTime()) / 86400000);
}

function parseStageDate(dateStr: string): Date {
	// ISO-Date 'YYYY-MM-DD' (oder Datetime mit T-Suffix) → lokales Date um Mitternacht.
	const clean = dateStr.split('T')[0];
	const [y, m, d] = clean.split('-').map(Number);
	return new Date(y, (m ?? 1) - 1, d ?? 1);
}

function todayIso(now: Date): string {
	const y = now.getFullYear();
	const m = String(now.getMonth() + 1).padStart(2, '0');
	const d = String(now.getDate()).padStart(2, '0');
	return `${y}-${m}-${d}`;
}

function sortedStageDates(trip: Trip): string[] {
	return (trip.stages ?? [])
		.map((s) => s.date)
		.filter((d): d is string => !!d)
		.slice()
		.sort();
}

export function getActiveStageDisplay(trip: Trip, now: Date): string {
	const status = deriveTripStatus(trip, now);
	const today = todayIso(now);

	if (status === 'paused') return 'Pausiert';

	if (status === 'planned') {
		const dates = sortedStageDates(trip);
		if (dates.length === 0) return 'Trip noch nicht geplant';
		const diff = daysBetween(now, parseStageDate(dates[0]));
		if (diff <= 0) return 'Trip startet heute';
		if (diff === 1) return 'Trip startet morgen';
		return `Trip startet in ${diff} Tagen`;
	}

	if (status === 'active') {
		const stages = trip.stages ?? [];
		const idx = stages.findIndex((s) => s.date === today);
		if (idx === -1) return 'Trip läuft';
		const stage = stages[idx];
		return `Tag ${idx + 1}/${stages.length} · ${stage.name}`;
	}

	// archived
	const dates = sortedStageDates(trip);
	if (dates.length === 0) return 'Trip beendet';
	const last = parseStageDate(dates[dates.length - 1]);
	const diff = daysBetween(last, now);
	if (diff <= 0) return 'Beendet heute';
	return `Beendet vor ${diff} Tagen`;
}

function parseHHMM(timeStr: string | undefined): string | null {
	if (!timeStr) return null;
	const parts = timeStr.split(':');
	if (parts.length < 2) return null;
	const hh = parts[0].padStart(2, '0');
	const mm = parts[1].padStart(2, '0');
	return `${hh}:${mm}`;
}

function compareHHMM(now: Date, hhmm: string): number {
	const [h, m] = hhmm.split(':').map(Number);
	const nowMin = now.getHours() * 60 + now.getMinutes();
	const tgtMin = h * 60 + m;
	return nowMin - tgtMin;
}

export function getNextBriefing(trip: Trip, now: Date): string {
	// Issue #207: trip.report_config ist jetzt typisiert (ReportConfig | undefined).
	const cfg = trip.report_config;
	if (!cfg) return 'Briefings deaktiviert';
	if (cfg.enabled === false) return 'Briefings deaktiviert';

	const morning = parseHHMM(cfg.morning_time);
	const evening = parseHHMM(cfg.evening_time);
	if (!morning && !evening) return 'Briefings deaktiviert';

	if (morning && compareHHMM(now, morning) < 0) return `heute, ${morning}`;
	if (evening && compareHHMM(now, evening) < 0) return `heute, ${evening}`;
	if (morning) return `morgen, ${morning}`;
	if (evening) return `morgen, ${evening}`;
	return 'Briefings deaktiviert';
}

export function getDaysLabel(trip: Trip, now: Date): string {
	const status = deriveTripStatus(trip, now);
	const today = todayIso(now);

	if (status === 'paused') {
		if (trip.paused_at) {
			const pausedDate = new Date(trip.paused_at);
			const diff = daysBetween(pausedDate, now);
			if (diff <= 0) return 'pausiert seit heute';
			return `pausiert seit ${diff} Tagen`;
		}
		return 'pausiert seit heute';
	}

	if (status === 'planned') {
		const dates = sortedStageDates(trip);
		if (dates.length === 0) return 'Trip noch nicht geplant';
		const diff = daysBetween(now, parseStageDate(dates[0]));
		if (diff <= 0) return 'heute';
		if (diff === 1) return 'morgen';
		return `in ${diff} Tagen`;
	}

	if (status === 'active') {
		const stages = trip.stages ?? [];
		const idx = stages.findIndex((s) => s.date === today);
		if (idx === -1) return 'Tag 1';
		return `läuft seit Tag ${idx + 1}`;
	}

	// archived
	const dates = sortedStageDates(trip);
	if (dates.length === 0) return 'Trip beendet';
	const last = parseStageDate(dates[dates.length - 1]);
	const diff = daysBetween(last, now);
	if (diff <= 0) return 'beendet heute';
	return `beendet vor ${diff} Tagen`;
}

export function formatDateRange(trip: Trip): string {
	const dates = sortedStageDates(trip);
	if (dates.length === 0) return '';

	const first = parseStageDate(dates[0]);
	const last = parseStageDate(dates[dates.length - 1]);

	const dF = first.getDate();
	const mF = first.getMonth();
	const yF = first.getFullYear();
	const dL = last.getDate();
	const mL = last.getMonth();
	const yL = last.getFullYear();

	const monthF = MONTH_NAMES_DE[mF];
	const monthL = MONTH_NAMES_DE[mL];

	// Einzelner Tag
	if (dates[0] === dates[dates.length - 1]) {
		return `${dF}. ${monthF} ${yF}`;
	}

	// Gleicher Monat + Jahr
	if (mF === mL && yF === yL) {
		return `${dF}.–${dL}. ${monthF} ${yF}`;
	}

	// Verschiedene Monate, gleicher Jahr
	if (yF === yL) {
		return `${dF}. ${monthF} – ${dL}. ${monthL} ${yF}`;
	}

	// Verschiedene Jahre
	return `${dF}. ${monthF} ${yF} – ${dL}. ${monthL} ${yL}`;
}
