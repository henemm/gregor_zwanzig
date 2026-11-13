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
// #2837 S1: geteilter Hub-Kopf (Trip und Vergleich) und sein Kebab.
const HUB_KOPF      = join(COMPARE_DIR, '..', 'shared', 'hub-kopf', 'HubKopf.svelte');
const KEBAB         = join(COMPARE_DIR, '..', 'molecules', 'SubscriptionKebab.svelte');

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
	// Umgehängt durch #2913 c2: der letzte desktop:hidden-Block der Seite (mobile Orte-Anzahl im Kopf)
	// entfällt — die Meta-Zeile ist für beide Breiten dieselbe (HubKopf). Der mobile Render-Pfad der
	// Seite ist die Umschaltung `mobil` per matchMedia (Aktionsblatt statt Dropdown, #2278 AC-12).
	test('/compare/[id]/+page.svelte hat einen mobilen Render-Pfad (matchMedia ≤899 px → mobil)', () => {
		assert.ok(existsSync(DETAIL_PAGE), '/compare/[id]/+page.svelte fehlt');
		const src = readFileSync(DETAIL_PAGE, 'utf-8');
		assert.match(
			src,
			/matchMedia\('\(max-width: 899px\)'\)/,
			'/compare/[id]/+page.svelte schaltet nicht auf mobil um — mobiler Render-Pfad fehlt'
		);
		assert.match(src, /\{mobil\}/, '/compare/[id]/+page.svelte reicht `mobil` nicht an den HubKopf');
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

	// Umgehängt durch #2837 S1 (ADR-0110): die mobile Kopfleiste der Detailseite ist der geteilte
	// HubKopf (Zurück-Pfeil, Senden, Kebab). Die 44-px-Tippflächen stehen dort (Leisten-Knöpfe)
	// bzw. im mobilen SubscriptionKebab-Knopf; gemessen im Browser: e2e/hub-kopf-paritaet-compare-trip HP-2/HP-7.
	test('/compare/[id]: der HubKopf der Seite hat 44px-Tippflächen in der mobilen Kopfleiste', () => {
		assert.ok(existsSync(DETAIL_PAGE), '/compare/[id]/+page.svelte fehlt');
		assert.match(readFileSync(DETAIL_PAGE, 'utf-8'), /<HubKopf\b/, '/compare/[id]/+page.svelte bindet den HubKopf nicht ein');
		const hubKopf = readFileSync(HUB_KOPF, 'utf-8');
		assert.match(hubKopf, /min-height:\s*44px;[\s\S]*?min-width:\s*44px;/, 'HubKopf hat kein 44px-Tap-Target für mobile Leisten-Knöpfe');
		assert.match(readFileSync(KEBAB, 'utf-8'), /style:width="44px"[\s\S]*?style:height="44px"/, 'mobiler Kebab-Knopf ohne 44×44-Tippfläche');
	});

	// Mobile-Shell S2: Rücksprung als <BackLink> im Inhalt (Mono-Caps, 36 px)
	// statt ArrowLeft-Icon in einer nachgebauten TopBar.
	// Umgehängt durch #2837 S1: der <BackLink> steht im HubKopf und zielt auf das Elternteil, das die
	// Seite mit href '/compare' übergibt (gerendert: hub_kopf_seiten_paritaet AC-2 „führt zur Liste").
	test('/compare/[id]: <BackLink> für Back-Navigation (HubKopf, Ziel /compare)', () => {
		assert.ok(existsSync(DETAIL_PAGE), '/compare/[id]/+page.svelte fehlt');
		const src = readFileSync(DETAIL_PAGE, 'utf-8');
		const hubKopf = readFileSync(HUB_KOPF, 'utf-8');
		assert.match(hubKopf, /<BackLink href=\{parent\.href\}/, 'HubKopf hat keinen <BackLink> auf das Elternteil');
		assert.match(src, /<HubKopf[\s\S]*?parent=\{\{[^}]*href: '\/compare' \}\}/, 'die Seite gibt dem HubKopf nicht /compare als Elternteil');
		assert.ok(!/ArrowLeft/.test(src) && !/ArrowLeft/.test(hubKopf), 'der Hub-Kopf nutzt noch das ArrowLeft-Icon der abgeschafften TopBar');
	});
});
