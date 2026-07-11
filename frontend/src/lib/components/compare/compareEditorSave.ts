// Issue #679 — Pure-Function: Compare-Preset-Save-Payload
// Spec: docs/specs/modules/issue_679_compare_editor_edit.md § AC-3
//
// Round-Trip-Spread: nicht editierte Felder (empfaenger, schedule, hour_from/to,
// weekday, previous_schedule) kommen unveraendert aus `original`. Nur explizit
// geaenderte Felder werden ueberschrieben. Verhindert Datenverlust beim Speichern.
//
// Kein Browser-/SvelteKit-Import — lauffaehig unter node --experimental-strip-types.

import type { ComparePreset, ActivityProfile, ChannelLayouts } from '../../types.ts';
import type { IdealRange } from './compareMetricDefs.ts';

export interface CompareEditorEdits {
	name: string;
	activityProfile: ActivityProfile | null;
	pickedIds: string[];
	region: string;
	idealRanges: Record<string, IdealRange>;
	channelLayouts: ChannelLayouts | null;
	// Issue #680: Slice 3 — aktive Metriken (AC-10). Optional → rückwärtskompatibel.
	activeMetricKeys?: string[];
	// Issue #1106: Slice C — Stundenverlauf-Metriken. Optional → rückwärtskompatibel.
	hourlyMetricKeys?: string[];
	// Issue #764: Vorhersage-Horizont. Optional → rückwärtskompatibel.
	forecastHours?: number;
	// Issue #1040: amtliche Warnungen ein/aus. Optional → rückwärtskompatibel.
	officialAlertsEnabled?: boolean;
	// Issue #1041 Slice 2: Radar-Alarm ein/aus (Default AUS). Optional → rückwärtskompatibel.
	radarAlertEnabled?: boolean;
	// Issue #1104: Anzahl Orte mit stündlichem Detail. Optional → rückwärtskompatibel.
	topN?: number;
	// Issue #1107: Stundenverlauf-Sektion ein/aus. Optional → rückwärtskompatibel.
	hourlyEnabled?: boolean;
	// Issue #1170: Alarm-Konfiguration (Epic #1095 Scheibe 3/3). Optional → rückwärtskompatibel.
	metricAlertLevels?: Record<string, string>;
	alertCooldownMinutes?: number;
	alertQuietFrom?: string;
	alertQuietTo?: string;
	// Issue #1216 Slice 2b: Amtliche-Warnungen-Alarm-Trigger + Kanal-Opt-in.
	// Optional → rückwärtskompatibel (undefined = Feld nicht editiert → Round-Trip).
	officialAlertTriggersEnabled?: boolean;
	sendTelegram?: boolean;
	sendSms?: boolean;
	// Issue #1134: Zeitfenster (Step 5). Optional → rückwärtskompatibel; ohne
	// Angabe bleibt der Round-Trip-Spread aus `original` erhalten.
	hourFrom?: number;
	hourTo?: number;
}

/**
 * Baut den PUT-Payload fuer `/api/compare/presets/{id}`.
 *
 * Schluesselprinzip: `{ ...original, <überschriebene Felder> }` — damit
 * round-trippen alle vom Editor nicht angefassten Felder unveraendert.
 */
export function buildComparePresetSavePayload(
	original: ComparePreset,
	edits: CompareEditorEdits
): { url: string; body: ComparePreset } {
	const url = '/api/compare/presets/' + original.id;

	const displayConfig: Record<string, unknown> = {
		...((original.display_config as Record<string, unknown>) ?? {}),
		region: edits.region
	};

	if (Object.keys(edits.idealRanges).length > 0) {
		displayConfig.ideal_ranges = edits.idealRanges;
	}

	if (edits.channelLayouts !== null) {
		displayConfig.channel_layouts = edits.channelLayouts;
	}

	if (edits.topN !== undefined) {
		displayConfig.top_n = edits.topN;
	}

	if (edits.activeMetricKeys !== undefined) {
		if (edits.activeMetricKeys.length > 0) {
			displayConfig.active_metrics = edits.activeMetricKeys;
		} else {
			// Leere Auswahl: active_metrics aus dem Spread entfernen, damit kein Datenschrott bleibt
			delete displayConfig.active_metrics;
		}
	}

	if (edits.hourlyMetricKeys !== undefined) {
		if (edits.hourlyMetricKeys.length > 0) {
			displayConfig.hourly_metrics = edits.hourlyMetricKeys;
		} else {
			// Leere Auswahl: hourly_metrics aus dem Spread entfernen (Default = alle sichtbar)
			delete displayConfig.hourly_metrics;
		}
	}

	// Issue #1170: metric_alert_levels lebt in display_config (analog Trip).
	if (edits.metricAlertLevels !== undefined) {
		displayConfig.metric_alert_levels = edits.metricAlertLevels;
	}

	const body: ComparePreset = {
		...original,
		name: edits.name,
		location_ids: edits.pickedIds,
		profil: edits.activityProfile ?? original.profil,
		display_config: displayConfig,
		// Issue #764: Edit-Wert überschreibt den Spread-Wert aus original.
		// undefined → Feld fehlt in edits → Spread-Wert bleibt erhalten (Round-Trip).
		...(edits.forecastHours !== undefined ? { forecast_hours: edits.forecastHours } : {}),
		// Issue #1040: analoges Round-Trip-Prinzip für official_alerts_enabled.
		...(edits.officialAlertsEnabled !== undefined
			? { official_alerts_enabled: edits.officialAlertsEnabled }
			: {}),
		// Issue #1041 Slice 2: analoges Round-Trip-Prinzip für radar_alert_enabled.
		...(edits.radarAlertEnabled !== undefined
			? { radar_alert_enabled: edits.radarAlertEnabled }
			: {}),
		// Issue #1107: analoges Round-Trip-Prinzip für hourly_enabled.
		...(edits.hourlyEnabled !== undefined ? { hourly_enabled: edits.hourlyEnabled } : {}),
		// Issue #1170: analoges Round-Trip-Prinzip für die Alarm-Konfiguration.
		...(edits.alertCooldownMinutes !== undefined
			? { alert_cooldown_minutes: edits.alertCooldownMinutes }
			: {}),
		...(edits.alertQuietFrom !== undefined ? { alert_quiet_from: edits.alertQuietFrom } : {}),
		...(edits.alertQuietTo !== undefined ? { alert_quiet_to: edits.alertQuietTo } : {}),
		// Issue #1216 Slice 2b: analoges Round-Trip-Prinzip für Trigger + Kanäle.
		...(edits.officialAlertTriggersEnabled !== undefined
			? { official_alert_triggers_enabled: edits.officialAlertTriggersEnabled }
			: {}),
		...(edits.sendTelegram !== undefined ? { send_telegram: edits.sendTelegram } : {}),
		...(edits.sendSms !== undefined ? { send_sms: edits.sendSms } : {}),
		// Issue #1134: Zeitfenster überschreibt den Spread-Wert aus original.
		// undefined → Feld fehlt in edits → Spread-Wert bleibt erhalten (Round-Trip).
		...(edits.hourFrom !== undefined ? { hour_from: edits.hourFrom } : {}),
		...(edits.hourTo !== undefined ? { hour_to: edits.hourTo } : {})
	};

	return { url, body };
}
