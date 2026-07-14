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
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const SRC = resolve(HERE, '../../../..');

const TILE = resolve(SRC, 'lib/components/compare/CompareTile.svelte');
const LIST_PAGE = resolve(SRC, 'routes/compare/+page.svelte');
const HUB_PAGE = resolve(SRC, 'routes/compare/[id]/+page.svelte');
const TABS = resolve(SRC, 'lib/components/compare/CompareTabs.svelte');
const SHEET = resolve(SRC, 'lib/components/mobile/MCompareActionSheet.svelte');

describe('AC-21 — mobile Liste: Chevron statt Kebab im dense-Modus', () => {
	test('CompareTile rendert im dense-Modus einen Chevron (Soll: screen-compare-list-mobile.jsx:54)', () => {
		const src = readFileSync(TILE, 'utf-8');
		assert.match(
			src,
			/chevron/i,
			'CompareTile.svelte kennt keinen Chevron — dense-Kacheln müssen einen ' +
				'Chevron als reines Navigations-Affordance zeigen (JSX: trailing={<MIcon kind="chevron"/>})'
		);
	});

	test('CompareTile gated den Kebab auf Nicht-dense ({#if !dense})', () => {
		const src = readFileSync(TILE, 'utf-8');
		const kebabIdx = src.indexOf('<CompareKebab');
		assert.ok(kebabIdx > -1, 'CompareKebab-Render nicht gefunden — Datei-Struktur geändert?');
		const before = src.slice(Math.max(0, kebabIdx - 600), kebabIdx);
		assert.match(
			before,
			/\{#if\s+!dense\}/,
			'CompareKebab wird unconditional gerendert — im dense-Modus (mobile Liste) ' +
				'darf KEIN Kebab erscheinen (Ist-Falle: S7 brauchte :visible-Selektoren, ' +
				'weil Desktop- und Mobile-Kebab dasselbe aria-label tragen)'
		);
	});

	test('mobile Listen-Kachel ist reine Navigation (kein onAction am dense-Tile)', () => {
		const src = readFileSync(LIST_PAGE, 'utf-8');
		const tiles = src.match(/<CompareTile[\s\S]*?\/>/g) ?? [];
		const denseTile = tiles.find((t) => /dense=\{?true\}?/.test(t));
		assert.ok(denseTile, 'Mobile CompareTile (dense) in routes/compare/+page.svelte nicht gefunden');
		assert.doesNotMatch(
			denseTile,
			/onAction/,
			'Mobile dense-Kachel reicht noch onAction (Kebab-Aktionen) durch — ' +
				'Aktionen leben mobil ausschließlich im Detail-Hub (Fluss: Liste→Detail)'
		);
	});
});

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

	test('CompareTabs hat eine Viewport-Weiche (matchMedia, Muster TripTabs.svelte:117-124)', () => {
		const src = readFileSync(TABS, 'utf-8');
		assert.match(
			src,
			/matchMedia\(\s*['"`]\(max-width:\s*899px\)['"`]\s*\)/,
			'CompareTabs.svelte hat keine isMobileViewport-Mechanik — der Monitoring-Streifen ' +
				'kann nicht zwischen Desktop-5-Stat-Leiste und mobilem 2×2 umschalten'
		);
	});

	test('mobiler Monitoring-Zweig zeigt GENAU die 4 Soll-Stats (ohne „Briefings")', () => {
		const src = readFileSync(TABS, 'utf-8');
		const startMarker = 'data-testid="compare-detail-monitoring-mobile"';
		const start = src.indexOf(startMarker);
		assert.ok(
			start > -1,
			'Mobiler Monitoring-Block (data-testid="compare-detail-monitoring-mobile") fehlt — ' +
				'Soll: 2×2-Grid mit 4 Stats (screen-compare-detail-mobile.jsx:79-85)'
		);
		// Blockende: nächstes schließendes Grid — pragmatisch: die 1200 Zeichen
		// nach dem Marker müssen die 4 Soll-Labels tragen, „Briefings" gehört
		// NICHT dazu (bleibt Desktop-only, 5. Stat der Desktop-Leiste).
		const block = src.slice(start, start + 1200);
		for (const label of ['Status', 'Nächster Versand', 'Zuletzt raus', 'Kanäle']) {
			assert.ok(
				block.includes(label),
				`Mobiler Monitoring-Block ohne Stat „${label}" (Soll: screen-compare-detail-mobile.jsx:81-84)`
			);
		}
		assert.ok(
			!block.includes('Briefings'),
			'Mobiler Monitoring-Block enthält „Briefings" — das Soll-2×2 hat GENAU 4 Stats, ' +
				'Briefings-Zeiten bleiben der Desktop-Leiste vorbehalten'
		);
	});

	// Fix-Loop 1 (Fresh-Eyes-Fund): der Ein-Mount-Umbau rendert die Tab-Leiste
	// jetzt auch mobil, aber ohne horizontales Scrollen waren „Versand"/
	// „Vorschau" auf 390px unerreichbar (Inline-Edit-Paritäts-Verletzung).
	// Muster TripTabs.svelte:330-352.
	test('Mobile-Media-Query macht die Tab-Leiste horizontal scrollbar (overflow-x: auto)', () => {
		const src = readFileSync(TABS, 'utf-8');
		const mqStart = src.indexOf('@media (max-width: 899px)');
		assert.ok(mqStart > -1, 'CompareTabs.svelte hat keine @media (max-width: 899px)-Regel');
		const mqBlock = src.slice(mqStart, mqStart + 1500);
		assert.match(
			mqBlock,
			/\.compare-tabs-bar\s*\{[^}]*overflow-x:\s*auto/,
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

describe('AC-23 — MCompareActionSheet: Lifecycle-Aktionsliste statt compareActions()', () => {
	// Ersetzt die (zu lose) Assertion aus issue_493_compare_mobile.test.ts:63-71 —
	// deren Regex /compareActions/ matcht als Substring auch compareLifecycleActions
	// und würde die Umstellung nie bemerken. Hier: positiver UND negativer Nachweis.
	test('Sheet leitet seine Aktionen aus compareLifecycleActions() ab', () => {
		const src = readFileSync(SHEET, 'utf-8');
		assert.match(
			src,
			/compareLifecycleActions\(/,
			'MCompareActionSheet.svelte nutzt compareLifecycleActions() nicht — ' +
				'mobile Aktionen müssen dem Desktop-Hub-Kebab (S3, AC-5) entsprechen: ' +
				'Toggle/Archivieren/Löschen, draft = nur „Entwurf löschen"'
		);
	});

	test('Sheet ruft den vollen compareActions()-Umfang NICHT mehr auf', () => {
		const src = readFileSync(SHEET, 'utf-8');
		assert.ok(
			!/(?<!Lifecycle)compareActions\(/.test(src),
			'MCompareActionSheet.svelte ruft noch compareActions() auf — ' +
				'„Briefing jetzt senden"/„Vorschau"/„Bearbeiten" gehören mobil nicht ' +
				'ins Lifecycle-Bottom-Sheet (Soll: CDM_lifecycleActions, ' +
				'screen-compare-detail-mobile.jsx:16-22)'
		);
	});
});
