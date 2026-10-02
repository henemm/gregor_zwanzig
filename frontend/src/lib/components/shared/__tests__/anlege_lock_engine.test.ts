// TDD RED — #2277 S4: geteilte Freischalt-Logik der Anlege-Seiten.
// Spec: docs/specs/modules/feat_2277_s4_anlege_lockengine.md (AC-1, AC-3, AC-4, AC-5, AC-7)
//
// Kern-API (hier festgelegt, Spec-Entscheidung 1+2: Schwanz-Kette, Tab-IDs als Parameter):
//   tailUnlocked(ids, p) / tailDone(ids, p) / canFinish(done, versandId?) / progressCount(done, steps)
// Prüfling wird relativ zur eigenen Testdatei aufgelöst (kein fester Hauptrepo-Pfad).
//
// Ausführung (aus frontend/):
//   node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/anlege_lock_engine.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import {
	tailUnlocked,
	tailDone,
	canFinish,
	progressCount,
} from '../anlegeLockEngine.ts';

const TRIP = { metriken: 'metriken', wertebereiche: 'wertebereiche', alarme: 'alarme', versand: 'versand' } as const;
const COMPARE = { metriken: 'metriken', wertebereiche: 'idealwerte', alarme: 'alarme', versand: 'versand' } as const;

function p(over: Partial<{ metrikenFrei: boolean; metrikenVisited: boolean; wertebereicheVisited: boolean; alarmeVisited: boolean; versandVisited: boolean }> = {}) {
	return { metrikenFrei: true, metrikenVisited: false, wertebereicheVisited: false, alarmeVisited: false, versandVisited: false, ...over };
}
const sorted = (s: Set<string>) => [...s].sort();

describe('AC-1: Schwanz-Kette Metriken → Wertebereiche → Alarme → Versand', () => {
	test('Vorderteil nicht erfüllt: gesamter Schwanz gesperrt', () => {
		assert.deepEqual(sorted(tailUnlocked(TRIP, p({ metrikenFrei: false, metrikenVisited: true, wertebereicheVisited: true, alarmeVisited: true }))), []);
	});
	test('Vorderteil erfüllt, nichts besucht: nur Metriken frei', () => {
		assert.deepEqual(sorted(tailUnlocked(TRIP, p())), ['metriken']);
	});
	test('Wertebereiche erst nach Besuch Metriken', () => {
		assert.deepEqual(sorted(tailUnlocked(TRIP, p({ metrikenVisited: true }))), ['metriken', 'wertebereiche']);
	});
	test('Alarme erst nach Besuch Wertebereiche (nicht schon nach Metriken)', () => {
		const u = tailUnlocked(TRIP, p({ metrikenVisited: true }));
		assert.ok(!u.has('alarme'));
		assert.ok(tailUnlocked(TRIP, p({ metrikenVisited: true, wertebereicheVisited: true })).has('alarme'));
	});
	test('Versand erst nach Besuch Alarme (nicht schon nach Wertebereiche)', () => {
		const u = tailUnlocked(TRIP, p({ metrikenVisited: true, wertebereicheVisited: true }));
		assert.ok(!u.has('versand'));
		assert.ok(tailUnlocked(TRIP, p({ metrikenVisited: true, wertebereicheVisited: true, alarmeVisited: true })).has('versand'));
	});
	test('Compare-IDs: Wertebereiche heißen idealwerte, Kette identisch', () => {
		const u = tailUnlocked(COMPARE, p({ metrikenVisited: true, wertebereicheVisited: true, alarmeVisited: true }));
		assert.deepEqual(sorted(u), ['alarme', 'idealwerte', 'metriken', 'versand']);
	});
	test('Kette über alle 16 Besuchs-Kombinationen gegen die Referenzformel', () => {
		for (let m = 0; m < 16; m++) {
			const f = { metrikenFrei: true, metrikenVisited: !!(m & 1), wertebereicheVisited: !!(m & 2), alarmeVisited: !!(m & 4), versandVisited: !!(m & 8) };
			const u = tailUnlocked(TRIP, f);
			assert.equal(u.has('metriken'), true);
			assert.equal(u.has('wertebereiche'), f.metrikenVisited);
			assert.equal(u.has('alarme'), f.wertebereicheVisited);
			assert.equal(u.has('versand'), f.alarmeVisited);
		}
	});
});

describe('AC-7: erledigt = Besuchs-Flag, monoton und rein', () => {
	test('tailDone spiegelt exakt die Besuchs-Flags, unabhängig vom Vorderteil', () => {
		assert.deepEqual(sorted(tailDone(TRIP, p({ metrikenFrei: false }))), []);
		assert.deepEqual(sorted(tailDone(TRIP, p({ metrikenVisited: true, alarmeVisited: true }))), ['alarme', 'metriken']);
	});
	test('Mehr Besuche nehmen nie etwas frei Gewordenes zurück (Monotonie)', () => {
		const a = tailUnlocked(TRIP, p({ metrikenVisited: true, wertebereicheVisited: true }));
		const b = tailUnlocked(TRIP, p({ metrikenVisited: true, wertebereicheVisited: true, alarmeVisited: true }));
		for (const id of a) assert.ok(b.has(id), `${id} fiel bei weiterem Besuch weg`);
	});
	test('Aufruf verändert die Eingabe nicht und liefert frische Mengen', () => {
		const input = p({ metrikenVisited: true });
		const copy = { ...input };
		const u1 = tailUnlocked(TRIP, input);
		u1.add('zzz');
		assert.deepEqual(input, copy);
		assert.ok(!tailUnlocked(TRIP, input).has('zzz'));
	});
});

describe('AC-3: canFinish', () => {
	test('erst mit Versand erledigt', () => {
		assert.equal(canFinish(new Set(['route', 'etappen', 'metriken', 'wertebereiche', 'alarme'])), false);
		assert.equal(canFinish(new Set(['versand'])), true);
	});
	test('Alarme allein genügt nicht', () => {
		assert.equal(canFinish(new Set(['alarme'])), false);
	});
});

describe('AC-4/AC-5: progressCount(done, steps)', () => {
	test('Trip-Schritte: Wertebereiche und Alarme zählen nicht mit, Maximum 4', () => {
		const steps = ['route', 'etappen', 'metriken', 'versand'];
		assert.equal(progressCount(new Set(['route', 'etappen', 'metriken', 'wertebereiche', 'alarme', 'versand']), steps), 4);
		assert.equal(progressCount(new Set(['wertebereiche', 'alarme']), steps), 0);
		assert.equal(progressCount(new Set(['route', 'versand']), steps), 2);
	});
	test('Compare: alle sechs Reiter ⇒ 6, weniger ⇒ genau deren Anzahl', () => {
		const steps = ['vergleich', 'orte', 'metriken', 'idealwerte', 'alarme', 'versand'];
		assert.equal(progressCount(new Set(steps), steps), 6);
		assert.equal(progressCount(new Set(['vergleich', 'orte', 'metriken']), steps), 3);
		assert.equal(progressCount(new Set(), steps), 0);
	});
});
