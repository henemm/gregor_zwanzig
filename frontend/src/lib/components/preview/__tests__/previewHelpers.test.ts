// TDD RED: Issue #189 — Preview-Tab-Integration: Pure-Function-Tests
//
// Spec: docs/specs/modules/issue_189_preview_tab_integration.md
// Master: docs/specs/modules/epic_140_output_vorschau.md
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/preview/__tests__/previewHelpers.test.ts
//
// Diese Tests decken AC-1 (Initial-Default), AC-6 (charCountStatus-Schwellen)
// und AC-7 (URL-Builder) ab. Die Komponenten-ACs (AC-2..AC-5, AC-8) werden
// in Phase 7 (Validation) per E2E-Hook gegen den laufenden Server verifiziert
// — gleiches Muster wie bei Issue #183 (headerStats.test.ts).

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
	buildPreviewUrl,
	defaultReportType,
	charCountStatus,
	type ReportType
} from '../previewHelpers.ts';

// ============================================================================
// AC-7: buildPreviewUrl — URL-Generierung
// ============================================================================

test('AC-7: buildPreviewUrl(email, gr20, morning) ohne date → kein date-Param', () => {
	assert.equal(
		buildPreviewUrl('email', 'gr20', 'morning'),
		'/api/preview/gr20/email?type=morning'
	);
});

test('AC-7: buildPreviewUrl(sms, gr20, evening, 2026-05-20) → date als Query', () => {
	assert.equal(
		buildPreviewUrl('sms', 'gr20', 'evening', '2026-05-20'),
		'/api/preview/gr20/sms?type=evening&date=2026-05-20'
	);
});

test('AC-7: buildPreviewUrl encodet trip_id mit Sonderzeichen', () => {
	assert.equal(
		buildPreviewUrl('email', 'tour/2026', 'morning'),
		'/api/preview/tour%2F2026/email?type=morning'
	);
});

test('AC-7: buildPreviewUrl unterscheidet zwischen email und sms Kanal', () => {
	assert.equal(
		buildPreviewUrl('email', 'x', 'morning'),
		'/api/preview/x/email?type=morning'
	);
	assert.equal(
		buildPreviewUrl('sms', 'x', 'morning'),
		'/api/preview/x/sms?type=morning'
	);
});

// ============================================================================
// AC-1: defaultReportType — Initial-Default für Morning/Evening
// ============================================================================

test('AC-1: defaultReportType vor 14:00 lokal → morning', () => {
	const d = new Date('2026-05-16T10:00:00');
	assert.equal(defaultReportType(d), 'morning');
});

test('AC-1: defaultReportType genau 14:00 → evening (Grenze)', () => {
	const d = new Date('2026-05-16T14:00:00');
	assert.equal(defaultReportType(d), 'evening');
});

test('AC-1: defaultReportType nach 14:00 → evening', () => {
	const d = new Date('2026-05-16T18:30:00');
	assert.equal(defaultReportType(d), 'evening');
});

test('AC-1: defaultReportType ganz früh 00:30 → morning', () => {
	const d = new Date('2026-05-16T00:30:00');
	assert.equal(defaultReportType(d), 'morning');
});

// ============================================================================
// AC-6: charCountStatus — Schwellen ok / warn / over
// ============================================================================

test('AC-6: charCountStatus für ≤144 Zeichen → ok', () => {
	assert.equal(charCountStatus(0), 'ok');
	assert.equal(charCountStatus(100), 'ok');
	assert.equal(charCountStatus(144), 'ok');
});

test('AC-6: charCountStatus für 145..160 Zeichen → warn (Warn-Puffer)', () => {
	assert.equal(charCountStatus(145), 'warn');
	assert.equal(charCountStatus(150), 'warn');
	assert.equal(charCountStatus(160), 'warn');
});

test('AC-6: charCountStatus für ≥161 Zeichen → over (Limit überschritten)', () => {
	assert.equal(charCountStatus(161), 'over');
	assert.equal(charCountStatus(200), 'over');
	assert.equal(charCountStatus(500), 'over');
});

test('AC-6: charCountStatus respektiert custom limit', () => {
	// limit=80 → warn-Schwelle bei n > 64 (limit - 16), over bei n > 80
	assert.equal(charCountStatus(50, 80), 'ok');
	assert.equal(charCountStatus(64, 80), 'ok');
	assert.equal(charCountStatus(65, 80), 'warn');
	assert.equal(charCountStatus(80, 80), 'warn');
	assert.equal(charCountStatus(81, 80), 'over');
});

// ============================================================================
// Typ-Sanity: ReportType-Werte sind exakt das erwartete Literal-Paar
// ============================================================================

test('AC-1: ReportType-Type lässt nur morning|evening zu (Compile-Sanity)', () => {
	const morning: ReportType = 'morning';
	const evening: ReportType = 'evening';
	assert.equal(morning, 'morning');
	assert.equal(evening, 'evening');
});
