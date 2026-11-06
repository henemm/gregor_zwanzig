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
import { fileURLToPath, pathToFileURL } from 'node:url';
import { umgebungFuer, werte, findeKomponenten, attributAusdruck, type Knoten } from '../../../../lib/components/shared/__tests__/svelteInstanzPruefstand.ts';
import { baum, einzig, liegtIn, mitTestid } from '../../../../lib/components/shared/hub-kopf/__tests__/htmlBaum.ts';
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
const SEITE = path.join(HERE, '..', '+page.svelte');
const ast = ladeSvelte(SEITE);
const KOMP = path.resolve(HERE, '../../../../lib/components');

const attrWert = (a: any) => (a ? (Array.isArray(a.value) ? a.value : [a.value]) : []);

// #2837 S1 (ADR-0110): das Lebenszyklus-Menue (SubscriptionKebab) liegt im geteilten HubKopf, den
// TripHeader einbettet. Die Seite reicht Aktionen und Auswahl-Handler an diese Kopf-Einbettung
// (die Komponente mit `onSend`); die AST-Zusicherungen unten wirken dort. Dass die Loesch-Aktion
// beim Kebab ANKOMMT (gerendert) und AUSGELOEST werden kann, belegt der Block „Kette" am Ende.
const kopfEinbettung = () => {
	const k = collect(ast.fragment, (n) => n.type === 'Component' && (n.attributes ?? []).some((a: any) => a.name === 'onSend'));
	assert.equal(k.length, 1, `genau eine Kopf-Einbettung (mit onSend) im Trip-Hub erwartet, gefunden ${k.length}`);
	return k[0];
};

describe('AC-5/#1064: Loeschen ist im Trip-Hub erreichbar und laeuft ueber den Bestaetigungsdialog', () => {
	test('der Hub reicht das Lebenszyklus-Menue an den Kopf; seine Aktionen stammen aus subscriptionActions(…, "hub")', () => {
		const kopf = kopfEinbettung();
		assert.equal(kopf.name, 'TripHeader', 'die Kopf-Einbettung des Trip-Hubs ist nicht TripHeader');
		const actions = attribut(kopf, 'actions');
		assert.ok(actions, '<TripHeader actions=…> fehlt');
		const r = erreichbar(ast, attrWert(actions));
		assert.ok(r.bezeichner.has('subscriptionActions'), 'Aktionen kommen nicht aus subscriptionActions');
		assert.ok(r.literale.has('hub'), 'Flaeche "hub" wird nicht angefordert');
		assert.ok(importe(ast).some((i) => /subscriptionActions/.test(i.quelle)), 'subscriptionActions nicht importiert');
	});

	test('"Loeschen" im Menue oeffnet den Dialog (setzt deleteDialogOpen) und loest NOCH keinen DELETE aus', () => {
		const kebab = kopfEinbettung();
		const onSelect = attribut(kebab, 'onSelect') ?? attribut(kebab, 'onAction');
		assert.ok(onSelect, 'Kopf-Einbettung hat keinen Auswahl-Handler (onSelect/onAction)');
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
			// Fix-Loop 1 (F008): exakt `trip.name`, nicht irgendein Bezeichner mit "name".
			collect(
				v ?? [],
				(n) =>
					n.type === 'MemberExpression' &&
					n.object?.type === 'Identifier' &&
					n.object.name === 'trip' &&
					n.property?.name === 'name'
			).length > 0
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
		const kebab = kopfEinbettung();
		const vomMenue = erreichbar(ast, attrWert(attribut(kebab, 'onSelect') ?? attribut(kebab, 'onAction')));
		assert.ok(!vomMenue.bezeichner.has('sendSubscription'), 'Menue sendet ohne Rueckfrage');
	});

	test('Pausieren/Fortsetzen und Archivieren/Reaktivieren erreichen einen Zustands-Schreibweg', () => {
		const kebab = kopfEinbettung();
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

// #2837 S1 (ADR-0110): Kette Seite → TripHeader → HubKopf → SubscriptionKebab. Jede Weitergabe wird
// in IHRER Komponente ausgewertet (svelteInstanzPruefstand: echtes Instanz-Skript, gesaete Props) und
// der Menue-Eintrag „delete" des Kebabs wird AUSGELOEST; gemessen wird der Zustand der Seite.
// Mobil: die Seite echt serverseitig gerendert (Pruefstand f9, Zustand mobil + offenes Blatt).
describe('#2837 S1 Kette: die Loesch-Aktion kommt beim Kebab im HubKopf an und ist dort ausloesbar', async () => {
	const T = await import('../../../../lib/components/trip-detail/__tests__/f9Pruefstand.ts');
	const { render } = await import('svelte/server');
	const loeschAufrufe: unknown[] = [];
	const seite = await umgebungFuer(
		SEITE,
		{ data: { trip: T.tripLaufend(), metricsCatalog: T.KATALOG, profile: null }, deleteSubscription: (...a: unknown[]) => loeschAufrufe.push(a), goto: () => Promise.resolve() },
		{ jsAlsTs: true }
	);
	const komponente = async (rel: string) => umgebungFuer(path.join(KOMP, rel), {}, { jsAlsTs: true });
	const tripHeader = await komponente('trip-detail/TripHeader.svelte');
	const hubKopf = await komponente('shared/hub-kopf/HubKopf.svelte');
	const kebab = await komponente('molecules/SubscriptionKebab.svelte');
	/** Wert des Attributs `name` an der (einzigen) Einbettung von `kind` in `eltern`, mit `props` als Umgebung. */
	const weiter = (eltern: { ast: Knoten; quelle: string; u: Knoten }, kind: string, name: string, props: Knoten): unknown => {
		const e = findeKomponenten(eltern.ast, kind);
		assert.equal(e.length, 1, `${kind} nicht genau einmal eingebettet`);
		const a = attributAusdruck(e[0], eltern.quelle, name);
		assert.ok(a, `${kind} bekommt kein ${name}`);
		return werte(a, Object.assign(Object.create(eltern.u), props));
	};
	const ausSeite = (name: string) => werte(attributAusdruck(kopfEinbettung(), seite.quelle, name)!, seite.u);

	test('Aktionen: die Liste der Seite (mit „delete") erreicht unverändert den SubscriptionKebab', () => {
		const liste = ausSeite('actions') as Array<{ id: string }>;
		assert.ok(liste.some((a) => a.id === 'delete'), `Hub-Aktionen ohne „delete": ${JSON.stringify(liste)}`);
		const imKopf = weiter(tripHeader, 'HubKopf', 'actions', { actions: liste });
		assert.equal(weiter(hubKopf, 'SubscriptionKebab', 'actions', { actions: imKopf }), liste);
	});

	test('„delete" im Kebab ausgeloest ⇒ Bestaetigungsdialog offen, noch kein DELETE', () => {
		const imKopf = weiter(tripHeader, 'HubKopf', 'onSelect', { onSelect: ausSeite('onSelect') });
		const amKebab = weiter(hubKopf, 'SubscriptionKebab', 'onSelect', { onSelect: imKopf });
		const eintrag = findeKomponenten(kebab.ast, 'DropdownMenu.Item');
		assert.equal(eintrag.length, 1, 'Menue-Eintrag des Kebabs nicht gefunden');
		const auswahl = werte(attributAusdruck(eintrag[0], kebab.quelle, 'onSelect')!, Object.assign(Object.create(kebab.u), { onSelect: amKebab, action: { id: 'delete' } })) as () => void;
		assert.equal(seite.u.deleteDialogOpen, false, 'Vorbedingung: Dialog zu');
		auswahl();
		assert.equal(seite.u.deleteDialogOpen, true, '„delete" im Kebab oeffnet den Loesch-Dialog der Seite nicht');
		assert.deepEqual(loeschAufrufe, [], 'DELETE ohne Rueckfrage ausgeloest');
		seite.u.deleteDialogOpen = false;
	});

	test('mobil gerendert: Kebab in der Kopfleiste, Tippen oeffnet das Blatt, dort steht „delete" und loest den Dialog aus', async () => {
		const zustand = [['let mobil = $state(false);', 'let mobil = $state(true);'], ['let sheetOpen = $state(false);', 'let sheetOpen = $state(true);']];
		const Seite = (await import(`${pathToFileURL(SEITE).href}?f8variante=${Buffer.from(JSON.stringify(zustand)).toString('base64url')}`)).default;
		const w = baum(render(Seite, { props: { data: { trip: T.tripLaufend(), metricsCatalog: T.KATALOG, profile: null } } }).body);
		assert.ok(liegtIn(einzig(w, 'subscription-kebab'), einzig(w, 'hub-kopf-leiste')), 'mobiler Kebab steht nicht in der Kopfleiste');
		assert.equal(mitTestid(w, 'subscription-action-delete').length, 1, '„Löschen" steht nicht genau einmal im Aktionsblatt');
		// Tippen auf den mobilen Kebab-Knopf: dessen onclick → onSheetOpen aus HubKopf ← TripHeader ← Seite.
		seite.u.sheetOpen = false;
		const imKopf = weiter(tripHeader, 'HubKopf', 'onSheetOpen', { onSheetOpen: ausSeite('onSheetOpen') });
		const amKebab = weiter(hubKopf, 'SubscriptionKebab', 'onSheetOpen', { onSheetOpen: imKopf });
		const knopf = collect(kebab.ast.fragment, (n) => n.type === 'RegularElement' && n.name === 'button' && /\bonSheetOpen\b/.test(attributAusdruck(n, kebab.quelle, 'onclick') ?? ''));
		assert.equal(knopf.length, 1, 'mobiler Kebab-Knopf (onclick → onSheetOpen) nicht genau einmal');
		(werte(attributAusdruck(knopf[0], kebab.quelle, 'onclick')!, Object.assign(Object.create(kebab.u), { onSheetOpen: amKebab })) as () => void)();
		assert.equal(seite.u.sheetOpen, true, 'Tippen auf den Kebab oeffnet das Aktionsblatt der Seite nicht');
		// Das Blatt loest ueber denselben Handler aus wie das Desktop-Menue.
		const blatt = findeKomponenten(seite.ast, 'SubscriptionActionSheet');
		assert.equal(blatt.length, 1);
		(werte(attributAusdruck(blatt[0], seite.quelle, 'onAction')!, seite.u) as (id: string) => void)('delete');
		assert.equal(seite.u.deleteDialogOpen, true, '„delete" im Blatt oeffnet den Loesch-Dialog nicht');
		assert.deepEqual(loeschAufrufe, [], 'DELETE ohne Rueckfrage ausgeloest');
	});
});
