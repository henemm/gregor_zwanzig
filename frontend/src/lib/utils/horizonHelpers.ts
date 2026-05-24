// Issue #343 — Wording-Heuristik und Dot-Pattern fuer HorizonChip-UI.
// Spec: docs/specs/modules/issue_343_horizon_chip_ui.md §6
//
// Reine Funktionen — keine Svelte-Imports, damit `node --experimental-strip-types --test`
// die Test-Datei laden kann.

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
	if (buckets.allThree > 0)         parts.push(`${buckets.allThree} alle drei Tage`);
	if (buckets.todayTomorrow > 0)    parts.push(`${buckets.todayTomorrow} nur heute + morgen`);
	if (buckets.onlyToday > 0)        parts.push(`${buckets.onlyToday} nur heute`);
	if (buckets.tomorrowDayAfter > 0) parts.push(`${buckets.tomorrowDayAfter} nur morgen + übermorgen`);
	if (buckets.other > 0)            parts.push(`${buckets.other} sonstige Kombinationen`);
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
