// Issue #2647 (i18n S2) — Datums-/Zeitformate ohne Intl-Abkuerzungen (eigene
// Tabellen, damit `Fr`/`Fri` in jeder Laufzeit gleich aussehen). Arbeitet auf
// den lokalen Bestandteilen des uebergebenen Date; die Zeitzonenwahl liegt
// beim Aufrufer. Glossar „Zeit und Format".
import type { Lang } from './locale.ts';
import { trFor, trnFor } from './index.ts';

const WOCHENTAG_KURZ: Record<Lang, string[]> = {
	de: ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'],
	en: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
};
const WOCHENTAG_LANG: Record<Lang, string[]> = {
	de: ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'],
	en: ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
};
const MONAT_LANG: Record<Lang, string[]> = {
	de: ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'],
	en: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
};
const MONAT_KURZ_EN = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const zwei = (n: number) => String(n).padStart(2, '0');

export function fmtWeekday(d: Date, lang: Lang, kurz = true): string {
	return (kurz ? WOCHENTAG_KURZ : WOCHENTAG_LANG)[lang][d.getDay()];
}

/** kurz: `Fr 30.10.` | `Fri 30 Oct`; lang: `Freitag, 30. Oktober 2026` | `Friday, 30 October 2026`. */
export function fmtDate(d: Date, lang: Lang, style: 'kurz' | 'lang'): string {
	const tag = d.getDate();
	const monat = d.getMonth();
	if (style === 'lang') {
		const trenner = lang === 'de' ? '. ' : ' ';
		return `${fmtWeekday(d, lang, false)}, ${tag}${trenner}${MONAT_LANG[lang][monat]} ${d.getFullYear()}`;
	}
	if (lang === 'en') return `${fmtWeekday(d, 'en')} ${tag} ${MONAT_KURZ_EN[monat]}`;
	return `${fmtWeekday(d, 'de')} ${zwei(tag)}.${zwei(monat + 1)}.`;
}

// Issue #2651 (F2): Tag/Monat/Jahr in der Zone Europe/Berlin (nur Ziffern aus
// Intl, Monatskuerzel aus der eigenen Tabelle).
const BERLIN = new Intl.DateTimeFormat('en-US', {
	timeZone: 'Europe/Berlin',
	day: 'numeric',
	month: 'numeric',
	year: 'numeric'
});

/** Datum in Europe/Berlin: `30.10.2026` | `30 Oct 2026`. */
export function fmtDateNumeric(d: Date, lang: Lang): string {
	const teil = (typ: string) => Number(BERLIN.formatToParts(d).find((p) => p.type === typ)?.value);
	const [tag, monat, jahr] = [teil('day'), teil('month'), teil('year')];
	if (lang === 'en') return `${tag} ${MONAT_KURZ_EN[monat - 1]} ${jahr}`;
	return `${zwei(tag)}.${zwei(monat)}.${jahr}`;
}

/** `14:30` (24 h, beide Sprachen). */
export function fmtTime(d: Date): string {
	return `${zwei(d.getHours())}:${zwei(d.getMinutes())}`;
}

/** `vor 3 Min` | `3 min ago`; unter einer Minute `gerade eben` | `just now`. */
export function fmtRelativeMinutes(min: number, lang: Lang): string {
	if (min < 1) return trFor(lang, 'aktionen.zeit.gerade_eben');
	return trnFor(lang, 'aktionen.zeit.vor_minuten', Math.floor(min));
}
