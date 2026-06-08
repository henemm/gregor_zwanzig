// TDD RED: Issue #647 — Home-Screen Fidelity Nachzügler (Compare-Outbox-Timeline).
//
// Spec: docs/specs/modules/issue_647_home_fidelity.md
//
// Verhaltenstests (kein Mock, kein Dateiinhalt-Check) gegen die NEUE Pure-Function
// `homeCompareTimeline(preset, now)` in routes/_home/cockpitHelpers.ts. Sie baut die
// Versand-Timeline (Zuletzt/Nächster) für die Compare-Outbox aus echten DTO-Feldern.
//
// RED vor Implementierung: Funktion fehlt → Import/Aufruf schlägt fehl.
//
// Ausführung (standalone, Lehre #665):
//   cd frontend && node --experimental-strip-types --test src/lib/issue_647_home_fidelity.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { homeCompareTimeline } from '../routes/_home/cockpitHelpers.ts';
import type { ComparePreset } from './types.ts';

function makeCompare(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cp-1',
		name: 'Skigebiet Vergleich',
		location_ids: ['loc-1', 'loc-2', 'loc-3'],
		schedule: 'daily',
		hour_from: 6,
		hour_to: 8,
		empfaenger: ['mail', 'telegram'],
		profil: 'winter_skiing' as never,
		created_at: '2026-01-01T00:00:00Z',
		...overrides
	} as ComparePreset;
}

// ─── AC-1: Preset MIT letzter_versand → zwei Zeilen (Zuletzt sent + Nächster planned) ──

test('AC-1: homeCompareTimeline liefert Zuletzt+Nächster wenn letzter_versand gesetzt ist', () => {
	const now = new Date('2026-06-05T04:00:00'); // vor 06:00 → Nächster heute
	const preset = makeCompare({ letzter_versand: '2026-06-04T06:00:00Z' });

	const rows = homeCompareTimeline(preset, now);

	assert.strictEqual(rows.length, 2, 'muss genau zwei Zeilen liefern');

	const sent = rows[0];
	assert.ok(sent.when.startsWith('Zuletzt · '), 'erste Zeile beginnt mit "Zuletzt · "');
	assert.strictEqual(sent.status, 'sent', 'erste Zeile status=sent');
	assert.deepStrictEqual(sent.channels, preset.empfaenger, 'channels = empfaenger');
	assert.ok(sent.etappe && sent.etappe.includes('3 Orte'), 'etappe nennt Orte-Anzahl');

	const next = rows[1];
	assert.ok(next.when.startsWith('Nächster · '), 'zweite Zeile beginnt mit "Nächster · "');
	assert.strictEqual(next.status, 'planned', 'zweite Zeile status=planned');
	assert.deepStrictEqual(next.channels, preset.empfaenger, 'channels = empfaenger');
});

// ─── AC-2: Preset OHNE letzter_versand → keine Zuletzt-Zeile, keine Fake-Daten ─────────

test('AC-2: homeCompareTimeline erfindet keine Zuletzt-Zeile wenn nie gesendet wurde', () => {
	const now = new Date('2026-06-05T04:00:00');
	const preset = makeCompare({ letzter_versand: undefined });

	const rows = homeCompareTimeline(preset, now);

	assert.ok(
		rows.every((r) => r.status !== 'sent'),
		'keine Zeile mit status=sent ohne echte Historie'
	);
	assert.ok(
		rows.every((r) => !r.when.startsWith('Zuletzt')),
		'keine "Zuletzt"-Zeile ohne letzter_versand'
	);
	// Es bleibt mindestens die "Nächster"-Zeile (daily → berechenbar).
	assert.ok(
		rows.some((r) => r.when.startsWith('Nächster · ') && r.status === 'planned'),
		'Nächster-Zeile aus deriveNextSend bleibt erhalten'
	);
});
