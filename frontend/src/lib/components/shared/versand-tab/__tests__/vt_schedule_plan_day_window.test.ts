// Fix-Loop nach Adversary-Verdict BROKEN — Issue #1319 Scheibe B+C.
//
// F001 (HIGH): VTSchedulePlan.svelte filterte bisher nur die angezeigten
// Endstunde-Optionen, korrigierte aber nie den gebundenen
// day_window_end_hour-$state-Wert -- eine Startstunde >= aktueller Endstunde
// konnte so ein ungueltiges Paar (start>=end) bauen und PUTten. Fix:
// VersandTab.svelte zieht die Endstunde jetzt ueber die pure, importierbare
// Funktion clampDayWindowEndHour() automatisch nach (echte Ausfuehrung unten,
// keine Mocks -- Praezedenz: corridor-editor/corridorEditorState.ts
// openBoundValue in corridorEditorMobile.test.ts).
//
// F002 (LOW): AC-6 (Tagesfenster-Control nur context="route") hat bisher nur
// einen Playwright-Test, der wegen #1329 (open-meteo-Kontingent) nicht laeuft.
// Ergaenzt um einen schnellen, source-inspizierenden Unit-Test analog
// vt_schedule_plan_hour_step.test.ts.
//
// Fix-Loop Runde 2 (F005, HIGH): Startstunde 23 war ueber das UI waehlbar,
// konnte aber nie ein gueltiges Fenster bilden (start<end<=23 verlangt).
// VTSchedulePlan.svelte deckelt die Start-Optionen jetzt auf 0..22 --
// gedeckt durch die source-inspizierenden Tests unten (kein Rendering-
// Harness fuer Svelte-5-Runen im node:test-Setup, daher Text-Grep wie in
// F002 oben).
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/versand-tab/__tests__/vt_schedule_plan_day_window.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { clampDayWindowEndHour } from '../dayWindowClamp.ts';

const here = dirname(fileURLToPath(import.meta.url));
const VT_SCHEDULE_PLAN = join(here, '..', 'VTSchedulePlan.svelte');
const VERSAND_TAB = join(here, '..', '..', 'VersandTab.svelte');

describe('F001-Fix: clampDayWindowEndHour() zieht die Endstunde nach, sobald start>=end waere', () => {
	test('Repro: Startstunde 19 bei Default-Endstunde 19 -- Endstunde wird auf 20 nachgezogen', () => {
		// Genau der Adversary-Reproduktionsfall: Start=19, End=Default(19).
		const result = clampDayWindowEndHour(19, 19);
		assert.equal(result, 20, `Endstunde muss auf start+1=20 nachgezogen werden, war aber ${result}`);
	});

	test('Startstunde ueberholt eine kleinere Endstunde (start=15, end=10) -- End wird auf 16 gezogen', () => {
		const result = clampDayWindowEndHour(15, 10);
		assert.equal(result, 16);
	});

	test('Unerreichbarer Grenzfall Startstunde=23 -- clampDayWindowEndHour bleibt als Backend-Sicherheitsnetz korrekt (0-23-Bereich, kein Wrap), auch wenn das UI 23 seit F005-Fix nicht mehr als Start anbietet', () => {
		const result = clampDayWindowEndHour(23, 23);
		assert.equal(result, 23, 'darf 23 nicht ueberschreiten (0-23-Bereich)');
	});

	test('gueltiges Paar bleibt unangetastet (start=6, end=16)', () => {
		const result = clampDayWindowEndHour(6, 16);
		assert.equal(result, 16, 'eine bereits gueltige Endstunde darf nicht veraendert werden');
	});

	test('Grenzfall start=end-1 (noch gueltig) bleibt unangetastet', () => {
		const result = clampDayWindowEndHour(5, 6);
		assert.equal(result, 6);
	});
});

describe('F001-Fix: VersandTab.svelte nutzt die echte Klemm-Funktion (kein Doppel-PUT-Risiko durch stillen Reset)', () => {
	test('importiert clampDayWindowEndHour aus dayWindowClamp.ts', () => {
		const src = readFileSync(VERSAND_TAB, 'utf-8');
		assert.match(
			src,
			/from '\.\/versand-tab\/dayWindowClamp\.ts'/,
			'VersandTab.svelte muss clampDayWindowEndHour importieren statt eine eigene Kopie zu bauen'
		);
	});

	test('makeDayWindowStartHandler setzt day_window_start_hour UND day_window_end_hour synchron im selben Handler-Aufruf', () => {
		const src = readFileSync(VERSAND_TAB, 'utf-8');
		const fnStart = src.indexOf('function makeDayWindowStartHandler');
		assert.ok(fnStart >= 0, 'makeDayWindowStartHandler fehlt');
		const fnEnd = src.indexOf('\n\t}', fnStart);
		const fnBody = src.slice(fnStart, fnEnd);
		assert.match(fnBody, /day_window_start_hour\s*=\s*v/, 'muss day_window_start_hour setzen');
		assert.match(
			fnBody,
			/day_window_end_hour\s*=\s*clampDayWindowEndHour\(v,\s*day_window_end_hour\)/,
			'muss day_window_end_hour im selben Aufruf ueber clampDayWindowEndHour nachziehen (ein PUT, kein Doppel-PUT)'
		);
	});

	test('onDayWindowStartHour bindet an makeDayWindowStartHandler (nicht mehr an den generischen makeHourSelectHandler)', () => {
		const src = readFileSync(VERSAND_TAB, 'utf-8');
		assert.match(
			src,
			/onDayWindowStartHour=\{makeDayWindowStartHandler\(\)\}/,
			'onDayWindowStartHour muss makeDayWindowStartHandler() verwenden'
		);
	});
});

describe('F005-Fix: Start-Dropdown bietet nur 0..22 an -- jede waehlbare Startstunde kann ein gueltiges Paar bilden', () => {
	const src = readFileSync(VT_SCHEDULE_PLAN, 'utf-8');

	test('dayWindowStartOptions filtert 23 aus den 24 Basis-Stunden heraus', () => {
		assert.match(
			src,
			/const dayWindowStartOptions = dayWindowHourOptions\.filter\(\(h\) => h < 23\)/,
			'Start-Optionen muessen auf 0..22 gedeckelt sein, sonst kann Start=23 nie ein gueltiges Fenster bilden'
		);
	});

	test('das Start-Select iteriert ueber dayWindowStartOptions, nicht mehr ueber die ungefilterten 0..23', () => {
		const startSelectIdx = src.indexOf('data-testid="day-window-start-hour"');
		assert.ok(startSelectIdx >= 0, 'Start-Select fehlt');
		const eachIdx = src.indexOf('{#each', startSelectIdx);
		const eachLine = src.slice(eachIdx, src.indexOf('\n', eachIdx));
		assert.match(
			eachLine,
			/dayWindowStartOptions/,
			'Start-Select muss dayWindowStartOptions rendern, nicht dayWindowHourOptions'
		);
	});

	test('Grenzfall start=22 -> clampDayWindowEndHour liefert 23 (letzte erreichbare Start-/End-Kombination bleibt gueltig)', () => {
		const result = clampDayWindowEndHour(22, 22);
		assert.equal(result, 23, 'bei Start=22 (hoechste ueber UI waehlbare Startstunde) muss End auf 23 nachgezogen werden');
	});
});

describe('F002/AC-6: Tagesfenster-Control liegt textuell im {#if isRoute}-Block (nur context="route")', () => {
	test('VTSchedulePlan.svelte existiert', () => {
		assert.ok(existsSync(VT_SCHEDULE_PLAN), 'VTSchedulePlan.svelte fehlt');
	});

	test('data-testid="day-window-control" liegt zwischen {#if isRoute} und dessen schliessendem {/if}', () => {
		const src = readFileSync(VT_SCHEDULE_PLAN, 'utf-8');
		const ifIdx = src.indexOf('{#if isRoute}');
		assert.ok(ifIdx >= 0, '{#if isRoute}-Block fehlt');
		const controlIdx = src.indexOf('data-testid="day-window-control"');
		assert.ok(controlIdx >= 0, 'data-testid="day-window-control" fehlt');
		assert.ok(controlIdx > ifIdx, 'day-window-control muss NACH {#if isRoute} liegen');

		// Naechstes {/if} nach ifIdx, das den isRoute-Block schliesst: es gibt
		// genau einen weiteren {#if}-Block (Mehrtages-Trend-Karte) VOR dem
		// Control, aber keinen NACH dem Control innerhalb desselben
		// isRoute-Blocks -- daher muss das erste {/if} NACH dem Control-Index
		// das schliessende {/if} des isRoute-Blocks sein.
		const closeIdx = src.indexOf('{/if}', controlIdx);
		assert.ok(closeIdx >= 0, 'kein schliessendes {/if} nach dem Control gefunden');
		// Zwischen Control und diesem {/if} darf kein weiterer {#if}-Block
		// oeffnen (sonst waere es nicht das isRoute-schliessende {/if}).
		const between = src.slice(controlIdx, closeIdx);
		assert.ok(!between.includes('{#if'), 'zwischen Control und dem schliessenden {/if} darf kein neuer Block oeffnen');
	});
});
