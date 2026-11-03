// TDD RED — Issue #2727 (Epic #2345, DoD-1): compareWizardState ablösen.
// Spec: docs/specs/modules/feat_2727_compare_wizardstate_abloesen.md — AC-6
//
// Der Schritt „Orte" (compare/steps/Step2Orte.svelte) bekommt die Auswahl als bindbare Prop
// `pickedIds = $bindable<string[]>([])` statt über `getContext(…)`. Gemessen auf drei Ebenen:
//   (1) Serverseitiges Rendern (svelte/server, ECHTE Komponente, kein Context): die gewählten Orte
//       erscheinen nummeriert und in Auswahl-Reihenfolge in der Liste „Im Vergleich".
//   (2) Instanz-Prüfstand (svelteInstanzPruefstand.ts): Auswählen/Abwählen (`togglePick`, dieselbe
//       Funktion, die die Bibliotheks-Kacheln aufrufen) ändert die gebundene Prop `pickedIds`.
//   (3) Im Anlege-Editor: die über `stateOverride.pickedIds` gesäten Orte erscheinen im Reiter
//       „Orte" — die Bindung Editor ↔ Step2Orte trägt ohne Context.
//
// Warum heute rot: Step2Orte liest `getContext('compare-…')` — ohne Context gibt es kein
// Zustandsobjekt (Rendern scheitert, `togglePick` wirft), eine Prop `pickedIds` existiert nicht;
// der Editor kennt `stateOverride.pickedIds` nicht.
//
// Ausführen (aus frontend/):
//   node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks \
//     --test src/lib/components/compare/__tests__/step2_orte_pickedids_prop.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { lade, renderKomponente, testids, innen, sichtbarerText } from '../../shared/__tests__/infoboxSsr.ts';
import { umgebungFuer, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';

const STEP2 = join(dirname(fileURLToPath(import.meta.url)), '..', 'steps', 'Step2Orte.svelte');

const ORTE = [
	{ id: 'loc-a', name: 'Alpbach', lat: 47.4, lon: 11.9 },
	{ id: 'loc-b', name: 'Brixen', lat: 46.7, lon: 11.6 },
	{ id: 'loc-c', name: 'Cortina', lat: 46.5, lon: 12.1 }
];

function renderStep2(props: Record<string, unknown>): string {
	return renderKomponente(STEP2_KOMPONENTE, props);
}
let STEP2_KOMPONENTE: unknown;

describe('AC-6 (1): Step2Orte rendert die Auswahl aus der Prop pickedIds — ohne Context', () => {
	test('gewählte Orte erscheinen nummeriert in Auswahl-Reihenfolge', async () => {
		STEP2_KOMPONENTE ??= await lade('compare/steps/Step2Orte.svelte');
		let html: string;
		try {
			html = renderStep2({ locations: ORTE, pickedIds: ['loc-b', 'loc-a'] });
		} catch (e) {
			assert.fail(`VERTRAG FEHLT (#2727): Step2Orte rendert ohne Context nicht (pickedIds-Prop fehlt?): ${String(e).slice(0, 200)}`);
		}
		const liste = innen(html, 'compare-step2-picked-list');
		assert.deepEqual(testids(liste, 'compare-step2-picked-item-'), ['compare-step2-picked-item-loc-b', 'compare-step2-picked-item-loc-a']);
		const text = sichtbarerText(liste);
		assert.match(text, /1\s+Brixen/, `Nummerierung fehlt: ${text}`);
		assert.match(text, /2\s+Alpbach/, `Nummerierung fehlt: ${text}`);
		assert.doesNotMatch(text, /Cortina/, 'nicht gewählter Ort steht in der Auswahl');
	});

	test('ohne pickedIds: leere Auswahl („Noch keine Orte"), Zähler „min. 2 erforderlich"', async () => {
		STEP2_KOMPONENTE ??= await lade('compare/steps/Step2Orte.svelte');
		let html: string;
		try {
			html = renderStep2({ locations: ORTE });
		} catch (e) {
			assert.fail(`VERTRAG FEHLT (#2727): Step2Orte rendert ohne Context nicht: ${String(e).slice(0, 200)}`);
		}
		assert.deepEqual(testids(html, 'compare-step2-picked-item-'), []);
		assert.match(sichtbarerText(innen(html, 'compare-step2-picked-list')), /Noch keine Orte/);
		assert.match(sichtbarerText(innen(html, 'compare-step2-counter')), /min\. 2 erforderlich/);
	});
});

describe('AC-6 (2): Auswählen/Abwählen ändert die gebundene Prop pickedIds', () => {
	async function step2(saat: Knoten): Promise<Knoten> {
		const { u } = await umgebungFuer(
			STEP2,
			{ locations: ORTE, groups: [], $bindable: (v: unknown) => v, ...saat },
			{ jsAlsTs: true }
		);
		return u;
	}

	test('Vorbedingung: pickedIds ist eine Prop mit Startwert [] (bindbar)', async () => {
		const u = await step2({});
		assert.deepEqual(u.pickedIds, [], 'VERTRAG FEHLT (#2727): Step2Orte deklariert keine Prop `pickedIds = $bindable([])`');
	});

	test('togglePick fügt einen Ort hinzu und entfernt ihn wieder — an der gebundenen Prop', async () => {
		const u = await step2({ pickedIds: ['loc-a'] });
		assert.equal(typeof u.togglePick, 'function', 'Messaufbau: togglePick nicht gebunden');
		try {
			u.togglePick('loc-c');
		} catch (e) {
			assert.fail(`VERTRAG FEHLT (#2727): togglePick schreibt nicht in die Prop pickedIds: ${String(e).slice(0, 160)}`);
		}
		assert.deepEqual(u.pickedIds, ['loc-a', 'loc-c']);
		u.togglePick('loc-a');
		assert.deepEqual(u.pickedIds, ['loc-c']);
	});
});

describe('AC-6 (3): im Anlege-Editor trägt die Bindung ohne Context', () => {
	test('stateOverride.pickedIds erscheint im Reiter „Orte" als Auswahl', async () => {
		const Editor = await lade('compare-new/CompareNewEditor.svelte');
		let html: string;
		try {
			html = renderKomponente(Editor, {
				locations: ORTE,
				stateOverride: { activeTab: 'orte', isMobileViewport: false, name: 'Dolomiten', pickedIds: ['loc-c', 'loc-a'] }
			});
		} catch (e) {
			assert.fail(`VERTRAG FEHLT (#2727): CompareNewEditor rendert ohne Context nicht: ${String(e).slice(0, 200)}`);
		}
		assert.deepEqual(
			testids(innen(html, 'compare-step2-picked-list'), 'compare-step2-picked-item-'),
			['compare-step2-picked-item-loc-c', 'compare-step2-picked-item-loc-a']
		);
	});
});
