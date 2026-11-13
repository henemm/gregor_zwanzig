// TDD RED — Issue #2837 Scheibe S1 (Epic #2345): Verdrahtung des geteilten Hub-Kopfs am
// AST (echter Svelte-5-Compiler, Prüfstand aktionsmodellAst.ts — Muster
// aktionsmodell_seiten_bindung.test.ts). Spec: docs/specs/modules/rework_2837_s1_hub_kopf.md
// Entscheidungen 1, 2, 3, 6; AC-1, AC-3, AC-7.
//
// Warum AST: Die Kernsuite hat kein DOM; bits-ui-Menüs und der `mobil`-Zustand der Seiten
// (matchMedia in onMount) sind unter svelte/server nicht erreichbar. Was sich deterministisch
// messen lässt, ist die BINDUNG: welche Datei welchen Knopf baut, mit welcher Variante, unter
// welcher Bedingung, und welche Symbole sie überhaupt einbindet. Das Rendern prüfen
// hub_kopf_baustein.test.ts / hub_kopf_seiten_paritaet.test.ts, das Klicken die E2E.
//
// RED HEUTE: HubKopf.svelte fehlt; beide Seiten bauen Senden und Kebab selbst (Trip: Btn
// accent + eigener Mobil-Knopf mit EllipsisVertical; Vergleich: Mobil-Knopf MoreHorizontal).
//
// Pfadregel #1409: relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/shared/hub-kopf/__tests__/hub_kopf_seiten_bindung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
	ladeSvelte,
	importe,
	komponenten,
	mitAttribut,
	attrKurz,
	bedingungen,
	collect,
	kurz,
	type Knoten
} from '../../__tests__/aktionsmodellAst.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(HERE, '../../../../..');
const KOMP = path.join(SRC, 'lib/components');
const HUBKOPF_DATEI = path.join(KOMP, 'shared/hub-kopf/HubKopf.svelte');
const KEBAB_DATEI = path.join(KOMP, 'molecules/SubscriptionKebab.svelte');
const SEITEN = {
	'Trip-Hub': path.join(SRC, 'routes/trips/[id]/+page.svelte'),
	'Compare-Hub': path.join(SRC, 'routes/compare/[id]/+page.svelte')
} as const;

function hubKopf(): Knoten {
	assert.ok(existsSync(HUBKOPF_DATEI), `HubKopf fehlt: ${path.relative(SRC, HUBKOPF_DATEI)}`);
	return ladeSvelte(HUBKOPF_DATEI);
}

/** Importquellen der Lucide-Kebab-Symbole (horizontal = `more-horizontal` bzw. `ellipsis`). */
const HORIZONTAL = /@lucide\/svelte\/icons\/(more-horizontal|ellipsis)$/;
const VERTIKAL = /@lucide\/svelte\/icons\/(more-vertical|ellipsis-vertical)$/;

describe('#2837 S1 Entscheidung 6 / AC-7 — Kebab-Symbol: nur vertikal, nur in SubscriptionKebab', () => {
	for (const [name, datei] of Object.entries(SEITEN)) {
		test(`${name}: bindet kein Kebab-Symbol mehr selbst ein (weder horizontal noch eigener Mobil-Knopf)`, () => {
			const q = importe(ladeSvelte(datei)).map((i) => i.quelle);
			assert.deepEqual(q.filter((x) => HORIZONTAL.test(x) || VERTIKAL.test(x)), [], `${name} importiert noch ein Kebab-Symbol`);
		});
		test(`${name}: baut weder „Senden" noch den Kebab selbst (beides liegt im geteilten HubKopf)`, () => {
			const ast = ladeSvelte(datei);
			assert.equal(mitAttribut(ast, 'data-testid', 'subscription-hub-send').length, 0, `${name}: eigener Senden-Knopf`);
			assert.equal(mitAttribut(ast, 'data-testid', 'subscription-kebab').length, 0, `${name}: eigener Kebab-Knopf`);
			assert.equal(komponenten(ast, 'SubscriptionKebab').length, 0, `${name}: bindet SubscriptionKebab selbst ein`);
		});
	}
	test('SubscriptionKebab: vertikales Symbol, kein horizontales', () => {
		const q = importe(ladeSvelte(KEBAB_DATEI)).map((i) => i.quelle);
		assert.ok(q.some((x) => VERTIKAL.test(x)), 'SubscriptionKebab importiert kein vertikales Symbol');
		assert.deepEqual(q.filter((x) => HORIZONTAL.test(x)), []);
	});
	test('HubKopf: kein horizontales Kebab-Symbol, bindet SubscriptionKebab mit actions/onSelect ein', () => {
		const ast = hubKopf();
		assert.deepEqual(importe(ast).map((i) => i.quelle).filter((x) => HORIZONTAL.test(x)), []);
		const k = komponenten(ast, 'SubscriptionKebab');
		assert.equal(k.length, 1, `HubKopf bindet SubscriptionKebab ${k.length}× ein (erwartet genau 1, mobil steckt im Kebab)`);
		assert.equal(attrKurz(k[0], 'actions'), 'actions');
		assert.equal(attrKurz(k[0], 'onSelect'), 'onSelect');
		assert.equal(attrKurz(k[0], 'mobil'), 'mobil');
		assert.equal(attrKurz(k[0], 'onSheetOpen'), 'onSheetOpen');
		assert.equal(attrKurz(k[0], 'data-testid'), '"subscription-kebab"');
	});
});

// #2980 AC-16 (ADR-0118): „Test schicken ▾" ist seit dem Fix-Loop Bildabgleich Btn accent
// (Fläche --g-accent-deep) statt primary/Ink; „Setup abschließen" bleibt primary (ADR-0110).
describe('#2837 S1 Entscheidungen 2/3 — Senden im HubKopf: Btn accent (#2980), Bindung an die Props', () => {
	test('genau ein Senden-Knopf: Btn variant="accent", onclick = onSend, disabled = sendDisabled', () => {
		const ast = hubKopf();
		const s = mitAttribut(ast, 'data-testid', 'subscription-hub-send');
		assert.equal(s.length, 1, `Senden ${s.length}× im HubKopf`);
		assert.equal(s[0].type, 'Component');
		assert.equal(s[0].name, 'Btn');
		assert.equal(attrKurz(s[0], 'variant'), '"accent"', 'Senden ist nicht Btn accent (Mutation a, #2980 AC-16)');
		assert.ok(['onSend', '() => onSend()', '() => onSend?.()'].includes(attrKurz(s[0], 'onclick') ?? ''), `onclick: ${attrKurz(s[0], 'onclick')}`);
		assert.equal(attrKurz(s[0], 'disabled'), 'sendDisabled');
	});
	test('Senden steht nur außerhalb des Setup-Modus; „Setup abschließen" (Btn primary) im Setup-Zweig', () => {
		const ast = hubKopf();
		const s = mitAttribut(ast, 'data-testid', 'subscription-hub-send')[0];
		assert.ok(s, 'Senden fehlt');
		assert.deepEqual(bedingungen(ast.fragment, s), ['!(sendMode === "setup")']);
		const setup = collect(ast.fragment, (n) => n.type === 'Component' && n.name === 'Btn').filter(
			(b) => JSON.stringify(bedingungen(ast.fragment, b)) === JSON.stringify(['sendMode === "setup"'])
		);
		assert.equal(setup.length, 1, 'kein (bzw. mehr als ein) Btn im Setup-Zweig');
		assert.equal(attrKurz(setup[0], 'variant'), '"primary"');
		// Setup führt zur Einrichtung (Prop onSetup), nie in den Sende-Dialog.
		assert.ok(['onSetup', '() => onSetup()', '() => onSetup?.()'].includes(attrKurz(setup[0], 'onclick') ?? ''), `Setup-onclick: ${attrKurz(setup[0], 'onclick')}`);
	});
	test('ein Markup: kein {#if} im Template verzweigt nach context', () => {
		const ast = hubKopf();
		const zweige = collect(ast.fragment, (n) => n.type === 'IfBlock' && /\bcontext\b/.test(kurz(n.test)));
		assert.deepEqual(zweige.map((n) => kurz(n.test)), []);
	});
});
