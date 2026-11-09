// TDD RED — #2277 S4: geteilte Freischalt-Logik der Anlege-Seiten.
// Spec: docs/specs/modules/feat_2277_s4_anlege_lockengine.md (AC-1, AC-3, AC-4, AC-5, AC-7)
//
// Kern-API (hier festgelegt, Spec-Entscheidung 1+2: Schwanz-Kette, Tab-IDs als Parameter):
//   tailUnlocked(ids, p) / tailDone(ids, p) / canFinish(done, letzterId?) / progressCount(done, steps)
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

// Feature #2287: beide Anlege-Seiten fuehren dieselben Kennungen.
// Issue #1743 (AC-19): kein Versand-Schritt. Issue #2794 S3a (Spec feat_2794_s3a_teil2_leiste.md
// AC-6): die Schwanz-Kette ist Wetter → Zustellung, `canFinish` gilt fuer `zustellung`.
const TRIP = { metriken: 'wetter', zustellung: 'zustellung' } as const;
const COMPARE = { metriken: 'wetter', zustellung: 'zustellung' } as const;

function p(over: Partial<{ metrikenFrei: boolean; metrikenVisited: boolean; zustellungVisited: boolean }> = {}) {
	return { metrikenFrei: true, metrikenVisited: false, zustellungVisited: false, ...over };
}
const sorted = (s: Set<string>) => [...s].sort();

describe('AC-1: Schwanz-Kette Wetter → Zustellung (#2794)', () => {
	test('Vorderteil nicht erfüllt: gesamter Schwanz gesperrt', () => {
		assert.deepEqual(sorted(tailUnlocked(TRIP, p({ metrikenFrei: false, metrikenVisited: true, zustellungVisited: true }))), []);
	});
	test('Vorderteil erfüllt, nichts besucht: nur Wetter frei', () => {
		assert.deepEqual(sorted(tailUnlocked(TRIP, p())), ['wetter']);
	});
	test('Zustellung erst nach Besuch Wetter', () => {
		assert.ok(!tailUnlocked(TRIP, p()).has('zustellung'));
		assert.deepEqual(sorted(tailUnlocked(TRIP, p({ metrikenVisited: true }))), ['wetter', 'zustellung']);
	});
	test('nach Besuch Zustellung wird KEIN entfallener Reiter freigeschaltet (Kette endet bei Zustellung)', () => {
		const u = tailUnlocked(TRIP, p({ metrikenVisited: true, zustellungVisited: true })) as Set<string>;
		for (const alt of ['versand', 'wertebereiche', 'alarme', 'wetter-metriken']) {
			assert.ok(!u.has(alt), `${alt} noch Teil der Kette: ${sorted(u).join(',')}`);
		}
	});
	test('Compare-IDs: identisch zu Trip (Feature #2287), Kette identisch', () => {
		const u = tailUnlocked(COMPARE, p({ metrikenVisited: true, zustellungVisited: true }));
		assert.deepEqual(sorted(u), ['wetter', 'zustellung']);
	});
	test('Kette über alle 4 Besuchs-Kombinationen gegen die Referenzformel', () => {
		for (let m = 0; m < 4; m++) {
			const f = { metrikenFrei: true, metrikenVisited: !!(m & 1), zustellungVisited: !!(m & 2) };
			const u = tailUnlocked(TRIP, f) as Set<string>;
			assert.equal(u.has('wetter'), true);
			assert.equal(u.has('zustellung'), f.metrikenVisited);
			assert.equal(u.size, f.metrikenVisited ? 2 : 1);
		}
	});
});

describe('AC-7: erledigt = Besuchs-Flag, monoton und rein', () => {
	test('tailDone spiegelt exakt die Besuchs-Flags, unabhängig vom Vorderteil', () => {
		assert.deepEqual(sorted(tailDone(TRIP, p({ metrikenFrei: false }))), []);
		assert.deepEqual(sorted(tailDone(TRIP, p({ zustellungVisited: true }))), ['zustellung']);
		assert.deepEqual(sorted(tailDone(TRIP, p({ metrikenVisited: true, zustellungVisited: true }))), ['wetter', 'zustellung']);
	});
	test('Mehr Besuche nehmen nie etwas frei Gewordenes zurück (Monotonie)', () => {
		const a = tailUnlocked(TRIP, p({ metrikenVisited: true }));
		const b = tailUnlocked(TRIP, p({ metrikenVisited: true, zustellungVisited: true }));
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

describe('AC-3 / #2794 AC-6: canFinish — frei, sobald Zustellung besucht ist (nicht früher)', () => {
	test('Zustellung erledigt → frei', () => {
		assert.equal(canFinish(new Set(['route', 'etappen', 'wetter', 'zustellung'])), true);
		assert.equal(canFinish(new Set(['zustellung'])), true);
	});
	test('Wetter erledigt, Zustellung nicht → gesperrt', () => {
		assert.equal(canFinish(new Set(['route', 'etappen', 'wetter'])), false);
	});
	test('ein Besuch eines entfallenen Reiters (versand/alarme) schaltet nichts frei', () => {
		assert.equal(canFinish(new Set(['versand'])), false);
		assert.equal(canFinish(new Set(['alarme'])), false);
	});
});

describe('AC-4/AC-5: progressCount(done, steps)', () => {
	test('zählt nur die übergebenen Schritte (Fremd-Einträge zählen nicht)', () => {
		const steps = ['route', 'etappen', 'wetter', 'zustellung'];
		assert.equal(progressCount(new Set(['route', 'etappen', 'wetter', 'zustellung', 'wegpunkte', 'versand']), steps), 4);
		assert.equal(progressCount(new Set(['wegpunkte', 'versand']), steps), 0);
		assert.equal(progressCount(new Set(['route', 'zustellung']), steps), 2);
	});
	test('Compare (#2794): alle vier Reiter ⇒ 4, weniger ⇒ genau deren Anzahl', () => {
		const steps = ['vergleich', 'orte', 'wetter', 'zustellung'];
		assert.equal(progressCount(new Set(steps), steps), 4);
		assert.equal(progressCount(new Set(['vergleich', 'orte', 'wetter']), steps), 3);
		assert.equal(progressCount(new Set(), steps), 0);
	});
});
