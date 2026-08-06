// TDD RED: Fix #1435 Etappe E4 — Schwellwert-Tabelle wird eine einzige Quelle
//
// Spec: docs/specs/modules/fix_1435_e4_schwellwert_quelle.md
//
// Wirkungstest (AC-1, AC-2, AC-6, AC-9): prüft die tatsächlich von
// `levelToThreshold()` zurückgegebene Zeichenkette, nicht Dateien
// gegeneinander. `METRIC_PRESETS`/`levelToThreshold()` selbst bleiben in
// dieser Etappe UNVERÄNDERT (das Skript und die generierte Datei existieren
// noch nicht) — die Nullgradgrenze-Fälle müssen deshalb jetzt ROT sein: die
// heutige Handkopie liefert 400/200/100 statt der wirksamen Backend-Werte
// 600/400/200 (ADR-0019 Punkt 4). Das ist der Bug, den E4 behebt.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/alerts-tab/__tests__/alertPresetThresholdDisplay.test.ts

import { test, mock } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

import { levelToThreshold } from '../alertMetricTable.ts';

// ─────────────────────────────────────────────────────────────────────────
// AC-1 / AC-2: Nullgradgrenze — die Anzeige muss den wirksamen Backend-Wert
// zeigen (ADR-0019 Punkt 4: 600/400/200), nicht die abgetippte, gedriftete
// Kopie (heute 400/200/100).
// ─────────────────────────────────────────────────────────────────────────

test('freezing_level > standard zeigt "Δ ≥ 400 m" (wirksamer Backend-Wert)', () => {
	assert.equal(levelToThreshold('freezing_level', 'standard'), 'Δ ≥ 400 m');
});

test('freezing_level > entspannt zeigt "Δ ≥ 600 m" (wirksamer Backend-Wert)', () => {
	assert.equal(levelToThreshold('freezing_level', 'entspannt'), 'Δ ≥ 600 m');
});

test('freezing_level > sensibel zeigt "Δ ≥ 200 m" (wirksamer Backend-Wert)', () => {
	assert.equal(levelToThreshold('freezing_level', 'sensibel'), 'Δ ≥ 200 m');
});

// ─────────────────────────────────────────────────────────────────────────
// Gegenprobe Verhaltensneutralität (AC-4): eine Größe, die heute schon
// deckungsgleich ist, darf durch die Zusammenführung nicht verändert werden.
// Bleibt grün, sowohl vor als auch nach der Implementierung.
// ─────────────────────────────────────────────────────────────────────────

test('wind_gust > standard bleibt "Δ ≥ 20 km/h" (Verhaltensneutralität)', () => {
	assert.equal(levelToThreshold('wind_gust', 'standard'), 'Δ ≥ 20 km/h');
});

// ─────────────────────────────────────────────────────────────────────────
// AC-6: Sichtweite ist THRESHOLD_CROSSING (Unterschreiten), nicht DELTA —
// die Zusammenführung darf diese Unterscheidung nicht verlieren.
// ─────────────────────────────────────────────────────────────────────────

test('visibility > standard zeigt "< 1000 m", nicht "Δ ≥ 1000 m" (AC-6)', () => {
	assert.equal(levelToThreshold('visibility', 'standard'), '< 1000 m');
});

// ─────────────────────────────────────────────────────────────────────────
// Adversary-Finding F001 (Fix-Loop nach der Adversary-Runde): der bisherige
// Wirkungstest allein prüft nur, dass 'visibility' im Set landet — das
// stimmt heute sowohl bei echter Ableitung aus dem `kind`-Feld ALS AUCH bei
// einem festen Literal `new Set(['visibility'])`, weil es aktuell zufällig
// die einzige threshold_crossing-Größe ist. Ersetzt man die Ableitung durch
// dieses Literal, blieben bisher alle 40 Tests grün.
//
// Dieser Test macht den Unterschied sichtbar, OHNE die echte generierte
// Datei zu verändern: er ersetzt sie über Node's eingebautes
// `mock.module()` (Flag `--experimental-test-module-mocks`, siehe
// package.json) durch einen künstlichen Datenstand mit ZWEI
// threshold_crossing-Größen ('cape' zusätzlich zu 'visibility') und lädt
// `alertMetricTable.ts` danach frisch (Cache-Bust per Query-Parameter), damit
// der echte Modulcode mit dem künstlichen Stand ausgeführt wird — kein
// Dateiinhalt-Grep, sondern ein echter Wirkungsnachweis gegen den
// tatsächlich exportierten Wert. Ein Literal würde 'cape' nicht enthalten
// und diesen Test unabhängig vom heutigen realen Datenstand rot machen.
// ─────────────────────────────────────────────────────────────────────────

test(
	'THRESHOLD_CROSSING_METRICS wird aus dem kind-Feld der generierten Datei abgeleitet, nicht aus einem Literal (F001)',
	async () => {
		const genUrl = pathToFileURL(
			path.resolve(
				path.dirname(fileURLToPath(import.meta.url)),
				'../../../generated/alertPresetThresholds.generated.json',
			),
		).href;

		const mocked = mock.module(genUrl, {
			defaultExport: {
				cape: { kind: 'threshold_crossing', entspannt: 1, standard: 2, sensibel: 3 },
				visibility: { kind: 'threshold_crossing', entspannt: 500, standard: 1000, sensibel: 3000 },
				wind_gust: { kind: 'delta', entspannt: 1, standard: 2, sensibel: 3 },
			},
		});

		try {
			const modUrl = pathToFileURL(
				path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../alertMetricTable.ts'),
			).href;
			const fresh = (await import(`${modUrl}?f001-mutation-probe=${Date.now()}`)) as {
				THRESHOLD_CROSSING_METRICS: ReadonlySet<string>;
			};

			assert.deepEqual(
				[...fresh.THRESHOLD_CROSSING_METRICS].sort(),
				['cape', 'visibility'],
				'THRESHOLD_CROSSING_METRICS muss beide threshold_crossing-Größen aus dem ' +
					"künstlichen Datenstand enthalten -- ein festes Literal wie new Set(['visibility']) " +
					"würde 'cape' nicht mitziehen, obwohl die generierte Datei es als threshold_crossing führt.",
			);
		} finally {
			mocked.restore();
		}
	},
);
