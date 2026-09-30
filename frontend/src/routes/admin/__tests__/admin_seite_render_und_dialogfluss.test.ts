// Issue #2155 S4 — Render der Admin-Seite, Dialog-Fluss-Helfer, Fehlerpfad, Load-Randfaelle.
// Schliesst Adversary-Findings F002 (Selbstschutz, Dialog, Fehleranzeige) und F003
// (fail-closed-Zweige im Load).
//
// Ehrliche Grenze: der echte Klick-Fluss im Browser (Dialog oeffnet/schliesst,
// Select springt zurueck) ist nur in der Staging-Playwright-Spec
// frontend/e2e/admin-nutzerverwaltung.staging.spec.ts messbar. Hier bewacht:
// das SSR-Render der Seite (Selbstschutz, Antrag-Hervorhebung, Sperr-Badge,
// Entsperren statt Sperren) und die reinen Zustands-/Sende-Helfer aus lib/admin.ts,
// die die Seite tatsaechlich benutzt. Nur `fetch` ist ersetzt (Netzgrenze).
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/routes/admin/__tests__/admin_seite_render_und_dialogfluss.test.ts

import { test, describe, before, after } from 'node:test';
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
const { load } = (await import(pathToFileURL(path.join(HERE, '..', '+page.server.ts')).href)) as any;
const A = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/admin.ts')).href);

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
	...over
});

const strip = (html: string) => html.replace(/<!--[\s\S]*?-->/g, '');

/** Der <div data-testid="admin-user-row" data-user-id="ID"> bis zur naechsten Zeile. */
function zeile(html: string, id: string): string {
	const teile = html.split('data-testid="admin-user-row"').slice(1);
	const hit = teile.find((t) => t.includes(`data-user-id="${id}"`));
	assert.ok(hit, `Zeile ${id} nicht gerendert`);
	return hit!;
}

function seite(users: unknown[], selfId: string): string {
	return strip(render(Seite, { props: { data: { users, selfId } } }).body);
}

/** Start-Tag des Buttons mit testid in einer Zeile. */
function buttonTag(z: string, testid: string): string | null {
	const m = new RegExp(`<button[^>]*data-testid="${testid}"[^>]*>`).exec(z);
	return m ? m[0] : null;
}

// ─── Render ──────────────────────────────────────────────────────────────────
describe('Admin-Seite (SSR): Selbstschutz, Sperrstatus, offener Antrag', () => {
	const users = [
		user({ id: 'ich', display_name: 'Ich' }),
		user({ id: 'andere', display_name: 'Andere' }),
		user({ id: 'gesperrt', display_name: 'Gesperrt', disabled: true }),
		user({ id: 'antrag', display_name: 'Antrag', requested_tier: 'premium', requested_at: '2026-09-29T10:00:00Z' })
	];
	const html = seite(users, 'ich');

	test('eigene Zeile: Sperren-Button ist deaktiviert', () => {
		const tag = buttonTag(zeile(html, 'ich'), 'admin-disable-btn');
		assert.ok(tag, 'eigene Zeile hat gar keinen Sperren-Button (Messaufbau)');
		assert.ok(/\bdisabled\b/.test(tag!), `Sperren-Button der eigenen Zeile nicht deaktiviert: ${tag}`);
	});

	test('fremde Zeile: Sperren-Button ist aktiv', () => {
		const tag = buttonTag(zeile(html, 'andere'), 'admin-disable-btn');
		assert.ok(tag, 'fremde Zeile hat keinen Sperren-Button');
		assert.ok(!/\bdisabled\b/.test(tag!), `Sperren-Button der fremden Zeile deaktiviert: ${tag}`);
	});

	test('selfId leer: niemand ist selbst-gesperrt (kein Zufallstreffer auf leere ID)', () => {
		const tag = buttonTag(zeile(seite(users, ''), 'ich'), 'admin-disable-btn');
		assert.ok(tag && !/\bdisabled\b/.test(tag!), 'Sperren-Button faelschlich deaktiviert');
	});

	test('gesperrter Nutzer: Badge und Entsperren statt Sperren', () => {
		const z = zeile(html, 'gesperrt');
		assert.ok(z.includes('data-testid="admin-disabled-badge"'));
		assert.ok(buttonTag(z, 'admin-enable-btn'));
		assert.equal(buttonTag(z, 'admin-disable-btn'), null);
		assert.ok(!zeile(html, 'andere').includes('admin-disabled-badge'));
	});

	test('offener Antrag ist nur an der Antrag-Zeile hervorgehoben, mit Ziel-Tier', () => {
		const z = zeile(html, 'antrag');
		assert.ok(z.includes('data-testid="admin-open-request"'), 'Hervorhebung fehlt');
		assert.ok(z.includes('Offener Antrag: Premium'), 'Ziel-Tier fehlt');
		assert.ok(!zeile(html, 'andere').includes('admin-open-request'), 'Hervorhebung ohne Antrag');
	});

	test('keine Fehlerzeile im Ausgangszustand', () => {
		assert.ok(!html.includes('admin-row-error'));
	});
});

// ─── Load: selfId und fail-closed-Zweige ─────────────────────────────────────
type Antwort = { ok: boolean; status: number; body?: unknown };
let profil: Antwort | 'wirft';
let liste: Antwort | 'wirft';

async function fetchDouble(input: any) {
	const url = String(input);
	const a = url.includes('/api/auth/profile') ? profil : liste;
	if (a === 'wirft') throw new Error('Netz weg');
	return { ok: a.ok, status: a.status, json: async () => a.body };
}
let originalFetch: typeof globalThis.fetch;
before(() => {
	originalFetch = globalThis.fetch;
	globalThis.fetch = fetchDouble as unknown as typeof globalThis.fetch;
});
after(() => {
	globalThis.fetch = originalFetch;
});

const event = { cookies: { get: () => 'sess' } };
const ADMIN: Antwort = { ok: true, status: 200, body: { id: 'admin-7', role: 'admin' } };
const LISTE_OK: Antwort = { ok: true, status: 200, body: { users: [user({ id: 'a' })] } };

async function statusVon(): Promise<number | 'ok'> {
	try {
		await load(event);
		return 'ok';
	} catch (e: any) {
		return e.status;
	}
}

describe('+page.server load: selfId und fail-closed', () => {
	test('selfId kommt aus profile.id', async () => {
		profil = ADMIN;
		liste = LISTE_OK;
		assert.equal((await load(event)).selfId, 'admin-7');
	});
	test('Profil ohne id => selfId leer (nie undefined/null)', async () => {
		profil = { ok: true, status: 200, body: { role: 'admin' } };
		liste = LISTE_OK;
		assert.equal((await load(event)).selfId, '');
	});
	test('Admin-Profil, Go antwortet auf der Liste 403 => 403', async () => {
		profil = ADMIN;
		liste = { ok: false, status: 403, body: {} };
		assert.equal(await statusVon(), 403);
	});
	test('Admin-Profil, Go antwortet auf der Liste 401 => 401', async () => {
		profil = ADMIN;
		liste = { ok: false, status: 401, body: {} };
		assert.equal(await statusVon(), 401);
	});
	test('Liste 500 => 502, kein Durchlassen', async () => {
		profil = ADMIN;
		liste = { ok: false, status: 500, body: {} };
		assert.equal(await statusVon(), 502);
	});
	test('Profil-Abruf scheitert (Antwort nicht ok) => 401, Liste wird nicht gezeigt', async () => {
		profil = { ok: false, status: 500, body: {} };
		liste = LISTE_OK;
		assert.equal(await statusVon(), 401);
	});
	test('Profil-Abruf wirft (Netz) => 401', async () => {
		profil = 'wirft';
		liste = LISTE_OK;
		assert.equal(await statusVon(), 401);
	});
	test('Profil liefert leere Antwort (null) => 401', async () => {
		profil = { ok: true, status: 200, body: null };
		liste = LISTE_OK;
		assert.equal(await statusVon(), 401);
	});
});

// ─── Dialog-Fluss als reine Zustandsfunktionen ───────────────────────────────
describe('Sperr-Dialog: erst die Bestaetigung sendet', () => {
	test('Sperren anklicken oeffnet nur die Auswahl, erzeugt keine Sende-Aktion', () => {
		const confirmId = A.askDisable('u-1');
		assert.equal(confirmId, 'u-1');
		// Die einzige Sende-Quelle fuer Sperren ist confirmDisableAction: ohne Auswahl nichts.
		assert.equal(A.confirmDisableAction(null), null);
	});
	test('Bestaetigen sendet genau {"disabled":true} fuer die gewaehlte ID', () => {
		assert.deepEqual(A.confirmDisableAction('u-1'), {
			id: 'u-1',
			path: 'disabled',
			body: { disabled: true }
		});
	});
	test('Abbrechen verwirft die Auswahl; danach gibt es nichts zu bestaetigen', () => {
		const nachAbbruch = A.cancelDisable();
		assert.equal(nachAbbruch, null);
		assert.equal(A.confirmDisableAction(nachAbbruch), null);
	});
	test('Entsperren sendet {"disabled":false} direkt, ohne Dialog', () => {
		assert.deepEqual(A.enableAction('u-2'), { id: 'u-2', path: 'disabled', body: { disabled: false } });
	});
	test('Sperren ist fuer das eigene Konto und bei laufender Aktion blockiert', () => {
		assert.equal(A.disableBlocked('ich', 'ich', false), true);
		assert.equal(A.disableBlocked('andere', 'ich', true), true);
		assert.equal(A.disableBlocked('andere', 'ich', false), false);
		assert.equal(A.disableBlocked('andere', '', false), false);
	});
});

// ─── Senden und Fehlerpfad ───────────────────────────────────────────────────
describe('sendAdminUpdate: Payload, Pfad, Fehler => Klartext ohne Zeilenaenderung', () => {
	type Aufruf = { url: string; init: any };
	function mitFetch(antwort: Antwort | 'wirft') {
		const aufrufe: Aufruf[] = [];
		const f = (async (url: any, init: any) => {
			aufrufe.push({ url: String(url), init });
			if (antwort === 'wirft') throw new Error('Netz weg');
			return { ok: antwort.ok, status: antwort.status, json: async () => antwort.body };
		}) as unknown as typeof fetch;
		return { f, aufrufe };
	}

	test('Erfolg: PUT auf /api/admin/users/<id>/disabled mit JSON-Body, liefert die Zeile', async () => {
		const neu = user({ id: 'a b', disabled: true });
		const { f, aufrufe } = mitFetch({ ok: true, status: 200, body: neu });
		const r = await A.sendAdminUpdate(f, 'a b', 'disabled', { disabled: true });
		assert.deepEqual(r, { ok: true, user: neu });
		assert.equal(aufrufe.length, 1);
		assert.equal(aufrufe[0].url, '/api/admin/users/a%20b/disabled');
		assert.equal(aufrufe[0].init.method, 'PUT');
		assert.equal(aufrufe[0].init.body, '{"disabled":true}');
	});

	test('Tier-Pfad /tier mit {"tier":...}', async () => {
		const { f, aufrufe } = mitFetch({ ok: true, status: 200, body: user({ tier: 'premium' }) });
		await A.sendAdminUpdate(f, 'u', 'tier', { tier: 'premium' });
		assert.equal(aufrufe[0].url, '/api/admin/users/u/tier');
		assert.equal(aufrufe[0].init.body, '{"tier":"premium"}');
	});

	test('Fehler 409 cannot_disable_self => Klartext, kein Nutzer, kein Rohcode', async () => {
		const { f } = mitFetch({ ok: false, status: 409, body: { error: 'cannot_disable_self' } });
		const r = await A.sendAdminUpdate(f, 'u', 'disabled', { disabled: true });
		assert.equal(r.ok, false);
		assert.equal(r.text, 'Das eigene Konto kann nicht gesperrt werden');
		assert.equal(r.user, undefined, 'Fehlerfall darf keine Zeile zum Ersetzen liefern');
	});

	test('Netzfehler => Klartext, kein Nutzer', async () => {
		const { f } = mitFetch('wirft');
		const r = await A.sendAdminUpdate(f, 'u', 'tier', { tier: 'free' });
		assert.equal(r.ok, false);
		assert.ok(r.text.length > 0 && !/Netz weg|cannot_/.test(r.text));
		assert.equal(r.user, undefined);
	});

	test('Fehler lassen die Liste unveraendert (Seite ersetzt nur bei ok)', async () => {
		const liste = [user({ id: 'a' }), user({ id: 'b' })];
		const { f } = mitFetch({ ok: false, status: 404, body: {} });
		const r = await A.sendAdminUpdate(f, 'a', 'tier', { tier: 'premium' });
		const nachher = r.ok ? A.replaceUserRow(liste, r.user) : liste;
		assert.deepEqual(nachher, liste);
		assert.equal(r.text, 'Nutzer nicht gefunden');
	});

	test('applySendResult: Fehler => Liste identisch, Klartext NUR an dieser Zeile', () => {
		const liste = [user({ id: 'a' }), user({ id: 'b' })];
		const r = A.applySendResult(liste, { b: 'alt' }, 'a', { ok: false, text: 'Nutzer nicht gefunden' });
		assert.deepEqual(r.users, liste);
		assert.equal(r.errors.a, 'Nutzer nicht gefunden');
		assert.equal(r.errors.b, 'alt', 'Fehler fremder Zeile darf nicht verschwinden');
		assert.deepEqual(liste.map((u) => u.id), ['a', 'b'], 'Eingabe mutiert');
	});

	test('applySendResult: Erfolg => nur diese Zeile ersetzt, ihr Fehler geloescht', () => {
		const liste = [user({ id: 'a' }), user({ id: 'b' })];
		const neu = user({ id: 'a', disabled: true });
		const r = A.applySendResult(liste, { a: 'alt', b: 'bleibt' }, 'a', { ok: true, user: neu });
		assert.deepEqual(r.users, [neu, liste[1]]);
		assert.equal(r.errors.a, undefined);
		assert.equal(r.errors.b, 'bleibt');
	});

	test('Tier-Select springt nach Fehler auf den alten Wert zurueck, nach Erfolg bleibt die Wahl', () => {
		assert.equal(A.tierSelectValueAfter(false, 'premium', 'free'), 'free');
		assert.equal(A.tierSelectValueAfter(true, 'premium', 'free'), 'premium');
	});
});
