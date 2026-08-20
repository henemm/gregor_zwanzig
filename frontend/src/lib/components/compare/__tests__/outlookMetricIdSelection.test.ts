// RED — #1848 A2: der 3-Tages-Ausblick spricht Kennungen, nicht Paare.
//
// Spec: docs/specs/modules/feat_1848_a2_ausblick_kennungen.md — AC-8
//       (dazu die Frontend-Haelfte von AC-1/AC-2)
// Kontext: docs/context/feat-1848-a2-outlook-kennungen.md — Abschnitt
//          „ZUSCHNITT-VERSCHIEBUNG: Frontend-Schluessel sind NICHT Kennungen"
//
// AC-8 verlangt, dass die Ausblick-Auswahl fuer Temperatur und fuer gefuehlte
// Temperatur JE EINEN EINZIGEN Eintrag zeigt — in BEIDEN Flaechen, im
// Trip-Editor wie im Ortsvergleich-Editor.
//
// 🔴 Warum das hier ohne Komponenten-Harness geprueft wird: das Projekt hat
// keine Svelte-Testinfrastruktur (kein @testing-library/svelte, kein jsdom;
// `npm test` ist der eingebaute node:test-Runner). Geprueft werden deshalb
// genau die Funktionen, die `CompareOutlookLayoutControls.svelte` tatsaechlich
// aufruft — und diese Komponente ist die EINZIGE Ausblick-Bedienflaeche:
// `WeatherMetricsTab.svelte` mountet sie zweimal (`:1400` Ortsvergleich,
// `:1783` Trip). Was fuer diese Funktionen gilt, gilt damit fuer beide
// Flaechen; ein Trip-eigener Auswahl-Baustein existiert nicht und duerfte
// nach der Trip/Compare-Teilungs-Invariante auch nicht entstehen.
//
// Die Anzeige (`materializeOutlookMetricKeys`) und der Umschalt-Pfad
// (`toggleOutlookMetricKeyFromState`) MUESSEN dasselbe Vokabular sprechen
// (Issue #1366 F001) — deshalb stehen beide hier.
//
// Reine Verhaltenstests auf den Pure-Functions des Lese-/Schreibwegs, kein
// Mock, keine Dateiinhalt-Pruefung. Muster:
// compareOutlookMetricSelection.test.ts.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs \
//     --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/outlookMetricIdSelection.test.ts

import { test, describe, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

import {
	buildComparePresetSavePayload,
	buildNewComparePresetPayload
} from '../compareEditorSave.ts';
import { hydrateLayoutFieldsFromPreset } from '../compareHubWizardBridge.ts';
import {
	registerCompareMetricCatalog,
	type CompareSelectionEntry
} from '../../shared/weather-metrics-tab/compareMetricSelection.ts';
import {
	materializeOutlookMetricKeys,
	toggleOutlookMetricKeyFromState
} from '../../shared/weather-metrics-tab/compareMetricOrder.ts';
import type { ComparePreset } from '../../../types.ts';

// Ausschnitt der echten Antwort von GET /api/compare/metrics
// (compare_metric_catalog.py, abgelesen 2026-08-20) — inklusive BEIDER
// mehrdeutiger Groessen: temperature und wind_chill tragen je zwei
// Auswertungen, alle uebrigen genau eine.
const CATALOG: CompareSelectionEntry[] = [
	{ metric: 'temp_max_c', label: 'Temperatur', metric_id: 'temperature', aggregation: 'max', aggregation_label: 'Maximum' },
	{ metric: 'temp_min_c', label: 'Temperatur', metric_id: 'temperature', aggregation: 'min', aggregation_label: 'Minimum' },
	{ metric: 'wind_chill_min_c', label: 'Gefühlte Temperatur', metric_id: 'wind_chill', aggregation: 'min', aggregation_label: 'Minimum' },
	{ metric: 'wind_chill_max_c', label: 'Gefühlte Temperatur', metric_id: 'wind_chill', aggregation: 'max', aggregation_label: 'Maximum' },
	{ metric: 'precip_sum_mm', label: 'Niederschlag', metric_id: 'precipitation', aggregation: 'sum', aggregation_label: 'Summe' },
	{ metric: 'pop_max_pct', label: 'Regenwahrscheinlichkeit', metric_id: 'rain_probability', aggregation: 'max', aggregation_label: 'Maximum' },
	{ metric: 'wind_max_kmh', label: 'Wind', metric_id: 'wind', aggregation: 'max', aggregation_label: 'Maximum' },
	{ metric: 'gust_max_kmh', label: 'Böen', metric_id: 'gust', aggregation: 'max', aggregation_label: 'Maximum' },
	{ metric: 'thunder_level_max', label: 'Gewitter', metric_id: 'thunder', aggregation: 'max', aggregation_label: 'Maximum' }
] as unknown as CompareSelectionEntry[];

// Der Umkehr-Index ist Modulzustand und wird im Editor beim Laden der
// Katalogantwort gefuellt — jeder Test legt ihn selbst an (Muster
// compareActiveMetricsStorageFormat.test.ts, Adversary-Befund F002 aus #1373).
beforeEach(() => {
	registerCompareMetricCatalog(CATALOG);
});

/** Groesse eines Auswahl-Eintrags: entweder ist er bereits die Kennung, oder
 *  er ist ein Katalog-Schluessel, dessen Zeile die Kennung nennt. So bleibt
 *  der Test unabhaengig davon, welche Schreibweise die Liste fuehrt — er
 *  zaehlt nur, wie viele EINTRAEGE auf dieselbe Groesse zeigen. */
function metricIdOf(key: string): string {
	const hit = CATALOG.find((e) => e.metric === key);
	return hit?.metric_id ?? key;
}

function eintraegeJeGroesse(keys: string[]): Record<string, number> {
	const zaehler: Record<string, number> = {};
	for (const key of keys) {
		const id = metricIdOf(key);
		zaehler[id] = (zaehler[id] ?? 0) + 1;
	}
	return zaehler;
}

function makePreset(displayConfig: Record<string, unknown>): ComparePreset {
	return {
		id: 'preset-1848-a2',
		name: 'Vergleich mit Ausblick',
		location_ids: ['loc-a', 'loc-b'],
		schedule: 'daily',
		profil: 'summer_trekking',
		hour_from: 9,
		hour_to: 16,
		empfaenger: ['a@example.com'],
		created_at: '2026-08-20T00:00:00Z',
		display_config: displayConfig,
		hourly_enabled: true
	} as unknown as ComparePreset;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function baseEdits(extra: Record<string, unknown> = {}): any {
	return {
		name: 'Vergleich mit Ausblick',
		activityProfile: 'summer_trekking',
		pickedIds: ['loc-a', 'loc-b'],
		region: 'Tirol',
		idealRanges: {},
		...extra
	};
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function newPresetFields(extra: Record<string, unknown> = {}): any {
	return {
		name: 'Neuer Vergleich',
		pickedIds: ['loc-a', 'loc-b'],
		activityProfile: 'summer_trekking',
		schedule: 'daily_morning',
		officialAlertsEnabled: false,
		radarAlertEnabled: false,
		hourlyEnabled: true,
		outlookEnabled: true,
		officialAlertTriggersEnabled: false,
		sendTelegram: false,
		sendSms: false,
		sendPremiumSms: false,
		officialWarningsEnabled: false,
		morningEnabled: true,
		morningTime: '06:00',
		eveningEnabled: false,
		eveningTime: '18:00',
		endDate: null,
		dayWindowStartHour: 4,
		dayWindowEndHour: 19,
		corridors: [],
		region: 'Tirol',
		idealRanges: {},
		activeMetricKeys: null,
		hourlyMetricKeys: null,
		metricAlertLevels: {},
		...extra
	};
}

function displayConfigOf(body: unknown): Record<string, unknown> {
	return (body as ComparePreset).display_config as unknown as Record<string, unknown>;
}

// ─── AC-8: je Groesse genau EIN Eintrag in der Auswahlliste ─────────────────

describe('AC-8 — die Ausblick-Auswahl zeigt je Groesse einen einzigen Eintrag', () => {
	test('die Vorbelegung („nie eingestellt") fuehrt Temperatur genau einmal', () => {
		const angezeigt = materializeOutlookMetricKeys(null);
		const zaehler = eintraegeJeGroesse(angezeigt);

		assert.equal(
			zaehler['temperature'],
			1,
			`Die Ausblick-Auswahl zeigt ${zaehler['temperature']} Eintraege fuer die Temperatur ` +
				`(angezeigt: ${JSON.stringify(angezeigt)}). AC-8 verlangt EINEN einzigen Eintrag ` +
				'„Temperatur" statt getrennter Kaestchen fuer Minimum und Maximum — die Oberflaeche ' +
				'verspricht sonst eine Halbauswahl, die das Backend nach A2 gar nicht mehr ' +
				'speichern kann (Kontext, Abschnitt ZUSCHNITT-VERSCHIEBUNG).'
		);
		const mehrfach = Object.entries(zaehler).filter(([, n]) => n > 1);
		assert.deepEqual(
			mehrfach,
			[],
			`Diese Groessen erscheinen mehrfach in der Ausblick-Auswahl: ${JSON.stringify(mehrfach)} ` +
				`(angezeigt: ${JSON.stringify(angezeigt)}). AC-8: je Groesse ein Eintrag.`
		);
	});

	test('ein Klick auf „Temperatur" waehlt die Groesse ab, statt einen weiteren Eintrag anzuhaengen', () => {
		const vorher = materializeOutlookMetricKeys(null);
		const nachher = toggleOutlookMetricKeyFromState(null, 'temperature');

		assert.equal(
			nachher.filter((k) => metricIdOf(k) === 'temperature').length,
			0,
			`Nach dem Klick auf „Temperatur" steht die Groesse weiterhin in der Auswahl: ` +
				`${JSON.stringify(nachher)} (vorher: ${JSON.stringify(vorher)}). Anzeige und ` +
				'Umschalt-Pfad muessen dasselbe Vokabular sprechen (#1366 F001) — sonst fuegt ein ' +
				'Klick auf den einen sichtbaren Eintrag einen zusaetzlichen hinzu, statt ihn ' +
				'abzuwaehlen (AC-8).'
		);
		assert.ok(
			nachher.length < vorher.length,
			`Die Auswahl ist nach dem Abwaehlen nicht kuerzer geworden: ${JSON.stringify(vorher)} ` +
				`-> ${JSON.stringify(nachher)} (AC-8).`
		);
	});

	test('gefuehlte Temperatur verhaelt sich wie die Temperatur — ein Eintrag, ein Klick', () => {
		// Ausgangslage aus einer BESTANDS-Auswahl, in der Tief UND Hoch der
		// gefuehlten Temperatur gespeichert sind: die Bedienflaeche zeigt dafuer
		// eine Zeile, ein Klick darauf muss die Groesse ganz abwaehlen.
		const geladen = hydrateLayoutFieldsFromPreset(
			makePreset({
				outlook_metrics: [
					{ metric_id: 'wind_chill', aggregation: 'min' },
					{ metric_id: 'wind_chill', aggregation: 'max' },
					{ metric_id: 'precipitation', aggregation: 'sum' }
				]
			}),
			CATALOG
		).outlookMetricKeys;
		const nachher = toggleOutlookMetricKeyFromState(geladen, 'wind_chill');

		assert.deepEqual(
			nachher,
			['precipitation'],
			`Ein Klick auf „Gefühlte Temperatur" ergab ${JSON.stringify(nachher)} statt ` +
				`['precipitation'] (Ausgangslage: ${JSON.stringify(geladen)}). Auch diese Groesse ` +
				'traegt zwei Auswertungen und muss als EIN Eintrag gefuehrt werden, den EIN Klick ' +
				'vollstaendig abwaehlt (AC-8).'
		);
	});
});

// ─── Lesen: die Paar-Altform wird zu je einer Kennung ────────────────────────

describe('Lesepfad — gespeicherte Paare werden zu je einer Kennung', () => {
	test('Bestands-Preset mit Temperatur min UND max zeigt einen einzigen Eintrag; die Drei-Werte-Semantik bleibt', () => {
		const bestand = hydrateLayoutFieldsFromPreset(
			makePreset({
				outlook_metrics: [
					{ metric_id: 'temperature', aggregation: 'min' },
					{ metric_id: 'temperature', aggregation: 'max' },
					{ metric_id: 'precipitation', aggregation: 'sum' }
				]
			}),
			CATALOG
		);

		assert.deepEqual(
			bestand.outlookMetricKeys,
			['temperature', 'precipitation'],
			`Die geladene Ausblick-Auswahl lautet ${JSON.stringify(bestand.outlookMetricKeys)} statt ` +
				"['temperature', 'precipitation']. Tief und Hoch derselben Groesse muessen beim Lesen " +
				'zu EINEM Eintrag werden, sonst erscheint „Temperatur" doppelt in der Auswahl (AC-2/AC-8).'
		);

		// Gegenprobe im selben Test: das Zusammenfassen darf die beiden anderen
		// Zustaende nicht einebnen — sonst waere „nie eingestellt" (sieben feste
		// Spalten) von „bewusst geleert" (Block entfaellt) nicht mehr zu trennen.
		assert.equal(
			hydrateLayoutFieldsFromPreset(makePreset({}), CATALOG).outlookMetricKeys,
			null,
			'Ein Preset ohne gespeicherte Ausblick-Auswahl muss als null zurueckkommen (AC-7).'
		);
		assert.deepEqual(
			hydrateLayoutFieldsFromPreset(makePreset({ outlook_metrics: [] }), CATALOG)
				.outlookMetricKeys,
			[],
			'Eine bewusst geleerte Auswahl muss als [] zurueckkommen, nicht als null (AC-7).'
		);
	});
});

// ─── Schreiben: reine Kennungen, kein Paar-Objekt ────────────────────────────

describe('Schreibpfad — display_config.outlook_metrics fuehrt reine Kennungen', () => {
	// 🔴 Beide Eingabeformen in EINEM Test: der Schreibweg reicht eine bereits
	// kennungsfoermige Auswahl heute schon unveraendert durch (weil kein
	// Katalog-Eintrag auf sie passt) — dieser Teil allein bewiese nichts. Die
	// Aussage von A2 ist, dass der Ausblick-Schreibweg UEBERHAUPT KEIN
	// Paar-Objekt mehr konstruiert, egal was er bekommt. Er muss die
	// Paar-Uebersetzung verlassen, so wie `hourly_metrics` es laengst getan hat
	// (compareEditorSave.ts:167 schreibt dort ungewandelte Zeichenketten).
	test('Hub-Speichern konstruiert kein Paar-Objekt — und laesst active_metrics unberuehrt', () => {
		const { body } = buildComparePresetSavePayload(
			makePreset({}),
			baseEdits({ outlookMetricKeys: ['temperature', 'precipitation'] })
		);
		assert.deepEqual(
			displayConfigOf(body).outlook_metrics,
			['temperature', 'precipitation'],
			`Gespeichert wurde ${JSON.stringify(displayConfigOf(body).outlook_metrics)} statt ` +
				"['temperature', 'precipitation'] (AC-1)."
		);

		const { body: altBody } = buildComparePresetSavePayload(
			makePreset({}),
			baseEdits({
				activeMetricKeys: ['temp_max_c', 'precip_sum_mm'],
				outlookMetricKeys: ['temp_max_c', 'precip_sum_mm']
			})
		);
		const ausblick = displayConfigOf(altBody).outlook_metrics as unknown[];
		assert.ok(
			Array.isArray(ausblick) && ausblick.every((e) => typeof e === 'string'),
			`Der Ausblick-Schreibweg hat aus der Auswahl Paar-Objekte gebaut: ` +
				`${JSON.stringify(ausblick)}. Nach A2 speichert der Ausblick ausschliesslich ` +
				'Zeichenketten — die Auswertung leitet der Katalog serverseitig ab (AC-1).'
		);

		// Gegenprobe: A2 aendert das Format des AUSBLICKS. Die Uebersichts-
		// Grundauswahl `active_metrics` behaelt ihr Paar-Format (ADR-0037) — wer
		// einfach `toStoredActiveMetrics()` umbaut, aendert unbeabsichtigt auch sie.
		assert.deepEqual(
			displayConfigOf(altBody).active_metrics,
			[
				{ metric_id: 'temperature', aggregation: 'max' },
				{ metric_id: 'precipitation', aggregation: 'sum' }
			],
			'Die Uebersichts-Grundauswahl `active_metrics` hat ihr Paar-Format verloren: ' +
				`${JSON.stringify(displayConfigOf(altBody).active_metrics)}. A2 stellt nur den ` +
				'Ausblick um.'
		);
	});

	test('Neuanlage konstruiert kein Paar-Objekt und haelt die Drei-Werte-Semantik', () => {
		const gefuellt = buildNewComparePresetPayload(
			newPresetFields({ outlookMetricKeys: ['temperature', 'gust'] })
		);
		assert.deepEqual(
			displayConfigOf(gefuellt).outlook_metrics,
			['temperature', 'gust'],
			`Die Neuanlage speicherte ${JSON.stringify(displayConfigOf(gefuellt).outlook_metrics)} ` +
				"statt ['temperature', 'gust'] (AC-1)."
		);

		const ausKatalogschluesseln = buildNewComparePresetPayload(
			newPresetFields({ outlookMetricKeys: ['temp_max_c', 'gust_max_kmh'] })
		);
		const ausblick = displayConfigOf(ausKatalogschluesseln).outlook_metrics as unknown[];
		assert.ok(
			Array.isArray(ausblick) && ausblick.every((e) => typeof e === 'string'),
			`Die Neuanlage hat Paar-Objekte gebaut: ${JSON.stringify(ausblick)} (AC-1).`
		);

		assert.ok(
			!(
				'outlook_metrics' in
				displayConfigOf(buildNewComparePresetPayload(newPresetFields({ outlookMetricKeys: null })))
			),
			'„Nie eingestellt" muss den Schluessel weglassen (Resolver erkennt „Feld fehlt" = ' +
				'sieben feste Spalten) (AC-7).'
		);
		assert.deepEqual(
			displayConfigOf(buildNewComparePresetPayload(newPresetFields({ outlookMetricKeys: [] })))
				.outlook_metrics,
			[],
			'Eine bewusst geleerte Auswahl muss als [] gesendet werden (Block entfaellt) (AC-7).'
		);
	});
});
