// Issue #1361/#1372 S1b — Adversary Runde 3/4 + Staging-Fund AC-5.
//
// Runde 3/4: das Tagesfenster im Trip (context="route") muss auch dann einen
// Speicherversuch ausloesen, wenn die allgemeine Vergleichsfunktion
// `reportConfigChangedByUser()` NICHTS meldet (s. reportConfigDirty.ts
// Modul-Kommentar — ein Vereinigungs-Fix dort wurde wieder verworfen). Der
// tragfaehige Weg: `DayWindowCard`s Handler setzen `userTouched` und loesen
// den Speicherversuch DIREKT aus der echten DOM-Geste aus.
//
// Staging-Fund AC-5 (live reproduziert, zweifach): das Aendern NUR der
// Endstunde loeste zwei PUTs aus — `/api/trips/{id}` (richtig) UND
// `/api/trips/{id}/weather-config` (unbeteiligt, schreibt den kompletten
// Metrik-Katalog unveraendert mit). Ursache: sowohl der explizite Handler-
// Aufruf ALS AUCH der ambiente `$effect` (der auf JEDE reportConfig-Aenderung
// reagiert) riefen `scheduleAutoSave()` — die eine Funktion, die IMMER beide
// Endpunkte bedient. Fix: eine eigene `scheduleReportConfigOnlySave()`, die
// AUSSCHLIESSLICH `/api/trips/{id}` anspricht (analog dem bereits entkoppelten
// Compare-Pfad, flushPendingWeatherMetricsSave -> EIN PUT). Sowohl der
// explizite DayWindowCard-Handler ALS AUCH der ambiente $effect (dessen
// eigene Aufgabe laut seinem Kommentar ausschliesslich reportConfig ist)
// rufen jetzt diese Funktion — sonst wuerde der $effect den expliziten Weg
// nach dem Debounce wieder auf die volle scheduleAutoSave() ueberschreiben
// (SaveStatus.schedule() ersetzt den anstehenden Callback bei jedem Aufruf).
//
// Kein Rendering-Harness fuer Svelte-5-Runen im node:test-Setup — daher
// source-inspizierende Tests (Praezedenz: day_window_card.test.ts).

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const WEATHER_METRICS_TAB = join(here, '..', 'WeatherMetricsTab.svelte');
const src = readFileSync(WEATHER_METRICS_TAB, 'utf-8');

/** Isoliert den route-Aufruf von DayWindowCard (der ZWEITE <DayWindowCard>
 * im Quelltext — der erste liegt im vergleich-Zweig weiter oben und bindet
 * an `wiz`, nicht an `reportConfig`). */
function routeDayWindowCardBlock(): string {
	const start = src.lastIndexOf('<DayWindowCard', src.indexOf('reportConfig.day_window_start_hour'));
	const end = src.indexOf('/>', start) + 2;
	assert.ok(start >= 0 && end > start, 'route-DayWindowCard-Block nicht gefunden');
	return src.slice(start, end);
}

/** Isoliert den Funktionskoerper von `function <name>() { ... }` (naive
 * Klammerzaehlung reicht hier: keine verschachtelten Funktionsdeklarationen
 * innerhalb der beiden betroffenen Funktionen). */
function functionBody(name: string): string {
	const sigIdx = src.indexOf(`function ${name}(`);
	assert.ok(sigIdx >= 0, `function ${name}() nicht gefunden`);
	const braceStart = src.indexOf('{', sigIdx);
	let depth = 0;
	for (let i = braceStart; i < src.length; i++) {
		if (src[i] === '{') depth++;
		else if (src[i] === '}') {
			depth--;
			if (depth === 0) return src.slice(braceStart, i + 1);
		}
	}
	throw new Error(`schliessende Klammer fuer function ${name}() nicht gefunden`);
}

describe('AC-4/AC-5 (Trip, context=route): DayWindowCard loest den Speicherversuch ausdruecklich aus', () => {
	test('onStartHour setzt userTouched=true UND ruft scheduleReportConfigOnlySave() direkt auf (nicht ueber den $effect)', () => {
		const block = routeDayWindowCardBlock();
		const onStartHourMatch = block.match(/onStartHour=\{[\s\S]*?\}\}/);
		assert.ok(onStartHourMatch, 'onStartHour-Handler nicht gefunden');
		const handlerBody = onStartHourMatch![0];
		assert.match(handlerBody, /userTouched\s*=\s*true/, 'onStartHour muss userTouched=true setzen (sonst verwirft weatherSaveGate jeden Speicherversuch)');
		assert.match(handlerBody, /scheduleReportConfigOnlySave\(\)/, 'onStartHour muss scheduleReportConfigOnlySave() direkt aus der DOM-Geste aufrufen');
		assert.ok(!/scheduleAutoSave\(\)/.test(handlerBody), 'onStartHour darf NICHT die volle scheduleAutoSave() (schreibt auch /weather-config) aufrufen');
	});

	test('onEndHour setzt userTouched=true UND ruft scheduleReportConfigOnlySave() direkt auf', () => {
		const block = routeDayWindowCardBlock();
		const onEndHourMatch = block.match(/onEndHour=\{[\s\S]*?\}\}/);
		assert.ok(onEndHourMatch, 'onEndHour-Handler nicht gefunden');
		const handlerBody = onEndHourMatch![0];
		assert.match(handlerBody, /userTouched\s*=\s*true/, 'onEndHour muss userTouched=true setzen');
		assert.match(handlerBody, /scheduleReportConfigOnlySave\(\)/, 'onEndHour muss scheduleReportConfigOnlySave() direkt aufrufen');
		assert.ok(!/scheduleAutoSave\(\)/.test(handlerBody), 'onEndHour darf NICHT die volle scheduleAutoSave() aufrufen');
	});

	test('die DayWindowCard fuer den Trip liegt AUSSERHALB des report-config-touch-scope (der Grund, warum der ausdrueckliche Weg noetig ist)', () => {
		const touchScopeStart = src.indexOf('class="report-config-touch-scope"');
		const dayWindowIdx = src.indexOf('reportConfig.day_window_start_hour');
		assert.ok(touchScopeStart >= 0 && dayWindowIdx >= 0, 'Referenzstellen nicht gefunden');
		assert.ok(
			dayWindowIdx < touchScopeStart,
			'DayWindowCard (route) muss VOR dem report-config-touch-scope-Container liegen — sonst waere der ' +
				'ausdrueckliche userTouched/scheduleReportConfigOnlySave()-Weg ueberfluessig (die Capture-Listener ' +
				'des Containers wuerden bereits greifen) und diese Doku waere irrefuehrend'
		);
	});
});

describe('Staging-Fund AC-5: scheduleReportConfigOnlySave() schreibt AUSSCHLIESSLICH /api/trips/{id}, nie /weather-config', () => {
	test('der Funktionskoerper enthaelt keinen Aufruf auf /weather-config', () => {
		const body = functionBody('scheduleReportConfigOnlySave');
		assert.ok(!/weather-config/.test(body), `scheduleReportConfigOnlySave() darf /weather-config nicht ansprechen:\n${body}`);
		assert.match(body, /api\.put<Trip>\(`\/api\/trips\/\$\{trip!\.id\}`/, 'scheduleReportConfigOnlySave() muss /api/trips/{id} (report_config) schreiben');
	});

	test('der ambiente $effect (reagiert auf JEDE reportConfig-Aenderung) ruft scheduleReportConfigOnlySave(), nicht scheduleAutoSave()', () => {
		// Der Effekt-Block direkt nach "let _lastReportConfig: ReportConfig = reportConfig;".
		const anchorIdx = src.indexOf('let _lastReportConfig: ReportConfig = reportConfig;');
		assert.ok(anchorIdx >= 0, 'Anker fuer den reportConfig-$effect nicht gefunden');
		const effectStart = src.indexOf('$effect(', anchorIdx);
		const effectEnd = src.indexOf('});', effectStart) + 3;
		const effectBody = src.slice(effectStart, effectEnd);

		assert.match(
			effectBody,
			/scheduleReportConfigOnlySave\(\)/,
			'der reportConfig-$effect muss scheduleReportConfigOnlySave() rufen — sonst ueberschreibt er den ' +
				'debounced Callback eines expliziten DayWindowCard-Aufrufs wieder mit der vollen scheduleAutoSave() ' +
				'(SaveStatus.schedule() ersetzt den anstehenden Callback bei jedem Aufruf, letzter Aufruf gewinnt)'
		);
		// Nur ein tatsaechlicher Aufruf (";" direkt danach) zaehlt -- der
		// erklaerende Kommentar im Effekt selbst nennt "scheduleAutoSave()" als
		// Wort, ohne ihn aufzurufen.
		assert.ok(
			!/scheduleAutoSave\(\);/.test(effectBody),
			`der reportConfig-$effect darf NICHT scheduleAutoSave() (voller Metrik-Katalog-PUT) aufrufen:\n${effectBody}`
		);
	});
});

describe('Gegenprobe: Metrik-Aenderungen loesen weiterhin die volle scheduleAutoSave() (schreiben /weather-config)', () => {
	test('onToggleMetric (Metrik an/aus) ruft weiterhin scheduleAutoSave()', () => {
		const body = functionBody('onToggleMetric');
		assert.match(body, /scheduleAutoSave\(\)/, 'onToggleMetric muss weiterhin die volle scheduleAutoSave() ausloesen — Metrik-Aenderungen duerfen NICHT durch die AC-5-Entkopplung mit abgeklemmt werden');
	});

	test('onDndReorder (Metrik-Reihenfolge) ruft weiterhin scheduleAutoSave()', () => {
		const body = functionBody('onDndReorder');
		assert.match(body, /scheduleAutoSave\(\)/, 'onDndReorder muss weiterhin die volle scheduleAutoSave() ausloesen');
	});

	test('smsThresholds-Handler (Metrik-Schwellwerte) rufen weiterhin scheduleAutoSave()', () => {
		const smsBlockStart = src.indexOf('smsThresholds = { ...smsThresholds');
		assert.ok(smsBlockStart >= 0, 'smsThresholds-Handler nicht gefunden');
		const line = src.slice(smsBlockStart, src.indexOf('\n', smsBlockStart));
		assert.match(line, /scheduleAutoSave\(\)/, 'smsThresholds-Handler muessen weiterhin scheduleAutoSave() rufen (echte Metrik-Konfiguration)');
	});
});
