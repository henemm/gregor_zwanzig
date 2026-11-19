// Issue #2973 (Epic #2913) — Hub-Anker im Staging-Abgleich: warten statt einmal lesen.
// Spec: docs/specs/fast/fix-2973-hub-anker-warten.md (AC-1 bis AC-4)
//
//   cd frontend && npm test -- src/lib/__tests__/elementliste_hub_anker_2973.test.ts
//
// Ohne Mocks: echte kleine Funktionen — `zaehle` liefert die Befunde einer Liste nacheinander und zählt mit,
// `warte` protokolliert die Wartezeiten.
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as L from '../../../e2e/elementliste_abgleich_logik.ts';
import type { HubAnker } from '../../../e2e/elementliste_abgleich_logik.ts';

const FRONTEND = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..', '..');

function zaehler(befunde: HubAnker[]) {
	const st = { aufrufe: 0 };
	const zaehle = async (): Promise<HubAnker> => {
		const b = befunde[Math.min(st.aufrufe, befunde.length - 1)];
		st.aufrufe += 1;
		return { ...b };
	};
	return { st, zaehle };
}

function warteProtokoll() {
	const pausen: number[] = [];
	const warte = async (ms: number): Promise<void> => {
		pausen.push(ms);
	};
	return { pausen, warte };
}

describe('#2973 warteAufHubAnker', () => {
	test('AC-1: Anker erst beim dritten Zählen ⇒ vollständiger Befund nach drei Zählungen und zwei Pausen', async () => {
		assert.equal(typeof L.warteAufHubAnker, 'function', 'warteAufHubAnker fehlt in elementliste_abgleich_logik.ts');
		const { st, zaehle } = zaehler([
			{ kopf: 0, flaeche: 0 },
			{ kopf: 1, flaeche: 0 },
			{ kopf: 1, flaeche: 1 }
		]);
		const { pausen, warte } = warteProtokoll();
		const anker = await L.warteAufHubAnker(zaehle, warte);
		assert.deepEqual(anker, { kopf: 1, flaeche: 1 });
		assert.equal(L.pruefeHubAnker(anker), null);
		assert.equal(st.aufrufe, 3);
		assert.deepEqual(pausen, [500, 500]);
	});

	test('AC-2: Anker fehlt immer, 4 Versuche ⇒ 4 Zählungen, unvollständiger Befund, fail-closed', async () => {
		assert.equal(typeof L.warteAufHubAnker, 'function', 'warteAufHubAnker fehlt in elementliste_abgleich_logik.ts');
		const { st, zaehle } = zaehler([{ kopf: 1, flaeche: 0 }]);
		const { pausen, warte } = warteProtokoll();
		const anker = await L.warteAufHubAnker(zaehle, warte, { versuche: 4, abstandMs: 250 });
		assert.deepEqual(anker, { kopf: 1, flaeche: 0 });
		assert.equal(st.aufrufe, 4);
		assert.deepEqual(pausen, [250, 250, 250], 'kein Warten nach dem letzten Versuch');
		const grund = L.pruefeHubAnker(anker);
		assert.ok(grund !== null, 'fehlender Anker muss weiter gemeldet werden');
		assert.match(grund, /Reiterfläche/);
	});

	test('AC-2: Vorgabe sind 10 Versuche', async () => {
		assert.equal(typeof L.warteAufHubAnker, 'function', 'warteAufHubAnker fehlt in elementliste_abgleich_logik.ts');
		const { st, zaehle } = zaehler([{ kopf: 0, flaeche: 1 }]);
		const { pausen, warte } = warteProtokoll();
		const anker = await L.warteAufHubAnker(zaehle, warte);
		assert.equal(st.aufrufe, 10);
		assert.equal(pausen.length, 9);
		assert.match(String(L.pruefeHubAnker(anker)), /Kopf/);
	});

	test('AC-3: beide Anker sofort da ⇒ genau eine Zählung, kein Warten', async () => {
		assert.equal(typeof L.warteAufHubAnker, 'function', 'warteAufHubAnker fehlt in elementliste_abgleich_logik.ts');
		const { st, zaehle } = zaehler([{ kopf: 1, flaeche: 2 }]);
		const { pausen, warte } = warteProtokoll();
		const anker = await L.warteAufHubAnker(zaehle, warte);
		assert.deepEqual(anker, { kopf: 1, flaeche: 2 });
		assert.equal(st.aufrufe, 1);
		assert.deepEqual(pausen, []);
	});

	test('AC-4: texteUnterHub wartet über warteAufHubAnker, bevor es die Texte liest (doc-compliance-test)', () => {
		// doc-compliance-test: Verdrahtung der Live-Spec; das Warteverhalten prüfen die Tests oben, die Wirkung der Staging-Lauf.
		const spec = readFileSync(join(FRONTEND, 'e2e/elementliste-abgleich.staging.spec.ts'), 'utf8');
		assert.match(spec, /^\s*warteAufHubAnker,$/m, 'Spec importiert warteAufHubAnker aus der Logik');
		const start = spec.indexOf('async function texteUnterHub');
		assert.ok(start >= 0, 'texteUnterHub fehlt');
		const ende = spec.indexOf('\n}\n', start);
		const rumpf = spec.slice(start, ende);
		const warten = rumpf.search(/await warteAufHubAnker\(/);
		const lesen = rumpf.search(/page\.evaluate\(sichtbareTexte/);
		assert.ok(warten >= 0, 'texteUnterHub ruft warteAufHubAnker nicht auf');
		assert.ok(lesen >= 0, 'texteUnterHub liest keine Texte');
		assert.ok(warten < lesen, 'Anker-Warten muss vor dem Lesen der Texte stehen');
		assert.match(rumpf, /page\.evaluate\(zaehleAnker, \{ kopf: HUB_ANKER_KOPF, flaeche: HUB_ANKER_FLAECHE \}\)/);
		assert.match(rumpf, /page\.waitForTimeout\(ms\)/);
	});
});
