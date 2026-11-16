// #3047 F5 T3 Orte (AC-10): eine in die Grundauswahl des Ortsvergleichs
// aufgenommene Metrik steht danach in JEDER bereits gespeicherten Liste, hinten
// angehaengt: Kanal-Listen (`channel_active_metrics`), Ausblick
// (`outlook_metrics`) und Stundenverlauf (`hourly_metrics`, nur stuendlich
// waehlbare Groessen). Gegenstueck zu neue_metrik_in_allen_listen.test.ts (Trip).
//
// SPEC: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md (AC-10)
// Konzept: docs/context/einstellungen_neu.md §5 Punkt 6/8.
//
// Geprueft wird die ECHTE Instanz-Funktion toggleCompareMetric aus
// WeatherMetricsTab.svelte (svelte/compiler, kein Nachbau, kein vi.mock); ihre
// Modul-Importe kommen aus den echten Modulen.
//
//   cd frontend && npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/neue_metrik_in_allen_listen_orte.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { stripTypeScriptTypes } from 'node:module';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { parse } from 'svelte/compiler';

import * as layouts from '../channelMetricLayouts.ts';
import * as compareLayouts from '../compareChannelMetricLayouts.ts';
import * as compareOrder from '../compareMetricOrder.ts';
import type { CompareSelectionEntry } from '../compareMetricSelection.ts';

const TAB = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../WeatherMetricsTab.svelte');
const TAB_QUELLE = readFileSync(TAB, 'utf-8');
const BINDUNGEN = { ...layouts, ...compareLayouts, ...compareOrder };

function toggleCompareMetric(zustand: Record<string, unknown>): (metric: string) => void {
	const ast = parse(TAB_QUELLE, { modern: true }) as unknown as {
		instance: { content: { body: Array<{ type: string; id?: { name: string }; start: number; end: number }> } };
	};
	const knoten = ast.instance.content.body.find(
		(n) => n.type === 'FunctionDeclaration' && n.id?.name === 'toggleCompareMetric'
	);
	assert.ok(knoten, 'Funktion toggleCompareMetric nicht mehr in WeatherMetricsTab.svelte');
	const quelle = stripTypeScriptTypes(TAB_QUELLE.slice(knoten.start, knoten.end));
	Object.setPrototypeOf(zustand, BINDUNGEN);
	// eslint-disable-next-line @typescript-eslint/no-implied-eval
	return new Function('zustand', `with (zustand) { ${quelle}\nreturn toggleCompareMetric; }`)(zustand);
}

const KATALOG: CompareSelectionEntry[] = [
	{ metric: 'wind_max_kmh', metric_id: 'wind', label: 'Wind', hourlySelectable: true, hourly_legacy_keys: ['wind_kmh'] },
	{ metric: 'temp_max_c', metric_id: 'temperature', label: 'Temperatur', hourlySelectable: true, hourly_legacy_keys: ['temp_c'] },
	{ metric: 'temp_min_c', metric_id: 'temperature', label: 'Temperatur', hourlySelectable: true, hourly_legacy_keys: ['temp_c'] },
	{ metric: 'uv_index_max', metric_id: 'uv_index', label: 'UV', hourlySelectable: true, hourly_legacy_keys: ['uv_index'] },
	{ metric: 'sunny_hours_h', metric_id: 'sunshine', label: 'Sonne', hourlySelectable: false }
];

type Aufrufe = { vergleich: unknown[][]; outlook: unknown[][]; hourly: unknown[][] };

function lage(over: Record<string, unknown> = {}): { zustand: Record<string, unknown>; aufrufe: Aufrufe } {
	const aufrufe: Aufrufe = { vergleich: [], outlook: [], hourly: [] };
	const active = ['wind_max_kmh', 'temp_max_c'];
	const zustand: Record<string, unknown> = {
		activeMetricKeys: active,
		materializedActiveMetricKeys: active,
		// E-Mail: eigene Folge; Telegram nie bearbeitet; SMS nur Wind
		channelActiveMetricKeys: { email: ['temp_max_c', 'wind_max_kmh'], telegram: null, sms: ['wind_max_kmh'] },
		outlookMetricKeys: ['wind', 'temperature'],
		hourlyMetricKeys: ['temp_c', 'wind'],
		compareCatalog: KATALOG,
		onVergleichsMetrikenChange: (...a: unknown[]) => aufrufe.vergleich.push(a),
		onOutlookMetricKeysChange: (...a: unknown[]) => aufrufe.outlook.push(a),
		onHourlyMetricKeysChange: (...a: unknown[]) => aufrufe.hourly.push(a),
		...over
	};
	return { zustand, aufrufe };
}

describe('#3047 AC-10 Orte: neue Metrik in allen bereits gespeicherten Listen', () => {
	test('Einwahl haengt die Metrik an jede gespeicherte Kanal-Liste hinten an, Folge bleibt', () => {
		const { zustand, aufrufe } = lage();
		toggleCompareMetric(zustand)('uv_index_max');
		assert.equal(aufrufe.vergleich.length, 1, 'genau ein gekoppelter Rueckruf');
		const [active, kanal] = aufrufe.vergleich[0] as [string[], Record<string, string[] | null>];
		assert.deepEqual(active, ['wind_max_kmh', 'temp_max_c', 'uv_index_max']);
		assert.deepEqual(kanal.email, ['temp_max_c', 'wind_max_kmh', 'uv_index_max'], 'E-Mail-Liste ohne neue Metrik');
		assert.deepEqual(kanal.sms, ['wind_max_kmh', 'uv_index_max'], 'SMS-Liste ohne neue Metrik');
		assert.equal(kanal.telegram, null, 'nie bearbeitete Liste bleibt ohne eigenen Eintrag');
	});

	test('Einwahl haengt die Metrik an gespeicherten Ausblick und Stundenverlauf hinten an', () => {
		const { zustand, aufrufe } = lage();
		toggleCompareMetric(zustand)('uv_index_max');
		assert.deepEqual(aufrufe.outlook, [[['wind', 'temperature', 'uv_index']]], 'Ausblick-Liste ohne neue Metrik');
		assert.deepEqual(aufrufe.hourly, [[['temp_c', 'wind', 'uv_index']]], 'Stundenverlauf ohne neue Metrik');
	});

	test('Stundenverlauf nur fuer stuendlich waehlbare Groessen; keine Dublette ueber Alt-Kurzschluessel', () => {
		const sonne = lage();
		toggleCompareMetric(sonne.zustand)('sunny_hours_h');
		assert.deepEqual(sonne.aufrufe.hourly, [], 'Sonnenstunden sind stuendlich nicht waehlbar');
		assert.deepEqual(sonne.aufrufe.outlook, [[['wind', 'temperature', 'sunshine']]]);

		// temp_min_c teilt die Groesse Temperatur, die als Alt-Kurzschluessel temp_c schon drin ist
		const tief = lage();
		toggleCompareMetric(tief.zustand)('temp_min_c');
		assert.deepEqual(tief.aufrufe.hourly, [], 'Temperatur steht schon (als temp_c) im Stundenverlauf');
		assert.deepEqual(tief.aufrufe.outlook, [], 'Temperatur steht schon im Ausblick');
	});

	test('nie eingestellte Listen (null) bleiben null', () => {
		const { zustand, aufrufe } = lage({
			channelActiveMetricKeys: { email: null, telegram: null, sms: null },
			outlookMetricKeys: null,
			hourlyMetricKeys: null
		});
		toggleCompareMetric(zustand)('uv_index_max');
		assert.deepEqual(aufrufe.outlook, []);
		assert.deepEqual(aufrufe.hourly, []);
		assert.deepEqual((aufrufe.vergleich[0] as unknown[])[1], { email: null, telegram: null, sms: null });
	});

	test('Abwahl wirkt weiter sofort in den Kanal-Listen (ADR-0050 Regel 3), Ausblick/Stunden unberuehrt', () => {
		const { zustand, aufrufe } = lage();
		toggleCompareMetric(zustand)('wind_max_kmh');
		const [active, kanal] = aufrufe.vergleich[0] as [string[], Record<string, string[] | null>];
		assert.deepEqual(active, ['temp_max_c']);
		assert.deepEqual(kanal, { email: ['temp_max_c'], telegram: null, sms: [] });
		assert.deepEqual(aufrufe.outlook, []);
		assert.deepEqual(aufrufe.hourly, []);
	});
});
