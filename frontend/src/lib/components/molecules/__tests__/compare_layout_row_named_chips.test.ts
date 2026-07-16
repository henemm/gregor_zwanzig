// TDD RED — Issue #1267: CompareLayoutRow zeigt benannte Spalten-Chips
// (Ortsnamen) statt Zahlen-Chips ("1", "2", ...), Kopfzeile mit fettem
// Kanal-Namen + mono Constraint-Unterzeile (volle Design-Parität).
//
// Source-Inspection-Tests (KEIN Mock, KEIN jsdom-Mount — Projekt-Idiom, siehe
// compare_editor_layout_tab_wiring.test.ts / issue_683_wizard_remove.test.ts):
// Svelte-5-Komponenten sind ohne @testing-library/svelte (nicht in
// package.json) in diesem Test-Setup nicht mountbar — echtes DOM-Verhalten
// wird ergänzend über Playwright gegen Staging abgesichert (E2E-Verify).
//
// Spec: docs/specs/modules/issue_1267_compare_layout_row_named_chips.md
// Soll: claude-code-handoff/current/jsx/molecules.jsx:1236-1272 +
//       screen-compare-detail.jsx:260 (cols={sub.layout[ch] || []} — Array von Namen)
//
// RED-Erwartung (vor Implementierung): alle 4 Tests FAIL — cols ist noch
// `number`, Kopfzeile noch mono-uppercase ohne Constraint-Unterzeile.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/molecules/__tests__/compare_layout_row_named_chips.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const COMPONENT_FILE = join(here, '..', 'CompareLayoutRow.svelte');
const src = () => readFileSync(COMPONENT_FILE, 'utf-8');

test('#1267 AC-1: cols ist ein Namens-Array — kein Zahlen-Index-Chip-Loop mehr', () => {
	const s = src();
	assert.ok(
		!/Array\.from\(\{\s*length:\s*cols/.test(s),
		'CompareLayoutRow: alte Zahlen-Chip-Generierung (Array.from({length: cols}...)) noch vorhanden — cols muss ein Namens-Array sein, kein Count'
	);
	assert.match(
		s,
		/\{#each cols as \w+/,
		'CompareLayoutRow: kein #each-Loop, der direkt über das cols-Array (Namen) iteriert'
	);
});

test('#1267 AC-3: cols.length === 0 steuert den SMS-Sonderfall (Array-Vertrag statt Zahl)', () => {
	assert.match(
		src(),
		/cols\.length\s*===?\s*0/,
		'CompareLayoutRow: cols.length===0 SMS-Sonderfall-Bedingung (Array-Vertrag) fehlt'
	);
});

test('#1267 AC-4: Kopfzeile zeigt fetten Kanal-Namen (CHANNEL_LABEL) + Constraint-Unterzeile (CHANNEL_CONSTRAINT)', () => {
	const s = src();
	assert.match(s, /CHANNEL_LABEL/, 'CompareLayoutRow: CHANNEL_LABEL-Map fehlt');
	assert.match(s, /CHANNEL_CONSTRAINT/, 'CompareLayoutRow: CHANNEL_CONSTRAINT-Map fehlt');
	assert.match(s, /email/, 'CompareLayoutRow: email-Kanal fehlt in Label/Constraint-Map');
	assert.match(s, /telegram/, 'CompareLayoutRow: telegram-Kanal fehlt in Label/Constraint-Map');
	assert.match(s, /\bsms\b/i, 'CompareLayoutRow: sms-Kanal fehlt in Label/Constraint-Map');
	const labelBlock = s.match(/CHANNEL_LABEL\s*[:=][^;]*/is)?.[0] ?? '';
	assert.ok(
		labelBlock === '' || !/signal/i.test(labelBlock),
		'CompareLayoutRow: signal-Kanal darf in CHANNEL_LABEL nicht vorkommen (Issue #610 — Signal entfernt)'
	);
	assert.match(
		s,
		/font-weight[":=]\s*["']?600/,
		'CompareLayoutRow: fetter Kanal-Name (font-weight 600) für die Kopfzeile fehlt'
	);
});

test('#1267 AC-5 Regressionsschutz: erstes Chip bleibt tone=accent, restliche default', () => {
	const s = src();
	assert.match(s, /accent/, 'CompareLayoutRow: tone "accent" für erstes Chip fehlt');
	assert.match(s, /default/, 'CompareLayoutRow: tone "default" für restliche Chips fehlt');
});
