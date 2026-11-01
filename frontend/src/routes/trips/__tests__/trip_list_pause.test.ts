// TDD RED — Issue #2278 (Epic #2345 P3), AC-1, AC-8 (Listen-Seite), AC-14 (mobile Trip-Liste), AC-17.
// Spec: docs/specs/modules/feat_2278_aktionsmodell.md — Implementation Details 1, 5, 7, 9.
//
// Die Trip-Liste (Desktop + Mobil) bezieht ihre Aktionen aus `subscriptionActions(…, 'list')` — nicht
// mehr aus der Konstante TRIP_ACTIONS (heute ohne "Pausieren", mit "Alert-Konfiguration"-Sonderdialog).
// Die Aktionen selbst sind in subscriptionActions.test.ts als Tabelle festgelegt; HIER wird gemessen,
// dass die Seite sie WIRKLICH benutzt und jede Aktion eine Wirkung erreicht (AC-16: kein totes Element).
//
// Pruefstand: AST (echter Svelte-Compiler) + Aufrufgraph des Instanz-Skripts — siehe
// lib/components/shared/__tests__/aktionsmodellAst.ts. Kein DOM in der Kernsuite; das Durchklicken
// bewachen Playwright `hub-list-menu.spec.ts` und `aktionsmodell-durchklick.spec.ts`.
//
// RED heute: TRIP_ACTIONS statt subscriptionActions, Alert-Konfiguration-Dialog, Inline-Karte/-Sheet,
// toter Code (primaryLabel, handlePrimaryAction, handleArchive).
//
// Pfadregel #1409: relativ zu DIESER Datei.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/trips/__tests__/trip_list_pause.test.ts

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
	importe
} from '../../../lib/components/shared/__tests__/aktionsmodellAst.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ast = ladeSvelte(path.join(HERE, '..', '+page.svelte'));
const { trFor } = await import('../../../lib/i18n/index.ts');
const wert = (a: any) => (a ? (Array.isArray(a.value) ? a.value : [a.value]) : []);
const hatLiteral = (lits: Set<string>, re: RegExp) => [...lits].some((l) => re.test(l));

function listenTabelle(): any {
	const t = komponenten(ast, 'ListTable')[0];
	assert.ok(t, '<ListTable> fehlt');
	return t;
}

describe('AC-1: Desktop-Trip-Liste — Zeilenmenue aus der EINEN Aktionsquelle', () => {
	test('rowActions kommt aus subscriptionActions(…, "list")', () => {
		const r = erreichbar(ast, wert(attribut(listenTabelle(), 'rowActions')));
		assert.ok(r.bezeichner.has('subscriptionActions'), 'rowActions benutzt subscriptionActions nicht');
		assert.ok(r.literale.has('list'), 'Flaeche "list" wird nicht angefordert');
		assert.ok(importe(ast).some((i) => /subscriptionActions/.test(i.quelle)));
	});

	test('"Pausieren"/"Fortsetzen" wirkt ueber den Adapter setPaused', () => {
		const r = erreichbar(ast, wert(attribut(listenTabelle(), 'onAction')));
		assert.ok(r.literale.has('pause') && r.literale.has('resume'), 'pause/resume nicht im Dispatch');
		assert.ok(r.bezeichner.has('setPaused'), 'Dispatch erreicht setPaused nicht — Pausieren ohne Wirkung');
	});

	test('"Senden" oeffnet den Sende-Dialog, sendet nicht direkt; die Bestaetigung sendet', () => {
		const r = erreichbar(ast, wert(attribut(listenTabelle(), 'onAction')));
		assert.ok(r.literale.has('send'));
		assert.ok(!r.bezeichner.has('sendSubscription') && !r.bezeichner.has('sendTripTestReport'), 'Senden ohne Rueckfrage');
		const dlgs = komponenten(ast, 'SendConfirmDialog');
		assert.equal(dlgs.length, 1, 'kein <SendConfirmDialog> auf der Trip-Liste');
		const zustand = ids(wert(attribut(dlgs[0], 'open')));
		assert.ok([...zustand].some((n) => r.bezeichner.has(n)), '"Senden" erreicht den Dialog-Zustand nicht');
		const best = erreichbar(ast, wert(attribut(dlgs[0], 'onConfirm')));
		assert.ok(best.bezeichner.has('sendSubscription'), 'Bestaetigen sendet nicht');
	});

	test('"Loeschen" oeffnet die Bestaetigung (deleteTarget), loescht nicht direkt', () => {
		const r = erreichbar(ast, wert(attribut(listenTabelle(), 'onAction')));
		assert.ok(r.literale.has('delete'));
		assert.ok(!r.bezeichner.has('deleteSubscription'), 'Loeschen ohne Rueckfrage');
	});

	test('Zeilen-Primaerknopf "Briefing senden" bleibt, oeffnet aber den Sende-Dialog (AC-3/AC-17: nie ohne Rueckfrage)', () => {
		const r = erreichbar(ast, wert(attribut(listenTabelle(), 'rowPrimary')));
		// #2652 (i18n F3): Beschriftung aus dem Katalog (deutsch „Briefing senden").
		assert.ok(r.literale.has('listen.aktion.briefing_senden'), 'Primaerknopf "Briefing senden" fehlt');
		assert.equal(trFor('de', 'listen.aktion.briefing_senden'), 'Briefing senden');
		const dlg = komponenten(ast, 'SendConfirmDialog')[0];
		assert.ok(dlg, '<SendConfirmDialog> fehlt');
		const zustand = ids(wert(attribut(dlg, 'open')));
		assert.ok([...zustand].some((n) => r.bezeichner.has(n)), 'Primaerknopf erreicht den Sende-Dialog nicht');
		for (const direkt of ['sendSubscription', 'sendTripTestReport', 'runTestReport', 'sendTripBriefing'])
			assert.ok(!r.bezeichner.has(direkt), `Primaerknopf sendet direkt (${direkt}) — ohne Rueckfrage`);
	});
});

describe('AC-8: "Alarme" und "Wetter-Metriken" navigieren auf den Hub-Reiter; Alert-Konfiguration existiert nicht', () => {
	test('Dispatch fuehrt auf ?tab=alarme und ?tab=wetter-metriken', () => {
		const r = erreichbar(ast, wert(attribut(listenTabelle(), 'onAction')));
		assert.ok(r.literale.has('alarms') && r.literale.has('weather'));
		assert.ok(hatLiteral(r.literale, /tab=alarme/), 'kein Sprung auf ?tab=alarme');
		assert.ok(hatLiteral(r.literale, /tab=wetter-metriken/), 'kein Sprung auf ?tab=wetter-metriken');
	});
	test('kein Alert-Konfigurations-Dialog mehr (openReportConfig / saveReportConfig / ReportConfigDialog)', () => {
		const alle = ids(ast.instance);
		for (const n of ['openReportConfig', 'saveReportConfig', 'ReportConfigDialog', 'reportConfigTarget'])
			assert.ok(!alle.has(n), `${n} existiert noch`);
		assert.equal(komponenten(ast, 'ReportConfigDialog').length, 0);
	});
});

describe('AC-17: toter Code und Inline-Karte/-Sheet sind entfernt', () => {
	test('primaryLabel, handlePrimaryAction, handleArchive, TRIP_ACTIONS gibt es nicht mehr', () => {
		const alle = ids(ast.instance);
		for (const n of ['primaryLabel', 'handlePrimaryAction', 'handleArchive', 'TRIP_ACTIONS'])
			assert.ok(!alle.has(n), `${n} (toter Code / Alt-Quelle) existiert noch`);
	});
	test('kein unerreichbarer Archiv-Dialog mehr', () => {
		const archivDialoge = komponenten(ast, 'ConfirmDialog').filter((d) =>
			[...ids(wert(attribut(d, 'open')))].some((n) => /archiv/i.test(n))
		);
		assert.equal(archivDialoge.length, 0, 'ConfirmDialog fuer Archivieren besteht noch (unerreichbar)');
	});
});

describe('AC-14/AC-2-Paritaet: mobile Trip-Liste nutzt dieselben Bausteine wie der Ortsvergleich', () => {
	test('SubscriptionCard, SubscriptionActionSheet und StatusFilterPills sind eingebunden', () => {
		assert.ok(komponenten(ast, 'SubscriptionCard').length >= 1, '<SubscriptionCard> fehlt');
		assert.equal(komponenten(ast, 'SubscriptionActionSheet').length, 1, '<SubscriptionActionSheet> fehlt');
		assert.equal(komponenten(ast, 'StatusFilterPills').length, 1, '<StatusFilterPills> fehlt');
		assert.ok(!ids(ast.instance).has('sheetTrip'), 'Inline-Sheet-Zustand sheetTrip existiert noch');
	});
	test('"Senden" im mobilen Blatt oeffnet den Sende-Dialog (statt nur die Vorschau)', () => {
		const sheet = komponenten(ast, 'SubscriptionActionSheet')[0];
		assert.ok(sheet, '<SubscriptionActionSheet> fehlt');
		const r = erreichbar(ast, wert(attribut(sheet, 'onAction')));
		assert.ok(r.literale.has('send'), 'Blatt kennt "send" nicht');
		const dlg = komponenten(ast, 'SendConfirmDialog')[0];
		const zustand = ids(wert(attribut(dlg, 'open')));
		assert.ok([...zustand].some((n) => r.bezeichner.has(n)), '"Senden" im Blatt erreicht den Sende-Dialog nicht (heute: nur Vorschau)');
		assert.ok(!r.bezeichner.has('sendSubscription'), 'Blatt sendet ohne Rueckfrage');
	});
});
