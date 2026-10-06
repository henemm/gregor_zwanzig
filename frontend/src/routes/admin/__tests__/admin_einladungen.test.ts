// Admin-Einladungslinks (Spec admin_einladungslinks_2519), AC-1 + AC-7 + AC-5 UI-Seite.
// SSR-Render der Admin-Seite (echt), Load-Verhalten und die Sende-Helfer aus
// lib/admin.ts; nur fetch ist ersetzt (Netzgrenze). Der Klick-Fluss im Browser
// ist nur in der Staging-Playwright-Spec messbar.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/routes/admin/__tests__/admin_einladungen.test.ts

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

const strip = (html: string) => html.replace(/<!--[\s\S]*?-->/g, '');
const inv = (over: Record<string, unknown>) => ({
	id: 'i1',
	tier: 'standard',
	note: '',
	status: 'open',
	created_at: '2026-10-06T10:00:00Z',
	created_by: 'alice',
	used_by: '',
	used_at: null,
	revoked_at: null,
	...over
});
function seite(invites: unknown[]): string {
	return strip(render(Seite, { props: { data: { users: [], selfId: 'alice', invites } } }).body);
}
function zeile(html: string, id: string): string {
	const hit = html.split('data-testid="admin-invite-row"').slice(1).find((t) => t.includes(`data-invite-id="${id}"`));
	assert.ok(hit, `Einladungszeile ${id} nicht gerendert`);
	return hit!;
}

describe('Admin-Seite (SSR): Einladungen', () => {
	const html = seite([
		inv({ id: 'offen', note: 'Tante Erna', tier: 'standard' }),
		inv({ id: 'benutzt', note: 'Onkel Karl', tier: 'premium', status: 'used', used_by: 'karl', used_at: '2026-10-07T08:00:00Z' }),
		inv({ id: 'weg', note: 'Cousin', tier: 'free', status: 'revoked', revoked_at: '2026-10-08T09:00:00Z' })
	]);

	test('Card "Einladungen" mit Formular (Level Standard vorgewaehlt, Notiz, Erstellen-Knopf)', () => {
		assert.ok(html.includes('data-testid="admin-invite-form"'));
		assert.match(html, /<select[^>]*data-testid="admin-invite-tier"[^>]*>[\s\S]*?<\/select>/);
		const sel = /<select[^>]*data-testid="admin-invite-tier"[^>]*>([\s\S]*?)<\/select>/.exec(html)![1];
		const gewaehlt = [...sel.matchAll(/<option([^>]*)>/g)].filter((m) => /\bselected\b/.test(m[1]));
		assert.equal(gewaehlt.length, 1);
		assert.ok(/value="standard"/.test(gewaehlt[0][1]), 'Default muss Standard sein');
		assert.ok(html.includes('data-testid="admin-invite-note"'));
		assert.ok(html.includes('Einladung erstellen'));
	});

	test('offene Zeile: Notiz, Level, Status Offen, Widerrufen-Knopf', () => {
		const z = zeile(html, 'offen');
		assert.ok(z.includes('Tante Erna') && z.includes('Standard'));
		assert.ok(z.includes('Offen'));
		assert.ok(z.includes('data-testid="admin-invite-revoke"'));
	});

	test('benutzte Zeile: "Benutzt von karl am <Datum>", kein Widerrufen', () => {
		const z = zeile(html, 'benutzt');
		assert.match(z, /Benutzt von karl am 7\.10\.2026/);
		assert.ok(z.includes('Premium'));
		assert.ok(!z.includes('admin-invite-revoke'));
	});

	test('widerrufene Zeile: "Widerrufen am <Datum>", kein Widerrufen-Knopf', () => {
		const z = zeile(html, 'weg');
		assert.match(z, /Widerrufen am 8\.10\.2026/);
		assert.ok(!z.includes('admin-invite-revoke'));
	});

	test('ohne Einladungen: leere Liste, Formular bleibt', () => {
		const leer = seite([]);
		assert.ok(leer.includes('data-testid="admin-invite-form"'));
		assert.ok(!leer.includes('admin-invite-row'));
	});
});

describe('lib/admin: Einladungs-Helfer', () => {
	function mitFetch(status: number, body: unknown) {
		const aufrufe: { url: string; init: any }[] = [];
		const f = (async (url: any, init: any) => {
			aufrufe.push({ url: String(url), init });
			return { ok: status < 300, status, json: async () => body };
		}) as unknown as typeof fetch;
		return { f, aufrufe };
	}

	test('createInvite: POST mit Level+Notiz, liefert Einladung und Link', async () => {
		const { f, aufrufe } = mitFetch(201, { invite: inv({ id: 'neu' }), link: 'https://x.de/register?invite=T0K' });
		const r = await A.createInvite(f, 'premium', 'Tante Erna');
		assert.equal(r.ok, true);
		assert.equal(r.link, 'https://x.de/register?invite=T0K');
		assert.equal(r.invite.id, 'neu');
		assert.equal(aufrufe[0].url, '/api/admin/invites');
		assert.equal(aufrufe[0].init.method, 'POST');
		assert.deepEqual(JSON.parse(aufrufe[0].init.body), { tier: 'premium', note: 'Tante Erna' });
	});

	test('createInvite: 400 => Klartext, kein Link', async () => {
		const { f } = mitFetch(400, { error: 'invalid_tier' });
		const r = await A.createInvite(f, 'gold', '');
		assert.equal(r.ok, false);
		assert.ok(r.text && !/invalid_tier/.test(r.text));
		assert.equal(r.link, undefined);
	});

	test('revokeInvite: POST auf /revoke, Fehler 409 => Klartext', async () => {
		const ok = mitFetch(200, inv({ status: 'revoked' }));
		const r1 = await A.revokeInvite(ok.f, 'a b');
		assert.equal(r1.ok, true);
		assert.equal(ok.aufrufe[0].url, '/api/admin/invites/a%20b/revoke');
		assert.equal(ok.aufrufe[0].init.method, 'POST');
		const bad = mitFetch(409, { error: 'invite_used' });
		const r2 = await A.revokeInvite(bad.f, 'x');
		assert.equal(r2.ok, false);
		assert.ok(r2.text && !/invite_used/.test(r2.text));
	});

	test('inviteStatusText: Offen / Benutzt von / Widerrufen am', () => {
		assert.equal(A.inviteStatusText(inv({})), 'Offen');
		assert.match(A.inviteStatusText(inv({ status: 'used', used_by: 'karl', used_at: '2026-10-07T08:00:00Z' })), /^Benutzt von karl am 7\.10\.2026/);
		assert.match(A.inviteStatusText(inv({ status: 'revoked', revoked_at: '2026-10-08T09:00:00Z' })), /^Widerrufen am 8\.10\.2026/);
	});
});

describe('+page.server load: Einladungen', () => {
	type Antwort = { ok: boolean; status: number; body?: unknown } | 'wirft';
	let invites: Antwort;
	let originalFetch: typeof globalThis.fetch;
	before(() => {
		originalFetch = globalThis.fetch;
		globalThis.fetch = (async (input: any) => {
			const url = String(input);
			let a: Antwort;
			if (url.includes('/api/auth/profile')) a = { ok: true, status: 200, body: { id: 'alice', role: 'admin' } };
			else if (url.includes('/api/admin/invites')) a = invites;
			else a = { ok: true, status: 200, body: { users: [] } };
			if (a === 'wirft') throw new Error('Netz weg');
			return { ok: a.ok, status: a.status, json: async () => a.body };
		}) as unknown as typeof fetch;
	});
	after(() => {
		globalThis.fetch = originalFetch;
	});
	const event = { cookies: { get: () => 'sess' } };

	test('liefert die Einladungen aus /api/admin/invites', async () => {
		invites = { ok: true, status: 200, body: { invites: [inv({ id: 'a' })] } };
		const d = await load(event);
		assert.equal(d.invites.length, 1);
		assert.equal(d.invites[0].id, 'a');
	});

	test('Einladungsliste nicht erreichbar: Nutzerverwaltung bleibt nutzbar, invites leer', async () => {
		invites = { ok: false, status: 500, body: {} };
		const d = await load(event);
		assert.deepEqual(d.invites, []);
		assert.ok(Array.isArray(d.users));
	});
});
