// TDD -- Issue #2422 S2a, AC-4: TS-Speichern ohne Aenderung = eingefrorener
// Stand, inklusive aller Felder (K8-Fix).
//
// SPEC: docs/specs/modules/fix_2422_s2a_editor_gleich_gespeichert.md (AC-4).
//
// Nutzt die geteilte Kette `_editor_kette.ts::speichernOhneAenderung()`
// (Laden + `buildWeatherConfigMetrics`/`mergeAllChannelLayoutsForSave` +
// flacher Merge wie `config_merge.go`). Vergleich gegen die eingefrorene
// `nach_speichern_<golden>.json` -- die Datei existiert erst NACH /50 (dort
// aus GENAU dieser Kette einmalig erzeugt und eingefroren). Bis dahin
// schlaegt dieser Test mit einer klaren "fehlt -- wird in /50 erzeugt"-
// Meldung fehl (ROT NUR WEGEN FEHLENDER /50-DATEI, kein RED-Beweis fuer
// B9/K8 selbst -- der steht in feld_erhalt_ohne_ausnahme.test.ts).
//
// Lauf:
//     cd frontend && npm test -- \
//       src/lib/components/shared/weather-metrics-tab/__tests__/editor_speichern_ohne_aenderung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import { speichernOhneAenderung, type GoldenTrip, type MinimalCatalog } from './_editor_kette.ts';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE_DIR = path.resolve(__dirname, '../../../../../../../tests/fixtures/einstellung_auslieferung');

function ladeGolden(name: string): GoldenTrip {
	return JSON.parse(readFileSync(path.join(FIXTURE_DIR, `${name}.json`), 'utf-8'));
}

// Echter Katalog-Snapshot (siehe editor_anzeige_gleich_erwartung.test.ts) --
// buildWeatherConfigMetrics emittiert einen Eintrag pro Katalog-ID.
const catalog: MinimalCatalog = JSON.parse(
	readFileSync(path.join(__dirname, 'fixtures', 'metric_catalog_selectable.json'), 'utf-8'),
);

describe('AC-4: TS-Speichern ohne Aenderung = eingefrorener Stand', () => {
	for (const name of ['golden_a', 'golden_b', 'golden_c']) {
		test(`${name}: Stand nach Speichern-ohne-Aenderung entspricht nach_speichern_${name}.json`, () => {
			const goldenPath = path.join(FIXTURE_DIR, `nach_speichern_${name}.json`);
			if (!existsSync(goldenPath)) {
				assert.fail(
					`AC-4: ${goldenPath} fehlt -- wird in /50 aus GENAU dieser Kette ` +
						`(_editor_kette.ts::speichernOhneAenderung) erzeugt und eingefroren. ` +
						`ROT NUR WEGEN FEHLENDER /50-DATEI, kein B9/K8-Befund.`,
				);
			}
			const golden = ladeGolden(name);
			const erwartet = JSON.parse(readFileSync(goldenPath, 'utf-8'));
			const ist = speichernOhneAenderung(golden, catalog);

			assert.deepEqual(
				ist,
				erwartet,
				`AC-4: ${name} -- Stand nach Speichern-ohne-Aenderung weicht vom ` +
					`eingefrorenen nach_speichern_${name}.json ab.`,
			);
		});
	}
});
