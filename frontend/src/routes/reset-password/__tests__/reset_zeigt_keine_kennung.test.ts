// Issue #2194 (E-Mail als Login-Kennung) — Nachbesserung Reset-Seite.
// Spec: docs/specs/modules/email_login_identifier.md (Affected Files: reset-password)
//
// Neue Konten tragen eine automatisch erzeugte Kennung `u-<8hex>`. Die Seite
// „Passwort zuruecksetzen" darf sie dem Nutzer nicht als editierbares
// „Benutzername"-Feld zeigen: die Kennung kommt aus dem Link (`?user=`) und
// wird unsichtbar mitgeschickt.
//
// Gemessen wird die ECHTE Seite mit dem ECHTEN `load` (Harness #2650), in de
// und en. Kein Dateiinhalt-Check.
//
//   cd frontend && npm test -- src/routes/reset-password/__tests__/reset_zeigt_keine_kennung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { laedeLoad, rendere, sichtbarerText, type Lang } from '../../__tests__/auth_zweisprachig_harness.ts';

const SPRACHEN: Lang[] = ['de', 'en'];
const KENNUNG = 'u-1a2b3c4d';
const LINK = `http://localhost/reset-password?user=${KENNUNG}&token=abc123`;

type Eingabe = Record<string, string>;

function eingaben(html: string): Eingabe[] {
	return [...html.matchAll(/<input\b[^>]*>/g)].map((m) => {
		const attrs: Eingabe = {};
		for (const a of m[0].matchAll(/\s([a-zA-Z:-]+)(?:="([^"]*)")?/g)) attrs[a[1].toLowerCase()] = a[2] ?? '';
		return attrs;
	});
}

async function resetSeite(lang: Lang): Promise<string> {
	const data = await laedeLoad('reset-password/+page.server.ts', LINK);
	return rendere('reset-password/+page.svelte', { form: null, data }, lang);
}

describe('#2194 — Reset-Seite zeigt die Konto-Kennung nicht als Benutzername-Feld', () => {
	for (const lang of SPRACHEN) {
		test(`reset_${lang}_kein_sichtbares_kennungsfeld`, async () => {
			const sichtbar = eingaben(await resetSeite(lang)).filter((e) => e.type !== 'hidden');
			const kennung = sichtbar.filter((e) => e.name === 'username' || e.value === KENNUNG);
			assert.deepEqual(kennung, [], `${lang}: sichtbares Eingabefeld fuer die Kennung gefunden`);
		});

		test(`reset_${lang}_verstecktes_feld_traegt_die_kennung_aus_dem_link`, async () => {
			const versteckt = eingaben(await resetSeite(lang)).filter((e) => e.type === 'hidden' && e.name === 'username');
			assert.equal(versteckt.length, 1, `${lang}: genau ein verstecktes Feld name="username" erwartet`);
			assert.equal(versteckt[0].value, KENNUNG, `${lang}: verstecktes Feld muss die Kennung aus ?user= tragen`);
		});

		test(`reset_${lang}_kein_sichtbarer_text_benutzername`, async () => {
			const text = sichtbarerText(await resetSeite(lang));
			assert.doesNotMatch(text, /benutzername|username/i, `${lang}: sichtbarer Text nennt „Benutzername/Username": ${text}`);
			assert.ok(!text.includes(KENNUNG), `${lang}: die Kennung ist sichtbar: ${text}`);
		});
	}
});
