// TDD RED — Issue #2276 Scheibe S6a (Epic #2345), AC-1 (und die Positiv-Seite
// von AC-4).
// Spec: docs/specs/modules/rework_2276_s6a_totcode_und_ratsche.md
//
// AC-1 verlangt, dass der in Befund 5 der Analyse belegte Totcode verschwindet
// UND dass die sechs dateiinternen Signaturtypen ausdruecklich stehenbleiben.
// Beides wird hier auf ZWEI Ebenen gemessen, weil ein Teil des Totcodes zur
// Laufzeit nicht existiert:
//
//   Teil A — Laufzeit (Prototype + Instanz). `saveComparePreset()` ist eine
//   Methode, die vier Totcode-Felder sind Instanz-Felder. Beide sind echte
//   Laufzeit-Assertions, kein Dateiinhalt-Grep. Jede Abwesenheits-Pruefung
//   traegt eine Positiv-Kontrolle mit (ein Nachbar, der bleiben MUSS) — sonst
//   wuerde ein kaputter Import oder ein leeres Objekt „alles entfernt"
//   vortaeuschen.
//
//   Teil B — Quelltext. `export type SaveStatus` ist ein Typ-Alias (zur
//   Laufzeit restlos geloescht, und `svelte-check` bleibt gruen, ob das
//   `export` davor steht oder nicht), die sieben `buildHubPutPayload`-Nennungen
//   sind Kommentartext, und die tote Bedingung in `WeatherMetricsTab.svelte`
//   ist per Konstruktion verhaltensneutral (fuer BEIDE Werte des Union-Typs
//   wahr). Fuer diese drei Posten ist der Quelltext der Wirkort — es gibt
//   keinen anderen mechanischen Nachweis. Praezedenz im Bestand:
//   shared/__tests__/legacy_wizard_removed.test.ts,
//   compare/__tests__/issue_683_wizard_remove.test.ts.
//
// Erwartung VOR der Implementierung: alle Abwesenheits-Tests sind ROT, alle
// Positiv-Kontrollen GRUEN.
//
// AC-4 (#1250-Zusicherung bleibt erhalten) hat hier absichtlich KEINEN roten
// Test — es ist ein Nicht-Regressions-Kriterium: Test 1+2 in
// wizard_state_no_legacy_save.test.ts sind heute gruen und muessen gruen
// bleiben. Der Nachweis ist der unveraenderte gruene Lauf jener Datei plus die
// Mutations-Gegenprobe in `/50` (`save()` wieder einfuehren ⇒ Test 1 rot).
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/totcode_rueckbau_speicherweg.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

// `$state` muss VOR dem Import von compareWizardState.svelte.ts im globalen
// Scope liegen — die Runen-Aufrufe sind Klassenfeld-Initializer, der Bezeichner
// wird aber schon beim Modul-Laden aufgeloest. Passthrough genuegt: wir lesen
// die Felder nur direkt nach dem `new`, ohne Reaktivitaet. Praezedenz:
// compare_wizard_save_new_preset_channels.test.ts:66.
(globalThis as unknown as { $state: <T>(v: T) => T }).$state = <T>(v: T): T => v;

const { CompareWizardState } = await import('../compareWizardState.svelte.ts');

const HIER = dirname(fileURLToPath(import.meta.url));
const COMPONENTS = join(HIER, '..', '..');
const lies = (...teile: string[]) => readFileSync(join(COMPONENTS, ...teile), 'utf-8');

// ── Teil A: Laufzeit ────────────────────────────────────────────────────────

describe('AC-1 / Teil A: CompareWizardState hat den Totcode nicht mehr', () => {
	const protoMethoden = Object.getOwnPropertyNames(CompareWizardState.prototype);
	const instanz = new CompareWizardState() as unknown as Record<string, unknown>;
	const felder = Object.keys(instanz);

	test('Positiv-Kontrolle: Prototype und Instanz sind ueberhaupt bestueckt', () => {
		assert.ok(
			protoMethoden.includes('saveNewPreset'),
			'saveNewPreset() muss bleiben (Anlege-Pfad POST /api/compare/presets) — ' +
				'fehlt sie, misst dieser Test einen kaputten Import statt den Rueckbau'
		);
		for (const feld of ['name', 'region', 'pickedIds', 'endDate', 'dayWindowStartHour']) {
			assert.ok(
				felder.includes(feld),
				'Instanz-Feld ' + feld + ' muss bleiben — Positiv-Kontrolle gegen eine leere Instanz'
			);
		}
	});

	test('saveComparePreset() ist vom Prototype verschwunden (null Aufrufer, Befund 5)', () => {
		assert.strictEqual(
			protoMethoden.includes('saveComparePreset'),
			false,
			'CompareWizardState.prototype.saveComparePreset muss entfernt sein. ' +
				'Gefundene Methoden: ' + protoMethoden.join(', ')
		);
	});

	for (const feld of [
		'subscriptionId',
		'subscriptionEnabled',
		'existingDisplayConfig',
		'includeHourly'
	]) {
		test('Instanz-Feld ' + feld + ' ist entfernt (nur deklariert, null Referenzen)', () => {
			assert.strictEqual(
				felder.includes(feld),
				false,
				feld + ' muss aus CompareWizardState entfernt sein. Gefundene Felder: ' + felder.join(', ')
			);
		});
	}
});

// ── Teil B: Quelltext ──────────────────────────────────────────────────────

describe('AC-1 / Teil B: Typ-Alias, tote Bedingung und Kommentar-Leichen sind weg', () => {
	test('compareWizardState.svelte.ts exportiert keinen Typ SaveStatus mehr', () => {
		const quelle = lies('compare', 'compareWizardState.svelte.ts');
		assert.ok(
			/saveStatus\s*=\s*\$state/.test(quelle),
			'Positiv-Kontrolle: das Feld saveStatus selbst muss bleiben'
		);
		assert.strictEqual(
			/export\s+type\s+SaveStatus\b/.test(quelle),
			false,
			'export type SaveStatus muss entfallen (null externe Importeure; der Name ' +
				'kollidiert mit der unabhaengigen Store-Klasse SaveStatus aus ' +
				'$lib/stores/saveStatusStore.svelte.ts, die ~15 Dateien importieren)'
		);
	});

	test('WeatherMetricsTab.svelte enthaelt die tautologische Kontext-Disjunktion nicht mehr', () => {
		const quelle = lies('shared', 'WeatherMetricsTab.svelte');
		assert.ok(
			quelle.includes('!compareCatalogLoaded') && quelle.includes('loadCompareMetricCatalog()'),
			'Positiv-Kontrolle: der Katalog-Ladeguard selbst muss bleiben — nur die ' +
				'ueberfluessige Kontext-Bedingung davor entfaellt'
		);
		const tautologisch = quelle
			.split('\n')
			.map((zeile, i) => ({ nr: i + 1, zeile }))
			.filter(
				({ zeile }) =>
					zeile.includes('||') &&
					zeile.includes("context === 'vergleich'") &&
					zeile.includes("context === 'route'")
			);
		assert.deepStrictEqual(
			tautologisch.map(({ nr }) => nr),
			[],
			'Eine Disjunktion ueber BEIDE Werte des Union-Typs "route" | "vergleich" ist ' +
				'immer wahr und muss ersatzlos vereinfacht werden. Fundstellen: ' +
				tautologisch.map(({ nr, zeile }) => nr + ': ' + zeile.trim()).join(' | ')
		);
	});

	const speicherModule: Array<[string[], string]> = [
		[['shared', 'alarmeVergleichSpeicherung.ts'], 'buildComparePresetSavePayload'],
		[['shared', 'versandVergleichSpeicherung.ts'], 'buildComparePresetSavePayload'],
		[['shared', 'corridor-editor', 'wertebereicheVergleichSpeicherung.ts'], 'context'],
		[['shared', 'weather-metrics-tab', 'weatherMetricsCompareSave.ts'], 'buildComparePresetSavePayload']
	];

	for (const [pfad, positivKontrolle] of speicherModule) {
		test(pfad.join('/') + ' nennt buildHubPutPayload nicht mehr', () => {
			const quelle = lies(...pfad);
			assert.ok(
				quelle.includes(positivKontrolle),
				'Positiv-Kontrolle: ' + positivKontrolle + ' muss in dieser Datei weiterhin vorkommen — ' +
					'sonst misst der Test eine leere oder falsche Datei'
			);
			const treffer = quelle
				.split('\n')
				.map((zeile, i) => ({ nr: i + 1, zeile }))
				.filter(({ zeile }) => zeile.includes('buildHubPutPayload'));
			assert.deepStrictEqual(
				treffer.map(({ nr }) => nr),
				[],
				'buildHubPutPayload wird hier nur noch in Kommentaren genannt, ohne Aufruf — ' +
					'die Nennung ist zu bereinigen (Ersetzung an Ort und Stelle, KEIN Loeschen ' +
					'von Zeilen: darunter liegen eingefrorene Ratschen-Fundstellen). Fundstellen: ' +
					treffer.map(({ nr, zeile }) => nr + ': ' + zeile.trim()).join(' | ')
			);
		});
	}
});

describe('AC-1 / Teil B: die sechs dateiinternen Signaturtypen bleiben stehen', () => {
	const signaturTypen: Array<[string[], string[]]> = [
		[['compare', 'compareHubWizardBridge.ts'], ['HubWizardFields', 'HubEdit', 'PutQueue']],
		[['compare', 'compareEditorSave.ts'], ['CompareEditorEdits', 'NewComparePresetFields']],
		[['compare', 'compareEditorLoad.ts'], ['RehydratedActiveMetrics']]
	];

	for (const [pfad, typen] of signaturTypen) {
		test(pfad.join('/') + ' traegt weiterhin ' + typen.join(', '), () => {
			const quelle = lies(...pfad);
			for (const typ of typen) {
				assert.ok(
					new RegExp('export\\s+(interface|type)\\s+' + typ + '\\b').test(quelle),
					typ + ' darf NICHT mitgeloescht werden — er traegt die Signaturen seiner ' +
						'eigenen Datei (Spec: "bleiben ausdruecklich stehen")'
				);
			}
		});
	}
});
