// nextBriefingText — Issue #1969 (Nächstes Briefing), AC-16/AC-19/AC-21.
// Spec: docs/specs/modules/feat_1969_naechstes_briefing.md („Anzeige-Wortlaut")
//
// EIN Formatierer für den Backend-Wert `NextBriefing` (GET /api/next-briefings).
// Liefert nur den Wert („Do 07:00 (CEST)"), nie das Etikett — das setzt der
// jeweilige Konsument (VTNextBriefing, Startseite, Status-Zeile, Hub).
// Wochentag/Uhrzeit/Kürzel stammen ausschließlich aus local_date/local_time/
// tz_abbr — nie aus `at` in Browser-Zone (ADR-0051 Regel 2/3).
//
// Pure Funktion, relative Importe — node:testbar.
// #2655 (F6): Wortlaut aus dem Katalog `versand.naechstes.*` / `versand.wochentag.<n>`
// in der aktuellen Sprache (Wochentag weiter zonenfrei per getUTCDay, Annahme A3).

import { get } from 'svelte/store';
import { tr, locale, type MessageKey } from '../../../i18n/index.ts';
import { fmtDate } from '../../../i18n/format.ts';

export type NextBriefingReason = 'manual' | 'paused' | 'disabled' | 'ended' | 'none';

export interface NextBriefing {
	at: string | null;
	local_date?: string;
	local_time?: string;
	tz?: string;
	tz_abbr?: string;
	slot?: 'morning' | 'evening';
	skipped?: { local_date: string; local_time: string; slot: 'morning' | 'evening' };
	overdue?: boolean;
	reason?: NextBriefingReason;
	paused_until?: string;
	/** #2346 S4: Zeitpunkt des letzten versendeten Briefings (Briefing-Log), `null` = nie. */
	last_briefing?: string | null;
}

/** Wochentag eines Ortstags „YYYY-MM-DD" — zonenfrei (UTC-Kalender), null bei Unfug. */
function wochentag(localDate: string | undefined): string | null {
	const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(localDate ?? '');
	if (!m) return null;
	const tag = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]))).getUTCDay();
	// i18n-dynamic: versand.wochentag.
	return Number.isNaN(tag) ? null : tr(`versand.wochentag.${tag}` as MessageKey);
}

/** „2026-10-28" → de „28.10." per String-Zerlegung, en „Wed 28 Oct" (12 Uhr Ortszeit, zonenfest). */
function tagMonat(isoDate: string): string | null {
	const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(isoDate);
	if (!m) return null;
	if (get(locale) === 'en') return fmtDate(new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]), 12), 'en', 'kurz');
	return `${m[3]}.${m[2]}.`;
}

/** Schluessel „beendet" je Abo-Art (Datentabelle statt Verzweigung). */
const BEENDET: Record<'route' | 'vergleich', MessageKey> = {
	route: 'versand.naechstes.beendet.route',
	vergleich: 'versand.naechstes.beendet.vergleich'
};

function grundText(nb: NextBriefing, context: 'route' | 'vergleich'): string {
	switch (nb.reason) {
		case 'paused': {
			const bis = nb.paused_until ? tagMonat(nb.paused_until) : null;
			return bis ? tr('versand.naechstes.pausiert_bis', { bis }) : tr('versand.naechstes.pausiert');
		}
		case 'ended':
			return tr(BEENDET[context] ?? BEENDET.route);
		case 'manual':
			return tr('versand.naechstes.grund.manual');
		case 'disabled':
			return tr('versand.naechstes.grund.disabled');
		case 'none':
			return tr('versand.naechstes.grund.none');
		default:
			return '—';
	}
}

/**
 * Anzeige-Wert eines `NextBriefing`. Nicht geladen / Fehler / kaputtes Objekt
 * ⇒ „—" (AC-19) — nie eine erfundene Zeit.
 */
export function formatNextBriefing(
	nb: NextBriefing | null | undefined,
	context: 'route' | 'vergleich' = 'route'
): string {
	if (!nb || typeof nb !== 'object') return '—';
	if (nb.at == null) return grundText(nb, context);
	const wt = wochentag(nb.local_date);
	if (!wt || !/^\d{2}:\d{2}$/.test(nb.local_time ?? '') || !nb.tz_abbr) return '—';
	let out = `${wt} ${nb.local_time} (${nb.tz_abbr})`;
	if (nb.skipped) {
		const swt = wochentag(nb.skipped.local_date);
		if (swt) out += ` — ${tr('versand.naechstes.uebersprungen', { termin: `${swt} ${nb.skipped.local_time}` })}`;
	}
	if (nb.overdue === true) out += ` — ${tr('versand.naechstes.nachgeholt')}`;
	return out;
}
