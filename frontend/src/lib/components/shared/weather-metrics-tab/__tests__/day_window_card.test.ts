// Issue #1361/#1372 S1b — gemeinsames Tagesfenster fuer Trip UND Ortsvergleich.
// Spec: docs/specs/modules/compare_shared_day_window.md § AC-4
//
// Die Tagesfenster-Steuerung zieht aus dem Versand-Reiter (VersandTab/
// VTSchedulePlan, nur context="route") in den geteilten Reiter Wetter-Metriken
// (DayWindowCard.svelte, beide Kontexte, Abschnitt 'tagesfenster').
//
// Die Klemm-Funktion clampDayWindowEndHour() (Epic #1319 Scheibe B) wandert
// mit ihren Tests hierher aus dem geloeschten
// versand-tab/__tests__/vt_schedule_plan_day_window.test.ts (dessen Subjekt,
// die Tagesfenster-Karte in VTSchedulePlan, nicht mehr existiert) — ihre
// Semantik aendert sich aber mit dieser Scheibe (PO-Entscheidung 2026-07-25):
// end < start ist jetzt ein GUELTIGES Mitternachts-Fenster, keine
// Nachzieh-Korrektur mehr. Nur end === start bleibt mehrdeutig.
//
// Kein Rendering-Harness fuer Svelte-5-Runen im node:test-Setup — daher
// source-inspizierende Tests (Praezedenz: vt_schedule_plan_hour_step.test.ts).

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { clampDayWindowEndHour } from '../../versand-tab/dayWindowClamp.ts';
import { weatherMetricsTabSections } from '../weatherMetricsTabSections.ts';

const here = dirname(fileURLToPath(import.meta.url));
const DAY_WINDOW_CARD = join(here, '..', 'DayWindowCard.svelte');
const WEATHER_METRICS_TAB = join(here, '..', '..', 'WeatherMetricsTab.svelte');
const VT_SCHEDULE_PLAN = join(here, '..', '..', 'versand-tab', 'VTSchedulePlan.svelte');
const VERSAND_TAB = join(here, '..', '..', 'VersandTab.svelte');

describe('clampDayWindowEndHour() — pure Klemm-Logik (AC-3, PO-Entscheidung 2026-07-25: Mitternacht gueltig)', () => {
	test('Startstunde 19 bei Default-Endstunde 19 (gleich) -- Endstunde wird auf 20 nachgezogen', () => {
		assert.equal(clampDayWindowEndHour(19, 19), 20);
	});

	test('gueltiges Vorwaerts-Paar bleibt unangetastet (start=6, end=16)', () => {
		assert.equal(clampDayWindowEndHour(6, 16), 16);
	});

	test('Mitternachts-Paar (start=22, end=2) bleibt unangetastet -- keine Nachzieh-Korrektur mehr', () => {
		assert.equal(clampDayWindowEndHour(22, 2), 2);
	});

	test('Grenzfall start=23, end=23 (gleich) -- End wird auf 0 nachgezogen (Modulo, kein 24)', () => {
		assert.equal(clampDayWindowEndHour(23, 23), 0);
	});

	test('start=22, end=22 (gleich) -- End auf 23 nachgezogen', () => {
		assert.equal(clampDayWindowEndHour(22, 22), 23);
	});
});

describe('AC-4: DayWindowCard.svelte — neue, geteilte Heimat der Tagesfenster-Steuerung', () => {
	test('DayWindowCard.svelte existiert', () => {
		assert.ok(existsSync(DAY_WINDOW_CARD), 'DayWindowCard.svelte fehlt');
	});

	test('traegt die drei bekannten Test-IDs (Karte + Von/Bis-Selects)', () => {
		const src = readFileSync(DAY_WINDOW_CARD, 'utf-8');
		for (const testid of ['day-window-control', 'day-window-start-hour', 'day-window-end-hour']) {
			assert.match(src, new RegExp(`data-testid="${testid}"`), `Test-ID "${testid}" fehlt`);
		}
	});

	test('hat KEIN context-Gate im Markup — dieselbe Karte fuer beide Kontexte (AC-4)', () => {
		const src = readFileSync(DAY_WINDOW_CARD, 'utf-8');
		assert.ok(!/context\s*===?\s*['"]route['"]/.test(src), 'DayWindowCard darf nicht route-exklusiv sein');
		assert.ok(!/context\s*===?\s*['"]vergleich['"]/.test(src), 'DayWindowCard darf nicht vergleich-exklusiv sein');
	});
});

describe('AC-3: Mitternachts-Fenster ist ueber die Bedienflaeche erreichbar (PO-Entscheidung 2026-07-25)', () => {
	const src = readFileSync(DAY_WINDOW_CARD, 'utf-8');

	test('Start-Optionen sind NICHT mehr auf 0..22 gedeckelt (der alte F005-Deckel galt nur ohne Mitternachts-Fenster)', () => {
		assert.ok(
			!/dayWindowHourOptions\.filter\(\(h\) => h < 23\)/.test(src),
			'der alte Vorwaerts-only-Deckel (h < 23) darf fuer die Startstunde nicht mehr gelten'
		);
	});

	test('End-Optionen bieten alle Stunden AUSSER der Startstunde an (nicht mehr nur "> startHour")', () => {
		assert.match(
			src,
			/dayWindowHourOptions\.filter\(\(h\) => h !== startHour\)/,
			'End-Optionen muessen auf "!== startHour" gefiltert sein, nicht auf "> startHour"'
		);
	});

	test('zeigt einen Mitternachts-Hinweis, wenn endHour < startHour', () => {
		assert.match(src, /data-testid="day-window-wrap-hint"/, 'Wrap-Hinweis-Element fehlt');
		assert.match(src, /wrapsMidnight/, 'wrapsMidnight-Bedingung fehlt');
		assert.match(src, /endHour\s*<\s*startHour/, 'Bedingung muss auf endHour < startHour pruefen');
	});
});

describe('AC-4: WeatherMetricsTab.svelte rendert DayWindowCard fuer beide Kontexte, gesteuert ueber die Section', () => {
	const src = readFileSync(WEATHER_METRICS_TAB, 'utf-8');

	test('importiert DayWindowCard', () => {
		assert.match(src, /import DayWindowCard from '\.\/weather-metrics-tab\/DayWindowCard\.svelte'/);
	});

	test("rendert <DayWindowCard hinter sections.includes('tagesfenster') — mindestens zweimal (route + vergleich)", () => {
		const gateMatches = src.match(/\{#if [^}]*sections\.includes\('tagesfenster'\)[^}]*\}/g) ?? [];
		assert.ok(
			gateMatches.length >= 2,
			`erwartet mindestens 2 Vorkommen (route + vergleich), gefunden: ${gateMatches.length}`
		);
		const cardMatches = src.match(/<DayWindowCard/g) ?? [];
		assert.ok(cardMatches.length >= 2, `erwartet mindestens 2 <DayWindowCard>-Aufrufe, gefunden: ${cardMatches.length}`);
	});

	test("weatherMetricsTabSections('route') und ('vergleich') liegen an derselben relativen Stelle (nach 'reihenfolge')", () => {
		const route = weatherMetricsTabSections('route');
		const vergleich = weatherMetricsTabSections('vergleich');
		for (const sections of [route, vergleich]) {
			assert.ok(sections.includes('tagesfenster'), `'tagesfenster' fehlt: ${JSON.stringify(sections)}`);
			assert.ok(
				sections.indexOf('reihenfolge') < sections.indexOf('tagesfenster'),
				`'tagesfenster' muss NACH 'reihenfolge' liegen: ${JSON.stringify(sections)}`
			);
		}
	});
});

describe('Regressionsschutz: Tagesfenster ist aus dem Versand-Reiter komplett entfernt', () => {
	test('VTSchedulePlan.svelte enthaelt keine day-window-control mehr', () => {
		const src = readFileSync(VT_SCHEDULE_PLAN, 'utf-8');
		assert.ok(!src.includes('data-testid="day-window-control"'), 'Tagesfenster-Karte haette aus VTSchedulePlan verschwinden muessen');
	});

	test('VersandTab.svelte importiert clampDayWindowEndHour nicht mehr (kein toter Import)', () => {
		const src = readFileSync(VERSAND_TAB, 'utf-8');
		assert.ok(!src.includes('dayWindowClamp'), 'VersandTab.svelte sollte dayWindowClamp nicht mehr referenzieren');
	});
});
