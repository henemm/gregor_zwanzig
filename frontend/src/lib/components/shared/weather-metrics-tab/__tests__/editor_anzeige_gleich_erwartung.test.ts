// TDD -- Issue #2422 S2a, AC-3: TS-Anzeige = Erwartung je Kanal, alle drei
// Goldens, ohne Ausnahme.
//
// SPEC: docs/specs/modules/fix_2422_s2a_editor_gleich_gespeichert.md (AC-3).
//
// Nutzt die geteilte Kette `_editor_kette.ts` (Nachbau von
// `WeatherMetricsTab.svelte::initFromTrip()` ueber die ECHTEN Helfer
// `bucketsToColumns`, `channelOverrideFromMetrics`,
// `splitChannelMetricsForDisplay`) -- dieselbe Nachbau-Logik wie AC-4/AC-14
// und der Erwartungsdatei-Generator, damit keine zweite, leicht abweichende
// Kopie entsteht (Drift-Risiko).
//
// Vergleich gegen die eingefrorenen `erwartung_golden_{a,b,c}.json`
// (`tests/helpers/erwartungsdateien_erzeugen.py`, Python-Orakel) -- reiner
// Datenvergleich, KEINE Kaskaden-Logik in TS (Memory: Orakel bleibt
// Python-exklusiv).
//
// Diese Datei ist bereits heute GRUEN fuer alle drei Goldens (S1-Bestand A/B
// unveraendert; Golden C neu: B9 wirkt hier NICHT -- die Editor-ANZEIGE zeigt
// die globale Reihenfolge schon immer, unabhaengig vom B9-Fix, nur die
// AUSLIEFERUNG war vorher falsch). Golden C dient hier als
// Regressionsschutz fuer die (B9-unabhaengige) Anzeige-Kette selbst.
//
// Lauf:
//     cd frontend && npm test -- \
//       src/lib/components/shared/weather-metrics-tab/__tests__/editor_anzeige_gleich_erwartung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import { ladeInEditorState, berechneAnzeige, type GoldenTrip, type MinimalCatalog } from './_editor_kette.ts';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE_DIR = path.resolve(__dirname, '../../../../../../../tests/fixtures/einstellung_auslieferung');

interface Erwartung {
	channels: Record<string, Array<{ metric_id: string; friendly: boolean }>>;
}

function ladeGolden(name: string): GoldenTrip {
	return JSON.parse(readFileSync(path.join(FIXTURE_DIR, `${name}.json`), 'utf-8'));
}
function ladeErwartung(name: string): Erwartung {
	return JSON.parse(readFileSync(path.join(FIXTURE_DIR, `erwartung_${name}.json`), 'utf-8'));
}

// Echter Katalog-Snapshot (29 waehlbare Metriken, aus app.metric_catalog.
// get_all_metrics() -- dieselbe Funktion hinter GET /api/metrics), NICHT ein
// auf Golden-eigene IDs verkuerzter Ad-hoc-Katalog: buildWeatherConfigMetrics
// emittiert einen Eintrag pro Katalog-ID (metricsEditor.ts:366).
const catalog: MinimalCatalog = JSON.parse(
	readFileSync(path.join(__dirname, 'fixtures', 'metric_catalog_selectable.json'), 'utf-8'),
);

describe('AC-3: TS-Anzeige = Erwartung je Kanal (alle drei Goldens, ohne Ausnahme)', () => {
	for (const name of ['golden_a', 'golden_b', 'golden_c']) {
		test(`${name}: email/telegram/sms Anzeige entspricht der eingefrorenen Erwartung`, () => {
			const golden = ladeGolden(name);
			const erwartung = ladeErwartung(name);
			const state = ladeInEditorState(golden, catalog);
			const anzeige = berechneAnzeige(state);

			for (const kanal of ['email', 'telegram', 'sms'] as const) {
				assert.deepEqual(
					anzeige[kanal],
					erwartung.channels[kanal],
					`AC-3: ${name}/${kanal} -- Editor-Anzeige weicht von der eingefrorenen ` +
						`Erwartung ab.\nIst:  ${JSON.stringify(anzeige[kanal])}\n` +
						`Soll: ${JSON.stringify(erwartung.channels[kanal])}`,
				);
			}
		});
	}
});
