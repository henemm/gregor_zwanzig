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
import { join, posix, relative } from 'node:path';
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
	'lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts',
	// #3383 S1: bis dahin in ERHALTEN, dann als Waise gelöscht (Spec rework_3383_waisen_s1.md, AC-2)
	'lib/components/shared/weather-metrics-tab/outlookFriendlyCapability.ts'
];

/** Bleiben (Vergleich/Vorlagen, Rest #3298/#3301). */
const ERHALTEN = [
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

// #3366 S2 (Spec rework_3366_waisen_waechter_layout_tab.md, AC-5): layout-tab-Waisen und 9 Barrels.
// Barrels heißen alle `index`, daher kein Basisnamen-Scan, sondern Auflösung des Modulpfads auf
// den gelöschten Pfad (ohne Endung) bzw. das Barrel-Verzeichnis. RED heute: alle 15 existieren,
// LayoutTab.svelte importiert die LT-Bausteine.
const GELOESCHT_3366 = [
	'lib/components/shared/layout-tab/LTCapNote.svelte',
	'lib/components/shared/layout-tab/LTChannelPicker.svelte',
	'lib/components/shared/layout-tab/LTCutLine.svelte',
	'lib/components/shared/layout-tab/LayoutTab.svelte',
	'lib/components/shared/layout-tab/channelLayoutsDirty.ts',
	'lib/components/shared/layout-tab/ltIdealRange.ts',
	'lib/components/email-preview/index.ts',
	'lib/components/ui/dot/index.ts',
	'lib/components/ui/elev-sparkline/index.ts',
	'lib/components/ui/eyebrow/index.ts',
	'lib/components/ui/input/index.ts',
	'lib/components/ui/pill/index.ts',
	'lib/components/ui/segmented/index.ts',
	'lib/components/ui/topo/index.ts',
	'lib/components/ui/wicon/index.ts'
];

const ERHALTEN_3366 = ['lib/components/shared/layout-tab/ltChannels.ts', 'lib/index.ts'];

/** Ziele, unter denen eine gelöschte Datei importiert werden konnte (ohne Endung, Barrel auch als Verzeichnis). */
function importZiele(rel: string): string[] {
	const ohne = rel.replace(/\.(svelte|ts)$/, '');
	return ohne.endsWith('/index') ? [ohne, ohne.slice(0, -'/index'.length)] : [ohne];
}

/** Modulpfad eines Imports → normalisierter Pfad relativ zu src ohne Endung, oder null (Paket). */
function modulZiel(spez: string, von: string): string | null {
	let p: string;
	if (spez.startsWith('$lib/')) p = 'lib/' + spez.slice(5);
	else if (spez.startsWith('.')) p = posix.join(posix.dirname(von), spez);
	else return null;
	return posix.normalize(p).replace(/\.(svelte|ts|js)$/, '');
}

describe('#3366 AC-5: layout-tab-Waisen und Barrels gelöscht, keine Importe, ltChannels und lib/index erhalten', () => {
	for (const rel of GELOESCHT_3366) {
		test(`gelöscht: ${rel}`, () => {
			assert.equal(existsSync(pfad(rel)), false, `${rel} existiert noch`);
		});
	}

	test('keine Produktionsdatei importiert eine in #3366 gelöschte Datei (statisch, Barrel-Export, dynamisch)', () => {
		const ziele = new Map<string, string>();
		for (const rel of GELOESCHT_3366) for (const z of importZiele(rel)) ziele.set(z, rel);
		const muster = /(?:from|import\s*\()\s*['"]([^'"]+)['"]/g;
		const funde: string[] = [];
		for (const rel of produktionsdateien()) {
			const text = readFileSync(pfad(rel), 'utf8');
			for (const m of text.matchAll(muster)) {
				const z = modulZiel(m[1], rel);
				if (z !== null && ziele.has(z)) funde.push(`${rel} -> ${ziele.get(z)}`);
			}
		}
		assert.deepEqual(funde, [], 'Produktions-Importe der in #3366 gelöschten Dateien');
	});

	for (const rel of ERHALTEN_3366) {
		test(`erhalten (Regressionsschutz, heute grün): ${rel}`, () => {
			assert.equal(existsSync(pfad(rel)), true, `${rel} wurde mitgelöscht, wird aber noch gebraucht`);
		});
	}
});

// #3383 S1 (Spec rework_3383_waisen_s1.md, AC-1/AC-2/AC-8): 14 Waisen der Gruppe S1 gelöscht.
// RED heute: alle 14 existieren noch. Importscan zweifach: Auflösung des Modulpfads auf den gelöschten
// Pfad und Basisnamen-Scan (Pfadsegment-genau) im Produktionscode.
const GELOESCHT_3383 = [
	'lib/components/molecules/GrundauswahlLeerHinweis.svelte',
	'lib/components/shared/reportConfigDirty.ts',
	'lib/components/shared/weather-metrics-tab/AggregationMetricRow.svelte',
	'lib/components/shared/weather-metrics-tab/MultiSymbolMetricRow.svelte',
	'lib/components/shared/weather-metrics-tab/ThresholdMetricRow.svelte',
	'lib/components/shared/weather-metrics-tab/WeatherV2Grundauswahl.svelte',
	'lib/components/shared/weather-metrics-tab/WeatherV2PresetBar.svelte',
	'lib/components/shared/weather-metrics-tab/compareAggregationGrouping.ts',
	'lib/components/shared/weather-metrics-tab/nurEinBericht.ts',
	'lib/components/shared/weather-metrics-tab/outlookFriendlyCapability.ts',
	'lib/components/shared/weather-metrics-tab/wertebereicheAnzeige.ts',
	'lib/components/trip-detail/AboutOutputLayout.svelte',
	'lib/components/trip-detail/WeatherV2Kanaele.svelte',
	'lib/components/trip-detail/weatherSaveGate.ts'
];

const ERHALTEN_3383 = [
	'lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts',
	'lib/components/trip-detail/metricsEditor.ts'
	// #3384 S4: WaypointPin.svelte verlässt ERHALTEN und steht in GELOESCHT_3384
];

describe('#3383 AC-1/AC-2/AC-8: Waisen S1 gelöscht, keine Importe, lebende Nachbarn erhalten', () => {
	test('Löschliste #3383 hat genau 14 Einträge ohne Doppelte', () => {
		assert.equal(new Set(GELOESCHT_3383).size, 14);
	});

	for (const rel of GELOESCHT_3383) {
		test(`gelöscht (#3383): ${rel}`, () => {
			assert.equal(existsSync(pfad(rel)), false, `${rel} existiert noch`);
		});
	}

	test('keine Produktionsdatei importiert eine in #3383 gelöschte Datei (aufgelöster Modulpfad)', () => {
		const ziele = new Map<string, string>();
		for (const rel of GELOESCHT_3383) for (const z of importZiele(rel)) ziele.set(z, rel);
		const muster = /(?:from|import\s*\()\s*['"]([^'"]+)['"]/g;
		const funde: string[] = [];
		for (const rel of produktionsdateien()) {
			const text = readFileSync(pfad(rel), 'utf8');
			for (const m of text.matchAll(muster)) {
				const z = modulZiel(m[1], rel);
				if (z !== null && ziele.has(z)) funde.push(`${rel} -> ${ziele.get(z)}`);
			}
		}
		assert.deepEqual(funde, [], 'Produktions-Importe der in #3383 gelöschten Dateien');
	});

	test('keine Produktionsdatei importiert einen Basisnamen der #3383-Löschliste', () => {
		const namen = GELOESCHT_3383.map(basisname);
		const muster = new RegExp(`(?:from|import\\s*\\()\\s*['"][^'"]*/(${namen.map(escape).join('|')})(?:\\.svelte|\\.ts|\\.js)?['"]`, 'g');
		const funde: string[] = [];
		for (const rel of produktionsdateien()) {
			const text = readFileSync(pfad(rel), 'utf8');
			for (const m of text.matchAll(muster)) funde.push(`${rel} -> ${m[1]}`);
		}
		assert.deepEqual(funde, [], 'Produktions-Importe der Basisnamen aus #3383');
	});

	for (const rel of ERHALTEN_3383) {
		test(`erhalten (Regressionsschutz, heute grün): ${rel}`, () => {
			assert.equal(existsSync(pfad(rel)), true, `${rel} wurde mitgelöscht, wird aber noch gebraucht`);
		});
	}
});

// #3384 S4 (Spec rework_3384_waisen_s4.md, AC-1): 19 Waisen der Gruppe S4 gelöscht, dazu die Browser-Spec
// issue-1093-unit samt Config (importierte nur layoutPreviewRows.ts). RED heute: alle existieren noch.
// Importscan zweifach wie #3383; EinstellTabelle.svelte bleibt (Regressionsschutz).
const GELOESCHT_3384 = [
	'lib/components/compare/AddReportCard.svelte',
	'lib/components/compare/CreateGroupDialog.svelte',
	'lib/components/compare/LocationPreviewMap.svelte',
	'lib/components/compare/layoutPreviewRows.ts',
	'lib/components/compare/versandPropsAus.ts',
	'lib/components/compare/wetterMetrikenPropsAus.ts',
	'lib/components/edit/EditRouteSection.svelte',
	'lib/components/edit/EditWeatherSection.svelte',
	'lib/components/edit/WeatherSummaryCard.svelte',
	'lib/components/edit/weatherSummary.ts',
	'lib/components/mobile/DrawerGroup.svelte',
	'lib/components/mobile/DrawerItem.svelte',
	'lib/components/mobile/NavIcon.svelte',
	'lib/components/trip-detail/waypoints/WaypointPin.svelte',
	'lib/utils/alertMetricCatalogIds.ts',
	'lib/utils/horizonHelpers.ts',
	'lib/utils/naturalSort.ts',
	'lib/utils/rightColumn.ts',
	'lib/utils/weatherEmoji.ts'
];

/** Mitgelöschte Browser-Spec samt Config (relativ zu frontend/src, liegen unter frontend/e2e). */
const GELOESCHT_3384_E2E = ['../e2e/issue-1093-unit.spec.ts', '../e2e/playwright.1093.unit.config.ts'];

const ERHALTEN_3384 = ['lib/components/molecules/EinstellTabelle.svelte'];

describe('#3384 AC-1: Waisen S4 gelöscht, keine Importe, EinstellTabelle erhalten', () => {
	test('Löschliste #3384 hat genau 19 Einträge ohne Doppelte', () => {
		assert.equal(new Set(GELOESCHT_3384).size, 19);
		assert.equal(GELOESCHT_3384.length, 19);
	});

	for (const rel of [...GELOESCHT_3384, ...GELOESCHT_3384_E2E]) {
		test(`gelöscht (#3384): ${rel}`, () => {
			assert.equal(existsSync(pfad(rel)), false, `${rel} existiert noch`);
		});
	}

	test('keine Produktionsdatei importiert eine in #3384 gelöschte Datei (aufgelöster Modulpfad)', () => {
		const ziele = new Map<string, string>();
		for (const rel of GELOESCHT_3384) for (const z of importZiele(rel)) ziele.set(z, rel);
		const muster = /(?:from|import\s*\()\s*['"]([^'"]+)['"]/g;
		const funde: string[] = [];
		for (const rel of produktionsdateien()) {
			const text = readFileSync(pfad(rel), 'utf8');
			for (const m of text.matchAll(muster)) {
				const z = modulZiel(m[1], rel);
				if (z !== null && ziele.has(z)) funde.push(`${rel} -> ${ziele.get(z)}`);
			}
		}
		assert.deepEqual(funde, [], 'Produktions-Importe der in #3384 gelöschten Dateien');
	});

	test('keine Produktionsdatei importiert einen Basisnamen der #3384-Löschliste', () => {
		const namen = GELOESCHT_3384.map(basisname);
		const muster = new RegExp(`(?:from|import\\s*\\()\\s*['"][^'"]*/(${namen.map(escape).join('|')})(?:\\.svelte|\\.ts|\\.js)?['"]`, 'g');
		const funde: string[] = [];
		for (const rel of produktionsdateien()) {
			const text = readFileSync(pfad(rel), 'utf8');
			for (const m of text.matchAll(muster)) funde.push(`${rel} -> ${m[1]}`);
		}
		assert.deepEqual(funde, [], 'Produktions-Importe der Basisnamen aus #3384');
	});

	for (const rel of ERHALTEN_3384) {
		test(`erhalten (Regressionsschutz, heute grün): ${rel}`, () => {
			assert.equal(existsSync(pfad(rel)), true, `${rel} wurde mitgelöscht, wird aber noch gebraucht`);
		});
	}
});

// #3384 AC-5 (Finding F004 aus #3383): das gelöschte Bauteil wird nirgends mehr genannt, weder in Code
// noch in Kommentaren. Einzige feste Ausnahme ist diese Datei, die den Namen als Gelöscht-Eintrag führt.
const F004_WORT = /\bThresholdMetricRow\b/;
const F004_AUSNAHME = 'lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts';

/** Alle Quelldateien (.ts/.svelte/.js) unter frontend/src, inklusive Tests. */
function alleQuelldateien(): string[] {
	const aus: string[] = [];
	const lauf = (dir: string) => {
		for (const name of readdirSync(dir)) {
			const voll = join(dir, name);
			if (statSync(voll).isDirectory()) {
				if (name !== 'node_modules') lauf(voll);
			} else if (/\.(ts|svelte|js)$/.test(name)) aus.push(relative(SRC, voll).split('\\').join('/'));
		}
	};
	lauf(SRC);
	return aus;
}

describe('#3384 AC-5 (F004): Wortscan auf das gelöschte Bauteil über frontend/src', () => {
	test('die Ausnahmedatei existiert (sonst wäre die Ausnahme verwaist)', () => {
		assert.equal(existsSync(pfad(F004_AUSNAHME)), true);
	});

	test('kein Treffer außerhalb der einen Ausnahmedatei', () => {
		const funde: string[] = [];
		for (const rel of alleQuelldateien()) {
			if (rel === F004_AUSNAHME) continue;
			readFileSync(pfad(rel), 'utf8')
				.split('\n')
				.forEach((zeile, i) => {
					if (F004_WORT.test(zeile)) funde.push(`${rel}:${i + 1}`);
				});
		}
		assert.deepEqual(funde, [], 'Verweise auf das gelöschte Bauteil');
	});
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
