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

// Issue #2278: MCompareActionSheet ist im geteilten SubscriptionActionSheet aufgegangen (beide Arten).
const ACTION_SHEET  = join(MOBILE_DIR, 'SubscriptionActionSheet.svelte');
const CMP_PAGE      = join(ROUTES_CMP, '+page.svelte');
const DETAIL_PAGE   = join(ROUTES_CMP_ID, '+page.svelte');

// ── AC-1: SubscriptionActionSheet ─────────────────────────────────────────────

describe('AC-1: SubscriptionActionSheet.svelte existiert', () => {
	test('SubscriptionActionSheet.svelte existiert in mobile/', () => {
		assert.ok(
			existsSync(ACTION_SHEET),
			'SubscriptionActionSheet.svelte fehlt in frontend/src/lib/components/mobile/'
		);
	});

	test('SubscriptionActionSheet.svelte nutzt Sheet als Basis (snap="half")', () => {
		assert.ok(existsSync(ACTION_SHEET), 'SubscriptionActionSheet.svelte fehlt');
		const src = readFileSync(ACTION_SHEET, 'utf-8');
		assert.match(
			src,
			/Sheet/,
			'SubscriptionActionSheet.svelte importiert Sheet nicht — Bottom-Sheet-Basis fehlt'
		);
	});

	test('SubscriptionActionSheet.svelte hat 52px Tap-Target für Aktions-Zeilen', () => {
		assert.ok(existsSync(ACTION_SHEET), 'SubscriptionActionSheet.svelte fehlt');
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

	test('/compare/+page.svelte rendert SubscriptionCard mit dense im mobilen Block', () => {
		const src = readFileSync(CMP_PAGE, 'utf-8');
		assert.match(
			src,
			/<SubscriptionCard[^>]*\bdense\b/,
			'/compare/+page.svelte hat kein dense auf SubscriptionCard für mobile Ansicht'
		);
	});

	// Das 44px-Tap-Target der mobilen Karte steckt im geteilten Baustein (Menue-Knopf 44x44).
	test('SubscriptionCard hat 44px Tap-Target für den Menü-Knopf (dense)', () => {
		const src = readFileSync(join(COMPARE_DIR, '..', 'organisms', 'SubscriptionCard.svelte'), 'utf-8');
		assert.match(src, /style:height="44px"/, 'SubscriptionCard: Menü-Knopf ohne 44px-Tap-Target');
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
	test('/compare/[id]/+page.svelte importiert SubscriptionActionSheet', () => {
		assert.ok(existsSync(DETAIL_PAGE), '/compare/[id]/+page.svelte fehlt');
		const src = readFileSync(DETAIL_PAGE, 'utf-8');
		assert.match(
			src,
			/SubscriptionActionSheet/,
			'SubscriptionActionSheet wird in /compare/[id]/+page.svelte nicht importiert'
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

	// Issue #1256 Scheibe 8 (AC-22, Ein-Mount-Strategie): der Bespoke-2×2-Grid
	// entfällt — die Seite rendert stattdessen den geteilten Hub (CompareDetail),
	// der intern (CompareTabs) auf das mobile 4-Stat-2×2 umschaltet
	// (s. compare_mobile_shared_hub.test.ts, AC-22).
	test('/compare/[id]/+page.svelte rendert den geteilten Hub (CompareDetail) statt eines Bespoke-Grids', () => {
		assert.ok(existsSync(DETAIL_PAGE), '/compare/[id]/+page.svelte fehlt');
		const src = readFileSync(DETAIL_PAGE, 'utf-8');
		assert.match(
			src,
			/<CompareDetail/,
			'/compare/[id]/+page.svelte rendert CompareDetail nicht — geteilter Hub fehlt'
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

	// Mobile-Shell S2: Rücksprung als <BackLink> im Inhalt (Mono-Caps, 36 px)
	// statt ArrowLeft-Icon in einer nachgebauten TopBar.
	test('/compare/[id]/+page.svelte hat <BackLink> für Back-Navigation', () => {
		assert.ok(existsSync(DETAIL_PAGE), '/compare/[id]/+page.svelte fehlt');
		const src = readFileSync(DETAIL_PAGE, 'utf-8');
		assert.match(
			src,
			/<BackLink href="\/compare"/,
			'/compare/[id]/+page.svelte hat keinen <BackLink href="/compare"> für die Back-Navigation im mobilen Kopf'
		);
		assert.ok(!/ArrowLeft/.test(src), '/compare/[id]/+page.svelte nutzt noch das ArrowLeft-Icon der abgeschafften TopBar');
	});
});
