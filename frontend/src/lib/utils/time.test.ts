// TDD: Issue #231 — report_config Zeit-Format-Inkonsistenz HH:MM vs HH:MM:SS.
//
// Spec: docs/specs/modules/issue_231_time_format.md
//
// Ausfuehren:
//   cd frontend && node --experimental-strip-types --test src/lib/utils/time.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { toHHMMSS } from './time.ts';

test('AC-1.1: toHHMMSS — HH:MM -> HH:MM:SS', () => {
	assert.equal(toHHMMSS('07:00'), '07:00:00');
	assert.equal(toHHMMSS('18:30'), '18:30:00');
});

test('AC-1.2: toHHMMSS — bereits HH:MM:SS bleibt unveraendert', () => {
	assert.equal(toHHMMSS('07:00:00'), '07:00:00');
});

test('AC-1.3: toHHMMSS — leerer String wird durchgereicht', () => {
	assert.equal(toHHMMSS(''), '');
});

test('AC-1.4: toHHMMSS — undefined wird durchgereicht', () => {
	assert.equal(toHHMMSS(undefined), undefined);
});

test('AC-1.5: toHHMMSS — unbekanntes Format wird durchgereicht (kein Crash)', () => {
	assert.equal(toHHMMSS('invalid'), 'invalid');
});
