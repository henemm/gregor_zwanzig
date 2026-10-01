// TDD RED — Issue #2277 Scheibe S2a: /trips/new bekommt den Reiter
// „Wertebereiche", gemountet ueber den geteilten CorridorEditor
// (context="route", createMode) — dauerhaft im DOM je Viewport (Muster
// WeatherMetricsTab/AlarmeTab), Aenderungen fliessen ueber onCorridorsChange in
// den EINEN POST /api/trips.
//
// Spec: docs/specs/modules/fix_2277_s2a_wertebereiche_trip_anlegen.md (AC-1, AC-2, AC-5)
//
// AC-1/AC-5: echtes SSR-Rendering ueber tripNewSsr.ts (Issue #1738).
// AC-2 (Verdrahtung): Wirkort-Pruefstand svelteInstanzPruefstand.ts gegen
// TripNewEditor.svelte — der ECHTE Rueckruf `handleCorridorsChange` und das
// ECHTE `buildAndSave()` laufen, nur der Transport (`api.post`) ist ein Spion.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/trip-new/__tests__/trip_new_wertebereiche_reiter.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { join } from 'node:path';
import { renderTripNew, countTestid, desktopTabs, mobilTabLabels, FRONTEND } from './tripNewSsr.ts';
import {
	umgebungFuer,
	findeKomponenten,
	attributAusdruck,
	type Knoten
} from '../../shared/__tests__/svelteInstanzPruefstand.ts';

const EDITOR = join(FRONTEND, 'src/lib/components/trip-new/TripNewEditor.svelte');

// Issue #2277 S3 (Spec feat_2277_s3_reiter_angleichung_rueckbau.md, AC-1/AC-2):
// die S2a-Folge „…, Wertebereiche, Briefing-Zeitplan, Alerts" ist abgeloest —
// die letzten Reiter heissen jetzt wie beim Ortsvergleich „Alarme · Versand".
const ERWARTETE_FOLGE = [
	'Route',
	'Etappen & GPX',
	'Wegpunkte prüfen',
	'Wetter-Metriken',
	'Wertebereiche',
	'Alarme',
	'Versand'
];

describe('AC-1: Reiter „Wertebereiche" zwischen Wetter-Metriken und Alarme', () => {
	test('Desktop: Reiterfolge …, Wetter-Metriken, Wertebereiche, Alarme, Versand', () => {
		const html = renderTripNew({ activeTab: 'route', isMobileViewport: false });
		const labels = desktopTabs(html).map((t) => t.label);
		assert.ok(labels.length >= 6, `Messaufbau kaputt: nur ${labels.length} Desktop-Tabs gelesen.`);
		assert.deepEqual(labels, ERWARTETE_FOLGE, 'AC-1 FAIL: Desktop-Reiterfolge stimmt nicht.');
	});

	test('Mobil: dieselbe Reiterfolge', () => {
		const html = renderTripNew({ activeTab: 'route', isMobileViewport: true });
		assert.deepEqual(
			mobilTabLabels(html).slice(0, ERWARTETE_FOLGE.length),
			ERWARTETE_FOLGE,
			'AC-1 FAIL: Mobil-Reiterfolge stimmt nicht.'
		);
	});

	test('Sperrhinweise: Wertebereiche → Wetter-Metriken, Alarme → Wertebereiche, Versand → Alarme', () => {
		const html = renderTripNew({ activeTab: 'route', isMobileViewport: false });
		const tabs = desktopTabs(html);
		const wb = tabs.find((t) => t.label === 'Wertebereiche');
		assert.ok(wb, 'AC-1 FAIL: kein Desktop-Reiter „Wertebereiche".');
		assert.equal(
			wb!.title,
			'Gesperrt — erst Wetter-Metriken öffnen',
			'AC-1 FAIL: Wertebereiche ist im Leerzustand nicht mit dem Hinweis auf Wetter-Metriken gesperrt.'
		);
		const al = tabs.find((t) => t.label === 'Alarme');
		assert.ok(al, 'AC-1 FAIL: kein Desktop-Reiter „Alarme".');
		assert.equal(
			al!.title,
			'Gesperrt — erst Wertebereiche öffnen',
			'AC-2 FAIL: Alarme verweist nicht auf den Wertebereiche-Reiter als Vorstufe.'
		);
		const vs = tabs.find((t) => t.label === 'Versand');
		assert.ok(vs, 'AC-1 FAIL: kein Desktop-Reiter „Versand".');
		assert.equal(
			vs!.title,
			'Gesperrt — erst Alarme öffnen',
			'AC-2 FAIL: Versand verweist nicht auf den Alarme-Reiter als Vorstufe.'
		);
	});
});

describe('AC-5: CorridorEditor bleibt dauerhaft gemountet — genau EINE Instanz je Kombination', () => {
	const kombinationen: { activeTab: string; isMobileViewport: boolean }[] = [
		{ activeTab: 'wertebereiche', isMobileViewport: false },
		{ activeTab: 'wertebereiche', isMobileViewport: true },
		{ activeTab: 'route', isMobileViewport: false }
	];
	for (const kombi of kombinationen) {
		test(`${JSON.stringify(kombi)} → genau 1 corridor-editor-route (nie 0, nie 2)`, () => {
			const html = renderTripNew(kombi);
			assert.equal(
				countTestid(html, 'corridor-editor-route'),
				1,
				`AC-5 FAIL: ${JSON.stringify(kombi)} liefert nicht genau eine CorridorEditor-Instanz — ` +
					'entweder fehlt das isMobileViewport-Gate / der Dauer-Mount (0) oder Desktop UND ' +
					'Mobil stehen gleichzeitig im DOM (2).'
			);
		});
	}
});

describe('AC-2 (Verdrahtung): CorridorEditor-Rueckruf → CreateTripState → POST-Body', () => {
	test('beide Mounts: context="route", createMode={true}, onCorridorsChange={handleCorridorsChange}', async () => {
		const { ast, quelle } = await umgebungFuer(EDITOR, {});
		const mounts = findeKomponenten(ast, 'CorridorEditor');
		assert.equal(mounts.length, 2, `AC-2 FAIL: ${mounts.length} CorridorEditor-Mounts (erwartet: Desktop + Mobil).`);
		for (const m of mounts) {
			assert.equal(attributAusdruck(m, quelle, 'createMode'), 'true', 'AC-2 FAIL: Mount ohne createMode={true}.');
			assert.equal(
				attributAusdruck(m, quelle, 'onCorridorsChange'),
				'handleCorridorsChange',
				'AC-2 FAIL: Mount meldet Aenderungen nicht an handleCorridorsChange.'
			);
			const ctx = (m.attributes as Knoten[]).find((a) => a.name === 'context');
			assert.ok(ctx, 'AC-2 FAIL: Mount ohne context-Attribut.');
		}
	});

	test('handleCorridorsChange(c) → buildAndSave() postet genau diese corridors', async () => {
		const gepostet: unknown[] = [];
		const saat: Knoten = {
			ready: true,
			saving: false,
			savedTripId: null,
			saveError: null,
			activeTab: 'versand',
			name: 'Karnischer Höhenweg',
			region: '',
			startDate: '2026-06-15',
			stages: [{ id: 1, name: 'Toblach → Helmhotel', waypoints: [] }],
			weatherMetrics: [],
			channels: { email: true, telegram: false, sms: false },
			reportConfig: undefined,
			selectedActivity: undefined,
			api: {
				post: async (_url: string, body: unknown) => {
					gepostet.push(body);
					return { id: 'neu123' };
				}
			}
		};
		const { u } = await umgebungFuer(EDITOR, saat);
		assert.equal(typeof u.buildAndSave, 'function', 'Messaufbau kaputt: buildAndSave nicht gebunden.');
		assert.ok(u.alarm !== undefined, 'Messaufbau kaputt: der Alarm-Schatten-State liess sich nicht herleiten.');
		assert.equal(
			typeof u.handleCorridorsChange,
			'function',
			'AC-2 FAIL: TripNewEditor hat keinen Rueckkanal handleCorridorsChange fuer den Wertebereiche-Reiter.'
		);
		const korridor = [{ metric: 'wind_gust', range: [null, 80], notify: true, mark: false }];
		u.handleCorridorsChange(korridor);
		const id = await u.buildAndSave();
		assert.equal(id, 'neu123', `Messaufbau kaputt: buildAndSave lieferte ${id} (saveError=${u.saveError}).`);
		assert.equal(gepostet.length, 1, 'Messaufbau kaputt: kein POST abgesetzt.');
		assert.deepEqual(
			(gepostet[0] as { corridors?: unknown }).corridors,
			korridor,
			'AC-2 FAIL: die ueber onCorridorsChange gemeldeten Wertebereiche fehlen im POST /api/trips.'
		);
	});
});
