// TDD RED — Issue #2268 (S1 von #2146, Epic #2138): app-weiter Footer mit
// „Impressum" und „Datenschutz".
//
// Spec: docs/specs/modules/app_footer_rechtstexte.md (AC-1 bis AC-7)
//
// WARUM DAS LAYOUT GERENDERT WIRD: Ob der Footer auf einer Route erscheint,
// entscheidet allein der `{#if}`-Baum in `+layout.svelte` — nicht der Baustein
// `AppFooter.svelte`. Ein Test, der nur den Baustein rendert, wäre grün, auch
// wenn das Layout ihn in einem Zweig vergisst oder im Showcase-Zweig einschaltet
// (Prüfort ≠ Wirkort). Deshalb wird das ECHTE Layout je Pfad serverseitig
// gerendert (svelte/server); `page.url.pathname` kommt aus dem Hook-Stub
// `layout-ssr-hooks.mjs` (`$app/state`, je Aufruf frisch gelesen).
//
// Die Seiteninhalte (`children`) sind ein Marker-Element; der Test misst, WO der
// Footer relativ zu `<main>` und Inhalt steht.
//
// RED HEUTE: `AppFooter.svelte` und die Verdrahtung im Layout existieren nicht —
// auf keiner Route steht ein `<footer>`.
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei auflösen.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/routes/__tests__/app_footer_je_route.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> routes -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../..');

register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);
register(
	pathToFileURL(path.join(FRONTEND, 'src/lib/components/trip-new/__tests__/ssrRunesHook.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);
register(pathToFileURL(path.join(HERE, 'layout-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const { render } = await import('svelte/server');
const Layout = (await import(pathToFileURL(path.join(FRONTEND, 'src/routes/+layout.svelte')).href))
	.default;

const IMPRESSUM = 'https://www.henemm.com/footer-information/imprint/';
const DATENSCHUTZ = 'https://www.henemm.com/legal/gregor-zwanzig/privacy-policy/';

/** Layout für einen Pfad rendern; der Seiteninhalt ist ein Marker-Element. */
function layoutHtml(pathname: string): string {
	(globalThis as Record<string, unknown>).__gzLayoutTestPath = pathname;
	const { body } = render(Layout, {
		props: {
			children: (renderer: { push: (s: string) => void }) =>
				renderer.push('<div data-testid="seiteninhalt">INHALT</div>'),
			data: { userId: 'user-a', displayName: 'Anna' }
		}
	});
	return body.replace(/<!--[\s\S]*?-->/g, '');
}

/** Inhalt des ersten Elements `tag` (ohne Verschachtelung gleichnamiger Tags). */
function inhaltVon(html: string, tag: string): string | null {
	const m = html.match(new RegExp(`<${tag}\\b[^>]*>([\\s\\S]*?)</${tag}>`));
	return m ? m[1] : null;
}

function footerLinks(html: string): { text: string; tag: string }[] {
	const footer = inhaltVon(html, 'footer');
	if (footer === null) return [];
	return [...footer.matchAll(/<a\b[^>]*>[\s\S]*?<\/a>/g)].map((m) => ({
		tag: m[0].match(/^<a\b[^>]*>/)![0],
		text: m[0].replace(/<[^>]+>/g, '').trim()
	}));
}

function attr(tag: string, name: string): string | null {
	const m = tag.match(new RegExp(`\\s${name}="([^"]*)"`));
	return m ? m[1] : null;
}

describe('AC-1: App-Route (/trips) — Footer mit genau zwei Links, innerhalb <main> als letztes Kind', () => {
	const html = layoutHtml('/trips');

	test('genau zwei Links: Impressum und Datenschutz mit wörtlichen Zielen', () => {
		const links = footerLinks(html);
		assert.equal(links.length, 2, `Erwartet genau 2 Footer-Links, gefunden: ${links.length}`);
		assert.deepEqual(
			links.map((l) => [l.text, attr(l.tag, 'href')]),
			[
				['Impressum', IMPRESSUM],
				['Datenschutz', DATENSCHUTZ]
			]
		);
	});

	test('der Footer steht INNERHALB <main> und ist dessen letztes Kind', () => {
		const main = inhaltVon(html, 'main');
		assert.ok(main !== null, 'kein <main> im App-Zweig gerendert');
		assert.ok(main.includes('<footer'), 'Footer steht nicht innerhalb von <main>');
		assert.ok(
			main.indexOf('INHALT') < main.indexOf('<footer'),
			'Footer steht VOR dem Seiteninhalt, nicht danach'
		);
		assert.match(
			main.trim(),
			/<\/footer>$/,
			'nach dem Footer folgt noch weiteres Markup — er ist nicht das letzte Kind von <main>'
		);
	});

	test('es gibt genau EINEN Footer (kein zweiter neben <main>)', () => {
		assert.equal((html.match(/<footer\b/g) ?? []).length, 1);
	});
});

describe('AC-2: öffentlicher Zweig (/login, /register) — Footer ohne Sidebar und BottomNav', () => {
	for (const pfad of ['/login', '/register']) {
		test(`${pfad}: derselbe Footer mit den zwei Links, kein App-Chrome`, () => {
			const html = layoutHtml(pfad);
			assert.deepEqual(
				footerLinks(html).map((l) => [l.text, attr(l.tag, 'href')]),
				[
					['Impressum', IMPRESSUM],
					['Datenschutz', DATENSCHUTZ]
				],
				`Auf ${pfad} fehlt der Footer oder seine Links weichen ab`
			);
			assert.ok(html.includes('INHALT'), 'Seiteninhalt fehlt');
			assert.ok(
				html.indexOf('INHALT') < html.indexOf('<footer'),
				'Footer steht nicht NACH dem Seiteninhalt'
			);
			assert.ok(!html.includes('desktop-sidebar'), 'Sidebar im öffentlichen Zweig gerendert');
			assert.ok(!html.includes('<main'), 'App-<main> im öffentlichen Zweig gerendert');
			assert.ok(!/bottom-?nav/i.test(html), 'BottomNav im öffentlichen Zweig gerendert');
		});
	}
});

describe('AC-3: Showcase /_design — bewusst KEIN Footer', () => {
	test('weder <footer> noch einer der beiden Links im Ergebnis', () => {
		const html = layoutHtml('/_design');
		assert.ok(html.includes('INHALT'), 'Showcase rendert den Seiteninhalt nicht');
		assert.ok(!html.includes('<footer'), 'Showcase trägt einen <footer>');
		assert.ok(!html.includes(IMPRESSUM), 'Impressum-Link im Showcase');
		assert.ok(!html.includes(DATENSCHUTZ), 'Datenschutz-Link im Showcase');
	});
});

describe('AC-4: /trips/new (App-Zweig ohne BottomNav) — Footer unterhalb des Editors', () => {
	const html = layoutHtml('/trips/new');

	test('Footer als letztes Kind von <main>, mit beiden Links', () => {
		const main = inhaltVon(html, 'main');
		assert.ok(main !== null, 'kein <main> gerendert');
		assert.match(main.trim(), /<\/footer>$/, 'Footer ist nicht das letzte Kind von <main>');
		assert.equal(footerLinks(html).length, 2);
	});

	test('keine BottomNav, und der Footer ist kein festes/klebendes Element', () => {
		assert.ok(!/bottom-?nav/i.test(html), 'BottomNav auf /trips/new gerendert');
		const footerTag = html.match(/<footer\b[^>]*>/)?.[0] ?? '';
		assert.ok(footerTag !== '', 'kein <footer> gerendert');
		assert.ok(!/position:\s*(fixed|sticky)/.test(footerTag), 'Footer ist fixed/sticky');
	});
});

describe('AC-5: /compare/new (Editor mit klebendem Fuß) — Footer erreichbar hinter dem Editor', () => {
	test('Footer steht im <main> NACH dem Editorinhalt, nicht als Geschwister neben <main>', () => {
		const html = layoutHtml('/compare/new');
		const main = inhaltVon(html, 'main');
		assert.ok(main !== null, 'kein <main> gerendert');
		assert.ok(main.includes('<footer'), 'Footer nicht innerhalb von <main>');
		assert.ok(main.indexOf('INHALT') < main.indexOf('<footer'), 'Footer steht vor dem Editor');
		assert.match(main.trim(), /<\/footer>$/);
		assert.equal(footerLinks(html).length, 2);
	});
});

describe('AC-6: Mobil — Footer scrollt mit und erbt die BottomNav-Freihaltung', () => {
	test('der Footer steht innerhalb des Elements mit Klasse mobile-scroll-pad', () => {
		const html = layoutHtml('/trips');
		const m = html.match(/<main\b[^>]*class="([^"]*)"[^>]*>/);
		assert.ok(m, '<main> ohne class gerendert');
		assert.ok(
			m[1].split(/\s+/).includes('mobile-scroll-pad'),
			`<main> trägt mobile-scroll-pad nicht: "${m[1]}"`
		);
		assert.ok(inhaltVon(html, 'main')?.includes('<footer'), 'Footer nicht in <main>');
	});

	test('der Footer ist kein position:fixed-Element', () => {
		const html = layoutHtml('/trips');
		const footerTag = html.match(/<footer\b[^>]*>/)?.[0] ?? '';
		assert.ok(footerTag !== '', 'kein <footer> gerendert');
		assert.ok(!/position:\s*fixed/.test(footerTag), 'Footer ist position:fixed');
	});
});

describe('AC-7: Links öffnen in neuem Tab, ohne Rückverweis', () => {
	for (const pfad of ['/trips', '/login']) {
		test(`${pfad}: target=_blank und rel enthält noopener und noreferrer`, () => {
			const links = footerLinks(layoutHtml(pfad));
			assert.equal(links.length, 2, `Auf ${pfad} fehlen die Footer-Links`);
			for (const l of links) {
				assert.equal(attr(l.tag, 'target'), '_blank', `${l.text}: target != _blank`);
				const rel = (attr(l.tag, 'rel') ?? '').split(/\s+/);
				assert.ok(rel.includes('noopener'), `${l.text}: rel ohne noopener`);
				assert.ok(rel.includes('noreferrer'), `${l.text}: rel ohne noreferrer`);
			}
		});
	}
});
