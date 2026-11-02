// Fix-Loop 1 — Issue #2727 (Epic #2345, DoD-1): compareWizardState ablösen.
// Spec: docs/specs/modules/feat_2727_compare_wizardstate_abloesen.md — AC-6
// Adversary-Findings F001 (HIGH) / F002 (MEDIUM), docs/artifacts/feat-2727-compare-wizardstate/adversary-dialog.md
//
// Der Anlege-Editor `/compare/new` bettet den Schritt „Orte" ZWEIMAL ein: im Desktop-Rahmen
// (`.cm-desktop`) und im Mobil-Rahmen (`.cm-mobile`, `dense` + Bibliotheks-Sheet). Beide Rahmen
// stehen im Markup, sichtbar ist je Viewport einer (CSS). Abgesichert war nur der Desktop-Mount —
// hier wird der MOBILE gemessen, dort wo die Zusicherung wirkt:
//
//   (a) Serverseitiges Rendern (svelte/server, ECHTE Komponenten, `bind:` echt kompiliert): die im
//       Editor-Zustand gewählten Orte erscheinen im MOBILEN Orte-Schritt nummeriert, in Auswahl-
//       Reihenfolge. Ohne `bind:pickedIds={wiz.pickedIds}` am mobilen Mount bliebe die Liste dort
//       leer („Noch keine Orte gewählt"), Auswahl im Sheet und Anzeige liefen auseinander.
//       SSR belegt die Richtung Editor → Schritt. Die Rückrichtung (✕ im Schritt schreibt
//       `wiz.pickedIds`, `orteContinueReady`, POST) misst der Instanz-Prüfstand unten — auch eine
//       zur Einweg-Prop herabgestufte Bindung (`pickedIds={wiz.pickedIds}`) wird dort rot.
//   (b) `dense` wirkt mobil: Mobil-Stapel mit Bibliotheks-Knopf, OHNE Smart-Import-Raster des
//       Desktops. `onOpenLibrary`: der Knopf des ECHTEN Step2Orte-Skripts (sein onclick-Ausdruck,
//       gegen die Props ausgewertet, die der Editor am mobilen Mount wirklich setzt) öffnet das
//       Bibliotheks-Sheet des Editors (`<Sheet open={mobileLibraryOpen}>`).
//
// Kein Mock: Rendern über svelte/server, Instanz-Skripte über svelteInstanzPruefstand.ts.
//
// Ausführen (aus frontend/):
//   node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks \
//     --test src/lib/components/shared/__tests__/compare_new_editor_mobil_orte_schritt.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { lade, renderKomponente, testids, innen, sichtbarerText } from './infoboxSsr.ts';
import { findeKomponenten, attributAusdruck, umgebungFuer, werte, ohneTypen, type Knoten } from './svelteInstanzPruefstand.ts';
import { derivedNeu } from './standardwerteEditorPruefstand.ts';
import { fetchMitschnitt, vergleichEditor } from './compareNeuEditorPruefstand.ts';

let netz: ReturnType<typeof fetchMitschnitt>;
beforeEach(() => {
	netz = fetchMitschnitt('cmp-neu');
});
afterEach(() => {
	netz.abbauen();
});

const HIER = dirname(fileURLToPath(import.meta.url));
const STEP2 = join(HIER, '..', '..', 'compare', 'steps', 'Step2Orte.svelte');

const ORTE = [
	{ id: 'loc-a', name: 'Alpbach', lat: 47.4, lon: 11.9 },
	{ id: 'loc-b', name: 'Brixen', lat: 46.7, lon: 11.6 },
	{ id: 'loc-c', name: 'Cortina', lat: 46.5, lon: 12.1 }
];

const MOBIL_ANKER = 'data-testid="cm-mobile-head"';

async function renderMobilOrte(pickedIds: string[]): Promise<{ desktop: string; mobil: string }> {
	const Editor = await lade('compare-new/CompareNewEditor.svelte');
	const html = renderKomponente(Editor, {
		locations: ORTE,
		stateOverride: { activeTab: 'orte', isMobileViewport: true, name: 'Dolomiten', pickedIds }
	});
	const ab = html.indexOf(MOBIL_ANKER);
	assert.ok(ab > 0, 'Messaufbau: Mobil-Rahmen (cm-mobile-head) fehlt im gerenderten Editor');
	return { desktop: html.slice(0, ab), mobil: html.slice(ab) };
}

describe('AC-6 mobil (F001): Auswahl des Editors erreicht den mobilen Orte-Schritt', () => {
	test('gewählte Orte erscheinen im MOBILEN Schritt nummeriert, in Auswahl-Reihenfolge', async () => {
		const { desktop, mobil } = await renderMobilOrte(['loc-c', 'loc-a']);
		// Positivkontrolle: der Desktop-Mount zeigt die Auswahl ebenfalls (getrennte Quelle).
		assert.deepEqual(testids(desktop, 'compare-step2-picked-item-'), ['compare-step2-picked-item-loc-c', 'compare-step2-picked-item-loc-a']);
		assert.deepEqual(
			testids(mobil, 'compare-step2-picked-item-'),
			['compare-step2-picked-item-loc-c', 'compare-step2-picked-item-loc-a'],
			'mobiler Orte-Schritt zeigt die Auswahl des Editors nicht — bind:pickedIds am mobilen Step2Orte fehlt?'
		);
		const text = sichtbarerText(mobil);
		assert.match(text, /1\s+Cortina/, `Nummerierung mobil fehlt: ${text.slice(0, 300)}`);
		assert.match(text, /2\s+Alpbach/, `Nummerierung mobil fehlt: ${text.slice(0, 300)}`);
		assert.doesNotMatch(text, /Noch keine Orte gewählt/, 'mobiler Schritt meldet trotz Auswahl „Noch keine Orte"');
		assert.match(sichtbarerText(innen(mobil, 'compare-step2-counter')), /passt/, 'mobiler Zähler reagiert nicht auf die Auswahl');
	});

	test('mobiler Zähler und Weiter-Knopf folgen der Auswahl (1 Ort ⇒ gesperrt, 2 Orte ⇒ frei)', async () => {
		const einer = await renderMobilOrte(['loc-b']);
		assert.deepEqual(testids(einer.mobil, 'compare-step2-picked-item-'), ['compare-step2-picked-item-loc-b']);
		assert.match(sichtbarerText(innen(einer.mobil, 'compare-step2-counter')), /min\. 2/);
		assert.match(sichtbarerText(einer.mobil), /noch 1 Ort nötig/);
		const zwei = await renderMobilOrte(['loc-b', 'loc-a']);
		assert.match(sichtbarerText(zwei.mobil), /Wetter-Metriken →/);
		assert.doesNotMatch(sichtbarerText(zwei.mobil), /Ort(e)? nötig/);
	});
});

// ── Rückrichtung: Abwählen IM mobilen Schritt erreicht den Editor-Zustand und den POST ─────────
//
// Die Bindung wird aus dem AST-Knoten `BindDirective pickedIds` am mobilen Mount gebaut (Getter/
// Setter auf den gebundenen Ausdruck im Editor-Skript, so wie Svelte `bind:` kompiliert) — nicht
// aus einem angenommenen Wert. Fehlt der Knoten (Bindung entfernt oder zur Einweg-Prop
// `pickedIds={…}` herabgestuft), bekommt der Schritt nur den Wert: echte Einweg-Semantik, das
// Abwählen bleibt lokal. Gehandelt wird über den ECHTEN onclick-Ausdruck des ✕-Knopfs im
// `{#if dense}`-Zweig von Step2Orte.

async function mobilerSchritt(pickedIds: string[]) {
	return orteSchrittAmMount('mobil', pickedIds);
}

/** Editor + ECHTES Step2Orte-Skript am gewählten Mount (`mobil` = nach `cm-mobile-head`,
 *  `desktop` = davor), die Bindung aus dem BindDirective-Knoten dieses Mounts. Liefert die echten
 *  Handler des jeweiligen Zweigs: ✕-Abwählen und (Desktop) Bibliotheks-Kachel = `togglePick`. */
async function orteSchrittAmMount(mount: 'mobil' | 'desktop', pickedIds: string[]) {
	const e = await vergleichEditor({
		stateOverride: {
			activeTab: 'orte', isMobileViewport: mount === 'mobil', metrikenVisited: true, idealsVisited: true, alarmeVisited: true,
			name: 'Dolomiten', pickedIds
		},
		locations: ORTE
	});
	const anker = e.quelle.indexOf(MOBIL_ANKER);
	assert.ok(anker > 0, 'Messaufbau: cm-mobile-head fehlt im Editor-Quelltext');
	const mounts = findeKomponenten(e.ast, 'Step2Orte').filter((k) => (mount === 'mobil' ? k.start > anker : k.start < anker));
	assert.equal(mounts.length, 1, `Messaufbau: erwartet genau einen ${mount}-Step2Orte, gefunden ${mounts.length}`);
	const mobil = mounts;
	const bindung = (mobil[0].attributes as Knoten[]).find((a) => a.type === 'BindDirective' && a.name === 'pickedIds');
	const wertAusdruck = bindung
		? e.quelle.slice(bindung.expression.start, bindung.expression.end)
		: attributAusdruck(mobil[0], e.quelle, 'pickedIds');
	const s = await umgebungFuer(
		STEP2,
		{ locations: ORTE, groups: [], dense: mount === 'mobil', pickedIds: wertAusdruck ? werte(wertAusdruck, e.u) : undefined, $bindable: (v: unknown) => v },
		{ jsAlsTs: true }
	);
	if (bindung) {
		const ausdruck = e.quelle.slice(bindung.expression.start, bindung.expression.end);
		Object.defineProperty(s.u, 'pickedIds', {
			get: () => werte(ausdruck, e.u),
			set: (v: unknown) => new Function('u', 'v', `with (u) { ${ausdruck} = v; }`)(e.u, v),
			configurable: true,
			enumerable: true
		});
	}
	// Zweig-Grenzen im Markup von Step2Orte: Desktop = `{#if !dense}`, Mobil = `{#if dense}`.
	const denseAb = s.quelle.indexOf('{#if dense}');
	const desktopAb = s.quelle.indexOf('{#if !dense}');
	assert.ok(denseAb > 0 && desktopAb > 0 && desktopAb < denseAb, 'Messaufbau: dense-/Desktop-Zweig in Step2Orte fehlt');
	const zweigAb = mount === 'mobil' ? denseAb : desktopAb;
	const handlerVon = (knopf: Knoten | null, was: string) => {
		assert.ok(knopf && (mount === 'mobil' || knopf.start < denseAb), `Messaufbau: ${was} im ${mount}-Zweig fehlt`);
		const onclick = (knopf.attributes as Knoten[]).find((a) => a.type === 'Attribute' && a.name === 'onclick');
		assert.ok(onclick?.value?.expression, `Messaufbau: ${was} ohne onclick`);
		const q = ohneTypen(s.quelle, onclick.value.expression);
		return (id: string) =>
			(new Function('u', 's', `with (u) { with (s) { return (${q}); } }`)(s.u, { loc: { id } }) as () => void)();
	};
	const entferne = handlerVon(knopfMitTestidPraefix(s.ast, 'compare-step2-picked-remove-', zweigAb), '✕-Knopf');
	// Desktop-Bibliothek: erste Kachel (Knopf) im Element `compare-step2-library`.
	const bibAb = s.quelle.indexOf('data-testid="compare-step2-library"');
	const waehle = mount === 'desktop' ? handlerVon(knopfMitTestidPraefix(s.ast, '', bibAb), 'Bibliotheks-Kachel') : null;
	return { e, entferne, waehle };
}

describe('AC-6 mobil (F001): Abwählen im mobilen Orte-Schritt wirkt im Editor-Zustand', () => {
	test('✕ an einem Ort ⇒ wiz.pickedIds ohne ihn, Weiter bleibt frei, POST ohne den Ort', async () => {
		const { e, entferne } = await mobilerSchritt(['loc-a', 'loc-b', 'loc-c']);
		entferne('loc-a');
		derivedNeu(e);
		assert.deepEqual(
			e.u.wiz.pickedIds,
			['loc-b', 'loc-c'],
			'Abwählen im mobilen Orte-Schritt erreicht den Editor-Zustand nicht — bind:pickedIds am mobilen Step2Orte fehlt oder ist einweg?'
		);
		assert.equal(e.u.orteContinueReady, true);
		await e.u.handleActivate();
		assert.deepEqual(netz.presetPosts().map((p) => p.koerper?.location_ids), [['loc-b', 'loc-c']], 'POST trägt den mobil abgewählten Ort weiter');
	});

	test('✕ an zwei von drei Orten ⇒ Editor hält 1 Ort, Weiter gesperrt', async () => {
		const { e, entferne } = await mobilerSchritt(['loc-a', 'loc-b', 'loc-c']);
		entferne('loc-a');
		entferne('loc-c');
		derivedNeu(e);
		assert.deepEqual(e.u.wiz.pickedIds, ['loc-b'], 'Abwählen im mobilen Orte-Schritt erreicht den Editor-Zustand nicht');
		assert.equal(e.u.orteContinueReady, false, 'Weiter-Knopf bleibt trotz nur 1 Ort frei');
		assert.equal(e.u.orteOk, false);
	});
});

describe('AC-6 Desktop: Aus-/Abwählen im Desktop-Orte-Schritt wirkt im Editor-Zustand und im POST', () => {
	test('Bibliotheks-Kachel wählt einen Ort aus ⇒ wiz.pickedIds, Weiter frei, POST mit beiden Orten', async () => {
		const { e, waehle } = await orteSchrittAmMount('desktop', ['loc-b']);
		derivedNeu(e);
		assert.equal(e.u.orteContinueReady, false, 'Vorbedingung: 1 Ort ⇒ Weiter gesperrt');
		// onclick der Bibliotheks-Kachel (`() => togglePick(loc.id)`) für die Kachel von loc-a.
		waehle!('loc-a');
		derivedNeu(e);
		assert.deepEqual(
			e.u.wiz.pickedIds,
			['loc-b', 'loc-a'],
			'Auswählen im Desktop-Orte-Schritt erreicht den Editor-Zustand nicht — bind:pickedIds am Desktop-Step2Orte fehlt oder ist einweg?'
		);
		assert.equal(e.u.orteContinueReady, true);
		await e.u.handleActivate();
		assert.deepEqual(netz.presetPosts().map((p) => p.koerper?.location_ids), [['loc-b', 'loc-a']], 'POST trägt die Desktop-Auswahl nicht');
	});

	test('✕ an einem Ort ⇒ wiz.pickedIds ohne ihn, POST ohne den Ort', async () => {
		const { e, entferne } = await orteSchrittAmMount('desktop', ['loc-a', 'loc-b', 'loc-c']);
		entferne('loc-b');
		derivedNeu(e);
		assert.deepEqual(
			e.u.wiz.pickedIds,
			['loc-a', 'loc-c'],
			'Abwählen im Desktop-Orte-Schritt erreicht den Editor-Zustand nicht — bind:pickedIds am Desktop-Step2Orte fehlt oder ist einweg?'
		);
		assert.equal(e.u.orteContinueReady, true);
		await e.u.handleActivate();
		assert.deepEqual(netz.presetPosts().map((p) => p.koerper?.location_ids), [['loc-a', 'loc-c']], 'POST trägt den abgewählten Ort weiter');
	});
});

describe('AC-6 mobil (F002): dense-Variante und Bibliotheks-Knopf', () => {
	test('mobil rendert der Schritt dicht: Bibliotheks-Knopf da, Smart-Import-Raster des Desktops nicht', async () => {
		const { mobil } = await renderMobilOrte(['loc-a', 'loc-b']);
		assert.deepEqual(
			testids(mobil, 'compare-step2-mobile-library-btn'),
			['compare-step2-mobile-library-btn'],
			'mobiler Orte-Schritt ohne Bibliotheks-Knopf — `dense` am mobilen Step2Orte fehlt?'
		);
		assert.deepEqual(testids(mobil, 'compare-step2-smart-import-input'), [], 'mobil steht der Desktop-Smart-Import (nicht dense)');
		assert.deepEqual(testids(mobil, 'compare-step2-library'), [], 'mobil steht die Desktop-Inline-Bibliothek (nicht dense)');
	});

	test('der Bibliotheks-Knopf im mobilen Schritt öffnet das Bibliotheks-Sheet des Editors', async () => {
		const e = await vergleichEditor({
			stateOverride: { activeTab: 'orte', isMobileViewport: true, name: 'Dolomiten', pickedIds: ['loc-a', 'loc-b'] },
			locations: ORTE
		});
		// Mobiler Mount = die Step2Orte-Einbettung NACH dem Mobil-Kopf (Position, nicht Attribute).
		const anker = e.quelle.indexOf(MOBIL_ANKER);
		assert.ok(anker > 0, 'Messaufbau: cm-mobile-head fehlt im Editor-Quelltext');
		const mobil = findeKomponenten(e.ast, 'Step2Orte').filter((k) => k.start > anker);
		assert.equal(mobil.length, 1, `Messaufbau: erwartet genau einen mobilen Step2Orte, gefunden ${mobil.length}`);

		const sheet = findeKomponenten(e.ast, 'Sheet');
		assert.equal(sheet.length, 1, 'Messaufbau: Bibliotheks-Sheet fehlt');
		const sheetOffen = attributAusdruck(sheet[0], e.quelle, 'open');
		assert.ok(sheetOffen, 'Messaufbau: Sheet ohne open-Attribut');
		assert.equal(werte(sheetOffen, e.u), false, 'Vorbedingung: Sheet startet geschlossen');

		// Die Props, die der Editor dem mobilen Schritt WIRKLICH setzt.
		const ausdruck = attributAusdruck(mobil[0], e.quelle, 'onOpenLibrary');
		const onOpenLibrary = ausdruck === null ? undefined : werte(ausdruck, e.u);

		// Das ECHTE Step2Orte-Skript mit diesen Props; sein Bibliotheks-Knopf-onclick aus dem Markup.
		const s = await umgebungFuer(
			STEP2,
			{ locations: ORTE, groups: [], pickedIds: ['loc-a', 'loc-b'], dense: true, onOpenLibrary, $bindable: (v: unknown) => v },
			{ jsAlsTs: true }
		);
		const knopf = knopfMitTestid(s.ast, 'compare-step2-mobile-library-btn');
		assert.ok(knopf, 'Messaufbau: Bibliotheks-Knopf fehlt in Step2Orte');
		const onclick = (knopf.attributes as Knoten[]).find((a) => a.type === 'Attribute' && a.name === 'onclick');
		assert.ok(onclick?.value?.expression, 'Messaufbau: Bibliotheks-Knopf ohne onclick');
		(werte(ohneTypen(s.quelle, onclick.value.expression), s.u) as () => void)();

		assert.equal(
			werte(sheetOffen, e.u),
			true,
			'Klick auf „Ort aus Bibliothek wählen" öffnet das Bibliotheks-Sheet nicht — onOpenLibrary am mobilen Step2Orte fehlt?'
		);
	});
});

/** Erster `<button>` nach Quelltext-Offset `ab`, dessen data-testid mit `praefix` beginnt. */
function knopfMitTestidPraefix(ast: Knoten, praefix: string, ab: number): Knoten | null {
	let treffer: Knoten | null = null;
	(function lauf(n: unknown): void {
		if (treffer || n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) return n.forEach(lauf);
		const k = n as Knoten;
		if (k.type === 'RegularElement' && k.name === 'button' && k.start > ab) {
			const t = (k.attributes as Knoten[]).find((a) => a.type === 'Attribute' && a.name === 'data-testid');
			const v = t?.value;
			const roh = Array.isArray(v)
				? v.map((x: Knoten) => (x.type === 'Text' ? x.data : '')).join('')
				: v?.type === 'ExpressionTag'
					? String(v.expression?.quasis?.[0]?.value?.raw ?? '')
					: '';
			if (roh.startsWith(praefix)) {
				treffer = k;
				return;
			}
		}
		for (const key of Object.keys(k)) if (key !== 'parent' && key !== 'loc') lauf(k[key]);
	})(ast.fragment);
	return treffer;
}

function knopfMitTestid(ast: Knoten, testid: string): Knoten | null {
	let treffer: Knoten | null = null;
	(function lauf(n: unknown): void {
		if (treffer || n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) return n.forEach(lauf);
		const k = n as Knoten;
		if (k.type === 'RegularElement' && k.name === 'button') {
			const t = (k.attributes as Knoten[]).find((a) => a.type === 'Attribute' && a.name === 'data-testid');
			if (Array.isArray(t?.value) && t.value.map((x: Knoten) => x.data ?? '').join('') === testid) {
				treffer = k;
				return;
			}
		}
		for (const key of Object.keys(k)) if (key !== 'parent' && key !== 'loc') lauf(k[key]);
	})(ast.fragment);
	return treffer;
}
