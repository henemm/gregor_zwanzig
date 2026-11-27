// Issue #3442 Fix-Loop 1 — Mutations-Lücken des Adversary (F001, F002, F004) als Verhalten geschlossen.
// Spec: docs/specs/modules/feat_3442_kebab_rueckfragen.md — AC-16 (Listen unverändert), AC-6 (Abbrechen hält das
// Menü offen), AC-8 (Fokus nach dem Umschalten in der Rückfrage).
//
// Prüfstand wie kebab_seiten_bindung.test.ts: kein DOM (bits-ui rendert unter svelte/server nichts). Ausgewertet wird
// das ECHTE Instanz-Skript (svelteInstanzPruefstand.umgebungFuer) und die ECHTEN Attribut-Ausdrücke der Einbettungen;
// Seiten-Rückrufe sind Zähler. Jede Weitergabe (Karte → Kebab, Kebab → Panel) wird in IHRER Komponente ausgewertet.
//
// Pfadregel #1409: relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/kebab_rueckfragen_luecken_3442.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { collect, bedingungen, type Knoten } from './aktionsmodellAst.ts';
import { umgebungFuer, ohneTypen, werte, effekteVon } from './svelteInstanzPruefstand.ts';
import { baum, mitTestid } from '../hub-kopf/__tests__/htmlBaum.ts';
import { rueckfrage } from '../kebabBestaetigung.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const KOMP = path.resolve(HERE, '../..');
const KEBAB_DATEI = path.join(KOMP, 'molecules/SubscriptionKebab.svelte');
const PANEL_DATEI = path.join(KOMP, 'shared/KebabBestaetigungPanel.svelte');
const KARTE_DATEI = path.join(KOMP, 'organisms/SubscriptionCard.svelte');

const FRONTEND = path.resolve(KOMP, '../../..');
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');

const NAME = 'GR221 Mallorca';
type Umgebung = { ast: Knoten; quelle: string; u: Knoten };

function zaehler() {
	const aufrufe: unknown[][] = [];
	return { fn: (...a: unknown[]) => void aufrufe.push(a), aufrufe };
}
const ereignis = () => new Event('menu-select', { cancelable: true });

/** Ausführbarer Quelltext des Attributs `name` an `einbettung` (TS-Typen ausgeblendet); `null`, wenn es fehlt. */
function ausdruck(k: Umgebung, einbettung: Knoten, name: string): string | null {
	const a = (einbettung.attributes ?? []).find((x: Knoten) => x.type === 'Attribute' && x.name === name);
	if (!a) return null;
	const v = Array.isArray(a.value) ? a.value : [a.value];
	assert.ok(v.length === 1 && v[0]?.type === 'ExpressionTag', `Attribut ${name} an <${einbettung.name}> ist kein Ausdruck`);
	return ohneTypen(k.quelle, v[0].expression);
}
function pflicht(k: Umgebung, einbettung: Knoten, name: string): string {
	const a = ausdruck(k, einbettung, name);
	assert.ok(a, `Attribut ${name} fehlt an <${einbettung.name}>`);
	return a;
}

/** Alle Ausdrucks-Attribute einer Einbettung, in der Umgebung `k` ausgewertet (die Props, die das Kind bekommt). */
function propsAn(k: Umgebung, einbettung: Knoten): Knoten {
	const props: Knoten = {};
	for (const a of (einbettung.attributes ?? []) as Knoten[]) {
		if (a.type !== 'Attribute') continue;
		const v = Array.isArray(a.value) ? a.value : [a.value];
		if (v.length === 1 && v[0]?.type === 'ExpressionTag') props[a.name] = werte(ohneTypen(k.quelle, v[0].expression), k.u);
		else if (a.value === true) props[a.name] = true;
	}
	return props;
}

/** `$derived`-Werte neu herleiten (der Prüfstand wertet sie nur einmal beim Aufbau aus). */
function neuHerleiten(k: Umgebung): void {
	for (const stmt of (k.ast.instance?.content?.body ?? []) as Knoten[]) {
		if (stmt.type !== 'VariableDeclaration') continue;
		for (const d of stmt.declarations as Knoten[]) {
			if (d.id?.type !== 'Identifier' || !d.init) continue;
			if (!/^\$derived/.test(k.quelle.slice(d.init.start, d.init.end))) continue;
			k.u[d.id.name] = werte(ohneTypen(k.quelle, d.init), k.u);
		}
	}
}

function sichtbar(k: Umgebung, ziel: Knoten): boolean {
	const b = bedingungen(k.ast.fragment, ziel);
	assert.ok(b, `<${ziel.name}> steht nicht (erreichbar) im Markup`);
	return b.every((c) => Boolean(werte(c, k.u)));
}

const nachName = (k: Umgebung, name: string) => collect(k.ast.fragment, (n) => n.type === 'Component' && n.name === name);
const testidAusdruck = (n: Knoten) => JSON.stringify((n.attributes ?? []).find((a: Knoten) => a.name === 'data-testid')?.value ?? '');

/** Listeneintrag des Kebabs mit dem Aktionsobjekt `action` auslösen (echter onSelect, echtes abbrechbares Ereignis). */
function waehleImKebab(kebab: Umgebung, action: { id: string; label: string }): Event {
	const eintrag = nachName(kebab, 'DropdownMenu.Item').filter((n) => /subscription-action-/.test(testidAusdruck(n)));
	assert.equal(eintrag.length, 1, 'Listeneintrag (subscription-action-…) des Kebabs nicht genau einmal');
	kebab.u.action = action;
	const e = ereignis();
	(werte(pflicht(kebab, eintrag[0], 'onSelect'), kebab.u) as (e: Event) => void)(e);
	neuHerleiten(kebab);
	return e;
}

// ------------------------------------------------------------------------------------------------
// F001 (AC-16): die Listenkarte fragt NICHT im Menü nach — die Wahl geht sofort an die Liste (deren eigener Dialog).
// Das Listenmenü führt „Löschen“ (Archivieren steht laut subscriptionActions nicht in der Liste); gemessen in
// mehreren Lebenszyklen der Karte (aktiv, archiviert).
const LISTEN_ABOS = {
	aktiv: { id: 'c1', name: NAME, location_ids: ['a', 'b'], schedule: 'daily' },
	archiviert: { id: 'c2', name: NAME, location_ids: ['a', 'b'], schedule: 'daily', archived_at: '2026-11-01T00:00:00Z' }
};
describe('F001/AC-16: Kebab der Listenkarte (SubscriptionCard) — Löschen geht sofort an die Liste, keine Rückfrage im Menü', () => {
	const kebabDerKarte = async (sub: Knoten) => {
		const liste = zaehler();
		const karte = await umgebungFuer(
			KARTE_DATEI,
			// Aktiver Orts-Vergleich der Liste; `actions` setzt die Liste nicht (lokaler Name `actionsProp`).
			{ kind: 'vergleich', sub, onAction: liste.fn, dense: false, actionsProp: undefined },
			{ jsAlsTs: true }
		);
		const einb = nachName(karte, 'SubscriptionKebab');
		assert.equal(einb.length, 1, 'SubscriptionCard bettet SubscriptionKebab nicht genau einmal ein');
		assert.equal(sichtbar(karte, einb[0]), true, 'Vorbedingung: Listen-Kebab (nicht dense, mit onAction) sichtbar');
		// Die Props, die die Karte dem Kebab WIRKLICH gibt; der Kebab wertet ihre Defaults selbst aus.
		const kebab = await umgebungFuer(KEBAB_DATEI, propsAn(karte, einb[0]), { jsAlsTs: true });
		return { kebab, liste };
	};

	for (const [zustand, sub] of Object.entries(LISTEN_ABOS)) {
		const id = 'delete';
		test(`Karte (${zustand}): „${id}“ im Menü ⇒ sofort onAction('${id}') an die Liste, Menü schließt, keine Rückfrage im Menü`, async () => {
			const { kebab, liste } = await kebabDerKarte(sub);
			const panel = nachName(kebab, 'KebabBestaetigungPanel');
			assert.equal(panel.length, 1);
			const aktion = (kebab.u.actions as Array<{ id: string; label: string }>).find((a) => a.id === id);
			assert.ok(aktion, `Vorbedingung: das Listenmenü der Karte führt „${id}“ (${JSON.stringify(kebab.u.actions)})`);
			const e = waehleImKebab(kebab, aktion);
			assert.deepEqual(liste.aufrufe, [[id]], `die Liste bekommt „${id}“ nicht sofort (Listenkarte fragt im Menü nach)`);
			assert.equal(e.defaultPrevented, false, 'Listen-Menü bleibt offen (Rückfrage im Menü statt Listen-Dialog)');
			assert.equal(sichtbar(kebab, panel[0]), false, 'Listen-Menü zeigt die Hub-Rückfrage (kebab-rueckfrage)');
		});
	}
});

// ------------------------------------------------------------------------------------------------
// F002 (AC-6): „Abbrechen“ im Desktop-Menü hält das Menü offen (preventDefault) und zeigt wieder die Liste.
describe('F002/AC-6: „Abbrechen“ in der Rückfrage des Desktop-Menüs', () => {
	const kette = async (id: 'archive' | 'delete') => {
		const seite = zaehler();
		const kebab = await umgebungFuer(
			KEBAB_DATEI,
			{ actions: [{ id, label: id }], onSelect: seite.fn, mobil: false, name: NAME },
			{ jsAlsTs: true }
		);
		waehleImKebab(kebab, { id, label: id });
		const einb = nachName(kebab, 'KebabBestaetigungPanel');
		assert.equal(einb.length, 1);
		assert.equal(sichtbar(kebab, einb[0]), true, 'Vorbedingung: Rückfrage steht im Menü');
		// Panel mit den Props, die der Kebab ihm gibt (onAbbrechen/onBestaetigen sind die des Kebabs).
		const panel = await umgebungFuer(PANEL_DATEI, propsAn(kebab, einb[0]), { jsAlsTs: true });
		assert.equal(panel.u.imMenue, true, 'Vorbedingung: der Kebab bindet das Panel im Menü-Modus (imMenue)');
		const items = nachName(panel, 'DropdownMenu.Item');
		assert.equal(items.length, 1, 'Panel: Knopf als DropdownMenu.Item nicht genau einmal');
		const druecke = (was: 'abbrechen' | 'bestaetigen'): Event => {
			const k = (panel.u.knoepfe as Knoten[]).find((x) => x.was === was);
			assert.ok(k, `Panel hat keinen Knopf „${was}“`);
			const e = ereignis();
			(werte(pflicht(panel, items[0], 'onSelect'), Object.assign(Object.create(panel.u), { k })) as (e: Event) => void)(e);
			neuHerleiten(kebab);
			return e;
		};
		return { kebab, einb: einb[0], seite, druecke };
	};

	for (const id of ['archive', 'delete'] as const) {
		test(`„${id}“: Abbrechen ⇒ Menü bleibt offen (preventDefault), zeigt wieder die Liste, keine Wirkung`, async () => {
			const { kebab, einb, seite, druecke } = await kette(id);
			const e = druecke('abbrechen');
			assert.equal(e.defaultPrevented, true, 'Abbrechen schließt das Menü (kein preventDefault)');
			assert.equal(sichtbar(kebab, einb), false, 'nach Abbrechen steht noch die Rückfrage statt der Liste');
			assert.deepEqual(seite.aufrufe, [], 'Abbrechen löst eine Aktion aus');
		});

		test(`„${id}“: Bestätigen ⇒ Menü schließt (kein preventDefault), die Seite bekommt genau einmal „${id}“`, async () => {
			const { seite, druecke } = await kette(id);
			const e = druecke('bestaetigen');
			assert.equal(e.defaultPrevented, false, 'Bestätigen lässt das Menü offen');
			assert.deepEqual(seite.aufrufe, [[id]]);
		});
	}
});

// ------------------------------------------------------------------------------------------------
// F004 (AC-8): nach dem Umschalten liegt der Fokus in der Rückfrage, auf „Abbrechen“.
// Der Effekt-Rumpf des Panels läuft gegen ein Element, das das ECHT gerenderte Panel-Markup (svelte/server,
// imMenue=false: Btn rendert) abbildet; `focus()` zeichnet auf, welcher Knopf ihn bekam.
describe('F004/AC-8: Fokus nach dem Umschalten auf der Rückfrage', () => {
	for (const id of ['archive', 'delete'] as const) {
		test(`„${id}“: der Fokus-Effekt des Panels setzt den Fokus auf den Abbrechen-Knopf der Rückfrage`, async () => {
			const Panel = (await import(pathToFileURL(PANEL_DATEI).href)).default;
			const rf = rueckfrage(id, NAME)!;
			const w = baum(render(Panel, { props: { rueckfrage: rf, onBestaetigen: () => {}, onAbbrechen: () => {} } }).body);
			const rahmen = mitTestid(w, 'kebab-rueckfrage');
			assert.equal(rahmen.length, 1, 'Panel-Rahmen (kebab-rueckfrage) nicht genau einmal gerendert');
			const fokus: string[] = [];
			const box = {
				querySelector(sel: string) {
					const m = /^\[data-testid="([^"]+)"\]$/.exec(sel);
					assert.ok(m, `Fokus-Effekt sucht mit einem unerwarteten Selektor: ${sel}`);
					const treffer = mitTestid(rahmen[0], m[1]);
					if (treffer.length !== 1) return null;
					return { focus: () => void fokus.push(m[1]) };
				}
			};
			const panel = await umgebungFuer(PANEL_DATEI, { rueckfrage: rf, onBestaetigen: () => {}, onAbbrechen: () => {}, imMenue: true }, { jsAlsTs: true });
			panel.u.box = box;
			const effekte = effekteVon(panel.ast, panel.quelle, panel.u);
			assert.ok(effekte.length >= 1, 'Panel hat keinen Effekt (Fokus nach dem Umschalten fehlt)');
			for (const f of effekte) f();
			assert.deepEqual(fokus, ['kebab-rueckfrage-abbrechen'], 'Fokus liegt nach dem Umschalten nicht auf „Abbrechen“ der Rückfrage');
		});
	}
});
