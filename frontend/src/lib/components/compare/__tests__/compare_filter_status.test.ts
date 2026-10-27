// Issue #2278 (AC-2): Filter-Pille eines Ortsvergleichs — gleiche Datumsregel wie beim Trip
// (Enddatum vor heute = fertig). end_date: beim Schreiben "", beim Lesen fehlend (beides = kein Ende).
//
// Ausfuehrung: cd frontend && npm test -- src/lib/components/compare/__tests__/compare_filter_status.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { compareFilterStatus } from '../subscriptionHelpers.ts';

const JETZT = new Date('2026-10-17T12:00:00');
const preset = (extra: Record<string, unknown> = {}) =>
	({ id: 'c', name: 'V', location_ids: ['a'], schedule: 'daily', ...extra }) as never;

test('ohne Enddatum (fehlt oder ""): aktiv bzw. pausiert', () => {
	assert.equal(compareFilterStatus(preset(), JETZT), 'aktiv');
	assert.equal(compareFilterStatus(preset({ end_date: '' }), JETZT), 'aktiv');
	assert.equal(compareFilterStatus(preset({ schedule: 'manual' }), JETZT), 'pausiert');
});

test('Enddatum vor heute = fertig, auch nach Auto-Pause; heute/Zukunft bleibt aktiv', () => {
	assert.equal(compareFilterStatus(preset({ end_date: '2026-10-16' }), JETZT), 'fertig');
	assert.equal(compareFilterStatus(preset({ end_date: '2026-10-16', paused_at: '2026-10-17T00:00:00Z' }), JETZT), 'fertig');
	assert.equal(compareFilterStatus(preset({ end_date: '2026-10-17' }), JETZT), 'aktiv');
	assert.equal(compareFilterStatus(preset({ end_date: '2027-01-01' }), JETZT), 'aktiv');
});

test('Entwurf: in keiner Pille (nur unter "Alle")', () => {
	assert.equal(compareFilterStatus(preset({ location_ids: [] }), JETZT), null);
});
