// Die vom PO freigegebenen deutschen Texte (Spec begriff_erklaerung_infobox.md,
// Abschnitt „Festgelegte Texte") als LITERALE.
//
// Absicht: Die Tests duerfen ihre Soll-Texte NICHT aus dem Katalog lesen, den sie
// pruefen — sonst bestaetigt sich der Katalog selbst. Aendert jemand einen Text
// in de.json, wird der Test rot, bis die Freigabe nachgezogen ist.

import type { InfoboxAbschnitt } from '../infoboxKeys.ts';

export type Kontext = 'route' | 'vergleich';

/** `info.<reiter>.<kontext>` -> freigegebener Text. */
export const INFO_TEXTE: Record<string, string> = {
	'info.wetter-metriken.route':
		'Kannst du überspringen — Standard: die vom System vorgewählten Wetter-Metriken.',
	'info.wetter-metriken.vergleich':
		'Kannst du überspringen — Standard: die vom System vorgewählten Metriken, dazu Stundenverlauf und 3-Tages-Ausblick (beide an).',
	'info.wertebereiche.route':
		'Kannst du überspringen — Standard: keine Wertebereiche, im Briefing wird nichts hervorgehoben.',
	'info.wertebereiche.vergleich':
		'Kannst du überspringen — Standard: die Wertebereiche werden aus dem Aktivitätsprofil vorbelegt.',
	'info.alarme.route':
		'Kannst du überspringen — Standard: Alarme per E-Mail und Telegram, Dringlichkeits-Schwelle „gering“, amtliche Warnungen aus. Telegram wirkt erst nach der Verknüpfung.',
	'info.alarme.vergleich':
		'Kannst du überspringen — Standard: Alarme per E-Mail und Telegram, Dringlichkeits-Schwelle „gering“, amtliche Warnungen aus. Telegram wirkt erst nach der Verknüpfung.',
	'info.versand.route':
		'Kannst du überspringen — Standard: E-Mail, Morgen-Briefing um 07:00 Uhr und Abend-Briefing um 18:00 Uhr.',
	'info.versand.vergleich':
		'Kannst du überspringen — Standard: E-Mail, Morgen-Briefing um 07:00 Uhr, kein Enddatum.',
	'info.wegpunkte.route': 'Kannst du überspringen — Standard: keine zusätzlichen Wegpunkte.'
};

export const TIP_TEXTE: Record<string, string> = {
	'tip.wertebereiche':
		'Ein Wertebereich legt für eine Metrik fest, welche Werte als passend gelten. Werte im Bereich werden im Briefing hervorgehoben.',
	'tip.kanal_schwelle':
		'Die Dringlichkeits-Schwelle legt je Kanal fest, ab welcher Stufe (gering, mittel, hoch) eine Meldung über diesen Kanal kommt.',
	'tip.cape':
		'CAPE (Gewitterenergie) misst in J/kg, wie viel Energie in der Luft für Gewitter steckt. Der Schwellwert ist ein Richtwert und wird je Wettermodell und Gebiet umgerechnet.',
	'tip.cooldown': 'Der Cooldown ist der Mindestabstand in Minuten zwischen zwei Meldungen derselben Metrik.'
};

/** Begriffe, zu denen ein `tip.aria.<begriff>`-Schluessel gehoert. */
export const BEGRIFFE = ['wertebereiche', 'kanal_schwelle', 'cape', 'cooldown'] as const;
export type Begriff = (typeof BEGRIFFE)[number];

/** Wort, das der Knopfname (`tip.aria.<begriff>`) nennen muss. */
export const ARIA_WORT: Record<Begriff, RegExp> = {
	wertebereiche: /Wertebereich/,
	kanal_schwelle: /Dringlichkeits-Schwelle/,
	cape: /CAPE/,
	cooldown: /Cooldown/
};

/** Die Infobox-Schluessel je Kontext (Pflichtreiter bewusst nicht dabei). Seit #1743 ist
 *  `versand` kein Reiter mehr, sondern ein ABSCHNITT im Reiter Wetter-Metriken — der Schluessel
 *  bleibt; in welchem Reiter er steht, sagt `REITER_DES_ABSCHNITTS`. */
export const REITER_MIT_INFOBOX: Record<Kontext, string[]> = {
	route: ['wetter-metriken', 'wertebereiche', 'alarme', 'versand', 'wegpunkte'],
	vergleich: ['wetter-metriken', 'wertebereiche', 'alarme', 'versand']
};

/** Issue #1743 (AC-19/AC-22): der Reiter, in dem der Infobox-Schluessel beim Anlegen offen ist.
 *  Der Typ `InfoboxAbschnitt` (vormals `InfoboxReiter`) wird hier bewusst referenziert — svelte-check
 *  bewacht damit die Umbenennung (AC-22). */
export const REITER_DES_ABSCHNITTS: Record<InfoboxAbschnitt, string> = {
	'wetter-metriken': 'wetter-metriken',
	wertebereiche: 'wertebereiche',
	alarme: 'alarme',
	versand: 'wetter-metriken',
	wegpunkte: 'wegpunkte'
};

export const PFLICHTREITER: Record<Kontext, string[]> = {
	route: ['route', 'etappen'],
	vergleich: ['vergleich', 'orte']
};
