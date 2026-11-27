// TDD RED — Issue #3442 (S5c aus #2797, Epic #2791): Rückfrage im Kebab-Menü statt Dialog — Bindung und Verhalten
// von SubscriptionKebab (Desktop), SubscriptionActionSheet (mobil), HubKopf und den beiden Hub-Seiten.
// Spec: docs/specs/modules/feat_3442_kebab_rueckfragen.md — AC-1, AC-3, AC-5, AC-6, AC-7, AC-9, AC-10, AC-13, AC-15.
//
// Prüfstand: kein DOM (bits-ui rendert unter svelte/server nichts). Gemessen wird (1) die Verdrahtung am AST des
// echten Svelte-Compilers (aktionsmodellAst) und (2) das VERHALTEN des echten Instanz-Skripts von Kebab und Blatt
// (svelteInstanzPruefstand.umgebungFuer): der Menüeintrag wird mit einem echten abbrechbaren Ereignis ausgelöst, die
// Seite (onSelect/onAction) ist ein Zähler, der nur aufzeichnet, was ankommt.
//
// VERTRAG für den Developer (zusätzlich zum Modell, siehe kebab_bestaetigung.test.ts):
//   frontend/src/lib/components/shared/KebabBestaetigungPanel.svelte — geteiltes Panel; Props
//     rueckfrage: KebabRueckfrage            (Ergebnis von kebabBestaetigung.rueckfrage(id, name))
//     onBestaetigen: () => void              (Bestätigen; der Aufrufer führt erst dann die Aktion aus)
//     onAbbrechen: () => void                (zurück zur Liste, ohne Wirkung)
//     data-abschnitt am Panel aus rueckfrage.abschnitt (kebab-bestaetigung-archivieren / -loeschen)
//   SubscriptionKebab: neue Prop `name`; Listeneintrag ruft bei Rückfrage-Aktionen event.preventDefault() und zeigt
//     das Panel statt onSelect; DropdownMenu.Root setzt den Rückfrage-Zustand über onOpenChange zurück;
//     data-abschnitt="kebab-menue" an der Menüliste.
//   SubscriptionActionSheet: bei Rückfrage-Aktionen Panel statt sofort onAction+onClose.
//
// Pfadregel #1409: relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/kebab_seiten_bindung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
	ladeSvelte,
	komponenten,
	collect,
	attrKurz,
	importe,
	erreichbar,
	bedingungen,
	kurz,
	mitAttribut,
	type Knoten
} from './aktionsmodellAst.ts';
import { umgebungFuer, ohneTypen, werte } from './svelteInstanzPruefstand.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(HERE, '../../../..');
const REPO = path.resolve(SRC, '../..');
const KOMP = path.join(SRC, 'lib/components');
const KEBAB_DATEI = path.join(KOMP, 'molecules/SubscriptionKebab.svelte');
const SHEET_DATEI = path.join(KOMP, 'mobile/SubscriptionActionSheet.svelte');
const PANEL_DATEI = path.join(KOMP, 'shared/KebabBestaetigungPanel.svelte');
const HUBKOPF_DATEI = path.join(KOMP, 'shared/hub-kopf/HubKopf.svelte');
const TRIP_HUB = ladeSvelte(path.join(SRC, 'routes/trips/[id]/+page.svelte'));
const CMP_HUB = ladeSvelte(path.join(SRC, 'routes/compare/[id]/+page.svelte'));
const SEITEN = [
	['Trip-Hub', TRIP_HUB],
	['Compare-Hub', CMP_HUB]
] as const;

const NAME = 'GR221 Mallorca';

async function modell(): Promise<Knoten> {
	try {
		return await import('../kebabBestaetigung.ts');
	} catch (e) {
		assert.fail(`TDD RED: shared/kebabBestaetigung.ts fehlt oder lädt nicht (${(e as Error).message})`);
	}
}

/** Echtes abbrechbares Ereignis (wie bits-ui es an onSelect gibt). */
const ereignis = () => new Event('menu-select', { cancelable: true });

/** Zähler für die Seite: zeichnet auf, was ankommt (keine eigene Logik). */
function zaehler() {
	const aufrufe: unknown[][] = [];
	const fn = (...a: unknown[]) => void aufrufe.push(a);
	return { fn, aufrufe };
}

/** Ausdruck des Attributs `name` an `einbettung` als ausführbarer Quelltext (TS-Typen ausgeblendet). */
function ausdruck(quelle: string, einbettung: Knoten, name: string): string {
	const a = (einbettung.attributes ?? []).find((x: Knoten) => x.type === 'Attribute' && x.name === name);
	assert.ok(a, `Attribut ${name} fehlt an <${einbettung.name}>`);
	const v = Array.isArray(a.value) ? a.value : [a.value];
	assert.ok(v.length === 1 && v[0]?.type === 'ExpressionTag', `Attribut ${name} ist kein Ausdruck`);
	return ohneTypen(quelle, v[0].expression);
}

/** `$derived`-Werte neu herleiten (der Prüfstand wertet sie sonst nur einmal beim Aufbau aus). */
function neuHerleiten(k: { ast: Knoten; quelle: string; u: Knoten }): void {
	for (const stmt of (k.ast.instance?.content?.body ?? []) as Knoten[]) {
		if (stmt.type !== 'VariableDeclaration') continue;
		for (const d of stmt.declarations as Knoten[]) {
			if (d.id?.type !== 'Identifier' || !d.init) continue;
			if (!/^\$derived/.test(k.quelle.slice(d.init.start, d.init.end))) continue;
			k.u[d.id.name] = werte(ohneTypen(k.quelle, d.init), k.u);
		}
	}
}

/** Ist die Einbettung `ziel` im aktuellen Zustand sichtbar (alle umgebenden Bedingungen wahr)? */
function sichtbar(k: { ast: Knoten; u: Knoten }, ziel: Knoten): boolean {
	const b = bedingungen(k.ast.fragment, ziel);
	assert.ok(b, `<${ziel.name}> steht nicht (erreichbar) im Markup`);
	return b.every((c) => Boolean(werte(c, k.u)));
}

const mitTestidPraefix = (wurzel: Knoten, praefix: string) =>
	collect(wurzel, (n) =>
		(n.type === 'RegularElement' || n.type === 'Component') &&
		(n.attributes ?? []).some(
			(a: Knoten) =>
				a.name === 'data-testid' &&
				Array.isArray(a.value) &&
				a.value.some((v: Knoten) => v.type === 'Text' && String(v.data).startsWith(praefix))
		)
	);

function panelEinbettung(ast: Knoten, wo: string): Knoten {
	const p = komponenten(ast, 'KebabBestaetigungPanel');
	assert.equal(p.length, 1, `TDD RED: ${wo} bindet KebabBestaetigungPanel nicht genau einmal ein (gefunden ${p.length})`);
	return p[0];
}

const AKTIONEN = [
	{ id: 'pause', label: 'Pausieren' },
	{ id: 'archive', label: 'Archivieren …' },
	{ id: 'delete', label: 'Löschen …', danger: true }
];

// ------------------------------------------------------------------------------------------------
describe('AC-13: ein Panel-Baustein, Abschnitt-Haken, Name bis zum Kebab', () => {
	test('KebabBestaetigungPanel existiert und trägt data-abschnitt aus rueckfrage.abschnitt', () => {
		assert.ok(existsSync(PANEL_DATEI), 'TDD RED: shared/KebabBestaetigungPanel.svelte fehlt');
		const ast = ladeSvelte(PANEL_DATEI);
		const haken = collect(ast.fragment, (n) => n.type === 'RegularElement' && (n.attributes ?? []).some((a: Knoten) => a.name === 'data-abschnitt'));
		assert.equal(haken.length, 1, 'Panel: genau ein Element mit data-abschnitt erwartet');
		assert.equal(attrKurz(haken[0], 'data-abschnitt'), 'rueckfrage.abschnitt');
	});

	test('SubscriptionKebab und SubscriptionActionSheet binden dasselbe Panel; keine Compare-eigene Variante', () => {
		panelEinbettung(ladeSvelte(KEBAB_DATEI), 'SubscriptionKebab');
		panelEinbettung(ladeSvelte(SHEET_DATEI), 'SubscriptionActionSheet');
		for (const [name, ast] of SEITEN) {
			assert.equal(komponenten(ast, 'KebabBestaetigungPanel').length, 0, `${name} baut die Rückfrage selbst`);
		}
	});

	test('SubscriptionKebab: Menüliste trägt data-abschnitt="kebab-menue"', () => {
		assert.equal(mitAttribut(ladeSvelte(KEBAB_DATEI), 'data-abschnitt', 'kebab-menue').length, 1);
	});

	test('HubKopf reicht den Namen an den Kebab (name={name})', () => {
		const k = komponenten(ladeSvelte(HUBKOPF_DATEI), 'SubscriptionKebab');
		assert.equal(k.length, 1);
		assert.equal(attrKurz(k[0], 'name'), 'name', 'HubKopf gibt den Namen nicht an SubscriptionKebab weiter');
	});

	test('beide Seiten geben dem Aktionsblatt den Namen des Abos (Rückfrage nennt ihn)', () => {
		assert.equal(attrKurz(komponenten(TRIP_HUB, 'SubscriptionActionSheet')[0], 'name'), 'trip.name');
		assert.equal(attrKurz(komponenten(CMP_HUB, 'SubscriptionActionSheet')[0], 'name'), 'currentPreset.name');
	});
});

// ------------------------------------------------------------------------------------------------
describe('AC-1/AC-3/AC-6/AC-7: Desktop-Kebab fragt im Menü nach; erst die Bestätigung erreicht die Seite', async () => {
	const kebab = async () => {
		const seite = zaehler();
		const k = await umgebungFuer(KEBAB_DATEI, { actions: AKTIONEN, onSelect: seite.fn, mobil: false, name: NAME }, { jsAlsTs: true });
		const eintraege = mitTestidPraefix(k.ast.fragment, 'subscription-action-').filter((n) => n.name === 'DropdownMenu.Item');
		assert.equal(eintraege.length, 1, 'Listeneintrag (DropdownMenu.Item, data-testid subscription-action-…) nicht genau einmal');
		const waehle = (id: string) => {
			k.u.action = AKTIONEN.find((a) => a.id === id);
			const e = ereignis();
			(werte(ausdruck(k.quelle, eintraege[0], 'onSelect'), k.u) as (e: Event) => void)(e);
			neuHerleiten(k);
			return e;
		};
		return { k, seite, waehle };
	};

	for (const id of ['delete', 'archive'] as const) {
		test(`„${id}“ wählen: Menü bleibt offen (preventDefault), Seite bekommt NICHTS, Panel zeigt rueckfrage('${id}', Name)`, async () => {
			const m = await modell();
			const { k, seite, waehle } = await kebab();
			const panel = panelEinbettung(k.ast, 'SubscriptionKebab');
			assert.equal(sichtbar(k, panel), false, 'Vorbedingung: Panel zu');
			const e = waehle(id);
			assert.equal(e.defaultPrevented, true, `„${id}“ schließt das Menü (kein preventDefault)`);
			assert.deepEqual(seite.aufrufe, [], `„${id}“ erreicht die Seite ohne Rückfrage`);
			assert.equal(sichtbar(k, panel), true, 'Rückfrage-Panel erscheint nicht');
			assert.deepEqual(werte(ausdruck(k.quelle, panel, 'rueckfrage'), k.u), m.rueckfrage(id, NAME));
		});

		test(`„${id}“ bestätigen ⇒ die Seite bekommt genau einmal onSelect('${id}')`, async () => {
			const { k, seite, waehle } = await kebab();
			waehle(id);
			const panel = panelEinbettung(k.ast, 'SubscriptionKebab');
			(werte(ausdruck(k.quelle, panel, 'onBestaetigen'), k.u) as () => void)();
			assert.deepEqual(seite.aufrufe, [[id]]);
		});

		test(`„${id}“ abbrechen ⇒ zurück zur Liste, keine Wirkung (AC-6)`, async () => {
			const { k, seite, waehle } = await kebab();
			waehle(id);
			const panel = panelEinbettung(k.ast, 'SubscriptionKebab');
			(werte(ausdruck(k.quelle, panel, 'onAbbrechen'), k.u) as () => void)();
			neuHerleiten(k);
			assert.deepEqual(seite.aufrufe, []);
			assert.equal(sichtbar(k, panel), false, 'nach Abbrechen steht noch die Rückfrage');
		});
	}

	test('Menü schließen (Escape/Außenklick, onOpenChange(false)) setzt die Rückfrage zurück (AC-7)', async () => {
		const { k, seite, waehle } = await kebab();
		waehle('delete');
		const roots = collect(k.ast.fragment, (n) => n.type === 'Component' && n.name === 'DropdownMenu.Root');
		assert.equal(roots.length, 1);
		(werte(ausdruck(k.quelle, roots[0], 'onOpenChange'), k.u) as (o: boolean) => void)(false);
		neuHerleiten(k);
		assert.equal(sichtbar(k, panelEinbettung(k.ast, 'SubscriptionKebab')), false, 'Wiederöffnen zeigte die Rückfrage statt der Liste');
		assert.deepEqual(seite.aufrufe, []);
	});

	test('„pause“ hat keine Rückfrage: sofort onSelect(\'pause\'), Menü schließt normal (AC-11)', async () => {
		const { k, seite, waehle } = await kebab();
		const e = waehle('pause');
		assert.equal(e.defaultPrevented, false);
		assert.deepEqual(seite.aufrufe, [['pause']]);
		assert.equal(sichtbar(k, panelEinbettung(k.ast, 'SubscriptionKebab')), false);
	});
});

// ------------------------------------------------------------------------------------------------
describe('AC-9: mobiles Aktionsblatt fragt im Blatt nach; schließt erst nach Bestätigung', async () => {
	const blatt = async () => {
		const seite = zaehler();
		const zu = zaehler();
		const k = await umgebungFuer(
			SHEET_DATEI,
			{ open: true, onClose: zu.fn, kind: 'trip', status: 'active', onAction: seite.fn, name: NAME, surface: 'hub' },
			{ jsAlsTs: true }
		);
		const knoepfe = mitTestidPraefix(k.ast.fragment, 'subscription-action-').filter((n) => n.name === 'button');
		assert.equal(knoepfe.length, 1, 'Aktionszeile (button, data-testid subscription-action-…) nicht genau einmal');
		const tippe = (id: string) => {
			k.u.action = { id, label: id };
			(werte(ausdruck(k.quelle, knoepfe[0], 'onclick'), k.u) as (e: Event) => void)(new Event('click'));
			neuHerleiten(k);
		};
		return { k, seite, zu, tippe };
	};

	for (const id of ['delete', 'archive'] as const) {
		test(`„${id}“ tippen: Blatt bleibt offen, Rückfrage im Blatt, Seite bekommt nichts`, async () => {
			const m = await modell();
			const { k, seite, zu, tippe } = await blatt();
			const panel = panelEinbettung(k.ast, 'SubscriptionActionSheet');
			tippe(id);
			assert.deepEqual(seite.aufrufe, [], `„${id}“ erreicht die Seite ohne Rückfrage`);
			assert.deepEqual(zu.aufrufe, [], 'Blatt schließt vor der Bestätigung');
			assert.equal(sichtbar(k, panel), true);
			assert.deepEqual(werte(ausdruck(k.quelle, panel, 'rueckfrage'), k.u), m.rueckfrage(id, NAME));
		});

		test(`„${id}“ bestätigen ⇒ onAction('${id}') genau einmal, dann schließt das Blatt`, async () => {
			const { k, seite, zu, tippe } = await blatt();
			tippe(id);
			(werte(ausdruck(k.quelle, panelEinbettung(k.ast, 'SubscriptionActionSheet'), 'onBestaetigen'), k.u) as () => void)();
			assert.deepEqual(seite.aufrufe, [[id]]);
			assert.equal(zu.aufrufe.length, 1);
		});

		test(`„${id}“ abbrechen ⇒ zurück zur Aktionsliste, Blatt bleibt offen, keine Wirkung`, async () => {
			const { k, seite, zu, tippe } = await blatt();
			tippe(id);
			const panel = panelEinbettung(k.ast, 'SubscriptionActionSheet');
			(werte(ausdruck(k.quelle, panel, 'onAbbrechen'), k.u) as () => void)();
			neuHerleiten(k);
			assert.deepEqual(seite.aufrufe, []);
			assert.deepEqual(zu.aufrufe, []);
			assert.equal(sichtbar(k, panel), false);
		});
	}

	test('„unarchive“ (ohne Rückfrage) wirkt sofort und schließt das Blatt (AC-10)', async () => {
		const { seite, zu, tippe } = await blatt();
		tippe('unarchive');
		assert.deepEqual(seite.aufrufe, [['unarchive']]);
		assert.equal(zu.aufrufe.length, 1);
	});
});

// ------------------------------------------------------------------------------------------------
describe('AC-1/AC-5/AC-13: Hub-Seiten ohne eigene Dialoge; Löschen nur über den bestätigten Menüweg', () => {
	for (const [name, ast] of SEITEN) {
		test(`${name}: kein ConfirmDialog mehr (weder eingebunden noch importiert)`, () => {
			assert.equal(komponenten(ast, 'ConfirmDialog').length, 0, `${name} bindet noch ConfirmDialog ein`);
			assert.ok(
				!importe(ast).some((i) => i.namen.includes('ConfirmDialog') || /ConfirmDialog/.test(i.quelle)),
				`${name} importiert noch ConfirmDialog`
			);
		});

		test(`${name}: Meldungen kommen aus dem geteilten Modell (erfolgsText, fehlerText)`, () => {
			const imp = importe(ast).filter((i) => /kebabBestaetigung/.test(i.quelle));
			assert.equal(imp.length, 1, `${name} importiert kebabBestaetigung nicht`);
			for (const f of ['erfolgsText', 'fehlerText']) assert.ok(imp[0].namen.includes(f), `${name}: ${f} nicht importiert`);
		});

		test(`${name}: deleteSubscription ist nur vom Menü-/Blatt-Weg erreichbar (den der Kebab erst nach Bestätigung auslöst)`, () => {
			const quellen: string[] = [];
			for (const el of collect(ast.fragment, (n) => n.type === 'Component' || n.type === 'RegularElement')) {
				for (const a of (el.attributes ?? []) as Knoten[]) {
					if (a.type !== 'Attribute') continue;
					const v = Array.isArray(a.value) ? a.value : [a.value];
					if (!(v.length === 1 && v[0]?.type === 'ExpressionTag')) continue;
					if (erreichbar(ast, v[0].expression).bezeichner.has('deleteSubscription')) quellen.push(`${el.name}.${a.name}`);
				}
			}
			const kopf = collect(ast.fragment, (n) => n.type === 'Component' && (n.attributes ?? []).some((a: Knoten) => a.name === 'onTest'));
			assert.equal(kopf.length, 1);
			assert.deepEqual(quellen.sort(), [`${kopf[0].name}.onSelect`, 'SubscriptionActionSheet.onAction'].sort());
		});
	}

	test('Compare-Hub: Archivieren und Reaktivieren bleiben auf der Seite (kein href-Sprung, kein Reload) (AC-5/AC-10)', () => {
		const handler = collect(CMP_HUB.fragment, (n) => n.type === 'Component' && n.name === 'SubscriptionActionSheet')[0];
		const onAction = (handler.attributes as Knoten[]).find((a) => a.name === 'onAction')!.value.expression;
		const binds = erreichbar(CMP_HUB, onAction);
		// den Zweig der jeweiligen Aktion im Dispatch finden und nur SEINEN Aufrufgraphen prüfen
		for (const id of ['archive', 'unarchive']) {
			const zweige = collect(binds.knoten, (n) => n.type === 'IfStatement' && new RegExp(`id === "${id}"`).test(kurz(n.test)));
			assert.equal(zweige.length, 1, `Dispatch-Zweig für „${id}“ nicht genau einmal`);
			const r = erreichbar(CMP_HUB, zweige[0].consequent);
			const spruenge = collect(r.knoten, (n) =>
				(n.type === 'AssignmentExpression' && /location(\.href)?$/.test(kurz(n.left))) ||
				(n.type === 'CallExpression' && /location\.(reload|assign|replace)$/.test(kurz(n.callee))) ||
				(n.type === 'CallExpression' && kurz(n.callee) === 'goto')
			).map(kurz);
			assert.deepEqual(spruenge, [], `„${id}“ verlässt bzw. lädt die Seite neu: ${spruenge.join(' | ')}`);
			assert.ok(r.bezeichner.has('setArchived'), `„${id}“ erreicht setArchived nicht`);
		}
	});
});

// ------------------------------------------------------------------------------------------------
// doc-compliance-test (Datenprüfung: liest die Elementliste und die Besitzer-Liste als DATEN, AC-15)
describe('AC-15: Besitzer-Einträge kebab-* sind entfernt, die Abschnitte stehen weiter in der Elementliste', () => {
	const besitzer = JSON.parse(readFileSync(path.join(REPO, 'docs/context/einstellungen_neu/elementliste_besitzer.json'), 'utf-8'));
	const elementliste = JSON.parse(readFileSync(path.join(REPO, 'docs/context/einstellungen_neu/elementliste.json'), 'utf-8'));
	test('elementliste_besitzer.json: kein Eintrag mit abschnitt kebab-*', () => {
		const rest = [...(besitzer.besitzer ?? []), ...(besitzer.ausnahmen ?? [])]
			.filter((e: Knoten) => typeof e.abschnitt === 'string' && e.abschnitt.startsWith('kebab-'))
			.map((e: Knoten) => `${e.ctx}/${e.abschnitt}`);
		assert.deepEqual(rest, [], `noch Besitzer-Einträge: ${rest.join(', ')}`);
	});
	test('Vorbedingung: die Elementliste führt die drei Abschnitte für trip und orte', () => {
		for (const ctx of ['trip', 'orte'])
			for (const ab of ['kebab-menue', 'kebab-bestaetigung-archivieren', 'kebab-bestaetigung-loeschen'])
				assert.ok(
					elementliste.elemente.some((e: Knoten) => e.ctx === ctx && e.abschnitt === ab),
					`Elementliste ohne ${ctx}/${ab}`
				);
	});
});
