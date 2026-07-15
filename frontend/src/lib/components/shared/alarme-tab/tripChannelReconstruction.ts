// Issue #1258 Scheibe S3 — Trip-Integration des geteilten Alarme-Tabs.
// AC-15: Beim erstmaligen Öffnen des Alarme-Tabs muss der AlertChannelPicker
// den aus dem heutigen Ist-Zustand rekonstruierten Kanal-Status zeigen, NICHT
// den Neuanlage-Default (kein stiller Kanal-Wechsel für Bestandstrips).
//
// Vorrang: `trip.alert_channels` (D2, scharfes Kanal-Set), sonst geerbte
// Briefing-Kanäle aus `report_config.send_*` (E-Mail-Default true, analog
// Backend-Legacy-Verhalten trip_alert.py:_briefing_channels), ohne
// report_config Legacy-Default {email:true, telegram:false, sms:false}.
//
// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md
//   (Implementation Details Abschnitt 9 "S3-Detail-Festlegungen", AC-15)
// Kontext: docs/context/feat-1258-s3-trip-alarme-tab.md (Entscheidung D4)

import type { Trip } from '$lib/types';
import type { AlertChannelState } from './alertChannelState.ts';

export function reconstructTripAlertChannels(trip: Trip): AlertChannelState {
	if (trip.alert_channels) {
		return {
			telegram: trip.alert_channels.telegram,
			sms: trip.alert_channels.sms,
			email: trip.alert_channels.email
		};
	}
	const rc = trip.report_config;
	if (rc) {
		return {
			telegram: rc.send_telegram ?? false,
			sms: rc.send_sms ?? false,
			email: rc.send_email ?? true
		};
	}
	return { telegram: false, sms: false, email: true };
}
