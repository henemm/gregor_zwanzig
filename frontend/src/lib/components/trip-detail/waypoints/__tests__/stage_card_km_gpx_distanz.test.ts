// TDD RED — #2119: Etappen-Kachel zeigt GPX-Track-Distanz statt Luftlinie.
// Spec: docs/specs/fast/fix-2119-stagecard-km.md — AC-1, AC-2, AC-3.
//
// Gemessen wird am ECHTEN serverseitigen Render (svelte/server) beider Kacheln
// (Desktop StageCard, mobil StageCardM) — kein Mock, kein Quelltext-Grep.
//
// Ausfuehrung: cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//   --experimental-test-module-mocks --test src/lib/components/trip-detail/waypoints/__tests__/stage_card_km_gpx_distanz.test.ts
import { register } from 'node:module';
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> waypoints -> trip-detail -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../../..');
register(
	pathToFileURL(path.join(FRONTEND, 'src/lib/components/trip-new/__tests__/ssrRunesHook.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);
register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const load = async (rel: string) =>
	(await import(pathToFileURL(path.join(FRONTEND, rel)).href)).default;
const StageCard = await load('src/lib/components/trip-detail/waypoints/StageCard.svelte');
const StageCardM = await load('src/lib/components/mobile/StageCardM.svelte');

// Luftlinie 47.0 -> 47.1 ist ca. 11 km; die vermessene Track-Distanz 17.5 km.
const wp = (id: string, lat: number, ele: number, dist?: number) => ({
	id,
	name: id,
	lat,
	lon: 11.0,
	elevation_m: ele,
	...(dist === undefined ? {} : { distance_from_start_km: dist })
});
const stageOf = (wps: unknown[]) => ({ id: 's1', name: 'Tag 1', date: '2026-08-01', waypoints: wps });

const VERMESSEN = stageOf([wp('a', 47.0, 100, 2), wp('b', 47.05, 400, 9), wp('c', 47.1, 766, 19.5)]);
const OHNE_MESSUNG = stageOf([wp('a', 47.0, 100), wp('b', 47.05, 400), wp('c', 47.1, 766)]);
const EIN_PUNKT = stageOf([wp('a', 47.0, 100, 0)]);

const desktop = (stage: unknown): string =>
	render(StageCard, { props: { stage, index: 0 } }).body;
const mobil = (stage: unknown): string =>
	render(StageCardM, { props: { stage, index: 0 } }).body;

describe('#2119 Etappen-Kachel: GPX-Track-Distanz', () => {
	test('AC-1: Desktop-Kachel zeigt Differenz der distance_from_start_km (17.5 km)', () => {
		assert.match(desktop(VERMESSEN), /17\.5\s*km/);
	});

	test('AC-2: mobile Kachel zeigt dieselbe Track-Distanz wie die Desktop-Kachel', () => {
		assert.match(mobil(VERMESSEN), /17\.5\s*km/);
	});

	test('AC-3: ohne Messwerte weiterhin Naeherungs-Distanz (beide Kacheln)', () => {
		assert.match(desktop(OHNE_MESSUNG), /\d+\.\d\s*km/);
		assert.match(mobil(OHNE_MESSUNG), /\d+\.\d\s*km/);
	});

	test('AC-3: unter 2 Wegpunkten keine km-Angabe (beide Kacheln)', () => {
		assert.doesNotMatch(desktop(EIN_PUNKT), /\d\s*km/);
		assert.doesNotMatch(mobil(EIN_PUNKT), /\d\s*km/);
	});
});
