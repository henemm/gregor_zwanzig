// TDD RED — Epic #1301 Scheibe F2a: /compare/new als Progressive-Tab-Editor.
//
// Reine-Logik-Verträge für den Compare-Anlege-Flow, gespiegelt aus dem
// Trip-Vorbild `tripNewLogic.ts` (#622). Freischalt-Kette exakt nach der
// Tab-Struktur-Tabelle der Spec:
//   docs/specs/modules/feat_1301_f2a_compare_new_trip_pattern.md
//   § "Tab-Struktur (7 Tabs)" / § "compareNewLogic.ts — Signaturen" / AC-2..AC-9
//
// Kette: Name → Orte≥2 → metriken → wertebereiche(idealwerte) → layout →
//        alarme → versand — mit visited-Kaskade (einmal besucht bleibt besucht).
//
// Echte Verhaltens-Tests (kein Mock). VOR der Implementierung SCHEITERN sie
// (RED), weil `../compareNewLogic.ts` noch nicht existiert (Import-Fehler).
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare-new/__tests__/compareNewLogic.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import {
	unlockedTabs,
	doneTabs,
	progressCount,
	canActivate,
	type CompareNewProgress,
	type CompareNewTabId,
} from '../compareNewLogic.ts';

// ── Progress-Builder: leerer Start, gezielt Felder überschreiben ──────────────

function progress(over: Partial<CompareNewProgress> = {}): CompareNewProgress {
	return {
		name: '',
		pickedCount: 0,
		metrikenVisited: false,
		idealsVisited: false,
		layoutVisited: false,
		alarmeVisited: false,
		versandVisited: false,
		...over,
	};
}

// ── AC-2: Leerzustand — nur "vergleich" offen ────────────────────────────────

describe('AC-2: unlockedTabs — progressive Freischaltung', () => {
	test('Leerzustand: nur "vergleich" offen, 6 Tabs gesperrt', () => {
		const u = unlockedTabs(progress());
		assert.deepEqual([...u].sort(), ['vergleich']);
	});

	test('AC-3: Name gesetzt → "orte" schaltet frei, "metriken" bleibt gesperrt', () => {
		const u = unlockedTabs(progress({ name: 'Sardinien-Woche' }));
		assert.ok(u.has('orte'), 'orte muss frei sein');
		assert.ok(!u.has('metriken'), 'metriken noch gesperrt (Orte fehlen)');
	});

	test('Nur Whitespace als Name schaltet "orte" NICHT frei', () => {
		const u = unlockedTabs(progress({ name: '   ' }));
		assert.ok(!u.has('orte'), 'Whitespace-Name darf nicht freischalten');
		assert.deepEqual([...u].sort(), ['vergleich']);
	});

	test('AC-4: genau 1 Ort schaltet "metriken" NICHT frei', () => {
		const u = unlockedTabs(progress({ name: 'X', pickedCount: 1 }));
		assert.ok(!u.has('metriken'), '1 Ort reicht nicht (Minimum 2)');
	});

	test('AC-4: 2 Orte schalten "metriken" frei, "idealwerte" bleibt gesperrt', () => {
		const u = unlockedTabs(progress({ name: 'X', pickedCount: 2 }));
		assert.ok(u.has('metriken'), 'metriken frei ab 2 Orten');
		assert.ok(!u.has('idealwerte'), 'idealwerte noch gesperrt (Metriken nicht besucht)');
	});

	test('AC-5: metrikenVisited → "idealwerte" frei; AC-6: idealsVisited → "layout" frei', () => {
		const u1 = unlockedTabs(progress({ name: 'X', pickedCount: 2, metrikenVisited: true }));
		assert.ok(u1.has('idealwerte'), 'idealwerte frei nach Metriken-Besuch');
		assert.ok(!u1.has('layout'), 'layout noch gesperrt');
		const u2 = unlockedTabs(
			progress({ name: 'X', pickedCount: 2, metrikenVisited: true, idealsVisited: true })
		);
		assert.ok(u2.has('layout'), 'layout frei nach Wertebereiche-Besuch');
		assert.ok(!u2.has('alarme'), 'alarme noch gesperrt');
	});

	test('AC-7/8: layoutVisited → "alarme" frei; alarmeVisited → "versand" frei', () => {
		const u1 = unlockedTabs(
			progress({
				name: 'X',
				pickedCount: 2,
				metrikenVisited: true,
				idealsVisited: true,
				layoutVisited: true,
			})
		);
		assert.ok(u1.has('alarme'), 'alarme frei nach Layout-Besuch');
		assert.ok(!u1.has('versand'), 'versand noch gesperrt');
		const u2 = unlockedTabs(
			progress({
				name: 'X',
				pickedCount: 2,
				metrikenVisited: true,
				idealsVisited: true,
				layoutVisited: true,
				alarmeVisited: true,
			})
		);
		assert.ok(u2.has('versand'), 'versand frei nach Alarme-Besuch');
	});

	test('Kaskade übersprungen: layoutVisited ohne Vorstufen schaltet "alarme" NICHT frei', () => {
		// Nur layoutVisited=true, aber ohne Name/Orte/metriken/ideals — der Tab
		// selbst darf ohne die kompletten Vorbedingungen nicht erreichbar sein.
		const u = unlockedTabs(progress({ layoutVisited: true }));
		assert.ok(!u.has('alarme'), 'ohne Name/Orte/metriken/ideals kein alarme-Zugang');
		assert.deepEqual([...u].sort(), ['vergleich']);
	});

	test('Vollständige Kette: alle 7 Tabs offen', () => {
		const u = unlockedTabs(
			progress({
				name: 'X',
				pickedCount: 3,
				metrikenVisited: true,
				idealsVisited: true,
				layoutVisited: true,
				alarmeVisited: true,
				versandVisited: true,
			})
		);
		const expected: CompareNewTabId[] = [
			'alarme',
			'idealwerte',
			'layout',
			'metriken',
			'orte',
			'vergleich',
			'versand',
		];
		assert.deepEqual([...u].sort(), expected);
	});
});

// ── doneTabs ──────────────────────────────────────────────────────────────────

describe('doneTabs — Done-Zustand nach Spec-Tabelle', () => {
	test('Name → vergleich done; ≥2 Orte → orte done', () => {
		const d = doneTabs(progress({ name: 'X', pickedCount: 2 }));
		assert.ok(d.has('vergleich'));
		assert.ok(d.has('orte'));
		assert.ok(!d.has('metriken'), 'metriken erst nach Besuch done');
	});

	test('1 Ort → orte NICHT done', () => {
		const d = doneTabs(progress({ name: 'X', pickedCount: 1 }));
		assert.ok(d.has('vergleich'));
		assert.ok(!d.has('orte'), '1 Ort zählt nicht als erledigt');
	});

	test('visited-Flags markieren die jeweiligen Tabs als done', () => {
		const d = doneTabs(
			progress({
				name: 'X',
				pickedCount: 2,
				metrikenVisited: true,
				idealsVisited: true,
				layoutVisited: true,
				alarmeVisited: true,
				versandVisited: true,
			})
		);
		for (const id of ['metriken', 'idealwerte', 'layout', 'alarme', 'versand'] as CompareNewTabId[]) {
			assert.ok(d.has(id), `${id} muss done sein`);
		}
	});
});

// ── progressCount (done.size, max 7) ─────────────────────────────────────────

describe('progressCount — Fortschrittszähler', () => {
	test('Leerzustand = 0', () => {
		assert.equal(progressCount(doneTabs(progress())), 0);
	});

	test('vollständige Kette = 7', () => {
		const d = doneTabs(
			progress({
				name: 'X',
				pickedCount: 2,
				metrikenVisited: true,
				idealsVisited: true,
				layoutVisited: true,
				alarmeVisited: true,
				versandVisited: true,
			})
		);
		assert.equal(progressCount(d), 7);
	});

	test('deckelt bei 7, auch wenn ein Fremd-Set größer wäre', () => {
		const bloated = new Set<CompareNewTabId>([
			'vergleich',
			'orte',
			'metriken',
			'idealwerte',
			'layout',
			'alarme',
			'versand',
		]);
		assert.equal(progressCount(bloated), 7);
	});
});

// ── canActivate (AC-8/AC-9: erst nach Versand-Besuch) ────────────────────────

describe('canActivate — "Briefing aktivieren" erst nach Versand-Besuch', () => {
	test('Versand nicht besucht → false (Aktivieren-Button deaktiviert)', () => {
		const d = doneTabs(
			progress({
				name: 'X',
				pickedCount: 2,
				metrikenVisited: true,
				idealsVisited: true,
				layoutVisited: true,
				alarmeVisited: true,
				versandVisited: false,
			})
		);
		assert.equal(canActivate(d), false);
	});

	test('Versand besucht → true (Aktivieren freigegeben)', () => {
		const d = doneTabs(
			progress({
				name: 'X',
				pickedCount: 2,
				metrikenVisited: true,
				idealsVisited: true,
				layoutVisited: true,
				alarmeVisited: true,
				versandVisited: true,
			})
		);
		assert.equal(canActivate(d), true);
	});

	test('Leerzustand → false', () => {
		assert.equal(canActivate(doneTabs(progress())), false);
	});
});
