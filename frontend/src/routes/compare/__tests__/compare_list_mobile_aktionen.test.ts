// TDD RED — Issue #2278 (Epic #2345 P3), AC-2, AC-3 (Compare-Liste), AC-14, AC-16 (Compare-Liste).
// Spec: docs/specs/modules/feat_2278_aktionsmodell.md — Implementation Details 1, 5, 7; Known Limitations 5.
//
// LOEST AB: die Entscheidung "Compare-Mobil-Liste nur Link" (#1256 S8 AC-21; Kommentar in
// routes/compare/+page.svelte). Ersatz laut Spec: dieselbe mobile Karte, dasselbe Aktionsblatt und
// dieselben Filter-Pillen wie beim Trip (Paritaetsvorgabe Epic #2345, DoD-3).
//
// Pruefstand: AST (echter Svelte-Compiler) + Aufrufgraph des Instanz-Skripts (aktionsmodellAst.ts);
// kein DOM in der Kernsuite. Durchklicken: Playwright `aktionsmodell-durchklick.spec.ts` (Mobil-Viewport).
// Das bestehende compare_list_mobile_chrome.test.ts (Link-only) wird in /50 abgeloest.
//
// RED heute: mobile Liste = <a href>-Kacheln ohne Aktionen/Filter; Aktionen aus compareActions().
//
// Pfadregel #1409: relativ zu DIESER Datei.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/compare/__tests__/compare_list_mobile_aktionen.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
	ladeSvelte,
	komponenten,
	attribut,
	erreichbar,
	ids,
	collect,
	importe
} from '../../../lib/components/shared/__tests__/aktionsmodellAst.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ast = ladeSvelte(path.join(HERE, '..', '+page.svelte'));
const wert = (a: any) => (a ? (Array.isArray(a.value) ? a.value : [a.value]) : []);

describe('AC-2: mobile Vergleichs-Liste hat Karte, Aktionsblatt und Filter-Pillen', () => {
	test('SubscriptionCard (kind="vergleich"), SubscriptionActionSheet und StatusFilterPills sind eingebunden', () => {
		const karten = komponenten(ast, 'SubscriptionCard');
		assert.ok(karten.length >= 1, '<SubscriptionCard> fehlt — mobile Liste zeigt noch die Link-only-Kachel');
		assert.equal(komponenten(ast, 'SubscriptionActionSheet').length, 1, '<SubscriptionActionSheet> fehlt');
		assert.equal(komponenten(ast, 'StatusFilterPills').length, 1, '<StatusFilterPills> fehlt (Alle/Aktiv/Geplant/Pausiert/Fertig)');
	});

	test('keine <a href>-Huelle um die mobile Karte mehr (Link-only abgeloest)', () => {
		const huellen = collect(
			ast.fragment,
			(n) =>
				n.type === 'RegularElement' &&
				n.name === 'a' &&
				komponenten(n, 'SubscriptionCard').length + komponenten(n, 'CompareTile').length > 0
		);
		assert.equal(huellen.length, 0, 'Karte steckt noch in einem <a>-Link ohne Aktionen');
		assert.equal(komponenten(ast, 'CompareTile').length, 0, 'CompareTile (Alt-Karte) wird noch benutzt');
	});

	test('Menue einer Karte oeffnet das Blatt; Kind = vergleich', () => {
		const karte = komponenten(ast, 'SubscriptionCard')[0];
		assert.ok(karte, '<SubscriptionCard> fehlt');
		const kind = attribut(karte, 'kind');
		assert.ok(kind, '<SubscriptionCard kind=…> fehlt');
		const sheet = komponenten(ast, 'SubscriptionActionSheet')[0];
		assert.ok(sheet, '<SubscriptionActionSheet> fehlt');
		const sheetOffen = ids(wert(attribut(sheet, 'open')));
		const vomMenue = erreichbar(ast, wert(attribut(karte, 'onAction')));
		assert.ok([...sheetOffen].some((n) => vomMenue.bezeichner.has(n)), 'Karten-Menue erreicht das Aktionsblatt nicht');
	});
});

describe('AC-16 (Compare-Liste): jede Aktion der Tabelle erreicht eine Wirkung', () => {
	test('Desktop-rowActions und mobiles Blatt kommen aus subscriptionActions', () => {
		const tabelle = komponenten(ast, 'ListTable')[0];
		assert.ok(tabelle, '<ListTable> fehlt');
		const r = erreichbar(ast, wert(attribut(tabelle, 'rowActions')));
		assert.ok(r.bezeichner.has('subscriptionActions'), 'rowActions benutzt subscriptionActions nicht');
		assert.ok(r.literale.has('list'));
		assert.ok(importe(ast).some((i) => /subscriptionActions/.test(i.quelle)));
		assert.ok(!ids(ast.instance).has('compareActions'), 'compareActions (Alt-Quelle) wird noch benutzt');
	});

	const WIRKUNG: Array<[string, string]> = [
		['pause', 'setPaused'],
		['resume', 'setPaused'],
		['alarms', 'goto'],
		['weather', 'goto'],
		['edit', 'goto'],
		['preview', 'goto'],
		['continue-setup', 'goto']
	];
	for (const surface of ['rowActions-Dispatch (Desktop)', 'Blatt-Dispatch (Mobil)']) {
		test(`${surface}: ${WIRKUNG.map(([a]) => a).join(' · ')} erreichen ihre Wirkung`, () => {
			const traeger = komponenten(ast, surface.startsWith('rowActions') ? 'ListTable' : 'SubscriptionActionSheet')[0];
			assert.ok(traeger, `${surface}: Baustein fehlt (<SubscriptionActionSheet> bzw. <ListTable>)`);
			const quelle = attribut(traeger, 'onAction');
			assert.ok(quelle, `${surface}: Handler fehlt`);
			const r = erreichbar(ast, wert(quelle));
			for (const [aktion, wirkung] of WIRKUNG) {
				assert.ok(r.literale.has(aktion), `${surface}: Aktion "${aktion}" fehlt im Dispatch`);
				assert.ok(r.bezeichner.has(wirkung), `${surface}: ${wirkung} nicht erreichbar (Aktion "${aktion}" ohne Wirkung)`);
			}
			assert.ok(r.literale.has('send') && r.literale.has('delete'));
			assert.ok(!r.bezeichner.has('sendSubscription') && !r.bezeichner.has('deleteSubscription'), `${surface}: Senden/Loeschen ohne Rueckfrage`);
		});
	}

	test('Senden: Sende-Dialog mit Ziel (Profil) und Bestaetigung; Loeschen: ConfirmDialog -> deleteSubscription', () => {
		const dlg = komponenten(ast, 'SendConfirmDialog')[0];
		assert.ok(dlg, '<SendConfirmDialog> fehlt (Compare-Liste)');
		assert.ok(attribut(dlg, 'profile'), 'Sende-Dialog bekommt kein Konto-Profil (kein Ziel)');
		assert.ok(erreichbar(ast, wert(attribut(dlg, 'onConfirm'))).bezeichner.has('sendSubscription'));
		const loesch = komponenten(ast, 'ConfirmDialog').find((c) =>
			[...ids(wert(attribut(c, 'open')))].some((n) => /delete/i.test(n))
		);
		assert.ok(loesch, 'Loesch-ConfirmDialog fehlt');
		assert.ok(erreichbar(ast, wert(attribut(loesch, 'onConfirm'))).bezeichner.has('deleteSubscription'));
	});
});
