// TDD RED — Issue #2276 Scheibe S6a (Epic #2345), AC-1 (und die Positiv-Seite
// von AC-4).
// Spec: docs/specs/modules/rework_2276_s6a_totcode_und_ratsche.md
//
// AC-1 verlangt, dass der in Befund 5 der Analyse belegte Totcode verschwindet
// UND dass die fuenf dateiinternen Signaturtypen ausdruecklich stehenbleiben.
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
// Umgebaut fuer Issue #2727 (Epic #2345, DoD-1) — Spec
// docs/specs/modules/feat_2727_compare_wizardstate_abloesen.md, AC-19/AC-22: die
// Zustandsklasse ist geloescht. Teil A misst den Totcode jetzt am Feldsatz, den Hub und
// Anlege-Editor halten (`compareFeldsatzStandard()`, compare/compareEditorSave.ts); der
// `SaveStatus`-Typ-Alias darf auch am neuen Ort nicht auftauchen; der AC-4-Block verlangt
// statt der Hub-Klasseninstanz den komponentenlokalen Feldsatz. Der Round-Trip-Nachweis zu
// AC-19 steht in compare_feldsatz_roundtrip_datenerhalt.test.ts.
// Heute rot (#2727): `compareFeldsatzStandard` fehlt, der Hub instanziiert noch die Klasse.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/totcode_rueckbau_speicherweg.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { neuerFeldsatz } from '../../shared/__tests__/compareFeldsatzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const COMPONENTS = join(HIER, '..', '..');
const lies = (...teile: string[]) => readFileSync(join(COMPONENTS, ...teile), 'utf-8');

// ── Teil A: Laufzeit (am Feldsatz, #2727) ───────────────────────────────────

describe('AC-1 / Teil A: der Ortsvergleich-Feldsatz traegt den Totcode nicht mehr', () => {
	test('Positiv-Kontrolle: der Feldsatz ist ueberhaupt bestueckt', () => {
		const felder = Object.keys(neuerFeldsatz());
		for (const feld of ['name', 'region', 'pickedIds', 'endDate', 'dayWindowStartHour']) {
			assert.ok(
				felder.includes(feld),
				'Feld ' + feld + ' muss bleiben — Positiv-Kontrolle gegen einen leeren Feldsatz'
			);
		}
	});

	test('saveComparePreset() gibt es nicht (null Aufrufer, Befund 5)', () => {
		assert.strictEqual('saveComparePreset' in neuerFeldsatz(), false, 'saveComparePreset ist zurueck');
	});

	for (const feld of [
		'subscriptionId',
		'subscriptionEnabled',
		'existingDisplayConfig',
		'includeHourly'
	]) {
		test('Feld ' + feld + ' ist entfernt (nur deklariert, null Referenzen)', () => {
			const felder = Object.keys(neuerFeldsatz());
			assert.strictEqual(
				felder.includes(feld),
				false,
				feld + ' gehoert nicht in den Feldsatz. Gefundene Felder: ' + felder.join(', ')
			);
		});
	}
});

// ── Teil B: Quelltext ──────────────────────────────────────────────────────

describe('AC-1 / Teil B: Typ-Alias, tote Bedingung und Kommentar-Leichen sind weg', () => {
	test('compareEditorSave.ts (neuer Ort der Feldsatz-Factory) exportiert keinen Typ SaveStatus', () => {
		const quelle = lies('compare', 'compareEditorSave.ts');
		assert.ok(
			/export\s+function\s+buildNewComparePresetPayload\b/.test(quelle),
			'Positiv-Kontrolle: buildNewComparePresetPayload muss in dieser Datei bleiben'
		);
		assert.strictEqual(
			/export\s+type\s+SaveStatus\b/.test(quelle),
			false,
			'export type SaveStatus darf nicht entstehen (der Name ' +
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
		[['shared', 'wetter-tab', 'wertebereicheVergleichSpeicherung.ts'], 'context'],
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

describe('AC-1 / Teil B: die fuenf dateiinternen Signaturtypen bleiben stehen', () => {
	const signaturTypen: Array<[string[], string[]]> = [
		// Issue #2375 (Spec compare_konfliktschutz_teilfelder.md §5, Risiko 6): `HubEdit`
		// entfaellt bewusst mit `buildHubPutPayload` (kein Aufrufer mehr, zweiter
		// Voll-Spread-Pfad) — die Ratsche traegt nur noch `PutQueue`.
		[['compare', 'compareHubPersistenz.ts'], ['PutQueue']],
		[['compare', 'compareHubHydration.ts'], ['HubFields']],
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

// Issue #2276 Scheibe S6f (Epic #2345), AC-4: der tote
// `setContext(<Wizard-Schluessel>, wizardState)`-Aufruf in
// CompareTabs.svelte:330 hat im gesamten Hub-Baum keinen `getContext`-Leser
// mehr (CorridorEditor(Mobile).svelte liest seit S6d aus
// `corridorPropsAus(wizardState)`) und entfaellt samt seinem Import.
// `onMount` (:140, unabhaengiger Verwendungszweck) bleibt bestehen — Positiv-Kontrolle.
// Issue #2727 (AC-22): statt der Hub-Klasseninstanz verlangt die zweite Positiv-Kontrolle jetzt den
// komponentenlokalen Feldsatz `$state(compareFeldsatzStandard())`. Der Context-Schluessel ist
// zweiteilig zusammengesetzt (Waechter compare_wizard_state_entfernt.test.ts zaehlt Code-Zeilen).
const WIZARD_SCHLUESSEL = 'compare-wizard' + '-state';
describe('AC-4 (S6f): toter setContext-Aufruf ist aus CompareTabs.svelte entfernt', () => {
	test('setContext(<Wizard-Schluessel>, …) ist weg, der lokale Feldsatz und onMount bleiben', () => {
		const quelle = lies('compare', 'CompareTabs.svelte');
		assert.ok(
			/\$state\s*\(\s*compareFeldsatzStandard\s*\(\s*\)\s*\)/.test(quelle),
			'Positiv-Kontrolle (#2727): der Hub haelt seinen Feldsatz lokal als $state(compareFeldsatzStandard())'
		);
		assert.ok(
			/\bonMount\s*\(/.test(quelle),
			'Positiv-Kontrolle: onMount() wird weiterhin gebraucht (:140) — nur setContext entfaellt'
		);
		assert.strictEqual(
			new RegExp(`setContext\\s*\\(\\s*['"]${WIZARD_SCHLUESSEL}['"]`).test(quelle),
			false,
			'setContext(<Wizard-Schluessel>, …) muss entfallen — kein getContext-Leser mehr im Hub-Baum'
		);
		assert.strictEqual(
			/import\s*\{[^}]*\bsetContext\b[^}]*\}\s*from\s*['"]svelte['"]/.test(quelle),
			false,
			'der ungenutzte setContext-Import aus \'svelte\' muss ebenfalls entfallen'
		);
	});
});
