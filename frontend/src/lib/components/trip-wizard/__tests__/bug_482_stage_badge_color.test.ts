// TDD RED — Bug #482: Etappen-Badge blau statt orange in Wizard Step 2.
// SPEC: docs/specs/modules/bug_482_stage_badge_color.md
//
// Root Cause: StageRow.svelte:77 verwendet tone="info" (blau) statt tone="accent" (orange).
//
// AC-1: Der Etappen-Badge nutzt tone="accent" (orange, --g-accent #c45a2a).
// AC-2: Der Quellcode enthält kein tone="info" für die Stage-Nummer-Pill.
//
// Diese Tests MÜSSEN in der RED-Phase SCHEITERN, weil StageRow.svelte
// noch tone="info" enthält.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-wizard/__tests__/bug_482_stage_badge_color.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const STAGE_ROW = join(here, '..', 'steps', 'StageRow.svelte');

function read(p: string): string {
	return readFileSync(p, 'utf-8');
}

// =============================================================================
// AC-1: Stage-Nummer-Pill nutzt tone="accent" (orange)
// =============================================================================

test('AC-1: StageRow verwendet tone="accent" für die Stage-Nummer-Pill', () => {
	const src = read(STAGE_ROW);
	assert.ok(
		src.includes('tone="accent"'),
		'StageRow.svelte enthält kein tone="accent" — Badge erscheint nicht orange'
	);
});

// =============================================================================
// AC-2: tone="info" kommt nicht für die Stage-Nummer-Pill vor
// =============================================================================

test('AC-2: StageRow enthält kein tone="info" (wäre blau, falscher Token)', () => {
	const src = read(STAGE_ROW);
	assert.ok(
		!src.includes('tone="info"'),
		'StageRow.svelte enthält noch tone="info" — Badge wird blau dargestellt'
	);
});
