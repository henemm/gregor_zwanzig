// Stand-Kennzeichnung offline vorgehaltener Ansichten (Issue #2131, Scheibe 4
// zu Epic #2127). Spec: docs/specs/modules/pwa_offline_ansicht_letzter_stand.md
//
// EINE Quelle fuer die Zeichenkette — sie wird an zwei Stellen gebraucht:
//   * im Service Worker, der sie beim ABLEGEN in das Dokument einschreibt
//     (AC-4: der Stand steht schon im Bytestrom, nicht erst in der Anzeige),
//   * im Browser, der sie bei einer Client-Navigation zwischen zwei abgelegten
//     Ansichten austauscht (AC-5 — dort gibt es kein neues Dokument).
// Zwei getrennte Fassungen waeren zwei Wahrheiten: die eine koennte sich
// aendern, ohne dass die andere es merkt.
//
// Zeitformat wie `$lib/utils/schedulerTime.ts`: Geraetezone plus Zonenkuerzel,
// damit die Zahl eindeutig bleibt.
//
// #2652 (i18n F3): Sprache als letzter Parameter (Default `de`). KEIN Svelte-
// Store (der Service Worker hat keinen): die Texte kommen direkt aus den
// Katalogdateien home.json, uebersetzt mit dem reinen Kern translate.ts.
// Der Herkunftssatz ist `home.stand.herkunft` (frueher STAND_HERKUNFT).

import de from '../i18n/messages/de/home.json' with { type: 'json' };
import en from '../i18n/messages/en/home.json' with { type: 'json' };
import { translate } from '../i18n/translate.ts';
import type { Lang } from '../i18n/locale.ts';

const KATALOGE = { de, en };
const INTL: Record<Lang, string> = { de: 'de-AT', en: 'en-GB' };
const text = (lang: Lang, key: string, params?: Record<string, string>) => translate(KATALOGE, lang, key, params);

/** Kennung des Markierungselements in `app.html`. */
export const STAND_ELEMENT_ID = 'gz-stand';

/** Hoher Kontrast (ADR-0008) — bewusst NICHT `--g-ink-4`. */
export const STAND_STIL =
	'display: block; padding: 8px 16px; background: rgba(192,138,26,0.12); ' +
	'color: #6b4a06; border-bottom: 1px solid #c08a1a; font-size: 13px; ' +
	'font-weight: 600; line-height: 1.4;';

/** Sprache eines HTML-Dokuments aus `<html lang>`; alles ausser `en` ergibt `de`. */
export function standSpracheAusHtml(html: string): Lang {
	return /<html\b[^>]*\blang=["']?en\b/i.test(html) ? 'en' : 'de';
}

export function formatiereStandZeit(zeit: Date, lang: Lang = 'de'): string {
	return zeit.toLocaleString(INTL[lang], {
		day: '2-digit',
		month: '2-digit',
		hour: '2-digit',
		minute: '2-digit',
		timeZoneName: 'short'
	});
}

/** Volle Zeile am Inhalt: „Stand: 05.09., 06:12 MESZ — offline, aus dem Gerätespeicher". */
export function standZeile(zeit: Date, lang: Lang = 'de'): string {
	return text(lang, 'home.stand.zeile', {
		zeit: formatiereStandZeit(zeit, lang),
		herkunft: text(lang, 'home.stand.herkunft')
	});
}

/**
 * Kurzform fuer die Offline-Uebersicht: dort ist die Herkunft die Aussage der
 * ganzen Seite und muss nicht in jeder Zeile wiederholt werden.
 */
export function standKurz(zeit: Date, lang: Lang = 'de'): string {
	return text(lang, 'home.stand.kurz', { zeit: formatiereStandZeit(zeit, lang) });
}
