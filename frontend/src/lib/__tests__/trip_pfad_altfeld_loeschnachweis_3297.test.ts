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

// #3385 S3 (Spec rework_3385_waisen_s3.md, AC-1/AC-7): 7 Waisen der Gruppe S3 (versand-tab) gelöscht.
// RED heute: alle 7 existieren, Tests und der Prüfstand f6 importieren oder lesen sie.
// Importscan über frontend/src UND frontend/e2e, alle Dateien inklusive Tests (Kommentare ausgenommen):
// kein Import-/Export-Spezifizierer, kein dynamisches import() und keine Pfad-Zeichenkette (auch in
// join/resolve), die auf einen der 7 Basisnamen (mit oder ohne Endung) zeigt. Einzige Ausnahme ist diese
// Datei, die die Pfade führt. EinstellTabelle.svelte und die lebenden versand-tab-Module bleiben.
const GELOESCHT_3385 = [
	'lib/components/shared/versand-tab/VTBriefingChannels.svelte',
	'lib/components/shared/versand-tab/VTLaufzeitRoute.svelte',
	'lib/components/shared/versand-tab/VTLaufzeitVergleich.svelte',
	'lib/components/shared/versand-tab/VTNextBriefing.svelte',
	'lib/components/shared/versand-tab/VTSchedulePlan.svelte',
	'lib/components/shared/versand-tab/channelContactLabel.ts',
	'lib/components/shared/versand-tab/vtBriefingChannelsText.ts'
];

const ERHALTEN_3385 = [
	'lib/components/molecules/EinstellTabelle.svelte',
	'lib/components/shared/versand-tab/channelConnectionStatus.ts',
	'lib/components/shared/versand-tab/premiumSmsChannelState.ts',
	'lib/components/shared/versand-tab/sendTargetLabel.ts',
	'lib/components/shared/versand-tab/nextBriefingText.ts',
	'lib/components/shared/versand-tab/nextBriefingLoad.ts',
	'lib/components/shared/versand-tab/naechstesBriefingLader.svelte.ts',
	'lib/components/shared/versand-tab/reportConfigPayload.ts',
	'lib/components/shared/versand-tab/mergeReportConfig.ts',
	'lib/components/shared/versand-tab/dayWindowClamp.ts'
];

const SCAN_3385_AUSNAHME = 'lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts';

/** Alle Quelldateien unter frontend/src und frontend/e2e (inklusive Tests), relativ zu frontend/src. */
function scanDateien3385(): string[] {
	const aus: string[] = [];
	const lauf = (dir: string) => {
		if (!existsSync(dir)) return;
		for (const name of readdirSync(dir)) {
			const voll = join(dir, name);
			if (statSync(voll).isDirectory()) {
				if (name !== 'node_modules' && name !== 'test-results' && name !== 'playwright-report') lauf(voll);
			} else if (/\.(ts|js|mjs|svelte)$/.test(name)) aus.push(relative(SRC, voll).split('\\').join('/'));
		}
	};
	lauf(SRC);
	lauf(join(SRC, '..', 'e2e'));
	return aus;
}

/**
 * Quelltext ohne Kommentare, zeilenweise: Kommentarzeilen (`//`, `*`, `/*`, `<!--`) entfallen, ein
 * Zeilenende-Kommentar ` // …` wird abgeschnitten. Bewusst kein Block-Regex über die ganze Datei: Glob-
 * Zeichenketten wie `'**\/*.ts'` enthalten `/*` und würden sonst echten Code bis zum nächsten `*\/` schlucken.
 */
function ohneKommentare(text: string): string {
	return text
		.split('\n')
		.filter((z) => !/^\s*(\/\/|\/\*|\*|<!--)/.test(z))
		.map((z) => z.replace(/\s\/\/\s.*$/, ''))
		.join('\n');
}

/**
 * Funde (`datei -> Basisname`) auf die #3385-Löschliste: (1) Import-/Export-Spezifizierer und dynamisches
 * import(); (2) Pfad-Zeichenketten, die auf eine gelöschte Datei zeigen (letztes Pfadsegment = Basisname
 * mit Endung, oder Basisname ohne Endung mit vorangestelltem Verzeichnis), wo immer sie stehen, also auch
 * in join/resolve/path.join und in Lade-Helfern wie imp('src/…/X.svelte'). Bloße Namen ohne Endung und
 * ohne Pfad (z. B. die Sperrliste VERBOTEN in s3b2795_zustellung_struktur.test.ts) sind kein Pfad.
 */
function funde3385(): string[] {
	const namen = new Set(GELOESCHT_3385.map(basisname));
	const trifftSpez = (spez: string) => {
		const b = (spez.split('/').pop() ?? '').replace(/\.(svelte|ts|js)$/, '');
		return namen.has(b) ? b : null;
	};
	const trifftPfad = (s: string) => {
		const letzt = s.split('/').pop() ?? '';
		const mitEndung = /\.(svelte|ts|js)$/.test(letzt);
		const b = letzt.replace(/\.(svelte|ts|js)$/, '');
		return namen.has(b) && (mitEndung || s.includes('/')) ? b : null;
	};
	const spezifizierer = /(?:\bfrom\s*|\bimport\s*\(\s*|\bimport\s+)['"`]([^'"`]+)['"`]/g;
	const zeichenkette = /['"`]([^'"`\n]+)['"`]/g;
	const funde: string[] = [];
	for (const rel of scanDateien3385()) {
		if (rel === SCAN_3385_AUSNAHME) continue;
		const text = ohneKommentare(readFileSync(pfad(rel), 'utf8'));
		for (const m of text.matchAll(spezifizierer)) {
			const b = trifftSpez(m[1]);
			if (b) funde.push(`${rel} -> ${b} (Import/Export)`);
		}
		for (const z of text.split('\n')) {
			for (const s of z.matchAll(zeichenkette)) {
				const b = trifftPfad(s[1]);
				if (b) funde.push(`${rel} -> ${b} (Pfad)`);
			}
		}
	}
	return funde;
}

describe('#3385 AC-1/AC-7: Waisen S3 gelöscht, kein Import und kein Pfad mehr, Nachbarn erhalten', () => {
	test('Löschliste #3385 hat genau 7 Einträge ohne Doppelte', () => {
		assert.equal(new Set(GELOESCHT_3385).size, 7);
		assert.equal(GELOESCHT_3385.length, 7);
	});

	for (const rel of GELOESCHT_3385) {
		test(`gelöscht (#3385): ${rel}`, () => {
			assert.equal(existsSync(pfad(rel)), false, `${rel} existiert noch`);
		});
	}

	test('die Ausnahmedatei des Importscans existiert (sonst wäre die Ausnahme verwaist)', () => {
		assert.equal(existsSync(pfad(SCAN_3385_AUSNAHME)), true);
	});

	test('Importscan frontend/src und frontend/e2e: kein Spezifizierer und keine Pfad-Zeichenkette auf die #3385-Löschliste', () => {
		const funde = funde3385();
		assert.deepEqual(funde, [], `Verweise auf die in #3385 gelöschten Dateien:\n${funde.join('\n')}`);
	});

	for (const rel of ERHALTEN_3385) {
		test(`erhalten (Regressionsschutz, heute grün): ${rel}`, () => {
			assert.equal(existsSync(pfad(rel)), true, `${rel} wurde mitgelöscht, wird aber noch gebraucht`);
		});
	}
});

// #3389 (Spec rework_3389_tote_exporte.md, AC-1/AC-2/AC-3/AC-6): Lösch-Nachweis auf EXPORTEBENE.
// Der Waisen-Wächter erkennt nur ganze Dateien; die beiden Module bleiben lebend (fünf Hydrations-
// Funktionen haben Produktionsaufrufer), ihre 21 toten Exporte samt den zwei nur noch internen Typen
// `VersandSnapshot`/`LayoutSnapshot` sind gelöscht. RED heute: alle 23 Namen existieren, die 21
// Testdateien und der Prüfstand bestehen, die Exportmenge ist zu groß.
const MODUL_VERSAND_3389 = 'lib/components/shared/versandVergleichSpeicherung.ts';
const MODUL_WETTER_3389 = 'lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts';

const GELOESCHT_3389: Record<string, string[]> = {
	[MODUL_VERSAND_3389]: [
		'versandSnapshotAus',
		'baueVersandNutzlast',
		'flushPendingVersandSave',
		'rollbackVersandSnapshot',
		'versandVergleichSpeicherungAktiv',
		'erstelleVersandVergleichSpeicherung',
		'versandZustandsBruecke',
		'VersandHydrationTarget',
		'VersandVergleichSpeicherungOptionen',
		'VersandSnapshot'
	],
	[MODUL_WETTER_3389]: [
		'flushPendingLayoutSave',
		'rollbackLayoutSnapshot',
		'WetterMetrikenLayoutSnapshot',
		'WetterMetrikenZustand',
		'wetterMetrikenSnapshotAus',
		'baueWetterMetrikenNutzlast',
		'flushPendingWetterMetrikenSave',
		'rollbackWetterMetrikenSnapshot',
		'WetterMetrikenVergleichSpeicherungOptionen',
		'erstelleWetterMetrikenVergleichSpeicherung',
		'wetterMetrikenVergleichSpeicherungAktiv',
		'wetterMetrikenZustandsBruecke',
		'LayoutSnapshot'
	]
};

const NAMEN_3389 = Object.values(GELOESCHT_3389).flat();

const LEBEND_3389: Record<string, string[]> = {
	[MODUL_VERSAND_3389]: ['hydrateVersandFieldsFromPreset'],
	[MODUL_WETTER_3389]: [
		'hydrateDayWindowFromPreset',
		'hydrateWeatherMetricsFromPreset',
		'hydrateLayoutFieldsFromPreset',
		'wetterMetrikenHydrationAbgeschlossen'
	]
};

/** Produktionsaufrufer der fünf lebenden Exporte (Schutz gegen „aus Versehen mitgelöscht“). */
const AUFRUFER_3389: Record<string, string[]> = {
	hydrateVersandFieldsFromPreset: [
		'lib/components/compare/CompareTabs.svelte',
		'lib/components/compare-new/compareNewVorlage.ts'
	],
	hydrateDayWindowFromPreset: [
		'lib/components/compare/CompareTabs.svelte',
		'lib/components/compare-new/compareNewVorlage.ts'
	],
	hydrateWeatherMetricsFromPreset: [
		'lib/components/compare/CompareTabs.svelte',
		'lib/components/compare/compareHubHydration.ts'
	],
	hydrateLayoutFieldsFromPreset: [
		'lib/components/compare/CompareTabs.svelte',
		'lib/components/compare-new/compareNewVorlage.ts'
	],
	wetterMetrikenHydrationAbgeschlossen: ['lib/components/compare/CompareTabs.svelte']
};

const GELOESCHTE_DATEIEN_3389 = [
	'lib/components/shared/__tests__/versand_vergleich_speichert_selbst.test.ts',
	'lib/components/shared/__tests__/versand_vergleich_konflikt_nochmal_speichern.test.ts',
	'lib/components/shared/__tests__/versand_vergleich_flush_vor_pausieren.test.ts',
	'lib/components/shared/__tests__/versand_nutzlast_verliert_keine_daten.test.ts',
	'lib/components/shared/__tests__/versand_nutzlast_reicht_keepalive_durch.test.ts',
	'lib/components/shared/__tests__/versand_enddatum_ohne_ereignis_bleibt_wirksam.test.ts',
	'lib/components/shared/__tests__/versand_speicherung_nur_im_vergleich_hub.test.ts',
	'lib/components/shared/__tests__/versand_vergleich_reiterwechsel_verliert_nichts.test.ts',
	'lib/components/compare/__tests__/compare_hub_layout_save.test.ts',
	'lib/components/compare/__tests__/compare_hub_layout_rollback.test.ts',
	'lib/components/compare/__tests__/compare_feldsatz_roundtrip_datenerhalt.test.ts',
	'lib/components/shared/weather-metrics-tab/__tests__/wetter_metriken_drei_stille_gesten_bleiben_wirksam.test.ts',
	'lib/components/shared/weather-metrics-tab/__tests__/wetter_metriken_intra_gesture_kollision.test.ts',
	'lib/components/shared/weather-metrics-tab/__tests__/wetter_metriken_nutzlast_reicht_keepalive_durch.test.ts',
	'lib/components/shared/weather-metrics-tab/__tests__/wetter_metriken_nutzlast_verliert_keine_daten.test.ts',
	'lib/components/shared/weather-metrics-tab/__tests__/wetter_metriken_speicherung_nur_im_vergleich_hub.test.ts',
	'lib/components/shared/weather-metrics-tab/__tests__/wetter_metriken_vergleich_flush_vor_pausieren.test.ts',
	'lib/components/shared/weather-metrics-tab/__tests__/wetter_metriken_vergleich_konflikt_nochmal_speichern.test.ts',
	'lib/components/shared/weather-metrics-tab/__tests__/wetter_metriken_vergleich_speichert_einmal.test.ts',
	'lib/components/shared/weather-metrics-tab/__tests__/wetter_metriken_reiterwechsel_verliert_nichts.test.ts',
	'lib/components/shared/weather-metrics-tab/__tests__/f006_zustellung_schreibt_keine_wetterfelder.test.ts'
];

const GELOESCHTER_PRUEFSTAND_3389 = 'lib/components/shared/weather-metrics-tab/__tests__/wetterMetrikenVergleichPruefstand.ts';

const SCAN_3389_AUSNAHME = 'lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts';

/**
 * Alle exportierten Namen eines Quelltexts (Kommentare ausgenommen): `export [async] function|const|let|
 * class|interface|type|enum <Name>` und `export { a, b as c }` (gezählt wird der nach außen sichtbare Name).
 */
function exporte3389(text: string): string[] {
	const code = ohneKommentare(text);
	const namen = new Set<string>();
	const dekl =
		/\bexport\s+(?:declare\s+)?(?:default\s+)?(?:async\s+)?(?:function\*?|const|let|var|class|interface|type|enum)\s+([A-Za-z_$][\w$]*)/g;
	for (const m of code.matchAll(dekl)) namen.add(m[1]);
	for (const m of code.matchAll(/\bexport\s+(?:type\s+)?\{([^}]*)\}/g)) {
		for (const teil of m[1].split(',')) {
			const t = teil.trim().replace(/^type\s+/, '');
			if (!t) continue;
			const alias = t.split(/\s+as\s+/);
			namen.add((alias[1] ?? alias[0]).trim());
		}
	}
	return [...namen].sort();
}

/** Wortgenaue Funde (`datei:zeile -> Name`) der 23 Namen in einem Quelltext ohne Kommentare. */
function wortFunde3389(rel: string, text: string): string[] {
	const funde: string[] = [];
	const muster = NAMEN_3389.map((n) => ({ n, re: new RegExp(`\\b${escape(n)}\\b`) }));
	ohneKommentare(text)
		.split('\n')
		.forEach((zeile, i) => {
			for (const { n, re } of muster) if (re.test(zeile)) funde.push(`${rel}:${i + 1} -> ${n}`);
		});
	return funde;
}

describe('#3389 AC-1/AC-2/AC-3/AC-6: tote Exporte gelöscht, Exportmenge genau die lebenden Hydrationen', () => {
	test('Löschliste #3389 hat genau 23 Namen (21 tote Exporte + VersandSnapshot + LayoutSnapshot) ohne Doppelte', () => {
		assert.equal(NAMEN_3389.length, 23);
		assert.equal(new Set(NAMEN_3389).size, 23);
		assert.equal(GELOESCHTE_DATEIEN_3389.length, 21);
		assert.equal(new Set(GELOESCHTE_DATEIEN_3389).size, 21);
	});

	test('Dateien gelöscht: die 21 Testdateien und der Prüfstand wetterMetrikenVergleichPruefstand.ts existieren nicht', () => {
		const vorhanden = [...GELOESCHTE_DATEIEN_3389, GELOESCHTER_PRUEFSTAND_3389].filter((rel) => existsSync(pfad(rel)));
		assert.deepEqual(vorhanden, [], `existieren noch:\n${vorhanden.join('\n')}`);
	});

	for (const modul of [MODUL_VERSAND_3389, MODUL_WETTER_3389]) {
		test(`Exportmenge ${basisname(modul)}: genau die lebenden Hydrations-Funktionen`, () => {
			assert.equal(existsSync(pfad(modul)), true, `${modul} muss bestehen bleiben`);
			const ist = exporte3389(readFileSync(pfad(modul), 'utf8'));
			assert.deepEqual(ist, [...LEBEND_3389[modul]].sort(), `Exporte von ${modul}`);
		});
	}

	test('die Ausnahmedatei des Wortscans existiert (sonst wäre die Ausnahme verwaist)', () => {
		assert.equal(existsSync(pfad(SCAN_3389_AUSNAHME)), true);
	});

	test('Wortscan frontend/src und frontend/e2e: keiner der 23 Namen kommt außerhalb dieser Datei im Code vor', () => {
		const funde: string[] = [];
		for (const rel of scanDateien3385()) {
			if (rel === SCAN_3389_AUSNAHME) continue;
			funde.push(...wortFunde3389(rel, readFileSync(pfad(rel), 'utf8')));
		}
		assert.deepEqual(funde, [], `Verweise auf die in #3389 gelöschten Namen:\n${funde.join('\n')}`);
	});

	for (const [name, dateien] of Object.entries(AUFRUFER_3389)) {
		test(`Aufrufer vorhanden (Regressionsschutz, heute grün): ${name}`, () => {
			for (const rel of dateien) {
				const code = ohneKommentare(readFileSync(pfad(rel), 'utf8'));
				assert.match(code, new RegExp(`\\b${escape(name)}\\b`), `${rel} nutzt ${name} nicht mehr`);
			}
		});
	}

	// Selbstnachweis (AC-3): der Wächter auf eingebetteten Mini-Quellen, ohne Plattendateien.
	test('Selbstnachweis (a): ein wieder eingeführtes export function erstelleVersandVergleichSpeicherung wird gemeldet', () => {
		const quelle = 'export function hydrateVersandFieldsFromPreset() {}\nexport function erstelleVersandVergleichSpeicherung() {}\n';
		const ist = exporte3389(quelle);
		assert.notDeepEqual(ist, LEBEND_3389[MODUL_VERSAND_3389]);
		assert.ok(ist.includes('erstelleVersandVergleichSpeicherung'));
		assert.ok(wortFunde3389('mini.ts', quelle).some((f) => f.endsWith('-> erstelleVersandVergleichSpeicherung')));
	});

	test('Selbstnachweis (b): ein Name nur in einem // oder * Kommentar ist kein Fund', () => {
		const quelle = [
			'// früher: erstelleVersandVergleichSpeicherung',
			'/**',
			' * wetterMetrikenSnapshotAus war hier',
			' */',
			'const x = 1; // flushPendingLayoutSave ist weg',
			'export function hydrateVersandFieldsFromPreset() {}'
		].join('\n');
		assert.deepEqual(wortFunde3389('mini.ts', quelle), []);
		assert.deepEqual(exporte3389(quelle), ['hydrateVersandFieldsFromPreset']);
	});

	test('Selbstnachweis (c): export const neuerExport erscheint als zusätzlicher Export', () => {
		const quelle = 'export function hydrateVersandFieldsFromPreset() {}\nexport const neuerExport = 1;\n';
		assert.deepEqual(exporte3389(quelle), ['hydrateVersandFieldsFromPreset', 'neuerExport']);
		assert.deepEqual(exporte3389('const a = 1;\nexport { a as neuerExport };\n'), ['neuerExport']);
	});

	test('Selbstnachweis (d): ein Import eines gelöschten Namens in einer anderen Datei wird gemeldet', () => {
		const quelle = "import { wetterMetrikenSnapshotAus } from '../weatherMetricsCompareSave.ts';\n";
		assert.deepEqual(wortFunde3389('andere.test.ts', quelle), ['andere.test.ts:1 -> wetterMetrikenSnapshotAus']);
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
