// TDD RED — Issue #2194 (E-Mail als Login-Kennung, Epic #2138), AC-14.
// Spec: docs/specs/modules/email_login_identifier.md
//
// AC-14: Login-, Registrier- und Passwort-vergessen-Seite fragen in de und en
// nach „E-Mail" bzw. „Email" statt nach „Benutzername"/„Username"; das
// Registrierformular hat kein Benutzername-Feld mehr; das Login-Feld traegt
// `autocomplete="email webauthn"`.
//
// Gemessen werden die ECHTEN Seiten (svelte/server `render`) samt echtem
// `load` bzw. echter Action (Harness #2650). Ersetzt ist nur die Netzgrenze
// `fetch` (Register-Action). Kein Dateiinhalt-Check: geprueft wird das
// gerenderte Markup und der sichtbare Text.
//
// Bewusst NICHT festgelegt: id/name des Feldes und der Katalogschluessel —
// GREEN darf sie umbenennen. Festgelegt sind nur Beschriftung, Attribut und
// die Abwesenheit des Benutzername-Begriffs.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/__tests__/auth_seiten_fragen_nach_email.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import {
	ROUTES,
	loginSeite,
	registerSeite,
	rendere,
	sichtbarerText,
	type Lang
} from './auth_zweisprachig_harness.ts';

const SPRACHEN: Lang[] = ['de', 'en'];
const ERWARTETES_WORT: Record<Lang, string> = { de: 'E-Mail', en: 'Email' };
const BENUTZERNAME = /benutzername|username/i;

type Eingabe = { attrs: Record<string, string>; roh: string };

function attribute(tag: string): Record<string, string> {
	const attrs: Record<string, string> = {};
	for (const m of tag.matchAll(/\s([a-zA-Z:-]+)(?:="([^"]*)")?/g)) attrs[m[1].toLowerCase()] = m[2] ?? '';
	return attrs;
}

function eingaben(html: string): Eingabe[] {
	return [...html.matchAll(/<input\b[^>]*>/g)].map((m) => ({ attrs: attribute(m[0]), roh: m[0] }));
}

function sichtbareEingaben(html: string): Eingabe[] {
	return eingaben(html).filter((e) => e.attrs.type !== 'hidden');
}

/** Das Formular, das die Login-Action (`?/login`) absendet — nicht das Resend-Formular. */
function loginFormular(html: string): string {
	const m = html.match(/<form\b[^>]*action="\?\/login"[^>]*>([\s\S]*?)<\/form>/);
	assert.ok(m, 'Login-Formular (action="?/login") nicht im gerenderten Markup gefunden');
	return m![0];
}

/** Text des <label for=id>, Leerraum/Kommentare normalisiert. */
function labelText(html: string, id: string): string | null {
	const re = new RegExp(`<label\\b[^>]*\\bfor="${id.replace(/[-]/g, '\\-')}"[^>]*>([\\s\\S]*?)<\\/label>`);
	const m = html.match(re);
	if (!m) return null;
	return m[1].replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
}

/** Das Kennungsfeld der Login-Seite: das erste sichtbare Nicht-Passwort-Feld im Login-Formular. */
function kennungsfeld(html: string): Eingabe {
	const feld = sichtbareEingaben(loginFormular(html)).find((e) => e.attrs.type !== 'password');
	assert.ok(feld, 'Login-Formular hat kein sichtbares Kennungsfeld');
	return feld!;
}

/**
 * `form` aus der ECHTEN Login-Action (`?/login`) — keine hart kodierten
 * Fehlercodes, damit GREEN die Codes umbenennen darf. Ersetzt ist nur `fetch`
 * (Go-API antwortet 401); bei leerer Eingabe endet die Action vor dem Netz.
 */
async function loginActionForm(felder: Record<string, string>, lang: Lang): Promise<unknown> {
	const { actions } = await import(pathToFileURL(path.join(ROUTES, 'login/+page.server.ts')).href);
	const echterFetch = globalThis.fetch;
	globalThis.fetch = async () =>
		new Response('{"code":"invalid_credentials"}', { status: 401, headers: { 'Content-Type': 'application/json' } });
	try {
		const body = new FormData();
		for (const [k, v] of Object.entries(felder)) body.set(k, v);
		const ereignis = {
			request: new Request('http://localhost/login?/login', { method: 'POST', body }),
			url: new URL('http://localhost/login'),
			cookies: { set() {}, get() {}, delete() {} },
			locals: { lang }
		};
		const ergebnis = (await actions.login(ereignis)) as { data?: unknown };
		assert.ok(ergebnis?.data, 'Login-Action lieferte kein fail()-Ergebnis');
		return ergebnis.data;
	} finally {
		globalThis.fetch = echterFetch;
	}
}

const LOGIN_ZUSTAENDE: Array<{ name: string; form: (lang: Lang) => Promise<unknown> }> = [
	{ name: 'leer', form: async () => null },
	{
		name: 'fehler_invalid',
		form: (lang) => loginActionForm({ username: 'anna@beispiel.de', password: 'falsch1234' }, lang)
	},
	{ name: 'fehler_pflicht', form: (lang) => loginActionForm({}, lang) }
];

describe('#2194 AC-14 — /login fragt nach der E-Mail-Adresse', () => {
	for (const lang of SPRACHEN) {
		test(`AC-14_login_${lang}_kennungsfeld_traegt_autocomplete_email_webauthn`, async () => {
			const feld = kennungsfeld(await loginSeite('http://localhost/login', null, lang));
			assert.equal(
				feld.attrs.autocomplete,
				'email webauthn',
				`AC-14 (${lang}): das Login-Kennungsfeld muss autocomplete="email webauthn" tragen, ist: ${feld.roh}`
			);
		});

		test(`AC-14_login_${lang}_beschriftung_ist_${ERWARTETES_WORT[lang]}`, async () => {
			const html = await loginSeite('http://localhost/login', null, lang);
			const feld = kennungsfeld(html);
			const text = labelText(html, feld.attrs.id ?? '');
			assert.ok(text !== null, `AC-14 (${lang}): Kennungsfeld ohne <label for="${feld.attrs.id}">`);
			assert.ok(
				text!.includes(ERWARTETES_WORT[lang]),
				`AC-14 (${lang}): Beschriftung des Login-Feldes soll „${ERWARTETES_WORT[lang]}" enthalten, ist „${text}"`
			);
			assert.doesNotMatch(text!, BENUTZERNAME, `AC-14 (${lang}): Beschriftung nennt noch den Benutzernamen: „${text}"`);
		});

		for (const z of LOGIN_ZUSTAENDE) {
			test(`AC-14_login_${lang}_${z.name}_sichtbarer_text_ohne_benutzername`, async () => {
				const text = sichtbarerText(await loginSeite('http://localhost/login', await z.form(lang), lang));
				const treffer = text.match(new RegExp(`.{0,40}(${BENUTZERNAME.source}).{0,40}`, 'i'));
				assert.equal(
					treffer,
					null,
					`AC-14 (${lang}, Zustand ${z.name}): sichtbarer Text fragt noch nach dem Benutzernamen: „${treffer?.[0]}"`
				);
			});
		}

		// Waechter, heute gruen: Testkonten (admin, Validator, tg-live-e2e) melden
		// sich in der Oberflaeche weiter per ID ohne „@" an (Spec: ID-Pfad bleibt
		// dauerhaft; global.setup.ts loggt `admin` ueber dieses Feld ein). Ein
		// `type="email"` ohne `novalidate` blockiert diese Eingabe per
		// HTML5-Validierung im Browser.
		test(`AC-14_waechter_login_${lang}_feld_nimmt_weiter_eine_id_ohne_at_an`, async () => {
			const html = await loginSeite('http://localhost/login', null, lang);
			const formular = loginFormular(html);
			const feld = kennungsfeld(html);
			const novalidate = /<form\b[^>]*\bnovalidate\b/.test(formular);
			assert.ok(
				feld.attrs.type !== 'email' || novalidate,
				`AC-14/AC-16 (${lang}): Login-Feld ist type="email" ohne novalidate — der ID-Login von Testkonten ` +
					`(z.B. „admin" in global.setup.ts) wuerde vom Browser blockiert: ${feld.roh}`
			);
		});
	}
});

describe('#2194 AC-14 — /register hat kein Benutzername-Feld mehr', () => {
	for (const lang of SPRACHEN) {
		test(`AC-14_register_${lang}_kein_benutzername_feld`, async () => {
			const html = await registerSeite({ status: 'none' }, null, lang);
			const benutzerFelder = sichtbareEingaben(html).filter(
				(e) => e.attrs.name === 'username' || e.attrs.id === 'username'
			);
			assert.deepEqual(
				benutzerFelder.map((e) => e.roh),
				[],
				`AC-14 (${lang}): Registrierformular hat noch ein Benutzername-Feld`
			);
			const text = sichtbarerText(html);
			assert.doesNotMatch(text, BENUTZERNAME, `AC-14 (${lang}): Registrierseite nennt noch den Benutzernamen`);
		});

		// Waechter, heute gruen: die Registrierung fragt weiter die E-Mail ab.
		test(`AC-14_waechter_register_${lang}_email_feld_bleibt`, async () => {
			const html = await registerSeite({ status: 'none' }, null, lang);
			const email = sichtbareEingaben(html).find((e) => e.attrs.type === 'email');
			assert.ok(email, `AC-14 (${lang}): Registrierformular ohne E-Mail-Feld`);
			const text = labelText(html, email!.attrs.id ?? '');
			assert.ok(text?.includes(ERWARTETES_WORT[lang]), `AC-14 (${lang}): E-Mail-Feld-Beschriftung ist „${text}"`);
		});

		test(`AC-14_register_${lang}_pflichtfeld_fehler_der_echten_action_ohne_benutzername`, async () => {
			const { actions } = await import(pathToFileURL(path.join(ROUTES, 'register/+page.server.ts')).href);
			const echterFetch = globalThis.fetch;
			// Bewusster Ersatz der Netzgrenze: Go-API antwortet 400 ohne Fehlercode.
			globalThis.fetch = async () =>
				new Response('{}', { status: 400, headers: { 'Content-Type': 'application/json' } });
			let ergebnis: { data?: Record<string, unknown> };
			try {
				const body = new FormData();
				body.set('email', 'neu@beispiel.de');
				body.set('password', 'geheim1234');
				body.set('confirmPassword', 'geheim1234');
				const ereignis = {
					request: new Request('http://localhost/register', { method: 'POST', body }),
					locals: { lang }
				};
				ergebnis = await actions.default(ereignis);
			} finally {
				globalThis.fetch = echterFetch;
			}
			assert.ok(ergebnis?.data, 'Register-Action lieferte bei 400 kein fail()-Ergebnis');
			const html = await registerSeite({ status: 'none' }, ergebnis.data, lang);
			const text = sichtbarerText(html);
			assert.doesNotMatch(
				text,
				BENUTZERNAME,
				`AC-14 (${lang}): Pflichtfeld-Fehler der Registrierung nennt noch den Benutzernamen: „${String(ergebnis.data.error)}"`
			);
		});
	}
});

describe('#2194 AC-14 — /forgot-password fragt nach der E-Mail-Adresse', () => {
	for (const lang of SPRACHEN) {
		test(`AC-14_forgot_${lang}_feld_fragt_nach_${ERWARTETES_WORT[lang]}`, async () => {
			const html = await rendere('forgot-password/+page.svelte', { form: null }, lang);
			const feld = sichtbareEingaben(html)[0];
			assert.ok(feld, `AC-14 (${lang}): Passwort-vergessen-Seite ohne Eingabefeld`);
			const beschriftung = `${feld.attrs.placeholder ?? ''} ${labelText(html, feld.attrs.id ?? '') ?? ''}`.trim();
			assert.ok(
				beschriftung.includes(ERWARTETES_WORT[lang]),
				`AC-14 (${lang}): Feld der Passwort-vergessen-Seite soll nach „${ERWARTETES_WORT[lang]}" fragen, ist „${beschriftung}"`
			);
			assert.doesNotMatch(sichtbarerText(html), BENUTZERNAME, `AC-14 (${lang}): Seite nennt noch den Benutzernamen`);
		});

		test(`AC-14_forgot_${lang}_pflichtfehler_der_echten_action_ohne_benutzername`, async () => {
			const { actions } = await import(pathToFileURL(path.join(ROUTES, 'forgot-password/+page.server.ts')).href);
			const ereignis = {
				request: new Request('http://localhost/forgot-password', { method: 'POST', body: new FormData() }),
				locals: { lang }
			};
			const ergebnis = (await actions.default(ereignis)) as { data?: Record<string, unknown> };
			assert.ok(ergebnis?.data?.error, 'Forgot-Action lieferte bei leerer Eingabe keinen Fehler');
			const html = await rendere('forgot-password/+page.svelte', { form: ergebnis.data }, lang);
			const text = sichtbarerText(html);
			assert.doesNotMatch(
				text,
				BENUTZERNAME,
				`AC-14 (${lang}): Pflichtfehler der Passwort-vergessen-Seite nennt noch den Benutzernamen: „${String(ergebnis.data!.error)}"`
			);
		});
	}
});
