// TDD RED — Issue #1258 Scheibe S2: geteilter Alarme-Organism (ungewired).
// AC-11: AlertChannelPicker-Logik — Design-Default (Telegram/SMS an, E-Mail
// aus) NUR ohne übergebenen Bestands-State; mit Bestand wird der Bestand
// übernommen (kein stiller Kanal-Wechsel); Warnhinweis bei 0 aktiven Kanälen.
//
// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md (AC-11)
// Design: claude-code-handoff/current/jsx/corridor-editor.jsx:469-489
//
// `alertChannelState.ts` existiert noch NICHT — Import schlägt heute fehl
// (RED), bis Phase 6 das Modul unter
// frontend/src/lib/components/shared/alarme-tab/alertChannelState.ts anlegt.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/alarme_alert_channel_defaults.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
	ALERT_CHANNEL_ORDER,
	NO_CHANNEL_WARNING,
	channelWarningNeeded,
	resolveAlertChannels
} from '../alarme-tab/alertChannelState.ts';

test('#1258 AC-11: ALERT_CHANNEL_ORDER ist telegram, sms, email (Design-Anzeigereihenfolge)', () => {
	assert.deepEqual(ALERT_CHANNEL_ORDER, ['telegram', 'sms', 'email']);
});

test('#1258 AC-11: resolveAlertChannels(undefined) liefert Design-Default TG/SMS an, E-Mail aus (Neuanlage)', () => {
	const state = resolveAlertChannels(undefined);
	assert.deepEqual(state, { telegram: true, sms: true, email: false });
});

test('#1258 AC-11: resolveAlertChannels(null) liefert denselben Default wie undefined', () => {
	assert.deepEqual(resolveAlertChannels(null), { telegram: true, sms: true, email: false });
});

test('#1258 AC-11: resolveAlertChannels mit Bestand {email:true, telegram:false, sms:false} bleibt unangetastet (kein Default-Overwrite)', () => {
	const state = resolveAlertChannels({ email: true, telegram: false, sms: false });
	assert.deepEqual(state, { telegram: false, sms: false, email: true });
});

test('#1258 AC-11: resolveAlertChannels mit teilweisem Bestand füllt fehlende Keys mit false (nicht mit Default)', () => {
	// Nur telegram im Bestand bekannt -> sms/email fehlen im Objekt und müssen
	// false werden, NICHT der Neuanlage-Default (kein stiller Kanal-Wechsel,
	// AC-15 verlangt spätere Ist-Zustand-Rekonstruktion, keine Defaults).
	const state = resolveAlertChannels({ telegram: true });
	assert.deepEqual(state, { telegram: true, sms: false, email: false });
});

// Adversary Fix-Loop 1, F001: ein Bestands-Objekt OHNE einen einzigen
// explizit gesetzten boolean-Wert (leeres Objekt oder nur undefined-Werte)
// ist kein echter Bestand — muss wie undefined behandelt werden (Default),
// sonst Foot-Gun fuer die S3-Bestand-Rekonstruktion (versehentlich `{}`
// statt `undefined` uebergeben wuerde sonst "alles aus" + Warnhinweis ergeben).
test('#1258 AC-11/F001: resolveAlertChannels({}) liefert den Neuanlage-Default (kein "alles aus")', () => {
	assert.deepEqual(resolveAlertChannels({}), { telegram: true, sms: true, email: false });
});

test('#1258 AC-11/F001: resolveAlertChannels({telegram: undefined}) liefert den Neuanlage-Default (kein explizit gesetzter Wert)', () => {
	assert.deepEqual(resolveAlertChannels({ telegram: undefined }), {
		telegram: true,
		sms: true,
		email: false
	});
});

test('#1258 AC-11: channelWarningNeeded ist true genau dann, wenn alle drei Kanäle aus sind', () => {
	assert.equal(channelWarningNeeded({ telegram: false, sms: false, email: false }), true);
	assert.equal(channelWarningNeeded({ telegram: true, sms: false, email: false }), false);
	assert.equal(channelWarningNeeded({ telegram: false, sms: false, email: true }), false);
});

test('#1258 AC-11: NO_CHANNEL_WARNING hat den exakten Design-Text', () => {
	assert.equal(NO_CHANNEL_WARNING, 'kein Kanal — Alerts gehen nirgends hin');
});

test('#1258 AC-11: Default-State selbst löst den Warnhinweis nicht aus (TG/SMS an)', () => {
	const state = resolveAlertChannels(undefined);
	assert.equal(channelWarningNeeded(state), false);
});
