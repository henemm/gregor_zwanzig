// TDD RED — Issue #1311, Scheibe C1 von Epic #1301: WeatherMetricsTab wird von
// trip-detail/ nach shared/ verschoben und um context="route"|"vergleich"
// erweitert (Vorbild: shared/AlarmeTab.svelte + alarme-tab/alarmeTabSections.ts).
//
// Spec: docs/specs/modules/compare_weather_metrics_tab.md § AC-1, AC-6, AC-8,
//   Implementation Details Abschnitt 1
//
// Source-Inspection-Muster analog compare/__tests__/compare_hub_fidelity.test.ts
// und shared/__tests__/alarme_save_single_writer.test.ts: readFileSync auf die
// Produktivdatei(en) + Assertions auf Struktur, keine Mocks. Solange die
// verschobene Komponente noch nicht existiert, werden die tieferen
// Struktur-Tests bewusst uebersprungen (skip) statt den Runner mit einem
// rohen ENOENT abzubrechen — der existsSync-Test selbst schlaegt sprechend fehl.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/weatherMetricsTabSharing.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

// __tests__ → shared → components → lib → src
// (Fix: die urspruengliche RED-Version ging nur 3 Ebenen hoch und landete bei
// `lib` statt `src` — SHARED_FILE haengte dann ein zweites `lib`-Segment an
// und zeigte auf einen nie existierenden Pfad, unabhaengig vom Verschiebungs-
// Ergebnis. Kommentar nannte bereits 4 Hops — reiner Off-by-one-Fix.)
const SRC = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', '..');

const SHARED_FILE = join(SRC, 'lib', 'components', 'shared', 'WeatherMetricsTab.svelte');
const TRIP_DETAIL_FILE = join(SRC, 'lib', 'components', 'trip-detail', 'WeatherMetricsTab.svelte');
const SECTIONS_FILE = join(SRC, 'lib', 'components', 'shared', 'weather-metrics-tab', 'weatherMetricsTabSections.ts');
const SECTIONS_MODULE_SPECIFIER = '../weather-metrics-tab/weatherMetricsTabSections.ts';

const sharedExists = () => existsSync(SHARED_FILE);
const sectionsExist = () => existsSync(SECTIONS_FILE);

describe('AC-1/AC-8: WeatherMetricsTab existiert unter shared/ (Verschiebung aus trip-detail/)', () => {
	test('frontend/src/lib/components/shared/WeatherMetricsTab.svelte existiert', () => {
		assert.ok(
			sharedExists(),
			'AC-1/AC-8 FAIL: shared/WeatherMetricsTab.svelte existiert noch nicht — die 1027-zeilige ' +
				'trip-detail/WeatherMetricsTab.svelte wurde noch nicht nach shared/ verschoben (Teilungs-Vorbild AlarmeTab.svelte)'
		);
	});

	test(
		'hat eine context-Prop (WeatherMetricsContext, Default "route")',
		{ skip: !sharedExists() },
		() => {
			const code = readFileSync(SHARED_FILE, 'utf-8');
			assert.match(
				code,
				/context\??\s*:\s*WeatherMetricsContext/,
				'AC-1 FAIL: keine context-Prop vom Typ WeatherMetricsContext in den Props gefunden'
			);
			assert.match(
				code,
				/context\s*=\s*['"]route['"]/,
				'AC-1 FAIL: Default-Wert der context-Prop ist nicht "route"'
			);
		}
	);

	test('hat eine wiz-Prop fuer den Compare-Kontext (analog AlarmeTab.svelte)', { skip: !sharedExists() }, () => {
		const code = readFileSync(SHARED_FILE, 'utf-8');
		assert.match(code, /wiz\??\s*:\s*CompareWizardState/, 'AC-1 FAIL: keine wiz-Prop (CompareWizardState) gefunden');
	});

	test(
		'Abschnittsreihenfolge kommt aus weatherMetricsTabSections(context), nicht aus dupliziertem Markup (AC-9-Analogon)',
		{ skip: !sharedExists() },
		() => {
			const code = readFileSync(SHARED_FILE, 'utf-8');
			assert.match(
				code,
				/weatherMetricsTabSections\(\s*context\s*\)/,
				'AC-1 FAIL: Komponente ruft weatherMetricsTabSections(context) nicht auf — Reihenfolge muesste aus der reinen Funktion kommen'
			);
		}
	);

	test(
		'Rendering von Reihenfolge/SMS-Schwellen/Report-Config ist an sections.includes(...) gebunden (Attrappen-Verbot AC-8)',
		{ skip: !sharedExists() },
		() => {
			const code = readFileSync(SHARED_FILE, 'utf-8');
			for (const section of ['reihenfolge', 'sms_schwellen', 'report_config']) {
				assert.match(
					code,
					new RegExp(`sections\\.includes\\(\\s*['"]${section}['"]\\s*\\)`),
					`AC-8 FAIL: kein sections.includes('${section}')-Gate gefunden — Abschnitt koennte im ` +
						`vergleich-Kontext unkontrolliert (als Attrappe) sichtbar sein`
				);
			}
		}
	);
});

describe('AC-1: trip-detail/WeatherMetricsTab.svelte wird durch die Verschiebung ersetzt (kein Duplikat)', () => {
	// Reine Verschiebung (git mv) laut Spec — die alte Datei darf nach C1 nicht
	// mehr als eigenstaendige 1027-Zeilen-Kopie neben shared/ existieren, sonst
	// ist Compare eine Kopie statt Teilung (Default-Fehler #1170).
	test('trip-detail/WeatherMetricsTab.svelte existiert nicht mehr, sobald shared/ existiert', { skip: !sharedExists() }, () => {
		assert.equal(
			existsSync(TRIP_DETAIL_FILE),
			false,
			'AC-1 FAIL (Duplikat-Verdacht): trip-detail/WeatherMetricsTab.svelte existiert NEBEN shared/WeatherMetricsTab.svelte ' +
				'— Trip/Compare-Teilungs-Invariante verlangt Verschiebung, keine Parallel-Kopie'
		);
	});
});

describe('AC-1/AC-8: weatherMetricsTabSections(context) — reine Funktion (Vorbild alarmeTabSections.ts)', () => {
	test('frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts existiert', () => {
		assert.ok(
			sectionsExist(),
			'AC-1/AC-8 FAIL: weatherMetricsTabSections.ts existiert noch nicht'
		);
	});

	test('route: enthaelt grundauswahl + alle drei route-only Sections', async () => {
		let mod: typeof import('../weather-metrics-tab/weatherMetricsTabSections.ts');
		try {
			mod = await import(SECTIONS_MODULE_SPECIFIER);
		} catch (e) {
			assert.fail(
				`AC-1 FAIL: weatherMetricsTabSections.ts kann nicht importiert werden (existiert noch nicht): ${(e as Error).message}`
			);
			return;
		}
		const sections = mod.weatherMetricsTabSections('route');
		assert.ok(sections.includes('grundauswahl'), 'AC-1 FAIL: "grundauswahl" fehlt im route-Kontext');
		for (const s of ['reihenfolge', 'sms_schwellen', 'report_config']) {
			assert.ok(sections.includes(s), `AC-6 FAIL: route-only Section "${s}" fehlt (Regressionsschutz)`);
		}
	});

	test(
		'vergleich: NUR grundauswahl — keine Buckets/Reihenfolge/Horizonte/SMS-Schwellen/Report-Config (AC-1, AC-8 Attrappen-Verbot)',
		async () => {
			let mod: typeof import('../weather-metrics-tab/weatherMetricsTabSections.ts');
			try {
				mod = await import(SECTIONS_MODULE_SPECIFIER);
			} catch (e) {
				assert.fail(
					`AC-1/AC-8 FAIL: weatherMetricsTabSections.ts kann nicht importiert werden (existiert noch nicht): ${(e as Error).message}`
				);
				return;
			}
			const sections = mod.weatherMetricsTabSections('vergleich');
			assert.deepEqual(
				sections,
				['grundauswahl'],
				'AC-1/AC-8 FAIL: der vergleich-Kontext zeigt mehr als nur die Grundauswahl — ' +
					`Ist: ${JSON.stringify(sections)}. Buckets/Horizonte/SMS-Schwellen/Report-Config haetten ` +
					'keine Mail-Wirkung im Vergleich und waeren Attrappen.'
			);
		}
	);
});
