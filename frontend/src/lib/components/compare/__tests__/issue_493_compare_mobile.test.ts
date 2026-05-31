// TDD RED — Issue #493: Mobile-Responsive Compare (Block E, Epic #485)
//
// Spec: docs/specs/modules/issue_493_compare_mobile.md
//
// Source-Inspection-Tests: prüfen Soll-Zustand nach Implementation.
//
// RED-Erwartung (vor Implementation):
//   AC-1a: FAIL — MCompareActionSheet.svelte existiert nicht
//   AC-1b: FAIL — mobile/index.ts exportiert MCompareActionSheet nicht
//   AC-2: FAIL — /compare/+page.svelte hat keinen desktop:hidden mobilen Stack
//   AC-3: FAIL — /compare/[id]/+page.svelte existiert nicht
//   AC-4: FAIL — /compare/[id]/+page.svelte hat keinen desktop:hidden mobilen Block
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_493_compare_mobile.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const COMPARE_DIR   = dirname(fileURLToPath(import.meta.url)) + '/..';
const MOBILE_DIR    = join(COMPARE_DIR, '..', 'mobile');
const ROUTES_CMP    = join(COMPARE_DIR, '..', '..', '..', 'routes', 'compare');
const ROUTES_CMP_ID = join(ROUTES_CMP, '[id]');

const ACTION_SHEET  = join(MOBILE_DIR, 'MCompareActionSheet.svelte');
const MOBILE_INDEX  = join(MOBILE_DIR, 'index.ts');
const CMP_PAGE      = join(ROUTES_CMP, '+page.svelte');
const DETAIL_PAGE   = join(ROUTES_CMP_ID, '+page.svelte');

// ── AC-1: MCompareActionSheet ─────────────────────────────────────────────────

describe('AC-1: MCompareActionSheet.svelte existiert und wird exportiert', () => {
	test('MCompareActionSheet.svelte existiert in mobile/', () => {
		assert.ok(
			existsSync(ACTION_SHEET),
			'MCompareActionSheet.svelte fehlt in frontend/src/lib/components/mobile/'
		);
	});

	test('mobile/index.ts exportiert MCompareActionSheet', () => {
		const src = readFileSync(MOBILE_INDEX, 'utf-8');
		assert.match(
			src,
			/MCompareActionSheet/,
			'mobile/index.ts exportiert MCompareActionSheet nicht — Export-Eintrag fehlt'
		);
	});

	test('MCompareActionSheet.svelte nutzt Sheet als Basis (snap="half")', () => {
		assert.ok(existsSync(ACTION_SHEET), 'MCompareActionSheet.svelte fehlt');
		const src = readFileSync(ACTION_SHEET, 'utf-8');
		assert.match(
			src,
			/Sheet/,
			'MCompareActionSheet.svelte importiert Sheet nicht — Bottom-Sheet-Basis fehlt'
		);
	});

	test('MCompareActionSheet.svelte nutzt compareActions()', () => {
		assert.ok(existsSync(ACTION_SHEET), 'MCompareActionSheet.svelte fehlt');
		const src = readFileSync(ACTION_SHEET, 'utf-8');
		assert.match(
			src,
			/compareActions/,
			'MCompareActionSheet.svelte verwendet compareActions() nicht — Aktionsliste fehlt'
		);
	});

	test('MCompareActionSheet.svelte hat 52px Tap-Target für Aktions-Zeilen', () => {
		assert.ok(existsSync(ACTION_SHEET), 'MCompareActionSheet.svelte fehlt');
		const src = readFileSync(ACTION_SHEET, 'utf-8');
		assert.match(
			src,
			/52px|min-height.*52|min-h-\[52/,
			'MCompareActionSheet.svelte hat kein 52px-Tap-Target für Aktions-Zeilen'
		);
	});
});

// ── AC-2: /compare mobiler Kachel-Stack ──────────────────────────────────────

describe('AC-2: /compare/+page.svelte hat mobilen Kachel-Stack', () => {
	test('/compare/+page.svelte enthält desktop:hidden-Block für mobilen Stack', () => {
		const src = readFileSync(CMP_PAGE, 'utf-8');
		assert.match(
			src,
			/desktop:hidden/,
			'/compare/+page.svelte hat keinen desktop:hidden-Block — mobiler Kachel-Stack fehlt'
		);
	});

	test('/compare/+page.svelte rendert CompareTile mit dense=true im mobilen Block', () => {
		const src = readFileSync(CMP_PAGE, 'utf-8');
		assert.match(
			src,
			/dense.*true|dense={true}/,
			'/compare/+page.svelte hat kein dense=true auf CompareTile für mobile Ansicht'
		);
	});

	test('/compare/+page.svelte hat 44px Tap-Target im mobilen Stack (min-h-[44px])', () => {
		const src = readFileSync(CMP_PAGE, 'utf-8');
		assert.match(
			src,
			/min-h-\[44px\]|min-height.*44/,
			'/compare/+page.svelte hat kein 44px-Tap-Target im mobilen Stack'
		);
	});
});

// ── AC-3: /compare/[id] Desktop-Layout vorhanden (Voraussetzung) ─────────────

describe('AC-3-prereq: /compare/[id]/+page.svelte als Basis vorhanden', () => {
	test('/compare/[id]/+page.svelte existiert', () => {
		assert.ok(
			existsSync(DETAIL_PAGE),
			'/compare/[id]/+page.svelte fehlt — Issue #491 muss zuerst implementiert werden'
		);
	});
});

// ── AC-3: Bottom-Sheet auf Detail-Seite ──────────────────────────────────────

describe('AC-3: ⋯-Button öffnet Bottom-Sheet auf /compare/[id]', () => {
	test('/compare/[id]/+page.svelte importiert MCompareActionSheet', () => {
		assert.ok(existsSync(DETAIL_PAGE), '/compare/[id]/+page.svelte fehlt');
		const src = readFileSync(DETAIL_PAGE, 'utf-8');
		assert.match(
			src,
			/MCompareActionSheet/,
			'MCompareActionSheet wird in /compare/[id]/+page.svelte nicht importiert'
		);
	});

	test('/compare/[id]/+page.svelte hat actionSheetOpen State', () => {
		assert.ok(existsSync(DETAIL_PAGE), '/compare/[id]/+page.svelte fehlt');
		const src = readFileSync(DETAIL_PAGE, 'utf-8');
		assert.match(
			src,
			/actionSheetOpen/,
			'/compare/[id]/+page.svelte hat kein actionSheetOpen-State für Bottom-Sheet'
		);
	});
});

// ── AC-4: /compare/[id] mobiles Layout ───────────────────────────────────────

describe('AC-4: /compare/[id]/+page.svelte hat mobilen Render-Pfad', () => {
	test('/compare/[id]/+page.svelte hat desktop:hidden-Block für mobiles Layout', () => {
		assert.ok(existsSync(DETAIL_PAGE), '/compare/[id]/+page.svelte fehlt');
		const src = readFileSync(DETAIL_PAGE, 'utf-8');
		assert.match(
			src,
			/desktop:hidden/,
			'/compare/[id]/+page.svelte hat keinen desktop:hidden-Block — mobiler Render-Pfad fehlt'
		);
	});

	test('/compare/[id]/+page.svelte hat 2x2-Grid für Monitoring (grid-cols-2)', () => {
		assert.ok(existsSync(DETAIL_PAGE), '/compare/[id]/+page.svelte fehlt');
		const src = readFileSync(DETAIL_PAGE, 'utf-8');
		assert.match(
			src,
			/grid-cols-2/,
			'/compare/[id]/+page.svelte hat kein grid-cols-2 für 2×2-Monitoring-Grid'
		);
	});

	test('/compare/[id]/+page.svelte hat 44px Back-Button in mobiler TopBar', () => {
		assert.ok(existsSync(DETAIL_PAGE), '/compare/[id]/+page.svelte fehlt');
		const src = readFileSync(DETAIL_PAGE, 'utf-8');
		assert.match(
			src,
			/min-h-\[44px\]|min-w-\[44px\]/,
			'/compare/[id]/+page.svelte hat kein 44px-Tap-Target für mobile TopBar-Buttons'
		);
	});

	test('/compare/[id]/+page.svelte hat ArrowLeft-Icon für Back-Navigation', () => {
		assert.ok(existsSync(DETAIL_PAGE), '/compare/[id]/+page.svelte fehlt');
		const src = readFileSync(DETAIL_PAGE, 'utf-8');
		assert.match(
			src,
			/ArrowLeft/,
			'/compare/[id]/+page.svelte hat kein ArrowLeft-Icon für Back-Navigation in mobiler TopBar'
		);
	});
});
