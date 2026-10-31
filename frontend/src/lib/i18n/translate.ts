// Issue #2647 (i18n S2) — reiner Uebersetzungskern ohne Store und ohne feste
// Kataloge (die bindet index.ts an). Konventionen Abschnitt 2: `{name}`-
// Platzhalter, Plural `x.one`/`x.other` mit implizitem `{count}`, Fallback auf
// Deutsch mit EINER Warnung je Schluessel und Prozess.
import type { Lang } from './locale.ts';

export type Katalog = Readonly<Record<string, string>>;
export type Kataloge = Readonly<Record<Lang, Katalog>>;
export type Params = Record<string, string | number>;

const gewarnt = new Set<string>();

function einsetzen(text: string, params?: Params): string {
	if (!params) return text;
	return text.replace(/\{([a-z0-9_]+)\}/g, (roh, name: string) =>
		Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : roh
	);
}

function warneEinmal(key: string): void {
	if (gewarnt.has(key)) return;
	gewarnt.add(key);
	console.warn(`i18n fallback: ${key}`);
}

export function translate(kataloge: Kataloge, lang: Lang, key: string, params?: Params): string {
	const wert = kataloge[lang]?.[key];
	if (wert !== undefined) return einsetzen(wert, params);
	if (lang !== 'de') warneEinmal(key);
	return einsetzen(kataloge.de[key] ?? key, params);
}

export function translatePlural(
	kataloge: Kataloge,
	lang: Lang,
	key: string,
	count: number,
	params?: Params
): string {
	const form = count === 1 ? 'one' : 'other';
	return translate(kataloge, lang, `${key}.${form}`, { count, ...params });
}
