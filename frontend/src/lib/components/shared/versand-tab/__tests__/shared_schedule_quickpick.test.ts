// TDD RED — Issue #1286: Quick-Pick-Chips wandern in die geteilte
// VTSchedulePlan (PO-Entscheidung 2026-07-17, überall verfügbar). Spec AC-3.
//
// RED-Erwartung: VTSchedulePlan.svelte trägt aktuell KEINE quickpick-Chips —
// schlägt fehl bis Phase 6.
//
// Source-Inspection-Test (kein DOM-Rendering, keine Mocks, kein Playwright —
// Praezedenz: vt_schedule_plan_hour_step.test.ts). Svelte-5-Komponenten sind
// ohne @testing-library/svelte (nicht in package.json) in diesem
// Test-Setup nicht mountbar.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/versand-tab/__tests__/shared_schedule_quickpick.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const VT_SCHEDULE_PLAN = join(here, '..', 'VTSchedulePlan.svelte');

/**
 * Extrahiert den kompletten <button ...>...</button> Block, der einen
 * gegebenen data-testid traegt, damit Verdrahtungs- und Wert-Pruefungen
 * wirklich AM Button haengen statt irgendwo im Datei-Text.
 */
function extractButtonBlock(src: string, testid: string): string {
	const marker = `data-testid="${testid}"`;
	const markerIdx = src.indexOf(marker);
	assert.ok(markerIdx >= 0, `data-testid="${testid}" nicht gefunden`);
	const tagStart = src.lastIndexOf('<button', markerIdx);
	assert.ok(tagStart >= 0, `kein <button vor data-testid="${testid}" gefunden`);
	const closeIdx = src.indexOf('</button>', markerIdx);
	assert.ok(closeIdx >= 0, `kein schliessendes </button> nach data-testid="${testid}" gefunden`);
	return src.slice(tagStart, closeIdx + '</button>'.length);
}

const QUICKPICK_TESTIDS = [
	'report-morning-quickpick-07',
	'report-morning-quickpick-18',
	'report-evening-quickpick-07',
	'report-evening-quickpick-18'
];

describe('AC-3: VTSchedulePlan.svelte traegt die Quick-Pick-Chips (geteilte Komponente)', () => {
	for (const testid of QUICKPICK_TESTIDS) {
		test(`Button mit data-testid="${testid}" existiert in VTSchedulePlan.svelte`, () => {
			const src = readFileSync(VT_SCHEDULE_PLAN, 'utf-8');
			assert.ok(
				src.includes(`data-testid="${testid}"`),
				`VTSchedulePlan.svelte muss einen Button mit data-testid="${testid}" tragen`
			);
		});
	}

	test('morning-quickpick-Buttons sind an onMorningTime verdrahtet (controlled, kein bind:)', () => {
		const src = readFileSync(VT_SCHEDULE_PLAN, 'utf-8');
		for (const testid of ['report-morning-quickpick-07', 'report-morning-quickpick-18']) {
			const block = extractButtonBlock(src, testid);
			assert.ok(
				block.includes('onMorningTime'),
				`Button-Block ${testid} muss den Callback onMorningTime referenzieren, aktueller Block:\n${block}`
			);
		}
	});

	test('evening-quickpick-Buttons sind an onEveningTime verdrahtet (controlled, kein bind:)', () => {
		const src = readFileSync(VT_SCHEDULE_PLAN, 'utf-8');
		for (const testid of ['report-evening-quickpick-07', 'report-evening-quickpick-18']) {
			const block = extractButtonBlock(src, testid);
			assert.ok(
				block.includes('onEveningTime'),
				`Button-Block ${testid} muss den Callback onEveningTime referenzieren, aktueller Block:\n${block}`
			);
		}
	});

	test('report-morning-quickpick-07 setzt 07:00', () => {
		const src = readFileSync(VT_SCHEDULE_PLAN, 'utf-8');
		const block = extractButtonBlock(src, 'report-morning-quickpick-07');
		assert.ok(block.includes('07:00'), `Block muss 07:00 setzen, aktueller Block:\n${block}`);
	});

	test('report-morning-quickpick-18 setzt 18:00', () => {
		const src = readFileSync(VT_SCHEDULE_PLAN, 'utf-8');
		const block = extractButtonBlock(src, 'report-morning-quickpick-18');
		assert.ok(block.includes('18:00'), `Block muss 18:00 setzen, aktueller Block:\n${block}`);
	});

	test('report-evening-quickpick-07 setzt 07:00', () => {
		const src = readFileSync(VT_SCHEDULE_PLAN, 'utf-8');
		const block = extractButtonBlock(src, 'report-evening-quickpick-07');
		assert.ok(block.includes('07:00'), `Block muss 07:00 setzen, aktueller Block:\n${block}`);
	});

	test('report-evening-quickpick-18 setzt 18:00', () => {
		const src = readFileSync(VT_SCHEDULE_PLAN, 'utf-8');
		const block = extractButtonBlock(src, 'report-evening-quickpick-18');
		assert.ok(block.includes('18:00'), `Block muss 18:00 setzen, aktueller Block:\n${block}`);
	});
});
