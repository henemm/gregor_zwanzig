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
import { quelleMitKatalog } from '../../../lib/i18n/__tests__/quelleMitKatalog.ts';
import { compile } from 'svelte/compiler';

const ROUTES_COMPARE = join(fileURLToPath(import.meta.url), '..', '..', '..');
const COMPARE_DIR = join(ROUTES_COMPARE, '..', 'lib', 'components', 'compare');

// #2652 (i18n F3): Eyebrow und Footer-Zaehler kommen aus dem Katalog — AC-1a/AC-3
// pruefen die GERENDERTE Liste (svelte/server, deutsche Oberflaeche).
const { seiteRendern, vergleich } = await import('../../__tests__/f3HomeListenSsr.ts');
const listeHtml = () => seiteRendern('compare', { presets: [vergleich('c-1'), vergleich('c-2')], profile: null });

const LIST_PAGE    = join(ROUTES_COMPARE, 'compare', '+page.svelte');
const HUB_PAGE     = join(ROUTES_COMPARE, 'compare', '[id]', '+page.svelte');
const COMPARE_TABS = join(COMPARE_DIR, 'CompareTabs.svelte');
const MTABBAR      = join(COMPARE_DIR, '..', 'mobile', 'MTabBar.svelte');
const HUB_UEBERSICHT = join(COMPARE_DIR, '..', 'shared', 'hub-uebersicht', 'HubUebersicht.svelte');
const HUB_REITERFLAECHE = join(COMPARE_DIR, '..', 'shared', 'hub-reiterflaeche', 'HubReiterflaeche.svelte');
// #2837 S1 (ADR-0110): der Breadcrumb des Hubs liegt im geteilten HubKopf (Trip und Vergleich).
const HUB_KOPF = join(COMPARE_DIR, '..', 'shared', 'hub-kopf', 'HubKopf.svelte');

// ═══════════════════════════════════════════════════════════════════
// Block A — Compare-Liste
// ═══════════════════════════════════════════════════════════════════

describe('AC-1: Compare-Liste — Eyebrow + Stat-Molecule + immer sichtbare Suche', () => {
	test('AC-1a: Eyebrow-Text ist "Workspace · Orts-Vergleiche" (Mixed Case, nicht CAPS)', () => {
		assert.match(
			listeHtml(),
			/>Workspace · Orts-Vergleiche</,
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
		assert.match(
			listeHtml(),
			/letter-spacing: 0\.06em">2 von 2 Vergleichen</,
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

	// Umgehängt durch #2837 S1 (ADR-0110, Adversary F001): die Unterkante des Hub-Kopfs gehört dem
	// geteilten HubKopf (Trip und Vergleich gleich), nicht der Seite. Geprüft am ECHTEN Stylesheet
	// des Bausteins (svelte/compiler, wie der Browser es bekommt): Desktop-Regel (min-width 900px)
	// am Wurzelelement .hub-kopf mit border-bottom 1px solid var(--g-rule). Dass beide Seiten dieses
	// Wurzelelement ohne eigenen Rahmen/Abstand tragen: hub_kopf_seiten_paritaet „Unterkante".
	test('AC-4b: Desktop-Header hat border-bottom mit var(--g-rule) (im geteilten HubKopf)', () => {
		const css = compile(readFileSync(HUB_KOPF, 'utf-8'), { generate: 'client', filename: HUB_KOPF }).css?.code.replace(/\s+/g, '') ?? '';
		assert.match(
			css,
			/@media\(min-width:900px\)\{\.hub-kopf(\.svelte-[a-z0-9]+)?\{border-bottom:1pxsolidvar\(--g-rule\);?\}/,
			`HubKopf braucht am Desktop border-bottom: 1px solid var(--g-rule) — IST: ${css.slice(0, 400)}`
		);
	});

	test('AC-4c: Breadcrumb-Links nutzen font-family var(--g-font-mono) (im geteilten HubKopf, #2837 S1)', () => {
		const src = readFileSync(HUB_KOPF, 'utf-8');
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
		// Mobile Usability Paket 2 (Spec mobile_tab_leisten_mtabbar): Die
		// Tab-Leiste lebt im geteilten MTabBar-Baustein — der Aktiv-Indikator
		// (border-bottom accent) wird dort gepflegt, CompareTabs rendert <MTabBar>.
		const tabsSrc = readFileSync(COMPARE_TABS, 'utf-8');
		assert.match(tabsSrc, /<MTabBar[\s>]/, 'CompareTabs.svelte rendert nicht mehr den MTabBar-Baustein');
		const src = readFileSync(MTABBAR, 'utf-8');
		assert.match(
			src,
			/border-bottom.*g-accent|g-accent.*border-bottom/,
			'MTabBar braucht border-bottom: 2px solid var(--g-accent) für den aktiven Tab — IST: nicht vorhanden'
		);
	});

	test('AC-5c: Tab-Inhalt steht in der geteilten Reiterfläche mit padding 28px 40px (#2880)', () => {
		// #2880: der Rand lebt im geteilten Baustein HubReiterflaeche (28/40/60, wie im Trip);
		// der eigene Rand 28/40/80 von `.compare-tabs-content` ist entfallen (doppelte Einrückung).
		// Gemessen im Browser: e2e/hub-anlegen-paritaet-flaechen.spec.ts PF-1 … PF-3.
		const tabsSrc = readFileSync(COMPARE_TABS, 'utf-8');
		assert.match(tabsSrc, /<HubReiterflaeche[\s>]/, 'CompareTabs.svelte rendert die geteilte Reiterfläche nicht');
		const src = readFileSync(HUB_REITERFLAECHE, 'utf-8');
		assert.match(src, /padding:\s*28px 40px/, 'HubReiterflaeche braucht padding: 28px 40px 60px');
	});
});

// ═══════════════════════════════════════════════════════════════════
// Block C — Hub Tab-Inhalte
// ═══════════════════════════════════════════════════════════════════

describe('AC-6: Übersicht-Tab — Monitoring-Streifen + SummaryCard-Grid', () => {
	// #1743 (AC-28): der Verifikations-Hinweis mit „Vorschau prüfen →" entfaellt samt
	// Vorschau-Reiter; Zusicherung jetzt: kein Hinweis-Streifen mit Vorschau-Sprung mehr.
	// Issue #2682: die Übersicht ist der geteilte Baustein HUB_UEBERSICHT — Positiv-Fälle lesen dort,
	// die Negativ-Zusicherung gilt für CompareTabs UND den Baustein (darf nicht vakuum werden).
	for (const [name, datei] of [['CompareTabs', COMPARE_TABS], ['HubUebersicht', HUB_UEBERSICHT]] as const) {
		test(`AC-6a (#1743): kein Verifikations-Hinweis mit Vorschau-Sprung mehr (${name})`, () => {
			const src = readFileSync(datei, 'utf-8');
			assert.doesNotMatch(
				src,
				/border-left:\s*3px solid var\(--g-accent\)/,
				'Verifikations-Hinweis-Streifen (border-left 3px g-accent) steht noch im Hub'
			);
			assert.doesNotMatch(src, />\s*Vorschau prüfen/, 'Knopf „Vorschau prüfen" steht noch im Hub');
		});
	}

	test('AC-6b: Übersicht-Tab hat SummaryCard mit "Bearbeiten →" Link', () => {
		// Issue #2659 (i18n F10): Text aus dem Katalog (aktionen.edit) — mit deutschem Wert gelesen.
		const src = quelleMitKatalog(readFileSync(HUB_UEBERSICHT, 'utf-8'));
		assert.match(
			src,
			/Bearbeiten\s*→|Bearbeiten\s*&rarr;/,
			'SummaryCard braucht "Bearbeiten →"-Link pro Sektion — IST: nicht vorhanden'
		);
	});

	test('AC-6c: Monitoring-Streifen hat 4 Stat-Felder (gap: 40px)', () => {
		const src = readFileSync(HUB_UEBERSICHT, 'utf-8');
		assert.match(
			src,
			/gap.*40|40.*gap/,
			'Monitoring-Streifen braucht gap: 40px für die 4 Stat-Felder'
		);
	});
});

// AC-7 (Email-View-Toggle im Vorschau-Tab) entfaellt: der Vorschau-Reiter
// entfiel mit #1743 ersatzlos.

