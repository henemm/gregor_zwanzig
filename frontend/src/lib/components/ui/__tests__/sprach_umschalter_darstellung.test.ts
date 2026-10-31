// Issue #2648 (i18n S3) — AC-7: der Besucher-Umschalter `DE | EN` steht genau
// einmal auf Startseite, Anmeldung und Registrierung (aktueller Knopf mit
// `aria-current`), in der angemeldeten Shell (Seitenleiste, geoeffnetes
// Konto-Menue) dagegen nicht. Alle Seiten laufen ECHT im SSR-Render; die
// Hooks stellen nur SvelteKits virtuelle Module bereit (`$app/*`) und oeffnen
// das Konto-Sheet (Vorbild: admin_nav_konto_sheet_durchreichung.test.ts).
// Spec: docs/specs/modules/i18n_s3_sprachumschalter_konto_2648.md
//
//   cd frontend && npm test -- src/lib/components/ui/__tests__/sprach_umschalter_darstellung.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> ui -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');
const SRC = path.join(FRONTEND, 'src');
const ROUTES_TESTS = path.join(SRC, 'routes/__tests__');
const base = pathToFileURL(FRONTEND + '/').href;
const hook = (p: string) => register(pathToFileURL(p).href, base);

hook(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs'));
hook(path.join(SRC, 'lib/components/trip-new/__tests__/ssrRunesHook.mjs'));
hook(path.join(ROUTES_TESTS, 'layout-ssr-hooks.mjs'));
hook(path.join(ROUTES_TESTS, 'konto-sheet-offen.hooks.mjs'));
hook(path.join(SRC, 'routes/login/__tests__/app-stores-stub-hooks.mjs'));

const { render } = await import('svelte/server');
const lade = async (rel: string) => (await import(pathToFileURL(path.join(SRC, rel)).href)).default;
const Startseite = await lade('routes/_start/Startseite.svelte');
const Login = await lade('routes/login/+page.svelte');
const Register = await lade('routes/register/+page.svelte');
const Layout = await lade('routes/+layout.svelte');
const { locale } = await import(pathToFileURL(path.join(SRC, 'lib/i18n/index.ts')).href);
after(() => locale.set('de'));

const MERKMAL = 'data-testid="sprach-umschalter"';
const strip = (html: string) => html.replace(/<!--[\s\S]*?-->/g, '');
const anzahl = (html: string, s: string) => html.split(s).length - 1;

/** Ausschnitt des (einzigen) Umschalter-Formulars. */
function umschalter(html: string): string {
	const start = html.indexOf(MERKMAL);
	assert.ok(start >= 0, 'Umschalter fehlt');
	const anfang = html.lastIndexOf('<form', start);
	return html.slice(anfang, html.indexOf('</form>', start) + 7);
}

/** Knopf (als HTML-Tag samt Text) mit dem Wert `l`. */
function knopf(form: string, l: string): string {
	const m = form.match(new RegExp(`<button[^>]*value="${l}"[^>]*>([^<]*)</button>`));
	assert.ok(m, `Knopf ${l} fehlt`);
	return m[0];
}

const SEITEN: Record<string, () => string> = {
	Startseite: () => render(Startseite).body,
	Anmeldung: () => render(Login, { props: { form: null, data: { googleEnabled: false } } }).body,
	Registrierung: () => render(Register, { props: { form: null, data: { googleEnabled: false } } }).body
};

describe('AC-7: Umschalter auf den Besucherseiten', () => {
	for (const [name, seite] of Object.entries(SEITEN)) {
		test(`${name}: genau ein Umschalter, Formular POST /lang mit DE und EN`, () => {
			locale.set('de');
			const html = strip(seite());
			assert.equal(anzahl(html, MERKMAL), 1, `${name}: Anzahl Umschalter`);
			const form = umschalter(html);
			assert.match(form, /method="POST"/i);
			assert.match(form, /action="\/lang"/);
			assert.match(knopf(form, 'de'), />DE<\/button>$/);
			assert.match(knopf(form, 'en'), />EN<\/button>$/);
			assert.match(knopf(form, 'de'), /name="lang"/);
			assert.match(knopf(form, 'de'), /type="submit"/);
		});
	}

	test('aktueller Knopf traegt aria-current, der andere nicht (de und en)', () => {
		locale.set('de');
		let form = umschalter(strip(SEITEN.Startseite()));
		assert.match(knopf(form, 'de'), /aria-current="true"/);
		assert.doesNotMatch(knopf(form, 'en'), /aria-current/);
		locale.set('en');
		form = umschalter(strip(SEITEN.Anmeldung()));
		assert.match(knopf(form, 'en'), /aria-current="true"/);
		assert.doesNotMatch(knopf(form, 'de'), /aria-current/);
	});

	test('Gruppenname aus dem Katalog in der aktuellen Sprache', () => {
		locale.set('en');
		assert.match(umschalter(strip(SEITEN.Registrierung())), /aria-label="Choose language"/);
		locale.set('de');
		assert.match(umschalter(strip(SEITEN.Registrierung())), /aria-label="Sprache wählen"/);
	});
});

describe('AC-7: kein Umschalter in der angemeldeten Shell', () => {
	test('Seitenleiste und geoeffnetes Konto-Menue enthalten keinen Umschalter', () => {
		(globalThis as Record<string, unknown>).__gzLayoutTestPath = '/trips';
		const html = strip(
			render(Layout, {
				props: {
					children: (r: { push: (s: string) => void }) => r.push('<div>INHALT</div>'),
					data: { userId: 'user-1', displayName: 'Uwe', isAdmin: false, lang: 'de' }
				}
			}).body
		);
		assert.ok(html.includes('data-testid="konto-sheet-export"'), 'Messaufbau: Konto-Sheet nicht offen');
		assert.ok(html.includes('INHALT'), 'Messaufbau: Layout ohne Inhalt');
		assert.equal(anzahl(html, MERKMAL), 0, 'angemeldete Shell zeigt einen Umschalter');
	});
});
