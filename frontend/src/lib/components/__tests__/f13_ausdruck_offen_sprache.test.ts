// Issue #2764 (i18n F13, Epics #2730/#2644) — AC-3/AC-4: die bisher in AUSDRUCK_OFFEN
// geparkten echten Nutzertexte sprechen die Nutzersprache.
//   * AC-3: SubscriptionCard ohne Namen, echter SSR-Render (svelte/server) in de und en,
//   * AC-4: Rueckfall-Name einer Mehrfach-Symbol-Zeile ohne Register-Eintrag
//     (symbolZeilenName) in de byte-gleich zum Bestand, en = label_en des Metrik-Registers
//     (src/app/metric_catalog.py, _ENGLISH_NAMES). Literale fest verankert, nicht aus dem
//     Katalog nachgezogen.
// Spec: docs/specs/modules/i18n_f13_ausdruck_offen_2764.md
//
//   cd frontend && npm test -- src/lib/components/__tests__/f13_ausdruck_offen_sprache.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../..');
const LIB = path.resolve(HERE, '../..');
const base = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(path.join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, base);
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, base);

const { render } = await import('svelte/server');
const { locale, trFor } = await import(pathToFileURL(path.join(LIB, 'i18n/index.ts')).href);
const { symbolZeilenName, SYMBOL_ZEILE_RUECKFALL } = await import(
	pathToFileURL(path.join(LIB, 'components/shared/weather-metrics-tab/wertebereicheAnzeige.ts')).href
);
const Card = (await import(pathToFileURL(path.join(LIB, 'components/organisms/SubscriptionCard.svelte')).href)).default;

afterEach(() => locale.set('de'));

const sichtbar = (h: string) => h.replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();

describe('AC-3: SubscriptionCard ohne Namen', () => {
	const TRIP = { id: 'trip-1', name: '', stages: [{ id: 's1', name: 'E1', date: '2026-10-17', waypoints: [] }] };
	const PRESET = { id: 'cmp-1', name: '', location_ids: ['a', 'b'], schedule: 'daily' };
	const JETZT = new Date('2026-10-17T12:00:00Z');
	for (const [kind, sub, href] of [
		['trip', TRIP, undefined],
		['vergleich', PRESET, '/compare/cmp-1']
	] as const) {
		test(`${kind}${href ? ' (mit Link)' : ''}: de „(ohne Namen)", en „(no name)" ohne Neuladen`, () => {
			const props = { kind, sub, now: JETZT, dense: true, ...(href ? { href } : {}) };
			locale.set('de');
			const de = sichtbar(render(Card as never, { props: props as never }).body);
			locale.set('en');
			const en = sichtbar(render(Card as never, { props: props as never }).body);
			assert.ok(de.includes('(ohne Namen)'), de);
			assert.ok(en.includes('(no name)'), en);
			assert.ok(!en.includes('ohne Namen'), en);
		});
	}
});

/** Rueckfall je Kennung: de wortgleich zum Bestand vor #2764, en = label_en des Registers. */
const ANKER: [id: string, de: string, en: string][] = [
	['temperature', 'Temperatur', 'Temperature'],
	['temperature_night', 'Nacht-Tiefsttemperatur', 'Night low'],
	['wind_chill', 'Gefühlte Temperatur', 'Feels-like temperature'],
	['temperature_day_low', 'Tages-Tiefsttemperatur (Gehzeit)', 'Daytime low (walking hours)'],
	['temperature_day_high', 'Tages-Höchsttemperatur (Gehzeit)', 'Daytime high (walking hours)'],
	['wind_chill_day_low', 'Gefühlte Tages-Tiefsttemperatur (Gehzeit)', 'Feels-like daytime low (walking hours)'],
	['wind_chill_day_high', 'Gefühlte Tages-Höchsttemperatur (Gehzeit)', 'Feels-like daytime high (walking hours)'],
	['wind_chill_night', 'Gefühlte Nacht-Tiefsttemperatur', 'Feels-like night low']
];

describe('AC-4: Mehrfach-Symbol-Zeile ohne Register-Eintrag', () => {
	test('jede der acht Zeilen hat einen Rueckfall-Schluessel', () => {
		assert.deepEqual(Object.keys(SYMBOL_ZEILE_RUECKFALL).sort(), ANKER.map(([id]) => id).sort());
	});

	for (const [id, de, en] of ANKER) {
		test(`${id}: de „${de}", en „${en}"`, () => {
			assert.equal(symbolZeilenName({}, id, SYMBOL_ZEILE_RUECKFALL[id], 'de'), de);
			assert.equal(symbolZeilenName({}, id, SYMBOL_ZEILE_RUECKFALL[id], 'en'), en);
		});
	}

	test('mit Register-Eintrag gewinnt der Registername (de und en)', () => {
		const register = { wind_chill: { label: 'Gefühlt (Register)', label_en: 'Feels (register)' } };
		assert.equal(symbolZeilenName(register, 'wind_chill', SYMBOL_ZEILE_RUECKFALL.wind_chill, 'de'), 'Gefühlt (Register)');
		assert.equal(symbolZeilenName(register, 'wind_chill', SYMBOL_ZEILE_RUECKFALL.wind_chill, 'en'), 'Feels (register)');
	});
});

describe('AC-5: Marke aus dem Katalog, deutscher Wortlaut unveraendert', () => {
	test('bausteine.marke.* liefert in beiden Sprachen den Eigennamen', () => {
		for (const lang of ['de', 'en'] as const) {
			assert.equal(`${trFor(lang, 'bausteine.marke.gregor')} · ${trFor(lang, 'bausteine.marke.zwanzig')}`, 'gregor · zwanzig');
			assert.equal(`X — ${trFor(lang, 'bausteine.marke.name')}`, 'X — Gregor Zwanzig');
		}
	});
});
