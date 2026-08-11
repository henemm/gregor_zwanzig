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
// ─────────────────────────────────────────────────────────────────────────────
// TDD RED — Issue #1745 Scheibe A: Premium-SMS als VIERTER Alarm-Kanal.
// Spec: docs/specs/modules/fix_1745_a_alarm_kanal_premium_sms_ui.md
//   (AC-1 Reihenfolge, AC-2 Neuanlage-Default, AC-3 Bestandserkennung,
//    AC-4 Warnhinweis)
//
// Die BESTEHENDEN deepEqual-Erwartungen dieser Datei werden mitgezogen (Spec
// „Test-Dateien", R4 im Kontextdokument): sie prüfen die vollständige Form des
// Kanal-Zustands, und diese Form bekommt ein viertes Feld. Sie laufen deshalb
// ab jetzt ROT, bis `alertChannelState.ts` den vierten Kanal kennt — das ist
// der Beweis, dass sie etwas bewachen, kein Kollateralschaden.
// ─────────────────────────────────────────────────────────────────────────────
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

// #1745 AC-1 (Teil a, reine Reihenfolge-Zusicherung). Ersetzt die frühere
// Drei-Kanal-Fassung dieses Tests (#1258 AC-11) — dieselbe Zusicherung, um den
// vierten Kanal erweitert.
// ROT HEUTE: ALERT_CHANNEL_ORDER ist ['telegram','sms','email'].
// Mutation (Spec): ALERT_CHANNEL_ORDER bleibt dreiwertig.
test('#1745 AC-1: alert_channel_order_hat_vier_kanaele_premium_sms_zuletzt', () => {
	assert.deepEqual(ALERT_CHANNEL_ORDER, ['telegram', 'sms', 'email', 'premium_sms']);
	// Der Picker rendert per {#each ALERT_CHANNEL_ORDER} — die Position IN
	// dieser Liste ist die Position in der Oberfläche. Premium-SMS steht nach
	// SMS (AC-1 Prüfort: „…-premium_sms nach …-sms").
	const order = [...ALERT_CHANNEL_ORDER] as string[];
	assert.ok(
		order.indexOf('premium_sms') > order.indexOf('sms'),
		`premium_sms muss NACH sms stehen, Reihenfolge ist: ${JSON.stringify(order)}`
	);
});

test('#1258 AC-11 / #1745 AC-2: resolveAlertChannels(undefined) liefert Design-Default TG/SMS an, E-Mail aus (Neuanlage)', () => {
	const state = resolveAlertChannels(undefined);
	assert.deepEqual(state, { telegram: true, sms: true, email: false, premium_sms: false });
});

test('#1258 AC-11: resolveAlertChannels(null) liefert denselben Default wie undefined', () => {
	assert.deepEqual(resolveAlertChannels(null), {
		telegram: true,
		sms: true,
		email: false,
		premium_sms: false
	});
});

test('#1258 AC-11: resolveAlertChannels mit Bestand {email:true, telegram:false, sms:false} bleibt unangetastet (kein Default-Overwrite)', () => {
	const state = resolveAlertChannels({ email: true, telegram: false, sms: false });
	assert.deepEqual(state, { telegram: false, sms: false, email: true, premium_sms: false });
});

test('#1258 AC-11: resolveAlertChannels mit teilweisem Bestand füllt fehlende Keys mit false (nicht mit Default)', () => {
	// Nur telegram im Bestand bekannt -> sms/email fehlen im Objekt und müssen
	// false werden, NICHT der Neuanlage-Default (kein stiller Kanal-Wechsel,
	// AC-15 verlangt spätere Ist-Zustand-Rekonstruktion, keine Defaults).
	const state = resolveAlertChannels({ telegram: true });
	assert.deepEqual(state, { telegram: true, sms: false, email: false, premium_sms: false });
});

// ─────────────────────────────────────────────────────────────────────────────
// #1745 AC-2 — Neuanlage-Default: Premium-SMS ist AUS (D1, Kostenkanal).
// ROT HEUTE: resolveAlertChannels(undefined).premium_sms ist `undefined`
// (NEW_ENTITY_DEFAULT kennt das Feld nicht).
// Mutation (Spec): NEW_ENTITY_DEFAULT.premium_sms auf `true` gesetzt.
// ─────────────────────────────────────────────────────────────────────────────
test('#1745 AC-2: neuanlage_default_premium_sms_aus', () => {
	const state = resolveAlertChannels(undefined) as Record<string, unknown>;
	assert.strictEqual(
		state.premium_sms,
		false,
		'Premium-SMS ist ein Kostenkanal (Satelliten-SMS) und muss beim Anlegen ausdrücklich ' +
			`angehakt werden — erhalten: ${JSON.stringify(state)}`
	);
	// Gegenprobe an derselben Stelle: Telegram/SMS bleiben unverändert AN, der
	// vierte Kanal darf den Design-Default der drei Bestandskanäle nicht kippen.
	assert.strictEqual(state.telegram, true);
	assert.strictEqual(state.sms, true);
	assert.strictEqual(state.email, false);
});

// ─────────────────────────────────────────────────────────────────────────────
// #1745 AC-3 — Bestand mit AUSSCHLIESSLICH Premium-SMS wird als Bestand erkannt
// (Landmine 2: hasAnyExplicitChannelValue() prüft heute nur drei Felder).
// ROT HEUTE: `{premium_sms:true}` gilt als „kein Bestand" → Neuanlage-Default
// {telegram:true, sms:true, email:false} überschreibt die Nutzer-Einstellung.
// Mutation (Spec): hasAnyExplicitChannelValue() bleibt bei der Drei-Felder-Prüfung.
// ─────────────────────────────────────────────────────────────────────────────
test('#1745 AC-3: bestand_nur_premium_sms_wird_erkannt', () => {
	const state = resolveAlertChannels({ premium_sms: true } as Record<string, boolean>);
	assert.deepEqual(
		state,
		{ telegram: false, sms: false, email: false, premium_sms: true },
		'Ein Bestand, der NUR beim vierten Kanal einen expliziten Wert trägt, darf nicht vom ' +
			'Neuanlage-Default überschrieben werden (dieselbe Fehlerklasse wie Adversary ' +
			'Fix-Loop 1/F001 für die drei Bestandskanäle).'
	);
});

test('#1745 AC-3 (Gegenprobe): {premium_sms:false} ist ebenfalls ein expliziter Bestand, kein Default-Fall', () => {
	// `false` ist ein echter, gesetzter Wert — die Weiche darf nicht auf
	// Wahrheitswert, sondern muss auf `typeof === 'boolean'` prüfen.
	assert.deepEqual(resolveAlertChannels({ premium_sms: false } as Record<string, boolean>), {
		telegram: false,
		sms: false,
		email: false,
		premium_sms: false
	});
});

// Adversary Fix-Loop 1, F001: ein Bestands-Objekt OHNE einen einzigen
// explizit gesetzten boolean-Wert (leeres Objekt oder nur undefined-Werte)
// ist kein echter Bestand — muss wie undefined behandelt werden (Default),
// sonst Foot-Gun fuer die S3-Bestand-Rekonstruktion (versehentlich `{}`
// statt `undefined` uebergeben wuerde sonst "alles aus" + Warnhinweis ergeben).
test('#1258 AC-11/F001: resolveAlertChannels({}) liefert den Neuanlage-Default (kein "alles aus")', () => {
	assert.deepEqual(resolveAlertChannels({}), {
		telegram: true,
		sms: true,
		email: false,
		premium_sms: false
	});
});

test('#1258 AC-11/F001: resolveAlertChannels({telegram: undefined}) liefert den Neuanlage-Default (kein explizit gesetzter Wert)', () => {
	assert.deepEqual(resolveAlertChannels({ telegram: undefined }), {
		telegram: true,
		sms: true,
		email: false,
		premium_sms: false
	});
});

test('#1258 AC-11/F001 (#1745): resolveAlertChannels({premium_sms: undefined}) liefert ebenfalls den Neuanlage-Default', () => {
	assert.deepEqual(
		resolveAlertChannels({ premium_sms: undefined } as Record<string, boolean | undefined>),
		{ telegram: true, sms: true, email: false, premium_sms: false }
	);
});

test('#1258 AC-11: channelWarningNeeded ist true genau dann, wenn ALLE Kanäle aus sind', () => {
	assert.equal(
		channelWarningNeeded({ telegram: false, sms: false, email: false, premium_sms: false }),
		true
	);
	assert.equal(
		channelWarningNeeded({ telegram: true, sms: false, email: false, premium_sms: false }),
		false
	);
	assert.equal(
		channelWarningNeeded({ telegram: false, sms: false, email: true, premium_sms: false }),
		false
	);
});

// ─────────────────────────────────────────────────────────────────────────────
// #1745 AC-4 — Warnhinweis bei ausschliesslich aktivem Premium-SMS
// (Landmine 4: channelWarningNeeded() prüft heute nur drei Felder).
// ROT HEUTE: liefert `true` — die Oberfläche behauptet „kein Kanal, Alerts gehen
// nirgends hin", während das Backend den Alarm sehr wohl per Premium-SMS
// zustellen würde (_effective_alert_channels kennt den Kanal seit #1701).
// Mutation (Spec): channelWarningNeeded() bleibt bei der Drei-Felder-Prüfung.
// ─────────────────────────────────────────────────────────────────────────────
test('#1745 AC-4: warnhinweis_bleibt_aus_bei_nur_premium_sms', () => {
	assert.equal(
		channelWarningNeeded({
			telegram: false,
			sms: false,
			email: false,
			premium_sms: true
		} as Record<string, boolean>),
		false,
		'Bei aktivem Premium-SMS darf der Hinweis „kein Kanal — Alerts gehen nirgends hin" NICHT ' +
			'erscheinen: der Alarm wird zugestellt, die Oberfläche behauptete sonst das Gegenteil.'
	);
});

test('#1258 AC-11: NO_CHANNEL_WARNING hat den exakten Design-Text', () => {
	assert.equal(NO_CHANNEL_WARNING, 'kein Kanal — Alerts gehen nirgends hin');
});

test('#1258 AC-11: Default-State selbst löst den Warnhinweis nicht aus (TG/SMS an)', () => {
	const state = resolveAlertChannels(undefined);
	assert.equal(channelWarningNeeded(state), false);
});
