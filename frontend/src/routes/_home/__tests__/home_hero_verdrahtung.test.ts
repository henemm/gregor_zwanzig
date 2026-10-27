// Issue #2346 S3 (AC-11/AC-12), Fix-Loop 1 (Adversary F001–F004): die Hero-Zusicherungen dort
// pruefen, wo sie wirken — nicht nur am isolierten Baustein (home_hero_paritaet.test.ts).
//   A  homeHeroProps(kind, sub, nextBriefings): die Verdrahtung, die +page.svelte per Spread an
//      <HomeHero> reicht (Kanaele aus Flags statt empfaenger, naechster Versand aus dem Backend).
//   B  HomeHero rendert Schnellaktionen (actions), rechte Spalte (aside) und das Oeffnen-Label je kind.
//   C  +page.svelte (AST, echter Svelte-Compiler wie aktionsmodellAst.ts — die Seite ist im
//      SSR-Harness nicht renderbar): genau zwei HomeHero, beide NUR aus homeHeroProps gespeist,
//      richtiges kind am richtigen Objekt, keine zweite Inline-Hero-Flaeche.
//
// Pfadregel #1409: relativ zu DIESER Datei.
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/_home/__tests__/home_hero_verdrahtung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { ladeSvelte, collect, bedingungen, type Knoten } from '../../../lib/components/shared/__tests__/aktionsmodellAst.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../..');
const HOME = path.resolve(HERE, '..');
const PAGE = path.resolve(HERE, '../../+page.svelte');

register(pathToFileURL(path.join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const { render } = await import('svelte/server');
const { createRawSnippet } = await import('svelte');
const { homeHeroProps } = await import(pathToFileURL(path.join(HOME, 'homeHeroProps.ts')).href);
const Hero = (await import(pathToFileURL(path.join(HOME, 'HomeHero.svelte')).href)).default;

const html = (props: Record<string, unknown>) => render(Hero, { props }).body.replace(/<!--.*?-->/g, '');
const kanaele = (h: string) => [...h.matchAll(/data-channel="([^"]+)"/g)].map((m) => m[1]);
const roh = (text: string) => createRawSnippet(() => ({ render: () => `<span>${text}</span>` }));

// Trip: nur E-Mail-Flag (Morgen-Slot aktiv), empfaenger nennt trotzdem Telegram.
const TRIP: any = {
	id: 'trip-1',
	name: 'GR20 Nord',
	region: 'Korsika',
	stages: [{ id: 's1', name: 'E1', date: '2026-10-29', waypoints: [] }],
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
// Vergleich: alle Opt-in-Flags aus, empfaenger nennt Telegram und SMS (#1452).
const PRESET: any = {
	id: 'cmp-1',
	name: 'Ortsvergleich Nord',
	location_ids: ['a', 'b'],
	schedule: 'daily',
	display_config: { region: 'Tirol' },
	send_telegram: false,
	send_sms: false,
	send_premium_sms: false,
	empfaenger: ['telegram:12345', 'sms:+4915100000']
};
// Backend-Antwort GET /api/next-briefings: je kind eine eigene Map (Trip Do, Vergleich Fr).
const NBS = {
	trips: { 'trip-1': { at: '2026-10-29T06:00:00Z', local_date: '2026-10-29', local_time: '07:00', tz_abbr: 'CET', slot: 'morning' } },
	compare: { 'cmp-1': { at: '2026-10-30T17:00:00Z', local_date: '2026-10-30', local_time: '18:00', tz_abbr: 'CET', slot: 'evening' } }
};

describe('A: homeHeroProps — Verdrahtung, die +page.svelte an HomeHero reicht', () => {
	test('Vergleich: Kanaele aus den Flags (nur Email), naechster Versand aus compare-Map', () => {
		assert.deepEqual(homeHeroProps('vergleich', PRESET, NBS), {
			kind: 'vergleich',
			id: 'cmp-1',
			name: 'Ortsvergleich Nord',
			href: '/compare/cmp-1',
			subtitle: 'Tirol · 2 Orte verglichen',
			channels: ['Email'],
			nextSend: 'Fr 18:00 (CET)'
		});
	});

	test('Trip: Kanaele aus report_config (nur Email), naechster Versand aus trips-Map', () => {
		assert.deepEqual(homeHeroProps('trip', TRIP, NBS), {
			kind: 'trip',
			id: 'trip-1',
			name: 'GR20 Nord',
			href: '/trips/trip-1?tab=uebersicht',
			subtitle: 'Korsika',
			channels: ['Email'],
			nextSend: 'Do 07:00 (CET)'
		});
	});

	test('Flag an zeigt den Kanal, auch ohne Eintrag in empfaenger (beide kinds)', () => {
		const p = { ...PRESET, empfaenger: [], send_telegram: true };
		assert.deepEqual(homeHeroProps('vergleich', p, NBS).channels, ['Email', 'Telegram']);
		const t = { ...TRIP, empfaenger: [], report_config: { ...TRIP.report_config, send_sms: true } };
		assert.deepEqual(homeHeroProps('trip', t, NBS).channels, ['Email', 'SMS']);
	});

	test('ohne Backend-Antwort: "—" statt eigener Rechnung', () => {
		assert.equal(homeHeroProps('trip', TRIP, null).nextSend, '—');
		assert.equal(homeHeroProps('vergleich', PRESET, null).nextSend, '—');
	});

	test('gerendert: der Vergleichs-Hero zeigt nur Email und den Backend-Versand', () => {
		const h = html({ ...homeHeroProps('vergleich', PRESET, NBS) });
		assert.deepEqual(kanaele(h), ['Email']);
		assert.ok(h.includes('Fr 18:00 (CET)'), 'naechster Versand fehlt im Hero');
		assert.ok(!/telegram|sms/i.test(h), 'Kanal aus empfaenger im Hero');
	});
});

describe('B: HomeHero rendert Schnellaktionen, rechte Spalte und das Oeffnen-Label je kind', () => {
	const basis = { id: 'x', name: 'X', channels: ['Email'] };

	test('actions-Snippet erscheint unter der Ueberschrift Schnellaktionen', () => {
		const h = html({ ...basis, kind: 'trip', href: '/trips/x', actions: roh('AKTION-PAUSENTAG') });
		assert.ok(h.includes('AKTION-PAUSENTAG'), 'Schnellaktionen werden nicht gerendert');
		assert.ok(h.indexOf('Schnellaktionen') >= 0 && h.indexOf('Schnellaktionen') < h.indexOf('AKTION-PAUSENTAG'));
	});

	// F006: pills im Feld "pills" (vor dem Titel), details zwischen Untertitel und Naechstem Versand.
	test('pills- und details-Snippet erscheinen an ihrer Stelle der Felderfolge', () => {
		const h = html({
			...basis, kind: 'trip', href: '/trips/x', subtitle: 'UNTERTITEL',
			pills: roh('PILL-LIVE'), details: roh('DETAIL-FORTSCHRITT')
		});
		const pos = (s: string) => h.indexOf(s);
		for (const s of ['PILL-LIVE', 'DETAIL-FORTSCHRITT']) assert.ok(pos(s) >= 0, `${s} wird nicht gerendert`);
		assert.ok(pos('data-field="pills"') < pos('PILL-LIVE') && pos('PILL-LIVE') < pos('data-field="title"'), 'pills nicht im Pills-Feld');
		assert.ok(
			pos('UNTERTITEL') < pos('DETAIL-FORTSCHRITT') && pos('DETAIL-FORTSCHRITT') < pos('data-field="next-send"'),
			'details nicht zwischen Untertitel und Naechstem Versand'
		);
	});

	test('ohne actions keine leere Schnellaktionen-Ueberschrift', () => {
		const h = html({ ...basis, kind: 'trip', href: '/trips/x' });
		assert.ok(!h.includes('Schnellaktionen'));
	});

	test('aside-Snippet (Versand heute + Alerts) erscheint im Hero-Raster nach der Karte', () => {
		const h = html({ ...basis, kind: 'vergleich', href: '/compare/x', aside: roh('SPALTE-OUTBOX') });
		assert.ok(h.includes('SPALTE-OUTBOX'), 'rechte Spalte wird nicht gerendert');
		assert.ok(h.indexOf('data-field="channels"') < h.indexOf('SPALTE-OUTBOX'));
	});

	test('Oeffnen-Link: Trip -> "Trip öffnen →", Vergleich -> "Vergleich öffnen →", Ziel = href', () => {
		const t = html({ ...basis, kind: 'trip', href: '/trips/x?tab=uebersicht' });
		const c = html({ ...basis, kind: 'vergleich', href: '/compare/x' });
		assert.match(t, /<a[^>]*href="\/trips\/x\?tab=uebersicht"[^>]*>Trip öffnen →<\/a>/);
		assert.ok(!t.includes('Vergleich öffnen'));
		assert.match(c, /<a[^>]*href="\/compare\/x"[^>]*>Vergleich öffnen →<\/a>/);
		assert.ok(!c.includes('Trip öffnen'));
	});
});

describe('C: +page.svelte bindet beide Heros ausschliesslich ueber homeHeroProps ein (AST)', () => {
	const ast = ladeSvelte(PAGE);
	const heroes = collect(ast.fragment, (n) => n.type === 'Component' && n.name === 'HomeHero');

	test('genau zwei HomeHero, jeder NUR mit {...homeHeroProps(...)} (kein Attribut ueberschreibt)', () => {
		assert.equal(heroes.length, 2, `HomeHero-Einbindungen: ${heroes.length}`);
		for (const h of heroes) {
			const attrs = h.attributes as Knoten[];
			assert.equal(attrs.length, 1, `HomeHero traegt zusaetzliche Attribute: ${attrs.map((a) => a.name ?? a.type).join(', ')}`);
			assert.equal(attrs[0].type, 'SpreadAttribute');
			assert.equal(attrs[0].expression?.type, 'CallExpression');
			assert.equal(attrs[0].expression.callee?.name, 'homeHeroProps');
		}
	});

	// F005: ein umbenanntes Snippet rendert HomeHero still nicht (Props pills/details/actions/aside).
	// Base 692d0486a: je Hero vier QuickAction (Trip :357-375, Vergleich :620-638).
	test('jeder HomeHero reicht genau die Snippets pills, details, actions, aside; actions mit 4 Schnellaktionen', () => {
		for (const h of heroes) {
			const kind = h.attributes[0].expression.arguments[0].value;
			const snippets = ((h.fragment?.nodes ?? []) as Knoten[]).filter((n) => n.type === 'SnippetBlock');
			const namen = snippets.map((s) => s.expression?.name).sort();
			assert.deepEqual(namen, ['actions', 'aside', 'details', 'pills'], `${kind}: Snippets ${namen.join(', ')}`);
			const actions = snippets.find((s) => s.expression?.name === 'actions')!;
			const qa = collect(actions.body, (n) => n.type === 'Component' && n.name === 'QuickAction');
			assert.equal(qa.length, 4, `${kind}: ${qa.length} Schnellaktionen im actions-Snippet`);
		}
	});

	test('richtiges kind am richtigen Objekt, beide mit der Backend-Antwort', () => {
		const aufrufe = heroes.map((h) => {
			const [k, sub, nbs] = (h.attributes[0].expression.arguments ?? []) as Knoten[];
			return [k?.type === 'Literal' ? k.value : `?${k?.type}`, sub?.name, nbs?.name];
		});
		assert.deepEqual(
			aufrufe.sort(),
			[
				['trip', 'hero', 'nextBriefings'],
				['vergleich', 'compareHero', 'nextBriefings']
			]
		);
	});

	test('Trip-Hero nur im Trip-Zustand, Vergleichs-Hero nur im Vergleichs-Zustand', () => {
		for (const h of heroes) {
			const kind = h.attributes[0].expression.arguments[0].value;
			const bed = (bedingungen(ast.fragment, h) ?? []).join(' && ');
			if (kind === 'trip') assert.match(bed, /heroIsActive/, bed);
			else assert.match(bed, /mode === 'compare'|mode === "compare"/, bed);
		}
	});

	test('keine zweite Inline-Hero-Flaeche (Raster, Felder, Hero-Ueberschriften) in +page.svelte', () => {
		const klassen = collect(
			ast.fragment,
			(n) => n.type === 'Attribute' && n.name === 'class' && Array.isArray(n.value) && n.value.some((v: Knoten) => v.type === 'Text' && /cockpit-hero/.test(v.data))
		);
		assert.equal(klassen.length, 0, 'cockpit-hero-Raster inline in +page.svelte');
		const felder = collect(ast.fragment, (n) => n.type === 'Attribute' && n.name === 'data-field');
		assert.equal(felder.length, 0, 'Hero-Felder (data-field) inline in +page.svelte');
		const texte = collect(ast.fragment, (n) => n.type === 'Text' && typeof n.data === 'string').map((n) => n.data.trim());
		for (const marke of ['Schnellaktionen', 'Kanäle', 'Nächster Versand', 'Trip öffnen →', 'Vergleich öffnen →'])
			assert.ok(!texte.includes(marke), `Hero-Inhalt "${marke}" inline in +page.svelte`);
		const akzent = texte.filter((t) => t.includes('border-left: 3px solid var(--g-accent)'));
		assert.deepEqual(akzent, [], 'Hero-Karte mit Akzentkante inline in +page.svelte');
	});
});
