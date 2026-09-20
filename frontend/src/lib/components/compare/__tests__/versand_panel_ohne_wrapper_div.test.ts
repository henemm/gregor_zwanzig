// TDD RED — Issue #2276 Scheibe S5 (Epic #2345), AC-1 (struktureller Teil):
// das Versand-Panel des Ortsvergleich-Hubs trägt KEINEN Sammel-Wrapper mehr.
// Der Speichervorgang läuft über `saveController.schedule()` im Reiter selbst,
// nicht über `onchange`/`onfocusout`/`onclick` eines umschließenden Divs.
//
// Spec: docs/specs/modules/rework_2276_s5_versand.md — AC-1, AC-9, AC-12
//
// WARUM AST statt DOM-Mount (Muster compare_layout_tab_dissolution.test.ts):
// dieses Repo hat kein vitest/jsdom/@testing-library/svelte
// (`"test": "node --import ./test-lib-loader.mjs --experimental-strip-types
// --experimental-test-module-mocks --test"`). Statt eines Text-Greps über den
// Dateiinhalt (laut CLAUDE.md als Verhaltensnachweis verboten) parst dieser
// Test die Komponenten mit dem ECHTEN Svelte-5-Compiler und inspiziert den
// Template-AST — geprüft wird die Baumstruktur, nicht ein Zeichenketten-Treffer.
//
// Warum dieser Test SEPARAT zum PUT-Zähltest (AC-1, Nachweisschicht Kern):
// ein reiner „genau ein PUT"-Test bliebe auch dann grün, wenn der alte
// Wrapper zusätzlich stehen bliebe (der Diff-Wächter unterdrückt den zweiten
// PUT). Nur die Strukturprüfung unterscheidet „Wrapper weg" von
// „Wrapper wirkungslos".
//
// Der echte Klick-/Speicherpfad wird zusätzlich gegen Staging bewiesen:
// frontend/e2e/compare-versand-speichert-selbst.spec.ts.
//
// RED HEUTE: `.hub-versand-wrap` existiert (CompareTabs.svelte:1148) und der
// Mount von `VersandTab` trägt die drei neuen Props nicht — echte
// Assertion-Fehler, kein fehlendes Modul.
//
// Pfadregel #1409: Prüflinge relativ zu DIESER Datei auflösen.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/compare/__tests__/versand_panel_ohne_wrapper_div.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

const here = dirname(fileURLToPath(import.meta.url));
const HUB = join(here, '..', 'CompareTabs.svelte');
const NEW_EDITOR = join(here, '..', '..', 'compare-new', 'CompareNewEditor.svelte');
const BRIEFING_TAB = join(here, '..', '..', 'trip-detail', 'BriefingScheduleTab.svelte');

function ast(file: string): unknown {
	return parse(readFileSync(file, 'utf-8'), { modern: true });
}

/** Findet das IfBlock-Fragment für `activeTab === '<tabValue>'` und liefert
 *  dessen `consequent`-Fragment, sonst null. */
function findTabPanelFragment(node: unknown, tabValue: string): unknown {
	let found: unknown = null;
	function visit(cur: unknown): void {
		if (found !== null || cur === null || typeof cur !== 'object') return;
		if (Array.isArray(cur)) {
			cur.forEach(visit);
			return;
		}
		const n = cur as Record<string, any>;
		if (
			n.type === 'IfBlock' &&
			n.test?.type === 'BinaryExpression' &&
			n.test.operator === '===' &&
			n.test.left?.type === 'Identifier' &&
			n.test.left.name === 'activeTab' &&
			n.test.right?.value === tabValue
		) {
			found = n.consequent;
			return;
		}
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(node);
	return found;
}

function findComponents(subtree: unknown, componentName: string): any[] {
	const found: any[] = [];
	function visit(cur: unknown): void {
		if (cur === null || typeof cur !== 'object') return;
		if (Array.isArray(cur)) {
			cur.forEach(visit);
			return;
		}
		const n = cur as Record<string, any>;
		if (n.type === 'Component' && n.name === componentName) found.push(n);
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(subtree);
	return found;
}

/** Alle Elemente im Subtree, die mindestens einen der genannten
 *  Ereignis-Handler tragen (Svelte-5-Attribut-Schreibweise `onchange={…}`). */
function findElementsWithHandlers(subtree: unknown, handler: string[]): any[] {
	const found: any[] = [];
	function visit(cur: unknown): void {
		if (cur === null || typeof cur !== 'object') return;
		if (Array.isArray(cur)) {
			cur.forEach(visit);
			return;
		}
		const n = cur as Record<string, any>;
		if (n.type === 'RegularElement') {
			const treffer = (n.attributes ?? []).some(
				(a: any) => a.type === 'Attribute' && handler.includes(a.name)
			);
			if (treffer) found.push(n);
		}
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(subtree);
	return found;
}

/** Namen der an eine Komponenten-Instanz übergebenen Props. */
function propNamen(component: any): string[] {
	return (component.attributes ?? [])
		.filter((a: any) => a.type === 'Attribute' || a.type === 'BindDirective')
		.map((a: any) => a.name as string);
}

describe('AC-1: das Versand-Panel des Hubs hat keinen Sammel-Wrapper mehr', () => {
	test('kein Element im Versand-Panel trägt onchange/onfocusout/onclick', () => {
		const panel = findTabPanelFragment(ast(HUB), 'versand');
		assert.ok(panel, 'Vorbedingung: das Versand-Panel muss im Hub-Markup auffindbar sein');

		const mitHandlern = findElementsWithHandlers(panel, ['onchange', 'onfocusout', 'onclick']);
		assert.deepEqual(
			mitHandlern.map((e) => e.name),
			[],
			'der Speicherweg läuft über saveController.schedule() im Reiter, nicht über einen Wrapper-Div mit Sammel-Ereignissen'
		);
	});

	test('VersandTab wird mit den Props der Selbst-Speicherung gemountet', () => {
		const panel = findTabPanelFragment(ast(HUB), 'versand');
		const mounts = findComponents(panel, 'VersandTab');
		assert.equal(mounts.length, 1, 'genau ein VersandTab-Mount im Versand-Panel erwartet');

		const props = propNamen(mounts[0]);
		for (const pflicht of ['preset', 'saveController', 'enqueueHubWrite', 'onCompareUpdate']) {
			assert.ok(
				props.includes(pflicht),
				`ohne Prop „${pflicht}" bleibt die Aktivierungsbedingung der neuen Orchestrierung falsch — der Reiter speichert nicht (übergeben: ${props.join(', ')})`
			);
		}
	});
});

describe('AC-9/AC-12: Anlege-Seite und Trip-Seite mounten VersandTab unverändert', () => {
	test('AC-9: CompareNewEditor übergibt weder preset noch saveController noch enqueueHubWrite', () => {
		const mounts = findComponents(ast(NEW_EDITOR), 'VersandTab');
		assert.ok(mounts.length > 0, 'Vorbedingung: die Anlege-Seite mountet VersandTab');
		for (const mount of mounts) {
			const props = propNamen(mount);
			for (const verboten of ['preset', 'saveController', 'enqueueHubWrite', 'onCompareUpdate']) {
				assert.ok(
					!props.includes(verboten),
					`die Anlege-Seite darf „${verboten}" nicht übergeben — sonst löst sie einen PUT aus, statt über wiz.saveNewPreset() zu speichern`
				);
			}
		}
	});

	test('AC-12: BriefingScheduleTab mountet VersandTab weiterhin im route-Kontext mit bind:reportConfig', () => {
		const mounts = findComponents(ast(BRIEFING_TAB), 'VersandTab');
		assert.equal(mounts.length, 1, 'Vorbedingung: die Trip-Seite mountet VersandTab genau einmal');
		const props = propNamen(mounts[0]);
		assert.ok(props.includes('reportConfig'), 'der Trip-Zweig speichert weiterhin über den report_config-Blob');
		assert.ok(
			!props.includes('preset') && !props.includes('enqueueHubWrite'),
			'der Trip-Zweig darf die Vergleichs-Orchestrierung nicht verdrahten'
		);
	});
});
