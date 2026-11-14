// Issue #2795 S3b, Teilschritt 1b (AC-30, Uebergangsblock): Telegram-Kurzstil und (nur Trip)
// Mehrtages-Trend. Beide sassen bisher im alten Versand-Abschnitt (Trip: `report_config`) bzw. im
// Alarm-Baustein (Orte: `display_config.telegram_style`), die der neue Reiter abloest. Bis Teil 2
// („Inhalt je Kanal“ im Reiter Wetter) bleiben sie im Uebergangsblock bedienbar und speichern
// dieselben Felder wie vorher — unter eigenem Owner 'kanal-stil', damit sie den Reiter-Speicherer
// (Owner 'versand'/'alarme', zustellungSpeicherung.ts) nie verdraengen. Wird mit Teil 2 abgebaut.
//
// Kein Browser-/SvelteKit-Import — lauffaehig unter node --experimental-strip-types.

import type { SaveFn, SaveStatus } from '../../../stores/saveStatusStore.svelte.ts';
import { merkeNutzlast } from '../../../stores/nutzlastStand.ts';
import type { ComparePreset, Trip } from '../../../types.ts';
import type { PutClient } from '../tripSpeicherung.ts';
import { ladeReportZustand } from '../versand-tab/reportConfigPayload.ts';
import type { Kontext } from './zustellungModell.ts';

export interface KanalStilStand {
	stil: 'rich' | 'kurzform';
	trendMorgen: boolean;
	trendAbend: boolean;
}

/** Mehrtages-Trend gibt es nur im Trip (VTSchedulePlan, KL-2). */
export const MIT_TREND: Record<Kontext, boolean> = { route: true, vergleich: false };

function tripStart(trip?: Trip): KanalStilStand {
	const z = ladeReportZustand(trip?.report_config as Record<string, unknown> | undefined);
	return { stil: z.telegram_style ?? 'rich', trendMorgen: z.multi_day_trend_morning, trendAbend: z.multi_day_trend_evening };
}

function tripNutzlast(s: KanalStilStand): Record<string, unknown> {
	const reports: string[] = [];
	if (s.trendMorgen) reports.push('morning');
	if (s.trendAbend) reports.push('evening');
	return {
		report_config: {
			telegram_style: s.stil,
			multi_day_trend_morning: s.trendMorgen,
			multi_day_trend_evening: s.trendAbend,
			multi_day_trend_reports: reports
		}
	};
}

/** Kontext-Unterschiede als Daten (Ratsche context_herkunft_zweige_eingefroren). */
const KONTEXT: Record<
	Kontext,
	{ start: (trip?: Trip, preset?: ComparePreset) => KanalStilStand; nutzlast: (s: KanalStilStand) => Record<string, unknown>; pfad: (id: string) => string }
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

/** Nutzlast wie bisher: Trip unter report_config (Kurzstil + Trend), Orte display_config.telegram_style. */
export function kanalStilNutzlast(context: Kontext, s: KanalStilStand): Record<string, unknown> {
	return KONTEXT[context].nutzlast(s);
}

export function erstelleKanalStilSpeicherung(opt: {
	context: Kontext;
	id: string;
	client: PutClient;
	saveController: SaveStatus;
	enqueueHubWrite?: <T>(fn: () => Promise<T>) => Promise<T>;
	onAntwort?: (antwort: unknown) => void;
}): { aenderungMelden(s: KanalStilStand): void } {
	const pfad = KONTEXT[opt.context].pfad(opt.id);
	let aktuell: KanalStilStand | null = null;
	const fn: SaveFn = async (init) => {
		const lauf = async () => {
			if (!aktuell) return;
			const body = kanalStilNutzlast(opt.context, aktuell);
			merkeNutzlast(fn, body);
			// PUT getrennt abwarten: `opt.onAntwort?.(await …)` wertete das Argument (den PUT) bei
			// fehlendem onAntwort gar nicht aus (Optional-Call schliesst kurz) — Fix-Loop 1, F004.
			const antwort = await opt.client.put<unknown>(pfad, body, init);
			opt.onAntwort?.(antwort);
		};
		await (opt.enqueueHubWrite ? opt.enqueueHubWrite(lauf) : lauf());
	};
	return {
		aenderungMelden(s: KanalStilStand): void {
			aktuell = { ...s };
			opt.saveController.schedule(fn, 700, 'kanal-stil');
		}
	};
}
