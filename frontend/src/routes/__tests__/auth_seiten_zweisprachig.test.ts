// TDD RED — Issue #2650 (i18n F1, Epic #2644), AC-2 und AC-3 für die übrigen Auth-Seiten:
// forgot-password, reset-password, magic-link, magic-link/verify, verify-email.
//
// AC-2: deutsche Ausgabe je Route (leerer Zustand, Fehlerzustand, Erfolg) ist
//       (bis auf Leerraum und Hydrations-Kommentare) byte-gleich zur Ausgabe vor
//       der Umstellung (Fixtures fixtures/auth/<route>.de.html).
// AC-3: englische Seiten und die echten Actions (Fehler über fail(), Erfolg über
//       fetch-Antwort) liefern ausschließlich englische Texte, ohne deutsches
//       Restwort; die deutschen Actions bleiben wortgleich zu heute.
//
// Die Actions laufen ECHT; ersetzt ist nur die globale fetch-Funktion (Netzgrenze).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/__tests__/auth_seiten_zweisprachig.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import {
	FIXTURE_DIR,
	GOLDEN_FAELLE,
	ROUTES,
	fixtureLesen,
	golden,
	rendere,
	restwoerter,
	sichtbarerText,
	trFor,
	type Lang
} from './auth_zweisprachig_harness.ts';

type Antwort = { status: number; body: unknown };
let aktuelleAntwort: Antwort = { status: 500, body: {} };
const echterFetch = globalThis.fetch;
globalThis.fetch = (async () =>
	new Response(JSON.stringify(aktuelleAntwort.body), {
		status: aktuelleAntwort.status,
		headers: { 'Content-Type': 'application/json' }
	})) as typeof fetch;
after(() => {
	globalThis.fetch = echterFetch;
});

/** Führt die echte Action einer Route aus; liefert das fail()-Ergebnis oder den Erfolgsrumpf. */
async function aktion(datei: string, felder: Record<string, string>, lang: Lang, antwort: Antwort | null): Promise<any> {
	if (antwort) aktuelleAntwort = antwort;
	const body = new FormData();
	for (const [k, v] of Object.entries(felder)) body.set(k, v);
	const modul = await import(pathToFileURL(path.join(ROUTES, datei)).href);
	const ereignis = { request: new Request('http://localhost/x', { method: 'POST', body }), locals: { lang } };
	return modul.actions.default(ereignis);
}

/** Formdaten, wie die Seite sie nach der Action bekommt: fail() → `.data`, Erfolg → Rumpf. */
async function formAus(datei: string, felder: Record<string, string>, antwort: Antwort | null): Promise<unknown> {
	const r = await aktion(datei, felder, 'en', antwort);
	return r?.data ?? r;
}

const SEITEN_EN: Array<{ name: string; datei: string; props: () => Promise<Record<string, unknown>> }> = [
	{
		name: 'forgot-password leer',
		datei: 'forgot-password/+page.svelte',
		props: async () => ({ form: null })
	},
	{
		name: 'forgot-password fehler',
		datei: 'forgot-password/+page.svelte',
		props: async () => ({ form: await formAus('forgot-password/+page.server.ts', { username: '' }, null) })
	},
	{
		name: 'forgot-password erfolg',
		datei: 'forgot-password/+page.svelte',
		props: async () => ({
			form: await formAus('forgot-password/+page.server.ts', { username: 'anna' }, { status: 200, body: {} })
		})
	},
	{
		name: 'reset-password leer',
		datei: 'reset-password/+page.svelte',
		props: async () => ({ form: null, data: { user: '', token: '' } })
	},
	{
		name: 'reset-password mit token',
		datei: 'reset-password/+page.svelte',
		props: async () => ({ form: null, data: { user: 'anna', token: 'abc' } })
	},
	{
		name: 'reset-password fehler',
		datei: 'reset-password/+page.svelte',
		props: async () => ({
			form: await formAus(
				'reset-password/+page.server.ts',
				{ username: 'anna', token: 't', new_password: 'kurz' },
				null
			),
			data: { user: '', token: '' }
		})
	},
	{
		name: 'reset-password erfolg',
		datei: 'reset-password/+page.svelte',
		props: async () => ({ form: { success: true }, data: { user: '', token: '' } })
	},
	{
		name: 'magic-link leer',
		datei: 'magic-link/+page.svelte',
		props: async () => ({ form: null })
	},
	{
		name: 'magic-link gesendet',
		datei: 'magic-link/+page.svelte',
		props: async () => ({ form: { sent: true, email: 'a@b.de' } })
	},
	{
		name: 'magic-link fehler',
		datei: 'magic-link/+page.svelte',
		props: async () => ({ form: await formAus('magic-link/+page.server.ts', { email: '' }, null) })
	},
	{
		name: 'magic-link-verify leer',
		datei: 'magic-link/verify/+page.svelte',
		props: async () => ({ form: null, data: { email: 'a@b.de' } })
	},
	{
		name: 'magic-link-verify fehler',
		datei: 'magic-link/verify/+page.svelte',
		props: async () => ({
			form: await formAus(
				'magic-link/verify/+page.server.ts',
				{ email: 'a@b.de', code: '123456' },
				{ status: 400, body: { error: 'invalid' } }
			),
			data: { email: 'a@b.de' }
		})
	},
	{
		name: 'verify-email unvollstaendig',
		datei: 'verify-email/+page.svelte',
		props: async () => ({ form: null, data: { user: '', token: '' } })
	},
	{
		name: 'verify-email formular',
		datei: 'verify-email/+page.svelte',
		props: async () => ({ form: null, data: { user: 'anna', token: 'abc' } })
	},
	{
		name: 'verify-email erfolg',
		datei: 'verify-email/+page.svelte',
		props: async () => ({ form: { success: true }, data: { user: '', token: '' } })
	},
	{
		name: 'verify-email fehler',
		datei: 'verify-email/+page.svelte',
		props: async () => ({
			form: await formAus(
				'verify-email/+page.server.ts',
				{ user: 'anna', token: 'abc' },
				{ status: 400, body: { error: 'token expired' } }
			),
			data: { user: 'anna', token: 'abc' }
		})
	}
];

describe('#2650 AC-3 — Auth-Seiten in Sprache en: kein deutsches Restwort', () => {
	for (const seite of SEITEN_EN) {
		test(`AC-3_${seite.name.replace(/\s+/g, '_')}_englisch_ohne_restwort`, async () => {
			const props = await seite.props();
			const html = await rendere(seite.datei, props, 'en');
			assert.deepEqual(restwoerter(html), [], `AC-3: deutsche Restwörter auf „${seite.name}"`);
		});
	}

	test('AC-3_forgot_password_titel_englisch', async () => {
		const html = await rendere('forgot-password/+page.svelte', { form: null }, 'en');
		assert.ok(sichtbarerText(html).includes(trFor('en', 'auth.forgot.titel')), 'AC-3: Titel fehlt in en');
	});
});

const ACTIONS_FAELLE: Array<{
	name: string;
	datei: string;
	felder: Record<string, string>;
	antwort: Antwort | null;
	de: string;
	key: string;
}> = [
	{
		name: 'forgot_benutzername_fehlt',
		datei: 'forgot-password/+page.server.ts',
		felder: { username: '' },
		antwort: null,
		de: 'Username required',
		key: 'auth.forgot.fehler_benutzername'
	},
	{
		name: 'reset_felder_fehlen',
		datei: 'reset-password/+page.server.ts',
		felder: { username: '', token: '', new_password: '' },
		antwort: null,
		de: 'Alle Felder sind erforderlich',
		key: 'auth.reset.fehler_pflichtfelder'
	},
	{
		name: 'reset_passwort_kurz',
		datei: 'reset-password/+page.server.ts',
		felder: { username: 'anna', token: 't', new_password: 'kurz' },
		antwort: null,
		de: 'Passwort muss mindestens 8 Zeichen haben',
		key: 'auth.reset.fehler_passwort_kurz'
	},
	{
		name: 'reset_token_abgelaufen',
		datei: 'reset-password/+page.server.ts',
		felder: { username: 'anna', token: 't', new_password: 'langesPasswort1' },
		antwort: { status: 400, body: { error: 'token expired' } },
		de: 'Token abgelaufen',
		key: 'auth.reset.fehler_token_abgelaufen'
	},
	{
		name: 'reset_token_ungueltig',
		datei: 'reset-password/+page.server.ts',
		felder: { username: 'anna', token: 't', new_password: 'langesPasswort1' },
		antwort: { status: 400, body: { error: 'x' } },
		de: 'Ungültiger Token',
		key: 'auth.reset.fehler_token_ungueltig'
	},
	{
		name: 'magic_email_fehlt',
		datei: 'magic-link/+page.server.ts',
		felder: { email: '' },
		antwort: null,
		de: 'E-Mail-Adresse erforderlich',
		key: 'auth.magic.fehler_email_pflicht'
	},
	{
		name: 'code_felder_fehlen',
		datei: 'magic-link/verify/+page.server.ts',
		felder: { email: 'a@b.de', code: '' },
		antwort: null,
		de: 'E-Mail und Code erforderlich',
		key: 'auth.code.fehler_pflicht'
	},
	{
		name: 'code_zu_viele_versuche',
		datei: 'magic-link/verify/+page.server.ts',
		felder: { email: 'a@b.de', code: '123456' },
		antwort: { status: 400, body: { error: 'max_attempts_exceeded' } },
		de: 'Zu viele Fehlversuche. Bitte fordere einen neuen Code an.',
		key: 'auth.code.fehler_zu_viele'
	},
	{
		name: 'code_ungueltig',
		datei: 'magic-link/verify/+page.server.ts',
		felder: { email: 'a@b.de', code: '123456' },
		antwort: { status: 400, body: { error: 'invalid' } },
		de: 'Ungültiger oder abgelaufener Code.',
		key: 'auth.code.fehler_ungueltig'
	},
	{
		name: 'bestaetigen_link_unvollstaendig',
		datei: 'verify-email/+page.server.ts',
		felder: { user: '', token: '' },
		antwort: null,
		de: 'Ungültiger Bestätigungslink.',
		key: 'auth.bestaetigen.fehler_ungueltig_link'
	},
	{
		name: 'bestaetigen_adresse_vergeben',
		datei: 'verify-email/+page.server.ts',
		felder: { user: 'anna', token: 't' },
		antwort: { status: 409, body: { error: 'address_taken' } },
		de: 'Diese Adresse gehört inzwischen zu einem anderen Konto. Bitte ändere deine Adresse im Konto erneut.',
		key: 'auth.bestaetigen.fehler_adresse_vergeben'
	},
	{
		name: 'bestaetigen_link_abgelaufen',
		datei: 'verify-email/+page.server.ts',
		felder: { user: 'anna', token: 't' },
		antwort: { status: 400, body: { error: 'token expired' } },
		de: 'Der Bestätigungslink ist abgelaufen. Bitte ändere deine Adresse erneut, um einen neuen Link zu erhalten.',
		key: 'auth.bestaetigen.fehler_abgelaufen'
	},
	{
		name: 'bestaetigen_link_ungueltig',
		datei: 'verify-email/+page.server.ts',
		felder: { user: 'anna', token: 't' },
		antwort: { status: 400, body: { error: 'x' } },
		de: 'Der Bestätigungslink ist ungültig oder wurde bereits verwendet.',
		key: 'auth.bestaetigen.fehler_ungueltig'
	}
];

describe('#2650 AC-3 — Actions der Auth-Routen: Deutsch unverändert, Englisch aus dem Katalog', () => {
	for (const fall of ACTIONS_FAELLE) {
		test(`AC-3_action_${fall.name}`, async () => {
			const de = (await aktion(fall.datei, fall.felder, 'de', fall.antwort)).data.error;
			const en = (await aktion(fall.datei, fall.felder, 'en', fall.antwort)).data.error;
			assert.equal(de, fall.de, `AC-3: deutscher Text geändert (${fall.name})`);
			assert.equal(en, trFor('en', fall.key as never), `AC-3: englischer Katalogtext fehlt (${fall.name})`);
			assert.notEqual(en, de, `AC-3: englischer Text ist identisch mit dem deutschen (${fall.name})`);
			assert.deepEqual(restwoerter(en), [], `AC-3: deutsches Restwort im englischen Text (${fall.name})`);
		});
	}
});

describe('#2650 AC-2 — Auth-Seiten in Sprache de: byte-gleich (normalisiert) zur Ausgabe vor der Umstellung', () => {
	for (const route of ['forgot-password', 'reset-password', 'magic-link', 'magic-link-verify', 'verify-email']) {
		test(`AC-2_${route}_alle_golden_zustaende_sind_gleich`, async () => {
			const fall = GOLDEN_FAELLE.find((g) => g.route === route);
			assert.ok(fall, `Golden-Fälle für ${route} fehlen`);
			const erwartet = fixtureLesen(readFileSync(path.join(FIXTURE_DIR, `${route}.de.html`), 'utf-8'));
			for (const f of fall!.faelle) {
				const soll = erwartet.get(f.name);
				assert.ok(soll !== undefined, `Golden-Fixture fehlt für ${route}/${f.name}`);
				assert.equal(golden(await f.render()), golden(soll!), `AC-2: ${route}/${f.name} weicht von der deutschen Ausgabe ab`);
			}
		});
	}
});
