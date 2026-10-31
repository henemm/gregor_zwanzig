// Issue #2520 — typisierter Textkatalog; Issue #2647 (i18n S2) — zweisprachig.
// Katalog je Bereich (messages/{de,en}/<bereich>.json), vereinigt in
// messages/{de,en}/index.ts. Unbekannter Schluessel = TypeScript-Fehler
// (svelte-check). Keine Abhaengigkeit. Schnittstelle: Konventionen Abschnitt 3.
//   Svelte-Markup: {$t('bereich.x')} · .ts-Module: tr(...) · Server: trFor(locals.lang, ...)
import { derived, get, type Readable } from 'svelte/store';
import { de } from './messages/de/index.ts';
import { en } from './messages/en/index.ts';
import { locale, type Lang } from './locale.ts';
import { translate, translatePlural, type Kataloge, type Params } from './translate.ts';

export { locale, type Lang };
export type MessageKey = keyof typeof de;

const KATALOGE: Kataloge = { de, en };

/** Sprache ausdruecklich (Server-Actions/Loader: `locals.lang`); `undefined` ergibt `de`. */
export function trFor(lang: Lang | undefined, key: MessageKey, params?: Params): string {
	return translate(KATALOGE, lang ?? 'de', key, params);
}

/** Plural mit ausdruecklicher Sprache; `key` ohne `.one`/`.other`. */
export function trnFor(lang: Lang | undefined, key: string, count: number, params?: Params): string {
	return translatePlural(KATALOGE, lang ?? 'de', key, count, params);
}

/** Fuer .ts-Module ohne Store-Kontext (liest die aktuelle `locale`). */
export function tr(key: MessageKey, params?: Params): string {
	return trFor(get(locale), key, params);
}

/** Plural-Gegenstueck zu `tr`. */
export function trn(key: string, count: number, params?: Params): string {
	return trnFor(get(locale), key, count, params);
}

export const t: Readable<(key: MessageKey, params?: Params) => string> = derived(
	locale,
	(lang) => (key: MessageKey, params?: Params) => trFor(lang, key, params)
);

export const tn: Readable<(key: string, count: number, params?: Params) => string> = derived(
	locale,
	(lang) => (key: string, count: number, params?: Params) => trnFor(lang, key, count, params)
);
