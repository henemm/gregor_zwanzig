// nextBriefingText — Issue #1969 (Nächstes Briefing), AC-16/AC-19/AC-21.
// Spec: docs/specs/modules/feat_1969_naechstes_briefing.md („Anzeige-Wortlaut")
//
// EIN Formatierer für den Backend-Wert `NextBriefing` (GET /api/next-briefings).
// Liefert nur den Wert („Do 29.10. 07:00 (CEST)", #2869), nie das Etikett — das setzt der
// jeweilige Konsument (VTNextBriefing, Startseite, Status-Zeile, Hub).
// Wochentag/Datum/Uhrzeit/Kürzel stammen ausschließlich aus local_date/local_time/
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

/**
 * #2869 AC-7: Kalendertag aus „YYYY-MM-DD"-Treffer als UTC-Date, nur wenn es den
 * Tag wirklich gibt (kein Weiterrechnen von 2026-13-99 / 2026-02-30). Sonst null.
 */
function kalenderTag(m: RegExpExecArray | null): Date | null {
	if (!m) return null;
	const [jahr, monat, tag] = [Number(m[1]), Number(m[2]), Number(m[3])];
	const d = new Date(Date.UTC(jahr, monat - 1, tag));
	if (d.getUTCFullYear() !== jahr || d.getUTCMonth() !== monat - 1 || d.getUTCDate() !== tag) return null;
	return d;
}

/**
 * #2869: Termin-Tag eines Ortstags „YYYY-MM-DD" — immer Wochentag + Datum,
 * zonenfrei aus `local_date` (nie aus `at`/Browser-Zone, ADR-0051).
 * de „So 08.11." (Wochentag aus dem Katalog per getUTCDay, Datum per
 * String-Zerlegung), en „Sun 8 Nov" (fmtDate kurz, 12 Uhr Ortszeit). null bei Unfug.
 */
function terminTag(localDate: string | undefined): string | null {
	const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(localDate ?? '');
	const d = kalenderTag(m);
	if (!m || !d) return null;
	const [jahr, monat, tag] = [Number(m[1]), Number(m[2]), Number(m[3])];
	const wt = d.getUTCDay();
	if (get(locale) === 'en') return fmtDate(new Date(jahr, monat - 1, tag, 12), 'en', 'kurz');
	// i18n-dynamic: versand.wochentag.
	return `${tr(`versand.wochentag.${wt}` as MessageKey)} ${m[3]}.${m[2]}.`;
}

/** „2026-10-28" → de „28.10." per String-Zerlegung, en „Wed 28 Oct" (12 Uhr Ortszeit, zonenfest). */
function tagMonat(isoDate: string): string | null {
	const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(isoDate);
	if (!m || !kalenderTag(m)) return null;
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
	const wt = terminTag(nb.local_date);
	if (!wt || !/^\d{2}:\d{2}$/.test(nb.local_time ?? '') || !nb.tz_abbr) return '—';
	let out = `${wt} ${nb.local_time} (${nb.tz_abbr})`;
	if (nb.skipped) {
		const swt = terminTag(nb.skipped.local_date);
		if (swt) out += ` — ${tr('versand.naechstes.uebersprungen', { termin: `${swt} ${nb.skipped.local_time}` })}`;
	}
	if (nb.overdue === true) out += ` — ${tr('versand.naechstes.nachgeholt')}`;
	return out;
}
