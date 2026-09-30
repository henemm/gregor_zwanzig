// TDD GREEN (Fix-Loop 1) — Bug #2454, Finding F001 (Adversary BROKEN).
//
// Der Adversary hat belegt, dass `deriveMissingChildMetrics()`/
// `moveWithDerivedChildren()` selbst solide unit-getestet sind (s.
// `kindmetriken_ableitung_und_mitnahme.test.ts`), der WIRKORT in
// `WeatherMetricsTab.svelte::initFromTrip()` (Bucket-Zerlegung aus
// `display_config.metrics`) aber von keinem Test erreicht wurde -- ein
// entfernter Aufruf blieb im vollen 3667-Test-Lauf unentdeckt.
//
// Fix-Loop 1 zieht die komplette Bucket-Zerlegung (inkl. der drei
// initFromTrip()-Zweige: hasBuckets / autoAssign / trip_default_enabled)
// als reine, exportierte Funktion `computeInitialBuckets()` nach
// metricsEditor.ts -- DIESELBE Funktion ruft jetzt sowohl
// `WeatherMetricsTab.svelte::initFromTrip()` als auch der Test-Nachbau
// `_editor_kette.ts::ladeInEditorState()` auf. Diese Datei bewacht die
// Funktion selbst; die Verdrahtung IN der .svelte-Komponente kann eine
// Node-Unit-Harness nicht erreichen ($effect/load() laufen dort nicht) --
// dafuer ist die Playwright-E2E-Spec zustaendig (docs/artifacts/.../
// test-green-output.txt dokumentiert, ob sie lokal gelaufen ist).
//
// Mutations-Gegenprobe (Fix-Loop 1, manuell, s. Rueckmeldung): Aufruf von
// `deriveMissingChildMetrics()` INNERHALB von `computeInitialBuckets()`
// entfernt -> Testfall 1 unten wird rot.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/trip-detail/bug_2454_wirkort_verdrahtung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import { computeInitialBuckets, CATEGORY_ORDER, type MetricCatalog } from './metricsEditor.ts';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const catalog: MetricCatalog = JSON.parse(
	readFileSync(
		path.join(__dirname, '../shared/weather-metrics-tab/__tests__/fixtures/metric_catalog_selectable.json'),
		'utf-8',
	),
);

// Fix-Loop 1 (Advisor-Befund): computeInitialBuckets() bekommt `allIds` jetzt
// als expliziten Parameter (Ordering-Fidelity zu WeatherMetricsTab.svelte::
// allCatalogIds() -- CATEGORY_ORDER zuerst, NICHT die rohe Objekt-Reihenfolge
// von metricsEditor.ts's privater allCatalogIds()). Nachbau derselben Regel.
function allIdsWieImEditor(cat: MetricCatalog): string[] {
	return CATEGORY_ORDER.filter((c) => c in cat)
		.concat(Object.keys(cat).filter((c) => !CATEGORY_ORDER.includes(c)))
		.flatMap((c) => (cat[c] ?? []).map((m) => m.id));
}
const allIds = allIdsWieImEditor(catalog);

describe('Bug #2454 F001: computeInitialBuckets() -- Wirkort von initFromTrip()', () => {
	test('Elter aktiv (mit bucket/order), Kind fehlt -> Kind erscheint im selben primary-Bucket', () => {
		const savedMetrics = [
			{ metric_id: 'wind_chill', enabled: true, bucket: 'primary', order: 0 },
		];
		const b = computeInitialBuckets(catalog, {}, savedMetrics, allIds);

		for (const kind of ['wind_chill_day_low', 'wind_chill_day_high', 'wind_chill_night']) {
			assert.ok(
				b.primary.includes(kind),
				`Bug #2454: ${kind} fehlt in primary -- computeInitialBuckets() muss fehlende Kind-Eintraege ` +
				`ableiten (deriveMissingChildMetrics), sonst kommt der urspruengliche Bug zurueck.\n` +
				`primary: ${JSON.stringify(b.primary)}`,
			);
		}
	});

	test('bereits expliziter Kind-Eintrag enabled:false bleibt aus', () => {
		const savedMetrics = [
			{ metric_id: 'wind_chill', enabled: true, bucket: 'primary', order: 0 },
			{ metric_id: 'wind_chill_day_low', enabled: false },
		];
		const b = computeInitialBuckets(catalog, {}, savedMetrics, allIds);

		assert.ok(!b.primary.includes('wind_chill_day_low'), 'DEC-6: expliziter false-Eintrag darf nicht überschrieben werden');
		assert.ok(b.primary.includes('wind_chill_day_high'), 'das nicht abgewaehlte Geschwister-Kind bleibt aktiv');
	});

	test('kein display_config.metrics (undefined) -> Vorbelegung nach trip_default_enabled greift weiterhin (#1552)', () => {
		const metricById = { wind: { trip_default_enabled: true } };
		const b = computeInitialBuckets(catalog, metricById, undefined, allIds);
		assert.ok(b.primary.includes('wind'), 'Issue #1552: Vorbelegung ueber trip_default_enabled darf durch die Extraktion nicht verlorengehen');
	});

	test('Alt-Bestand ohne bucket/order-Felder faellt auf autoAssign zurueck', () => {
		const savedMetrics = [{ metric_id: 'wind', enabled: true }];
		const b = computeInitialBuckets(catalog, {}, savedMetrics, allIds);
		assert.ok(b.primary.includes('wind'), 'Alt-Bestand (kein bucket/order) muss ueber autoAssign aktiv werden');
	});
});
