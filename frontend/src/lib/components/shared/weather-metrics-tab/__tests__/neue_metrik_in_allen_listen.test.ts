// #3047 F2 T3 (AC-10): eine in die Grundauswahl aufgenommene Metrik steht danach
// in JEDER bereits bearbeiteten Liste, hinten angehaengt und eingeschaltet; die
// bestehende Folge bleibt.
//
// SPEC: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md (AC-10)
// Konzept: docs/context/einstellungen_neu.md §5 Punkt 6 („Hinzufuegen meldet:
// … steht in allen Listen unter ‚Inhalt je Kanal und Flaeche‘“) und Punkt 8
// („Jede Liste nimmt nur aus den Metriken oben, sie kann abwaehlen, aber
// nichts hinzufuegen“).
//
// Geprueft werden die ECHTEN Funktionen, die WeatherMetricsTab.svelte::
// onToggleMetric() aufruft: `toggleGlobalMetric` (Kanal-Listen E-Mail/Telegram/
// SMS; Premium-SMS sendet den SMS-Text, ADR-0049) und `appendNewMetricsToOutlook`
// (gespeicherte Ausblick-Liste `outlook_metrics`, Kennungen).
//
//   cd frontend && npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/neue_metrik_in_allen_listen.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { stripTypeScriptTypes } from 'node:module';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { parse } from 'svelte/compiler';

import * as layouts from '../channelMetricLayouts.ts';
import type { ChannelOverride } from '../channelMetricLayouts.ts';
import type { Buckets } from '../../../trip-detail/metricsEditor.ts';
import type { ChannelId } from '../../layout-tab/ltChannels.ts';
import type { CompareSelectionEntry } from '../compareMetricSelection.ts';

// Echte Instanz-Funktion onToggleMetric aus WeatherMetricsTab.svelte (Wirkort),
// Technik wie editor_standard_gleich_mail.test.ts (svelte/compiler, kein Nachbau).
const TAB = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../WeatherMetricsTab.svelte');
const TAB_QUELLE = readFileSync(TAB, 'utf-8');
function tabFunktion(name: string, zustand: Record<string, unknown>): (...a: unknown[]) => unknown {
	const ast = parse(TAB_QUELLE, { modern: true }) as unknown as {
		instance: { content: { body: Array<{ type: string; id?: { name: string }; start: number; end: number }> } };
	};
	const knoten = ast.instance.content.body.find((n) => n.type === 'FunctionDeclaration' && n.id?.name === name);
	assert.ok(knoten, `Funktion ${name} nicht mehr in WeatherMetricsTab.svelte`);
	const quelle = stripTypeScriptTypes(TAB_QUELLE.slice(knoten.start, knoten.end));
	Object.setPrototypeOf(zustand, layouts);
	// eslint-disable-next-line @typescript-eslint/no-implied-eval
	return new Function('zustand', `with (zustand) { ${quelle}\nreturn ${name}; }`)(zustand);
}

const override = (primary: string[], off: string[]): ChannelOverride => ({
	buckets: { primary, secondary: [], off },
	friendlyMap: { wind: true }
});

function ausgangslage(): { buckets: Buckets; channelBuckets: Record<ChannelId, ChannelOverride | null> } {
	return {
		buckets: { primary: ['wind', 'gust', 'temperature'], secondary: [], off: ['uv_index', 'wind_chill', 'wind_chill_night'] },
		channelBuckets: {
			// E-Mail: eigene Folge, Boeen abgewaehlt
			email: override(['temperature', 'wind'], ['gust', 'uv_index', 'wind_chill', 'wind_chill_night']),
			telegram: null, // nie bearbeitet -> folgt der Grundauswahl
			sms: override(['gust', 'wind'], ['temperature', 'uv_index', 'wind_chill', 'wind_chill_night'])
		}
	};
}

describe('#3047 AC-10 neue Metrik in allen bereits bearbeiteten Listen', () => {
	test('Einwahl haengt die Metrik in jeder bearbeiteten Kanal-Liste hinten an, Folge bleibt', () => {
		const { buckets, channelBuckets } = ausgangslage();
		const r = layouts.toggleGlobalMetric(buckets, channelBuckets, 'uv_index', false);
		assert.deepEqual(r.buckets.primary, ['wind', 'gust', 'temperature', 'uv_index']);
		assert.deepEqual(r.channelBuckets.email!.buckets.primary, ['temperature', 'wind', 'uv_index'],
			'E-Mail-Liste: neue Metrik fehlt oder Folge veraendert');
		assert.deepEqual(r.channelBuckets.sms!.buckets.primary, ['gust', 'wind', 'uv_index'],
			'SMS-Liste: neue Metrik fehlt oder Folge veraendert');
		assert.ok(!r.channelBuckets.email!.buckets.off.includes('uv_index'), 'E-Mail: neue Metrik steht noch unter „aus“');
		assert.equal(r.channelBuckets.telegram, null, 'nie bearbeitete Liste bleibt ohne eigenen Eintrag');
		assert.deepEqual(r.channelBuckets.email!.friendlyMap, { wind: true }, 'Darstellung je Zeile bleibt');
		// Eine in der Liste bewusst abgewaehlte, global aktive Metrik bleibt abgewaehlt.
		assert.ok(!r.channelBuckets.email!.buckets.primary.includes('gust'), 'Abwahl in der Liste geht verloren');
	});

	test('Einwahl eines Elters nimmt die abgeleiteten Kinder in die bearbeitete Liste mit', () => {
		const { buckets, channelBuckets } = ausgangslage();
		const r = layouts.toggleGlobalMetric(buckets, channelBuckets, 'wind_chill', false);
		assert.deepEqual(r.channelBuckets.email!.buckets.primary, ['temperature', 'wind', 'wind_chill', 'wind_chill_night']);
		assert.deepEqual(r.channelBuckets.sms!.buckets.primary, ['gust', 'wind', 'wind_chill', 'wind_chill_night']);
	});

	test('Einwahl haengt die Metrik an eine gespeicherte Ausblick-Liste hinten an', () => {
		const katalog: CompareSelectionEntry[] = [
			{ metric: 'temp_max_c', metric_id: 'temperature', label: 'Temperatur' },
			{ metric: 'uv_index_max', metric_id: 'uv_index', label: 'UV' },
			{ metric: 'wind_max_kmh', metric_id: 'wind', label: 'Wind' }
		];
		const append = (layouts as Record<string, unknown>).appendNewMetricsToOutlook as
			| ((keys: string[] | null, ids: string[], catalog: CompareSelectionEntry[]) => string[] | null)
			| undefined;
		assert.equal(typeof append, 'function', 'appendNewMetricsToOutlook fehlt: Ausblick-Liste bekommt die neue Metrik nicht');
		assert.deepEqual(append!(['wind', 'temperature'], ['uv_index'], katalog), ['wind', 'temperature', 'uv_index']);
		// nie eingestellt (null) folgt ohnehin der Grundauswahl
		assert.equal(append!(null, ['uv_index'], katalog), null);
		// ohne Tageswert im Ausblick-Katalog (z. B. Kind-Kennung) kein Eintrag, keine Dublette
		assert.deepEqual(append!(['wind'], ['wind', 'temperature_night'], katalog), ['wind']);
	});

	test('Wirkort onToggleMetric: Kanal-Listen und gespeicherter Ausblick bekommen die Metrik hinten', () => {
		const { buckets, channelBuckets } = ausgangslage();
		const zustand: Record<string, unknown> = {
			userTouched: false, buckets, channelBuckets, friendlyMap: {}, selectedTemplate: '',
			outlookMetricKeysRoute: ['wind', 'temperature'],
			compareCatalog: [
				{ metric: 'uv_index_max', metric_id: 'uv_index', label: 'UV' },
				{ metric: 'wind_max_kmh', metric_id: 'wind', label: 'Wind' },
				{ metric: 'temp_max_c', metric_id: 'temperature', label: 'Temperatur' }
			],
			applyDiff: () => {}, scheduleAutoSave: () => {}
		};
		tabFunktion('onToggleMetric', zustand)('uv_index', false);
		assert.deepEqual((zustand.channelBuckets as typeof channelBuckets).email!.buckets.primary, ['temperature', 'wind', 'uv_index']);
		assert.deepEqual(zustand.outlookMetricKeysRoute, ['wind', 'temperature', 'uv_index'],
			'gespeicherte Ausblick-Liste bekommt die neue Metrik nicht');
	});
});
