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
	// Kanaele (VTBriefingChannels)
	['versand.kanaele.titel', 'Geplantes Briefing · Kanäle', 'Planned briefing · channels'],
	['versand.kanal.email_fehlt', 'E-Mail-Adresse fehlt — <link>', 'Email address missing — <link>'],
	['versand.kanal.telegram_fehlt', 'Telegram-Chat-ID fehlt — <link>', 'Telegram chat ID missing — <link>'],
	['versand.kanal.nummer_fehlt', 'Handynummer fehlt — <link>', 'Mobile number missing — <link>'],
	['versand.kanal.im_account_einrichten', 'im Account einrichten', 'set it up in your account'],
	['versand.kanal.nummer_unbestaetigt', 'Nummer noch nicht bestätigt — <link>', 'Number not confirmed yet — <link>'],
	['versand.kanal.code_eingeben', 'Code im Account eingeben', 'enter the code in your account'],
	['versand.kanal.sms_ab_standard', 'SMS ab Level Standard verfügbar', 'SMS is available from the Standard level'],
	['versand.kanal.bald_verfuegbar', 'bald verfügbar', 'coming soon'],
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
	// Einleitung und Unterzeilen (vtBriefingChannelsText)
	[
		'versand.briefing.lead.route',
		'Das Trip-Briefing ist eine Etappen-Tabelle — E-Mail trägt alle Spalten, Telegram die ersten <telegram_spalten>, SMS kein Raster, Fließtext.',
		'The trip briefing is a stage table — email carries all columns, Telegram the first <telegram_spalten>, SMS has no grid, plain text.'
	],
	[
		'versand.briefing.lead.vergleich',
		'Der Orts-Vergleich ist eine breite Tabelle — realistisch läuft er per E-Mail. Telegram trägt nur ≤ <telegram_spalten> Spalten, SMS kein Raster, Fließtext.',
		'The location comparison is a wide table — in practice it goes by email. Telegram carries only ≤ <telegram_spalten> columns, SMS has no grid, plain text.'
	],
	['versand.briefing.sub.email', 'Layout · volle Tabelle', 'Layout · full table'],
	['versand.briefing.sub.telegram', 'Layout · <telegram_spalten> Spalten', 'Layout · <telegram_spalten> columns'],
	['versand.briefing.sub.telegram_kurzform', 'folgt der SMS-Auswahl', 'follows the SMS selection'],
	['versand.briefing.sub.sms', 'Layout · kein Raster, <zeichen> Zeichen', 'Layout · no grid, <zeichen> characters'],
	// Zeitplan (VTSchedulePlan)
	['versand.zeitplan.titel', 'Briefing-Zeitplan', 'Briefing schedule'],
	['versand.zeitplan.kein_kanal', 'Kein Kanal aktiv.', 'No channel active.'],
	['versand.zeitplan.kein_kanal_text', 'Aktiviere oben mindestens einen Briefing-Kanal, damit hier Zeitplan-Optionen erscheinen.', 'Turn on at least one briefing channel above to see schedule options here.'],
	['versand.zeitplan.vergleich_intro', 'Wie beim Trip: das <morgen> zeigt den heutigen Tag, das <abend> den morgigen. Du wählst nur die Uhrzeit.', 'As with a trip: the <morgen> shows today, the <abend> shows tomorrow. You only choose the time.'],
	['versand.zeitplan.morgen', 'Morgen-Briefing', 'Morning briefing'],
	['versand.zeitplan.morgen_sub', 'Gleicher Tag — alles für die heutige Etappe', 'Same day — everything for today’s stage'],
	['versand.zeitplan.abend', 'Abend-Briefing', 'Evening briefing'],
	['versand.zeitplan.abend_sub', 'Nächster Tag — Ausblick auf morgen', 'Next day — outlook for tomorrow'],
	['versand.zeitplan.aktiv', 'Aktiv', 'Active'],
	['versand.zeitplan.uhrzeit', 'Uhrzeit', 'Time'],
	['versand.zeitplan.morgens', 'Morgens <zeit>', 'Morning <zeit>'],
	['versand.zeitplan.abends', 'Abends <zeit>', 'Evening <zeit>'],
	['versand.zeitplan.trend', 'Mehrtages-Trend', 'Multi-day trend'],
	['versand.zeitplan.trend_sub', 'Sonntags · 3–7-Tage-Ausblick (optional)', 'Sundays · 3–7-day outlook (optional)'],
	['versand.zeitplan.im_morgen', 'im Morgen-Briefing', 'in the morning briefing'],
	['versand.zeitplan.im_abend', 'im Abend-Briefing', 'in the evening briefing'],
	// Laufzeit (VTLaufzeitRoute / VTLaufzeitVergleich)
	['versand.laufzeit.titel', 'Laufzeit', 'Duration'],
	['versand.laufzeit.route', 'Läuft mit der Trip · endet <ende>', 'Runs with the trip · ends <ende>'],
	['versand.laufzeit.route_sub', 'Das Enddatum ergibt sich aus den Etappen — es wird dort gepflegt, nicht hier.', 'The end date comes from the stages — it is maintained there, not here.'],
	['versand.laufzeit.etappen_oeffnen', 'Etappen öffnen →', 'Open stages →'],
	['versand.laufzeit.offen', 'Bis auf Weiteres', 'Until further notice'],
	['versand.laufzeit.bis_datum', 'Bis Datum', 'Until a date'],
	['versand.laufzeit.ohne_ende', 'Der Versand läuft ohne Enddatum weiter.', 'Delivery continues without an end date.'],
	// Naechstes Briefing (VTNextBriefing / nextBriefingText)
	['versand.naechstes.titel', 'Nächstes Briefing', 'Next briefing'],
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
		'Telegram bekommt denselben kurzen Ein-Zeilen-Text wie SMS, ohne Knöpfe. Inhalt und Werte folgen der SMS-Auswahl im Layout-Reiter; die Telegram-Auswahl gilt nur für das ausführliche Telegram.',
		'Telegram gets the same short one-line text as SMS, without buttons. Content and values follow the SMS selection in the Layout tab; the Telegram selection only applies to the detailed Telegram message.'
	],
	['telegram_kurzstil.hinweis_inaktiv', 'Erst aktiv, wenn Telegram als Kanal an ist.', 'Only active when Telegram is switched on as a channel.']
];
