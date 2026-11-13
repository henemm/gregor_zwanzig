// Pure-Functions fuer Trip-Hero (Issue #154, Epic #135 Step 3).
// Spec: docs/specs/modules/epic_135_step3_trip_hero.md
//
// Alle Funktionen sind seiteneffektfrei und arbeiten auf Tages-Granularitaet
// in lokaler Zeit. KEIN toLocaleString — Monatsnamen und Zeitraum-Muster aus
// dem Katalog (home.monat.*, home.zeitraum.*; #2652 i18n F3), deterministisch
// ohne ICU. Sprache: aktuelle `locale` (tr), Aufrufer in Svelte lesen
// `$locale` im $derived mit, damit ein Sprachwechsel ohne Neuladen wirkt.
// #2913 c2: getDaysLabel („läuft seit Tag N“ u. a.) entfernt — einziger Nutzer war der Zusatz
// neben der Status-Pill im Trip-Kopf, den das Mockup nicht zeigt (Spec feat_2913_c2_seitenkopf.md).

import type { Trip } from '../types.ts';
import { tr, type MessageKey } from '../i18n/index.ts';

// i18n-dynamic: home.monat.
const monat = (m: number) => tr(`home.monat.${m + 1}` as MessageKey);

function parseStageDate(dateStr: string): Date {
	// ISO-Date 'YYYY-MM-DD' (oder Datetime mit T-Suffix) → lokales Date um Mitternacht.
	const clean = dateStr.split('T')[0];
	const [y, m, d] = clean.split('-').map(Number);
	return new Date(y, (m ?? 1) - 1, d ?? 1);
}

function sortedStageDates(trip: Trip): string[] {
	return (trip.stages ?? [])
		.map((s) => s.date)
		.filter((d): d is string => !!d)
		.slice()
		.sort();
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
