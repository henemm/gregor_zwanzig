// Gemeinsamer Prüfstand der Ortsvergleich-Speichertests (Issue #2276 Scheibe S5,
// Epic #2345). KEINE Testdatei (kein `.test.ts`) — nur zwei Aufbauhilfen:
// `makePreset` (ein voller Vergleich als Ausgangsbestand) und `createController`
// (echte `SaveStatus`-Instanz mit Kennung {typ:'vergleich', id}). Die früheren
// Versand-Hilfen entfielen mit dem toten Versand-Speicherer (#3389).
//
// Transport: echtes `api` gegen `fakeTripServer.ts`. Echte `SaveStatus`-Instanz.

import { SaveStatus } from '../../../stores/saveStatusStore.svelte.ts';
import type { ComparePreset } from '../../../types.ts';

export function makePreset(id: string, overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id,
		name: 'Ortsvergleich Versand',
		location_ids: ['loc-a', 'loc-b', 'loc-c'],
		schedule: 'daily',
		previous_schedule: 'daily',
		profil: 'wandern',
		hour_from: 6,
		hour_to: 9,
		forecast_hours: 48,
		empfaenger: ['a@example.com'],
		created_at: '2026-01-01T00:00:00Z',
		official_alerts_enabled: true,
		official_warnings: { enabled: true },
		radar_alert_enabled: false,
		send_telegram: true,
		send_sms: false,
		send_premium_sms: false,
		morning_enabled: true,
		morning_time: '06:30:00',
		evening_enabled: false,
		evening_time: '18:00:00',
		end_date: '2026-08-01',
		// Die drei Legacy-Restfelder (Spec, Implementation Details Punkt 6):
		// kein Kontrollelement im Versand-Tab mutiert sie, der Versand-PUT muss
		// sie trotzdem tragen — sonst nullt er Alarm-Zustellungsfelder (AC-11).
		alert_cooldown_minutes: 45,
		alert_quiet_from: '22:00',
		alert_quiet_to: '07:00',
		alert_channel_thresholds: { email: 'gering', telegram: 'hoch', sms: 'gering' },
		hourly_enabled: true,
		outlook_enabled: true,
		day_window_start_hour: 4,
		day_window_end_hour: 19,
		corridors: [{ metric: 'snow_depth_cm', range: [30, 200], notify: false, mark: true }],
		display_config: {
			region: 'Tirol',
			ideal_ranges: { snow_depth_cm: { min: 30, max: 200 } },
			active_metrics: ['snow_depth_cm'],
			metric_alert_levels: { snow_depth_cm: 'warn' },
			telegram_style: 'kurzform',
			hourly_metrics: ['snow_depth_cm'],
			outlook_metrics: ['snow_depth_cm'],
			outlook_metric_formats: { snow_depth_cm: true }
		},
		...overrides
	} as ComparePreset;
}

/** Echte SaveStatus-Instanz ohne Konstruktor (Runen-Felder), MIT Kennung
 *  {typ:'vergleich', id} — sonst läuft `retryConflict()` leer. */
export function createController(id: string): SaveStatus {
	const inst = Object.create(SaveStatus.prototype) as SaveStatus;
	const f = inst as unknown as Record<string, unknown>;
	f.state = 'idle';
	f.savedAt = null;
	f.error = null;
	f._timer = null;
	f._pendingFn = null;
	f._inflight = null;
	f._lastFailed = null;
	f._unresolvedError = null;
	f._tripId = id;
	f._resourceKind = 'vergleich';
	return inst;
}
