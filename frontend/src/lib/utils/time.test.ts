// TDD: Issue #231 — report_config Zeit-Format-Inkonsistenz HH:MM vs HH:MM:SS.
//
// Spec: docs/specs/modules/issue_231_time_format.md
//
// Ausfuehren:
//   cd frontend && node --experimental-strip-types --test src/lib/utils/time.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { toHHMMSS, HOUR_OPTIONS, toHourOption } from './time.ts';

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

// ── Issue #1379: Versandzeit-Auswahl auf volle Stunden ──────────────────────
// Die Auswahlliste im Briefing-Zeitplan (VTSchedulePlan) bietet ausschliesslich
// volle Stunden an; toHourOption bildet einen gespeicherten Wert auf den
// passenden Listeneintrag ab (reine Anzeige-Ableitung, kein Rueckschreiben).
// Spec: docs/specs/modules/versandzeit_stundenwahl.md (AC-1, AC-5)

test('AC-1: HOUR_OPTIONS enthaelt genau die 24 vollen Stunden 00:00..23:00', () => {
	assert.equal(HOUR_OPTIONS.length, 24);
	assert.equal(HOUR_OPTIONS[0], '00:00');
	assert.equal(HOUR_OPTIONS[7], '07:00');
	assert.equal(HOUR_OPTIONS[23], '23:00');
	// keine Minuten-Eintraege moeglich
	assert.ok(HOUR_OPTIONS.every((h) => /^\d{2}:00$/.test(h)));
	assert.equal(new Set(HOUR_OPTIONS).size, 24);
});

test('AC-1: toHourOption liefert fuer volle Stunden exakt den Listeneintrag', () => {
	assert.equal(toHourOption('07:00'), '07:00');
	assert.equal(toHourOption('00:00'), '00:00');
	assert.equal(toHourOption('23:00'), '23:00');
	assert.equal(toHourOption('18:00:00'), '18:00');
	assert.ok(HOUR_OPTIONS.includes(toHourOption('05:00')));
});

test('AC-5: Bestandswert mit Minuten wird auf seine Stunde gekappt (Truncate wie serverseitig)', () => {
	assert.equal(toHourOption('07:30'), '07:00');
	assert.equal(toHourOption('05:59'), '05:00');
	assert.equal(toHourOption('23:45:30'), '23:00');
	assert.equal(toHourOption('9:15'), '09:00');
});

test('AC-5: unbrauchbare Werte liefern den Vorgabe-Eintrag, nie leer, nie zufaellig', () => {
	assert.equal(toHourOption('', '07:00'), '07:00');
	assert.equal(toHourOption(undefined, '18:00'), '18:00');
	assert.equal(toHourOption(null, '18:00'), '18:00');
	assert.equal(toHourOption('kaputt', '07:00'), '07:00');
	assert.equal(toHourOption('99:00', '07:00'), '07:00');
	assert.equal(toHourOption('-1:00', '18:00'), '18:00');
	for (const i of ['07:30', '', 'kaputt', '99:00', '23:59', undefined, '00:01', '12:00:00']) {
		assert.ok(HOUR_OPTIONS.includes(toHourOption(i)), `${String(i)} -> kein Listeneintrag`);
	}
});
