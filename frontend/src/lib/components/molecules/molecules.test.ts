// TDD RED: Issue #372 — Molecules-Schicht lib/components/molecules/
//
// Spec: docs/specs/modules/issue_372_molecules.md
// Vorlage: docs/design-requests/issue_15_atomic_design/spec/molecules.jsx
//
// Source-Inspection-Test (kein Render, keine Mocks): Datei-Existenz, index.ts-
// Re-Exporte, Schluessel-Verhalten (dense/Card, Em-Dash, Varianten, Atom-Importe).
//
// RED vor Implementierung: molecules/-Dateien fehlen → Asserts schlagen fehl.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test src/lib/components/molecules/molecules.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const read = (f: string) => readFileSync(join(here, f), 'utf-8');
const has = (f: string) => existsSync(join(here, f));

const ALL_10 = [
	'Field', 'DetailRow', 'StagePill', 'ChannelRow', 'ChannelChip',
	'BriefingTimelineRow', 'BriefingScheduleRow', 'ThresholdRow', 'Stat', 'AlertRow',
];

test('#372 AC-1: alle 10 Molecule-Dateien existieren in molecules/', () => {
	for (const name of ALL_10) {
		assert.ok(has(`${name}.svelte`), `molecules/${name}.svelte fehlt`);
	}
	assert.ok(has('index.ts'), 'molecules/index.ts fehlt');
});

test('#372 AC-1: index.ts re-exportiert alle 10 Molecules', () => {
	const idx = read('index.ts');
	for (const name of ALL_10) {
		assert.ok(new RegExp(`\\b${name}\\b`).test(idx), `index.ts exportiert ${name} nicht`);
	}
});

test('#372 AC-2: ChannelRow dense/Card-Layout + nutzt Switch', () => {
	const cr = read('ChannelRow.svelte');
	assert.ok(/dense/.test(cr), 'ChannelRow dense-Prop fehlt');
	assert.ok(/g-card-alt/.test(cr), 'ChannelRow Card-Layout (--g-card-alt) fehlt');
	assert.ok(/g-rule-soft/.test(cr), 'ChannelRow dense bottom-border (--g-rule-soft) fehlt');
	assert.ok(/Switch/.test(cr), 'ChannelRow nutzt Switch-Atom nicht');
});

test('#372 AC-3: Stat Em-Dash bei leerem Wert + layout/size', () => {
	const stat = read('Stat.svelte');
	assert.ok(/—|\\u2014|&mdash;/.test(stat), 'Stat Em-Dash-Fallback fehlt');
	assert.ok(/stack/.test(stat) && /inline/.test(stat), 'Stat layout stack|inline fehlt');
	assert.ok(/sm/.test(stat) && /lg/.test(stat), 'Stat size sm|lg fehlt');
});

test('#372 AC-4: AlertRow 3 Varianten + StagePill data-state', () => {
	const ar = read('AlertRow.svelte');
	for (const v of ['icon', 'dot', 'plain']) {
		assert.ok(ar.includes(v), `AlertRow variant "${v}" fehlt`);
	}
	const sp = read('StagePill.svelte');
	assert.ok(/data-state/.test(sp), 'StagePill data-state fehlt');
});

test('#372 AC-5: Molecules importieren Atome aus atoms/ (keine Inline-Duplikate)', () => {
	const wantsAtom: Record<string, string> = {
		'BriefingScheduleRow': 'Switch',
		'BriefingTimelineRow': 'ChannelChip',
		'AlertRow': 'WIcon',
	};
	for (const [mol, atom] of Object.entries(wantsAtom)) {
		const src = read(`${mol}.svelte`);
		// F001 (Adversary): echten import verlangen (default ODER named), nicht bloße Erwähnung.
		assert.ok(new RegExp(`import\\b[^;]*\\b${atom}\\b[^;]*\\bfrom\\b`).test(src), `${mol} importiert ${atom} nicht (echter import erforderlich)`);
	}
});

test('#372 AC-5/6: SSR-fest + Token-basiert', () => {
	for (const name of ALL_10) {
		if (!has(`${name}.svelte`)) continue;
		const src = read(`${name}.svelte`);
		const hasRaw = /\b(window|document)\./.test(src);
		const hasGuard = /browser|onMount/.test(src);
		assert.ok(!hasRaw || hasGuard, `${name}: ungeschuetzter window/document-Zugriff (nicht SSR-fest)`);
		assert.ok(/var\(--g-/.test(src), `${name}: nutzt keine --g-*-Tokens`);
	}
});
