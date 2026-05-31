// TDD RED — Issue #475: OutputLayoutEditor Organisms-Migration
//
// Spec: docs/specs/modules/issue_475_outputlayouteditor_organisms_migration.md
//
// Source-Inspection-Tests (kein Render, keine Mocks).
// RED: Alle Tests schlagen fehl, bis zur Implementierung.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/organisms/issue_475_organisms_migration.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');
const read = (f: string) => readFileSync(f, 'utf-8');

// ── AC-1: OutputLayoutEditor importiert kein ui/card ─────────────────────────

test('#475 AC-1: OutputLayoutEditor enthält keinen Import aus $lib/components/ui/card', () => {
	const src = read(join(root, 'shared', 'OutputLayoutEditor.svelte'));
	assert.ok(
		!src.includes("from '$lib/components/ui/card") &&
		!src.includes('from "$lib/components/ui/card'),
		'OutputLayoutEditor importiert noch $lib/components/ui/card — muss auf atoms/Card umgestellt werden.',
	);
});

test('#475 AC-1: OutputLayoutEditor enthält kein <Card.Root>', () => {
	const src = read(join(root, 'shared', 'OutputLayoutEditor.svelte'));
	assert.ok(
		!src.includes('<Card.Root>') && !src.includes('</Card.Root>'),
		'OutputLayoutEditor enthält noch <Card.Root> / </Card.Root> — muss auf <Card> / </Card> umgestellt werden.',
	);
});

test('#475 AC-1: OutputLayoutEditor importiert Card aus atoms/', () => {
	const src = read(join(root, 'shared', 'OutputLayoutEditor.svelte'));
	assert.ok(
		/import[^;]*\bCard\b[^;]*from\s+['"](\$lib\/components\/atoms|\.\.\/atoms\/Card\.svelte)['"]/.test(src),
		'OutputLayoutEditor muss Card aus atoms/ importieren.',
	);
});

// ── AC-2: organisms/index.ts re-exportiert OutputLayoutEditor ─────────────────

test('#475 AC-2: organisms/index.ts re-exportiert OutputLayoutEditor', () => {
	const src = read(join(here, 'index.ts'));
	assert.ok(
		src.includes('OutputLayoutEditor'),
		'organisms/index.ts enthält keinen Export für OutputLayoutEditor — Barrel-Eintrag fehlt.',
	);
});

// ── AC-3: Consumer-Imports zeigen auf organisms/ ──────────────────────────────

test('#475 AC-3: compare/steps/Step4Layout importiert OutputLayoutEditor aus organisms', () => {
	const src = read(join(root, 'compare', 'steps', 'Step4Layout.svelte'));
	assert.ok(
		/from\s+['"](\$lib\/components\/organisms)['"]/.test(src),
		'compare/steps/Step4Layout.svelte hat keinen Import aus $lib/components/organisms.',
	);
	assert.ok(
		!src.includes("from '$lib/components/shared/OutputLayoutEditor"),
		'compare/steps/Step4Layout.svelte importiert OutputLayoutEditor noch direkt aus shared/ — auf organisms umstellen.',
	);
});

test('#475 AC-3: trip-detail/WeatherMetricsTab importiert OutputLayoutEditor aus organisms', () => {
	const src = read(join(root, 'trip-detail', 'WeatherMetricsTab.svelte'));
	assert.ok(
		/from\s+['"](\$lib\/components\/organisms)['"]/.test(src),
		'trip-detail/WeatherMetricsTab.svelte hat keinen Import aus $lib/components/organisms.',
	);
	assert.ok(
		!src.includes("from '$lib/components/shared/OutputLayoutEditor"),
		'trip-detail/WeatherMetricsTab.svelte importiert OutputLayoutEditor noch direkt aus shared/ — auf organisms umstellen.',
	);
});

test('#475 AC-3: trip-wizard/steps/Step4Layout importiert OutputLayoutEditor aus organisms', () => {
	const src = read(join(root, 'trip-wizard', 'steps', 'Step4Layout.svelte'));
	assert.ok(
		/from\s+['"](\$lib\/components\/organisms)['"]/.test(src),
		'trip-wizard/steps/Step4Layout.svelte hat keinen Import aus $lib/components/organisms.',
	);
	assert.ok(
		!src.includes("from '$lib/components/shared/OutputLayoutEditor"),
		'trip-wizard/steps/Step4Layout.svelte importiert OutputLayoutEditor noch direkt aus shared/ — auf organisms umstellen.',
	);
});
