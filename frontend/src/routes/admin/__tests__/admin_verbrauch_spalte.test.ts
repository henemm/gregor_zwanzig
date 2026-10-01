// Issue #2475 (S4 von #2150) — AC-9: Admin-Seite zeigt je Nutzerzeile den
// Open-Meteo-Verbrauch heute (Spalte "Verbrauch", Feld open_meteo_calls_today).
// Spec: docs/specs/modules/forecast_budget_verbrauch_je_nutzer.md
//
// SSR-Render der echten Seite, nur Eingabedaten gesetzt (Netzgrenze liegt im Load).
// Vertrag fuer die Umsetzung: Zelle mit data-testid="admin-user-verbrauch" je Zeile.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/routes/admin/__tests__/admin_verbrauch_spalte.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../..');
const base = pathToFileURL(FRONTEND + '/').href;

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, base);
register(
	pathToFileURL(path.join(FRONTEND, 'src/lib/components/trip-new/__tests__/ssrRunesHook.mjs')).href,
	base
);
register(pathToFileURL(path.join(HERE, 'server-load-resolve.hooks.mjs')).href, base);

const { render } = await import('svelte/server');
const Seite = (await import(pathToFileURL(path.join(HERE, '..', '+page.svelte')).href)).default;

const user = (over: Record<string, unknown>) => ({
	id: 'u',
	email: 'u@example.org',
	display_name: 'U',
	tier: 'free',
	requested_tier: '',
	requested_at: '',
	email_verified_at: '',
	created_at: '2026-08-01T10:00:00Z',
	disabled: false,
	is_test_user: false,
	last_trip_report_run: null,
	open_meteo_calls_today: 0,
	...over
});

const strip = (html: string) => html.replace(/<!--[\s\S]*?-->/g, '');

function zeile(html: string, id: string): string {
	const teile = html.split('data-testid="admin-user-row"').slice(1);
	const hit = teile.find((t) => t.includes(`data-user-id="${id}"`));
	assert.ok(hit, `Zeile ${id} nicht gerendert`);
	// nur bis zur naechsten Zeile, damit die Nachbarzahl nicht mitgelesen wird
	return hit!.split('data-testid="admin-user-row"')[0];
}

/** Text der Verbrauchs-Zelle einer Zeile. */
function verbrauch(z: string): string | null {
	const m = /data-testid="admin-user-verbrauch"[^>]*>([\s\S]*?)<\//.exec(z);
	return m ? m[1].replace(/<[^>]*>/g, '').trim() : null;
}

describe('Admin-Seite (SSR): Spalte Verbrauch (AC-9)', () => {
	const html = strip(
		render(Seite, {
			props: {
				data: {
					users: [
						user({ id: 'a', display_name: 'Anna', open_meteo_calls_today: 120 }),
						user({ id: 'b', display_name: 'Bernd', open_meteo_calls_today: 7 }),
						user({ id: 'n', display_name: 'Null', open_meteo_calls_today: 0 })
					],
					selfId: 'x'
				}
			}
		}).body
	);

	test('Zeile des ersten Nutzers zeigt 120, die des zweiten 7 (keine Vermischung)', () => {
		assert.equal(verbrauch(zeile(html, 'a')), '120');
		assert.equal(verbrauch(zeile(html, 'b')), '7');
	});

	test('Verbrauch 0 wird als 0 gezeigt, nicht leer', () => {
		assert.equal(verbrauch(zeile(html, 'n')), '0');
	});

	test('Spaltenbeschriftung "Verbrauch" ist sichtbar', () => {
		assert.ok(html.includes('Verbrauch'), 'Beschriftung "Verbrauch" fehlt');
	});
});
