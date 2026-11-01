// TDD RED — Issue #2650 (i18n F1, Epic #2644), AC-1 und AC-2 für /login.
//
// AC-1: Besucher mit Sprache en sieht auf /login jeden Text englisch; nach Abzug
//       aller englischen auth.*-Katalogwerte bleibt kein deutsches Wort übrig
//       (Eigenname „Gregor" ausgenommen). Gemessen wird die echte Seite
//       (svelte/server) mit dem echten load() und den Fehlercodes der Action.
// AC-2: dieselben Zustände auf Deutsch sind (bis auf Leerraum und Svelte-
//       Hydrations-Kommentare) byte-gleich zur Ausgabe vor der Umstellung.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/login/__tests__/auth_login_zweisprachig.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import {
	GOLDEN_FAELLE,
	FIXTURE_DIR,
	fixtureLesen,
	golden,
	loginSeite,
	restwoerter,
	sichtbarerText,
	trFor
} from '../../__tests__/auth_zweisprachig_harness.ts';

const ZUSTAENDE = [
	{ name: 'leer', href: 'http://localhost/login', form: null },
	{ name: 'fehler_invalid', href: 'http://localhost/login', form: { error: 'Invalid credentials', username: 'anna', resent: false } },
	{ name: 'fehler_rate', href: 'http://localhost/login', form: { error: 'Rate limit exceeded', username: 'anna', resent: false } },
	{
		name: 'fehler_pflicht',
		href: 'http://localhost/login',
		form: { error: 'Username and password required', username: '', resent: false }
	},
	{ name: 'email_nicht_bestaetigt', href: 'http://localhost/login', form: { error: 'email_not_verified', username: 'anna', resent: false } },
	{ name: 'erneut_gesendet', href: 'http://localhost/login', form: { error: 'email_not_verified', username: 'anna', resent: true } },
	{ name: 'registriert', href: 'http://localhost/login?registered=1', form: null },
	{ name: 'sitzung_abgelaufen', href: 'http://localhost/login?expired=1', form: null },
	{ name: 'google_oauth_failed', href: 'http://localhost/login?error=oauth_failed', form: null },
	{ name: 'google_oauth_link_failed', href: 'http://localhost/login?error=oauth_link_failed', form: null },
	{ name: 'google_email_nicht_bestaetigt', href: 'http://localhost/login?error=email_not_verified', form: null }
];

describe('#2650 AC-1 — /login in Sprache en: kein deutsches Restwort', () => {
	for (const z of ZUSTAENDE) {
		test(`AC-1_${z.name}_englisch_ohne_restwort`, async () => {
			const html = await loginSeite(z.href, z.form, 'en');
			const rest = restwoerter(html);
			assert.deepEqual(rest, [], `AC-1: deutsche Restwörter im Zustand ${z.name}: ${rest.join(', ')}`);
		});
	}

	test('AC-1_fehlercodes_werden_auf_englische_katalogtexte_abgebildet', async () => {
		const rate = sichtbarerText(await loginSeite('http://localhost/login', ZUSTAENDE[2].form, 'en'));
		const invalid = sichtbarerText(await loginSeite('http://localhost/login', ZUSTAENDE[1].form, 'en'));
		const pflicht = sichtbarerText(await loginSeite('http://localhost/login', ZUSTAENDE[3].form, 'en'));
		assert.ok(rate.includes(trFor('en', 'auth.fehler.zu_viele_versuche')), 'AC-1: Rate-Limit-Text fehlt in en');
		assert.ok(invalid.includes(trFor('en', 'auth.login.ungueltige_daten')), 'AC-1: Invalid-credentials-Text fehlt in en');
		assert.ok(pflicht.includes(trFor('en', 'auth.login.pflichtfelder')), 'AC-1: Pflichtfeld-Text fehlt in en');
		assert.ok(!invalid.includes('Invalid credentials'), 'AC-1: der Rohcode darf nicht sichtbar sein');
	});

	test('AC-1_google_fehlercode_zeigt_englischen_text', async () => {
		const html = sichtbarerText(await loginSeite('http://localhost/login?error=oauth_failed', null, 'en'));
		assert.ok(
			html.includes(trFor('en', 'auth.login.google_fehler_allgemein')),
			'AC-1: der Google-Fehlercode oauth_failed zeigt keinen englischen Katalogtext'
		);
	});
});

describe('#2650 AC-2 — /login in Sprache de: byte-gleich (normalisiert) zur Ausgabe vor der Umstellung', () => {
	const fall = GOLDEN_FAELLE.find((g) => g.route === 'login');
	const erwartet = fixtureLesen(readFileSync(path.join(FIXTURE_DIR, 'login.de.html'), 'utf-8'));

	test('AC-2_alle_golden_zustaende_sind_gleich', async () => {
		assert.ok(fall, 'Golden-Fälle für login fehlen');
		for (const f of fall!.faelle) {
			const ist = await f.render();
			const soll = erwartet.get(f.name);
			assert.ok(soll !== undefined, `Golden-Fixture fehlt für Zustand ${f.name}`);
			assert.equal(golden(ist), golden(soll!), `AC-2: Zustand ${f.name} weicht von der deutschen Ausgabe ab`);
		}
	});
});
