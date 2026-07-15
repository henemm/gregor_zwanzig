// Issue #679 — Pure-Function: Compare-Preset-Save-Payload
// Spec: docs/specs/modules/issue_679_compare_editor_edit.md § AC-3
//
// Round-Trip-Spread: nicht editierte Felder (empfaenger, schedule, hour_from/to,
// weekday, previous_schedule) kommen unveraendert aus `original`. Nur explizit
// geaenderte Felder werden ueberschrieben. Verhindert Datenverlust beim Speichern.
//
// Kein Browser-/SvelteKit-Import — lauffaehig unter node --experimental-strip-types.

import type { ComparePreset, ActivityProfile, ChannelLayouts, Corridor } from '../../types.ts';
import type { IdealRange } from './compareMetricDefs.ts';
import { toHHMMSS } from '../../utils/time.ts';

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
	// Issue #1232 Scheibe 2b: Zwei-Slot-Zeitplan + editierbare Laufzeit
	// (VersandTab context="vergleich"). Optional → rückwärtskompatibel.
	// endDate: undefined = unangetastet (Round-Trip), null = "bis auf Weiteres"
	// (Lösch-Sentinel → sendet ""), string = "YYYY-MM-DD".
	morningEnabled?: boolean;
	morningTime?: string;
	eveningEnabled?: boolean;
	eveningTime?: string;
	endDate?: string | null;
	// Issue #1231 Slice 4: Korridore (TOP-LEVEL Feld, analog Go-Model
	// ComparePreset.Corridors `json:"corridors"` — NICHT in display_config
	// verschachtelt). Optional → rückwärtskompatibel (undefined = Round-Trip
	// via `...original`, wie alle anderen Felder hier).
	corridors?: Corridor[];
	// Issue #1258 S4 (AC-27): amtliche Warnungen ein/aus. Optional →
	// rückwärtskompatibel (undefined = Feld nicht editiert → Round-Trip).
	// `sources` wird NIE vom FE gesendet — Bestand aus `original` bleibt beim
	// Body-Bau erhalten (Merge, kein Replace).
	officialWarnings?: { enabled: boolean };
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
		// Bug #1191 (Adversary F001): Leere Auswahl EXPLIZIT als [] persistieren —
		// NICHT loeschen. Sonst ist "Nutzer hat alles abgewaehlt" (nichts feuert)
		// nicht von "nie konfiguriert/migriert" (Legacy-Fallback: alles feuert)
		// unterscheidbar. Read-Modify-Write-Merge bleibt gewahrt (Spread + Ueberschreiben).
		displayConfig.active_metrics = edits.activeMetricKeys;
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
		...(edits.hourTo !== undefined ? { hour_to: edits.hourTo } : {}),
		// Issue #1232 Scheibe 2b: Zwei-Slot-Zeitplan + End-Datum-Lösch-Sentinel.
		...(edits.morningEnabled !== undefined ? { morning_enabled: edits.morningEnabled } : {}),
		...(edits.morningTime !== undefined ? { morning_time: toHHMMSS(edits.morningTime) } : {}),
		...(edits.eveningEnabled !== undefined ? { evening_enabled: edits.eveningEnabled } : {}),
		...(edits.eveningTime !== undefined ? { evening_time: toHHMMSS(edits.eveningTime) } : {}),
		...(edits.endDate !== undefined ? { end_date: edits.endDate === null ? '' : edits.endDate } : {}),
		// Issue #1231 Slice 4: analoges Round-Trip-Prinzip für corridors.
		...(edits.corridors !== undefined ? { corridors: edits.corridors } : {}),
		// Issue #1258 S4 (AC-27, Fix-Loop 1 / Adversary F001): official_warnings.
		// enabled aus edits. `sources` wird NIEMALS im Body gesendet — auch nicht
		// als Echo aus `original` (das war der F001-Clobber-Bug: original ist ein
		// Mount-Snapshot und kann inzwischen serverseitig geänderte sources
		// überschreiben). Ohne `sources`-Key im Body macht der Go-RMW
		// (compare_preset.go:331-342) den Bestand-Merge selbst.
		...(edits.officialWarnings !== undefined
			? { official_warnings: { enabled: edits.officialWarnings.enabled } }
			: {})
	};

	return { url, body };
}
