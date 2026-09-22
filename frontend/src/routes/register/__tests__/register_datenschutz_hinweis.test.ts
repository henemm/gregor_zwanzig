// TDD RED — Issue #2268 (S1 von #2146, Epic #2138): Hinweissatz mit
// Datenschutz-Link unter dem Knopf „Konto erstellen".
//
// Spec: docs/specs/modules/app_footer_rechtstexte.md (AC-8, AC-9, AC-10)
//
// Die Registrierungsseite wird ECHT serverseitig gerendert (svelte/server, Hooks:
// frontend/test-svelte-ssr-hooks.mjs), mit `googleEnabled` true UND false — der
// Satz muss in beiden Fällen direkt unter dem Knopf stehen, VOR dem
// „oder"-Trenner. Der bestehende register_email_taken.test.ts ist ein
// Action-Test ohne Render und bleibt unberührt.
//
// RED HEUTE: Die Seite hat keinen Hinweissatz.
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei auflösen.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/register/__tests__/register_datenschutz_hinweis.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> register -> routes -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../..');

register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const Register = (
	await import(pathToFileURL(path.join(FRONTEND, 'src/routes/register/+page.svelte')).href)
).default;

const DATENSCHUTZ = 'https://www.henemm.com/legal/gregor-zwanzig/privacy-policy/';
const SATZ = 'Hinweise zum Umgang mit deinen Daten: Datenschutz';

function seite(googleEnabled: boolean): string {
	const { body } = render(Register, { props: { form: null, data: { googleEnabled } } });
	return body.replace(/<!--[\s\S]*?-->/g, '');
}

/** Alle <p>-Absätze, deren sichtbarer Text den Satz enthält. */
function hinweisAbsaetze(html: string): string[] {
	return [...html.matchAll(/<p\b[^>]*>[\s\S]*?<\/p>/g)]
		.map((m) => m[0])
		.filter((p) => p.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').includes('Hinweise zum Umgang'));
}

for (const google of [true, false]) {
	describe(`googleEnabled=${google}`, () => {
		const html = seite(google);

		test('AC-8: der Satz steht wörtlich da', () => {
			const absaetze = hinweisAbsaetze(html);
			assert.equal(absaetze.length, 1, 'Erwartet genau einen Hinweisabsatz');
			const text = absaetze[0].replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
			assert.equal(text, SATZ);
		});

		test('AC-8: genau ein Link im Absatz — nur auf „Datenschutz", mit Ziel/target/rel', () => {
			const absatz = hinweisAbsaetze(html)[0] ?? '';
			const links = [...absatz.matchAll(/<a\b[^>]*>[\s\S]*?<\/a>/g)].map((m) => m[0]);
			assert.equal(links.length, 1, `Erwartet genau 1 Link, gefunden: ${links.length}`);
			assert.equal(links[0].replace(/<[^>]+>/g, '').trim(), 'Datenschutz');
			assert.match(links[0], new RegExp(`href="${DATENSCHUTZ}"`));
			assert.match(links[0], /target="_blank"/);
			const rel = links[0].match(/rel="([^"]*)"/)?.[1].split(/\s+/) ?? [];
			assert.ok(rel.includes('noopener') && rel.includes('noreferrer'), `rel: ${rel.join(' ')}`);
		});

		test('AC-9: Reihenfolge Knopf → Satz (→ „oder"-Trenner)', () => {
			const knopf = html.indexOf('Konto erstellen</button>');
			const satz = html.indexOf('Hinweise zum Umgang');
			assert.ok(knopf >= 0, 'Knopf „Konto erstellen" nicht gefunden');
			assert.ok(satz >= 0, 'Hinweissatz nicht gefunden');
			assert.ok(satz > knopf, 'Der Satz steht nicht unter dem Knopf');
			if (google) {
				const oder = html.indexOf('>oder<');
				assert.ok(oder >= 0, '„oder"-Trenner fehlt bei googleEnabled=true');
				assert.ok(satz < oder, 'Der Satz steht HINTER dem „oder"-Trenner');
				assert.ok(satz < html.indexOf('/api/auth/google/init'), 'Satz steht hinter dem Google-Knopf');
			} else {
				assert.ok(!html.includes('>oder<'), 'ohne Google darf es keinen „oder"-Trenner geben');
			}
		});

		test('AC-8: der Satz steht NACH dem <form>, nicht darin (Formular unverändert)', () => {
			const formEnde = html.indexOf('</form>');
			assert.ok(formEnde >= 0);
			assert.ok(html.indexOf('Hinweise zum Umgang') > formEnde, 'Satz steht innerhalb des <form>');
		});

		test('AC-10: kein Zustimmungsschritt — 4 Eingaben, keine Checkbox, Knopf nicht gesperrt', () => {
			const form = html.match(/<form\b[\s\S]*?<\/form>/)?.[0] ?? '';
			const inputs = [...form.matchAll(/<input\b[^>]*>/g)].map((m) => m[0]);
			assert.equal(inputs.length, 4, `Erwartet 4 Eingabefelder, gefunden: ${inputs.length}`);
			assert.equal(inputs.filter((i) => /type="checkbox"/.test(i)).length, 0, 'Checkbox im Formular');
			assert.deepEqual(
				inputs.map((i) => i.match(/name="([^"]*)"/)?.[1]),
				['username', 'email', 'password', 'confirmPassword']
			);
			const knopf = form.match(/<button\b[^>]*type="submit"[^>]*>/)?.[0] ?? '';
			assert.ok(knopf !== '', 'Submit-Knopf fehlt');
			assert.ok(!/\sdisabled/.test(knopf), 'Knopf ist gesperrt');
		});
	});
}
