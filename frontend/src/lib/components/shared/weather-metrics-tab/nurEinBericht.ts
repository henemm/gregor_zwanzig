// nurEinBericht.ts — #3047 N3: Altbestand `morning_enabled`/`evening_enabled`
// je Trip-Metrik (display_config.metrics). Der Editor bietet die Flags nicht an,
// bewahrt sie beim Speichern (Read-Modify-Write, buildWeatherConfigMetrics) und
// kennzeichnet bis Phase 2 (#3065) je Metrik, wenn sie nur in EINEM Bericht
// erscheint.
//
// Semantik exakt wie die Mail (src/app/models.py::_filter_metrics_by_report_type):
// je Bericht gilt das Bericht-Flag, wenn es `true`/`false` ist, sonst `enabled`
// (fehlend = true, wie der Loader).

export type NurBericht = 'morgens' | 'abends';

export interface BerichtFlags {
	metric_id: string;
	enabled?: boolean;
	morning_enabled?: boolean | null;
	evening_enabled?: boolean | null;
}

function imBericht(flag: boolean | null | undefined, an: boolean): boolean {
	if (flag === true) return true;
	if (flag === false) return false;
	return an;
}

/** `an` = der Grundauswahl-Stand im Editor (wird beim Speichern zu `enabled`). */
export function nurEinBericht(eintrag: BerichtFlags, an: boolean): NurBericht | null {
	const morgens = imBericht(eintrag.morning_enabled, an);
	const abends = imBericht(eintrag.evening_enabled, an);
	if (morgens && !abends) return 'morgens';
	if (abends && !morgens) return 'abends';
	return null;
}

/** Kennzeichnung je Kennung fuer die gespeicherten Eintraege; `aktiv` = die
 *  Grundauswahl des Editors (`buckets.primary`). Ohne Bericht-Flag kein Eintrag. */
export function nurEinBerichtJeMetrik(
	bestand: ReadonlyArray<BerichtFlags> | null | undefined,
	aktiv: readonly string[]
): Record<string, NurBericht> {
	const out: Record<string, NurBericht> = {};
	for (const eintrag of bestand ?? []) {
		const nur = nurEinBericht(eintrag, aktiv.includes(eintrag.metric_id));
		if (nur) out[eintrag.metric_id] = nur;
	}
	return out;
}
