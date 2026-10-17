// TDD RED — Issue #2278 (Epic #2345 P3), AC-15.
// Spec: docs/specs/modules/feat_2278_aktionsmodell.md — AC-15 (+ Source: routes/_home/CompareKachel.svelte).
//
// Die Startseiten-Kachel verhaelt sich wie heute: Klick oeffnet den Hub; das Kebab bietet NUR
// "Bearbeiten" (oeffnet den Hub). Gemessen: die Kachel behandelt heute nur `edit`; kommt die neue
// Liste hinzu (Pausieren, Senden, …), duerfen dort keine wirkungslosen Eintraege erscheinen (AC-16).
// Die Kachel zieht von CompareTile auf `SubscriptionCard` um und bekommt ihre Aktionsliste explizit.
//
// Vertrag (hier festgelegt):
//   routes/_home/kachelActions.ts  exportiert `compareKachelActions()` => [{ id: 'edit', label: 'Bearbeiten' }]
//   CompareKachel.svelte           <SubscriptionCard kind="vergleich" compact actions={compareKachelActions()}
//                                   onclick={… goto('/compare/'+id)} onAction={… 'edit' => goto('/compare/'+id)} />
//
// Pruefstand: die Aktionsliste ist eine reine Funktion (direkt aufgerufen); die Verdrahtung wird am AST
// gemessen (Aufrufgraph, aktionsmodellAst.ts). Die Menue-Eintraege selbst rendern unter svelte/server
// nicht (bits-ui-Portal); die Klick-Wirkung bewacht Playwright `aktionsmodell-durchklick.spec.ts`.
//
// RED heute: kachelActions.ts fehlt; CompareKachel benutzt CompareTile (Aktionen aus compareActions()).
//
// Pfadregel #1409: relativ zu DIESER Datei.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/_home/__tests__/compare_kachel_aktionen.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import {
	ladeSvelte,
	komponenten,
	attribut,
	erreichbar,
	importe
} from '../../../lib/components/shared/__tests__/aktionsmodellAst.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const mod: any = await import(pathToFileURL(path.join(HERE, '..', 'kachelActions.ts')).href).catch(() => null);
const ast = ladeSvelte(path.join(HERE, '..', 'CompareKachel.svelte'));
const wert = (a: any) => (a ? (Array.isArray(a.value) ? a.value : [a.value]) : []);

describe('AC-15: Aktionsliste der Startseiten-Kachel = nur "Bearbeiten"', () => {
	test('compareKachelActions() liefert genau [edit]', () => {
		assert.ok(mod, 'routes/_home/kachelActions.ts fehlt (RED)');
		assert.deepEqual(mod.compareKachelActions(), [{ id: 'edit', label: 'Bearbeiten' }]);
	});

	test('die Liste ist unabhaengig von der Listen-Tabelle: kein pause/send/delete/alarms/weather/preview', () => {
		assert.ok(mod, 'routes/_home/kachelActions.ts fehlt (RED)');
		const idsListe = mod.compareKachelActions().map((a: any) => a.id);
		for (const verboten of ['pause', 'resume', 'send', 'delete', 'alarms', 'weather', 'preview', 'archive'])
			assert.ok(!idsListe.includes(verboten), `${verboten} in der Kachel-Liste (wirkungslos)`);
	});
});

describe('AC-15: CompareKachel — Klick oeffnet den Hub, Kebab nur Bearbeiten (Hub)', () => {
	test('baut auf SubscriptionCard (kind="vergleich") statt CompareTile', () => {
		const karten = komponenten(ast, 'SubscriptionCard');
		assert.equal(karten.length, 1, '<SubscriptionCard> fehlt in CompareKachel');
		assert.equal(komponenten(ast, 'CompareTile').length, 0, 'CompareTile wird noch benutzt');
		assert.ok(attribut(karten[0], 'kind'), 'kind fehlt');
	});

	test('Aktionsliste kommt aus compareKachelActions, nicht aus subscriptionActions', () => {
		const karte = komponenten(ast, 'SubscriptionCard')[0];
		assert.ok(karte, '<SubscriptionCard> fehlt');
		const a = attribut(karte, 'actions');
		assert.ok(a, '<SubscriptionCard actions=…> fehlt — Kachel zeigte sonst die volle Listen-Tabelle');
		const r = erreichbar(ast, wert(a));
		assert.ok(r.bezeichner.has('compareKachelActions'));
		assert.ok(!r.bezeichner.has('subscriptionActions'));
		assert.ok(importe(ast).some((i) => /kachelActions/.test(i.quelle)));
	});

	test('Klick und "edit" navigieren auf /compare/{id}; kein Adapter-Aufruf (nichts wirkungslos)', () => {
		const karte = komponenten(ast, 'SubscriptionCard')[0];
		assert.ok(karte, '<SubscriptionCard> fehlt');
		const klick = erreichbar(ast, wert(attribut(karte, 'onclick')));
		assert.ok(klick.bezeichner.has('goto'));
		assert.ok([...klick.literale].some((l) => l.startsWith('/compare/')));
		const aktion = erreichbar(ast, wert(attribut(karte, 'onAction')));
		assert.ok(aktion.literale.has('edit'));
		assert.ok(aktion.bezeichner.has('goto'));
		for (const n of ['setPaused', 'sendSubscription', 'deleteSubscription', 'setArchived'])
			assert.ok(!aktion.bezeichner.has(n), `Kachel-Aktion erreicht ${n}`);
	});
});
