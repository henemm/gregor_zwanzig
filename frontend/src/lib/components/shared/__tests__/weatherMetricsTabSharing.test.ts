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
		// D2-Fix-Loop 2 (AC-6, Staging-Befund BROKEN): 'official_alerts' ist eine
		// Ausnahme vom Attrappen-Verbot fuer vergleich — der Amtliche-
		// Warnungen-Schalter hat echte Mail-Wirkung (official_alerts_enabled)
		// und ist fuer bestehende Vergleiche nur noch ueber diesen Hub-Tab
		// erreichbar (der Alarm-Tab-Toggle entfaellt mit D2).
		// Spec: d2_1301_official_alerts_single_control.md § AC-6.
		//
		// Issue #1359 Scheibe 1: 'reihenfolge' kommt DAZU. Diese Erwartung fror
		// das Fehlen des Abschnitts fest — sie dreht sich um, weil die
		// Listenposition in `display_config.active_metrics` seit #1335/#1359 die
		// Zeilenfolge in HTML-Mail, Klartext und Telegram bestimmt (und ueber
		// das SMS-Budget sogar, WELCHE Metriken die SMS erreichen). Damit hat
		// der Abschnitt echte Mail-Wirkung und ist keine Attrappe.
		// Spec: compare_metric_order.md § "Abgeloeste Festlegung".
		// 'sms_schwellen'/'report_config' bleiben route-exklusiv.
		'vergleich: grundauswahl + reihenfolge + stundenverlauf + official_alerts — keine Buckets/Horizonte/SMS-Schwellen/Report-Config (AC-1, AC-8 Attrappen-Verbot)',
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
			// Issue #1360: 'stundenverlauf' ist die neue Heimat der Stundenverlauf-
			// Steuerung (Layout-Reiter aufgeloest). Sie hat echte Mail-Wirkung
			// (hourly_enabled/hourly_metrics) und ist deshalb KEINE Attrappe.
			// Issue #1361/#1372 S1b: 'tagesfenster' kommt DAZU — geteilt mit dem
			// Trip (AC-4), wirkt auf Stundentabelle UND Vergleichswerte.
			// Issue #1361 Befund 2/#1368: 'ausblick' kommt DAZU — Schalter
			// (outlook_enabled) und Spaltenauswahl (display_config.outlook_metrics)
			// haben echte Mail-Wirkung im 3-Tages-Ausblick, also keine Attrappe.
			assert.deepEqual(
				sections,
				[
					'grundauswahl',
					'reihenfolge',
					'tagesfenster',
					'stundenverlauf',
					'ausblick',
					'official_alerts'
				],
				'AC-1/AC-8/AC-6 FAIL: der vergleich-Kontext zeigt mehr/weniger als Grundauswahl+Reihenfolge+Tagesfenster+Stundenverlauf+Amtliche-Warnungen — ' +
					`Ist: ${JSON.stringify(sections)}. Horizonte/SMS-Schwellen/Report-Config haetten ` +
					'keine Mail-Wirkung im Vergleich und waeren Attrappen.'
			);
		}
	);
});

// Issue #1575 Scheibe 3, AC-8: die kanal-eigene Metrik-Auswahl ist Trip-only
// (#1351 haelt `channel_layouts` bewusst aus dem Ortsvergleich heraus). Geprueft
// wird die STELLE im Quelltext, nicht die blosse Anwesenheit eines Wortes:
// jedes Vorkommen der neuen Kanal-Ableitung im Markup muss hinter dem `{:else}`
// des `{#if context === 'vergleich'}`-Blocks liegen, und keiner der
// vergleich-eigenen Handler darf sie aufrufen.
describe('AC-8 (#1575): Kanal-eigene Auswahl bleibt strukturell aus dem vergleich-Zweig heraus', () => {
	const compareHandlers = [
		'onCompareDndReorder', 'onCompareRemove', 'noopMode', 'onToggleVergleichOfficialAlerts',
	];

	test('channelView()/channelBuckets stehen im Markup nur im route-Zweig', { skip: !sharedExists() }, () => {
		const code = readFileSync(SHARED_FILE, 'utf-8');
		const markupStart = code.indexOf("{#if context === 'vergleich'}");
		const routeStart = code.indexOf('\n{:else}', markupStart);
		assert.ok(markupStart > 0 && routeStart > markupStart, 'Markup-Verzweigung nicht gefunden');

		for (const m of code.matchAll(/channelView\(|channelBuckets/g)) {
			if (m.index! < markupStart) continue; // <script>-Teil: Definition + route-Handler
			assert.ok(
				m.index! > routeStart,
				`AC-8 FAIL: "${m[0]}" steht im vergleich-Zweig des Markups (Position ${m.index}, ` +
					`vergleich-Block ${markupStart}..${routeStart}) — der Ortsvergleich bekommt ` +
					'laut #1351 keine Kanal-Persistenz'
			);
		}
	});

	test('kein vergleich-Handler ruft die neuen Kanal-Funktionen', { skip: !sharedExists() }, () => {
		const code = readFileSync(SHARED_FILE, 'utf-8');
		for (const name of compareHandlers) {
			const start = code.indexOf(`function ${name}(`);
			assert.ok(start > 0, `${name} nicht gefunden — Test ist blind geworden`);
			const body = code.slice(start, code.indexOf('\n\t}', start));
			assert.doesNotMatch(
				body,
				/editActiveChannel|channelBuckets|channelView\(|mergeChannelLayoutsForSave|startChannelOverride/,
				`AC-8 FAIL: ${name} (vergleich-Zweig) greift auf die kanal-eigene Auswahl zu`
			);
		}
	});
});
