// #3047 N3: Altbestand `morning_enabled`/`evening_enabled` je Trip-Metrik.
//
// Der Editor bietet die Bericht-Flags nicht an (Phase 2: #3065), aber
//   (a) er kennzeichnet sichtbar je Metrik „nur morgens"/„nur abends", wenn sie
//       nur in EINEM Bericht erscheint -- Semantik wie die Mail
//       (src/app/models.py::_filter_metrics_by_report_type: Bericht-Flag
//       true/false gewinnt, sonst `enabled`);
//   (b) er bewahrt die Flags beim Speichern (Read-Modify-Write).
// Geprueft am echten Reiter: der Attribut-Ausdruck `nurBerichtById={...}` der
// Grundauswahl-Einbettung in WeatherMetricsTab.svelte wird mit dem Editor-Zustand
// ausgewertet und WeatherV2Grundauswahl damit per svelte/server gerendert.
//
//   cd frontend && npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/nur_ein_bericht_kennzeichnung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register, stripTypeScriptTypes } from 'node:module';
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { parse } from 'svelte/compiler';

import * as metricsEditor from '../../../trip-detail/metricsEditor.ts';
import { toggleGlobalMetric } from '../channelMetricLayouts.ts';
import { buildGlobalMetricsForSave } from '../weatherMetricsSavePayload.ts';
import { nurEinBericht, nurEinBerichtJeMetrik } from '../nurEinBericht.ts';
import { attributAusdruck, findeKomponenten, werte } from '../../__tests__/svelteInstanzPruefstand.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../../..');
const SHARED = path.resolve(HERE, '../..');
const TAB = path.join(SHARED, 'WeatherMetricsTab.svelte');
const FIXTURE = path.resolve(FRONTEND, '..', 'tests', 'fixtures', 'einstellung_gleich_mail', 'editor_standard.json');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const WeatherV2Grundauswahl = (await import(pathToFileURL(path.join(SHARED, 'weather-metrics-tab', 'WeatherV2Grundauswahl.svelte')).href)).default;
const { locale } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);

const KATALOG = JSON.parse(readFileSync(FIXTURE, 'utf-8')).kataloge.trip_api_metrics as metricsEditor.MetricCatalog;
const BY_ID = Object.fromEntries(Object.values(KATALOG).flat().map((m) => [m.id, m]));
const IDS = Object.values(KATALOG).flat().map((m) => m.id);

const TAB_QUELLE = readFileSync(TAB, 'utf-8');
const TAB_AST = parse(TAB_QUELLE, { modern: true });
const [GRUNDAUSWAHL] = findeKomponenten(TAB_AST as never, 'WeatherV2Grundauswahl');
const AUSDRUCK = attributAusdruck(GRUNDAUSWAHL, TAB_QUELLE, 'nurBerichtById');

// Altbestand: Temperatur nur abends aus, Wind aus aber morgens an, Boeen abends
// an aber morgens aus, Niederschlag beide Flags gesetzt (= wie enabled).
const BESTAND = [
	{ metric_id: 'temperature', enabled: true, order: 0, bucket: 'primary', evening_enabled: false },
	{ metric_id: 'wind', enabled: false, order: 0, morning_enabled: true },
	{ metric_id: 'gust', enabled: true, order: 1, bucket: 'primary', morning_enabled: false },
	{ metric_id: 'precipitation', enabled: true, order: 2, bucket: 'primary', morning_enabled: true, evening_enabled: true },
	{ metric_id: 'thunder', enabled: true, order: 3, bucket: 'primary' }
];

/** Kennzeichnungen, wie der Reiter sie zeigt: Ausdruck der Einbettung -> Render. */
function kennzeichnungen(buckets: metricsEditor.Buckets, sprache = 'de'): Record<string, string> {
	assert.ok(AUSDRUCK, 'WeatherV2Grundauswahl-Einbettung reicht nurBerichtById nicht durch');
	const nurBerichtById = werte(stripTypeScriptTypes(AUSDRUCK), {
		nurEinBerichtJeMetrik, buckets, trip: { display_config: { metrics: BESTAND } }
	});
	locale.set(sprache);
	try {
		const html = render(WeatherV2Grundauswahl as never, {
			props: { catalog: KATALOG, primaryColumns: buckets.primary, highlight: null, onToggle: () => {}, nurBerichtById }
		} as never).body;
		const out: Record<string, string> = {};
		for (const m of html.matchAll(/data-testid="wm2-nur-bericht-([^"]+)"[^>]*>([^<]*)</g)) out[m[1]] = m[2];
		return out;
	} finally {
		locale.set('de');
	}
}
const geladen = () => metricsEditor.computeInitialBuckets(KATALOG, BY_ID, BESTAND as never, IDS);

describe('#3047 N3 nur morgens / nur abends (Altbestand)', () => {
	test('n3_semantik_wie_mail', () => {
		assert.equal(nurEinBericht({ metric_id: 'a', enabled: false, morning_enabled: true }, false), 'morgens');
		assert.equal(nurEinBericht({ metric_id: 'a', enabled: true, evening_enabled: false }, true), 'morgens');
		assert.equal(nurEinBericht({ metric_id: 'a', enabled: true, morning_enabled: false }, true), 'abends');
		assert.equal(nurEinBericht({ metric_id: 'a', enabled: false, evening_enabled: true }, false), 'abends');
		assert.equal(nurEinBericht({ metric_id: 'a', morning_enabled: true, evening_enabled: true }, false), null);
		assert.equal(nurEinBericht({ metric_id: 'a', morning_enabled: false, evening_enabled: false }, true), null);
		assert.equal(nurEinBericht({ metric_id: 'a', morning_enabled: null, evening_enabled: null }, true), null);
	});

	test('n3_editor_kennzeichnet_je_zeile', () => {
		assert.deepEqual(kennzeichnungen(geladen()), {
			temperature: 'nur morgens', wind: 'nur morgens', gust: 'nur abends'
		});
		assert.deepEqual(kennzeichnungen(geladen(), 'en'), {
			temperature: 'morning only', wind: 'morning only', gust: 'evening only'
		});
	});

	test('n3_kennzeichnung_folgt_dem_editorstand', () => {
		// Temperatur abwaehlen: abends ohnehin aus, morgens folgt jetzt `enabled:false`
		// -> in keinem Bericht -> keine Kennzeichnung mehr.
		const { buckets } = toggleGlobalMetric(geladen(), { email: null, telegram: null, sms: null }, 'temperature', true);
		assert.equal(kennzeichnungen(buckets).temperature, undefined);
	});

	test('n3_speichern_bewahrt_bericht_flags', () => {
		const { buckets } = toggleGlobalMetric(geladen(), { email: null, telegram: null, sms: null }, 'thunder', true);
		const gespeichert = buildGlobalMetricsForSave(
			{ metrics: BESTAND } as never, buckets, {}, {}, KATALOG, {}, []
		);
		const flags = (id: string) => {
			const e = gespeichert.find((m) => m.metric_id === id) as unknown as Record<string, unknown>;
			return [e.morning_enabled, e.evening_enabled];
		};
		assert.deepEqual(flags('temperature'), [undefined, false]);
		assert.deepEqual(flags('wind'), [true, undefined]);
		assert.deepEqual(flags('gust'), [false, undefined]);
		assert.deepEqual(flags('precipitation'), [true, true]);
	});
});
