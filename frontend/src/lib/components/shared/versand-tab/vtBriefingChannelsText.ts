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

export type VtBriefingContext = 'route' | 'vergleich';

/** SMS-Zeichengrenze je Ausgabeweg — Trip 160, Vergleich 153 (Spec Abschnitt 5). */
export function vtBriefingSmsCharLimit(context: VtBriefingContext): number {
	return context === 'vergleich' ? SMS_COMPARE_CHAR_LIMIT : SMS_TRIP_CHAR_LIMIT;
}

/** Einleitungstext oberhalb der Kanal-Liste — keine Wertung (AC-5/AC-5a). */
export function vtBriefingLeadText(context: VtBriefingContext): string {
	if (context === 'vergleich') {
		return (
			'Der Orts-Vergleich ist eine breite Tabelle — realistisch läuft er per E-Mail. ' +
			`Telegram trägt nur ≤ ${CHANNEL_COL_BUDGET.telegram} Spalten, SMS kein Raster, Fließtext.`
		);
	}
	return (
		'Das Trip-Briefing ist eine Etappen-Tabelle — E-Mail trägt alle Spalten, ' +
		`Telegram die ersten ${CHANNEL_COL_BUDGET.telegram}, SMS kein Raster, Fließtext.`
	);
}

/** Kanal-Unterzeile je Kanal (Layout-Hinweis) — keine Wertung (AC-5/AC-5a). */
export function vtBriefingSubTexts(context: VtBriefingContext): { email: string; telegram: string; sms: string } {
	return {
		email: 'Layout · volle Tabelle',
		telegram: `Layout · ${CHANNEL_COL_BUDGET.telegram} Spalten`,
		sms: `Layout · kein Raster, ${vtBriefingSmsCharLimit(context)} Zeichen`
	};
}
