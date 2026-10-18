// Fix-Loop 1 — Issue #2278, F003/F005/F010/F012 (AC-3, AC-4, AC-15, AC-16).
// Die Ausloeser, ueber die jede Aktion den Nutzer erreicht (Kebab-Auswahl, Blatt-Zeile, Filter-Pille,
// Karten-Menueknopf) und der Weg Radiowahl -> onConfirm -> Request. Ein totes Ausloeseereignis legt
// jede Aktion lahm, ohne dass ein Modelltest rot wird. bits-ui rendert unter svelte/server nichts und
// die Kernsuite hat kein DOM: geprueft wird die BINDUNG am AST (exakter Ausdruck), siehe aktionsmodellAst.ts.
//
// Pfadregel #1409: relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/aktionsmodell_bausteine_ausloeser.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
	ladeSvelte,
	komponenten,
	collect,
	attrKurz,
	attrAusdruck,
	initialisierer,
	zweig,
	kurz
} from './aktionsmodellAst.ts';

const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../..');
const lade = (rel: string) => ladeSvelte(path.join(SRC, rel));
const knoepfe = (ast: any) => collect(ast.fragment, (n) => n.type === 'RegularElement' && n.name === 'button');

describe('F005: jeder Ausloeser ruft den Handler mit der richtigen Aktion', () => {
	test('Kebab: die Menue-Auswahl ruft onSelect(action.id)', () => {
		const items = collect(lade('lib/components/molecules/SubscriptionKebab.svelte').fragment, (n) => n.name === 'DropdownMenu.Item');
		assert.deepEqual(items.map((i) => attrKurz(i, 'onSelect')), ['() => onSelect?.(action.id)']);
	});
	test('Aktionsblatt: der Klick ruft onAction(action.id), danach onClose()', () => {
		const b = knoepfe(lade('lib/components/mobile/SubscriptionActionSheet.svelte'));
		assert.deepEqual(b.map((x) => attrKurz(x, 'onclick')), ['() => { onAction(action.id); onClose() }']);
	});
	test('Filter-Pille: der Klick ruft onSelect(f.value)', () => {
		const b = knoepfe(lade('lib/components/molecules/StatusFilterPills.svelte'));
		assert.deepEqual(b.map((x) => attrKurz(x, 'onclick')), ['() => onSelect(f.value)']);
	});
	test('Karte: der Menueknopf ruft onAction("menu"), das Kebab der breiten Karte reicht die Aktion durch', () => {
		const ast = lade('lib/components/organisms/SubscriptionCard.svelte');
		assert.deepEqual(knoepfe(ast).map((x) => attrKurz(x, 'onclick')), ['(e) => { e.stopPropagation(); onAction?.("menu") }']);
		assert.deepEqual(komponenten(ast, 'SubscriptionKebab').map((k) => attrKurz(k, 'onSelect')), ['(id) => onAction?.(id)']);
	});
});

describe('F003/F010: Radiowahl -> onConfirm -> Request', () => {
	const ast = lade('lib/components/molecules/SendConfirmDialog.svelte');
	const dialog = komponenten(ast, 'ConfirmDialog')[0];

	test('ConfirmDialog rendert seine Kinder (sonst gibt es keine Radios im Dialog)', () => {
		const rt = collect(lade('lib/components/molecules/ConfirmDialog.svelte').fragment, (n) => n.type === 'RenderTag');
		assert.deepEqual(rt.map(kurz), ['children?.()']);
	});
	test('die Radios stehen IM ConfirmDialog, iterieren die Wahl des Modells und setzen `auswahl`', () => {
		const eachs = collect(dialog.fragment, (n) => n.type === 'EachBlock').map((n) => kurz(n.expression));
		assert.deepEqual(eachs, ['modell.berichtsartWahl']);
		const inputs = collect(dialog.fragment, (n) => n.type === 'RegularElement' && n.name === 'input');
		assert.deepEqual(inputs.map((i) => [attrKurz(i, 'type'), attrKurz(i, 'checked'), attrKurz(i, 'onchange')]), [
			['"radio"', 'auswahl === w.value', '() => auswahl = w.value']
		]);
	});
	test('das Modell bekommt kind UND die Wahl; die Bestaetigung gibt die Berichtsart des Modells weiter', () => {
		assert.equal(kurz(initialisierer(ast, 'modell')), '$derived(sendConfirmModel(kind, profile, subscription, auswahl))');
		assert.equal(attrKurz(dialog, 'onConfirm'), '() => onConfirm(modell.berichtsart)');
	});
	test('F010: beim Oeffnen wird die Wahl auf "morning" zurueckgesetzt (liest nur `open`)', () => {
		const effekte = collect(ast.instance, (n) => n.type === 'CallExpression' && n.callee?.name === '$effect');
		assert.equal(effekte.length, 1);
		const ifs = collect(effekte[0], (n) => n.type === 'IfStatement').map(kurz);
		assert.deepEqual(ifs, ['if (open) auswahl = "morning"']);
	});
});

describe('F012/AC-15: Startseiten-Kachel', () => {
	const kachel = lade('routes/_home/CompareKachel.svelte');
	const karte = komponenten(kachel, 'SubscriptionCard')[0];

	test('die Startseite uebergibt der Kachel genau die Prop, die sie liest (sub)', () => {
		const home = komponenten(lade('routes/+page.svelte'), 'CompareKachel');
		assert.ok(home.length >= 1);
		const props = collect(kachel.instance, (n) => n.type === 'VariableDeclarator' && n.init?.callee?.name === '$props').flatMap((d) =>
			d.id.properties.map((p: any) => p.key.name)
		);
		for (const k of home) {
			assert.deepEqual(k.attributes.map((a: any) => a.name), props);
			assert.equal(attrKurz(k, 'sub'), 'preset');
		}
	});
	test('Klick und "Bearbeiten" navigieren auf den Hub des Vergleichs', () => {
		assert.equal(attrKurz(karte, 'onclick'), '() => goto("/compare/" + sub.id)');
		assert.deepEqual(zweig(attrAusdruck(karte, 'onAction'), 'id', 'edit'), ['goto("/compare/" + sub.id)']);
	});
});
