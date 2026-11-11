// TDD RED — Issue #2919 (Epic #2730, ADR-0104): vier deutsche Restbegriffe bei Profilsprache en.
// Spec: docs/specs/modules/i18n_2919_en_restbegriffe.md (AC-1 … AC-6)
// Echtes SSR-Rendering (svelte/server) mit locale en und de, keine Mocks.
//
//   cd frontend && npm test -- src/lib/components/__tests__/en_restbegriffe_2919.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { readFileSync } from 'node:fs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../..');
const LIB = path.resolve(HERE, '../..');
const base = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(path.join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, base);
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, base);

const { render } = await import('svelte/server');
const { locale, trFor } = await import(pathToFileURL(path.join(LIB, 'i18n/index.ts')).href);
const { scanneMarkup } = await import(pathToFileURL(path.join(LIB, 'i18n/__tests__/hardcode_scan.ts')).href);
const lade = async (rel: string) => (await import(pathToFileURL(path.join(LIB, rel)).href)).default;

afterEach(() => locale.set('de'));

const html = (comp: any, props: Record<string, unknown>) =>
	render(comp, { props: props as never }).body.replace(/<!--[\s\S]*?-->/g, '');
const ent = (s: string) =>
	s.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
const text = (h: string) => ent(h.replace(/<[^>]*>/g, ' ')).replace(/\s+/g, ' ').trim();

function mitSprache<T>(lang: 'de' | 'en', fn: () => T): T {
	locale.set(lang);
	return fn();
}

// ---------------------------------------------------------------- AC-1
describe('AC-1: Filterchips auf /trips und /compare', () => {
	const COUNTS = { all: 9, aktiv: 4, geplant: 2, pausiert: 1, fertig: 2 };
	const chips = (h: string) =>
		[...h.matchAll(/data-testid="status-filter-pill-[^"]+"[^>]*>([\s\S]*?)<\/button>/g)].map((m) => text(m[1]));

	test('en: All / Active / Planned / Paused / Finished mit unveraenderten Zaehlern', async () => {
		const Pills = await lade('components/molecules/StatusFilterPills.svelte');
		const h = mitSprache('en', () => html(Pills, { active: 'all', counts: COUNTS, onSelect: () => {} }));
		assert.deepEqual(chips(h), ['All (9)', 'Active (4)', 'Planned (2)', 'Paused (1)', 'Finished (2)']);
		// Logikwerte (Filterwerte) bleiben deutsch.
		for (const v of ['all', 'aktiv', 'geplant', 'pausiert', 'fertig']) {
			assert.match(h, new RegExp(`data-testid="status-filter-pill-${v}"`));
		}
	});

	test('de: unveraendert Alle / Aktiv / Geplant / Pausiert / Fertig', async () => {
		const Pills = await lade('components/molecules/StatusFilterPills.svelte');
		const h = mitSprache('de', () => html(Pills, { active: 'all', counts: COUNTS, onSelect: () => {} }));
		assert.deepEqual(chips(h), ['Alle (9)', 'Aktiv (4)', 'Geplant (2)', 'Pausiert (1)', 'Fertig (2)']);
	});
});

// ---------------------------------------------------------------- AC-2
describe('AC-2: Status auf Trip- und Vergleichskarte', () => {
	const JETZT = new Date('2026-10-17T12:00:00Z');
	const trip = (extra: Record<string, unknown>, dates: string[]) => ({
		id: 'trip-1',
		name: 'GR20 Nord',
		region: 'Korsika',
		stages: dates.map((d, i) => ({ id: `s${i}`, name: `E${i}`, date: d, waypoints: [] })),
		...extra
	});
	const preset = (extra: Record<string, unknown>) => ({
		id: 'cmp-1',
		name: 'Vergleich',
		location_ids: ['a', 'b'],
		schedule: 'daily',
		profil: 'wintersport',
		...extra
	});
	// [Beschreibung, kind, sub, data-status, de, en]
	const FAELLE: Array<[string, 'trip' | 'vergleich', Record<string, unknown>, string, string, string]> = [
		['Trip aktiv', 'trip', trip({}, ['2026-10-17']), 'active', 'aktiv', 'active'],
		['Trip geplant', 'trip', trip({}, ['2026-12-01']), 'active', 'geplant', 'planned'],
		['Trip fertig', 'trip', trip({}, ['2026-09-01']), 'active', 'fertig', 'finished'],
		['Trip pausiert', 'trip', trip({ paused_at: '2026-10-01T00:00:00Z' }, ['2026-10-17']), 'paused', 'pausiert', 'paused'],
		['Trip Entwurf', 'trip', trip({}, []), 'draft', 'draft', 'draft'],
		['Trip archiviert', 'trip', trip({ archived_at: '2026-10-01T00:00:00Z' }, ['2026-10-17']), 'archived', 'archiviert', 'archived'],
		['Vergleich aktiv', 'vergleich', preset({}), 'active', 'aktiv', 'active'],
		['Vergleich pausiert', 'vergleich', preset({ paused_at: '2026-10-01T00:00:00Z' }), 'paused', 'pausiert', 'paused'],
		['Vergleich Entwurf', 'vergleich', preset({ location_ids: [] }), 'draft', 'draft', 'draft'],
		['Vergleich archiviert', 'vergleich', preset({ archived_at: '2026-10-01T00:00:00Z' }), 'archived', 'archiviert', 'archived']
	];
	const statusFeld = (h: string) => {
		const m = h.match(/data-field="status"[^>]*>([^<]*)</);
		assert.ok(m, 'data-field="status" fehlt');
		return text(m[1]);
	};

	for (const [name, kind, sub, dataStatus, deText, enText] of FAELLE) {
		test(`${name}: en "${enText}", de "${deText}", data-status "${dataStatus}"`, async () => {
			const Card = await lade('components/organisms/SubscriptionCard.svelte');
			const props = { kind, sub, now: JETZT, dense: true, onAction: () => {}, onclick: () => {} };
			const en = mitSprache('en', () => html(Card, props));
			const de = mitSprache('de', () => html(Card, props));
			assert.equal(statusFeld(en), enText, 'en-Anzeige');
			assert.equal(statusFeld(de), deText, 'de-Anzeige unveraendert');
			assert.match(en, new RegExp(`data-status="${dataStatus}"`));
			assert.match(de, new RegExp(`data-status="${dataStatus}"`));
		});
	}
});

// ---------------------------------------------------------------- AC-3
describe('AC-3: Ueberschrift des mobilen Aktionsblatts', () => {
	const props = { open: true, onClose: () => {}, kind: 'trip', status: 'active', name: 'GR20 Nord', onAction: () => {} };
	test('en: ACTIONS', async () => {
		const Sheet = await lade('components/mobile/SubscriptionActionSheet.svelte');
		const h = text(mitSprache('en', () => html(Sheet, props)));
		assert.match(h, /\bACTIONS\b/);
		assert.doesNotMatch(h, /AKTIONEN/);
	});
	test('de: weiterhin AKTIONEN', async () => {
		const Sheet = await lade('components/mobile/SubscriptionActionSheet.svelte');
		const h = text(mitSprache('de', () => html(Sheet, props)));
		assert.match(h, /\bAKTIONEN\b/);
	});
});

// ---------------------------------------------------------------- AC-4
describe('AC-4: Logo-Untertitel', () => {
	test('en ohne caption: V0.20 · WEATHER BRIEFING', async () => {
		const W = await lade('brand/BrandWordmark.svelte');
		const h = text(mitSprache('en', () => html(W, {})));
		assert.match(h, /V0\.20 · WEATHER BRIEFING/);
		assert.doesNotMatch(h, /WETTER/);
	});
	test('de ohne caption: V0.20 · WETTER-BRIEFING', async () => {
		const W = await lade('brand/BrandWordmark.svelte');
		const h = text(mitSprache('de', () => html(W, {})));
		assert.match(h, /V0\.20 · WETTER-BRIEFING/);
	});
	test('Sprachwechsel ohne Neuladen: dieselbe Komponente folgt der Sprache', async () => {
		const W = await lade('brand/BrandWordmark.svelte');
		const a = text(mitSprache('de', () => html(W, {})));
		const b = text(mitSprache('en', () => html(W, {})));
		const c = text(mitSprache('de', () => html(W, {})));
		assert.match(a, /WETTER-BRIEFING/);
		assert.match(b, /WEATHER BRIEFING/);
		assert.match(c, /WETTER-BRIEFING/);
	});
	test('caption=null: kein Untertitel, in beiden Sprachen', async () => {
		const W = await lade('brand/BrandWordmark.svelte');
		for (const lang of ['de', 'en'] as const) {
			const h = text(mitSprache(lang, () => html(W, { caption: null })));
			assert.doesNotMatch(h, /V0\.20|BRIEFING/, lang);
		}
	});
	test('explizite caption bleibt wie uebergeben', async () => {
		const W = await lade('brand/BrandWordmark.svelte');
		const h = text(mitSprache('en', () => html(W, { caption: 'Eigener Text' })));
		assert.match(h, /EIGENER TEXT/);
	});
});

// ---------------------------------------------------------------- AC-5
describe('AC-5: Hardcode-Ratsche erkennt eyebrow=', () => {
	test('Fixture: statisches eyebrow="Aktionen" ist ein Attribut-Treffer', () => {
		const quelle = ['<script lang="ts">', '</script>', '', '<Sheet eyebrow="Aktionen" />'].join('\n');
		assert.deepEqual(scanneMarkup(quelle), [{ zeile: 4, art: 'attribut', text: 'Aktionen' }]);
	});
	test('Fixture: eyebrow mit Katalog-Ausdruck ist kein Treffer', () => {
		const quelle = "<Sheet eyebrow={$t('aktionen.sheet.eyebrow')} />";
		assert.deepEqual(scanneMarkup(quelle), []);
	});
	test('echtes SubscriptionActionSheet hat keinen eyebrow-Treffer', () => {
		const q = readFileSync(path.join(LIB, 'components/mobile/SubscriptionActionSheet.svelte'), 'utf8');
		assert.deepEqual(scanneMarkup(q), []);
		assert.doesNotMatch(q, /eyebrow\s*=\s*["']/, 'eyebrow ist noch ein statischer Text');
	});
});

// ---------------------------------------------------------------- AC-6
describe('AC-6: vier neue Katalogschluessel in de und en', () => {
	const NEU: Array<[string, string, string]> = [
		['listen.filter.alle', 'Alle', 'All'],
		['listen.status.archiviert', 'archiviert', 'archived'],
		['aktionen.sheet.eyebrow', 'AKTIONEN', 'ACTIONS'],
		['bausteine.wordmark.caption', 'V0.20 · Wetter-Briefing', 'V0.20 · Weather briefing']
	];
	for (const [k, de, en] of NEU) {
		test(`${k}: de "${de}", en "${en}"`, () => {
			assert.equal(trFor('de', k), de);
			assert.equal(trFor('en', k), en);
		});
	}
});
