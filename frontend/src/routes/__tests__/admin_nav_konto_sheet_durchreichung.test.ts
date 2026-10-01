// Issue #2155 S4 — AC-1: Admin-Eintrag im mobilen Konto-Sheet nur fuer Admins,
// gemessen an der Weitergabe +layout.svelte -> KontoSheet (Adversary-Finding F002).
//
// Der Schwester-Test admin_nav_nur_fuer_admin.test.ts rendert KontoSheet nur
// isoliert; die Weitergabe im Layout (`isAdmin={data.isAdmin === true}` am
// KontoSheet) blieb unbewacht, weil das Sheet im SSR-Render zu ist. Hier
// oeffnet `konto-sheet-offen.hooks.mjs` ausschliesslich das generische
// Bottom-Sheet; Layout und KontoSheet laufen echt. Eigene Datei, damit der
// Hook die Bedingungen der uebrigen Layout-Tests nicht veraendert.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/routes/__tests__/admin_nav_konto_sheet_durchreichung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../..');
const base = pathToFileURL(FRONTEND + '/').href;

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, base);
register(
	pathToFileURL(path.join(FRONTEND, 'src/lib/components/trip-new/__tests__/ssrRunesHook.mjs')).href,
	base
);
register(pathToFileURL(path.join(HERE, 'layout-ssr-hooks.mjs')).href, base);
// Zuletzt registriert => laeuft zuerst: oeffnet nur mobile/Sheet.svelte.
register(pathToFileURL(path.join(HERE, 'konto-sheet-offen.hooks.mjs')).href, base);

const { render } = await import('svelte/server');
const Layout = (await import(pathToFileURL(path.join(HERE, '..', '+layout.svelte')).href)).default;

const strip = (html: string) => html.replace(/<!--[\s\S]*?-->/g, '');
const anzahl = (html: string, testid: string) =>
	html.match(new RegExp(`data-testid="${testid}"`, 'g'))?.length ?? 0;

function layoutHtml(data: Record<string, unknown>): string {
	(globalThis as Record<string, unknown>).__gzLayoutTestPath = '/trips';
	const { body } = render(Layout, {
		props: {
			children: (r: { push: (s: string) => void }) => r.push('<div>INHALT</div>'),
			data
		}
	});
	return strip(body);
}

describe('+layout.svelte reicht isAdmin an das (geoeffnete) Konto-Sheet durch', () => {
	test('Admin: genau ein Admin-Eintrag im Konto-Sheet', () => {
		const html = layoutHtml({ userId: 'admin-1', displayName: 'Ada', isAdmin: true });
		assert.equal(anzahl(html, 'konto-sheet-export'), 1, 'Messaufbau kaputt: Konto-Sheet nicht gerendert');
		assert.equal(anzahl(html, 'konto-sheet-admin'), 1, 'Admin-Eintrag fehlt im Konto-Sheet');
	});

	test('Nicht-Admin: kein Admin-Eintrag im Konto-Sheet', () => {
		const html = layoutHtml({ userId: 'user-1', displayName: 'Uwe', isAdmin: false });
		assert.equal(anzahl(html, 'konto-sheet-export'), 1, 'Messaufbau kaputt: Konto-Sheet nicht gerendert');
		assert.equal(anzahl(html, 'konto-sheet-admin'), 0, 'Nicht-Admin sieht Admin-Eintrag im Konto-Sheet');
	});

	test('isAdmin fehlt in data: kein Admin-Eintrag im Konto-Sheet', () => {
		const html = layoutHtml({ userId: 'user-1', displayName: 'Uwe' });
		assert.equal(anzahl(html, 'konto-sheet-export'), 1, 'Messaufbau kaputt: Konto-Sheet nicht gerendert');
		assert.equal(anzahl(html, 'konto-sheet-admin'), 0, 'ohne isAdmin erscheint ein Admin-Eintrag');
	});

	test('isAdmin als truthy Nicht-Boolean ("true") => kein Admin-Eintrag (strikt === true)', () => {
		const html = layoutHtml({ userId: 'user-1', displayName: 'Uwe', isAdmin: 'true' });
		assert.equal(anzahl(html, 'konto-sheet-admin'), 0, 'truthy Nicht-Boolean oeffnet den Admin-Eintrag');
	});
});
