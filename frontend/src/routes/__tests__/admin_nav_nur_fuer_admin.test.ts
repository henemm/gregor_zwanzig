// Issue #2155 S4 — Admin-Eintrag in der Navigation nur fuer Admins (AC-1).
// Schliesst Adversary-Finding F001: isAdmin fest `true` an EINER der vier Stellen
// (layout.server, +layout.svelte, Sidebar, KontoSheet) muss einen Test rot machen.
//
// Gemessen wird ECHT: `load()` aus +layout.server.ts (nur die Netzgrenze `fetch`
// ist ersetzt), das echte Layout sowie Sidebar und KontoSheet serverseitig
// gerendert. Zwei Nutzer (Admin / Nutzer) + fehlendes Profil.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/routes/__tests__/admin_nav_nur_fuer_admin.test.ts

import { test, describe, before, after } from 'node:test';
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
register(pathToFileURL(path.join(HERE, '../admin/__tests__/server-load-resolve.hooks.mjs')).href, base);

const { render } = await import('svelte/server');
const Layout = (await import(pathToFileURL(path.join(HERE, '..', '+layout.svelte')).href)).default;
const Sidebar = (
	await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/ui/sidebar/Sidebar.svelte')).href)
).default;
const KontoSheet = (
	await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/ui/sidebar/KontoSheet.svelte')).href)
).default;
const { load } = (await import(pathToFileURL(path.join(HERE, '..', '+layout.server.ts')).href)) as any;

const strip = (html: string) => html.replace(/<!--[\s\S]*?-->/g, '');
const hatAdminLink = (html: string) => /href="\/admin"/.test(html);

// ─── Layout-Load (layout.server.ts): Rolle -> isAdmin ────────────────────────
const PROFIL_JE_SITZUNG: Record<string, any> = {
	'sess-admin': { id: 'admin-1', role: 'admin', display_name: 'Ada' },
	'sess-user': { id: 'user-1', role: 'user', display_name: 'Uwe' },
	'sess-ohne-rolle': { id: 'user-2', display_name: 'Ohne' }
};

async function fetchDouble(_input: any, init?: any) {
	const sitzung = String(init?.headers?.Cookie ?? '').replace('gz_session=', '');
	const profil = PROFIL_JE_SITZUNG[sitzung];
	if (!profil) return { ok: false, status: 401, json: async () => ({}) };
	return { ok: true, status: 200, json: async () => profil };
}
let originalFetch: typeof globalThis.fetch;
before(() => {
	originalFetch = globalThis.fetch;
	globalThis.fetch = fetchDouble as unknown as typeof globalThis.fetch;
});
after(() => {
	globalThis.fetch = originalFetch;
});

const loadFor = (sitzung: string, userId: string | null = 'x') =>
	load({ locals: { userId }, cookies: { get: () => sitzung } });

describe('layout.server load: isAdmin folgt der Rolle (fail-closed)', () => {
	test('Admin-Profil => isAdmin true', async () => {
		assert.equal((await loadFor('sess-admin')).isAdmin, true);
	});
	test('Nutzer-Profil => isAdmin false', async () => {
		assert.equal((await loadFor('sess-user')).isAdmin, false);
	});
	test('Profil ohne role-Feld => isAdmin false', async () => {
		assert.equal((await loadFor('sess-ohne-rolle')).isAdmin, false);
	});
	test('Profil-Abruf scheitert (401) => isAdmin false', async () => {
		assert.equal((await loadFor('unbekannt')).isAdmin, false);
	});
	test('nicht angemeldet => isAdmin false, kein Abruf noetig', async () => {
		assert.equal((await loadFor('sess-admin', null)).isAdmin, false);
	});
});

// ─── Layout: Weitergabe ans Sidebar ──────────────────────────────────────────
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

describe('+layout.svelte reicht isAdmin an Sidebar/KontoSheet durch', () => {
	test('Nicht-Admin: kein Admin-Link irgendwo im Layout', () => {
		const html = layoutHtml({ userId: 'user-1', displayName: 'Uwe', isAdmin: false });
		assert.ok(html.includes('INHALT'), 'Messaufbau kaputt');
		assert.ok(!hatAdminLink(html), 'Nicht-Admin sieht einen Admin-Link');
	});
	test('isAdmin fehlt in data => kein Admin-Link', () => {
		const html = layoutHtml({ userId: 'user-1', displayName: 'Uwe' });
		assert.ok(!hatAdminLink(html), 'Ohne isAdmin darf kein Admin-Link erscheinen');
	});
	test('Admin: Admin-Link in der Sidebar vorhanden', () => {
		const html = layoutHtml({ userId: 'admin-1', displayName: 'Ada', isAdmin: true });
		assert.ok(html.includes('data-testid="nav-admin"'), 'Admin-Eintrag fehlt in der Sidebar');
	});
});

// ─── Sidebar direkt ──────────────────────────────────────────────────────────
function sidebarHtml(isAdmin: boolean | undefined): string {
	const props: Record<string, unknown> = {
		userId: 'u',
		displayName: 'U',
		currentPath: '/trips',
		darkMode: false,
		ontoggleDark: () => {}
	};
	if (isAdmin !== undefined) props.isAdmin = isAdmin;
	return strip(render(Sidebar, { props }).body);
}

describe('Sidebar: Admin-Eintrag nur bei isAdmin', () => {
	test('Nicht-Admin: kein nav-admin, keine Admin-Beschriftung', () => {
		const html = sidebarHtml(false);
		assert.ok(html.includes('data-testid="nav-trips"'), 'Messaufbau kaputt: Basis-Navigation fehlt');
		assert.ok(!html.includes('nav-admin') && !hatAdminLink(html));
	});
	test('Default (Prop fehlt): kein Admin-Eintrag', () => {
		assert.ok(!sidebarHtml(undefined).includes('nav-admin'));
	});
	test('Admin: genau ein Eintrag nav-admin -> /admin, Basis-Eintraege bleiben', () => {
		const html = sidebarHtml(true);
		assert.equal(html.match(/data-testid="nav-admin"/g)?.length, 1);
		assert.ok(hatAdminLink(html));
		for (const id of ['home', 'trips', 'compare', 'archive']) {
			assert.ok(html.includes(`data-testid="nav-${id}"`), `Basis-Eintrag ${id} fehlt`);
		}
	});
});

// ─── KontoSheet direkt (mobil) ───────────────────────────────────────────────
function kontoHtml(isAdmin: boolean | undefined): string {
	const props: Record<string, unknown> = {
		open: true,
		onClose: () => {},
		initials: 'U',
		displayName: 'U',
		userId: 'u',
		darkMode: false,
		ontoggleDark: () => {}
	};
	if (isAdmin !== undefined) props.isAdmin = isAdmin;
	return strip(render(KontoSheet, { props }).body);
}

describe('KontoSheet: Admin-Zeile nur bei isAdmin', () => {
	test('Nicht-Admin: keine Zeile konto-sheet-admin', () => {
		const html = kontoHtml(false);
		assert.ok(html.includes('data-testid="konto-sheet-export"'), 'Messaufbau kaputt: Sheet leer');
		assert.ok(!html.includes('konto-sheet-admin') && !hatAdminLink(html));
	});
	test('Default (Prop fehlt): keine Admin-Zeile', () => {
		assert.ok(!kontoHtml(undefined).includes('konto-sheet-admin'));
	});
	test('Admin: Zeile konto-sheet-admin -> /admin vorhanden', () => {
		const html = kontoHtml(true);
		assert.equal(html.match(/data-testid="konto-sheet-admin"/g)?.length, 1);
		assert.ok(hatAdminLink(html));
	});
});
