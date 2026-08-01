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
const RIGHT_COLUMN_TS = join(here, '..', '..', '..', 'utils', 'rightColumn.ts');
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

describe('AC-7: rightColumn.ts hat die vier aufruferlosen Helfer verloren, getReportSchedule bleibt', () => {
	function parseRightColumn(): { sf: ts.SourceFile; src: string } {
		const src = readFileSync(RIGHT_COLUMN_TS, 'utf-8');
		return { sf: ts.createSourceFile(RIGHT_COLUMN_TS, src, ts.ScriptTarget.Latest, true), src };
	}

	function declaredNames(sf: ts.SourceFile): Set<string> {
		const names = new Set<string>();
		function visit(node: ts.Node): void {
			if (ts.isFunctionDeclaration(node) && node.name) names.add(node.name.text);
			if (ts.isVariableStatement(node)) {
				for (const decl of node.declarationList.declarations) {
					if (ts.isIdentifier(decl.name)) names.add(decl.name.text);
				}
			}
			if (ts.isInterfaceDeclaration(node)) names.add(node.name.text);
			ts.forEachChild(node, visit);
		}
		sf.forEachChild(visit);
		return names;
	}

	test('METRIC_LABELS, prettyLabel, getDefaultMetricsForProfile, getActiveMetrics sind nicht mehr deklariert', () => {
		const { sf } = parseRightColumn();
		const names = declaredNames(sf);
		const forbidden = ['METRIC_LABELS', 'prettyLabel', 'getDefaultMetricsForProfile', 'getActiveMetrics'];
		const stillPresent = forbidden.filter((n) => names.has(n));
		assert.deepEqual(
			stillPresent,
			[],
			`rightColumn.ts deklariert noch: ${stillPresent.join(', ')} — ihr einziger Aufrufer war die ` +
				'jetzt gelöschte Karte bzw. TripOverview.svelte (AC-7).'
		);
	});

	test('getReportSchedule und der Typ ReportSchedule sind weiterhin exportiert', () => {
		const { src } = parseRightColumn();
		// doc-compliance-test: Export-Vertrag der beiden weiter benötigten Symbole
		// (BriefingPreviewCard.svelte, TripHeader.svelte, TripEditView.svelte).
		assert.match(src, /export\s+function\s+getReportSchedule\s*\(/, 'export function getReportSchedule fehlt');
		assert.match(src, /export\s+interface\s+ReportSchedule\b/, 'export interface ReportSchedule fehlt');
	});
});
