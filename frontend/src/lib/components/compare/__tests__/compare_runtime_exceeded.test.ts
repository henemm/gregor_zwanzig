// TDD — Issue #1250 Scheibe 3 "Auto-Pause bei end_date" (AC-12).
//
// Spec: docs/specs/modules/issue_1250_briefing_subscription.md, AC-10–AC-12.
//
// isRuntimeExceeded() liefert true gdw. ein Compare-Preset per Auto-Pause
// pausiert wurde (paused_at gesetzt) UND sein end_date (datumsmaessig, ohne
// Uhrzeit) vor heute liegt — die Grundlage fuer den Hub-Hinweis "Laufzeit
// überschritten" (kein eigenes Backend-Feld, rein abgeleitet).
//
// KEIN DOM/Browser — reine Ableitungsfunktion, lauffaehig unter
// node --experimental-strip-types.

import { describe, test } from 'node:test';
import assert from 'node:assert/strict';
import type { ComparePreset } from '../../../types.ts';
import { isRuntimeExceeded } from '../subscriptionHelpers.ts';

function makePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cmp-1',
		name: 'Skigebiete Tirol',
		location_ids: ['loc-1', 'loc-2'],
		schedule: 'manual',
		profil: 'wintersport',
		hour_from: 6,
		hour_to: 9,
		empfaenger: ['urlauber@example.com'],
		forecast_hours: 48,
		created_at: '2026-01-01T00:00:00Z',
		display_config: {},
		...overrides
	};
}

function isoDateOffset(days: number): string {
	const d = new Date();
	d.setHours(0, 0, 0, 0);
	d.setDate(d.getDate() + days);
	return d.toISOString().slice(0, 10);
}

describe('isRuntimeExceeded — AC-12: Hub-Hinweis "Laufzeit überschritten"', () => {
	test('paused_at gesetzt + end_date gestern -> true', () => {
		const preset = makePreset({
			paused_at: '2026-07-15T06:00:00Z',
			end_date: isoDateOffset(-1)
		});
		assert.strictEqual(isRuntimeExceeded(preset), true);
	});

	test('kein paused_at (nicht pausiert) -> false, auch bei abgelaufenem end_date', () => {
		const preset = makePreset({ end_date: isoDateOffset(-1) });
		assert.strictEqual(isRuntimeExceeded(preset), false);
	});

	test('paused_at gesetzt, aber end_date in der Zukunft -> false', () => {
		const preset = makePreset({
			paused_at: '2026-07-15T06:00:00Z',
			end_date: isoDateOffset(1)
		});
		assert.strictEqual(isRuntimeExceeded(preset), false);
	});

	test('paused_at gesetzt, aber kein end_date -> false', () => {
		const preset = makePreset({ paused_at: '2026-07-15T06:00:00Z' });
		assert.strictEqual(isRuntimeExceeded(preset), false);
	});

	test('kein paused_at UND kein end_date -> false', () => {
		const preset = makePreset();
		assert.strictEqual(isRuntimeExceeded(preset), false);
	});
});
