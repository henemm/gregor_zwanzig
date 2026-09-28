// TDD RED — Issue #2277 Scheibe S2b: die App-weite BottomNav ist auf BEIDEN
// Anlege-Seiten ausgeblendet (`isWizard` → `istAnlegeSeite`).
//
// Spec: docs/specs/modules/fix_2277_s2b_mobile_rahmen_angleichung.md (AC-6)
//
// Ob die BottomNav erscheint, entscheidet allein der `{#if}`-Baum in
// `+layout.svelte` — deshalb wird das ECHTE Layout je Pfad serverseitig
// gerendert; `page.url.pathname` liefert der Hook-Stub `layout-ssr-hooks.mjs`
// (Vorbild app_footer_je_route.test.ts, Issue #2268).
//
// RED HEUTE: `isWizard` prüft nur `/trips/new` — auf `/compare/new` rendert
// die BottomNav weiterhin.
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei auflösen.
//
// Ausführen:
//   cd frontend && npm test -- src/routes/__tests__/layout_istanlegeseite_bottomnav.test.ts

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
const Layout = (await import(pathToFileURL(path.join(HERE, '..', '+layout.svelte')).href)).default;

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

describe('AC-6: BottomNav auf beiden Anlege-Seiten ausgeblendet, sonst sichtbar', () => {
	test('/compare/new: KEINE BottomNav', () => {
		const html = layoutHtml('/compare/new');
		assert.ok(html.includes('INHALT'), 'Messaufbau kaputt: Seiteninhalt fehlt im App-Zweig.');
		assert.ok(
			!/bottom-?nav/i.test(html),
			'AC-6 FAIL: auf /compare/new rendert das Layout weiterhin eine BottomNav.'
		);
	});

	test('/trips/new: weiterhin KEINE BottomNav', () => {
		const html = layoutHtml('/trips/new');
		assert.ok(html.includes('INHALT'), 'Messaufbau kaputt: Seiteninhalt fehlt im App-Zweig.');
		assert.ok(!/bottom-?nav/i.test(html), 'AC-6 FAIL: auf /trips/new rendert eine BottomNav.');
	});

	// Der Leerraum entsteht am <main>-Padding (.mobile-scroll-pad reserviert die
	// Nav-Hoehe); auf Anlege-Seiten hebt der Modifikator das auf, padding-top bleibt.
	function mainKlassen(html: string): string[] {
		const m = /<main\b[^>]*\bclass="([^"]*)"/.exec(html);
		assert.ok(m, 'Messaufbau kaputt: kein <main class> im Layout.');
		return m![1].split(/\s+/);
	}

	for (const pfad of ['/trips/new', '/compare/new']) {
		test(`${pfad}: <main> hebt die BottomNav-Reservierung auf, behält mobile-scroll-pad (padding-top)`, () => {
			const klassen = mainKlassen(layoutHtml(pfad));
			assert.ok(klassen.includes('mobile-scroll-pad'), `${pfad}: mobile-scroll-pad fehlt — Safe-Area oben ginge verloren.`);
			assert.ok(
				klassen.includes('mobile-scroll-pad--ohne-nav'),
				`${pfad}: <main> reserviert unten weiter Platz für die ausgeblendete BottomNav.`
			);
		});
	}

	test('/trips: <main> behält die BottomNav-Reservierung', () => {
		const klassen = mainKlassen(layoutHtml('/trips'));
		assert.ok(klassen.includes('mobile-scroll-pad'));
		assert.ok(
			!klassen.includes('mobile-scroll-pad--ohne-nav'),
			'/trips: Reservierung aufgehoben, obwohl die BottomNav dort sichtbar ist.'
		);
	});

	test('/trips (Kontrollroute): weiterhin EINE BottomNav', () => {
		const html = layoutHtml('/trips');
		assert.ok(
			/bottom-?nav/i.test(html),
			'AC-6 FAIL (Positivkontrolle): auf /trips fehlt die BottomNav — die Messung wäre sonst vakuum-grün.'
		);
	});
});
