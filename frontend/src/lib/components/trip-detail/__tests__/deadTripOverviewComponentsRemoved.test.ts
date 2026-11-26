// TDD RED — Feature #1435 Etappe E3a: die vier seit Issue #487 toten
// Bauteile (fälschlich als "Reparatur"-Ziel benannt) samt zugehörigem toten
// E2E-Test müssen verschwinden, ebenso ihre vier Aufrufer-losen Helfer in
// `rightColumn.ts`.
// Spec: docs/specs/modules/feat_1435_e3a_uebersicht_wetter_block.md
// Implementation Details Punkt 4, AC-6, AC-7.
//
// RED heute: alle fünf Dateien existieren noch, `index.ts` exportiert noch
// TripOverview/WeatherMetricsPreviewCard, `rightColumn.ts` exportiert noch
// die vier zu entfernenden Symbole.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/trip-detail/__tests__/deadTripOverviewComponentsRemoved.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const here = dirname(fileURLToPath(import.meta.url));
const TRIP_DETAIL_DIR = join(here, '..');
const INDEX_TS = join(TRIP_DETAIL_DIR, 'index.ts');
const E2E_SPEC = join(here, '..', '..', '..', '..', '..', 'e2e', 'trip-detail-overview-right.spec.ts');

const DEAD_COMPONENT_PATHS = [
	join(TRIP_DETAIL_DIR, 'MetricsPreview.svelte'),
	join(TRIP_DETAIL_DIR, 'WeatherMetricsPreviewCard.svelte'),
	join(TRIP_DETAIL_DIR, 'WeatherMetricsPreviewCard.tokens.test.ts'),
	join(TRIP_DETAIL_DIR, 'TripOverview.svelte')
];

describe('AC-6: die vier toten Bauteile und der tote E2E-Test existieren nicht mehr', () => {
	for (const path of DEAD_COMPONENT_PATHS) {
		test(`${path.split('/').pop()} existiert nicht mehr`, () => {
			assert.equal(
				existsSync(path),
				false,
				`${path} existiert noch — dieses Bauteil ist seit Issue #487 nirgends mehr eingebunden ` +
					'und muss laut Spec gelöscht werden (AC-6).'
			);
		});
	}

	test('e2e/trip-detail-overview-right.spec.ts existiert nicht mehr', () => {
		assert.equal(
			existsSync(E2E_SPEC),
			false,
			'Der E2E-Test prüft right-card-*-Testids, die nur in der gelöschten Karte existierten (AC-6).'
		);
	});

	test('trip-detail/index.ts exportiert TripOverview und WeatherMetricsPreviewCard nicht mehr', () => {
		const src = readFileSync(INDEX_TS, 'utf-8');
		const sf = ts.createSourceFile(INDEX_TS, src, ts.ScriptTarget.Latest, true);
		const referencesRemovedNames: string[] = [];
		sf.forEachChild((node) => {
			if (ts.isExportDeclaration(node)) {
				const text = node.getText(sf);
				if (/\bTripOverview\b/.test(text)) referencesRemovedNames.push('TripOverview');
				if (/\bWeatherMetricsPreviewCard\b/.test(text)) referencesRemovedNames.push('WeatherMetricsPreviewCard');
			}
		});
		assert.deepEqual(
			referencesRemovedNames,
			[],
			`trip-detail/index.ts enthält noch Export-Referenzen auf gelöschte Bauteile: ${referencesRemovedNames.join(', ')} (AC-6).`
		);
	});
});

// #1743 (Spec feat_1743_reiter_aufraeumen §10, AC-28/AC-33): Totcode der Briefing-Vorschau entfaellt.
const DEAD_1743 = [
	join(TRIP_DETAIL_DIR, 'PreviewCard.svelte'),
	join(TRIP_DETAIL_DIR, 'BriefingPreviewCard.svelte'),
	join(TRIP_DETAIL_DIR, '..', 'shared', 'layout-tab', 'LTComparePreview.svelte'),
	join(TRIP_DETAIL_DIR, '..', 'shared', 'PreviewTab.svelte'),
	join(TRIP_DETAIL_DIR, '..', 'shared', 'previewLoader.ts')
];

describe('#1743: Briefing-Vorschau-Totcode existiert nicht mehr', () => {
	for (const path of DEAD_1743) {
		test(`${path.split('/').pop()} existiert nicht mehr`, () => {
			assert.equal(existsSync(path), false, `${path} existiert noch — Briefing-Vorschau entfaellt ersatzlos (#1743).`);
		});
	}

	test('trip-detail/index.ts exportiert PreviewCard und BriefingPreviewCard nicht mehr', () => {
		const src = readFileSync(INDEX_TS, 'utf-8');
		const sf = ts.createSourceFile(INDEX_TS, src, ts.ScriptTarget.Latest, true);
		const reste: string[] = [];
		sf.forEachChild((node) => {
			if (ts.isExportDeclaration(node)) {
				const text = node.getText(sf);
				for (const name of ['PreviewCard', 'BriefingPreviewCard']) {
					if (new RegExp(`\\b${name}\\b`).test(text)) reste.push(name);
				}
			}
		});
		assert.deepEqual(reste, [], `trip-detail/index.ts exportiert noch: ${reste.join(', ')}`);
	});
});

// #3384 S4: Block „AC-7: rightColumn.ts …“ mit der Waise utils/rightColumn.ts gelöscht (Lösch-Nachweis
// in trip_pfad_altfeld_loeschnachweis_3297.test.ts, GELOESCHT_3384).
