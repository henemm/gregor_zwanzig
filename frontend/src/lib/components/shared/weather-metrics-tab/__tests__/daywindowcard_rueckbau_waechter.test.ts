// TDD RED — Issue #2931: Rueckbau Tagesfenster-Abschnitt + DayWindowCard aus
// WeatherMetricsTab (ADR-0112: alte Bausteine loeschen).
// Spec: docs/specs/modules/fix_2931_daywindowcard_rueckbau.md (AC-1 bis AC-3, AC-5, AC-6).
//
// Zwei Schichten in dieser Datei:
//   * VERHALTEN (AC-2): der ECHTE WeatherMetricsTab wird per svelte/server im
//     Standardbereich 'alles' in BEIDEN Kontexten gerendert (Pruefstand
//     f5Pruefstand.ts, derselbe Zustand wie die F5-Goldens) — das Markup darf
//     weder `weather-metrics-tagesfenster` noch `dwc-` enthalten. Ausserdem
//     liefert die echte Abschnittsfunktion kein 'tagesfenster' mehr.
//   * doc-compliance-test (AC-1, AC-3, AC-5, AC-6): Struktur-Waechter
//     (Existenz, Import-Scan, Props-Interface, Kataloge, Ratschen-Konfig). Sie
//     belegen KEIN Nutzerverhalten; der Erhalt der Tagesfenster-SPEICHERPFADE
//     (AC-4) ist in weatherMetricsCompareSave / wetter_tab_scheibe_c /
//     trip_new_editor_weather_metrics_wiring belegt, die unveraendert gruen
//     bleiben muessen. Muster wie mail_inhalt_rueckbau_waechter.test.ts.
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/shared/weather-metrics-tab/__tests__/daywindowcard_rueckbau_waechter.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { join, dirname, relative } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const WMT = join(HERE, '..');                          // shared/weather-metrics-tab
const SHARED = join(WMT, '..');                        // shared
const LIB = join(SHARED, '..', '..');                  // frontend/src/lib
const FRONTEND = join(LIB, '..', '..');                // frontend
const REPO = join(FRONTEND, '..');
const SELF = fileURLToPath(import.meta.url);

const istKommentar = (z: string) => /^\s*(\/\/|\/\*|\*|#|<!--)/.test(z);

function dateien(dir: string, out: string[] = []): string[] {
	if (!existsSync(dir)) return out;
	for (const name of readdirSync(dir)) {
		if (name === 'node_modules' || name === '.svelte-kit' || name === '__pycache__') continue;
		const p = join(dir, name);
		if (statSync(p).isDirectory()) dateien(p, out);
		else if (/\.(ts|js|mjs|svelte|py)$/.test(name)) out.push(p);
	}
	return out;
}

// ---------------------------------------------------------------------------
// AC-2 — Verhalten: gerendertes Markup in beiden Kontexten, Bereich 'alles'
// ---------------------------------------------------------------------------
describe('AC-2: WeatherMetricsTab zeigt in keinem Kontext einen Tagesfenster-Abschnitt', () => {
	test('abschnittsliste_enthaelt_kein_tagesfenster__route_und_vergleich_alle_bereiche', async () => {
		const { weatherMetricsTabSections } = await import(pathToFileURL(join(WMT, 'weatherMetricsTabSections.ts')).href);
		for (const ctx of ['route', 'vergleich']) {
			for (const bereich of ['alles', 'zustellung', 'wetter']) {
				const s: string[] = weatherMetricsTabSections(ctx, bereich);
				assert.ok(!s.includes('tagesfenster'), `AC-2: Abschnittsliste ${ctx}/${bereich} enthaelt noch 'tagesfenster': ${s.join(', ')}`);
			}
		}
	});

	// Pruefstand erst hier laden: er registriert die SSR-Hooks und rendert den echten Tab.
	for (const ctx of ['route', 'vergleich'] as const) {
		test(`ssr_markup_ohne_tagesfenster_und_ohne_dwc__${ctx}`, async () => {
			const p = await import(pathToFileURL(join(HERE, 'f5Pruefstand.ts')).href);
			const html: string = ctx === 'route' ? p.routeRendern({}, 'rueckbau-2931') : p.vergleichRendern({});
			// Gegenprobe: der Tab wurde wirklich gerendert (sonst waere "nichts drin" trivial).
			assert.ok(html.length > 1000, `AC-2: ${ctx}-Render ist verdaechtig kurz (${html.length} Zeichen)`);
			assert.ok(!html.includes('weather-metrics-tagesfenster'), `AC-2: ${ctx}-Markup enthaelt noch data-testid="weather-metrics-tagesfenster"`);
			const dwc = html.match(/dwc-[\w-]*/g) ?? [];
			assert.deepEqual(dwc, [], `AC-2: ${ctx}-Markup enthaelt noch DayWindowCard-Markup: ${[...new Set(dwc)].join(', ')}`);
		});
	}
});

// ---------------------------------------------------------------------------
// AC-1 — doc-compliance-test: Baustein + Test geloescht, niemand laedt sie
// ---------------------------------------------------------------------------
describe('AC-1: DayWindowCard samt eigenem Test ist geloescht', () => {
	for (const rel of [
		'DayWindowCard.svelte',
		'__tests__/day_window_card.test.ts',
		'../__tests__/weatherMetricsTabDayWindowSave.test.ts'
	]) {
		test(`datei_existiert_nicht_mehr__${rel.replace(/\W+/g, '_')}`, () => {
			assert.ok(!existsSync(join(WMT, rel)), `AC-1: ${rel} existiert noch.`);
		});
	}

	// Gezaehlt wird nur, was die Datei LAEDT: ein Import des Bezeichners oder ein
	// Pfad-String auf DayWindowCard.svelte (import/readFileSync/pathToFileURL).
	// Abwesenheits-Zusicherungen anderer Tests (z. B. wetter_tab_scheibe_c:
	// importVon(q, 'DayWindowCard') === null) und Kommentare bleiben erlaubt.
	const LAEDT = /\bimport\b[^\n]*\bDayWindowCard\b|['"][^'"\n]*DayWindowCard\.svelte[^'"\n]*['"]|<DayWindowCard\b/;
	test('kein_quell_test_oder_e2e_code_laedt_DayWindowCard', () => {
		const treffer: string[] = [];
		for (const w of [join(FRONTEND, 'src'), join(FRONTEND, 'e2e'), join(REPO, 'tests')]) {
			for (const f of dateien(w)) {
				if (f === SELF) continue;
				readFileSync(f, 'utf-8').split('\n').forEach((z, i) => {
					if (!istKommentar(z) && LAEDT.test(z)) treffer.push(`${relative(REPO, f)}:${i + 1}: ${z.trim().slice(0, 120)}`);
				});
			}
		}
		assert.deepEqual(treffer, [], `AC-1: ${treffer.length} Bezug/Bezuege auf DayWindowCard:\n${treffer.join('\n')}`);
	});
});

// ---------------------------------------------------------------------------
// AC-3 — doc-compliance-test: tote Prop raus, Wertprops + Handler bleiben
// ---------------------------------------------------------------------------
describe('AC-3: Prop onDayWindowChange entfernt, Tagesfenster-Wertprops bleiben', () => {
	const code = readFileSync(join(SHARED, 'WeatherMetricsTab.svelte'), 'utf-8');
	const props = code.match(/interface\s+Props\s*\{([\s\S]*?)\n\t\}/)?.[1] ?? '';

	test('props_interface_gefunden', () => {
		assert.ok(props.length > 0, 'AC-3: interface Props in WeatherMetricsTab.svelte nicht gefunden');
	});

	test('keine_prop_onDayWindowChange_und_kein_aufruf', () => {
		const zeilen = code.split('\n').filter((z) => !istKommentar(z) && /\bonDayWindowChange\b/.test(z));
		assert.deepEqual(zeilen.map((z) => z.trim()), [], 'AC-3: onDayWindowChange (Prop, Destrukturierung oder $effect-Aufruf) ist noch vorhanden');
	});

	for (const name of ['dayWindowStartHour', 'dayWindowEndHour', 'onDayWindowStartHourChange', 'onDayWindowEndHourChange']) {
		test(`prop_bleibt__${name}`, () => {
			assert.match(props, new RegExp(`\\b${name}\\?\\s*:`), `AC-3: Prop ${name} fehlt im Props-Interface (darf NICHT mit entfernt werden)`);
		});
	}
});

// ---------------------------------------------------------------------------
// AC-5 — doc-compliance-test: Bausteine-Ratsche
// ---------------------------------------------------------------------------
describe('AC-5: BESTAND-Ratsche gesenkt', () => {
	test('bestand_ohne_daywindowcard_und_obergrenze_198', async () => {
		const { KONFIG } = await import(pathToFileURL(join(LIB, '__tests__', 'bausteine_waechter_regeln.ts')).href);
		assert.ok(!KONFIG.BESTAND.some((b: string) => /DayWindowCard/.test(b)), 'AC-5: DayWindowCard steht noch in BESTAND');
		assert.equal(KONFIG.BESTAND_OBERGRENZE, 198, 'AC-5: BESTAND_OBERGRENZE muss von 199 auf 198 sinken');
	});
});

// ---------------------------------------------------------------------------
// AC-6 — doc-compliance-test: Kataloge DE/EN + Elementliste
// ---------------------------------------------------------------------------
describe('AC-6: Katalogschluessel wertebereiche.tagesfenster.* gestrichen, Elementliste umgestellt', () => {
	for (const sprache of ['de', 'en']) {
		test(`katalog_${sprache}_ohne_wertebereiche_tagesfenster`, () => {
			const kat = JSON.parse(readFileSync(join(LIB, 'i18n', 'messages', sprache, 'wertebereiche.json'), 'utf-8'));
			const rest = Object.keys(kat).filter((k) => k.startsWith('wertebereiche.tagesfenster.'));
			assert.deepEqual(rest, [], `AC-6: ${sprache}/wertebereiche.json enthaelt noch ${rest.join(', ')}`);
		});
	}

	test('elementliste_verweist_auf_wetter_anpassen_tagesfenster', () => {
		const roh = readFileSync(join(REPO, 'docs', 'context', 'einstellungen_neu', 'elementliste.json'), 'utf-8');
		const eintraege = JSON.stringify(JSON.parse(roh)).match(/\{[^{}]*"text_de":"Tagesfenster"[^{}]*\}/g) ?? [];
		assert.equal(eintraege.length, 4, `AC-6: erwartet 4 Tagesfenster-Eintraege in der Elementliste, gefunden ${eintraege.length}`);
		for (const e of eintraege) {
			const o = JSON.parse(e);
			assert.equal(o.i18n_key, 'wetter.anpassen.tagesfenster', `AC-6: ${o.id} zeigt auf ${o.i18n_key}`);
			assert.equal(o.text_en, 'Day window', `AC-6: ${o.id} text_en veraendert`);
		}
	});
});
