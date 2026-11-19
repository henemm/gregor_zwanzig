// Issue #2795 S3b, Teilschritt 1b (AC-30): Telegram-Kurzstil und (nur Trip) Mehrtages-Trend — Lesen des
// gespeicherten Stands und Formen der Teilfeld-Nutzlast (Trip `report_config`, Orte
// `display_config.telegram_style`).
// Issue #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 14): die Bedienung im Uebergangsblock
// (KanalStil, eigener Speicherer mit Owner 'kanal-stil') ist entfernt. Den Kurzstil schaltet allein die Karte
// „Was steht wo“ (wasStehtWoSpeicherung.ts formt ihre Nutzlast hier); den Ausblick je Briefing schreibt die
// Karte als `outlook_reports`. `kanalStilStart` liest die Altfelder (`multi_day_trend_*`) weiter, bis B6 sie
// abbaut — die Gleichheits-Pruefungen ac26/p12 vergleichen damit Einstellung und Ausgabe.
//
// Kein Browser-/SvelteKit-Import — lauffaehig unter node --experimental-strip-types.

import type { ComparePreset, Trip } from '../../../types.ts';
import { ladeReportZustand } from '../versand-tab/reportConfigPayload.ts';
import type { Kontext } from './zustellungModell.ts';

export interface KanalStilStand {
	stil: 'rich' | 'kurzform';
	trendMorgen: boolean;
	trendAbend: boolean;
}

/** Gespeicherter Trip: der Trend steht, wie Python ihn liest (#3047 E2) — allein `multi_day_trend_reports`,
 *  fehlt die Liste, gilt ["evening"] (loader.py, Konzept §5 Punkt 8 „Vorbelegung: nur abends“). */
const PYTHON_TREND_STANDARD: readonly string[] = ['evening'];

function tripStart(trip?: Trip): KanalStilStand {
	const rc = trip?.report_config as Record<string, unknown> | undefined;
	const z = ladeReportZustand(rc);
	const trend = Array.isArray(rc?.multi_day_trend_reports) ? (rc.multi_day_trend_reports as string[]) : PYTHON_TREND_STANDARD;
	return { stil: z.telegram_style ?? 'rich', trendMorgen: trend.includes('morning'), trendAbend: trend.includes('evening') };
}

/** #3047 E2: mit `vorher` nur die geaenderten Felder — Kurzstil umschalten schreibt den Trend nicht mit. */
function tripNutzlast(s: KanalStilStand, vorher?: KanalStilStand): Record<string, unknown> {
	const reports: string[] = [];
	if (s.trendMorgen) reports.push('morning');
	if (s.trendAbend) reports.push('evening');
	const stil = !vorher || vorher.stil !== s.stil;
	const trend = !vorher || vorher.trendMorgen !== s.trendMorgen || vorher.trendAbend !== s.trendAbend;
	return {
		report_config: {
			...(stil ? { telegram_style: s.stil } : {}),
			...(trend ? { multi_day_trend_morning: s.trendMorgen, multi_day_trend_evening: s.trendAbend, multi_day_trend_reports: reports } : {})
		}
	};
}

/** Kontext-Unterschiede als Daten (Ratsche context_herkunft_zweige_eingefroren). */
const KONTEXT: Record<
	Kontext,
	{ start: (trip?: Trip, preset?: ComparePreset) => KanalStilStand; nutzlast: (s: KanalStilStand, vorher?: KanalStilStand) => Record<string, unknown>; pfad: (id: string) => string }
> = {
	route: { start: (trip) => tripStart(trip), nutzlast: tripNutzlast, pfad: (id) => `/api/trips/${id}` },
	vergleich: {
		start: (_trip, preset) => ({ stil: preset?.display_config?.telegram_style === 'kurzform' ? 'kurzform' : 'rich', trendMorgen: false, trendAbend: false }),
		nutzlast: (s) => ({ display_config: { telegram_style: s.stil } }),
		pfad: (id) => `/api/compare/presets/${id}`
	}
};

/** Startwerte aus dem gespeicherten Abo (Trip: report_config, Orte: display_config). */
export function kanalStilStart(context: Kontext, trip?: Trip, preset?: ComparePreset): KanalStilStand {
	return KONTEXT[context].start(trip, preset);
}

/** Nutzlast: Trip unter report_config (Kurzstil + Trend), Orte display_config.telegram_style.
 *  `vorher` = zuletzt gespeicherter Stand: der Trip sendet dann nur, was sich geaendert hat (#3047 E2). */
export function kanalStilNutzlast(context: Kontext, s: KanalStilStand, vorher?: KanalStilStand): Record<string, unknown> {
	return KONTEXT[context].nutzlast(s, vorher);
}
