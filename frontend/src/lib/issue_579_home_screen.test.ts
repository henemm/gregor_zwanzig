// Issue #579 — Home-Screen 1:1 nach JSX
//
// Spec: docs/specs/modules/issue_579_home_screen.md
//
// Verhaltens-Test für die reine Funktion plannedBriefings in cockpitHelpers.ts
// (AC-8: Briefing-Zeit ohne Sekunden). Die ursprünglichen Source-Inspection-Tests
// (readFileSync gegen +page.svelte / cockpitHelpers.ts) wurden entfernt —
// Dateiinhalt-Checks sind laut CLAUDE.md verboten (Präzedenz #893).
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/lib/issue_579_home_screen.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { plannedBriefings } from '../routes/_home/cockpitHelpers.ts';
import type { ReportConfig } from './types.ts';

// ─── AC-8: Briefing-Zeit ohne Sekunden ────────────────────────────────────────

test('AC-8: plannedBriefings kürzt morning_time HH:MM:SS auf HH:MM', () => {
	const rc: ReportConfig = {
		morning_enabled: true,
		morning_time: '07:00:00',
		evening_enabled: false,
		send_email: true,
	} as ReportConfig;
	const result = plannedBriefings(rc);
	assert.equal(result.length, 1, 'Genau eine Briefing-Row erwartet');
	assert.equal(result[0].when, '07:00', `morning_time muss als "07:00" kommen, war: "${result[0].when}"`);
});

test('AC-8: plannedBriefings kürzt evening_time HH:MM:SS auf HH:MM', () => {
	const rc: ReportConfig = {
		morning_enabled: false,
		evening_enabled: true,
		evening_time: '18:30:00',
		send_email: true,
	} as ReportConfig;
	const result = plannedBriefings(rc);
	assert.equal(result[0].when, '18:30', `evening_time muss als "18:30" kommen, war: "${result[0].when}"`);
});
