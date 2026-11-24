// Issue #3319 F001 (Adversary) — die oeffentlichen Funktionsseiten (/funktionen und jede
// Unterseite) rendern im Wurzel-Layout den oeffentlichen Zweig: KEINE App-Seitenleiste,
// KEINE untere Navigation und KEIN zweites <main> (die Seite bringt ihr eigenes <main> mit).
// Spec: docs/specs/modules/oeffentliche_doku_3319.md (AC-4, AC-6, AC-11)
//
// Wirkort ist der {#if}-Baum in `+layout.svelte` (`isLogin`), nicht die Seitenliste.
// Deshalb wird das ECHTE Layout je Pfad serverseitig gerendert (Muster aus
// app_footer_je_route.test.ts, `$app/state` per layout-ssr-hooks.mjs). Entfernt man
// `FUNKTIONEN_PFADE.has(page.url.pathname) ||` aus dem Layout, wird dieser Test rot.
// Gegenkontrolle: nicht-oeffentliche Nachbarpfade bekommen weiterhin das App-Geruest.
// Im Browser: frontend/e2e/funktionen-oeffentlich.staging.spec.ts („F001: …“).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/routes/__tests__/layout_funktionen_oeffentlich.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> routes -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../..');
const base = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, base);
register(pathToFileURL(path.join(FRONTEND, 'src/lib/components/trip-new/__tests__/ssrRunesHook.mjs')).href, base);
register(pathToFileURL(path.join(HERE, 'layout-ssr-hooks.mjs')).href, base);

const { render } = await import('svelte/server');
const Layout = (await import(pathToFileURL(path.join(FRONTEND, 'src/routes/+layout.svelte')).href)).default;
const { FUNKTIONEN_PFADE } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/funktionen_seiten.ts')).href);

const MARKER = '<div data-testid="seiteninhalt">INHALT</div>';

/** Layout fuer einen Pfad rendern; Seiteninhalt = Marker. `userId` undefined = ausgeloggt. */
function layoutHtml(pathname: string, userId?: string): string {
	(globalThis as Record<string, unknown>).__gzLayoutTestPath = pathname;
	const { body } = render(Layout, {
		props: {
			children: (renderer: { push: (s: string) => void }) => renderer.push(MARKER),
			data: userId ? { userId, displayName: 'Anna' } : {}
		}
	});
	return body.replace(/<!--[\s\S]*?-->/g, '');
}

function pruefeOeffentlich(html: string, wo: string): void {
	assert.ok(html.includes('INHALT'), `${wo}: Seiteninhalt fehlt`);
	assert.ok(!html.includes('desktop-sidebar'), `${wo}: App-Seitenleiste gerendert`);
	assert.ok(!html.includes('<main'), `${wo}: Layout rendert ein eigenes <main> (doppeltes <main> mit der Seite)`);
	assert.ok(!/bottom-?nav/i.test(html), `${wo}: untere App-Navigation gerendert`);
	assert.ok(html.includes('<footer'), `${wo}: Footer fehlt im oeffentlichen Zweig`);
}

const PFADE = [...(FUNKTIONEN_PFADE as ReadonlySet<string>)];

describe('F001: oeffentliche Funktionsseiten ohne App-Geruest', () => {
	test('Messaufbau: Uebersicht + neun Unterseiten', () => {
		assert.equal(PFADE.length, 10);
		assert.ok(PFADE.includes('/funktionen'));
	});
	for (const pfad of PFADE) {
		test(`${pfad} ausgeloggt: kein App-Geruest, kein Layout-<main>`, () => {
			pruefeOeffentlich(layoutHtml(pfad), `${pfad} (ausgeloggt)`);
		});
		test(`${pfad} angemeldet: ebenfalls oeffentlicher Zweig (Seite bringt eigenes <main>)`, () => {
			pruefeOeffentlich(layoutHtml(pfad, 'user-a'), `${pfad} (angemeldet)`);
		});
	}
});

describe('F001 Gegenkontrolle: Nachbarpfade bekommen das App-Geruest', () => {
	for (const pfad of ['/funktionenx', '/funktionen/unbekannt', '/trips']) {
		test(`${pfad} angemeldet: Seitenleiste und <main>`, () => {
			const html = layoutHtml(pfad, 'user-a');
			assert.ok(html.includes('desktop-sidebar'), `${pfad}: Seitenleiste fehlt — Messaufbau erkennt das App-Geruest nicht`);
			assert.ok(html.includes('<main'), `${pfad}: <main> fehlt`);
		});
	}
});
