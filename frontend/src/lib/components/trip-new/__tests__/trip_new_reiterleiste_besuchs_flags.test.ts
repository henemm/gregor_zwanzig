// #2277 S4 (AC-2): Wirkstelle der Trip-Reiterleiste. Der echte TripNewEditor (SSR)
// reicht die Besuchs-Flags an die geteilte Lock-Engine durch; gelesen wird die
// gerenderte Reiterleiste (⊘ = gesperrt, ✓ = erledigt), nicht die Logik-Funktion.
// Wichtig ist der Fall "Besuchs-Flags gesetzt, Etappen ohne GPX (etDone false)":
// Verhalten wie vor dem Refactoring — der Schwanz-Schritt nach Wetter haengt NUR an
// den Besuchs-Flags, Wetter und Wegpunkte nur an etDone.
//
// Issue #1743 (feat_1743_reiter_aufraeumen, AC-19): der Reiter „Versand" entfaellt.
// Issue #2794 S3a (Spec feat_2794_s3a_teil2_leiste.md AC-6): die Leiste hat fuenf Reiter
// (Route · Etappen & GPX · Wegpunkte prüfen · Wetter · Zustellung); „Speichern" ist frei,
// sobald Zustellung besucht ist (nicht frueher).
//
// Ausfuehren (aus frontend/):
//   node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/trip-new/__tests__/trip_new_reiterleiste_besuchs_flags.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { renderTripNew, type TripNewStateOverride } from './tripNewSsr.ts';

const LABELS: Record<string, string> = {
	route: 'Route', etappen: 'Etappen &amp; GPX', wegpunkte: 'Wegpunkte prüfen',
	wetter: 'Wetter', zustellung: 'Zustellung',
};

/** Desktop-Reiterleiste: je Reiter { locked, done }. */
function bar(over: TripNewStateOverride) {
	const html = renderTripNew({
		isMobileViewport: false, activeTab: 'route',
		name: 'X', startDate: '2026-07-01', stageNames: ['E1'], ...over,
	});
	const tabs = [...html.matchAll(/<div[^>]*role="tab"[^>]*>([\s\S]*?)<\/div>/g)].map((m) => m[1]);
	assert.ok(tabs.length >= 5, 'Desktop-Reiterleiste nicht gefunden — Wirkstelle nicht erreicht');
	assert.ok(!tabs.some((t) => t.includes('Versand')), '#1743 AC-19 FAIL: Reiter „Versand" existiert noch.');
	assert.equal(tabs.length, 5, 'Desktop-Reiterleiste soll genau 5 Reiter haben (#2794)');
	const out: Record<string, { locked: boolean; done: boolean }> = {};
	for (const [id, label] of Object.entries(LABELS)) {
		// Bezeichnung als ganzes Wort (sonst trifft „Wetter" auch „Wetter-Metriken").
		const inner = tabs.find((t) => new RegExp(`(^|[^\\w-])${label}($|[^\\w-])`).test(t));
		assert.ok(inner, `Reiter ${id} fehlt`);
		out[id] = { locked: inner!.includes('⊘'), done: inner!.includes('✓') };
	}
	return out;
}
const lockedIds = (b: ReturnType<typeof bar>) => Object.keys(b).filter((k) => b[k].locked).sort();

describe('AC-2: Trip-Reiterleiste reicht die Besuchs-Flags durch (etDone = false)', () => {
	test('nichts besucht: ab Wegpunkte alles gesperrt', () => {
		assert.deepEqual(lockedIds(bar({})), ['wegpunkte', 'wetter', 'zustellung']);
	});
	test('nur Wetter-Flag: Zustellung frei', () => {
		assert.deepEqual(lockedIds(bar({ wtVisited: true })), ['wegpunkte', 'wetter']);
	});
	test('F001: Flags wt+zu gesetzt, etDone false => nur Wetter und Wegpunkte gesperrt (wie HEAD)', () => {
		const b = bar({ wtVisited: true, zuVisited: true });
		assert.deepEqual(lockedIds(b), ['wegpunkte', 'wetter']);
		assert.equal(b.zustellung.done, true);
		assert.equal(b.wetter.done, true);
	});
	test('Kette: zu-Flag allein oeffnet nichts (jede Stufe haengt nur am Vorgaenger-Flag)', () => {
		assert.deepEqual(lockedIds(bar({ zuVisited: true })), ['wegpunkte', 'wetter', 'zustellung']);
	});
});

// AC-3 / #2794 AC-6: Speichern-Knopf (Desktop trip-new-save-btn, Mobil tn-mobile-save) haengt am
// Zustellungs-Besuch — vor und nach dem Zustellungs-Besuch.
function saveDisabled(over: TripNewStateOverride, mobile: boolean, testid: string): boolean {
	// #2347 S4 (AN-9): tn-mobile-save steht erst im letzten Schritt im Footer. Die
	// Vorbelegung von activeTab ruft switchTab nicht auf ⇒ zuVisited kommt allein
	// aus `over`, die Zusicherung „haengt am letzten Besuch" bleibt unveraendert.
	const html = renderTripNew({
		isMobileViewport: mobile, activeTab: testid === 'tn-mobile-save' ? 'zustellung' : 'route',
		name: 'X', startDate: '2026-07-01', stageNames: ['E1'], ...over,
	});
	// #2837 S2: Pfad folgt dem Rahmen — Desktop-Speichern wird im Fuß tn-desktop-footer des
	// AnlegeRahmen gesucht, mobil im Fuß tn-mobile-footer. Die Zusicherung selbst bleibt wörtlich.
	const fuss = html.indexOf(`data-testid="${mobile ? 'tn-mobile-footer' : 'tn-desktop-footer'}"`);
	assert.notEqual(fuss, -1, `Fuß des Rahmens fehlt (${mobile ? 'tn-mobile-footer' : 'tn-desktop-footer'})`);
	const m = html.slice(fuss).match(new RegExp(`<button[^>]*data-testid="${testid}"[^>]*>`));
	assert.ok(m, `Knopf ${testid} nicht gerendert — Wirkstelle nicht erreicht`);
	return /\sdisabled(=|\s|>)/.test(m![0]);
}

describe('AC-3 / #2794 AC-6: Speichern-Knopf vor und nach Zustellungs-Besuch (TripNewEditor)', () => {
	for (const [mobile, testid] of [[false, 'trip-new-save-btn'], [true, 'tn-mobile-save']] as const) {
		test(`${testid}: Wetter besucht, Zustellung NICHT besucht => disabled`, () => {
			assert.equal(saveDisabled({ wtVisited: true }, mobile, testid), true);
		});
		test(`${testid}: Zustellung besucht => nicht disabled`, () => {
			assert.equal(saveDisabled({ wtVisited: true, zuVisited: true }, mobile, testid), false);
		});
	}
});
