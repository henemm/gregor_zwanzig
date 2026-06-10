// RED-Tests fuer Issue #687 — Kanal-pro-Alert-Logik im Alert-Regel-Editor.
//
// Spec: docs/specs/modules/issue_687_alert_editor_soll_ist.md
//
// Pure-Function-Extraktion (analog expandRules, Issue #179/#297): die
// Kanal-Vererbungs- und Toggle-Logik wird testbar aus AlertRuleRow.svelte
// herausgezogen. effectiveAlertChannels() spiegelt die AlertCard-Logik (#638):
// leere/fehlende rule.channels => "erbt alle aktiven Briefing-Kanaele".
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/alert-rules-editor/alertChannels.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { effectiveAlertChannels, toggleAlertChannel } from './alertChannels.ts';
import type { AlertRule } from '$lib/types';

function baseRule(overrides: Partial<AlertRule> = {}): AlertRule {
	return {
		id: 'r1',
		kind: 'absolute',
		metric: 'wind_gust',
		threshold: 50,
		unit: 'km/h',
		severity: 'warning',
		enabled: true,
		...overrides
	};
}

// --- effectiveAlertChannels: Vererbung (AC-3) ---

test('effectiveAlertChannels: leere channels erbt alle aktiven Briefing-Kanaele', () => {
	const rule = baseRule({ channels: [] });
	assert.deepEqual(effectiveAlertChannels(rule, ['email', 'telegram']), ['email', 'telegram']);
});

test('effectiveAlertChannels: fehlendes channels-Feld erbt alle aktiven Kanaele', () => {
	const rule = baseRule(); // kein channels
	assert.deepEqual(effectiveAlertChannels(rule, ['email', 'telegram']), ['email', 'telegram']);
});

test('effectiveAlertChannels: explizite channels werden zurueckgegeben (keine Vererbung)', () => {
	const rule = baseRule({ channels: ['email'] });
	assert.deepEqual(effectiveAlertChannels(rule, ['email', 'telegram', 'sms']), ['email']);
});

// --- toggleAlertChannel: Umschalten (AC-4) ---

test('toggleAlertChannel: aktiven Kanal abwaehlen entfernt ihn', () => {
	const rule = baseRule({ channels: ['email', 'telegram'] });
	const next = toggleAlertChannel(rule, 'telegram', ['email', 'telegram', 'sms']);
	assert.deepEqual(next.channels, ['email']);
});

test('toggleAlertChannel: inaktiven Kanal anwaehlen fuegt ihn hinzu', () => {
	const rule = baseRule({ channels: ['email'] });
	const next = toggleAlertChannel(rule, 'sms', ['email', 'telegram', 'sms']);
	assert.deepEqual(next.channels, ['email', 'sms']);
});

test('toggleAlertChannel: erstes Toggle materialisiert die geerbten Kanaele minus dem abgewaehlten', () => {
	// rule erbt (channels leer) email+telegram; Telegram abwaehlen => nur email bleibt.
	const rule = baseRule({ channels: [] });
	const next = toggleAlertChannel(rule, 'telegram', ['email', 'telegram']);
	assert.deepEqual(next.channels, ['email']);
});

// --- Immutabilitaet + Datenerhalt (AC-5) ---

test('toggleAlertChannel: laesst die Original-Regel unveraendert (immutabel)', () => {
	const rule = baseRule({ channels: ['email', 'telegram'] });
	const snapshot = JSON.stringify(rule);
	toggleAlertChannel(rule, 'telegram', ['email', 'telegram']);
	assert.equal(JSON.stringify(rule), snapshot);
});

test('toggleAlertChannel: erhaelt severity und alle uebrigen Felder (kein Datenverlust)', () => {
	const rule = baseRule({ channels: ['email'], severity: 'info', kind: 'delta', threshold: 12 });
	const next = toggleAlertChannel(rule, 'telegram', ['email', 'telegram']);
	assert.equal(next.severity, 'info');
	assert.equal(next.kind, 'delta');
	assert.equal(next.threshold, 12);
	assert.equal(next.metric, 'wind_gust');
	assert.equal(next.id, 'r1');
});
