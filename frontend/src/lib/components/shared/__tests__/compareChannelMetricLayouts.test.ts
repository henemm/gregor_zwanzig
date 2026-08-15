// TDD RED — Issue #1703 Scheibe 8: kanal-eigene Metrik-Auswahl der
// Uebersichtstabelle im Ortsvergleich (AC-S8-10, AC-S8-11, Copy-on-write).
//
// Spec: docs/specs/modules/feat_1703_s8_compare_kanal_tabs.md
//   Abschnitt 4 ("Neues Frontend-Modul compareChannelMetricLayouts.ts"),
//   Abschnitt 3 ("Persistenz-Format"), AC-S8-10, AC-S8-11,
//   Mutations-Gegenproben M4/M5.
// Kontext: docs/context/feat-1703-s8-compare-kanal-tabs.md Risiken 3 + 4.
//
// Befund, den diese Datei rot macht: der Compare-Speicherweg kennt heute NUR
// eine flache Liste (`compareEditorSave.ts:104-130` droppt `channel_layouts`
// sogar aktiv, #1351). `internal/handler/config_merge.go:11-22` ersetzt jeden
// display_config-Top-Level-Key als GANZES und loescht nie einen Key — wer beim
// Speichern nur den zuletzt sichtbaren Kanal serialisiert, verliert die
// uebrigen (M4), und wer eine geleerte Auswahl als weggelassenen Key sendet,
// bekommt still den alten Stand zurueck (M5).
//
// Das Modul `../weather-metrics-tab/compareChannelMetricLayouts.ts` existiert
// noch NICHT -> der Import wirft einen Modul-Resolve-Fehler, ALLE Tests dieser
// Datei scheitern (RED). Muster: shared/__tests__/channelPayloadAllChannels.test.ts.
//
// Kontrakt fuer GREEN (reine Funktionen, kein Svelte-State, kein DOM):
//
//   compareChannelActiveMetricsFromStored(
//     stored: Record<string, StoredActiveMetric[]> | undefined,
//     catalog: CompareSelectionEntry[],
//   ): Record<ChannelId, string[] | null>
//     - Kanal-Key fehlt -> null (nie editiert, folgt der Grundauswahl)
//     - Kanal-Key vorhanden -> Auswahl-Schluessel, [] bleibt []
//
//   mergeAllCompareChannelActiveMetricsForSave(
//     prevStored: Record<string, StoredActiveMetric[]> | undefined,
//     channelOverrides: Record<ChannelId, string[] | null>,
//     catalog: CompareSelectionEntry[],
//   ): Record<ChannelId, StoredActiveMetric[]>
//     - JEDER Eintrag !== null wird serialisiert, nicht nur der aktive Kanal
//     - null -> Wert aus prevStored bleibt unveraendert; mutiert prevStored nicht
//     - [] -> als leeres Array serialisiert, NICHT als fehlender Key
//
//   startCompareChannelOverride(globalKeys: string[]): string[]
//     - Kopie der globalen Reihenfolge als Startpunkt (nicht leer, nicht geteilt)
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/compareChannelMetricLayouts.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import type { ChannelId } from '$lib/components/shared/layout-tab/ltChannels';
import type {
	CompareSelectionEntry,
	StoredActiveMetric
} from '../weather-metrics-tab/compareMetricSelection.ts';

const {
	compareChannelActiveMetricsFromStored,
	mergeAllCompareChannelActiveMetricsForSave,
	startCompareChannelOverride
} = await import('../weather-metrics-tab/compareChannelMetricLayouts.ts');

// Echte Katalogzeilen (Beleg: src/output/renderers/compare_metric_catalog.py).
const catalog: CompareSelectionEntry[] = [
	{ metric: 'temp_max_c', label: 'Temperatur', metric_id: 'temperature', aggregation: 'max' },
	{ metric: 'wind_max_kmh', label: 'Wind', metric_id: 'wind', aggregation: 'max' },
	{ metric: 'precip_sum_mm', label: 'Niederschlag', metric_id: 'precipitation', aggregation: 'sum' }
];

const stored = (metric_id: string, aggregation: string): StoredActiveMetric => ({
	metric_id,
	aggregation
});
const persistedEmail: StoredActiveMetric[] = [stored('temperature', 'max')];
const persistedTelegram: StoredActiveMetric[] = [stored('wind', 'max')];

describe('AC-S8-10: beim Speichern gehen ALLE editierten Kanaele mit', () => {
	test('drei nacheinander editierte Kanaele stehen alle im Ergebnis, nicht nur der letzte', () => {
		const overrides: Record<ChannelId, string[] | null> = {
			email: ['temp_max_c'],
			telegram: ['wind_max_kmh'],
			sms: ['precip_sum_mm', 'temp_max_c']
		};

		const next = mergeAllCompareChannelActiveMetricsForSave(undefined, overrides, catalog);

		assert.deepEqual(next.email, [stored('temperature', 'max')], 'AC-S8-10 FAIL: email fehlt');
		assert.deepEqual(next.telegram, [stored('wind', 'max')], 'AC-S8-10 FAIL: telegram fehlt');
		assert.deepEqual(
			next.sms,
			[stored('precipitation', 'sum'), stored('temperature', 'max')],
			'AC-S8-10 FAIL: der zuletzt editierte Kanal darf nicht der einzige serialisierte sein ' +
				'(M4) — und die Reihenfolge des Kanals bleibt positionsgetreu'
		);
	});

	test('nie editierter Kanal (null) behaelt seinen gespeicherten Stand, prevStored wird nicht mutiert', () => {
		const prev = { email: persistedEmail, telegram: persistedTelegram };
		const overrides: Record<ChannelId, string[] | null> = {
			email: null,
			telegram: null,
			sms: ['temp_max_c']
		};

		const next = mergeAllCompareChannelActiveMetricsForSave(prev, overrides, catalog);

		assert.deepEqual(
			next.email,
			persistedEmail,
			'AC-S8-10 FAIL: config_merge.go ersetzt channel_active_metrics als GANZES — ein ' +
				'nicht mitgesendeter Kanal geht lautlos verloren (BUG-DATALOSS-GR221-Muster)'
		);
		assert.deepEqual(next.telegram, persistedTelegram, 'AC-S8-10 FAIL: telegram ging verloren');
		assert.deepEqual(next.sms, [stored('temperature', 'max')]);
		assert.deepEqual(
			prev,
			{ email: persistedEmail, telegram: persistedTelegram },
			'AC-S8-10 FAIL: der uebergebene Server-Vorstand wurde mutiert'
		);
	});
});

describe('AC-S8-11: eine bewusst geleerte Kanal-Auswahl reist als [] mit', () => {
	test('leerer SMS-Override erzeugt sms: [], keinen weggelassenen Schluessel', () => {
		const prev = { sms: [stored('temperature', 'max')] };
		const overrides: Record<ChannelId, string[] | null> = {
			email: null,
			telegram: null,
			sms: []
		};

		const next = mergeAllCompareChannelActiveMetricsForSave(prev, overrides, catalog);

		assert.ok(
			Object.prototype.hasOwnProperty.call(next, 'sms'),
			'AC-S8-11 FAIL: der sms-Schluessel fehlt im Payload — config_merge.go loescht Keys NIE, ' +
				'ein weggelassener Schluessel laesst den alten Stand stehen (M5)'
		);
		assert.deepEqual(
			next.sms,
			[],
			'AC-S8-11 FAIL: die bewusste Leerauswahl muss als [] persistiert werden, nicht als ' +
				'Rueckfall auf die globale Liste'
		);
	});
});

describe('Hydration: gespeicherter Stand -> Kanal-Overrides', () => {
	test('fehlender Kanal-Key bleibt null (folgt der Grundauswahl), vorhandener wird aufgeloest', () => {
		const hydrated = compareChannelActiveMetricsFromStored(
			{ sms: [stored('wind', 'max'), stored('temperature', 'max')] },
			catalog
		);

		assert.deepEqual(hydrated.sms, ['wind_max_kmh', 'temp_max_c'], 'sms-Override nicht aufgeloest');
		assert.equal(hydrated.email, null, 'ein nie editierter Kanal muss null bleiben, nicht []');
		assert.equal(hydrated.telegram, null);
	});

	test('gespeichertes [] bleibt [] (bewusste Leerauswahl), nicht null', () => {
		const hydrated = compareChannelActiveMetricsFromStored({ sms: [] }, catalog);

		assert.deepEqual(
			hydrated.sms,
			[],
			'AC-S8-11 FAIL: nach dem Neuladen faellt die geleerte SMS-Auswahl auf die globale ' +
				'Liste zurueck — [] und "nie editiert" sind zwei verschiedene Zustaende'
		);
	});

	test('kein gespeichertes Feld (Altbestand) -> alle drei Kanaele null', () => {
		assert.deepEqual(compareChannelActiveMetricsFromStored(undefined, catalog), {
			email: null,
			telegram: null,
			sms: null
		});
	});
});

describe('Copy-on-write: der erste Kanal-Edit startet als Kopie der Grundauswahl', () => {
	test('startet inhaltlich mit der globalen Reihenfolge und teilt ihr Array nicht', () => {
		const globalKeys = ['temp_max_c', 'wind_max_kmh'];

		const override = startCompareChannelOverride(globalKeys);
		assert.deepEqual(override, globalKeys, 'der erste Kanal-Edit darf nicht leer starten');

		override.push('precip_sum_mm');
		assert.deepEqual(
			globalKeys,
			['temp_max_c', 'wind_max_kmh'],
			'FAIL: der Kanal-Override teilt sein Array mit der Grundauswahl — ein SMS-Edit ' +
				'wuerde damit die globale Auswahl und alle anderen Kanaele veraendern'
		);
	});
});
