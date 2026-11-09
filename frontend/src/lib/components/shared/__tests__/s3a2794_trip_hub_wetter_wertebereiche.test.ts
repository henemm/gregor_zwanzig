// Regressionswaechter — Issue #2794 S3a, Teil-PR 2 (Adversary-Finding F013).
// Spec: docs/specs/modules/feat_2794_s3a_teil2_leiste.md (§4 Reiter Wetter: Metrik-Oberflaeche,
// darunter die Wertebereiche-Ansicht bis Teil-PR 3)
//
// Warum: im Trip-Hub (TripTabs.svelte) bindet der Reiter `wetter` die Wertebereiche ein —
// Desktop ueber CorridorEditor, mobil ueber CorridorEditorMobile. Faellt eine der beiden
// Einbettungen weg (oder rutscht sie in den Reiter zustellung), verliert der Nutzer auf
// diesem Geraetetyp die Wertebereiche — bisher hielt das kein Test fest (nur „mindestens eine
// Wertebereiche-Ansicht, alle unter wetter").
//
// Messweise: AST der echten Komponente (svelte/compiler.parse, Helfer s3a2794Ast.ts): welche
// Einbettung steht unter welchem Reiter- und Viewport-Zweig. Keine Textmuster-Suche.
//
// Ausfuehren (aus frontend/):
//   npm test -- src/lib/components/shared/__tests__/s3a2794_trip_hub_wetter_wertebereiche.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { svelteAst, einbettungenMitWeichen, reiterVon, viewportVon, schliessenSichAus, type Einbettung } from './s3a2794Ast.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const KOMP = join(HIER, '..', '..');
const TRIP_HUB = join(KOMP, 'trip-detail', 'TripTabs.svelte');

function wertebereiche(): { e: Einbettung[]; quelle: string } {
	const { ast, quelle } = svelteAst(TRIP_HUB);
	return { e: einbettungenMitWeichen(ast, quelle, ['CorridorEditor', 'CorridorEditorMobile']), quelle };
}

const beschreibe = (e: Einbettung, quelle: string) =>
	`${e.name}@${quelle.slice(0, e.knoten.start).split('\n').length} [${e.weichen.map((w) => `${w.zweig}:${w.test}`).join(' > ')}]`;

describe('F013: Trip-Hub Reiter wetter bindet die Wertebereiche ein (Desktop + mobil), Reiter zustellung nicht', () => {
	test('s3a2794_f013_wetter_genau_ein_corridor_editor_desktop', () => {
		const { e, quelle } = wertebereiche();
		const d = e.filter((x) => x.name === 'CorridorEditor' && reiterVon(x).includes('wetter'));
		assert.equal(d.length, 1, `F013: erwartet genau einen CorridorEditor im Reiter wetter, gefunden ${d.length}`);
		assert.equal(viewportVon(d[0]), 'desktop', `F013: ${beschreibe(d[0], quelle)} steht nicht im Desktop-Zweig`);
	});

	test('s3a2794_f013_wetter_genau_ein_corridor_editor_mobile_mobil', () => {
		const { e, quelle } = wertebereiche();
		const m = e.filter((x) => x.name === 'CorridorEditorMobile' && reiterVon(x).includes('wetter'));
		assert.equal(m.length, 1, `F013: erwartet genau einen CorridorEditorMobile im Reiter wetter, gefunden ${m.length}`);
		assert.equal(viewportVon(m[0]), 'mobil', `F013: ${beschreibe(m[0], quelle)} steht nicht im Mobil-Zweig`);
	});

	test('s3a2794_f013_desktop_und_mobil_schliessen_sich_aus', () => {
		const { e, quelle } = wertebereiche();
		const d = e.find((x) => x.name === 'CorridorEditor' && reiterVon(x).includes('wetter'));
		const m = e.find((x) => x.name === 'CorridorEditorMobile' && reiterVon(x).includes('wetter'));
		assert.ok(d && m, 'F013: Desktop- oder Mobil-Wertebereiche fehlen im Reiter wetter');
		assert.ok(schliessenSichAus(d!, m!), `F013: ${beschreibe(d!, quelle)} und ${beschreibe(m!, quelle)} koennen zugleich gemountet sein`);
	});

	test('s3a2794_f013_zustellung_ohne_wertebereiche', () => {
		const { e, quelle } = wertebereiche();
		const z = e.filter((x) => reiterVon(x).includes('zustellung'));
		assert.equal(z.length, 0, `F013: Wertebereiche im Reiter zustellung: ${z.map((x) => beschreibe(x, quelle)).join(' | ')}`);
	});

	test('s3a2794_f013_keine_wertebereiche_ausserhalb_des_reiters_wetter', () => {
		const { e, quelle } = wertebereiche();
		assert.equal(e.length, 2, `F013: erwartet genau 2 Wertebereiche-Einbettungen im Trip-Hub, gefunden: ${e.map((x) => beschreibe(x, quelle)).join(' | ')}`);
		for (const x of e) assert.deepEqual(reiterVon(x), ['wetter'], `F013: ${beschreibe(x, quelle)} haengt nicht (nur) am Reiter wetter`);
	});
});
