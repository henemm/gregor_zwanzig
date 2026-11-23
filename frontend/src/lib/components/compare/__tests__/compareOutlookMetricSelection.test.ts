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
	normalizeStoredOutlookMetrics,
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

// Issue #3276 (Spec-AC-38, AC-2): `outlook_metrics` ist Altschluessel. Der Ortsvergleich schreibt
// die Ausblick-Auswahl nicht mehr (Einstellung nur in „Was steht wo"). Die drei Schreib-Tests
// (Teilmenge im Kennungsformat, Speichern→Laden, bewusste Leerauswahl []) sind durch die
// Gegenprobe ersetzt: ein Editor-Wert erreicht den Rumpf nicht, auch nicht als [].
describe('AC-12 — Ausblick-Metriken (seit #3276: nur Bestand, kein Schreiben)', () => {
	for (const auswahl of [['temperature', 'precipitation'], []]) {
		test(`Editor-Wert ${JSON.stringify(auswahl)} wird nicht als display_config.outlook_metrics geschrieben`, () => {
			const { body } = buildComparePresetSavePayload(makePreset(), baseEdits({ outlookMetricKeys: auswahl }));
			assert.ok(
				!('outlook_metrics' in displayConfigOf(body)),
				`#3276: outlook_metrics im Rumpf: ${JSON.stringify(displayConfigOf(body).outlook_metrics)}`
			);
		});
	}

	test('unangetastete Ausblick-Auswahl bleibt per Read-Modify-Write erhalten', () => {
		// Bewusst in der PAAR-ALTFORM abgelegt: genau so liegen Bestandsdaten
		// auf der Platte. Ein nicht editiertes Feld wird unveraendert
		// durchgereicht, nicht umgeschrieben — Read-Modify-Write, kein
		// Blind-Replace (Fehlerklasse #102).
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

	// #3276: „Ausblick- und Stundenverlauf-Auswahl bleiben getrennte Felder" entfaellt — beide
	// werden nicht mehr geschrieben; der Bestand beider Felder bleibt unveraendert.
	test('Ausblick- und Stundenverlauf-Bestand bleiben unveraendert, auch gegen Editor-Werte', () => {
		const { body } = buildComparePresetSavePayload(
			makePreset(),
			baseEdits({ outlookMetricKeys: ['temperature'], hourlyMetricKeys: ['visibility_m'] })
		);
		const dc = displayConfigOf(body);
		assert.deepEqual(dc.hourly_metrics, ['temp_c', 'wind_kmh']);
		assert.ok(!('outlook_metrics' in dc));
	});
});

// ─── AC-6 (Issue #1406 Scheibe A) — UMGESTELLT in Issue #1848 Scheibe A2 ─────
//
// Ursprünglich sicherte AC-6 zu: ein reiner Markup-Umbau des Auswahl-Blocks
// darf `display_config.outlook_metrics` nicht verändern — belegt an der
// Temperatur-Mehrfachauswahl (Höchst- UND Tiefstwert gleichzeitig aktiv), die
// damals über ein AggregationMetricRow-Kästchenpaar bedient wurde.
//
// A2 ändert das Speicherformat ABSICHTLICH (Spec AC-1/AC-8, PO-Entscheid
// 2026-08-20): gespeichert wird die Kennung, und beide Temperatur-Enden sind
// EIN Eintrag — sie ergeben seit #1848 A1 EINE Spannen-Spalte `9/27`. Die
// Kästchenpaar-Bedienung ist damit entfallen.
//
// Die Zusicherung bleibt der Sache nach erhalten und wird hier auf den
// heutigen Sollzustand gedreht: die Bedienfläche und die Persistenz sprechen
// dasselbe Vokabular, die Auswahl übersteht Speichern und Neuladen
// zeichengleich, und aus einer Größe wird nie mehr als ein Eintrag.
//
// Spec: docs/specs/modules/feat_1406a_ausblick_geteiltes_element.md § AC-6
//       docs/specs/modules/feat_1848_a2_ausblick_kennungen.md § AC-1/AC-8

describe('AC-6 [#1848 A2] — Persistenz-Roundtrip bleibt zeichengleich, unabhaengig von der Auswahl-Block-Markup-Form', () => {
	// #3276: der Schreib-Teil (Temperatur als EIN Eintrag im Rumpf) entfaellt — der Ortsvergleich
	// schreibt `outlook_metrics` nicht mehr. Der Lese-Teil (Bestand) bleibt unten.
	test('Roundtrip: eine BESTANDS-Mehrfachauswahl (max+min) kommt als EIN Eintrag zurueck', () => {
		// Die Gegenrichtung zum Test darueber: so liegt die Auswahl in
		// Bestandsdaten auf der Platte. Der Leser darf sie nicht als zwei
		// Eintraege anzeigen — die Bedienflaeche zeigt seit A2 EINE Zeile
		// „Temperatur", und ein Klick darauf schaltet die ganze Groesse.
		const gespeichert = [
			{ metric_id: 'temperature', aggregation: 'max' },
			{ metric_id: 'temperature', aggregation: 'min' }
		];
		const wiederGeladen = normalizeStoredOutlookMetrics(gespeichert, CATALOG);

		assert.deepEqual(
			wiederGeladen,
			['temperature'],
			'AC-6 FAIL: die Bestands-Mehrfachauswahl (max+min) erscheint als ' +
				`${JSON.stringify(wiederGeladen)} statt als ein einziger Eintrag ['temperature'].`
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
