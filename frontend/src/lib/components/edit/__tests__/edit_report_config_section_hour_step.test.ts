// Issue #1280 (Adversary-Nachtrag F003) — Stopgap: EditReportConfigSection.svelte
// ist eine zweite, unabhaengige Zeit-Eingabe-Komponente (nicht VTSchedulePlan),
// live erreichbar ueber den Anlege-Wizard (TripNewEditor.svelte:765,990).
// TripEditView.svelte und BriefingsTab.svelte importieren dieselbe Komponente,
// sind aber unrouted/nie gerendert (kein <TripEditView>/<BriefingsTab> in einem
// live erreichbaren Elternbaum) — der Anlege-Wizard ist der einzige lebendige
// Importer. Serverseitige Write-Normalisierung (internal/handler/trip.go,
// CreateTripHandler) bleibt die autoritative Instanz; step ist nur Komfort.
//
// Source-Inspection-Test (kein DOM-Rendering, keine Mocks) — Praezedenz:
// vt_schedule_plan_hour_step.test.ts.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/edit/__tests__/edit_report_config_section_hour_step.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const EDIT_REPORT_CONFIG_SECTION = join(here, '..', 'EditReportConfigSection.svelte');

/**
 * Extrahiert den kompletten <input ...> Tag-Block, der einen gegebenen
 * data-testid traegt (nicht-greedy bis zum schliessenden ">"), damit die
 * step-Pruefung wirklich AM Input haengt statt irgendwo im Datei-Text.
 */
function extractInputBlock(src: string, testid: string): string {
	const marker = `data-testid="${testid}"`;
	const markerIdx = src.indexOf(marker);
	assert.ok(markerIdx >= 0, `data-testid="${testid}" nicht gefunden`);
	const tagStart = src.lastIndexOf('<input', markerIdx);
	assert.ok(tagStart >= 0, `kein <input vor data-testid="${testid}" gefunden`);
	const tagEnd = src.indexOf('/>', tagStart);
	assert.ok(tagEnd >= 0, `kein schliessendes /> nach data-testid="${testid}" gefunden`);
	return src.slice(tagStart, tagEnd + 2);
}

describe('EditReportConfigSection.svelte begrenzt beide Zeitfelder auf volle Stunden (step=3600)', () => {
	test('EditReportConfigSection.svelte existiert', () => {
		assert.ok(existsSync(EDIT_REPORT_CONFIG_SECTION), 'EditReportConfigSection.svelte fehlt');
	});

	test('report-morning-time Input traegt step={3600}', () => {
		const src = readFileSync(EDIT_REPORT_CONFIG_SECTION, 'utf-8');
		const block = extractInputBlock(src, 'report-morning-time');
		assert.ok(
			/step=\{?3600\}?|step="3600"/.test(block),
			`report-morning-time-Input muss step=3600 (volle Stunde) tragen, aktueller Tag-Block:\n${block}`
		);
	});

	test('report-evening-time Input traegt step={3600}', () => {
		const src = readFileSync(EDIT_REPORT_CONFIG_SECTION, 'utf-8');
		const block = extractInputBlock(src, 'report-evening-time');
		assert.ok(
			/step=\{?3600\}?|step="3600"/.test(block),
			`report-evening-time-Input muss step=3600 (volle Stunde) tragen, aktueller Tag-Block:\n${block}`
		);
	});
});
