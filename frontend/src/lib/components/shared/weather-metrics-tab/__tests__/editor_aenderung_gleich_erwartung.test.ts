// TDD -- Issue #2422 S2a, AC-14: TS -- Aenderungsfaelle 1-4, Anzeige UND
// Speichern = eingefrorener Stand.
//
// SPEC: docs/specs/modules/fix_2422_s2a_editor_gleich_gespeichert.md (AC-14).
//
// Simuliert jeden der vier Faelle aus `aenderungsfaelle.json` ueber dieselbe
// geteilte Kette wie AC-3/AC-4 (`_editor_kette.ts`) und vergleicht sowohl die
// resultierende Anzeige (`nach_aenderung_<fall>_anzeige.json`) als auch den
// gespeicherten Stand (`nach_aenderung_<fall>.json`) -- beide Dateien
// existieren erst NACH /50 (dort aus GENAU dieser Kette erzeugt). Bis dahin
// klare "fehlt -- wird in /50 erzeugt"-Meldung (ROT NUR WEGEN FEHLENDER
// /50-DATEI).
//
// Lauf:
//     cd frontend && npm test -- \
//       src/lib/components/shared/weather-metrics-tab/__tests__/editor_aenderung_gleich_erwartung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import {
	baueSpeichernPayload,
	berechneAnzeige,
	flacherMerge,
	ladeInEditorState,
	wendeAenderungAn,
	type Aenderungsfall,
	type GoldenTrip,
	type MinimalCatalog,
} from './_editor_kette.ts';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE_DIR = path.resolve(__dirname, '../../../../../../../tests/fixtures/einstellung_auslieferung');

function ladeGolden(name: string): GoldenTrip {
	return JSON.parse(readFileSync(path.join(FIXTURE_DIR, `${name}.json`), 'utf-8'));
}
function ladeFaelle(): Record<string, Aenderungsfall & { golden: string }> {
	return JSON.parse(readFileSync(path.join(FIXTURE_DIR, 'aenderungsfaelle.json'), 'utf-8'));
}

// Echter Katalog-Snapshot (siehe editor_anzeige_gleich_erwartung.test.ts).
const catalog: MinimalCatalog = JSON.parse(
	readFileSync(path.join(__dirname, 'fixtures', 'metric_catalog_selectable.json'), 'utf-8'),
);
const faelle = ladeFaelle();

describe('AC-14: Aenderungsfaelle 1-4 -- Anzeige UND Speichern = eingefrorener Stand', () => {
	for (const [fall, definition] of Object.entries(faelle)) {
		test(`${fall}: Anzeige nach Aenderung entspricht nach_aenderung_${fall}_anzeige.json`, () => {
			const anzeigePath = path.join(FIXTURE_DIR, `nach_aenderung_${fall}_anzeige.json`);
			if (!existsSync(anzeigePath)) {
				assert.fail(
					`AC-14: ${anzeigePath} fehlt -- wird in /50 aus GENAU dieser Kette ` +
						`erzeugt und eingefroren. ROT NUR WEGEN FEHLENDER /50-DATEI.`,
				);
			}
			const golden = ladeGolden(definition.golden);
			const stateVorher = ladeInEditorState(golden, catalog);
			const stateNachher = wendeAenderungAn(stateVorher, definition);
			const anzeigeNachher = berechneAnzeige(stateNachher);
			// Form wie erwartung_golden_*.json: { channels: { email, telegram,
			// sms } } (siehe erzeuge_nach_dateien.ts).
			const erwartet: { channels: Record<'email' | 'telegram' | 'sms', unknown> } = JSON.parse(
				readFileSync(anzeigePath, 'utf-8'),
			);

			for (const kanal of ['email', 'telegram', 'sms'] as const) {
				assert.deepEqual(
					anzeigeNachher[kanal], erwartet.channels[kanal],
					`AC-14: ${fall}/${kanal} -- Anzeige nach Aenderung weicht ab.`,
				);
			}
		});

		test(`${fall}: gespeicherter Stand entspricht nach_aenderung_${fall}.json`, () => {
			const standPath = path.join(FIXTURE_DIR, `nach_aenderung_${fall}.json`);
			if (!existsSync(standPath)) {
				assert.fail(
					`AC-14: ${standPath} fehlt -- wird in /50 aus GENAU dieser Kette ` +
						`erzeugt und eingefroren. ROT NUR WEGEN FEHLENDER /50-DATEI.`,
				);
			}
			const golden = ladeGolden(definition.golden);
			const stateVorher = ladeInEditorState(golden, catalog);
			const stateNachher = wendeAenderungAn(stateVorher, definition);
			const payload = baueSpeichernPayload(golden, stateNachher, catalog);
			const ist = flacherMerge(golden, payload);
			const erwartet = JSON.parse(readFileSync(standPath, 'utf-8'));

			assert.deepEqual(
				ist, erwartet,
				`AC-14: ${fall} -- gespeicherter Stand weicht von nach_aenderung_${fall}.json ab.`,
			);
		});
	}
});
