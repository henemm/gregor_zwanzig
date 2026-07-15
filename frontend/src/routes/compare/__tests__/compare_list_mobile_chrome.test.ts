// TDD RED — Issue #1256 Scheibe S8d: Mobile-Editor-Fidelity, Gruppe A (Liste)
//
// Spec: docs/specs/modules/feat_1256_s8d_mobile_editor_fidelity.md (AC-1..AC-5)
// Soll: screen-compare-list-mobile.jsx (Handoff-4), mobile-shell.jsx:87-114
//       (TopAppBar title/eyebrow/right-Fähigkeiten, #373)
//
// Source-Wächter (Kern-Schicht): prüfen den Soll-Zustand des Markups/der
// Komponenten-Fähigkeiten. Verhaltensnachweis aus Nutzersicht folgt in
// Phase 6 per Playwright gegen Staging (frontend/e2e/compare-editor-fidelity-s8d.spec.ts)
// — ROT-Beleg gegen Staging ist für noch-nicht-deployten Stand unmöglich
// (S4-Lehre, s. compare_hub_fidelity.test.ts Kopf-Kommentar).
//
// RED-Erwartung (vor Implementation): AC-1..AC-5 FAIL (inkl. der
// TopAppBar-Fähigkeits-Tests, die AC-1/AC-15 gemeinsam absichern).
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs \
//     --experimental-strip-types --test \
//     src/routes/compare/__tests__/compare_list_mobile_chrome.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const COMPARE_DIR = join(dirname(fileURLToPath(import.meta.url)), '..');
const ROUTES_DIR = join(COMPARE_DIR, '..');
const PAGE_FILE = join(COMPARE_DIR, '+page.svelte');
const TOP_APP_BAR_FILE = join(ROUTES_DIR, '..', 'lib', 'components', 'ui', 'sidebar', 'TopAppBar.svelte');

const page = () => readFileSync(PAGE_FILE, 'utf-8');
const topAppBar = () => readFileSync(TOP_APP_BAR_FILE, 'utf-8');

describe('TopAppBar-Fähigkeiten (mobile-shell.jsx:87-114, #373 additiv) — Grundlage für AC-1/AC-15', () => {
	test('title-Prop existiert und wird gerendert', () => {
		const bar = topAppBar();
		assert.match(
			bar,
			/title\??:\s*string/,
			'AC-1/AC-15 FAIL: TopAppBar-Props hat keine title-Prop (Soll: mobile-shell.jsx:105-109)'
		);
		assert.match(
			bar,
			/\{title\}/,
			'AC-1/AC-15 FAIL: title wird nicht im Markup gerendert (Prop deklariert, aber ungenutzt reicht nicht)'
		);
	});

	test('Back-Variante von leftIcon rendert ein echtes Zurück-Tap-Ziel', () => {
		// Bewusst der bereits im Repo etablierte Zurück-Pfeil-Pfad (identisch zur
		// heutigen nachgebauten cm-mobile-appbar, CompareEditor.svelte:1128) —
		// kein neu erfundener Mechanismus, sondern Wiederverwendung des
		// vorhandenen Icons an der kanonischen Stelle.
		assert.ok(
			topAppBar().includes('M19 12H5M12 5l-7 7 7 7'),
			'AC-15 FAIL: TopAppBar rendert bei leftIcon="back" kein Zurück-Icon (Pfad M19 12H5M12 5l-7 7 7 7 fehlt) — Ist: leftIcon nur als data-Attribut, kein sichtbares Element'
		);
	});

	test('seiten-eigene rechte Aktion ersetzt die Default-Bell/Plus-Gruppe', () => {
		assert.match(
			topAppBar(),
			/\{#if\s+right\}[\s\S]{0,80}\{@render right\(\)\}[\s\S]{0,400}\{:else\}[\s\S]{0,400}top-app-bar-bell/,
			'AC-1/AC-15 FAIL: right ersetzt die Default-Bell/Plus-Gruppe nicht — Ist: right UND Bell/Plus werden immer beide gerendert (kein if/else)'
		);
	});
});

describe('AC-1: Mobile-Kopf befüllt die Design-Kopfleiste (JSX-M Z.22)', () => {
	test('eyebrow zeigt „Workspace · N" mit dynamischer Vergleichs-Anzahl', () => {
		const code = page();
		assert.match(
			code,
			/eyebrow[=:][^\n]*Workspace/,
			'AC-1 FAIL: keine eyebrow-Befüllung Richtung „Workspace" für die Design-Kopfleiste erkennbar (Ist: nur statisches <Eyebrow>Workspace · Orts-Vergleiche</Eyebrow> im Desktop-Kopf, keine Zahl)'
		);
		assert.match(
			code,
			/Workspace[^\n]{0,60}presets\.length/,
			'AC-1 FAIL: eyebrow zeigt nicht die dynamische Vergleichs-Anzahl (presets.length) — Soll: „Workspace · N"'
		);
	});

	test('Plus-Tap-Ziel führt zusätzlich zur Design-Kopfleiste nach /compare/new', () => {
		// Ist heute genau 1 Treffer (die bestehende „+ Neuer Vergleich"-CTA-Taste).
		// Soll: ein zweiter Treffer als rechte Aktion der Design-Kopfleiste.
		const matches = (page().match(/\/compare\/new/g) ?? []).length;
		assert.ok(
			matches >= 2,
			`AC-1 FAIL: kein zweites /compare/new-Ziel für die rechte Kopfleisten-Aktion gefunden (${matches} Treffer, erwartet >=2 — einer bleibt die bestehende CTA-Taste)`
		);
	});
});

describe('AC-2: kurzer mobiler Intro-Text (JSX-M Z.27-30)', () => {
	test('kurzer Intro-Satz „…läuft, bis du stoppst." ist im Markup vorhanden', () => {
		assert.ok(
			page().includes('Ohne Ranking — läuft, bis du stoppst.'),
			'AC-2 FAIL: kurzer mobiler Intro-Text fehlt (Soll: JSX-M Z.27-30 „Stehende Monitore: … Ohne Ranking — läuft, bis du stoppst.")'
		);
	});
});

describe('AC-3: Suchfeld mobil entfernt, Desktop unverändert (Handoff-5-P3)', () => {
	test('Suchfeld ist in einen Desktop-only-Wrapper gefasst', () => {
		assert.match(
			page(),
			/hidden desktop:block[\s\S]{0,400}Suchen…/,
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
