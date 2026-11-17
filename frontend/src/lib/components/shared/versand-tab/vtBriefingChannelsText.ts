// vtBriefingChannelsText.ts — Issue #1719 Scheibe S3 (Adversary-Fund F002,
// BROKEN, verifiziert nach GREEN, 2026-08-11): die Hinweistexte von
// VTBriefingChannels.svelte ("Geplantes Briefing · Kanäle") waren bislang
// nur inline im Svelte-Script definiert — ohne Renderharness nicht als reine
// Funktion pruefbar. AC-5 (keine Wertung) deckte per `ltCapNoteText` nur den
// Trip-Kanal-Reiter (LayoutTab) ab, NICHT den Versand-Reiter — ausgerechnet
// die Stelle, an der die urspruengliche Bevormundung stand ("SMS läuft
// flach"). Extrahiert analog channelConnectionStatus.ts/
// channelContactLabel.ts/premiumSmsChannelState.ts (bereits geteilte
// Ableitungen im selben Verzeichnis, gleiches Muster).
//
// Spec: docs/specs/modules/fix_1719_s3_aus_ist_ein_zustand.md AC-5a

import { CHANNEL_COL_BUDGET } from '$lib/components/trip-detail/metricsEditor';
import { SMS_TRIP_CHAR_LIMIT, SMS_COMPARE_CHAR_LIMIT } from '$lib/components/shared/layout-tab/ltChannels';
import { tr } from '../../../i18n/index.ts';

export type VtBriefingContext = 'route' | 'vergleich';

/** SMS-Zeichengrenze je Ausgabeweg — Trip 160, Vergleich 153 (Spec Abschnitt 5). */
export function vtBriefingSmsCharLimit(context: VtBriefingContext): number {
	return context === 'vergleich' ? SMS_COMPARE_CHAR_LIMIT : SMS_TRIP_CHAR_LIMIT;
}

/** Einleitungstext oberhalb der Kanal-Liste — keine Wertung (AC-5/AC-5a). */
export function vtBriefingLeadText(context: VtBriefingContext): string {
	// #2655 (F6): je Kontext ein ganzer Satz im Katalog (keine Satz-Konkatenation).
	const telegram_spalten = CHANNEL_COL_BUDGET.telegram;
	if (context === 'vergleich') return tr('versand.briefing.lead.vergleich', { platz: telegram_spalten + 1 }); // #3047 R8 (AC-24): ab Platz 8 zweite Zeile je Ort
	return tr('versand.briefing.lead.route', { telegram_spalten });
}

/** #3047 R8 (AC-24): Telegram-Unterzeile je Kontext — Trip: Etappen-Tabelle mit
 *  7 Spalten (narrow.py); Orts-Vergleich: alle Zeilen, ab Platz 8 eine zweite
 *  Zeile je Ort (comparison.py). Daten je Kontext statt Verzweigung. */
const TELEGRAM_SUB: Record<VtBriefingContext, () => string> = {
	route: () => tr('versand.briefing.sub.telegram', { telegram_spalten: CHANNEL_COL_BUDGET.telegram }),
	vergleich: () => tr('versand.briefing.sub.telegram_vergleich', { platz: CHANNEL_COL_BUDGET.telegram + 1 })
};

/** Kanal-Unterzeile je Kanal (Layout-Hinweis) — keine Wertung (AC-5/AC-5a). */
export function vtBriefingSubTexts(
	context: VtBriefingContext,
	telegramStyle: 'rich' | 'kurzform' = 'rich'
): { email: string; telegram: string; sms: string } {
	// Issue #2455: Telegram-Kurzform uebernimmt die SMS-Auswahl 1:1.
	return {
		email: tr('versand.briefing.sub.email'),
		telegram:
			telegramStyle === 'kurzform'
				? tr('versand.briefing.sub.telegram_kurzform')
				: TELEGRAM_SUB[context](),
		sms: tr('versand.briefing.sub.sms', { zeichen: vtBriefingSmsCharLimit(context) })
	};
}
