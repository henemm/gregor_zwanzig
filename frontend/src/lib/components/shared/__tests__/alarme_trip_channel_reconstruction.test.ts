// TDD RED — Issue #1258 Scheibe S3: Trip-Integration des Alarme-Tabs.
// AC-15: Der AlertChannelPicker muss beim erstmaligen Öffnen des Alarme-Tabs
// den aus dem heutigen Ist-Zustand rekonstruierten Kanal-Status zeigen, NICHT
// den Neuanlage-Default (kein stiller Kanal-Wechsel für Bestandstrips).
//
// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md
//   (Implementation Details Abschnitt 9 "S3-Detail-Festlegungen", AC-15)
// Kontext: docs/context/feat-1258-s3-trip-alarme-tab.md (Entscheidung D4)
// Vorbild (Import-Stil, Runner):
//   frontend/src/lib/components/shared/__tests__/alarme_alert_channel_defaults.test.ts
//
// `tripChannelReconstruction.ts` existiert noch NICHT — Import schlägt heute
// fehl (RED), bis die Implementierung das Modul unter
// frontend/src/lib/components/shared/alarme-tab/tripChannelReconstruction.ts
// anlegt.
//
// ─────────────────────────────────────────────────────────────────────────────
// TDD RED — Issue #1745 Scheibe A (AC-7): der vierte Kanal in der
// Ist-Zustand-Rekonstruktion. Spec:
//   docs/specs/modules/fix_1745_a_alarm_kanal_premium_sms_ui.md (AC-7, D4)
//
// Die drei BESTEHENDEN deepEqual-Erwartungen werden mitgezogen (Spec
// „Test-Dateien", R4 im Kontextdokument): sie prüfen die vollständige Form des
// rekonstruierten Kanal-Zustands, und diese Form bekommt ein viertes Feld. Sie
// laufen deshalb ab jetzt ROT.
// ─────────────────────────────────────────────────────────────────────────────
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/alarme_trip_channel_reconstruction.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import type { Trip } from '$lib/types';

import { reconstructTripAlertChannels } from '../alarme-tab/tripChannelReconstruction.ts';
import { resolveAlertChannels } from '../alarme-tab/alertChannelState.ts';

test('#1258 AC-15: trip.alert_channels gesetzt -> exakt dessen Werte, unabhängig von report_config', () => {
	const trip = {
		alert_channels: { email: false, telegram: true, sms: false, premium_sms: true },
		report_config: { send_email: true, send_telegram: false, send_sms: true }
	} as unknown as Trip;

	const result = reconstructTripAlertChannels(trip);
	assert.deepEqual(result, { telegram: true, sms: false, email: false, premium_sms: true });
});

test('#1258 AC-15: kein alert_channels, report_config mit send_telegram=true -> {email:true(Default), telegram:true, sms:false}', () => {
	const trip = {
		report_config: { send_email: true, send_telegram: true, send_sms: false }
	} as unknown as Trip;

	const result = reconstructTripAlertChannels(trip);
	assert.deepEqual(result, { telegram: true, sms: false, email: true, premium_sms: false });
});

test('#1258 AC-15: kein alert_channels, kein report_config -> Legacy-Default {email:true, telegram:false, sms:false}', () => {
	const trip = {} as unknown as Trip;

	const result = reconstructTripAlertChannels(trip);
	assert.deepEqual(result, { telegram: false, sms: false, email: true, premium_sms: false });
});

// ─────────────────────────────────────────────────────────────────────────────
// #1745 AC-7 (D4) — der HEUTIGE Zustand ALLER Trips: `alert_channels` ist
// gesetzt, trägt aber keinen `premium_sms`-Schlüssel. Gleichzeitig ist
// Premium-SMS im Briefing (report_config.send_premium_sms) bereits aktiv —
// exakt der KHW-Trip. Der Alarm-Reiter darf den Briefing-Haken NICHT erben:
// sobald `alert_channels` existiert, ersetzt es den geerbten Anteil
// vollständig (deckt sich mit #1258 S3 AC-15, „kein stiller Kanal-Wechsel").
//
// ROT HEUTE: `reconstructTripAlertChannels` kennt das Feld nicht, das Ergebnis
// hat gar keinen `premium_sms`-Schlüssel (undefined).
// Mutation (Spec): die Rekonstruktion liest bei fehlendem Schlüssel
// `report_config.send_premium_sms` statt fest `false`.
// ─────────────────────────────────────────────────────────────────────────────
test('#1745 AC-7: fehlender_premium_sms_schluessel_bedeutet_aus_kein_briefing_fallback', () => {
	const trip = {
		alert_channels: { email: true, telegram: true, sms: true },
		report_config: {
			send_email: true,
			send_telegram: true,
			send_sms: true,
			send_premium_sms: true
		}
	} as unknown as Trip;

	const result = reconstructTripAlertChannels(trip) as Record<string, boolean>;

	assert.strictEqual(
		result.premium_sms,
		false,
		'Ein Bestandstrip mit gesetztem alert_channels OHNE premium_sms-Schlüssel muss den vierten ' +
			'Kanal AUS zeigen — der im Briefing aktive Haken (report_config.send_premium_sms) darf ' +
			`nicht stillschweigend zum Alarm-Kanal werden (D4). Erhalten: ${JSON.stringify(result)}`
	);
	assert.deepEqual(result, { telegram: true, sms: true, email: true, premium_sms: false });
});

test('#1745 AC-7 (Vererbungszweig): OHNE alert_channels erbt der Alarm-Reiter report_config.send_premium_sms', () => {
	// Gegenstück zum Test oben: erst wenn es gar kein scharfes Kanal-Set gibt,
	// zählt der Briefing-Haken — sonst wäre der Fix „premium_sms immer false"
	// und der Vererbungszweig stillgelegt (die Mutation, die AC-7 allein nicht
	// fängt: eine fest verdrahtete `false` an BEIDEN Stellen).
	const trip = {
		report_config: {
			send_email: true,
			send_telegram: false,
			send_sms: false,
			send_premium_sms: true
		}
	} as unknown as Trip;

	const result = reconstructTripAlertChannels(trip) as Record<string, boolean>;
	assert.strictEqual(
		result.premium_sms,
		true,
		`geerbter Briefing-Kanal muss im Vererbungszweig ankommen — erhalten: ${JSON.stringify(result)}`
	);
});

// AC-15 verlangt, dass der rekonstruierte Bestand NICHT als Neuanlage-Default
// (TG/SMS an, E-Mail aus) missinterpretiert wird — resolveAlertChannels()
// (S2, hasAnyExplicitChannelValue-Weiche) muss das Rekonstruktions-Ergebnis
// unverändert durchreichen, statt es auf den Neuanlage-Default zurückzusetzen.
test('#1258 AC-15: rekonstruiertes Ergebnis wird von resolveAlertChannels() als expliziter Bestand erkannt (kein Neuanlage-Default-Reset)', () => {
	const trip = {
		report_config: { send_email: true, send_telegram: false, send_sms: false }
	} as unknown as Trip;

	const reconstructed = reconstructTripAlertChannels(trip);
	const resolved = resolveAlertChannels(reconstructed);

	assert.deepEqual(
		resolved,
		reconstructed,
		'resolveAlertChannels darf das rekonstruierte Ergebnis nicht auf den Neuanlage-Default zurücksetzen'
	);
	assert.notDeepEqual(
		resolved,
		{ telegram: true, sms: true, email: false },
		'rekonstruiertes Bestandsergebnis darf nicht zufällig mit dem Neuanlage-Default kollidieren'
	);
});
