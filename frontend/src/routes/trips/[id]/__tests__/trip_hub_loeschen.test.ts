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
import { umgebungFuer, werte, findeKomponenten, attributAusdruck, ohneTypen, type Knoten } from '../../../../lib/components/shared/__tests__/svelteInstanzPruefstand.ts';
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
/** #3442: Ausdrucksknoten des Attributs `name` (für ohneTypen + werte); scheitert laut, wenn er fehlt. */
const ausdruckKnoten = (einbettung: any, name: string) => {
	const tag = attrWert(attribut(einbettung, name))[0];
	assert.ok(tag?.type === 'ExpressionTag', `<${einbettung.name}> hat kein Ausdrucks-Attribut ${name}`);
	return tag.expression;
};

// #2837 S1 (ADR-0110): das Lebenszyklus-Menue (SubscriptionKebab) liegt im geteilten HubKopf, den
// TripHeader einbettet. Die Seite reicht Aktionen und Auswahl-Handler an diese Kopf-Einbettung
// (die Komponente mit `onTest`, seit #3440 statt `onSend`); die AST-Zusicherungen unten wirken dort. Dass
// die Loesch-Aktion beim Kebab ANKOMMT (gerendert) und AUSGELOEST werden kann, belegt der Block „Kette" am Ende.
const kopfEinbettung = () => {
	const k = collect(ast.fragment, (n) => n.type === 'Component' && (n.attributes ?? []).some((a: any) => a.name === 'onTest'));
	assert.equal(k.length, 1, `genau eine Kopf-Einbettung (mit onTest) im Trip-Hub erwartet, gefunden ${k.length}`);
	return k[0];
};

describe('AC-5/#1064 → #3442: Loeschen ist im Trip-Hub erreichbar und laeuft ueber die Rueckfrage im Kebab-Menue', () => {
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

	// #3442 (feat_3442 AC-1/AC-2/AC-13): die Rückfrage („Löschen?“ mit dem Namen, „Endgültig löschen“) sitzt im
	// Kebab-Menü selbst (KebabBestaetigungPanel, Name über HubKopf → SubscriptionKebab). onSelect der Seite kommt
	// erst NACH der Bestätigung an — die Seite löscht dann direkt. Belegt in der Kette unten und in
	// shared/__tests__/kebab_seiten_bindung.test.ts.
	test('"Loeschen" kommt erst nach der Rueckfrage im Menue an: der Seiten-Handler loescht und navigiert auf /trips', () => {
		const kebab = kopfEinbettung();
		const onSelect = attribut(kebab, 'onSelect') ?? attribut(kebab, 'onAction');
		assert.ok(onSelect, 'Kopf-Einbettung hat keinen Auswahl-Handler (onSelect/onAction)');
		const r = erreichbar(ast, attrWert(onSelect));
		assert.ok(r.literale.has('delete'), 'der Handler kennt die Aktion "delete" nicht');
		assert.ok(!r.bezeichner.has('deleteDialogOpen'), 'Handler oeffnet noch einen Seitendialog (#3442: Rueckfrage im Menue)');
		assert.ok(r.bezeichner.has('deleteSubscription'), 'der bestaetigte Menue-Weg loescht nicht');
		assert.ok(r.literale.has('/trips'), 'nach dem Loeschen keine Navigation auf /trips');
	});

	test('kein Loesch-ConfirmDialog mehr im Trip-Hub (die Rueckfrage nennt den Namen im Menue)', () => {
		assert.equal(komponenten(ast, 'ConfirmDialog').length, 0, 'Trip-Hub bindet noch ConfirmDialog ein');
		const kopf = collect(ladeSvelte(path.join(KOMP, 'shared/hub-kopf/HubKopf.svelte')).fragment, (n) => n.type === 'Component' && n.name === 'SubscriptionKebab');
		assert.equal(kopf.length, 1);
		assert.ok(attribut(kopf[0], 'name'), 'HubKopf gibt den Namen nicht an den Kebab (Rueckfrage ohne Namen)');
	});
});

describe('AC-12: Lebenszyklus-Menue statt Breadcrumb-Aktionsleiste; „Test schicken“ ist Primaerknopf mit Menue (#3440)', () => {
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

	test('Senden: kein SendConfirmDialog mehr; nur die Menue-Wahl (onTest) erreicht sendSubscription', () => {
		// #3440 (Fortschreibung feat_2278 AC-12): der Klick auf die Kanalzeile ist die Auslösung.
		assert.equal(komponenten(ast, 'SendConfirmDialog').length, 0, '<SendConfirmDialog> steht noch im Trip-Hub');
		const r = erreichbar(ast, attrWert(attribut(kopfEinbettung(), 'onTest')));
		assert.ok(r.bezeichner.has('sendSubscription'), 'die Menue-Wahl sendet nicht (sendSubscription)');
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

	// #3442: „delete" im Kebab ⇒ Rückfrage im Menü (preventDefault, Panel), noch KEIN DELETE; erst „Endgültig löschen“
	// im Panel (onBestaetigen) läuft über HubKopf ← TripHeader bis zur Seite und löscht genau einmal.
	test('„delete" im Kebab ausgeloest ⇒ Rueckfrage im Menue, noch kein DELETE; Bestaetigen im Panel loescht genau einmal', () => {
		const imKopf = weiter(tripHeader, 'HubKopf', 'onSelect', { onSelect: ausSeite('onSelect') });
		const amKebab = weiter(hubKopf, 'SubscriptionKebab', 'onSelect', { onSelect: imKopf });
		const eintrag = findeKomponenten(kebab.ast, 'DropdownMenu.Item').filter((n) => /subscription-action-/.test(JSON.stringify(attribut(n, 'data-testid')?.value ?? '')));
		assert.equal(eintrag.length, 1, 'Menue-Eintrag (subscription-action-…) des Kebabs nicht gefunden');
		// Der Kebab-Zustand lebt in kebab.u (seine Funktionen sind dort gebunden) — Props direkt dort setzen.
		Object.assign(kebab.u, { onSelect: amKebab, name: 'Trip Kette', mobil: false, action: { id: 'delete', label: 'Löschen …' } });
		const neuHerleiten = () => {
			for (const stmt of (kebab.ast.instance?.content?.body ?? []) as Knoten[])
				if (stmt.type === 'VariableDeclaration')
					for (const d of stmt.declarations as Knoten[])
						if (d.id?.type === 'Identifier' && d.init && /^\$derived/.test(kebab.quelle.slice(d.init.start, d.init.end)))
							kebab.u[d.id.name] = werte(ohneTypen(kebab.quelle, d.init), kebab.u);
		};
		const e = new Event('menu-select', { cancelable: true });
		(werte(ohneTypen(kebab.quelle, ausdruckKnoten(eintrag[0], 'onSelect')), kebab.u) as (e: Event) => void)(e);
		neuHerleiten();
		assert.equal(e.defaultPrevented, true, '„delete" schliesst das Menue sofort (keine Rueckfrage im Menue)');
		assert.notEqual(seite.u.deleteDialogOpen, true, '„delete" oeffnet einen Seitendialog statt der Rueckfrage im Menue');
		assert.deepEqual(loeschAufrufe, [], 'DELETE ohne Rueckfrage ausgeloest');
		const panel = findeKomponenten(kebab.ast, 'KebabBestaetigungPanel');
		assert.equal(panel.length, 1, 'TDD RED: SubscriptionKebab bindet KebabBestaetigungPanel nicht ein');
		(werte(ohneTypen(kebab.quelle, ausdruckKnoten(panel[0], 'onBestaetigen')), kebab.u) as () => void)();
		assert.equal(loeschAufrufe.length, 1, 'Bestaetigen im Panel loescht nicht genau einmal');
		assert.deepEqual(loeschAufrufe[0], ['trip', T.tripLaufend().id]);
	});

	test('mobil gerendert: Kebab in der Kopfleiste, Tippen oeffnet das Blatt, dort steht „delete"; die bestaetigte Aktion loescht ueber denselben Handler', async () => {
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
		// #3442: Das Blatt fragt selbst nach (kebab_seiten_bindung.test.ts AC-9) und meldet erst die BESTAETIGTE
		// Aktion an denselben Seiten-Handler wie das Desktop-Menue — der loescht dann direkt, ohne Seitendialog.
		const blatt = findeKomponenten(seite.ast, 'SubscriptionActionSheet');
		assert.equal(blatt.length, 1);
		assert.equal(attributAusdruck(blatt[0], seite.quelle, 'onAction'), attributAusdruck(kopfEinbettung(), seite.quelle, 'onSelect'), 'Blatt und Menue nutzen verschiedene Handler');
		const vorher = loeschAufrufe.length;
		(werte(attributAusdruck(blatt[0], seite.quelle, 'onAction')!, seite.u) as (id: string) => void)('delete');
		assert.notEqual(seite.u.deleteDialogOpen, true, '„delete" (bestaetigt im Blatt) oeffnet noch einen Seitendialog');
		assert.equal(loeschAufrufe.length, vorher + 1, 'die bestaetigte Loeschung aus dem Blatt erreicht deleteSubscription nicht');
	});
});
