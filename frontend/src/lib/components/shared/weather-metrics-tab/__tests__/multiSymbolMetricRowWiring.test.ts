// Fix #1613 — SMS-Kuerzel fuer Mehrfach-Symbol-Metriken fehlen im Frontend.
// Spec: docs/specs/modules/fix_1613_sms_multi_symbols.md § AC-4/AC-5/AC-6
//
// `wind_chill` (Gefuehlte Temperatur, FN/FK/FD/WC) hat bislang KEINEN
// Anzeigeort in der Schwellwerte-Sektion — der PO hat konkret bestaetigt,
// dass 'WC' im Trip-Editor sichtbar fehlt. Diese Tests pruefen das Wiring
// der neuen `MultiSymbolMetricRow` fuer `wind_chill` im Quelltext.
//
// Kein Rendering-Harness fuer Svelte-5-Runen im node:test-Setup (kein
// @testing-library/svelte) — daher source-inspizierende Tests
// (Praezedenz: weatherMetricsTabDayWindowSave.test.ts, day_window_card.test.ts).
// Die tatsaechliche Pixel-Sichtbarkeit von "WC" wird zusaetzlich bei der
// Staging-Validierung vor dem Prod-Deploy bestaetigt.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const WEATHER_METRICS_TAB = join(here, '..', '..', 'WeatherMetricsTab.svelte');
const src = readFileSync(WEATHER_METRICS_TAB, 'utf-8');

/** Isoliert den `{#if !buckets.off.includes('wind_chill')}...{/if}`-Block
 * um den erwarteten `<MultiSymbolMetricRow metricId="wind_chill" .../>`-Aufruf
 * (analog dem bestehenden Gate-Muster der sieben ThresholdMetricRow-Zeilen). */
function windChillGateBlock(): string {
	const gateRe = /\{#if !buckets\.off\.includes\('wind_chill'\)\}/;
	const gateMatch = gateRe.exec(src);
	assert.ok(
		gateMatch,
		"AC-5: kein {#if !buckets.off.includes('wind_chill')}-Gate im Quelltext gefunden — " +
			'wind_chill hat noch keinen Schwellwerte-Anzeigeort'
	);
	const start = gateMatch!.index;
	const end = src.indexOf('{/if}', start);
	assert.ok(end > start, 'AC-5: schliessendes {/if} zum wind_chill-Gate nicht gefunden');
	return src.slice(start, end + '{/if}'.length);
}

describe('AC-4: MultiSymbolMetricRow ist fuer wind_chill verdrahtet (Kuerzel WC bislang strukturell unsichtbar)', () => {
	test('WeatherMetricsTab.svelte importiert MultiSymbolMetricRow', () => {
		assert.match(
			src,
			/import MultiSymbolMetricRow from '\.\/weather-metrics-tab\/MultiSymbolMetricRow\.svelte'/,
			'AC-4: Import von MultiSymbolMetricRow fehlt'
		);
	});

	test('der wind_chill-Gate-Block enthaelt genau einen <MultiSymbolMetricRow>-Aufruf', () => {
		const block = windChillGateBlock();
		const matches = block.match(/<MultiSymbolMetricRow/g) ?? [];
		assert.equal(
			matches.length,
			1,
			`AC-4: erwarte genau einen <MultiSymbolMetricRow>-Aufruf im wind_chill-Gate, gefunden ${matches.length}`
		);
	});

	test('der Aufruf setzt metricId="wind_chill"', () => {
		const block = windChillGateBlock();
		assert.match(
			block,
			/<MultiSymbolMetricRow[\s\S]*?metricId="wind_chill"/,
			'AC-4: metricId="wind_chill" fehlt am MultiSymbolMetricRow-Aufruf'
		);
	});

	test("die symbols-Prop bindet an metricSymbols['wind_chill'] -- NICHT hartcodiert", () => {
		const block = windChillGateBlock();
		const callMatch = block.match(/<MultiSymbolMetricRow[\s\S]*?\/>/);
		assert.ok(callMatch, 'AC-4: MultiSymbolMetricRow-Aufruf (selbstschliessendes Tag) nicht gefunden');
		const call = callMatch![0];
		assert.match(
			call,
			/symbols=\{metricSymbols\['wind_chill'\][^}]*\}/,
			`AC-4: symbols-Prop muss an metricSymbols['wind_chill'] gebunden sein (nicht hartcodiert), gefunden:\n${call}`
		);
		assert.ok(
			!/symbols=\{\s*\[\s*['"]/.test(call),
			`AC-4: symbols-Prop darf kein hartcodiertes Array sein (z.B. symbols={['FN','FK','FD','WC']}):\n${call}`
		);
	});
});

describe("AC-5: dasselbe Gate-Muster wie die sieben bestehenden Schwellwert-Zeilen -- Abwahl blendet aus", () => {
	test("MultiSymbolMetricRow(wind_chill) steht INNERHALB von {#if !buckets.off.includes('wind_chill')} ... {/if}", () => {
		// windChillGateBlock() wirft bereits, wenn Gate-Start oder -Ende fehlen --
		// hier zusaetzlich sicherstellen, dass der Row-Aufruf tatsaechlich
		// ZWISCHEN Gate-Start und {/if} liegt (nicht nur zufaellig irgendwo im Text).
		const block = windChillGateBlock();
		const rowIdx = block.indexOf('<MultiSymbolMetricRow');
		const closeIdx = block.lastIndexOf('{/if}');
		assert.ok(
			rowIdx >= 0 && rowIdx < closeIdx,
			'AC-5: <MultiSymbolMetricRow> fuer wind_chill muss zwischen Gate-Oeffnung und {/if} liegen'
		);
	});

	test('exakt dasselbe Gate-Textmuster wie bei den bestehenden ThresholdMetricRow-Zeilen (z.B. wind)', () => {
		const existingGate = /\{#if !buckets\.off\.includes\('wind'\)\}/;
		assert.match(src, existingGate, 'Referenz-Gate-Muster (wind) nicht gefunden -- Vergleichsbasis fehlt');
		assert.match(
			src,
			/\{#if !buckets\.off\.includes\('wind_chill'\)\}/,
			"AC-5: wind_chill muss exakt demselben Gate-Muster folgen: {#if !buckets.off.includes('wind_chill')}"
		);
	});
});

describe('AC-6: bestehende sieben ThresholdMetricRow-Aufrufe lesen metricSymbols[id]?.[0] statt metricSymbols[id] (Typwechsel string -> string[])', () => {
	const existingIds = [
		'wind', 'gust', 'precipitation', 'rain_probability', 'thunder', 'snow_depth', 'snowfall_limit',
	];

	for (const id of existingIds) {
		test(`smsSymbol-Prop fuer '${id}' verwendet ?.[0], kein direkter String-Zugriff`, () => {
			const re = new RegExp(`smsSymbol=\\{metricSymbols\\['${id}'\\][^}]*\\}`);
			const match = src.match(re);
			assert.ok(match, `AC-6: smsSymbol-Prop fuer '${id}' nicht gefunden (Muster: smsSymbol={metricSymbols['${id}']...})`);
			assert.match(
				match![0],
				/\?\.\[0\]/,
				`AC-6: '${id}' muss metricSymbols['${id}']?.[0] lesen (Array-Zugriff nach der Typumstellung), gefunden: ${match![0]}`
			);
		});
	}

	test('SmsSymbolEntry-Typ traegt sms_symbols: string[] (nicht mehr sms_symbol: string)', () => {
		assert.match(
			src,
			/interface SmsSymbolEntry\s*\{[\s\S]*?sms_symbols:\s*string\[\][\s\S]*?\}/,
			'AC-6: SmsSymbolEntry.sms_symbols: string[] fehlt (oder noch als sms_symbol: string typisiert)'
		);
	});
});
