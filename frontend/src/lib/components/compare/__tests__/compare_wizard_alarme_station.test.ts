// TDD RED — Issue #1258 Scheibe S4: Compare-Editor-Integration —
// Create-Wizard-Station "Alarme" (AC-28).
//
// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md
//   (AC-28, Abschnitt 10 "S4-Detail-Festlegungen")
// Context: docs/context/feat-1258-s4-compare-editor.md (E1/E2)
//
// ZIELBILD (noch nicht implementiert — RED bis Phase 6):
//   TAB_ORDER wird um die reguläre Station "alarme" erweitert:
//     vergleich → orte → idealwerte → layout → alarme → versand
//   Progress-Modell bekommt `alarmeVisited`; die letzte Freischalt-Kante
//   wird ersetzt: layoutVisited schaltet NICHT mehr direkt "versand" frei,
//   sondern "alarme" — "versand" erst nach alarmeVisited.
//
// Heutiger IST-Stand (compareEditorLogic.ts): TAB_ORDER hat nur 5 Einträge
// (kein "alarme"), unlockedTabs() schaltet "versand" bereits bei
// layoutVisited=true frei — beides widerspricht dem Zielbild unten und
// muss daher rot sein.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_wizard_alarme_station.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { TAB_ORDER, unlockedTabs, doneTabs } from '../compareEditorLogic.ts';

const empty = {
	name: '',
	pickedCount: 0,
	idealsVisited: false,
	layoutVisited: false,
	alarmeVisited: false,
	versandVisited: false
};

describe('#1258 AC-28: TAB_ORDER enthält die reguläre Station "alarme"', () => {
	test('genau 6 Tabs, "alarme" zwischen "layout" und "versand"', () => {
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

describe('#1258 AC-28: Freischalt-Kette — alarme vor versand', () => {
	test('layoutVisited schaltet "alarme" frei, aber "versand" bleibt bis alarmeVisited gesperrt', () => {
		const afterLayout = {
			...empty,
			name: 'X',
			pickedCount: 2,
			idealsVisited: true,
			layoutVisited: true
		};
		const ulAfterLayout = unlockedTabs(afterLayout);
		assert.ok(ulAfterLayout.has('alarme'), '"alarme" muss nach Layout-Besuch offen sein');
		assert.ok(
			!ulAfterLayout.has('versand'),
			'"versand" darf ohne Alarme-Besuch NICHT freigeschaltet sein (heutiges Verhalten schaltet fälschlich direkt frei)'
		);

		const afterAlarme = { ...afterLayout, alarmeVisited: true };
		const ulAfterAlarme = unlockedTabs(afterAlarme);
		assert.ok(ulAfterAlarme.has('versand'), '"versand" muss nach Alarme-Besuch offen sein');
	});
});

describe('#1258 AC-28: doneTabs/Fortschritt zählt sechs Stationen', () => {
	test('voll konfiguriert (inkl. alarmeVisited) → alle 6 Stationen erledigt', () => {
		const done = doneTabs({
			name: 'X',
			pickedCount: 3,
			idealsVisited: true,
			layoutVisited: true,
			alarmeVisited: true,
			versandVisited: true
		});
		assert.equal(done.size, 6, 'Fortschrittsanzeige muss sechs Stationen zählen (AC-28)');
		for (const t of TAB_ORDER) assert.ok(done.has(t), `${t} fehlt in doneTabs`);
	});
});
