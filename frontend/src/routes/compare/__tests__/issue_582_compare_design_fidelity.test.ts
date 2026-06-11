// TDD RED — Issue #582: Compare-Screen Design-Fidelity
//
// Spec: docs/specs/modules/issue_582_compare_design_fidelity.md
//
// Source-Inspection-Tests: prüfen ob die Svelte-Dateien 1:1 nach JSX-Vorlage
// implementiert sind. Kein DOM-Rendering, keine Mocks.
//
// RED-Erwartung (vor Implementation):
//   AC-1: FAIL — +page.svelte hat "WORKSPACE · ORTS-VERGLEICHE" (Caps), kein <Stat, showSearch-Guard
//   AC-2: FAIL — Leerzustand nutzt kein <Card-Molecule
//   AC-3: FAIL — Footer-Zähler "N von M Vergleichen" fehlt
//   AC-4: FAIL — [id]/+page.svelte hat max-w-5xl statt inline padding 22px 40px
//   AC-5: FAIL — CompareTabs.svelte nutzt <Segmented statt Button-mit-Underline
//   AC-6: FAIL — Übersicht-Tab hat kein g-r-3 border-left accent Verifikations-Hinweis
//   AC-7: FAIL — Vorschau-Tab hat kein Email-View-Toggle Desktop/iPhone
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/routes/compare/__tests__/issue_582_compare_design_fidelity.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const ROUTES_COMPARE = join(fileURLToPath(import.meta.url), '..', '..', '..');
const COMPARE_DIR = join(ROUTES_COMPARE, '..', 'lib', 'components', 'compare');

const LIST_PAGE    = join(ROUTES_COMPARE, 'compare', '+page.svelte');
const HUB_PAGE     = join(ROUTES_COMPARE, 'compare', '[id]', '+page.svelte');
const COMPARE_TABS = join(COMPARE_DIR, 'CompareTabs.svelte');

// ═══════════════════════════════════════════════════════════════════
// Block A — Compare-Liste
// ═══════════════════════════════════════════════════════════════════

describe('AC-1: Compare-Liste — Eyebrow + Stat-Molecule + immer sichtbare Suche', () => {
	test('AC-1a: Eyebrow-Text ist "Workspace · Orts-Vergleiche" (Mixed Case, nicht CAPS)', () => {
		const src = readFileSync(LIST_PAGE, 'utf-8');
		assert.match(
			src,
			/Workspace\s*·\s*Orts-Vergleiche/,
			'Eyebrow muss "Workspace · Orts-Vergleiche" lauten (Mixed Case) — IST: "WORKSPACE · ORTS-VERGLEICHE"'
		);
	});

	test('AC-1b: Stats-Zeile nutzt <Stat Molecule (nicht rohes HTML)', () => {
		const src = readFileSync(LIST_PAGE, 'utf-8');
		assert.match(
			src,
			/<Stat\b/,
			'Stats-Zeile muss das <Stat>-Molecule verwenden — IST: rohe HTML-Divs mit inline Styling'
		);
	});

	test('AC-1c: Stat-Molecule hat tone="accent" für Aktiv-Wert', () => {
		const src = readFileSync(LIST_PAGE, 'utf-8');
		assert.match(
			src,
			/tone="accent"|tone=\{['""]accent['"]\}/,
			'Stat-Molecule muss tone="accent" für den Aktiv-Wert haben'
		);
	});

	test('AC-1d: Suche ist IMMER sichtbar (kein showSearch-Guard)', () => {
		const src = readFileSync(LIST_PAGE, 'utf-8');
		assert.doesNotMatch(
			src,
			/showSearch/,
			'showSearch-Guard muss entfernt werden — JSX zeigt Suche immer an (nicht erst ab 3 Vergleichen)'
		);
	});
});

describe('AC-2: Compare-Liste — Leerzustand als Card-Molecule', () => {
	test('AC-2: Leerzustand nutzt <Card padding={40} mit zentriertem Text', () => {
		const src = readFileSync(LIST_PAGE, 'utf-8');
		assert.match(
			src,
			/padding.*40|40.*padding/,
			'Leerzustand muss <Card padding={40}> verwenden — IST: roher div-Text'
		);
	});
});

describe('AC-3: Compare-Liste — Footer-Zähler', () => {
	test('AC-3: Footer zeigt "N von M Vergleichen" in mono/ink-4', () => {
		const src = readFileSync(LIST_PAGE, 'utf-8');
		assert.match(
			src,
			/von.*Vergleich|Vergleich.*von/,
			'Footer-Zähler "N von M Vergleichen" fehlt — JSX hat: {filtered.length} von {subs.length} Vergleichen'
		);
	});

	test('AC-3: Footer-Zähler nutzt var(--g-font-mono)', () => {
		const src = readFileSync(LIST_PAGE, 'utf-8');
		assert.match(
			src,
			/g-font-mono/,
			'Footer-Zähler muss font-family: var(--g-font-mono) haben'
		);
	});
});

// ═══════════════════════════════════════════════════════════════════
// Block B — Compare-Hub Header + Tab-Leiste
// ═══════════════════════════════════════════════════════════════════

describe('AC-4: Compare-Hub — Full-width Header ohne max-w Container', () => {
	test('AC-4a: Desktop-Header hat KEIN max-w-5xl (Tailwind-Container entfernt)', () => {
		const src = readFileSync(HUB_PAGE, 'utf-8');
		assert.doesNotMatch(
			src,
			/max-w-5xl/,
			'Desktop-Header darf kein max-w-5xl haben — JSX definiert full-width mit padding: 22px 40px 0'
		);
	});

	test('AC-4b: Desktop-Header hat border-bottom mit var(--g-rule)', () => {
		const src = readFileSync(HUB_PAGE, 'utf-8');
		assert.match(
			src,
			/border-bottom.*g-rule|g-rule.*border-bottom/,
			'Desktop-Header braucht border-bottom: 1px solid var(--g-rule) — IST: nicht vorhanden'
		);
	});

	test('AC-4c: Breadcrumb-Links nutzen font-family var(--g-font-mono)', () => {
		const src = readFileSync(HUB_PAGE, 'utf-8');
		assert.match(
			src,
			/g-font-mono/,
			'Breadcrumb-Links brauchen font-family: var(--g-font-mono) als Inline-Style'
		);
	});
});

describe('AC-5: Compare-Hub — Tab-Buttons mit Underline statt Segmented', () => {
	test('AC-5a: CompareTabs nutzt KEINE <Segmented-Komponente für Tab-Leiste', () => {
		const src = readFileSync(COMPARE_TABS, 'utf-8');
		// Segmented für Tab-Navigation (not für andere Zwecke) — checkt ob die Tab-Leiste
		// noch Segmented verwendet (line ~188 im IST-Zustand)
		const lines = src.split('\n');
		const tabLineIdx = lines.findIndex(l => /Segmented.*options.*segmentedOptions|segmentedOptions.*Segmented/.test(l));
		assert.equal(
			tabLineIdx,
			-1,
			`CompareTabs Tab-Leiste muss <button>-mit-underline verwenden statt <Segmented options={segmentedOptions}> (gefunden in Zeile ${tabLineIdx + 1})`
		);
	});

	test('AC-5b: CompareTabs hat Tab-Buttons mit border-bottom accent als Aktiv-Indikator', () => {
		const src = readFileSync(COMPARE_TABS, 'utf-8');
		assert.match(
			src,
			/border-bottom.*g-accent|g-accent.*border-bottom/,
			'Tab-Buttons brauchen border-bottom: 2px solid var(--g-accent) für aktiven Tab — IST: nicht vorhanden'
		);
	});

	test('AC-5c: Tab-Inhalt-Wrapper hat padding 28px 40px', () => {
		const src = readFileSync(COMPARE_TABS, 'utf-8');
		assert.match(
			src,
			/28px.*40px|padding.*28px/,
			'Tab-Inhalt-Wrapper braucht padding: 28px 40px 80px — IST: Tailwind-Klassen'
		);
	});
});

// ═══════════════════════════════════════════════════════════════════
// Block C — Hub Tab-Inhalte
// ═══════════════════════════════════════════════════════════════════

describe('AC-6: Übersicht-Tab — Monitoring-Streifen + SummaryCard-Grid', () => {
	test('AC-6a: Verifikations-Hinweis hat border-left mit g-accent', () => {
		const src = readFileSync(COMPARE_TABS, 'utf-8');
		assert.match(
			src,
			/border-left.*3px.*g-accent|borderLeft.*3px.*g-accent/,
			'Verifikations-Hinweis braucht border-left: 3px solid var(--g-accent) — Übersicht- und Vorschau-Tab'
		);
	});

	test('AC-6b: Übersicht-Tab hat SummaryCard mit "Bearbeiten →" Link', () => {
		const src = readFileSync(COMPARE_TABS, 'utf-8');
		assert.match(
			src,
			/Bearbeiten\s*→|Bearbeiten\s*&rarr;/,
			'SummaryCard braucht "Bearbeiten →"-Link pro Sektion — IST: nicht vorhanden'
		);
	});

	test('AC-6c: Monitoring-Streifen hat 4 Stat-Felder (gap: 40px)', () => {
		const src = readFileSync(COMPARE_TABS, 'utf-8');
		assert.match(
			src,
			/gap.*40|40.*gap/,
			'Monitoring-Streifen braucht gap: 40px für die 4 Stat-Felder'
		);
	});
});

describe('AC-7: Vorschau-Tab — ChannelSwitch + Email-Toggle + BriefingPreview', () => {
	test('AC-7: Vorschau-Tab hat Email-View-Toggle Desktop/iPhone', () => {
		const src = readFileSync(COMPARE_TABS, 'utf-8');
		assert.match(
			src,
			/Desktop.*Inbox|iPhone.*Mail|desktop.*iphone/i,
			'Vorschau-Tab muss Email-View-Toggle mit "Desktop-Inbox" und "iPhone-Mail" haben — IST: nicht vorhanden'
		);
	});
});

