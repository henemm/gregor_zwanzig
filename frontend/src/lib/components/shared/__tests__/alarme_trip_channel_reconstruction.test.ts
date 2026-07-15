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
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/alarme_trip_channel_reconstruction.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import type { Trip } from '$lib/types';

import { reconstructTripAlertChannels } from '../alarme-tab/tripChannelReconstruction.ts';
import { resolveAlertChannels } from '../alarme-tab/alertChannelState.ts';

test('#1258 AC-15: trip.alert_channels gesetzt -> exakt dessen Werte, unabhängig von report_config', () => {
	const trip = {
		alert_channels: { email: false, telegram: true, sms: false },
		report_config: { send_email: true, send_telegram: false, send_sms: true }
	} as unknown as Trip;

	const result = reconstructTripAlertChannels(trip);
	assert.deepEqual(result, { telegram: true, sms: false, email: false });
});

test('#1258 AC-15: kein alert_channels, report_config mit send_telegram=true -> {email:true(Default), telegram:true, sms:false}', () => {
	const trip = {
		report_config: { send_email: true, send_telegram: true, send_sms: false }
	} as unknown as Trip;

	const result = reconstructTripAlertChannels(trip);
	assert.deepEqual(result, { telegram: true, sms: false, email: true });
});

test('#1258 AC-15: kein alert_channels, kein report_config -> Legacy-Default {email:true, telegram:false, sms:false}', () => {
	const trip = {} as unknown as Trip;

	const result = reconstructTripAlertChannels(trip);
	assert.deepEqual(result, { telegram: false, sms: false, email: true });
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
