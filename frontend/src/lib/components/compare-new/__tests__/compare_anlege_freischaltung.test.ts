// Epic #1301 Scheibe F2a / #2277 S4: Freischalt-Vertrag des Compare-Anlege-Flows.
//
// Vormals compareNewLogic.test.ts (Datei gelöscht, #2277 S4). Die Schwanz-Kette
// kommt jetzt aus dem geteilten Kern shared/anlegeLockEngine.ts; das Compare-
// Vorderteil (Name, ≥2 Orte) und der Zähler-Deckel 6 wohnen in CompareNewEditor.svelte.
// Die Hilfsfunktionen unten bilden genau diese Komposition ab (Kern + Vorderteil);
// die Wirkstelle selbst (echte Reiterleiste) prüft compare_new_lock_engine_wirkstelle.test.ts.
// Freischalt-Kette: Name → Orte≥2 → metriken → wertebereiche(idealwerte) → alarme → versand,
// mit Besuchs-Kaskade (einmal besucht bleibt besucht). Kein Mock.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare-new/__tests__/compare_anlege_freischaltung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import {
	tailUnlocked,
	tailDone,
	canFinish,
	progressCount as kernProgressCount,
	type TailIds,
} from '../../shared/anlegeLockEngine.ts';

type CompareNewTabId = 'vergleich' | 'orte' | 'metriken' | 'idealwerte' | 'alarme' | 'versand';
interface CompareNewProgress {
	name: string;
	pickedCount: number;
	metrikenVisited: boolean;
	idealsVisited: boolean;
	alarmeVisited: boolean;
	versandVisited: boolean;
}
const TAIL: TailIds<CompareNewTabId> = { metriken: 'metriken', wertebereiche: 'idealwerte', alarme: 'alarme', versand: 'versand' };
const STEPS: CompareNewTabId[] = ['vergleich', 'orte', 'metriken', 'idealwerte', 'alarme', 'versand'];

function tailP(p: CompareNewProgress) {
	return {
		metrikenFrei: !!p.name.trim() && p.pickedCount >= 2,
		metrikenVisited: p.metrikenVisited,
		wertebereicheVisited: p.idealsVisited,
		alarmeVisited: p.alarmeVisited,
		versandVisited: p.versandVisited,
	};
}
function unlockedTabs(p: CompareNewProgress): Set<CompareNewTabId> {
	const s = tailUnlocked(TAIL, tailP(p));
	s.add('vergleich');
	if (p.name.trim()) s.add('orte');
	return s;
}
function doneTabs(p: CompareNewProgress): Set<CompareNewTabId> {
	const s = tailDone(TAIL, tailP(p));
	if (p.name.trim()) s.add('vergleich');
	if (p.pickedCount >= 2) s.add('orte');
	return s;
}
function progressCount(done: Set<CompareNewTabId>): number {
	return Math.min(kernProgressCount(done, STEPS), 6);
}
const canActivate = (done: Set<CompareNewTabId>) => canFinish(done);

// ── Progress-Builder: leerer Start, gezielt Felder überschreiben ──────────────

function progress(over: Partial<CompareNewProgress> = {}): CompareNewProgress {
	return {
		name: '',
		pickedCount: 0,
		metrikenVisited: false,
		idealsVisited: false,
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

	test('AC-5: metrikenVisited → "idealwerte" frei, "alarme" bleibt gesperrt', () => {
		const u1 = unlockedTabs(progress({ name: 'X', pickedCount: 2, metrikenVisited: true }));
		assert.ok(u1.has('idealwerte'), 'idealwerte frei nach Metriken-Besuch');
		// Issue #1360: hier stand vormals der Layout-Reiter — er ist aufgeloest,
		// naechste Stufe ist direkt 'alarme'.
		assert.ok(!u1.has('alarme'), 'alarme noch gesperrt (Wertebereiche nicht besucht)');
	});

	test('AC-7/8: idealsVisited → "alarme" frei; alarmeVisited → "versand" frei', () => {
		const u1 = unlockedTabs(
			progress({
				name: 'X',
				pickedCount: 2,
				metrikenVisited: true,
				idealsVisited: true,
			})
		);
		assert.ok(u1.has('alarme'), 'alarme frei nach Wertebereiche-Besuch (#1360: Layout-Reiter aufgeloest)');
		assert.ok(!u1.has('versand'), 'versand noch gesperrt');
		const u2 = unlockedTabs(
			progress({
				name: 'X',
				pickedCount: 2,
				metrikenVisited: true,
				idealsVisited: true,
				alarmeVisited: true,
			})
		);
		assert.ok(u2.has('versand'), 'versand frei nach Alarme-Besuch');
	});

	test('Kaskade übersprungen: idealsVisited ohne Vorstufen schaltet "alarme" NICHT frei', () => {
		// Nur idealsVisited=true, aber ohne Name/Orte/metriken — der Tab selbst
		// darf ohne die kompletten Vorbedingungen nicht erreichbar sein.
		// Issue #1360: vormals layoutVisited (Reiter aufgeloest).
		const u = unlockedTabs(progress({ idealsVisited: true }));
		assert.ok(!u.has('alarme'), 'ohne Name/Orte/metriken kein alarme-Zugang');
		assert.deepEqual([...u].sort(), ['vergleich']);
	});

	test('Vollständige Kette: alle 6 Tabs offen (#1360: ohne Layout-Reiter)', () => {
		const u = unlockedTabs(
			progress({
				name: 'X',
				pickedCount: 3,
				metrikenVisited: true,
				idealsVisited: true,
				alarmeVisited: true,
				versandVisited: true,
			})
		);
		const expected: CompareNewTabId[] = [
			'alarme',
			'idealwerte',
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
				alarmeVisited: true,
				versandVisited: true,
			})
		);
		for (const id of ['metriken', 'idealwerte', 'alarme', 'versand'] as CompareNewTabId[]) {
			assert.ok(d.has(id), `${id} muss done sein`);
		}
	});
});

// ── progressCount (done.size, max 6 — Issue #1360) ───────────────────────────

describe('progressCount — Fortschrittszähler', () => {
	test('Leerzustand = 0', () => {
		assert.equal(progressCount(doneTabs(progress())), 0);
	});

	test('vollständige Kette = 6', () => {
		const d = doneTabs(
			progress({
				name: 'X',
				pickedCount: 2,
				metrikenVisited: true,
				idealsVisited: true,
				alarmeVisited: true,
				versandVisited: true,
			})
		);
		assert.equal(progressCount(d), 6);
	});

	test('deckelt bei 6, auch wenn ein Fremd-Set größer wäre', () => {
		const bloated = new Set<CompareNewTabId>([
			'vergleich',
			'orte',
			'metriken',
			'idealwerte',
			'alarme',
			'versand',
			'nochwas' as CompareNewTabId,
		]);
		assert.equal(progressCount(bloated), 6);
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
