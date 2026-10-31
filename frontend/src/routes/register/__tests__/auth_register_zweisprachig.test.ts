// TDD RED — Issue #2650 (i18n F1, Epic #2644), AC-2, AC-3, AC-4, AC-5 für /register.
//
// AC-2: deutsche Seite (Zustände inkl. Einladung) byte-gleich (normalisiert) zur
//       Ausgabe vor der Umstellung.
// AC-3: englische Seite mit gültiger, ungültiger und unsicherer Einladung ohne
//       deutsches Restwort; das Einladungs-Level ist Platzhalter.
// AC-4: die echte Action liefert auf Deutsch exakt die bisherigen Fehlertexte
//       (429, 409 email_taken, 409 Kennung, 400 invite_invalid, 400 invalid_email,
//       400 sonst, 500, Passwörter ungleich) und auf Englisch den Katalogtext
//       (anderer, nicht leerer Wert).
// AC-5: zwei gleichzeitige Anfragen (en und de) mit demselben Fehlerfall bekommen
//       je ihre eigene Sprache.
//
// Die Action läuft ECHT; ersetzt ist nur die globale fetch-Funktion (Netzgrenze
// zur Go-API). Kein Mock des Prüflings.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/register/__tests__/auth_register_zweisprachig.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import {
	FIXTURE_DIR,
	FRONTEND,
	GOLDEN_FAELLE,
	TIER_LABEL_FREE,
	fixtureLesen,
	golden,
	registerSeite,
	restwoerter,
	sichtbarerText,
	trFor,
	type Lang
} from '../../../routes/__tests__/auth_zweisprachig_harness.ts';

const { actions } = await import(pathToFileURL(path.join(FRONTEND, 'src/routes/register/+page.server.ts')).href);

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

/** Führt die echte Registrierungs-Action in `lang` aus und liefert ihre Fehlermeldung. */
async function registrieren(lang: Lang, antwort: Antwort | null, passwort2 = 'geheim1234'): Promise<string> {
	if (antwort) aktuelleAntwort = antwort;
	const body = new FormData();
	body.set('username', 'neuling');
	body.set('email', 'neu@beispiel.de');
	body.set('password', 'geheim1234');
	body.set('confirmPassword', passwort2);
	const ereignis = { request: new Request('http://localhost/register', { method: 'POST', body }), locals: { lang } };
	const ergebnis = (await actions.default(ereignis)) as { data: { error?: string } };
	return ergebnis.data.error ?? '';
}

const FAELLE: Array<{ name: string; antwort: Antwort | null; passwort2?: string; de: string; key: string }> = [
	{
		name: 'passwoerter_ungleich',
		antwort: null,
		passwort2: 'anders1234',
		de: 'Passwörter stimmen nicht überein',
		key: 'auth.register.passwoerter_ungleich'
	},
	{
		name: '429',
		antwort: { status: 429, body: {} },
		de: 'Zu viele Versuche — bitte in einigen Minuten erneut versuchen.',
		key: 'auth.fehler.zu_viele_versuche'
	},
	{
		name: '409_email_taken',
		antwort: { status: 409, body: { error: 'email_taken' } },
		de: "Diese E-Mail-Adresse gehört bereits zu einem Konto. Melde dich an – bei Bedarf über 'Passwort vergessen' oder den Anmeldelink per E-Mail.",
		key: 'auth.register.email_vergeben'
	},
	{
		name: '409_kennung',
		antwort: { status: 409, body: { error: 'user already exists' } },
		de: 'Benutzername bereits vergeben',
		key: 'auth.register.benutzername_vergeben'
	},
	{
		name: '400_invite_invalid',
		antwort: { status: 400, body: { error: 'invite_invalid' } },
		de: 'Die Einladung ist nicht (mehr) gültig. Lade die Seite ohne Einladungslink neu, um dich normal zu registrieren.',
		key: 'auth.register.fehler_einladung_ungueltig'
	},
	{
		name: '400_invalid_email',
		antwort: { status: 400, body: { error: 'invalid_email' } },
		de: 'Bitte eine gültige E-Mail-Adresse angeben',
		key: 'auth.register.fehler_email_ungueltig'
	},
	{
		name: '400_sonst',
		antwort: { status: 400, body: {} },
		de: 'Benutzername (3–50 Zeichen), E-Mail und Passwort (mind. 8 Zeichen) erforderlich',
		key: 'auth.register.fehler_pflichtfelder'
	},
	{
		name: '500',
		antwort: { status: 500, body: {} },
		de: 'Registrierung fehlgeschlagen',
		key: 'auth.register.fehler_allgemein'
	}
];

describe('#2650 AC-4 — Registrierungs-Action: Deutsch unverändert, Englisch aus dem Katalog', () => {
	for (const fall of FAELLE) {
		test(`AC-4_${fall.name}`, async () => {
			const deText = await registrieren('de', fall.antwort, fall.passwort2);
			const enText = await registrieren('en', fall.antwort, fall.passwort2);
			assert.equal(deText, fall.de, `AC-4: deutscher Fehlertext ${fall.name} hat sich geändert`);
			assert.equal(enText, trFor('en', fall.key as never), `AC-4: englischer Katalogtext fehlt für ${fall.name}`);
			assert.notEqual(enText, '', `AC-4: englischer Text für ${fall.name} ist leer`);
			assert.notEqual(enText, deText, `AC-4: englischer Text für ${fall.name} ist identisch mit dem deutschen`);
			assert.deepEqual(restwoerter(enText), [], `AC-4: deutsches Restwort im englischen Text ${fall.name}`);
		});
	}
});

describe('#2650 AC-5 — gleichzeitige Anfragen mischen die Sprache nicht', () => {
	test('AC-5_en_und_de_parallel_bleiben_getrennt', async () => {
		const [en, de] = await Promise.all([
			registrieren('en', { status: 429, body: {} }),
			registrieren('de', { status: 429, body: {} })
		]);
		assert.equal(en, trFor('en', 'auth.fehler.zu_viele_versuche'), 'AC-5: die englische Anfrage erhielt keinen englischen Text');
		assert.equal(de, 'Zu viele Versuche — bitte in einigen Minuten erneut versuchen.', 'AC-5: die deutsche Anfrage wurde beeinflusst');
	});
});

describe('#2650 AC-3 — /register in Sprache en: alle Einladungszustände ohne Restwort', () => {
	test('AC-3_leer_englisch_ohne_restwort', async () => {
		const html = await registerSeite({ status: 'none' }, null, 'en');
		assert.deepEqual(restwoerter(html), []);
	});

	test('AC-3_gueltige_einladung_zeigt_level_als_platzhalter', async () => {
		const html = await registerSeite({ status: 'valid', token: 't1', tier: 'free' }, null, 'en');
		assert.deepEqual(restwoerter(html, [TIER_LABEL_FREE]), []);
		assert.ok(
			sichtbarerText(html).includes(trFor('en', 'auth.register.einladung_gueltig', { level: TIER_LABEL_FREE })),
			'AC-3: der Einladungshinweis mit Level fehlt in en'
		);
	});

	test('AC-3_unsichere_und_ungueltige_einladung_englisch', async () => {
		const unbekannt = await registerSeite({ status: 'unknown', token: 't2' }, null, 'en');
		const ungueltig = await registerSeite({ status: 'invalid' }, null, 'en');
		assert.deepEqual(restwoerter(unbekannt), []);
		assert.deepEqual(restwoerter(ungueltig), []);
	});

	test('AC-3_fehlermeldung_der_action_englisch_angezeigt', async () => {
		const meldung = await registrieren('en', null, 'anders1234');
		const html = await registerSeite({ status: 'none' }, { error: meldung, username: 'neuling', email: 'neu@beispiel.de' }, 'en');
		assert.deepEqual(restwoerter(html), []);
	});
});

describe('#2650 AC-2 — /register in Sprache de: byte-gleich (normalisiert) zur Ausgabe vor der Umstellung', () => {
	test('AC-2_alle_golden_zustaende_sind_gleich', async () => {
		const fall = GOLDEN_FAELLE.find((g) => g.route === 'register');
		assert.ok(fall, 'Golden-Fälle für register fehlen');
		const erwartet = fixtureLesen(readFileSync(path.join(FIXTURE_DIR, 'register.de.html'), 'utf-8'));
		for (const f of fall!.faelle) {
			const soll = erwartet.get(f.name);
			assert.ok(soll !== undefined, `Golden-Fixture fehlt für Zustand ${f.name}`);
			assert.equal(golden(await f.render()), golden(soll!), `AC-2: Zustand ${f.name} weicht von der deutschen Ausgabe ab`);
		}
	});
});
