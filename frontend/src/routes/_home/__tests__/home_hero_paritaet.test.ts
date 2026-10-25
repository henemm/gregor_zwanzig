// TDD RED — Issue #2346 S3 (Epic #2345 P6): EIN Hero-Baustein fuer Trip und Ortsvergleich.
// Spec: docs/specs/modules/feat_2346_cockpit_paritaet.md — AC-4, AC-11, AC-12.
//
// Vertrag (hier festgelegt, /50 baut danach):
//   routes/_home/HomeHero.svelte   Props: kind, id, name, href, subtitle?, channels: string[], nextSend?: string|null,
//                                   pills?, details?, actions? (Snippets fuer kind-eigene Inhalte).
//     -> Wurzel traegt data-testid="home-hero-{id}" und data-kind="trip"|"vergleich".
//     -> gemeinsame Felder tragen data-field in dieser Reihenfolge: "pills" | "title" | "subtitle" | "next-send" | "channels".
//     -> Titel ist ein echter <a href=…>; jeder Kanal ist ein Chip data-channel="<Name>"; leere Kanalliste zeigt "—".
//   routes/_home/homeHeroChannels.ts   homeHeroChannels(kind, sub): string[]
//     -> Trip: heroKanaele(report_config) (Slot-Regel); Vergleich: presetChannels(sub) (Flags) — nie aus empfaenger.
//   shared/OutlookLayoutControls.svelte (umbenannt aus CompareOutlookLayoutControls);
//   compare/CompareHourlyLayoutControls.svelte (verschoben, Kopfzeile gz-eigenstaendig:).
//
// Pfadregel #1409: relativ zu DIESER Datei.
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/_home/__tests__/home_hero_paritaet.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { existsSync, readdirSync, readFileSync } from 'node:fs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../..');
const HOME = path.resolve(HERE, '..');
const COMPONENTS = path.join(FRONTEND, 'src/lib/components');

register(pathToFileURL(path.join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const { render } = await import('svelte/server');

async function laden(abs: string): Promise<any> {
	assert.ok(existsSync(abs), `${path.relative(FRONTEND, abs)} fehlt (RED)`);
	return (await import(pathToFileURL(abs).href)).default;
}
async function modul(abs: string): Promise<any> {
	assert.ok(existsSync(abs), `${path.relative(FRONTEND, abs)} fehlt (RED)`);
	return import(pathToFileURL(abs).href);
}
const html = (comp: any, props: Record<string, unknown>) => render(comp, { props }).body.replace(/<!--.*?-->/g, '');
const kanaele = (h: string) => [...h.matchAll(/data-channel="([^"]+)"/g)].map((m) => m[1]);
const feldNamen = (h: string) => [...h.matchAll(/data-field="([^"]+)"/g)].map((m) => m[1]);

const TRIP: any = {
	id: 'trip-1',
	name: 'GR20 Nord',
	stages: [{ id: 's1', name: 'E1', date: '2026-10-17', waypoints: [] }],
	report_config: {
		enabled: true,
		send_email: true,
		send_telegram: false,
		send_sms: false,
		send_premium_sms: false,
		morning_enabled: true,
		morning_time: '07:00'
	},
	empfaenger: ['mail@example.org', 'telegram:12345']
};
// Flags: nur E-Mail (immer) — Telegram/SMS AUS, obwohl empfaenger einen Telegram-Eintrag traegt (#1452).
const PRESET: any = {
	id: 'cmp-1',
	name: 'Ortsvergleich Nord',
	location_ids: ['a', 'b'],
	schedule: 'daily',
	send_telegram: false,
	send_sms: false,
	send_premium_sms: false,
	empfaenger: ['telegram:12345', 'sms:+4915100000']
};

describe('AC-11: ein HomeHero-Baustein, beide kinds mit gleicher Felderfolge', () => {
	test('Trip- und Vergleichs-Hero zeigen dieselben Felder in derselben Reihenfolge', async () => {
		const Hero = await laden(path.join(HOME, 'HomeHero.svelte'));
		const basis = { subtitle: 'Korsika', nextSend: 'Do 07:00 (CEST)' };
		const t = html(Hero, { kind: 'trip', id: TRIP.id, name: TRIP.name, href: '/trips/trip-1?tab=uebersicht', channels: ['Email'], ...basis });
		const c = html(Hero, { kind: 'vergleich', id: PRESET.id, name: PRESET.name, href: '/compare/cmp-1', channels: ['Email'], ...basis });
		const soll = ['pills', 'title', 'subtitle', 'next-send', 'channels'];
		assert.deepEqual(feldNamen(t), soll, 'Trip: Felder/Reihenfolge');
		assert.deepEqual(feldNamen(c), soll, 'Vergleich: Felder/Reihenfolge');
		assert.match(t, /data-kind="trip"/);
		assert.match(c, /data-kind="vergleich"/);
		assert.match(t, /data-testid="home-hero-trip-1"/);
		assert.match(c, /data-testid="home-hero-cmp-1"/);
	});

	test('Titel ist ein echter Link, naechster Versand erscheint wie uebergeben', async () => {
		const Hero = await laden(path.join(HOME, 'HomeHero.svelte'));
		const h = html(Hero, {
			kind: 'vergleich', id: 'cmp-1', name: 'Ortsvergleich Nord', href: '/compare/cmp-1',
			channels: ['Email'], nextSend: 'Fr 07:00 (CEST)'
		});
		assert.match(h, /<a[^>]*href="\/compare\/cmp-1"[^>]*>[^<]*Ortsvergleich Nord/);
		assert.ok(h.includes('Fr 07:00 (CEST)'), 'nextSend sichtbar');
	});

	test('leere Kanalliste zeigt "—", fehlender nextSend ebenfalls', async () => {
		const Hero = await laden(path.join(HOME, 'HomeHero.svelte'));
		const h = html(Hero, { kind: 'trip', id: 't', name: 'X', href: '/trips/t', channels: [] });
		assert.deepEqual(kanaele(h), []);
		assert.ok((h.match(/—/g) ?? []).length >= 2, 'Kanaele und naechster Versand zeigen "—"');
	});
});

describe('AC-12: Kanaele aus Flags, nie aus empfaenger (#1452)', () => {
	test('Vergleich mit Telegram in empfaenger, aber Flag aus: Hero zeigt nur Email', async () => {
		const { homeHeroChannels } = await modul(path.join(HOME, 'homeHeroChannels.ts'));
		const kan = homeHeroChannels('vergleich', PRESET);
		assert.deepEqual(kan, ['Email']);
		const Hero = await laden(path.join(HOME, 'HomeHero.svelte'));
		const h = html(Hero, { kind: 'vergleich', id: PRESET.id, name: PRESET.name, href: '/compare/cmp-1', channels: kan });
		assert.deepEqual(kanaele(h), ['Email']);
		assert.ok(!/telegram|sms/i.test(h), 'kein Kanal aus empfaenger im Hero');
	});

	test('Vergleich mit gesetztem Flag zeigt den Kanal, ohne dass empfaenger ihn nennt', async () => {
		const { homeHeroChannels } = await modul(path.join(HOME, 'homeHeroChannels.ts'));
		const kan = homeHeroChannels('vergleich', { ...PRESET, empfaenger: [], send_telegram: true });
		assert.deepEqual(kan, ['Email', 'Telegram']);
	});

	test('Trip: Kanaele aus report_config-Flags, nie aus empfaenger', async () => {
		const { homeHeroChannels } = await modul(path.join(HOME, 'homeHeroChannels.ts'));
		assert.deepEqual(homeHeroChannels('trip', TRIP), ['Email']);
		const mitTelegram = { ...TRIP, report_config: { ...TRIP.report_config, send_telegram: true } };
		assert.deepEqual(homeHeroChannels('trip', mitTelegram), ['Email', 'Telegram']);
	});
});

describe('AC-4: shared/ ohne Compare*-Komponenten (Struktur)', () => {
	test('keine Compare*-Komponentendatei in shared/', () => {
		const dateien = readdirSync(path.join(COMPONENTS, 'shared')).filter((f) => /^Compare.*\.svelte$/.test(f));
		assert.deepEqual(dateien, [], 'shared/ enthaelt noch Compare*-Komponenten');
	});

	test('OutlookLayoutControls liegt in shared/', () => {
		assert.ok(existsSync(path.join(COMPONENTS, 'shared/OutlookLayoutControls.svelte')), 'shared/OutlookLayoutControls.svelte fehlt (RED)');
	});

	test('CompareHourlyLayoutControls liegt in compare/ mit gz-eigenstaendig-Kopfzeile und Begruendung', () => {
		const p = path.join(COMPONENTS, 'compare/CompareHourlyLayoutControls.svelte');
		assert.ok(existsSync(p), 'compare/CompareHourlyLayoutControls.svelte fehlt (RED)');
		const kopf = readFileSync(p, 'utf8').split('\n').slice(0, 6).join('\n');
		const m = kopf.match(/gz-eigenstaendig:\s*(.+)/);
		assert.ok(m && m[1].trim().length >= 15, 'Kopfzeile gz-eigenstaendig: mit Begruendung (>=15 Zeichen) fehlt');
	});
});
