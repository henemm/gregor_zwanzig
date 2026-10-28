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
// frontend/e2e/hub-versand-speichert-selbst.spec.ts (#2347 S3b).
//
// RED HEUTE: `.hub-versand-wrap` existiert (CompareTabs.svelte:1148) und der
// Mount von `VersandTab` trägt die drei neuen Props nicht — echte
// Assertion-Fehler, kein fehlendes Modul.
//
// Pfadregel #1409: Prüflinge relativ zu DIESER Datei auflösen.
//
// #1743 (Spec feat_1743_reiter_aufraeumen §3, AC-7, AC-8): der Reiter „Versand" entfällt; der
// Versand-Inhalt steht im geteilten Baustein `shared/WetterMetrikenVersandPanel.svelte` in
// `<section id="versand" data-testid="versand-abschnitt">`. Die Pins ziehen dorthin um:
//   - Hub: das Panel `wetter-metriken` mountet GENAU EIN `WetterMetrikenVersandPanel`
//     (context="vergleich") mit den Selbstspeicher-Props und ohne Sammel-Wrapper.
//   - Baustein: `VersandTab` sitzt im Abschnitt `#versand`; kein Element dort trägt
//     onchange/onfocusout/onclick (Sammel-Wrapper).
//   - Anlege-Seite: mountet den Baustein ohne die Hub-Orchestrierungs-Props.
// Ein eigenes Hub-Panel `versand` darf es nicht mehr geben.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/compare/__tests__/versand_panel_ohne_wrapper_div.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

const here = dirname(fileURLToPath(import.meta.url));
const HUB = join(here, '..', 'CompareTabs.svelte');
const NEW_EDITOR = join(here, '..', '..', 'compare-new', 'CompareNewEditor.svelte');
const BRIEFING_TAB = join(here, '..', '..', 'trip-detail', 'BriefingScheduleTab.svelte');
const PANEL = join(here, '..', '..', 'shared', 'WetterMetrikenVersandPanel.svelte');

function ast(file: string): unknown {
	if (!existsSync(file)) {
		assert.fail(`#1743: ${file.split('/components/')[1]} existiert nicht — der geteilte Baustein „Wetter-Metriken + Versand" fehlt`);
	}
	return parse(readFileSync(file, 'utf-8'), { modern: true });
}

/** Erstes Element `<section id="versand">` im Baustein (Teilbaum), sonst null. */
function findVersandAbschnitt(node: unknown): any {
	let found: any = null;
	function visit(cur: unknown): void {
		if (found !== null || cur === null || typeof cur !== 'object') return;
		if (Array.isArray(cur)) {
			cur.forEach(visit);
			return;
		}
		const n = cur as Record<string, any>;
		if (n.type === 'RegularElement' && n.name === 'section') {
			const id = (n.attributes ?? []).find((a: any) => a.type === 'Attribute' && a.name === 'id');
			const wert = Array.isArray(id?.value) ? id.value.map((t: any) => t.data ?? '').join('') : undefined;
			if (wert === 'versand') {
				found = n;
				return;
			}
		}
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(node);
	return found;
}

/** Statischer Wert eines Attributs (nur reiner Text), sonst null. */
function statischerWert(component: any, name: string): string | null {
	const a = (component.attributes ?? []).find((x: any) => x.type === 'Attribute' && x.name === name);
	if (!a || !Array.isArray(a.value)) return null;
	return a.value.map((t: any) => (t.type === 'Text' ? t.data : '\u0000')).join('');
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

describe('AC-1 (#1743 umgezogen): der Versand-Abschnitt hat keinen Sammel-Wrapper', () => {
	test('#1743: der Hub hat kein eigenes Panel „versand" mehr', () => {
		assert.equal(findTabPanelFragment(ast(HUB), 'versand'), null, 'ein Hub-Panel activeTab === \'versand\' existiert noch');
	});

	test('Hub-Panel wetter-metriken: kein Element trägt onchange/onfocusout/onclick', () => {
		const panel = findTabPanelFragment(ast(HUB), 'wetter-metriken');
		assert.ok(panel, 'Vorbedingung: das Panel wetter-metriken muss im Hub-Markup auffindbar sein');
		const mitHandlern = findElementsWithHandlers(panel, ['onchange', 'onfocusout', 'onclick']);
		assert.deepEqual(
			mitHandlern.map((e) => e.name),
			[],
			'der Speicherweg läuft über saveController.schedule() im Baustein, nicht über einen Wrapper-Div mit Sammel-Ereignissen'
		);
	});

	test('Hub-Panel wetter-metriken mountet genau einen WetterMetrikenVersandPanel (context="vergleich") mit den Props der Selbst-Speicherung', () => {
		const panel = findTabPanelFragment(ast(HUB), 'wetter-metriken');
		const mounts = findComponents(panel, 'WetterMetrikenVersandPanel');
		assert.equal(mounts.length, 1, 'genau ein WetterMetrikenVersandPanel im Panel wetter-metriken erwartet');
		assert.equal(statischerWert(mounts[0], 'context'), 'vergleich', 'der Vergleichs-Hub mountet den Baustein mit context="vergleich"');
		const props = propNamen(mounts[0]);
		for (const pflicht of ['preset', 'saveController', 'enqueueHubWrite', 'onCompareUpdate']) {
			assert.ok(
				props.includes(pflicht),
				`ohne Prop „${pflicht}" bleibt die Aktivierungsbedingung der Orchestrierung falsch — der Abschnitt speichert nicht (übergeben: ${props.join(', ')})`
			);
		}
	});

	// #1743 AC-7: die Aktivierungs-Karte (Snippet `hubActivationCard` des Vergleichs-Hubs) wandert
	// mit in den Versand-Abschnitt. Der Prop-Name am Baustein ist frei; am VersandTab bleibt es
	// die bestehende Prop `activation`. Der Trip-Hub reicht keine Karte.
	test('AC-7: Vergleichs-Hub reicht die Aktivierungs-Karte (hubActivationCard) an den Baustein', () => {
		const panel = findTabPanelFragment(ast(HUB), 'wetter-metriken');
		const mounts = findComponents(panel, 'WetterMetrikenVersandPanel');
		assert.equal(mounts.length, 1, 'genau ein WetterMetrikenVersandPanel im Panel wetter-metriken erwartet');
		const quelle = readFileSync(HUB, 'utf-8');
		const ausdruecke = (mounts[0].attributes ?? [])
			.filter((a: any) => a.type === 'Attribute' && a.value?.type === 'ExpressionTag')
			.map((a: any) => quelle.slice(a.value.expression.start, a.value.expression.end));
		assert.ok(
			ausdruecke.some((x: string) => /\bhubActivationCard\b/.test(x)),
			`die Aktivierungs-Karte fehlt im Versand-Abschnitt des Vergleichs (Attribute: ${ausdruecke.join(', ')})`
		);
	});

	test('AC-7: Trip-Hub reicht dem Baustein KEINE Aktivierungs-Karte', () => {
		const TRIP_HUB = join(here, '..', '..', 'trip-detail', 'TripTabs.svelte');
		const quelle = readFileSync(TRIP_HUB, 'utf-8');
		const mounts = findComponents(ast(TRIP_HUB), 'WetterMetrikenVersandPanel');
		assert.equal(mounts.length, 1, 'Vorbedingung: der Trip-Hub mountet WetterMetrikenVersandPanel genau einmal');
		const ausdruecke = (mounts[0].attributes ?? [])
			.filter((a: any) => a.type === 'Attribute' && a.value?.type === 'ExpressionTag')
			.map((a: any) => quelle.slice(a.value.expression.start, a.value.expression.end));
		assert.ok(!ausdruecke.some((x: string) => /\bhubActivationCard\b/.test(x)), 'Aktivierungs-Karte im Trip-Hub');
	});

	test('AC-7: im Baustein bekommt der VersandTab im Abschnitt #versand die Prop activation', () => {
		const abschnitt = findVersandAbschnitt(ast(PANEL));
		assert.ok(abschnitt, 'WetterMetrikenVersandPanel hat keinen <section id="versand">');
		const versand = findComponents(abschnitt, 'VersandTab');
		assert.equal(versand.length, 1, 'genau ein VersandTab im Abschnitt #versand');
		assert.ok(propNamen(versand[0]).includes('activation'), 'VersandTab im Abschnitt bekommt die Aktivierungs-Karte nicht durchgereicht');
	});

	test('Baustein: VersandTab sitzt im Abschnitt <section id="versand">, dort ohne Sammel-Ereignisse', () => {
		const abschnitt = findVersandAbschnitt(ast(PANEL));
		assert.ok(abschnitt, 'WetterMetrikenVersandPanel hat keinen <section id="versand">');
		const testid = (abschnitt.attributes ?? []).find((a: any) => a.type === 'Attribute' && a.name === 'data-testid');
		assert.equal(
			Array.isArray(testid?.value) ? testid.value.map((t: any) => t.data ?? '').join('') : null,
			'versand-abschnitt',
			'der Abschnitt trägt data-testid="versand-abschnitt" (red-schnittstellen.md)'
		);
		assert.equal(findComponents(abschnitt, 'VersandTab').length, 1, 'genau ein VersandTab im Abschnitt #versand');
		assert.deepEqual(
			findElementsWithHandlers(abschnitt, ['onchange', 'onfocusout', 'onclick']).map((e) => e.name),
			[],
			'kein Sammel-Wrapper im Versand-Abschnitt'
		);
	});
});

describe('AC-9/AC-12: Anlege-Seite und Trip-Seite mounten VersandTab unverändert', () => {
	test('AC-9: CompareNewEditor übergibt dem Baustein weder preset noch saveController noch enqueueHubWrite', () => {
		// #1743: die Anlege-Seite mountet den geteilten Baustein statt VersandTab direkt.
		const mounts = findComponents(ast(NEW_EDITOR), 'WetterMetrikenVersandPanel');
		assert.ok(mounts.length > 0, 'Vorbedingung: die Anlege-Seite mountet WetterMetrikenVersandPanel');
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
