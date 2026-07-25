// Issue #1361/#1372 S1b — Adversary Runde 3/4: das Tagesfenster im Trip
// (context="route") muss auch dann einen Speicherversuch ausloesen, wenn die
// allgemeine Vergleichsfunktion `reportConfigChangedByUser()` NICHTS meldet.
//
// Hintergrund (s. reportConfigDirty.ts Modul-Kommentar): ein Versuch, das
// ueber eine Vereinigungs-Regel in `reportConfigChangedByUser()` zu loesen,
// wurde WIEDER VERWORFEN (Runde 4) — er erzeugte ein falsches "Nicht
// gespeichert" beim bloszen Oeffnen jedes Bestandstrips (Mount-Kanonisierung
// meldete faelschlich "geaendert", der skip-Zweig von `scheduleAutoSave()`
// ruft `saveController.setDirty()` auch ohne echte Nutzergeste). Der
// tragfaehige Weg: `DayWindowCard`s Handler setzen `userTouched` und rufen
// `scheduleAutoSave()` DIREKT aus der echten DOM-Geste — denselben Weg, den
// die SMS-Schwellwert-Felder in derselben Datei seit jeher gehen. Die
// allgemeine Diff-Funktion entscheidet auf diesem Pfad gar nicht mehr mit.
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

describe('AC-4/AC-5 (Trip, context=route): DayWindowCard loest den Speicherversuch ausdruecklich aus', () => {
	const src = readFileSync(WEATHER_METRICS_TAB, 'utf-8');

	/** Isoliert den route-Aufruf von DayWindowCard (der ZWEITE <DayWindowCard>
	 * im Quelltext — der erste liegt im vergleich-Zweig weiter oben und bindet
	 * an `wiz`, nicht an `reportConfig`/`scheduleAutoSave`). */
	function routeDayWindowCardBlock(): string {
		const start = src.lastIndexOf('<DayWindowCard', src.indexOf('reportConfig.day_window_start_hour'));
		const end = src.indexOf('/>', start) + 2;
		assert.ok(start >= 0 && end > start, 'route-DayWindowCard-Block nicht gefunden');
		return src.slice(start, end);
	}

	test('onStartHour setzt userTouched=true UND ruft scheduleAutoSave() direkt auf (nicht ueber den $effect)', () => {
		const block = routeDayWindowCardBlock();
		const onStartHourMatch = block.match(/onStartHour=\{[\s\S]*?\}\}/);
		assert.ok(onStartHourMatch, 'onStartHour-Handler nicht gefunden');
		const handlerBody = onStartHourMatch![0];
		assert.match(handlerBody, /userTouched\s*=\s*true/, 'onStartHour muss userTouched=true setzen (sonst verwirft weatherSaveGate jeden Speicherversuch)');
		assert.match(handlerBody, /scheduleAutoSave\(\)/, 'onStartHour muss scheduleAutoSave() direkt aus der DOM-Geste aufrufen');
	});

	test('onEndHour setzt userTouched=true UND ruft scheduleAutoSave() direkt auf', () => {
		const block = routeDayWindowCardBlock();
		const onEndHourMatch = block.match(/onEndHour=\{[\s\S]*?\}\}/);
		assert.ok(onEndHourMatch, 'onEndHour-Handler nicht gefunden');
		const handlerBody = onEndHourMatch![0];
		assert.match(handlerBody, /userTouched\s*=\s*true/, 'onEndHour muss userTouched=true setzen');
		assert.match(handlerBody, /scheduleAutoSave\(\)/, 'onEndHour muss scheduleAutoSave() direkt aufrufen');
	});

	test('die DayWindowCard fuer den Trip liegt AUSSERHALB des report-config-touch-scope (der Grund, warum der ausdrueckliche Weg noetig ist)', () => {
		const touchScopeStart = src.indexOf('class="report-config-touch-scope"');
		const dayWindowIdx = src.indexOf('reportConfig.day_window_start_hour');
		assert.ok(touchScopeStart >= 0 && dayWindowIdx >= 0, 'Referenzstellen nicht gefunden');
		assert.ok(
			dayWindowIdx < touchScopeStart,
			'DayWindowCard (route) muss VOR dem report-config-touch-scope-Container liegen — sonst waere der ' +
				'ausdrueckliche userTouched/scheduleAutoSave()-Weg ueberfluessig (die Capture-Listener des ' +
				'Containers wuerden bereits greifen) und diese Doku waere irrefuehrend'
		);
	});
});
