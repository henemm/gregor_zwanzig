// TDD RED — Issue #678 (Epic #677): Compare-Editor Progressive-Lock-Engine
//
// Spec: docs/specs/modules/issue_678_compare_editor_shell.md  § Acceptance Criteria
//
// `compareEditorLogic.ts` existiert in der RED-Phase noch NICHT → der Import
// wirft einen Modul-Resolve-Fehler und alle Tests scheitern (RED).
//
// Reine Verhaltenstests (kein Mock, keine Dateiinhalt-Prüfung): sie treiben die
// Freischalt-/Erledigt-Logik mit echten Eingaben und prüfen das beobachtbare
// Ergebnis — exakt die Logik hinter AC-1 (Lock), AC-2 (Freischalt + ✓) und
// AC-3 (Fortschritt N/5).
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/compareEditorLogic.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { TAB_ORDER, unlockedTabs, doneTabs } from './compareEditorLogic.ts';

const empty = {
	name: '',
	pickedCount: 0,
	idealsVisited: false,
	layoutVisited: false,
	alarmeVisited: false,
	versandVisited: false
};

// Issue #1258 Scheibe S4 (AC-28): TAB_ORDER waechst um die reguläre Station
// "alarme" zwischen "layout" und "versand" — s. auch
// compare_wizard_alarme_station.test.ts (feingranulare AC-28-Nachweise).
describe('TAB_ORDER', () => {
	test('genau 6 Tabs in fester Reihenfolge', () => {
		assert.deepEqual(TAB_ORDER, [
			'vergleich',
			'orte',
			'idealwerte',
			'layout',
			'alarme',
			'versand'
		]);
	});
});

describe('AC-1/AC-2: unlockedTabs — Freischalt-Progression', () => {
	test('Leerzustand: nur "vergleich" offen, "orte" gesperrt', () => {
		const ul = unlockedTabs(empty);
		assert.ok(ul.has('vergleich'));
		assert.ok(!ul.has('orte'), '"orte" muss ohne Namen gesperrt sein');
		assert.ok(!ul.has('idealwerte'));
	});

	test('Name gesetzt → "orte" wird freigeschaltet', () => {
		const ul = unlockedTabs({ ...empty, name: 'Skitouren Hochkönig' });
		assert.ok(ul.has('orte'), 'Name ≠ leer schaltet "orte" frei');
		assert.ok(!ul.has('idealwerte'), '"idealwerte" bleibt ohne ≥2 Orte gesperrt');
	});

	test('Nur Whitespace zählt nicht als Name', () => {
		const ul = unlockedTabs({ ...empty, name: '   ' });
		assert.ok(!ul.has('orte'), 'Whitespace-Name schaltet nicht frei');
	});

	test('≥2 Orte → "idealwerte" frei; <2 bleibt gesperrt', () => {
		assert.ok(!unlockedTabs({ ...empty, name: 'X', pickedCount: 1 }).has('idealwerte'));
		assert.ok(unlockedTabs({ ...empty, name: 'X', pickedCount: 2 }).has('idealwerte'));
	});

	test('Besuch von Idealwerte/Layout schaltet Layout/Alarme frei, Versand erst nach Alarme', () => {
		const base = { ...empty, name: 'X', pickedCount: 2 };
		assert.ok(!unlockedTabs(base).has('layout'), 'Layout erst nach Idealwerte-Besuch');
		assert.ok(unlockedTabs({ ...base, idealsVisited: true }).has('layout'));
		assert.ok(
			!unlockedTabs({ ...base, idealsVisited: true }).has('alarme'),
			'Alarme erst nach Layout-Besuch'
		);
		assert.ok(
			unlockedTabs({ ...base, idealsVisited: true, layoutVisited: true }).has('alarme'),
			'Alarme nach Layout-Besuch offen (AC-28)'
		);
		assert.ok(
			!unlockedTabs({ ...base, idealsVisited: true, layoutVisited: true }).has('versand'),
			'Versand erst nach Alarme-Besuch (AC-28)'
		);
		assert.ok(
			unlockedTabs({
				...base,
				idealsVisited: true,
				layoutVisited: true,
				alarmeVisited: true
			}).has('versand')
		);
	});
});

describe('AC-2/AC-3: doneTabs — Erledigt-Kennzeichnung & Fortschritt', () => {
	test('Leerzustand: nichts erledigt (0/6)', () => {
		assert.equal(doneTabs(empty).size, 0);
	});

	test('Name gesetzt → "vergleich" erledigt (1/6)', () => {
		const done = doneTabs({ ...empty, name: 'Skitouren Hochkönig' });
		assert.ok(done.has('vergleich'));
		assert.equal(done.size, 1);
	});

	test('Voll konfiguriert → alle 6 erledigt', () => {
		const done = doneTabs({
			name: 'X',
			pickedCount: 3,
			idealsVisited: true,
			layoutVisited: true,
			alarmeVisited: true,
			versandVisited: true
		});
		assert.equal(done.size, 6);
		for (const t of TAB_ORDER) assert.ok(done.has(t), `${t} fehlt`);
	});
});
