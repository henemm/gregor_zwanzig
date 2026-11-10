// Regressionswaechter — Issue #2794 S3a, Teil-PR 2 (Adversary-Finding F013), nachgezogen in Teil-PR 3.
// Spec: docs/specs/modules/feat_2794_s3a_teil2_leiste.md (§4 Reiter Wetter), Teil-PR 3:
// docs/specs/modules/feat_2794_s3a_teil3_wetter.md §6 (f) Waechter-Nachzug.
//
// Warum: im Trip-Hub (TripTabs.svelte) muss der Reiter `wetter` die Grenzen (bis Teil-PR 2 die
// Wertebereiche-Ansicht CorridorEditor/CorridorEditorMobile, seit Teil-PR 3 die Ampel-Grenzen im
// WetterTab) auf JEDEM Geraetetyp tragen. Faellt die Einbettung fuer einen Geraetetyp weg (oder
// rutscht sie in den Reiter zustellung), verliert der Nutzer dort die Grenzen.
//
// Nachzug Teil-PR 3 (Zusicherung uebertragen, nicht aufgeweicht): der Traeger ist jetzt EIN
// WetterTab ohne Viewport-Weiche (eine Komponente fuer Desktop UND mobil, AC-38) — damit ist
// „Desktop und mobil" strenger gefasst als vorher (eine Instanz statt zwei, die sich ausschliessen
// muessen). Die Alt-Ansicht darf im Hub gar nicht mehr haengen (sonst zwei Speicherer).
//
// Messweise: AST der echten Komponente (svelte/compiler.parse, Helfer s3a2794Ast.ts). Keine Textsuche.
//
// Ausfuehren (aus frontend/):
//   npm test -- src/lib/components/shared/__tests__/s3a2794_trip_hub_wetter_wertebereiche.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { svelteAst, einbettungenMitWeichen, reiterVon, viewportVon, type Einbettung } from './s3a2794Ast.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const KOMP = join(HIER, '..', '..');
const TRIP_HUB = join(KOMP, 'trip-detail', 'TripTabs.svelte');

function einbettungen(namen: string[]): { e: Einbettung[]; quelle: string } {
	const { ast, quelle } = svelteAst(TRIP_HUB);
	return { e: einbettungenMitWeichen(ast, quelle, namen), quelle };
}

const beschreibe = (e: Einbettung, quelle: string) =>
	`${e.name}@${quelle.slice(0, e.knoten.start).split('\n').length} [${e.weichen.map((w) => `${w.zweig}:${w.test}`).join(' > ')}]`;

describe('F013: Trip-Hub Reiter wetter traegt die Grenzen auf Desktop UND mobil, Reiter zustellung nicht', () => {
	test('s3a2794_f013_wetter_genau_ein_wettertab_fuer_desktop_und_mobil', () => {
		const { e, quelle } = einbettungen(['WetterTab']);
		const w = e.filter((x) => reiterVon(x).includes('wetter'));
		assert.equal(w.length, 1, `F013: erwartet genau einen WetterTab im Reiter wetter, gefunden ${w.length}`);
		assert.equal(viewportVon(w[0]), null, `F013: ${beschreibe(w[0], quelle)} haengt an einer Viewport-Weiche (ein Geraetetyp ohne Grenzen)`);
	});

	test('s3a2794_f013_keine_alt_wertebereiche_im_hub', () => {
		const { e, quelle } = einbettungen(['CorridorEditor', 'CorridorEditorMobile']);
		assert.deepEqual(e.map((x) => beschreibe(x, quelle)), [], 'F013/AC-38: Alt-Wertebereiche noch im Trip-Hub (zweiter Speicherer)');
	});

	test('s3a2794_f013_zustellung_ohne_grenzen_traeger', () => {
		const { e, quelle } = einbettungen(['WetterTab', 'CorridorEditor', 'CorridorEditorMobile']);
		const z = e.filter((x) => reiterVon(x).includes('zustellung'));
		assert.equal(z.length, 0, `F013: Grenzen-Traeger im Reiter zustellung: ${z.map((x) => beschreibe(x, quelle)).join(' | ')}`);
	});

	test('s3a2794_f013_keine_grenzen_ausserhalb_des_reiters_wetter', () => {
		const { e, quelle } = einbettungen(['WetterTab']);
		assert.equal(e.length, 1, `F013: erwartet genau 1 WetterTab im Trip-Hub, gefunden: ${e.map((x) => beschreibe(x, quelle)).join(' | ')}`);
		for (const x of e) assert.deepEqual(reiterVon(x), ['wetter'], `F013: ${beschreibe(x, quelle)} haengt nicht (nur) am Reiter wetter`);
	});
});
