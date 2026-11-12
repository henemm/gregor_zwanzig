// Issue #2276 Scheibe S3 (Epic #2345), AC-7 — fortgefuehrt mit #2794 S3a Teil-PR 4a:
// die geteilte Wertebereiche-Logik laedt zur Laufzeit KEIN Modul aus der
// Compare-Hub-Klebeschicht (`compare/compareHubPersistenz.ts`,
// `compare/compareHubHydration.ts`). Ein Laufzeit-Import von
// `buildComparePresetSavePayload` aus `compare/compareEditorSave.ts` bleibt
// ausdruecklich zulaessig (Design Punkt 9 der Spec S3).
//
// Vorher pruefte diese Datei den Ladegraphen beim SSR-Render von
// CorridorEditor/CorridorEditorMobile (shared/corridor-editor/__tests__/
// corridor_editor_laedt_keine_compare_klebeschicht.test.ts). Die Oberflaeche ist
// entfernt (AC-31); die Logikmodule, die bleiben, zogen nach shared/wetter-tab/
// um (AC-47) — die Zusicherung gilt jetzt fuer genau diese Module plus die neue
// Anlege-Vorbelegung, gemessen am selben Ladegraphen.
//
// Spec: docs/specs/modules/rework_2276_s3_wertebereiche.md — AC-7;
//       docs/specs/modules/feat_2794_s3a_teil4_entfernen.md — AC-47
//
// Nachweis ueber den tatsaechlichen Ladegraphen, KEIN Dateiinhalt-/Grep-Check:
// ein Aufloesungs-Haken (`module.registerHooks`, in-thread) protokolliert jede
// Modul-URL, die beim Import der Module geladen wird. `import type`
// verschwindet beim Uebersetzen und bleibt zulaessig.
//
// Mutations-Gegenprobe: einen Laufzeit-Import aus `compare/compareHubHydration.ts`
// in eines der Module einfuegen => die Klebeschicht erscheint im Ladegraphen => rot.
//
// Pfadregel #1409: Prueflinge relativ zu DIESER Datei aufloesen.
//
// Ausfuehren:
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/wertebereiche_logik_laedt_keine_compare_klebeschicht.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { existsSync } from 'node:fs';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> wetter-tab -> shared -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../../..');
const WETTER_TAB = path.resolve(HERE, '..');

/** Jede URL, die ab hier aufgeloest wird (Ladegraph der Prueflinge). */
const geladen = new Set<string>();
registerHooks({
	resolve(specifier, context, nextResolve) {
		const ergebnis = nextResolve(specifier, context);
		geladen.add(ergebnis.url);
		return ergebnis;
	}
});

const MODULE = [
	'corridorEditorState.ts',
	'compareMetricCatalogLoader.ts',
	'wertebereicheVergleichSpeicherung.ts',
	'anlegeVorbelegung.ts'
];
for (const m of MODULE) await import(pathToFileURL(path.join(WETTER_TAB, m)).href);

const BRIDGE_PFADE = [
	'/src/lib/components/compare/compareHubPersistenz.ts',
	'/src/lib/components/compare/compareHubHydration.ts'
];

describe('AC-7/AC-47: die Wertebereiche-Logik unter shared/wetter-tab/ laedt keine Compare-Klebeschicht', () => {
	test('Ladegraph der vier Module enthaelt weder compareHubPersistenz.ts noch compareHubHydration.ts', () => {
		const liste = [...geladen];
		for (const m of MODULE) {
			assert.ok(
				liste.some((u) => u.endsWith(`/src/lib/components/shared/wetter-tab/${m}`)),
				`Vorbedingung: der Protokoll-Haken muss ${m} sehen — sonst beweist „Klebeschicht fehlt" nichts`
			);
		}
		// Vakuum-Schutz: eine reine Abwesenheits-Pruefung waere gruen, solange die
		// Klebeschicht-Module gar nicht existieren — das bewiese nichts.
		for (const pfad of BRIDGE_PFADE) {
			assert.ok(
				existsSync(path.join(FRONTEND, pfad)),
				`Vakuum-Schutz: ${pfad} muss existieren — sonst ist die Abwesenheits-Pruefung unten wirkungslos`
			);
		}
		assert.deepEqual(
			liste.filter((u) => BRIDGE_PFADE.some((pfad) => u.endsWith(pfad))),
			[],
			'ein Wertebereiche-Logikmodul (oder ein von ihm geladenes Modul) laedt compare/compareHubPersistenz.ts oder compare/compareHubHydration.ts zur Laufzeit'
		);
	});
});
