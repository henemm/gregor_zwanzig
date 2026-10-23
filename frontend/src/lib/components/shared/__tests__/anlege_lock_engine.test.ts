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

// Feature #2287: beide Anlege-Seiten fuehren dieselben Kennungen (wetter-metriken, wertebereiche, alarme).
// Issue #1743 (Spec feat_1743_reiter_aufraeumen, Abschnitt 9, AC-19): der Schritt „Versand" entfaellt —
// TailIds ohne `versand`, die Kette endet bei Alarme, `canFinish` gilt fuer `alarme`.
const TRIP = { metriken: 'wetter-metriken', wertebereiche: 'wertebereiche', alarme: 'alarme' } as const;
const COMPARE = { metriken: 'wetter-metriken', wertebereiche: 'wertebereiche', alarme: 'alarme' } as const;

function p(over: Partial<{ metrikenFrei: boolean; metrikenVisited: boolean; wertebereicheVisited: boolean; alarmeVisited: boolean }> = {}) {
	return { metrikenFrei: true, metrikenVisited: false, wertebereicheVisited: false, alarmeVisited: false, ...over };
}
const sorted = (s: Set<string>) => [...s].sort();

describe('AC-1: Schwanz-Kette Metriken → Wertebereiche → Alarme (#1743: kein Versand-Schritt)', () => {
	test('Vorderteil nicht erfüllt: gesamter Schwanz gesperrt', () => {
		assert.deepEqual(sorted(tailUnlocked(TRIP, p({ metrikenFrei: false, metrikenVisited: true, wertebereicheVisited: true, alarmeVisited: true }))), []);
	});
	test('Vorderteil erfüllt, nichts besucht: nur Metriken frei', () => {
		assert.deepEqual(sorted(tailUnlocked(TRIP, p())), ['wetter-metriken']);
	});
	test('Wertebereiche erst nach Besuch Metriken', () => {
		assert.deepEqual(sorted(tailUnlocked(TRIP, p({ metrikenVisited: true }))), ['wertebereiche', 'wetter-metriken']);
	});
	test('Alarme erst nach Besuch Wertebereiche (nicht schon nach Metriken)', () => {
		const u = tailUnlocked(TRIP, p({ metrikenVisited: true }));
		assert.ok(!u.has('alarme'));
		assert.ok(tailUnlocked(TRIP, p({ metrikenVisited: true, wertebereicheVisited: true })).has('alarme'));
	});
	test('#1743: nach Besuch Alarme wird KEIN Versand-Reiter freigeschaltet (Kette endet bei Alarme)', () => {
		const u = tailUnlocked(TRIP, p({ metrikenVisited: true, wertebereicheVisited: true, alarmeVisited: true })) as Set<string>;
		assert.ok(!u.has('versand'), `versand noch Teil der Kette: ${sorted(u).join(',')}`);
	});
	test('Compare-IDs: identisch zu Trip (Feature #2287), Kette identisch', () => {
		const u = tailUnlocked(COMPARE, p({ metrikenVisited: true, wertebereicheVisited: true, alarmeVisited: true }));
		assert.deepEqual(sorted(u), ['alarme', 'wertebereiche', 'wetter-metriken']);
	});
	test('Kette über alle 8 Besuchs-Kombinationen gegen die Referenzformel', () => {
		for (let m = 0; m < 8; m++) {
			const f = { metrikenFrei: true, metrikenVisited: !!(m & 1), wertebereicheVisited: !!(m & 2), alarmeVisited: !!(m & 4) };
			const u = tailUnlocked(TRIP, f) as Set<string>;
			assert.equal(u.has('wetter-metriken'), true);
			assert.equal(u.has('wertebereiche'), f.metrikenVisited);
			assert.equal(u.has('alarme'), f.wertebereicheVisited);
			assert.equal(u.has('versand'), false);
		}
	});
});

describe('AC-7: erledigt = Besuchs-Flag, monoton und rein', () => {
	test('tailDone spiegelt exakt die Besuchs-Flags, unabhängig vom Vorderteil', () => {
		assert.deepEqual(sorted(tailDone(TRIP, p({ metrikenFrei: false }))), []);
		assert.deepEqual(sorted(tailDone(TRIP, p({ metrikenVisited: true, alarmeVisited: true }))), ['alarme', 'wetter-metriken']);
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

describe('AC-3 / #1743 AC-19: canFinish — frei, sobald Alarme besucht ist (nicht früher)', () => {
	test('Alarme erledigt → frei (ohne Versand)', () => {
		assert.equal(canFinish(new Set(['route', 'etappen', 'wetter-metriken', 'wertebereiche', 'alarme'])), true);
		assert.equal(canFinish(new Set(['alarme'])), true);
	});
	test('Wertebereiche erledigt, Alarme nicht → gesperrt', () => {
		assert.equal(canFinish(new Set(['route', 'etappen', 'wetter-metriken', 'wertebereiche'])), false);
	});
	test('ein Versand-Besuch allein schaltet nichts frei', () => {
		assert.equal(canFinish(new Set(['versand'])), false);
	});
});

describe('AC-4/AC-5: progressCount(done, steps)', () => {
	test('zählt nur die übergebenen Schritte (Fremd-Einträge zählen nicht)', () => {
		const steps = ['route', 'etappen', 'wetter-metriken', 'alarme'];
		assert.equal(progressCount(new Set(['route', 'etappen', 'wetter-metriken', 'wertebereiche', 'alarme', 'versand']), steps), 4);
		assert.equal(progressCount(new Set(['wertebereiche', 'versand']), steps), 0);
		assert.equal(progressCount(new Set(['route', 'alarme']), steps), 2);
	});
	test('Compare (#1743): alle fünf Reiter ⇒ 5, weniger ⇒ genau deren Anzahl', () => {
		const steps = ['vergleich', 'orte', 'wetter-metriken', 'wertebereiche', 'alarme'];
		assert.equal(progressCount(new Set(steps), steps), 5);
		assert.equal(progressCount(new Set(['vergleich', 'orte', 'wetter-metriken']), steps), 3);
		assert.equal(progressCount(new Set(), steps), 0);
	});
});
