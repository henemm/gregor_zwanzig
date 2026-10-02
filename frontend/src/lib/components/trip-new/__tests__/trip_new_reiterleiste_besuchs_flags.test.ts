// #2277 S4 (AC-2): Wirkstelle der Trip-Reiterleiste. Der echte TripNewEditor (SSR)
// reicht die Besuchs-Flags an die geteilte Lock-Engine durch; gelesen wird die
// gerenderte Reiterleiste (⊘ = gesperrt, ✓ = erledigt), nicht die Logik-Funktion.
// Wichtig ist der Fall "Besuchs-Flags gesetzt, Etappen ohne GPX (etDone false)":
// Verhalten wie vor dem Refactoring — Wertebereiche/Alarme/Versand haengen NUR an
// den Besuchs-Flags, Wetter-Metriken und Wegpunkte nur an etDone.
//
// Ausfuehren (aus frontend/):
//   node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/trip-new/__tests__/trip_new_reiterleiste_besuchs_flags.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { renderTripNew, type TripNewStateOverride } from './tripNewSsr.ts';

const LABELS: Record<string, string> = {
	route: 'Route', etappen: 'Etappen &amp; GPX', wegpunkte: 'Wegpunkte prüfen',
	metriken: 'Wetter-Metriken', wertebereiche: 'Wertebereiche', alarme: 'Alarme', versand: 'Versand',
};

/** Desktop-Reiterleiste: je Reiter { locked, done }. */
function bar(over: TripNewStateOverride) {
	const html = renderTripNew({
		isMobileViewport: false, activeTab: 'route',
		name: 'X', startDate: '2026-07-01', stageNames: ['E1'], ...over,
	});
	const tabs = [...html.matchAll(/<div[^>]*role="tab"[^>]*>([\s\S]*?)<\/div>/g)].map((m) => m[1]);
	assert.equal(tabs.length, 7, 'Desktop-Reiterleiste mit 7 Reitern nicht gefunden — Wirkstelle nicht erreicht');
	const out: Record<string, { locked: boolean; done: boolean }> = {};
	for (const [id, label] of Object.entries(LABELS)) {
		const inner = tabs.find((t) => t.includes(label));
		assert.ok(inner, `Reiter ${id} fehlt`);
		out[id] = { locked: inner!.includes('⊘'), done: inner!.includes('✓') };
	}
	return out;
}
const lockedIds = (b: ReturnType<typeof bar>) => Object.keys(b).filter((k) => b[k].locked).sort();

describe('AC-2: Trip-Reiterleiste reicht die Besuchs-Flags durch (etDone = false)', () => {
	test('nichts besucht: ab Wegpunkte alles gesperrt', () => {
		assert.deepEqual(lockedIds(bar({})), ['alarme', 'metriken', 'versand', 'wegpunkte', 'wertebereiche']);
	});
	test('nur Metriken-Flag: Wertebereiche frei, Alarme/Versand gesperrt', () => {
		assert.deepEqual(lockedIds(bar({ wtVisited: true })), ['alarme', 'metriken', 'versand', 'wegpunkte']);
	});
	test('F001: Flags wt+wb+al gesetzt, etDone false => nur Metriken und Wegpunkte gesperrt (wie HEAD)', () => {
		const b = bar({ wtVisited: true, wbVisited: true, alVisited: true });
		assert.deepEqual(lockedIds(b), ['metriken', 'wegpunkte']);
		assert.equal(b.wertebereiche.done, true);
		assert.equal(b.alarme.done, true);
		assert.equal(b.metriken.done, true);
		assert.equal(b.versand.done, false);
	});
	test('Kette: wb-Flag oeffnet Alarme (jede Stufe haengt nur am Vorgaenger-Flag)', () => {
		assert.deepEqual(lockedIds(bar({ wbVisited: true })), ['metriken', 'versand', 'wegpunkte', 'wertebereiche']);
	});
	test('Versand-Flag macht Versand erledigt', () => {
		assert.equal(bar({ vsVisited: true }).versand.done, true);
	});
});

// AC-3: Speichern-Knopf (Desktop trip-new-save-btn, Mobil tn-mobile-save) haengt am
// Versand-Besuch, nicht am Alarme-Besuch — vor und nach dem Versand-Besuch.
function saveDisabled(over: TripNewStateOverride, mobile: boolean, testid: string): boolean {
	const html = renderTripNew({
		isMobileViewport: mobile, activeTab: 'route',
		name: 'X', startDate: '2026-07-01', stageNames: ['E1'], ...over,
	});
	const m = html.match(new RegExp(`<button[^>]*data-testid="${testid}"[^>]*>`));
	assert.ok(m, `Knopf ${testid} nicht gerendert — Wirkstelle nicht erreicht`);
	return /\sdisabled(=|\s|>)/.test(m![0]);
}

describe('AC-3: Speichern-Knopf vor und nach Versand-Besuch (TripNewEditor)', () => {
	const alarmeBesucht = { wtVisited: true, wbVisited: true, alVisited: true };
	for (const [mobile, testid] of [[false, 'trip-new-save-btn'], [true, 'tn-mobile-save']] as const) {
		test(`${testid}: Alarme besucht, Versand NICHT besucht => disabled`, () => {
			assert.equal(saveDisabled(alarmeBesucht, mobile, testid), true);
		});
		test(`${testid}: zusaetzlich Versand besucht => nicht disabled`, () => {
			assert.equal(saveDisabled({ ...alarmeBesucht, vsVisited: true }, mobile, testid), false);
		});
	}
});
