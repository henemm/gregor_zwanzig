// TDD RED — Issue #1280: Versandzeit-Eingabe auf volle Stunden begrenzen.
//
// Spec: docs/specs/modules/fix_1280_versandzeit_stunden_raster.md (AC-5)
//
// Source-Inspection-Test (kein DOM-Rendering, keine Mocks, kein Playwright —
// Praezedenz: shared/corridor-editor/corridorEditorMobile.test.ts,
// organisms/__tests__/list_table_unify.test.ts). Svelte-5-Komponenten sind
// ohne @testing-library/svelte (nicht in package.json) in diesem
// Test-Setup nicht mountbar; die tatsaechliche Browser-Wirkung von
// step={3600} wird laut Spec "Known Limitations" ergaenzend ueber die
// Server-Write-Normalisierung abgesichert (separate Go-Tests, siehe Spec).
//
// RED-Erwartung: VTSchedulePlan.svelte traegt aktuell KEIN step-Attribut auf
// den beiden Zeit-Inputs (Zeile 86 morning, Zeile 111 evening) — beide
// step-Assertions unten schlagen fehl, bis Phase 6 sie behebt.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/versand-tab/__tests__/vt_schedule_plan_hour_step.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const VT_SCHEDULE_PLAN = join(here, '..', 'VTSchedulePlan.svelte');
const VERSAND_TAB = join(here, '..', '..', 'VersandTab.svelte');

/**
 * Extrahiert den kompletten <input ...> Tag-Block, der einen gegebenen
 * data-testid traegt (nicht-greedy bis zum schliessenden ">"), damit die
 * step-Pruefung wirklich AM Input haengt statt irgendwo im Datei-Text.
 */
function extractInputBlock(src: string, testid: string): string {
	const marker = `data-testid="${testid}"`;
	const markerIdx = src.indexOf(marker);
	assert.ok(markerIdx >= 0, `data-testid="${testid}" nicht gefunden`);
	// Tag-Anfang vor dem Marker suchen.
	const tagStart = src.lastIndexOf('<input', markerIdx);
	assert.ok(tagStart >= 0, `kein <input vor data-testid="${testid}" gefunden`);
	const tagEnd = src.indexOf('/>', tagStart);
	assert.ok(tagEnd >= 0, `kein schliessendes /> nach data-testid="${testid}" gefunden`);
	return src.slice(tagStart, tagEnd + 2);
}

describe('AC-5: VTSchedulePlan.svelte begrenzt beide Zeitfelder auf volle Stunden (step=3600)', () => {
	test('VTSchedulePlan.svelte existiert (geteilte Komponente)', () => {
		assert.ok(existsSync(VT_SCHEDULE_PLAN), 'VTSchedulePlan.svelte fehlt');
	});

	test('report-morning-time Input traegt step={3600}', () => {
		const src = readFileSync(VT_SCHEDULE_PLAN, 'utf-8');
		const block = extractInputBlock(src, 'report-morning-time');
		assert.ok(
			/step=\{?3600\}?|step="3600"/.test(block),
			`report-morning-time-Input muss step=3600 (volle Stunde) tragen, aktueller Tag-Block:\n${block}`
		);
	});

	test('report-evening-time Input traegt step={3600}', () => {
		const src = readFileSync(VT_SCHEDULE_PLAN, 'utf-8');
		const block = extractInputBlock(src, 'report-evening-time');
		assert.ok(
			/step=\{?3600\}?|step="3600"/.test(block),
			`report-evening-time-Input muss step=3600 (volle Stunde) tragen, aktueller Tag-Block:\n${block}`
		);
	});

	// Trip/Compare-Teilungs-Invariante (CLAUDE.md): der Fix darf NICHT
	// dupliziert werden — es gibt genau EINEN Import-/Nutzungsort, der beide
	// Kontexte (context="route" implizit als Default, context="vergleich"
	// explizit) mit derselben Komponente bedient.
	test('VersandTab.svelte nutzt dieselbe VTSchedulePlan-Instanz fuer route UND vergleich (kein Duplikat)', () => {
		assert.ok(existsSync(VERSAND_TAB), 'VersandTab.svelte fehlt');
		const src = readFileSync(VERSAND_TAB, 'utf-8');
		const importCount = (src.match(/import VTSchedulePlan from '\.\/versand-tab\/VTSchedulePlan\.svelte'/g) || [])
			.length;
		assert.equal(importCount, 1, 'VTSchedulePlan darf nur EINMAL importiert werden (geteilte Komponente)');

		const usageCount = (src.match(/<VTSchedulePlan/g) || []).length;
		assert.equal(
			usageCount,
			2,
			'VTSchedulePlan muss fuer BEIDE Kontexte (route + vergleich) verwendet werden, keine eigene Kopie je Kontext'
		);
		assert.ok(
			src.includes('context="vergleich"'),
			'die vergleich-Verwendung muss context="vergleich" explizit setzen'
		);
	});
});
