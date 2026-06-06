// TDD RED: Issue #610 — Signal-Kanal app-weit aus dem Frontend entfernen
//
// Spec: docs/specs/modules/bug_610_signal_frontend.md
//
// Diese Tests sind ABSICHTLICH ROT solange Signal noch im Code existiert.
// Sie werden GRÜN nachdem die Implementierung abgeschlossen ist.
//
// Abgedeckte ACs:
//   AC-3: reportChannels() darf 'signal' nicht mehr aus send_signal=true ableiten.
//   AC-4: CHANNEL_COL_BUDGET darf keinen 'signal'-Schlüssel mehr enthalten.
//         channelOverflow() darf kein signal-Feld mehr zurückgeben.
//
// Nicht hier testbar (reiner TypeScript-Typ, kein Laufzeitverhalten):
//   previewHelpers buildPreviewUrl — 'signal' ist nur im TS-Union-Typ gelistet;
//   die Funktion baut jeden String direkt in die URL ein, es gibt keinen
//   Runtime-Branch der 'signal' ablehnen oder anders behandeln würde.
//   Die Entfernung von 'signal' aus dem Union-Typ wird durch `npm run check`
//   (svelte-check) als AC-4 verifiziert — kein sinnvoller node:test möglich.
//
// Ausführen (aus frontend/):
//   node --experimental-strip-types --test \
//     src/lib/__tests__/issue_610_signal_removal_red.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { reportChannels } from '../../routes/_home/cockpitHelpers.ts';
import {
	CHANNEL_COL_BUDGET,
	channelOverflow,
} from '../components/trip-detail/metricsEditor.ts';

// ============================================================================
// AC-3: reportChannels — send_signal darf 'signal' nicht mehr ableiten
// ============================================================================

test('#610 AC-3: reportChannels mit send_signal=true enthält kein "signal" mehr', () => {
	// Minimales ReportConfig-Objekt: nur send_signal gesetzt.
	// Nach der Implementierung darf 'signal' nicht mehr im Ergebnis erscheinen.
	const rc = {
		send_email: false,
		send_signal: true,
		send_telegram: false,
		send_sms: false,
		morning_enabled: false,
		evening_enabled: false,
	};
	const channels = reportChannels(rc as Parameters<typeof reportChannels>[0]);
	assert.ok(
		!channels.includes('signal'),
		`reportChannels darf 'signal' nicht enthalten, war: [${channels.join(', ')}]`
	);
});

test('#610 AC-3: reportChannels mit allen Kanälen true enthält nur email/telegram/sms', () => {
	const rc = {
		send_email: true,
		send_signal: true,
		send_telegram: true,
		send_sms: true,
		morning_enabled: false,
		evening_enabled: false,
	};
	const channels = reportChannels(rc as Parameters<typeof reportChannels>[0]);
	assert.ok(!channels.includes('signal'), `'signal' darf nicht enthalten sein, war: [${channels.join(', ')}]`);
	// Die drei gültigen Kanäle müssen weiterhin enthalten sein
	assert.ok(channels.includes('email'), `'email' muss enthalten sein`);
	assert.ok(channels.includes('telegram'), `'telegram' muss enthalten sein`);
	assert.ok(channels.includes('sms'), `'sms' muss enthalten sein`);
});

test('#610 AC-3: reportChannels mit send_signal=false und email=true liefert nur email', () => {
	const rc = {
		send_email: true,
		send_signal: false,
		send_telegram: false,
		send_sms: false,
		morning_enabled: false,
		evening_enabled: false,
	};
	const channels = reportChannels(rc as Parameters<typeof reportChannels>[0]);
	assert.deepEqual(channels, ['email']);
});

// ============================================================================
// AC-4: CHANNEL_COL_BUDGET — kein 'signal'-Schlüssel mehr
// ============================================================================

test('#610 AC-4: CHANNEL_COL_BUDGET hat keinen "signal"-Schlüssel', () => {
	const keys = Object.keys(CHANNEL_COL_BUDGET);
	assert.ok(
		!keys.includes('signal'),
		`CHANNEL_COL_BUDGET darf 'signal' nicht enthalten, Schlüssel: [${keys.join(', ')}]`
	);
});

test('#610 AC-4: CHANNEL_COL_BUDGET enthält genau email, telegram, sms', () => {
	const keys = Object.keys(CHANNEL_COL_BUDGET).sort();
	assert.deepEqual(
		keys,
		['email', 'sms', 'telegram'],
		`Erwartet [email, sms, telegram], war: [${keys.join(', ')}]`
	);
});

// ============================================================================
// AC-4: channelOverflow — kein signal-Feld mehr
// ============================================================================

test('#610 AC-4: channelOverflow gibt kein "signal"-Feld zurück', () => {
	const overflow = channelOverflow(3);
	assert.ok(
		!('signal' in overflow),
		`channelOverflow darf kein 'signal'-Feld enthalten, Felder: [${Object.keys(overflow).join(', ')}]`
	);
});

test('#610 AC-4: channelOverflow liefert nur email/telegram/sms-Felder', () => {
	const overflow = channelOverflow(3);
	const keys = Object.keys(overflow).sort();
	assert.deepEqual(
		keys,
		['email', 'sms', 'telegram'],
		`Erwartet [email, sms, telegram], war: [${keys.join(', ')}]`
	);
});
