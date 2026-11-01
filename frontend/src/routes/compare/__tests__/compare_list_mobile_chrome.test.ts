// TDD RED — Issue #1256 Scheibe S8d: Mobile-Editor-Fidelity, Gruppe A (Liste)
//
// Spec: docs/specs/modules/feat_1256_s8d_mobile_editor_fidelity.md (AC-1..AC-5)
// Soll: screen-compare-list-mobile.jsx (Handoff-4); seit Mobile-Shell S2
//       ohne Kopfleiste — <PageHeader> traegt Titel/Eyebrow/Rechts-Slot.
//
// Source-Wächter (Kern-Schicht): prüfen den Soll-Zustand des Markups/der
// Komponenten-Fähigkeiten. Verhaltensnachweis aus Nutzersicht folgt in
// Phase 6 per Playwright (seit #2347 S4 je kind in frontend/e2e/hub-liste-seitenrahmen.spec.ts
// HL-1..HL-5; vormals compare-editor-fidelity-s8d.spec.ts AC-1..AC-5)
// — ROT-Beleg gegen Staging ist für noch-nicht-deployten Stand unmöglich
// (S4-Lehre, s. compare_hub_fidelity.test.ts Kopf-Kommentar).
//
// RED-Erwartung (vor Implementation): AC-1..AC-5 FAIL (inkl. der
// PageHeader-Fähigkeits-Tests, die AC-1/AC-15 gemeinsam absichern).
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs \
//     --experimental-strip-types --test \
//     src/routes/compare/__tests__/compare_list_mobile_chrome.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const COMPARE_DIR = join(dirname(fileURLToPath(import.meta.url)), '..');
const ROUTES_DIR = join(COMPARE_DIR, '..');
const PAGE_FILE = join(COMPARE_DIR, '+page.svelte');
const PAGE_HEADER_FILE = join(ROUTES_DIR, '..', 'lib', 'components', 'atoms', 'PageHeader.svelte');
const SIDEBAR_DIR = join(ROUTES_DIR, '..', 'lib', 'components', 'ui', 'sidebar');

const page = () => readFileSync(PAGE_FILE, 'utf-8');
const pageHeader = () => readFileSync(PAGE_HEADER_FILE, 'utf-8');

// #2652 (i18n F3): die Texte kommen aus dem Katalog — AC-1..AC-3 pruefen deshalb die
// GERENDERTE Seite (svelte/server, deutsche Oberflaeche) statt des Quelltexts.
const { seiteRendern, vergleich } = await import('../../__tests__/f3HomeListenSsr.ts');
const gerendert = () =>
	seiteRendern('compare', { presets: [vergleich('c-1'), vergleich('c-2')], profile: null });

// Mobile-Shell S2 (docs/design-requests/mobile_shell_ohne_topbar.md): die
// globale Kopfleiste und ihr Store sind abgeschafft. Titel/Eyebrow/„Neuer
// Vergleich" stehen mobil im <PageHeader> der Seite — derselbe Baustein wie
// auf der Uebersicht (AP-011).
describe('PageHeader-Fähigkeiten — Grundlage für AC-1/AC-15 ohne Kopfleiste', () => {
	test('back-Prop rendert einen Rücksprung-Link über dem Eyebrow', () => {
		const hdr = pageHeader();
		assert.match(hdr, /back\??:\s*\{\s*href:\s*string;\s*label:\s*string\s*\}/, 'PageHeader hat keine back-Prop {href,label}');
		assert.ok(hdr.includes('<BackLink'), 'PageHeader rendert bei back keinen <BackLink>');
	});

	test('kein Kopfleisten-Store und keine TopAppBar-Komponente mehr im Repo', () => {
		assert.ok(!existsSync(join(SIDEBAR_DIR, 'TopAppBar.svelte')), 'ui/sidebar/TopAppBar.svelte existiert noch');
		assert.ok(!existsSync(join(ROUTES_DIR, '..', 'lib', 'stores', 'topAppBar.svelte.ts')), 'stores/topAppBar.svelte.ts existiert noch');
		assert.ok(!page().includes('topAppBarStore'), 'compare/+page.svelte befüllt noch den Kopfleisten-Store');
	});
});

describe('AC-1: Mobiler Kopf steht im <PageHeader> der Seite (JSX-M Z.22)', () => {
	test('eyebrow zeigt „Workspace · N" mit dynamischer Vergleichs-Anzahl', () => {
		const kopf = /<header data-slot="page-header"[\s\S]*?<\/header>/.exec(gerendert())?.[0] ?? '';
		assert.ok(kopf.includes('Workspace · 2'), `AC-1 FAIL: der mobile <PageHeader> zeigt nicht „Workspace · N": ${kopf}`);
		assert.match(kopf, />Orts-Vergleiche<\/h1>/, 'AC-1 FAIL: der mobile <PageHeader> zeigt nicht „Orts-Vergleiche"');
	});

	test('„Neuer Vergleich" führt auch mobil (Rechts-Slot) nach /compare/new', () => {
		const matches = (page().match(/\/compare\/new/g) ?? []).length;
		assert.ok(
			matches >= 2,
			`AC-1 FAIL: kein zweites /compare/new-Ziel für den mobilen Rechts-Slot gefunden (${matches} Treffer, erwartet >=2 — einer bleibt die Desktop-CTA)`
		);
		assert.ok(page().includes('data-testid="compare-list-new-mobile"'), 'AC-1 FAIL: mobiler „Neuer Vergleich"-Knopf (compare-list-new-mobile) fehlt');
	});
});

describe('AC-2: kurzer mobiler Intro-Text (JSX-M Z.27-30)', () => {
	test('kurzer Intro-Satz „…läuft, bis du stoppst." ist im Markup vorhanden', () => {
		assert.ok(
			gerendert().includes('Ohne Ranking — läuft, bis du stoppst.'),
			'AC-2 FAIL: kurzer mobiler Intro-Text fehlt (Soll: JSX-M Z.27-30 „Stehende Monitore: … Ohne Ranking — läuft, bis du stoppst.")'
		);
	});
});

describe('AC-3: Suchfeld mobil entfernt, Desktop unverändert (Handoff-5-P3)', () => {
	test('Suchfeld ist in einen Desktop-only-Wrapper gefasst', () => {
		assert.match(
			gerendert(),
			/class="hidden desktop:block"[^>]*>[\s\S]{0,600}placeholder="Suchen…"/,
			'AC-3 FAIL: das Suchfeld (placeholder „Suchen…") ist nicht in einen "hidden desktop:block"-Wrapper gefasst — Ist: ohne Viewport-Weiche, immer sichtbar (Issue #582)'
		);
	});
});

describe('AC-4: Stats-Zeile mobil size="sm" (JSX-M Z.42-44)', () => {
	test('mindestens eine Stat-Verwendung mit size="sm"', () => {
		assert.match(
			page(),
			/<Stat\s[^>]*size="sm"/,
			'AC-4 FAIL: keine Stat-Zeile mit size="sm" für Mobile gefunden (Ist: Stat ohne Größenvariante, +page.svelte:65-67)'
		);
	});
});

describe('AC-5: kompaktes mobiles Content-Padding (JSX-M Z.24)', () => {
	test('Padding „12px 16px 24px" ist im Markup vorhanden', () => {
		assert.ok(
			page().includes('12px 16px 24px'),
			'AC-5 FAIL: kompaktes mobiles Content-Padding "12px 16px 24px" fehlt (Ist: einheitlich "32px 40px 60px" für beide Viewports, +page.svelte:34)'
		);
	});
});
