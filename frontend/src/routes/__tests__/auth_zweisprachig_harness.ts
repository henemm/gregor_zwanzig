// Issue #2650 (i18n F1, Epic #2644) — gemeinsamer Aufbau fuer die Zweisprachigkeits-Tests
// der Auth-Routen (login, register, forgot-password, reset-password, magic-link,
// magic-link/verify, verify-email).
//
// Gemessen werden die ECHTEN Seiten (svelte/server `render`) und die ECHTEN
// `load`/`actions`. Ersetzt ist nur die Netzgrenze `fetch` (je Test) und das
// SvelteKit-Virtual-Modul `$app/forms` bzw. `$app/stores` (Stub-Hooks). Kein Mock
// des Prueflings.
//
// Golden-Fixtures `fixtures/auth/<route>.de.html`: die deutsche Ausgabe VOR der
// Umstellung (main, Commit RED). Format: Abschnitte `=== zustand: <name> ===`, je
// Abschnitt das gerenderte HTML plus ein abschliessendes Zeilenende.
//
// Pfadregel #1409: alles relativ zu DIESER Datei.

import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const ROUTES = path.resolve(HERE, '..');
export const FRONTEND = path.resolve(HERE, '../../..');
export const FIXTURE_DIR = path.join(HERE, 'fixtures', 'auth');
const BASIS = pathToFileURL(FRONTEND + '/').href;

register(pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, BASIS);
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, BASIS);
register(pathToFileURL(path.join(ROUTES, 'login/__tests__/app-stores-url-stub-hooks.mjs')).href, BASIS);
register(pathToFileURL(path.join(HERE, 'auth_app_forms_stub_hooks.mjs')).href, BASIS);

export type Lang = 'de' | 'en';

const { render } = await import('svelte/server');
const i18n = await import('../../lib/i18n/index.ts');
const { de } = await import('../../lib/i18n/messages/de/index.ts');
const { en } = await import('../../lib/i18n/messages/en/index.ts');
const { TIER_LABELS } = await import('../../lib/admin.ts');
export const locale = i18n.locale;
export const trFor = i18n.trFor;
export const KATALOG_DE: Record<string, string> = de;
export const KATALOG_EN: Record<string, string> = en;
export const TIER_LABEL_FREE: string = TIER_LABELS.free;

/** Rendert eine Seiten-/Bausteinkomponente unter `lang` (Store je Aufruf gesetzt und zurueckgesetzt). */
export async function rendere(datei: string, props: Record<string, unknown>, lang: Lang): Promise<string> {
	const komponente = (await import(pathToFileURL(path.join(ROUTES, datei)).href)).default;
	locale.set(lang);
	try {
		return render(komponente, { props: props as Record<string, never> }).body;
	} finally {
		locale.set('de');
	}
}

/** Echter `load` einer Route mit gesetzter URL (und Request fuer Routen, die Header lesen). */
export async function laedeLoad(datei: string, href: string): Promise<Record<string, unknown>> {
	const modul = await import(pathToFileURL(path.join(ROUTES, datei)).href);
	const geladen = await modul.load({ url: new URL(href), request: new Request(href) });
	return (geladen ?? {}) as Record<string, unknown>;
}

/** Sichtbarer Text inkl. `placeholder`/`title`-Werten, Leerraum normalisiert. */
export function sichtbarerText(html: string): string {
	const ohne = html
		.replace(/<!--[\s\S]*?-->/g, ' ')
		.replace(/<(script|style)[\s\S]*?<\/\1>/gi, ' ');
	const attribute = [...ohne.matchAll(/\s(?:placeholder|title)="([^"]*)"/g)].map((m) => m[1]).join(' ');
	const text = ohne.replace(/<[^>]+>/g, ' ').replace(/&[a-z]+;/g, ' ');
	return `${text} ${attribute}`.replace(/\s+/g, ' ').trim();
}

// Erlaubt sind Eigenname/Markenschriftzug (Wordmark: „gregor.zwanzig“, Zeile
// „V0.20 · WETTER-BRIEFING") und der Sprachumschalter „DE | EN". Der Schriftzug
// gehoert der gemeinsamen Marken-Komponente, nicht den Auth-Routen (Known Limitations #2650).
const ERLAUBT = new Set(['Gregor', 'Zwanzig', 'gregor', 'zwanzig', 'WETTER', 'BRIEFING', 'DE', 'EN']);

// Deutsche Funktionswoerter, die im englischen Text nie vorkommen (Restwort-Netz
// neben dem Katalogvergleich). Bewusst ohne Woerter, die auch Englisch sind (in, an, or).
const DEUTSCHE_FUNKTIONSWOERTER = ['der', 'die', 'das', 'den', 'dem', 'und', 'ist', 'nicht', 'bitte', 'du', 'dein', 'deine', 'mit', 'für', 'ein', 'eine', 'wurde', 'sind'];

const woerter = (text: string): string[] => text.match(/[A-Za-zÄÖÜäöüß]{2,}/g) ?? [];

/**
 * Restwort-Pruefung (AC-1/AC-3) per Katalog-Differenz (Adversary #2650 F001): ein
 * sichtbares Wort ist ein Restwort, wenn es ein deutsches `auth.*`-Katalogwort ist
 * oder ein deutsches Funktionswort, und NICHT im englischen `auth.*`-Katalog
 * vorkommt. Der englische Katalog wird nicht mehr vom Text abgezogen.
 * `erlaubt` nennt dynamische Werte, die nicht aus dem Katalog kommen.
 */
export function restwoerter(html: string, erlaubt: string[] = []): string[] {
	const auth = (katalog: Record<string, string>) =>
		Object.entries(katalog)
			.filter(([schluessel]) => schluessel.startsWith('auth.'))
			.map(([, wert]) => wert);
	const deutsch = new Set([...auth(KATALOG_DE).flatMap(woerter), ...DEUTSCHE_FUNKTIONSWOERTER]);
	const englisch = new Set(auth(KATALOG_EN).flatMap(woerter));
	const frei = new Set([...ERLAUBT, ...erlaubt]);
	return woerter(sichtbarerText(html)).filter((wort) => deutsch.has(wort) && !englisch.has(wort) && !frei.has(wort));
}

// ─── Golden-Fixtures (deutsche Ausgabe vor der Umstellung) ───────────────────

export type Fall = { name: string; render: () => Promise<string> };
export type Golden = { route: string; faelle: Fall[] };

/** Login-Seite samt echtem `load` (Google eingerichtet, damit der Google-Knopf mitgerendert wird). */
export async function loginSeite(href: string, form: unknown, lang: Lang = 'de'): Promise<string> {
	(globalThis as { __gzLoginTestUrl?: string }).__gzLoginTestUrl = href;
	const geladen = await laedeLoad('login/+page.server.ts', href);
	return rendere('login/+page.svelte', { form, data: { ...geladen, googleEnabled: true } }, lang);
}

/** Registrierungs-Seite mit gegebenem Einladungszustand (Google eingerichtet). */
export async function registerSeite(invite: Record<string, unknown>, form: unknown, lang: Lang = 'de'): Promise<string> {
	return rendere('register/+page.svelte', { form, data: { googleEnabled: true, invite } }, lang);
}

const LOGIN_FORM = (error: string, resent = false) => ({ error, username: 'anna', resent });

export const GOLDEN_FAELLE: Golden[] = [
	{
		route: 'login',
		faelle: [
			{ name: 'leer', render: () => loginSeite('http://localhost/login', null) },
			{ name: 'fehler_invalid', render: () => loginSeite('http://localhost/login', LOGIN_FORM('Invalid credentials')) },
			{ name: 'fehler_rate', render: () => loginSeite('http://localhost/login', LOGIN_FORM('Rate limit exceeded')) },
			{
				name: 'fehler_pflicht',
				render: () => loginSeite('http://localhost/login', { error: 'Username and password required', username: '', resent: false })
			},
			{ name: 'fehler_unbekannt', render: () => loginSeite('http://localhost/login', LOGIN_FORM('Unbekannter Fehler')) },
			{ name: 'email_nicht_bestaetigt', render: () => loginSeite('http://localhost/login', LOGIN_FORM('email_not_verified')) },
			{ name: 'erneut_gesendet', render: () => loginSeite('http://localhost/login', LOGIN_FORM('email_not_verified', true)) },
			{ name: 'registriert', render: () => loginSeite('http://localhost/login?registered=1', null) },
			{ name: 'sitzung_abgelaufen', render: () => loginSeite('http://localhost/login?expired=1', null) },
			{ name: 'google_oauth_failed', render: () => loginSeite('http://localhost/login?error=oauth_failed', null) },
			{ name: 'google_oauth_link_failed', render: () => loginSeite('http://localhost/login?error=oauth_link_failed', null) },
			{ name: 'google_email_nicht_bestaetigt', render: () => loginSeite('http://localhost/login?error=email_not_verified', null) }
		]
	},
	{
		route: 'register',
		faelle: [
			{ name: 'leer', render: () => registerSeite({ status: 'none' }, null) },
			{ name: 'einladung_gueltig', render: () => registerSeite({ status: 'valid', token: 't1', tier: 'free' }, null) },
			{ name: 'einladung_unbekannt', render: () => registerSeite({ status: 'unknown', token: 't2' }, null) },
			{ name: 'einladung_ungueltig', render: () => registerSeite({ status: 'invalid' }, null) },
			{
				name: 'fehler_passwoerter',
				render: () =>
					registerSeite({ status: 'none' }, { error: 'Passwörter stimmen nicht überein', username: 'anna', email: 'a@b.de' })
			}
		]
	},
	{
		route: 'forgot-password',
		faelle: [
			{ name: 'leer', render: () => rendere('forgot-password/+page.svelte', { form: null }, 'de') },
			{
				name: 'fehler',
				render: () => rendere('forgot-password/+page.svelte', { form: { error: 'Username required', username: '' } }, 'de')
			},
			{
				name: 'erfolg',
				render: () => rendere('forgot-password/+page.svelte', { form: { success: true, username: 'anna' } }, 'de')
			}
		]
	},
	{
		route: 'reset-password',
		faelle: [
			{
				name: 'leer',
				render: () => rendere('reset-password/+page.svelte', { form: null, data: { user: '', token: '' } }, 'de')
			},
			{
				name: 'mit_token',
				render: () => rendere('reset-password/+page.svelte', { form: null, data: { user: 'anna', token: 'abc' } }, 'de')
			},
			{
				name: 'fehler',
				render: () =>
					rendere(
						'reset-password/+page.svelte',
						{ form: { error: 'Ungültiger Token', username: 'anna', token: 'x' }, data: { user: '', token: '' } },
						'de'
					)
			},
			{
				name: 'erfolg',
				render: () => rendere('reset-password/+page.svelte', { form: { success: true }, data: { user: '', token: '' } }, 'de')
			}
		]
	},
	{
		route: 'magic-link',
		faelle: [
			{ name: 'leer', render: () => rendere('magic-link/+page.svelte', { form: null }, 'de') },
			{
				name: 'gesendet',
				render: () => rendere('magic-link/+page.svelte', { form: { sent: true, email: 'a@b.de' } }, 'de')
			},
			{
				name: 'fehler',
				render: () => rendere('magic-link/+page.svelte', { form: { error: 'E-Mail-Adresse erforderlich', email: '' } }, 'de')
			}
		]
	},
	{
		route: 'magic-link-verify',
		faelle: [
			{
				name: 'leer',
				render: () => rendere('magic-link/verify/+page.svelte', { form: null, data: { email: 'a@b.de' } }, 'de')
			},
			{
				name: 'fehler',
				render: () =>
					rendere(
						'magic-link/verify/+page.svelte',
						{ form: { error: 'Ungültiger oder abgelaufener Code.', email: 'a@b.de' }, data: { email: 'a@b.de' } },
						'de'
					)
			}
		]
	},
	{
		route: 'verify-email',
		faelle: [
			{
				name: 'unvollstaendig',
				render: () => rendere('verify-email/+page.svelte', { form: null, data: { user: '', token: '' } }, 'de')
			},
			{
				name: 'formular',
				render: () => rendere('verify-email/+page.svelte', { form: null, data: { user: 'anna', token: 'abc' } }, 'de')
			},
			{
				name: 'fehler',
				render: () =>
					rendere(
						'verify-email/+page.svelte',
						{
							form: { error: 'Der Bestätigungslink ist abgelaufen. Bitte ändere deine Adresse erneut, um einen neuen Link zu erhalten.', user: 'anna', token: 'abc' },
							data: { user: 'anna', token: 'abc' }
						},
						'de'
					)
			},
			{
				name: 'erfolg',
				render: () => rendere('verify-email/+page.svelte', { form: { success: true }, data: { user: '', token: '' } }, 'de')
			}
		]
	}
];

/**
 * Vergleichsform fuer Golden-Tests: Svelte-Hydrations-Kommentare weg, jeder
 * Leerraum-Lauf (auch Zeilenumbrueche aus dem Template) wird ein Leerzeichen.
 * Wortlaut und Tag-Struktur bleiben exakt vergleichbar.
 */
export function golden(html: string): string {
	return html.replace(/<!--[\s\S]*?-->/g, '').replace(/\s+/g, ' ').trim();
}

/** Serialisiert Abschnitte in das Fixture-Format. */
export function fixtureSchreiben(abschnitte: Array<[string, string]>): string {
	return abschnitte.map(([name, html]) => `=== zustand: ${name} ===\n${html}\n`).join('');
}

/** Liest das Fixture-Format zurueck in Abschnitte (Name -> HTML ohne das Zeilenende des Formats). */
export function fixtureLesen(text: string): Map<string, string> {
	const karte = new Map<string, string>();
	const teile = text.split(/^=== zustand: (\S+) ===\n/m);
	for (let i = 1; i < teile.length; i += 2) {
		karte.set(teile[i], teile[i + 1].slice(0, -1));
	}
	return karte;
}
