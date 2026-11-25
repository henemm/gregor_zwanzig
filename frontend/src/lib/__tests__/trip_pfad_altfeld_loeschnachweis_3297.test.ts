// # doc-compliance-test
// Lösch- und Sperrnachweis — Issue #3297 + #3020 (Epic #3122).
// Spec: docs/specs/modules/feat_3297_trip_pfad_ohne_altfelder.md (AC-7, AC-8)
//
// Ausdrücklich ein Dateiinhalt-/Dateisystem-Nachweis (Ausnahme `# doc-compliance-test` der Test-Politik):
// geprüft wird, dass der nicht mehr eingebundene Alt-Editor samt Umfeld gelöscht ist, keine
// Produktionsdatei ihn noch importiert (auch nicht über Barrels oder dynamisch), die weiter benutzten
// Vergleich-/Vorlagen-Hilfen erhalten sind und die Schlüssel `show_outlook` und
// `multi_day_trend_reports` in keiner Produktionsdatei mehr stehen. Das Verhalten (Nutzlasten ohne
// Altschlüssel) belegt trip-new/__tests__/trip_pfad_ohne_altfelder_3297.test.ts.
//
// RED heute: alle Dateien der Löschliste existieren, Barrels und WetterMetrikenVersandPanel importieren
// sie, elf Produktionsdateien nennen show_outlook/multi_day_trend_reports.
// Regressionsschutz (heute grün): die Vergleich-Hilfen existieren.
//
// Ausführen (aus frontend/):
//   npm test -- src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const SRC = fileURLToPath(new URL('../../', import.meta.url)); // frontend/src/
const pfad = (rel: string) => join(SRC, rel);

/** Löschliste (Spec, Affected Files: DELETE). */
const GELOESCHT = [
	'lib/components/shared/WeatherMetricsTab.svelte',
	'lib/components/shared/WetterMetrikenVersandPanel.svelte',
	'lib/components/trip-detail/BriefingScheduleTab.svelte',
	'lib/components/shared/VersandTab.svelte',
	'lib/components/shared/MailInhaltCard.svelte',
	'lib/components/shared/OutlookLayoutControls.svelte',
	'lib/components/shared/weather-metrics-tab/channelMetricLayouts.ts',
	'lib/components/shared/weather-metrics-tab/weatherMetricsSavePayload.ts',
	'lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts'
];

/** Bleiben (Vergleich/Vorlagen, Rest #3298/#3301). */
const ERHALTEN = [
	'lib/components/shared/weather-metrics-tab/outlookFriendlyCapability.ts',
	'lib/components/shared/weather-metrics-tab/compareMetricSelection.ts',
	'lib/components/shared/weather-metrics-tab/compareMetricOrder.ts',
	'lib/components/shared/weather-metrics-tab/compareChannelMetricLayouts.ts',
	'lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts',
	'lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte',
	'lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts'
];

const istTest = (rel: string) => /(^|\/)__tests__\//.test(rel) || /\.(test|spec)\.[tj]s$/.test(rel);

/** Alle Produktions-Quelldateien unter frontend/src (ohne Tests). */
function produktionsdateien(): string[] {
	const aus: string[] = [];
	const lauf = (dir: string) => {
		for (const name of readdirSync(dir)) {
			const voll = join(dir, name);
			if (statSync(voll).isDirectory()) {
				if (name !== 'node_modules') lauf(voll);
				continue;
			}
			const rel = relative(SRC, voll).split('\\').join('/');
			if (/\.(ts|js|svelte)$/.test(name) && !istTest(rel)) aus.push(rel);
		}
	};
	lauf(SRC);
	return aus;
}

const basisname = (rel: string) => rel.split('/').pop()!.replace(/\.(svelte|ts)$/, '');
const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

describe('#3297/#3020 AC-7: toter Alt-Editor gelöscht, keine Importe, Vergleich-Hilfen erhalten', () => {
	for (const rel of GELOESCHT) {
		test(`gelöscht: ${rel}`, () => {
			assert.equal(existsSync(pfad(rel)), false, `${rel} existiert noch`);
		});
	}

	test('keine Produktionsdatei importiert eine gelöschte Datei (statisch, Barrel-Export, dynamisch)', () => {
		const namen = GELOESCHT.map(basisname);
		// Pfadsegment-genau: `…/Name`, `…/Name.svelte`, `…/Name.ts` im Modulpfad von import/export/import().
		const muster = new RegExp(`(?:from|import\\s*\\()\\s*['"][^'"]*/(${namen.map(escape).join('|')})(?:\\.svelte|\\.ts|\\.js)?['"]`, 'g');
		const funde: string[] = [];
		for (const rel of produktionsdateien()) {
			const text = readFileSync(pfad(rel), 'utf8');
			for (const m of text.matchAll(muster)) funde.push(`${rel} -> ${m[1]}`);
		}
		assert.deepEqual(funde, [], 'Produktions-Importe der gelöschten Dateien');
	});

	for (const rel of ERHALTEN) {
		test(`erhalten (Regressionsschutz, heute grün): ${rel}`, () => {
			assert.equal(existsSync(pfad(rel)), true, `${rel} wurde mitgelöscht, wird aber noch gebraucht`);
		});
	}
});

describe('#3297 AC-8: show_outlook und multi_day_trend_reports aus dem Frontend-Produktionscode', () => {
	test('keine Produktionsdatei unter frontend/src nennt einen der beiden Schlüssel', () => {
		const funde: string[] = [];
		for (const rel of produktionsdateien()) {
			readFileSync(pfad(rel), 'utf8')
				.split('\n')
				.forEach((zeile, i) => {
					if (/\b(show_outlook|multi_day_trend_reports)\b/.test(zeile)) funde.push(`${rel}:${i + 1}`);
				});
		}
		assert.deepEqual(funde, [], 'Treffer auf show_outlook/multi_day_trend_reports');
	});
});
