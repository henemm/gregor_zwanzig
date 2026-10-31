// Issue #2647 (i18n S2) — Sprachaufloesung je Anfrage (Konventionen Abschnitt 1):
// Cookie `gz_lang` > `Accept-Language` > `de`. Fuer Angemeldete ueberschreibt
// der Layout-Loader das Ergebnis mit der Profilsprache.
import type { Lang } from './locale.ts';

function alsLang(wert: string | null | undefined): Lang | null {
	return wert === 'de' || wert === 'en' ? wert : null;
}

/** Erster unterstuetzter Eintrag (Hauptsprache vor `-`/`;`), sonst `null`. */
export function parseAcceptLanguage(header: string | null | undefined): Lang | null {
	if (!header) return null;
	for (const eintrag of header.split(',')) {
		const haupt = eintrag.split(';')[0].trim().split('-')[0].toLowerCase();
		const lang = alsLang(haupt);
		if (lang) return lang;
	}
	return null;
}

export function resolveLang(quelle: {
	cookie?: string | null;
	acceptLanguage?: string | null;
}): Lang {
	return alsLang(quelle.cookie) ?? parseAcceptLanguage(quelle.acceptLanguage) ?? 'de';
}
