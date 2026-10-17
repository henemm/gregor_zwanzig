// TDD RED — Issue #2278 (Epic #2345 P3), AC-5 (schliesst #1064) und AC-12 (Trip-Hub: Lebenszyklus-Menue).
// Spec: docs/specs/modules/feat_2278_aktionsmodell.md — Implementation Details 9.
//
// Gemessener Defekt (#1064): im Trip-Hub hat `handleDeleteClick` KEINEN Aufrufer — der
// Loesch-Dialog ist unerreichbar. Ziel: Lebenszyklus-Menue `SubscriptionKebab` mit den Aktionen
// aus `subscriptionActions('trip', status, 'hub')`; "Loeschen" oeffnet den Bestaetigungsdialog; erst
// dessen Bestaetigung loest DELETE aus (`deleteSubscription`), danach Navigation auf /trips.
//
// Pruefstand: kein DOM, bits-ui-Dialoge rendern unter svelte/server nichts. Deshalb wird die
// VERDRAHTUNG am AST (echter Svelte-Compiler) gemessen: welche Funktionen ein Klick-Handler
// ERREICHT (Aufrufgraph des Instanz-Skripts), nicht welcher Text im File steht. Das Klicken
// selbst bewacht Playwright `aktionsmodell-durchklick.spec.ts`.
// Ergaenzend (Compare-Gegenstueck bleibt): routes/compare/__tests__/compare_hub_loeschen_bestaetigung.
//
// RED heute: kein SubscriptionKebab im Trip-Hub, Loeschen unerreichbar, Breadcrumb-Aktionsleiste.
//
// Pfadregel #1409: relativ zu DIESER Datei.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test "src/routes/trips/[id]/__tests__/trip_hub_loeschen.test.ts"

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
	ladeSvelte,
	komponenten,
	attribut,
	erreichbar,
	importe,
	collect,
	literale
} from '../../../../lib/components/shared/__tests__/aktionsmodellAst.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ast = ladeSvelte(path.join(HERE, '..', '+page.svelte'));

const attrWert = (a: any) => (a ? (Array.isArray(a.value) ? a.value : [a.value]) : []);

describe('AC-5/#1064: Loeschen ist im Trip-Hub erreichbar und laeuft ueber den Bestaetigungsdialog', () => {
	test('der Hub bindet SubscriptionKebab ein; seine Aktionen stammen aus subscriptionActions(…, "hub")', () => {
		const kebabs = komponenten(ast, 'SubscriptionKebab');
		assert.ok(kebabs.length >= 1, 'kein <SubscriptionKebab> im Trip-Hub (Lebenszyklus-Menue fehlt)');
		const actions = attribut(kebabs[0], 'actions');
		assert.ok(actions, '<SubscriptionKebab actions=…> fehlt');
		const r = erreichbar(ast, attrWert(actions));
		assert.ok(r.bezeichner.has('subscriptionActions'), 'Aktionen kommen nicht aus subscriptionActions');
		assert.ok(r.literale.has('hub'), 'Flaeche "hub" wird nicht angefordert');
		assert.ok(importe(ast).some((i) => /subscriptionActions/.test(i.quelle)), 'subscriptionActions nicht importiert');
	});

	test('"Loeschen" im Menue oeffnet den Dialog (setzt deleteDialogOpen) und loest NOCH keinen DELETE aus', () => {
		const kebab = komponenten(ast, 'SubscriptionKebab')[0];
		assert.ok(kebab, '<SubscriptionKebab> fehlt');
		const onSelect = attribut(kebab, 'onSelect') ?? attribut(kebab, 'onAction');
		assert.ok(onSelect, 'Kebab hat keinen Auswahl-Handler (onSelect/onAction)');
		const r = erreichbar(ast, attrWert(onSelect));
		assert.ok(r.literale.has('delete'), 'der Handler kennt die Aktion "delete" nicht');
		assert.ok(r.bezeichner.has('deleteDialogOpen'), 'Handler erreicht deleteDialogOpen nicht — Dialog bleibt unerreichbar (#1064)');
		assert.ok(!r.bezeichner.has('deleteSubscription'), 'DELETE haengt direkt am Menue — Rueckfrage umgangen');
		assert.ok(!r.bezeichner.has('fetch'), 'Menue-Handler ruft fetch direkt (Rueckfrage umgangen)');
	});

	test('ConfirmDialog "Loeschen": Testids *-delete-confirm-{dialog,cancel,yes}, Name im Text', () => {
		const dialoge = komponenten(ast, 'ConfirmDialog').filter((d) =>
			literale(attribut(d, 'confirmTestid')?.value ?? []).has('trip-detail-delete-confirm-yes') ||
			[...literale(attribut(d, 'confirmTestid')?.value ?? [])].some((l) => /delete-confirm-yes$/.test(l))
		);
		assert.equal(dialoge.length, 1, 'genau ein Loesch-ConfirmDialog erwartet');
		const d = dialoge[0];
		const dlg = [...literale(attribut(d, 'data-testid')?.value ?? [])][0] ?? '';
		const cancel = [...literale(attribut(d, 'cancelTestid')?.value ?? [])][0] ?? '';
		assert.match(dlg, /delete-confirm-dialog$/);
		assert.match(cancel, /delete-confirm-cancel$/);
		// "mit dem Namen": Titel oder Beschreibung referenziert den Namen (Ausdruck, kein reiner Literaltext).
		const tb = [attribut(d, 'title')?.value, attribut(d, 'description')?.value];
		const namensBezug = tb.some((v) =>
			collect(v ?? [], (n) => n.type === 'MemberExpression' || (n.type === 'Identifier' && /name/i.test(n.name))).length > 0
		);
		assert.ok(namensBezug, 'Dialogtext nennt den Trip-Namen nicht (AC-5: "mit dem Namen")');
	});

	test('erst die Bestaetigung ruft deleteSubscription und navigiert danach auf /trips', () => {
		const d = komponenten(ast, 'ConfirmDialog').find((c) =>
			[...literale(attribut(c, 'confirmTestid')?.value ?? [])].some((l) => /delete-confirm-yes$/.test(l))
		);
		assert.ok(d, 'Loesch-ConfirmDialog fehlt');
		const onConfirm = attribut(d, 'onConfirm');
		const r = erreichbar(ast, attrWert(onConfirm));
		assert.ok(r.bezeichner.has('deleteSubscription'), 'Bestaetigen loest kein deleteSubscription aus');
		assert.ok(r.literale.has('/trips'), 'nach dem Loeschen keine Navigation auf /trips');
		const abbrechen = erreichbar(ast, attrWert(attribut(d, 'onCancel')));
		assert.ok(!abbrechen.bezeichner.has('deleteSubscription'), 'Abbrechen darf nicht loeschen');
	});
});

describe('AC-12: Lebenszyklus-Menue statt Breadcrumb-Aktionsleiste; Senden ist Primaerknopf mit Sende-Dialog', () => {
	test('die Breadcrumb-Aktionsleiste (Pausieren/Archivieren/Test-Briefing) existiert nicht mehr', () => {
		const leiste = collect(
			ast.fragment,
			(n) =>
				n.type === 'RegularElement' &&
				(n.attributes ?? []).some(
					(a: any) => a.name === 'class' && [...literale(a.value)].some((l) => /breadcrumb-actions/.test(l))
				)
		);
		assert.equal(leiste.length, 0, '<div class="breadcrumb-actions"> mit Einzelknoepfen besteht noch');
	});

	test('Senden: SendConfirmDialog eingebunden, nur seine Bestaetigung erreicht sendSubscription', () => {
		const dlgs = komponenten(ast, 'SendConfirmDialog');
		assert.equal(dlgs.length, 1, 'kein <SendConfirmDialog> im Trip-Hub');
		const r = erreichbar(ast, attrWert(attribut(dlgs[0], 'onConfirm')));
		assert.ok(r.bezeichner.has('sendSubscription'), 'Bestaetigen sendet nicht (sendSubscription)');
		const kebab = komponenten(ast, 'SubscriptionKebab')[0];
		const vomMenue = erreichbar(ast, attrWert(attribut(kebab, 'onSelect') ?? attribut(kebab, 'onAction')));
		assert.ok(!vomMenue.bezeichner.has('sendSubscription'), 'Menue sendet ohne Rueckfrage');
	});

	test('Pausieren/Fortsetzen und Archivieren/Reaktivieren erreichen einen Zustands-Schreibweg', () => {
		const kebab = komponenten(ast, 'SubscriptionKebab')[0];
		assert.ok(kebab, '<SubscriptionKebab> fehlt');
		const r = erreichbar(ast, attrWert(attribut(kebab, 'onSelect') ?? attribut(kebab, 'onAction')));
		assert.ok(r.literale.has('pause') && r.literale.has('resume'), 'Pausieren/Fortsetzen nicht verdrahtet');
		assert.ok(r.literale.has('archive') && r.literale.has('unarchive'), 'Archivieren/Reaktivieren nicht verdrahtet');
		// Schreibweg: entweder der bestehende Hub-Schreiber (flusht offene Speicherungen, ETag #1433)
		// oder der Adapter. Beides ist zulaessig; ein Handler OHNE Schreibweg waere ein totes Element.
		const schreibt = ['sendStateUpdate', 'setPaused', 'setArchived'].some((n) => r.bezeichner.has(n));
		assert.ok(schreibt, 'Pausieren/Archivieren erreichen keinen Schreibweg (sendStateUpdate / setPaused / setArchived)');
		// Archivieren/Reaktivieren hat eine Rueckfrage (ConfirmDialog) oder schreibt direkt — Reaktivieren darf nie fehlen.
	});
});
