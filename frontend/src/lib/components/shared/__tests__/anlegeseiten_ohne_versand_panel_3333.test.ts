// doc-compliance-test
// Strukturwächter (kein Verhaltensnachweis) — Issue #3333 (Teil D2 von #3307, Epic #3122), Spec
// docs/specs/modules/feat_3333_zustellung_anlegen_orte.md, Test Plan Nr. 9 (AC-13):
// „Anlegeseiten ohne WetterMetrikenVersandPanel“. Keine der beiden Anlegeseiten (TripNewEditor,
// CompareNewEditor) importiert oder mountet das Alt-Panel; die Panel-Datei selbst bleibt bis zum Rückbau
// (#3020, #3036) bestehen. Das Verhalten (Reiter Zustellung statt Alt-Panel) belegen die SSR- und
// Verdrahtungstests (AC-1); dieser Wächter verhindert nur, dass ein späterer Umbau das Panel unbemerkt
// wieder einbettet. Muster: *_laedt_keine_compare_klebeschicht.test.ts.
//
// Gemessen am Svelte-AST (svelte/compiler `parse`): Import-Deklarationen des Instanz-Skripts und
// Komponenten-Einbettungen im Markup — kein Zeichenketten-Grep (Kommentare zählen nicht).
//
//   cd frontend && npm test -- src/lib/components/shared/__tests__/anlegeseiten_ohne_versand_panel_3333.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';
import { findeKomponenten, type Knoten } from './svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const COMPONENTS = resolve(HIER, '..', '..');
const PANEL = join(COMPONENTS, 'shared', 'WetterMetrikenVersandPanel.svelte');
const ANLEGESEITEN: Record<string, string> = {
	TripNewEditor: join(COMPONENTS, 'trip-new', 'TripNewEditor.svelte'),
	CompareNewEditor: join(COMPONENTS, 'compare-new', 'CompareNewEditor.svelte')
};

function importQuellen(ast: Knoten): string[] {
	const body = (ast.instance?.content?.body ?? []) as Knoten[];
	return body.filter((s) => s.type === 'ImportDeclaration').map((s) => String(s.source.value));
}

describe('#3333 AC-13: Anlegeseiten ohne WetterMetrikenVersandPanel (Strukturwächter)', () => {
	test('Vakuum-Schutz: die Panel-Datei besteht bis zum Rückbau (#3020, #3036)', () => {
		assert.ok(existsSync(PANEL), `${PANEL} fehlt — Rückbau gehört zu #3020/#3036, nicht zu #3333`);
	});

	for (const [name, datei] of Object.entries(ANLEGESEITEN)) {
		test(`${name} importiert das Alt-Panel nicht`, () => {
			const ast = parse(readFileSync(datei, 'utf-8'), { modern: true }) as Knoten;
			assert.ok(importQuellen(ast).length > 0, `Messaufbau: keine Importe in ${name} gefunden`);
			const treffer = importQuellen(ast).filter((q) => /WetterMetrikenVersandPanel(\.svelte)?$/.test(q));
			assert.deepEqual(treffer, [], `${name} importiert das Alt-Panel`);
		});

		test(`${name} mountet das Alt-Panel nicht`, () => {
			const ast = parse(readFileSync(datei, 'utf-8'), { modern: true }) as Knoten;
			assert.ok(findeKomponenten(ast, 'ZustellungTab').length >= 1, `Messaufbau: ${name} bettet den Reiter Zustellung nicht ein`);
			assert.equal(findeKomponenten(ast, 'WetterMetrikenVersandPanel').length, 0, `${name} bettet das Alt-Panel ein`);
		});
	}
});
