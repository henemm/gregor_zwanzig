// Issue #2655 (i18n F6) — feste Literal-Anker fuer JEDEN Katalogwert des Pakets
// (versand.* und telegram_kurzstil.*): Schluessel -> de | en, Platzhalter als
// <name> eingesetzt. Die deutschen Literale sind gegen den Wortlaut in
// origin/main (Quelltexte VOR der Umstellung, Commit 96cfde332) abgeglichen:
// VTBriefingChannels/VTSchedulePlan/VTLaufzeit*/VTNextBriefing.svelte,
// TelegramKurzstilToggle.svelte, channelConnectionStatus.ts, premiumSmsChannelState.ts,
// sendTargetLabel.ts, vtBriefingChannelsText.ts, nextBriefingText.ts. Saetze mit
// Hervorhebung/Link stehen mit Platzhalter (<morgen>, <link>) an der Stelle des
// Elements. NICHT aus dem Katalog nachziehen: eine Abweichung ist ein Befund.
// Verwendet in versand_tab_sprache.test.ts (Wertvergleich + statischer Gegencheck).

export const F6_ANKER: [schluessel: string, de: string, en: string][] = [
	// #3385: versand.kanaele.*, versand.kanal.*, versand.briefing.*, versand.zeitplan.*,
	// versand.laufzeit.* und versand.naechstes.titel entfallen mit den geloeschten Bausteinen
	// (VTBriefingChannels, vtBriefingChannelsText, VTSchedulePlan, VTLaufzeit*, VTNextBriefing).
	// Verbindungsstatus (channelConnectionStatus)
	['versand.status.nicht_verbunden', 'nicht verbunden', 'not connected'],
	['versand.status.bestaetigt', 'bestätigt', 'confirmed'],
	['versand.status.nicht_bestaetigt', 'nicht bestätigt', 'not confirmed'],
	['versand.status.verbunden', 'verbunden', 'connected'],
	['versand.status.hinterlegt', 'hinterlegt', 'on file'],
	['versand.status.eingetragen_unbestaetigt', 'eingetragen, unbestätigt', 'entered, unconfirmed'],
	// Premium-SMS (premiumSmsChannelState)
	['versand.premium_sms.nicht_verfuegbar', 'nicht verfügbar', 'not available'],
	['versand.premium_sms.hinweis.nicht_verfuegbar', 'Premium-SMS ab Level Premium verfügbar', 'Premium SMS is available from the Premium level'],
	['versand.premium_sms.gelernt', 'gelernt', 'learned'],
	['versand.premium_sms.hinweis.gelernt', 'Das Gerät hat sich gemeldet — Briefings gehen an die gelernte Rückadresse.', 'The device has reported in — briefings go to the learned reply address.'],
	['versand.premium_sms.verfallen', 'verfallen', 'expired'],
	[
		'versand.premium_sms.hinweis.verfallen',
		'Rückadresse verfallen — Garmin kann die Nummer inzwischen einem fremden Gerät zugeteilt haben. Sobald sich das Gerät wieder meldet, ist der Kanal erneut nutzbar.',
		'Reply address expired — Garmin may have assigned the number to another device by now. As soon as the device reports in again, the channel can be used again.'
	],
	['versand.premium_sms.hinweis.nie_gemeldet', 'Das Gerät hat sich noch nie gemeldet — die Rückadresse wird beim ersten Empfang gelernt.', 'The device has never reported in — the reply address is learned on first receipt.'],
	['versand.premium_sms.zuletzt_gemeldet', 'zuletzt gemeldet am <datum>', 'last reported on <datum>'],
	// Naechstes Briefing (nextBriefingText)
	['versand.naechstes.pausiert', 'pausiert', 'paused'],
	['versand.naechstes.pausiert_bis', 'pausiert bis <bis>', 'paused until <bis>'],
	['versand.naechstes.beendet.route', 'Trip beendet', 'Trip ended'],
	['versand.naechstes.beendet.vergleich', 'Ortsvergleich beendet', 'Location comparison ended'],
	['versand.naechstes.grund.manual', 'nur manueller Versand', 'manual delivery only'],
	['versand.naechstes.grund.disabled', 'Briefings abgeschaltet', 'Briefings switched off'],
	['versand.naechstes.grund.none', 'kein Termin geplant', 'no time scheduled'],
	['versand.naechstes.uebersprungen', '<termin> wird übersprungen', '<termin> is skipped'],
	['versand.naechstes.nachgeholt', 'läuft jetzt / wird nachgeholt', 'running now / will be caught up'],
	['versand.wochentag.0', 'So', 'Sun'],
	['versand.wochentag.1', 'Mo', 'Mon'],
	['versand.wochentag.2', 'Di', 'Tue'],
	['versand.wochentag.3', 'Mi', 'Wed'],
	['versand.wochentag.4', 'Do', 'Thu'],
	['versand.wochentag.5', 'Fr', 'Fri'],
	['versand.wochentag.6', 'Sa', 'Sat'],
	// Sende-Ziel (sendTargetLabel, Dialog „Geht an …")
	['versand.ziel.unbekannt', 'Versandziel unbekannt — das Konto-Profil ist nicht verfügbar; es wird nichts gesendet.', 'Delivery target unknown — the account profile is not available; nothing is sent.'],
	['versand.ziel.keine_adresse', 'Im Konto ist keine E-Mail-Adresse hinterlegt — es kann nichts gesendet werden.', 'No email address is set in the account — nothing can be sent.'],
	['versand.ziel.unbestaetigt', 'Die Adresse <adresse> ist nicht bestätigt — es wird nichts zugestellt.', 'The address <adresse> is not confirmed — nothing is delivered.'],
	['versand.ziel.geht_an', 'Geht an <ziele>.', 'Goes to <ziele>.'],
	// Telegram-Kurzstil (bausteine.json, Bereich telegram_kurzstil.*)
	['telegram_kurzstil.checkbox', 'Telegram im SMS-Kurzstil', 'Telegram in SMS compact style'],
	[
		'telegram_kurzstil.hinweis_aktiv',
		'Telegram bekommt denselben kurzen Ein-Zeilen-Text wie SMS, ohne Knöpfe. Inhalt und Werte folgen der SMS-Auswahl im Reiter Zustellung; die Telegram-Auswahl gilt nur für das ausführliche Telegram.',
		'Telegram gets the same short one-line text as SMS, without buttons. Content and values follow the SMS selection in the Delivery tab; the Telegram selection only applies to the detailed Telegram message.'
	],
	['telegram_kurzstil.hinweis_inaktiv', 'Erst aktiv, wenn Telegram als Kanal an ist.', 'Only active when Telegram is switched on as a channel.']
];
