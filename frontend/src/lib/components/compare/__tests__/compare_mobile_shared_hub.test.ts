// TDD RED — Issue #1256 Scheibe 8: Mobile-Vervollständigung (AC-21/22/23).
//
// Spec: docs/specs/modules/issue_1256_compare_ui_rewire.md § Scheibe 8
// Soll (JSX, Handoff-4):
//   - screen-compare-list-mobile.jsx:48-57 — CompareTile dense mit
//     trailing-Chevron STATT Kebab (Kachel = reine Navigation zur Detail-Seite)
//   - screen-compare-detail-mobile.jsx:70-100 — mobiler Hub hat DIESELBEN
//     6 Tabs; Übersicht-Tab = 2×2-Monitoring mit GENAU 4 Stats
//     (Status / Nächster Versand / Zuletzt raus / Kanäle mit Namen),
//     KEIN eigener Bespoke-Pfad
//   - screen-compare-detail-mobile.jsx:16-22 (CDM_lifecycleActions) —
//     Bottom-Sheet zeigt NUR Lifecycle-Aktionen (deckungsgleich mit
//     compareLifecycleActions() aus Scheibe 3, subscriptionHelpers.ts:245)
//
// IST-BEFUND aus der Context-Phase (Spec-Annahme „AC-21 bereits vorhanden"
// war stale): CompareTile.svelte rendert den Kebab UNCONDITIONAL (Z. 155-163,
// deshalb brauchte die S7-Staging-Suite :visible-Selektoren); der mobile Hub
// ist ein Bespoke-Block in routes/compare/[id]/+page.svelte (#493) mit
// 5 Stat-Karten (inkl. „Briefings", Kanäle als ANZAHL via channelCountLabel)
// und OHNE Tabs — keine Inline-Edit-Parität auf Mobile.
//
// Ziel-Architektur (Analyse, Teilungs-Invariante + TripTabs-Muster
// TripTabs.svelte:117-124/198-202): CompareDetail wird EINMAL gemountet,
// CompareTabs schaltet intern via matchMedia(max-width: 899px) den
// Monitoring-Streifen auf das 4-Stat-2×2 und den Idealwerte-Tab auf
// CorridorEditorMobile. Kein zweiter DOM-Baum (doppelte testids/Fetches/
// hubPutQueue-Instanzen = S4-F001-/S7-F004-Fehlerklasse).
//
// Source-Inspection-Tests (KEIN Mock, KEIN jsdom-Mount — Projekt-Idiom,
// siehe step2_orte_library_grouping.test.ts): Svelte-5-Komponenten sind in
// diesem Setup nicht mountbar — echtes DOM-/Klick-Verhalten wird in Phase 6
// über Playwright gegen Staging abgesichert (AC-21 Fresh-Eyes, AC-22
// DOM-Zählung, AC-24 Lock-Toast + floating CTA).

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { register } from 'node:module';
import { resolve, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const SRC = resolve(HERE, '../../../..');
// #2682: das Modell der Übersicht wird echt geladen (endungslose Importe der Helfer).
register(pathToFileURL(resolve(SRC, '..', 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(resolve(SRC, '..') + '/').href);
const HUB_UEBERSICHT = resolve(SRC, 'lib/components/shared/hub-uebersicht/HubUebersicht.svelte');
const MODELL = resolve(SRC, 'lib/components/shared/hub-uebersicht/hubUebersichtModell.ts');

const HUB_PAGE = resolve(SRC, 'routes/compare/[id]/+page.svelte');
const TABS = resolve(SRC, 'lib/components/compare/CompareTabs.svelte');
const MTABBAR = resolve(SRC, 'lib/components/mobile/MTabBar.svelte');
const SHEET = resolve(SRC, 'lib/components/mobile/SubscriptionActionSheet.svelte');

// AC-21 (mobile Liste = reine Navigation, Chevron statt Kebab) und AC-23 (Lifecycle-Blatt aus
// compareLifecycleActions) sind mit #2278 abgeloest (Entscheidung #1256 S8 AC-21 -> Paritaet,
// Epic #2345 DoD-3): mobile Karte/Blatt/Pillen sind geteilt und stehen in
// organisms/__tests__/subscription_card.test.ts und routes/compare/__tests__/compare_list_mobile_aktionen.test.ts.

describe('AC-22 — mobiler Hub: geteilte CompareTabs mit 4-Stat-2×2 statt Bespoke-Block', () => {
	test('Hub-Seite nutzt keinen Bespoke-Kanäle-Zähler mehr (channelCountLabel weg)', () => {
		const src = readFileSync(HUB_PAGE, 'utf-8');
		assert.doesNotMatch(
			src,
			/channelCountLabel/,
			'routes/compare/[id]/+page.svelte zählt Kanäle noch selbst (Bespoke-5-Karten-Grid) — ' +
				'Soll: Kanal-NAMEN aus dem geteilten CompareTabs-Monitoring (channelsLabel, S3 AC-6)'
		);
	});

	// Issue #2682: der Monitoring-Streifen liegt im geteilten Baustein HubUebersicht — die Weiche
	// steht dort; CompareTabs behält seine eigene fuer Orte-Rahmen/Wertebereiche (Fall unten).
	for (const [name, datei] of [
		['CompareTabs', TABS],
		['HubUebersicht (Übersicht, #2682)', HUB_UEBERSICHT]
	] as const) {
		test(`${name} hat eine Viewport-Weiche (matchMedia, Muster TripTabs.svelte:117-124)`, () => {
			const src = readFileSync(datei, 'utf-8');
			assert.match(
				src,
				/matchMedia\(\s*['"`]\(max-width:\s*899px\)['"`]\s*\)/,
				`${name} hat keine isMobileViewport-Mechanik — der Monitoring-Streifen ` +
					'kann nicht zwischen Desktop-5-Stat-Leiste und mobilem 2×2 umschalten'
			);
		});
	}

	test('mobiler Monitoring-Zweig zeigt GENAU die 4 Soll-Stats (ohne „Briefings")', async () => {
		// #2682: das Raster rendert die mobilen Kennzahlen des Modells; ihre Etiketten werden
		// am echten Ableiter gemessen (Vergleich), nicht mehr als Literale im Markup.
		const src = readFileSync(HUB_UEBERSICHT, 'utf-8');
		const startMarker = 'data-testid={modell.rasterTestid}';
		const start = src.indexOf(startMarker);
		assert.ok(
			start > -1,
			'Mobiler Monitoring-Block (data-testid={modell.rasterTestid}) fehlt in HubUebersicht — ' +
				'Soll: 2×2-Grid mit 4 Stats (screen-compare-detail-mobile.jsx:79-85)'
		);
		const block = src.slice(start, start + 600);
		assert.match(block, /\{#each mobileKennzahlen as k/, 'das Raster rendert nicht die mobilen Kennzahlen');
		assert.match(src, /mobileKennzahlen = \$derived\(modell\.kennzahlen\.filter\(\(k\) => k\.mobil\)\)/);
		const { deriveVergleichKennzahlen } = await import(pathToFileURL(MODELL).href);
		const m = deriveVergleichKennzahlen(
			{ id: 'c', name: 'V', location_ids: ['l1'], schedule: 'daily', profil: 'wandern' },
			'active',
			undefined,
			[{ rank: 1, loc: { id: 'l1', name: 'A' } }]
		);
		const labels = m.kennzahlen.filter((k: { mobil: boolean }) => k.mobil).map((k: { label: string }) => k.label);
		assert.deepEqual(
			labels,
			['Status', 'Nächster Versand', 'Zuletzt raus', 'Kanäle'],
			'Mobiler Monitoring-Block: das Soll-2×2 hat GENAU diese 4 Stats, ' +
				'Briefings-Zeiten bleiben der Desktop-Leiste vorbehalten'
		);
	});

	// Fix-Loop 1 (Fresh-Eyes-Fund): der Ein-Mount-Umbau rendert die Tab-Leiste
	// jetzt auch mobil, aber ohne horizontales Scrollen waren „Versand"/
	// „Vorschau" auf 390px unerreichbar (Inline-Edit-Paritäts-Verletzung).
	// Mobile Usability Paket 2 (Spec mobile_tab_leisten_mtabbar): Die Leiste
	// lebt im geteilten MTabBar-Baustein — CompareTabs rendert ihn nur noch.
	test('Mobile-Media-Query macht die Tab-Leiste horizontal scrollbar (overflow-x: auto)', () => {
		const tabsSrc = readFileSync(TABS, 'utf-8');
		assert.match(
			tabsSrc,
			/<MTabBar[\s>]/,
			'CompareTabs.svelte rendert nicht mehr den MTabBar-Baustein'
		);
		const src = readFileSync(MTABBAR, 'utf-8');
		const mqStart = src.indexOf('@media (max-width: 899px)');
		assert.ok(mqStart > -1, 'MTabBar.svelte hat keine @media (max-width: 899px)-Regel');
		const mqBlock = src.slice(mqStart, mqStart + 1500);
		assert.match(
			mqBlock,
			/\.mtabbar\s*\{[^}]*overflow-x:\s*auto/,
			'Mobile-Media-Query enthält keine overflow-x: auto-Regel für die Tab-Leiste — ' +
				'„Versand"/„Vorschau" bleiben auf schmalen Viewports unerreichbar'
		);
	});

	test('Idealwerte-Tab schaltet mobil auf CorridorEditorMobile (Muster TripTabs.svelte:198-202)', () => {
		const src = readFileSync(TABS, 'utf-8');
		assert.match(
			src,
			/CorridorEditorMobile/,
			'CompareTabs.svelte importiert CorridorEditorMobile nicht — mobile ' +
				'Inline-Edit-Parität (S6-Spiegelung) fehlt'
		);
		const mobileUse = src.indexOf('<CorridorEditorMobile');
		assert.ok(mobileUse > -1, 'CorridorEditorMobile wird nicht gerendert');
		const before = src.slice(Math.max(0, mobileUse - 400), mobileUse);
		assert.match(
			before,
			/\{#if\s+isMobileViewport\}/,
			'CorridorEditorMobile hängt nicht an der isMobileViewport-Weiche — ' +
				'Desktop muss weiterhin den vollen CorridorEditor rendern'
		);
	});
});

describe('AC-23 (abgeloest durch #2278): Aktionsblatt kommt aus der einen Quelle subscriptionActions', () => {
	test('SubscriptionActionSheet leitet seine Aktionen aus subscriptionActions() ab', () => {
		const src = readFileSync(SHEET, 'utf-8');
		assert.match(src, /subscriptionActions\(/, 'SubscriptionActionSheet nutzt subscriptionActions() nicht');
	});
});
