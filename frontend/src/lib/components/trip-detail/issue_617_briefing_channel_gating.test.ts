// TDD RED: Issue #617 — Briefing-Zeitplan zeigt nur Wetter-aktive Kanäle.
//
// Spec: docs/specs/modules/issue_617_briefing_channel_chaining.md
//
// Diese Tests sind ABSICHTLICH ROT, bis der pure Helper
// `briefingChannelGating.ts` existiert und EditReportConfigSection ihn nutzt.
// Sie prüfen ECHTES Laufzeitverhalten (importierte pure Funktionen), kein
// Datei-Inhalt. Vorbild: issue_619_report_config_write.test.ts.
//
// Abgedeckte ACs (Unit-Ebene, deterministisch):
//   AC-1: nur Wetter-aktive Kanäle sind sichtbar (sms aus → nicht sichtbar).
//   AC-2: Banner-Liste enthält die aktiven Kanal-Labels.
//   AC-3: 0 aktive Kanäle → Warnzustand (hasNoActiveChannel === true).
//   AC-4: syncSendFlags setzt verwaiste send_* auf false, erhält übrige Felder.
//   AC-6: ohne weatherChannels-Prop → unverändertes Altverhalten (alle Kanäle,
//         keine Banner, send_* unangetastet).
//
// AC-2/AC-3/AC-5 (gerenderte UI + Navigation) und AC-7 (Multi-User) werden per
// Playwright/staging-validator verifiziert (issue-617-briefing-channel-chaining.spec.ts).
//
// Ausführen (aus frontend/):
//   node --experimental-strip-types --test \
//     src/lib/components/trip-detail/issue_617_briefing_channel_gating.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
	visibleChannels,
	activeChannelLabels,
	hasNoActiveChannel,
	syncSendFlags,
	type ChannelConfig
} from './briefingChannelGating.ts';

const EMAIL_TG: ChannelConfig = { email: true, telegram: true, sms: false };
const NONE: ChannelConfig = { email: false, telegram: false, sms: false };
const ALL: ChannelConfig = { email: true, telegram: true, sms: true };

// ── AC-1: Sichtbarkeit folgt den Wetter-Kanälen ────────────────────────────
test('AC-1: nur Wetter-aktive Kanäle sind sichtbar (sms aus → unsichtbar)', () => {
	const vis = visibleChannels(EMAIL_TG);
	assert.equal(vis.email, true);
	assert.equal(vis.telegram, true);
	assert.equal(vis.sms, false);
});

// ── AC-2: Banner listet die aktiven Kanal-Labels ──────────────────────────
test('AC-2: activeChannelLabels liefert lesbare Labels der aktiven Kanäle', () => {
	assert.deepEqual(activeChannelLabels(EMAIL_TG), ['Email', 'Telegram']);
	assert.deepEqual(activeChannelLabels(ALL), ['Email', 'Telegram', 'SMS']);
});

// ── AC-3: Kein aktiver Kanal → Warnzustand ────────────────────────────────
test('AC-3: hasNoActiveChannel ist true nur bei 0 aktiven Wetter-Kanälen', () => {
	assert.equal(hasNoActiveChannel(NONE), true);
	assert.equal(hasNoActiveChannel(EMAIL_TG), false);
});

// ── AC-4: Sync der Versand-Flags (verwaiste Kanäle aus, Rest erhalten) ─────
test('AC-4: syncSendFlags setzt verwaisten send_sms auf false, erhält übrige Felder', () => {
	const before = {
		enabled: true,
		morning_time: '07:00:00',
		evening_time: '18:00:00',
		send_email: true,
		send_telegram: true,
		send_sms: true, // verwaist: SMS nicht in EMAIL_TG aktiv
		multi_day_trend_evening: true,
		change_threshold_wind_kmh: 20 // unbekanntes Feld muss erhalten bleiben
	};
	const after = syncSendFlags(before, EMAIL_TG);
	assert.equal(after.send_sms, false, 'verwaister Kanal muss aus');
	assert.equal(after.send_email, true, 'aktiver Kanal bleibt nach Nutzerwahl');
	assert.equal(after.send_telegram, true);
	// Read-Modify-Write: übrige Felder unverändert
	assert.equal(after.evening_time, '18:00:00');
	assert.equal(after.morning_time, '07:00:00');
	assert.equal(after.multi_day_trend_evening, true);
	assert.equal((after as Record<string, unknown>).change_threshold_wind_kmh, 20);
});

// ── AC-5 (Logik-Anteil): Auswahl unter aktiven Kanälen bleibt frei ────────
test('AC-5: syncSendFlags überschreibt aktive Kanäle NICHT (Nutzerwahl frei)', () => {
	const before = { send_email: true, send_telegram: false, send_sms: false };
	const after = syncSendFlags(before, EMAIL_TG);
	assert.equal(after.send_email, true);
	assert.equal(after.send_telegram, false, 'abgewählter aktiver Kanal bleibt aus');
});

// ── AC-6: ohne Prop → unverändertes Altverhalten ──────────────────────────
test('AC-6: ohne weatherChannels sind alle Kanäle sichtbar, kein Warnzustand', () => {
	const vis = visibleChannels(undefined);
	assert.deepEqual(vis, { email: true, telegram: true, sms: true });
	assert.equal(hasNoActiveChannel(undefined), false);
});

test('AC-6: syncSendFlags ohne weatherChannels lässt send_* unangetastet', () => {
	const before = { send_email: false, send_telegram: false, send_sms: true, morning_time: '06:00' };
	const after = syncSendFlags(before, undefined);
	assert.equal(after.send_sms, true);
	assert.equal(after.send_email, false);
	assert.equal(after.morning_time, '06:00');
});
