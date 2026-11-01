// Pure-Functions fuer Trip-Hero (Issue #154, Epic #135 Step 3).
// Spec: docs/specs/modules/epic_135_step3_trip_hero.md
//
// Alle Funktionen sind seiteneffektfrei und arbeiten auf Tages-Granularitaet
// in lokaler Zeit. KEIN toLocaleString — Monatsnamen und Zeitraum-Muster aus
// dem Katalog (home.monat.*, home.zeitraum.*; #2652 i18n F3), deterministisch
// ohne ICU. Sprache: aktuelle `locale` (tr/trn), Aufrufer in Svelte lesen
// `$locale` im $derived mit, damit ein Sprachwechsel ohne Neuladen wirkt.

import type { Trip } from '../types.ts';
import { deriveTripStatus } from './tripStatus.ts';
import { tr, trn, type MessageKey } from '../i18n/index.ts';

// i18n-dynamic: home.monat.
const monat = (m: number) => tr(`home.monat.${m + 1}` as MessageKey);

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

export function getDaysLabel(trip: Trip, now: Date): string {
	const status = deriveTripStatus(trip, now);
	const today = todayIso(now);

	if (status === 'paused') {
		if (trip.paused_at) {
			const pausedDate = new Date(trip.paused_at);
			const diff = daysBetween(pausedDate, now);
			if (diff <= 0) return tr('home.tage.pausiert_seit_heute');
			return trn('home.tage.pausiert_seit', diff);
		}
		return tr('home.tage.pausiert_seit_heute');
	}

	if (status === 'planned') {
		const dates = sortedStageDates(trip);
		if (dates.length === 0) return tr('home.tage.nicht_geplant');
		const diff = daysBetween(now, parseStageDate(dates[0]));
		if (diff <= 0) return tr('home.tage.heute');
		if (diff === 1) return tr('home.tage.morgen');
		return trn('home.tage.in_tagen', diff);
	}

	if (status === 'active') {
		const stages = trip.stages ?? [];
		const idx = stages.findIndex((s) => s.date === today);
		if (idx === -1) return tr('home.tage.tag_eins');
		return tr('home.tage.laeuft_seit', { tag: idx + 1 });
	}

	// #1271: draft (keine datierten Etappen) hat kein "Tage bis Start" —
	// sonst fiele es in den Fallback unten und zeigte fälschlich "Trip beendet".
	if (status === 'draft') return tr('home.tage.nicht_geplant');

	// finished/archived
	const dates = sortedStageDates(trip);
	if (dates.length === 0) return tr('home.tage.beendet');
	const last = parseStageDate(dates[dates.length - 1]);
	const diff = daysBetween(last, now);
	if (diff <= 0) return tr('home.tage.beendet_heute');
	return trn('home.tage.beendet_vor', diff);
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

	const monthF = monat(mF);
	const monthL = monat(mL);

	// Einzelner Tag
	if (dates[0] === dates[dates.length - 1]) {
		return tr('home.zeitraum.tag', { tag: dF, monat: monthF, jahr: yF });
	}

	// Gleicher Monat + Jahr
	if (mF === mL && yF === yL) {
		return tr('home.zeitraum.gleicher_monat', { von: dF, bis: dL, monat: monthF, jahr: yF });
	}

	// Verschiedene Monate, gleicher Jahr
	if (yF === yL) {
		return tr('home.zeitraum.verschiedene_monate', { von: dF, monat_von: monthF, bis: dL, monat_bis: monthL, jahr: yF });
	}

	// Verschiedene Jahre
	return tr('home.zeitraum.verschiedene_jahre', {
		von: dF, monat_von: monthF, jahr_von: yF, bis: dL, monat_bis: monthL, jahr_bis: yL
	});
}
