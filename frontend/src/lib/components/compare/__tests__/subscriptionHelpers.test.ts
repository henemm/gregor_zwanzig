// TDD RED — Issue #301 Lieferung B: subscriptionHelpers (Extraktion aus
// CompareSubscriptionsPanel.svelte für AutoReportCard).
//
// RED-by-import: das Modul ../subscriptionHelpers.ts existiert noch nicht,
// daher schlägt der Import von scheduleLabel/locationsLabel/formatLastRun fehl.
// Der GREEN-Schritt ist ein reines Verschieben der heute inline in
// CompareSubscriptionsPanel.svelte (Z. 16–39) lebenden Helfer.
//
// Spec: docs/specs/modules/issue_301b_auto_reports_overview.md (§1)
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/subscriptionHelpers.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { scheduleLabel, locationsLabel, formatLastRun } from '../subscriptionHelpers.ts';
import type { Subscription } from '../../../types.ts';

// ─── Fixtures (echte Subscription-Objekte, keine Mocks) ──────────────────────

function makeSub(overrides: Partial<Subscription> = {}): Subscription {
	return {
		id: 'sub-1',
		name: 'Test-Abo',
		enabled: true,
		locations: ['*'],
		forecast_hours: 24,
		time_window_start: 6,
		time_window_end: 18,
		schedule: 'daily_morning',
		weekday: 0,
		include_hourly: false,
		top_n: 3,
		send_email: true,
		send_signal: false,
		send_telegram: false,
		...overrides
	};
}

// ─── scheduleLabel ───────────────────────────────────────────────────────────

test('scheduleLabel: daily_morning → "Täglich 07:00"', () => {
	assert.equal(scheduleLabel(makeSub({ schedule: 'daily_morning' })), 'Täglich 07:00');
});

test('scheduleLabel: daily_evening → "Täglich 18:00"', () => {
	assert.equal(scheduleLabel(makeSub({ schedule: 'daily_evening' })), 'Täglich 18:00');
});

// Konvention 0=Montag (SubscriptionForm.svelte:19 + subscriptions/+page.svelte:19).
test('scheduleLabel: weekly + weekday=0 → "Wöchentlich Montag"', () => {
	assert.equal(scheduleLabel(makeSub({ schedule: 'weekly', weekday: 0 })), 'Wöchentlich Montag');
});

test('scheduleLabel: weekly + weekday=1 → "Wöchentlich Dienstag"', () => {
	assert.equal(scheduleLabel(makeSub({ schedule: 'weekly', weekday: 1 })), 'Wöchentlich Dienstag');
});

test('scheduleLabel: weekly + weekday=4 → "Wöchentlich Freitag"', () => {
	assert.equal(scheduleLabel(makeSub({ schedule: 'weekly', weekday: 4 })), 'Wöchentlich Freitag');
});

test('scheduleLabel: weekly + weekday=7 (OOB) → "Wöchentlich " ohne "undefined"', () => {
	assert.equal(scheduleLabel(makeSub({ schedule: 'weekly', weekday: 7 })), 'Wöchentlich ');
});

test('scheduleLabel: unbekannter schedule → roher schedule-Wert', () => {
	// Bewusst ungültiger Wert: die Funktion fällt auf sub.schedule zurück.
	const sub = makeSub({ schedule: 'monthly' as Subscription['schedule'] });
	assert.equal(scheduleLabel(sub), 'monthly');
});

// ─── locationsLabel ──────────────────────────────────────────────────────────

test('locationsLabel: ["*"] → "Alle Orte"', () => {
	assert.equal(locationsLabel(makeSub({ locations: ['*'] })), 'Alle Orte');
});

test('locationsLabel: leeres Array → "Alle Orte"', () => {
	assert.equal(locationsLabel(makeSub({ locations: [] })), 'Alle Orte');
});

test('locationsLabel: ["a","b"] → "2 Orte"', () => {
	assert.equal(locationsLabel(makeSub({ locations: ['a', 'b'] })), '2 Orte');
});

// ─── formatLastRun ───────────────────────────────────────────────────────────

test('formatLastRun: undefined → leerer String', () => {
	assert.equal(formatLastRun(undefined), '');
});

test('formatLastRun: gültiger ISO-Timestamp → nicht-leerer String mit Jahreszahl', () => {
	const out = formatLastRun('2026-05-23T07:00:00Z');
	assert.notEqual(out, '');
	assert.match(out, /2026/);
});

test('formatLastRun: ungültiges Datum → leerer String (kein Crash)', () => {
	assert.equal(formatLastRun('not-a-date'), '');
});
