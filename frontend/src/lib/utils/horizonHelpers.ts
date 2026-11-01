// Issue #343 — Wording-Heuristik und Dot-Pattern fuer HorizonChip-UI.
// Spec: docs/specs/modules/issue_343_horizon_chip_ui.md §6
//
// Reine Funktionen — keine Svelte-Imports, damit `node --experimental-strip-types --test`
// die Test-Datei laden kann.

import { tr, type MessageKey } from '../i18n/index.ts';

export type Horizons = {
	today: boolean;
	tomorrow: boolean;
	day_after: boolean;
};

export const HORIZONS_ALL: Horizons = {
	today: true,
	tomorrow: true,
	day_after: true,
};

export type HorizonSummaryInput = {
	metric_id: string;
	horizons: Horizons;
	enabled?: boolean;
};

/**
 * Wording-Heuristik aus Issue #343 (Component-Spec §6 + Wording-Tabelle).
 * Gruppiert Metriken nach Horizont-Pattern und liefert eine condensed
 * Zusammenfassungs-Zeile zurueck.
 *
 * Beispiel-Output:
 *   "5 alle drei Tage · 2 nur heute + morgen · 1 nur heute"
 *
 * - Disabled-Metriken (enabled === false) werden NICHT gezaehlt.
 * - Buckets mit n=0 werden weggelassen.
 * - Trenner zwischen Buckets: " · " (Mittelpunkt mit Leerzeichen, COPY.md §8).
 * - Bucket-Reihenfolge: alle-drei → heute+morgen → nur-heute → morgen+uebermorgen → sonstige.
 */
export function computeHorizonSummary(metrics: HorizonSummaryInput[]): string {
	const buckets = {
		allThree: 0,         // (t, t, t)
		todayTomorrow: 0,    // (t, t, f)
		onlyToday: 0,        // (t, f, f)
		tomorrowDayAfter: 0, // (f, t, t)
		other: 0,            // alles andere
	};

	for (const m of metrics) {
		if (m.enabled === false) continue;
		const { today, tomorrow, day_after } = m.horizons;
		if (today && tomorrow && day_after) buckets.allThree++;
		else if (today && tomorrow && !day_after) buckets.todayTomorrow++;
		else if (today && !tomorrow && !day_after) buckets.onlyToday++;
		else if (!today && tomorrow && day_after) buckets.tomorrowDayAfter++;
		else buckets.other++;
	}

	const parts: string[] = [];
	const gruppen: [number, MessageKey][] = [
		[buckets.allThree, 'bausteine.horizont.alle_drei'],
		[buckets.todayTomorrow, 'bausteine.horizont.nur_heute_morgen'],
		[buckets.onlyToday, 'bausteine.horizont.nur_heute'],
		[buckets.tomorrowDayAfter, 'bausteine.horizont.nur_morgen_uebermorgen'],
		[buckets.other, 'bausteine.horizont.sonstige']
	];
	for (const [anzahl, key] of gruppen) if (anzahl > 0) parts.push(tr(key, { anzahl }));
	return parts.join(' · ');
}

/**
 * Liefert die ●●●/●●○/●○○-Darstellung fuer eine Horizons-Konfig.
 * Reihenfolge: heute / morgen / uebermorgen.
 */
export function dotsForHorizons(h: Horizons): string {
	return [h.today, h.tomorrow, h.day_after]
		.map((b) => (b ? '●' : '○'))
		.join('');
}
