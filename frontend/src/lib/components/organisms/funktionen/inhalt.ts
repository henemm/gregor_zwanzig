// Issue #3319 / #3320 (AC-6/AC-8) — Inhalt der oeffentlichen Funktionsseiten:
// je Inventarpunkt Absaetze, optionaler Level-Hinweis und Bilder. Welche
// Inventarpunkte auf welcher Unterseite stehen, legt allein
// `$lib/funktionen_seiten` fest. Alle Texte als Katalogschluessel (funktionen.*).
// Die Bilddateien liegen je Sprache unter static/funktionen/ bzw.
// static/funktionen/en/; ihre Masse schreiben die Bild-Skripte nach
// bildmasse.json (scripts/landing_screenshots.py --funktionen,
// scripts/funktionen_screenshots.py, Runbook docs/runbooks/funktionen_screenshots.md).
import type { MessageKey } from '$lib/i18n';
import type { FunktionenSlug, InventarId } from '$lib/funktionen_seiten';
import bildmasse from './bildmasse.json' with { type: 'json' };

export type BildName =
	| 'cockpit'
	| 'trip-anlegen'
	| 'trip-hub'
	| 'archiv'
	| 'briefing-mail'
	| 'briefing-telegram'
	| 'trip-wetter'
	| 'alarm-mail'
	| 'ortsvergleich'
	| 'konto-kanaele'
	| 'briefing-sms'
	| 'premium-sms'
	| 'trip-zustellung'
	| 'befehle-mail'
	| 'briefing-quelle'
	| 'konto-level';

export type Bild = { name: BildName; alt: MessageKey; caption: MessageKey };

export type InventarInhalt = {
	titel: MessageKey;
	absaetze: readonly MessageKey[];
	/** Hinweis „Verfuegbar in“, wo das Level eine Rolle spielt. */
	verfuegbar?: MessageKey;
	bilder: readonly Bild[];
};

const bild = (name: BildName, schluessel: string): Bild => ({
	name,
	alt: `funktionen.bild.${schluessel}.alt` as MessageKey,
	caption: `funktionen.bild.${schluessel}.caption` as MessageKey
});

// i18n-dynamic: funktionen.bild.
const BILD: Record<BildName, Bild> = {
	cockpit: bild('cockpit', 'cockpit'),
	'trip-anlegen': bild('trip-anlegen', 'trip_anlegen'),
	'trip-hub': bild('trip-hub', 'trip_hub'),
	archiv: bild('archiv', 'archiv'),
	'briefing-mail': bild('briefing-mail', 'briefing_mail'),
	'briefing-telegram': bild('briefing-telegram', 'briefing_telegram'),
	'trip-wetter': bild('trip-wetter', 'trip_wetter'),
	'alarm-mail': bild('alarm-mail', 'alarm_mail'),
	ortsvergleich: bild('ortsvergleich', 'ortsvergleich'),
	'konto-kanaele': bild('konto-kanaele', 'konto_kanaele'),
	'briefing-sms': bild('briefing-sms', 'briefing_sms'),
	'premium-sms': bild('premium-sms', 'premium_sms'),
	'trip-zustellung': bild('trip-zustellung', 'trip_zustellung'),
	'befehle-mail': bild('befehle-mail', 'befehle_mail'),
	'briefing-quelle': bild('briefing-quelle', 'briefing_quelle'),
	'konto-level': bild('konto-level', 'konto_level')
};

export const INVENTAR: Record<InventarId, InventarInhalt> = {
	cockpit: { titel: 'funktionen.cockpit.titel', absaetze: ['funktionen.cockpit.text'], bilder: [BILD.cockpit] },
	trip_anlegen: {
		titel: 'funktionen.trip_anlegen.titel',
		absaetze: ['funktionen.trip_anlegen.text'],
		verfuegbar: 'funktionen.trips.verfuegbar',
		bilder: [BILD['trip-anlegen']]
	},
	trip_hub: { titel: 'funktionen.trip_hub.titel', absaetze: ['funktionen.trip_hub.text'], bilder: [BILD['trip-hub']] },
	archiv: { titel: 'funktionen.archiv.titel', absaetze: ['funktionen.archiv.text'], bilder: [BILD.archiv] },
	briefings: {
		titel: 'funktionen.briefings.titel',
		absaetze: ['funktionen.briefings.text', 'funktionen.briefings.text2'],
		bilder: [BILD['briefing-mail'], BILD['briefing-telegram']]
	},
	wetter: {
		titel: 'funktionen.wetter.titel',
		absaetze: ['funktionen.wetter.text', 'funktionen.wetter.text2'],
		bilder: [BILD['trip-wetter']]
	},
	alarme: {
		titel: 'funktionen.alarme.titel',
		absaetze: ['funktionen.alarme.text', 'funktionen.alarme.text2', 'funktionen.alarme.text3'],
		verfuegbar: 'funktionen.alarme.verfuegbar',
		bilder: [BILD['alarm-mail']]
	},
	ortsvergleich: {
		titel: 'funktionen.ortsvergleich.titel',
		absaetze: ['funktionen.ortsvergleich.text', 'funktionen.ortsvergleich.text2'],
		verfuegbar: 'funktionen.ortsvergleich.verfuegbar',
		bilder: [BILD.ortsvergleich]
	},
	kanaele: {
		titel: 'funktionen.kanaele.titel',
		absaetze: ['funktionen.kanaele.text', 'funktionen.kanaele.text2'],
		verfuegbar: 'funktionen.kanaele.verfuegbar',
		bilder: [BILD['konto-kanaele'], BILD['briefing-sms'], BILD['premium-sms']]
	},
	zustellung: {
		titel: 'funktionen.zustellung.titel',
		absaetze: ['funktionen.zustellung.text', 'funktionen.zustellung.text2'],
		bilder: [BILD['trip-zustellung']]
	},
	befehle: {
		titel: 'funktionen.befehle.titel',
		absaetze: ['funktionen.befehle.text', 'funktionen.befehle.kanaele', 'funktionen.befehle.ortsvergleich'],
		bilder: [BILD['befehle-mail']]
	},
	wetterdaten: {
		titel: 'funktionen.wetterdaten.titel',
		absaetze: ['funktionen.wetterdaten.text', 'funktionen.wetterdaten.text2'],
		bilder: [BILD['briefing-quelle']]
	},
	konto: {
		titel: 'funktionen.konto.titel',
		absaetze: ['funktionen.konto.text', 'funktionen.konto.text2'],
		bilder: [BILD['konto-level']]
	},
	app: { titel: 'funktionen.app.titel', absaetze: ['funktionen.app.text'], bilder: [] }
};

// i18n-dynamic: funktionen.seite.
/** Katalogschluessel einer Unterseite (Titel, Kachelsatz, Einleitung, Meta-Beschreibung). */
export function seitenText(slug: FunktionenSlug, teil: 'titel' | 'kachel' | 'einleitung' | 'beschreibung'): MessageKey {
	return `funktionen.seite.${slug}.${teil}` as MessageKey;
}
/** Kurzformen fuer das Markup (dort keine Wort-Literale, Hardcode-Waechter). */
export const seitenTitel = (slug: FunktionenSlug): MessageKey => seitenText(slug, 'titel');
export const seitenKachel = (slug: FunktionenSlug): MessageKey => seitenText(slug, 'kachel');
export const seitenEinleitung = (slug: FunktionenSlug): MessageKey => seitenText(slug, 'einleitung');
export const seitenBeschreibung = (slug: FunktionenSlug): MessageKey => seitenText(slug, 'beschreibung');

/** Bild der Themenkachel: das erste Bild der Unterseite (Level-Seite ohne Bild). */
export function kachelBild(inventar: readonly InventarId[]): Bild | undefined {
	return inventar.flatMap((id) => INVENTAR[id].bilder)[0];
}

type Masse = { width: number; height: number };
const MASSE = bildmasse as Record<string, Partial<Record<'de' | 'en', Masse>>>;

/** Pfad und feste Masse der Bilddatei je Sprache (eigene Datei je Sprache, AC-8). */
export function bildQuelle(name: BildName, lang: 'de' | 'en'): { src: string } & Masse {
	const m = MASSE[name]?.[lang];
	// Masse stehen in bildmasse.json (geschrieben von den Bild-Skripten); fehlt ein
	// Eintrag, ist das Bild nicht erzeugt worden — kein erfundener Ersatzwert.
	if (!m) throw new Error(`bildmasse.json: keine Masse fuer ${name} (${lang})`);
	return { src: lang === 'en' ? `/funktionen/en/${name}.webp` : `/funktionen/${name}.webp`, ...m };
}
