// TDD RED: Issue #504 — Begriff „Wachhund" aus UI entfernen
//
// Spec: docs/specs/modules/issue_504_wachhund_to_alerts.md
//
// AC-1: Kartentitel ist "Alarm-Schwellen" (war: "Wachhund-Schwellen")
// AC-2: Kein "Wachhund" in TripOverview.svelte
// AC-3: Kein "Wachhund" in Testbeschreibungen der Begleit-Testdatei
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-detail/TripOverview.issue504.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const COMPONENT = join(here, 'TripOverview.svelte');
const TEST_487 = join(here, 'TripOverview.issue487.test.ts');

const source = readFileSync(COMPONENT, 'utf8');
const test487 = readFileSync(TEST_487, 'utf8');

// ─────────────────────────────────────────────────────────────
// AC-1: Kartentitel ist "Alarm-Schwellen"
// ─────────────────────────────────────────────────────────────

describe('AC-1: Kartentitel ist "Alarm-Schwellen"', () => {
	test('title-Prop enthält "Alarm-Schwellen"', () => {
		assert.ok(
			source.includes('title="Alarm-Schwellen"'),
			'TripOverview.svelte muss title="Alarm-Schwellen" enthalten (war: "Wachhund-Schwellen")'
		);
	});
});

// ─────────────────────────────────────────────────────────────
// AC-2: Kein "Wachhund" in TripOverview.svelte
// ─────────────────────────────────────────────────────────────

describe('AC-2: Kein "Wachhund" in der Svelte-Komponente', () => {
	test('weder im Template noch in Kommentaren', () => {
		assert.ok(
			!source.includes('Wachhund'),
			'TripOverview.svelte darf den Begriff "Wachhund" nicht mehr enthalten'
		);
	});
});

// ─────────────────────────────────────────────────────────────
// AC-3: Kein "Wachhund" in Testbeschreibungen (issue487.test.ts)
// ─────────────────────────────────────────────────────────────

describe('AC-3: Kein "Wachhund" in TripOverview.issue487.test.ts', () => {
	test('Test-Beschreibungen nutzen "Alarm-Schwellen" statt "Wachhund-Schwellen"', () => {
		assert.ok(
			!test487.includes('Wachhund'),
			'TripOverview.issue487.test.ts darf den Begriff "Wachhund" nicht mehr enthalten'
		);
	});
});
