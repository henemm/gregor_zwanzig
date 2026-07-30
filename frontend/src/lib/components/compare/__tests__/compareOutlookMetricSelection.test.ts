// TDD RED — 3-Tages-Ausblick der Vergleichs-Mail konfigurierbar (#1361 Befund 2 / #1368)
//
// Spec: docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md § AC-12, AC-13
// Kontext: docs/context/fix-1361-1368-ausblick-konfigurierbar.md
//
// Reine Verhaltenstests auf den Pure-Functions des Speicher-/Ladewegs
// (buildComparePresetSavePayload / normalizeStoredActiveMetrics) — KEIN Mock,
// KEINE Dateiinhalt-Pruefung. Muster: compareEditorHourlyMetrics.test.ts +
// compareEditorHourlyToggle.test.ts + compareActiveMetricsStorageFormat.test.ts.
//
// Der Roundtrip ist die eigentliche Aussage von AC-12: was der Editor
// speichert, muss er beim naechsten Laden in derselben Reihenfolge wieder
// anzeigen. Geschrieben wird ausschliesslich das Neuformat (Groesse +
// Auswertung, #1373) ueber DIESELBE Katalogantwort, die active_metrics bereits
// nutzt — kein viertes Vokabular.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs \
//     --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compareOutlookMetricSelection.test.ts

import { test, describe, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

import { buildComparePresetSavePayload } from '../compareEditorSave.ts';
import {
	normalizeStoredActiveMetrics,
	registerCompareMetricCatalog,
	type CompareSelectionEntry
} from '../../shared/weather-metrics-tab/compareMetricSelection.ts';
import type { ComparePreset } from '../../../types.ts';

// Ausschnitt der echten Antwort von GET /api/compare/metrics
// (compare_metric_catalog.py) — dieselbe Quelle, die der Editor bereits laedt.
const CATALOG: CompareSelectionEntry[] = [
	{ metric: 'temp_max_c', label: 'Temperatur max', metric_id: 'temperature', aggregation: 'max' },
	// Issue #1406 Scheibe A (AC-6): zweite Temperatur-Auswertung ergaenzt, damit
	// die Mehrfachauswahl-Roundtrip-Tests unten (Hoechst- UND Tiefstwert
	// gleichzeitig) beide Katalog-Eintraege real auflösen koennen.
	{ metric: 'temp_min_c', label: 'Temperatur min', metric_id: 'temperature', aggregation: 'min' },
	{ metric: 'precip_sum_mm', label: 'Niederschlag', metric_id: 'precipitation', aggregation: 'sum' },
	{ metric: 'gust_max_kmh', label: 'Böen', metric_id: 'gust', aggregation: 'max' }
];

// Der Umkehr-Index (Auswahl-Schluessel <-> Groesse+Auswertung) ist Modulzustand
// und wird im Editor beim Laden der Katalogantwort gefuellt
// (`toCompareSelectionEntries`). Jeder Test legt ihn selbst an — identisches
// Muster wie compareActiveMetricsStorageFormat.test.ts (Adversary-Befund F002
// aus #1373). GREEN-Nachtrag: in der RED-Fassung fehlte diese Zeile, der
// Speicherweg konnte die Uebersetzung deshalb strukturell nie leisten.
beforeEach(() => {
	registerCompareMetricCatalog(CATALOG);
});

function makePreset(): ComparePreset {
	return {
		id: 'preset-outlook-1368',
		name: 'Vergleich mit Ausblick',
		location_ids: ['loc-a', 'loc-b'],
		schedule: 'daily',
		previous_schedule: 'daily',
		weekday: 3,
		profil: 'summer_trekking',
		hour_from: 9,
		hour_to: 16,
		empfaenger: ['a@example.com'],
		created_at: '2026-07-01T00:00:00Z',
		display_config: { region: 'Tirol', hourly_metrics: ['temp_c', 'wind_kmh'] },
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

function displayConfigOf(body: ComparePreset): Record<string, unknown> {
	return body.display_config as unknown as Record<string, unknown>;
}

// ─── AC-12: Auswahl uebersteht Speichern + Neuladen, Reihenfolge bleibt ──────

describe('AC-12 — Ausblick-Metriken: Roundtrip Speichern → Neuladen', () => {
	test('die gewaehlte Teilmenge landet als display_config.outlook_metrics im Neuformat', () => {
		const { body } = buildComparePresetSavePayload(
			makePreset(),
			baseEdits({ outlookMetricKeys: ['temp_max_c', 'precip_sum_mm'] })
		);

		assert.deepEqual(
			displayConfigOf(body).outlook_metrics,
			[
				{ metric_id: 'temperature', aggregation: 'max' },
				{ metric_id: 'precipitation', aggregation: 'sum' }
			],
			'Die Ausblick-Auswahl erreicht die Persistenz nicht: display_config.outlook_metrics ' +
				`fehlt oder hat das falsche Format (erhalten: ${JSON.stringify(displayConfigOf(body).outlook_metrics)})`
		);
	});

	test('Speichern → Laden liefert exakt dieselbe Auswahl in derselben Reihenfolge', () => {
		const gewaehlt = ['precip_sum_mm', 'gust_max_kmh', 'temp_max_c'];

		const { body } = buildComparePresetSavePayload(
			makePreset(),
			baseEdits({ outlookMetricKeys: gewaehlt })
		);
		// Ladeweg: derselbe geteilte Leser wie fuer active_metrics (#1373).
		const wiederGeladen = normalizeStoredActiveMetrics(
			displayConfigOf(body).outlook_metrics,
			CATALOG
		);

		assert.deepEqual(
			wiederGeladen,
			gewaehlt,
			'Nach Speichern und Neuladen zeigt die Bedienflaeche nicht mehr dieselbe ' +
				`Ausblick-Auswahl/Reihenfolge (erhalten: ${JSON.stringify(wiederGeladen)})`
		);
	});

	test('bewusste Leerauswahl wird als [] persistiert, nicht geloescht', () => {
		// Der Server-Merge (mergeConfigMap, config_merge.go) ueberschreibt Keys nur,
		// loescht sie nie — ein weggelassener Key bliebe wirkungslos (analog
		// active_metrics/#1191 und hourly_metrics/#1299).
		const { body } = buildComparePresetSavePayload(
			makePreset(),
			baseEdits({ outlookMetricKeys: [] })
		);

		assert.deepEqual(
			displayConfigOf(body).outlook_metrics,
			[],
			'Eine bewusst geleerte Ausblick-Auswahl muss explizit als [] gespeichert werden'
		);
	});

	test('unangetastete Ausblick-Auswahl bleibt per Read-Modify-Write erhalten', () => {
		const original = makePreset();
		(original.display_config as unknown as Record<string, unknown>).outlook_metrics = [
			{ metric_id: 'temperature', aggregation: 'max' }
		];

		// outlookMetricKeys absichtlich weggelassen (= Feld nicht editiert).
		const { body } = buildComparePresetSavePayload(original, baseEdits());

		assert.deepEqual(
			displayConfigOf(body).outlook_metrics,
			[{ metric_id: 'temperature', aggregation: 'max' }],
			'Eine nicht editierte Ausblick-Auswahl darf beim Speichern nicht verloren gehen'
		);
	});

	test('Ausblick-Auswahl und Stundenverlauf-Auswahl bleiben getrennte Felder', () => {
		const { body } = buildComparePresetSavePayload(
			makePreset(),
			baseEdits({
				outlookMetricKeys: ['temp_max_c'],
				hourlyMetricKeys: ['temp_c', 'wind_kmh']
			})
		);
		const dc = displayConfigOf(body);

		assert.deepEqual(dc.hourly_metrics, ['temp_c', 'wind_kmh']);
		assert.deepEqual(dc.outlook_metrics, [{ metric_id: 'temperature', aggregation: 'max' }]);
	});
});

// ─── AC-6 (Issue #1406 Scheibe A) — Persistenz zeichengleich vor/nach dem ────
// Auswahl-Block-Umbau: buildComparePresetSavePayload/normalizeStoredActiveMetrics
// sind Pure-Functions auf outlookMetricKeys, unabhaengig von der Svelte-Markup-
// Form des Auswahl-Blocks (flache Liste vs. gruppiertes AggregationMetricRow-
// Muster). Der deterministische Nachweisweg fuer AC-6 (PO-informierte
// Tech-Lead-Entscheidung, Kontingent-Schonung #1329, s. Spec § AC-6): dieselbe
// Auswahl liefert vor UND nach dem Umbau exakt dasselbe display_config.
// outlook_metrics — insbesondere die Temperatur-Mehrfachauswahl (Hoechst- UND
// Tiefstwert gleichzeitig aktiv), die im Ausblick nach diesem Umbau erstmals
// ueber ein AggregationMetricRow-Kaestchenpaar statt zwei flacher Checkboxen
// bedient wird.
//
// Spec: docs/specs/modules/feat_1406a_ausblick_geteiltes_element.md § AC-6, Test-Plan

describe('AC-6 — Persistenz-Roundtrip bleibt zeichengleich, unabhaengig von der Auswahl-Block-Markup-Form', () => {
	test('Temperatur Hoechst- UND Tiefstwert gleichzeitig aktiv: display_config.outlook_metrics exakt wie vor dem Auswahl-Block-Umbau', () => {
		const { body } = buildComparePresetSavePayload(
			makePreset(),
			baseEdits({ outlookMetricKeys: ['temp_max_c', 'temp_min_c', 'precip_sum_mm'] })
		);

		assert.deepEqual(
			displayConfigOf(body).outlook_metrics,
			[
				{ metric_id: 'temperature', aggregation: 'max' },
				{ metric_id: 'temperature', aggregation: 'min' },
				{ metric_id: 'precipitation', aggregation: 'sum' }
			],
			'AC-6 FAIL: display_config.outlook_metrics weicht bei gleichzeitig aktivem Hoechst- UND ' +
				`Tiefstwert der Temperatur ab (erhalten: ${JSON.stringify(displayConfigOf(body).outlook_metrics)}). ` +
				'Ein reiner Auswahl-Block-Markup-Umbau (Issue #1406 Scheibe A) darf dieses Format nicht aendern — ' +
				'weicht es doch ab, ist AC-6 nicht mehr deterministisch belegbar und die Staging-Mail-Verifikation ' +
				'(email_spec_validator.py) muss nachgeholt werden.'
		);
	});

	test('Roundtrip: dieselbe Mehrfachauswahl geladen -> dieselben Auswahl-Schluessel, keine Verschmelzung von max/min', () => {
		const gewaehlt = ['temp_max_c', 'temp_min_c'];
		const { body } = buildComparePresetSavePayload(makePreset(), baseEdits({ outlookMetricKeys: gewaehlt }));
		const wiederGeladen = normalizeStoredActiveMetrics(displayConfigOf(body).outlook_metrics, CATALOG);

		assert.deepEqual(
			wiederGeladen,
			gewaehlt,
			'AC-6 FAIL: nach Speichern und Neuladen der Temperatur-Mehrfachauswahl (max+min) zeigt die ' +
				`Bedienflaeche nicht mehr dieselben zwei Auswahl-Schluessel (erhalten: ${JSON.stringify(wiederGeladen)}).`
		);
	});
});

// ─── AC-13 (Bedienflaeche): Ausblick-Schalter erreicht die Persistenz ────────

describe('AC-13 — Ausblick-Schalter im Speicher-Payload', () => {
	test('outlookEnabled=false landet als Top-Level outlook_enabled im PUT-Body', () => {
		const { body } = buildComparePresetSavePayload(
			makePreset(),
			baseEdits({ outlookEnabled: false })
		);

		assert.equal(
			(body as unknown as Record<string, unknown>).outlook_enabled,
			false,
			'Der ausgeschaltete 3-Tages-Ausblick erreicht die Go-API nicht — ' +
				'outlook_enabled fehlt im PUT-Body (heute gibt es dafuer gar keine Bedienflaeche)'
		);
	});

	test('unangetasteter Schalter wird nicht ueberschrieben (Round-Trip via original)', () => {
		const original = makePreset();
		(original as unknown as Record<string, unknown>).outlook_enabled = false;

		// outlookEnabled absichtlich weggelassen (= Feld nicht editiert).
		const { body } = buildComparePresetSavePayload(original, baseEdits());

		assert.equal(
			(body as unknown as Record<string, unknown>).outlook_enabled,
			false,
			'Ein nicht editierter Ausblick-Schalter darf beim Speichern nicht kippen'
		);
	});
});
