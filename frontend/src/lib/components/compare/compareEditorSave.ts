// Issue #679 — Pure-Function: Compare-Preset-Save-Payload
// Spec: docs/specs/modules/issue_679_compare_editor_edit.md § AC-3
//
// Round-Trip-Spread: nicht editierte Felder (empfaenger, schedule, hour_from/to,
// weekday, previous_schedule) kommen unveraendert aus `original`. Nur explizit
// geaenderte Felder werden ueberschrieben. Verhindert Datenverlust beim Speichern.
//
// Kein Browser-/SvelteKit-Import — lauffaehig unter node --experimental-strip-types.

import type { ComparePreset, ActivityProfile, Corridor } from '../../types.ts';
import type { IdealRange } from '../shared/corridor-editor/corridorEditorState.ts';
import { toHHMMSS } from '../../utils/time.ts';
// Issue #1373 (S2 Scheibe B): Speicherformat der Metrik-Auswahl ist Größe +
// Auswertung. Die Übersetzung kommt aus der bereits geladenen Antwort von
// GET /api/compare/metrics (Scheibe A liefert metric_id/aggregation je Eintrag) —
// keine zweite Tabelle im Frontend, keine zusätzliche Anfrage.
import { toStoredActiveMetrics } from '../shared/weather-metrics-tab/compareMetricSelection.ts';

export interface CompareEditorEdits {
	name: string;
	activityProfile: ActivityProfile | null;
	pickedIds: string[];
	region: string;
	idealRanges: Record<string, IdealRange>;
	// Issue #680: Slice 3 — aktive Metriken (AC-10). Optional → rückwärtskompatibel.
	activeMetricKeys?: string[];
	// Issue #1106: Slice C — Stundenverlauf-Metriken. Optional → rückwärtskompatibel.
	hourlyMetricKeys?: string[];
	// Issue #1040: amtliche Warnungen ein/aus. Optional → rückwärtskompatibel.
	officialAlertsEnabled?: boolean;
	// Issue #1041 Slice 2: Radar-Alarm ein/aus (Default AUS). Optional → rückwärtskompatibel.
	radarAlertEnabled?: boolean;
	// Issue #1107: Stundenverlauf-Sektion ein/aus. Optional → rückwärtskompatibel.
	hourlyEnabled?: boolean;
	// Issue #1170: Alarm-Konfiguration (Epic #1095 Scheibe 3/3). Optional → rückwärtskompatibel.
	metricAlertLevels?: Record<string, string>;
	// Issue #1260 S5: Telegram-Kurzstil (display_config.telegram_style). Optional →
	// rückwärtskompatibel; undefined = Feld nicht editiert → Round-Trip via `...original`.
	telegramStyle?: 'rich' | 'kurzform';
	alertCooldownMinutes?: number;
	alertQuietFrom?: string;
	alertQuietTo?: string;
	// Issue #1216 Slice 2b: Amtliche-Warnungen-Alarm-Trigger + Kanal-Opt-in.
	// Optional → rückwärtskompatibel (undefined = Feld nicht editiert → Round-Trip).
	officialAlertTriggersEnabled?: boolean;
	sendTelegram?: boolean;
	sendSms?: boolean;
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
	// Issue #1361/#1372 S1b: gemeinsames Tagesfenster (Reiter Wetter-Metriken,
	// beide Kontexte). Optional → rückwärtskompatibel (undefined = Feld nicht
	// editiert → Round-Trip via `...original`).
	dayWindowStartHour?: number;
	dayWindowEndHour?: number;
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

	// Issue #1351 Teil 2 (AC-6): channel_layouts ist Compare-Ballast (seit
	// #1287/#1291 vom Editor nicht mehr bedient) — Read-Modify-Write-Merge
	// bleibt fuer ALLE anderen Felder aus original.display_config erhalten,
	// nur dieser eine Key faellt beim Speichern universell weg (auch bei
	// noch nicht migrierten Alt-Presets).
	const { channel_layouts: _droppedChannelLayouts, ...restDisplayConfig } =
		(original.display_config as Record<string, unknown>) ?? {};
	const displayConfig: Record<string, unknown> = {
		...restDisplayConfig,
		region: edits.region
	};

	if (Object.keys(edits.idealRanges).length > 0) {
		displayConfig.ideal_ranges = edits.idealRanges;
	}

	if (edits.activeMetricKeys !== undefined) {
		// Bug #1191 (Adversary F001): Leere Auswahl EXPLIZIT als [] persistieren —
		// NICHT loeschen. Sonst ist "Nutzer hat alles abgewaehlt" (nichts feuert)
		// nicht von "nie konfiguriert/migriert" (Legacy-Fallback: alles feuert)
		// unterscheidbar. Read-Modify-Write-Merge bleibt gewahrt (Spread + Ueberschreiben).
		//
		// Issue #1373 (S2 Scheibe B): geschrieben wird nur noch das neue Format
		// (Groesse + Auswertung). [] bleibt [] — die Uebersetzung einer leeren
		// Auswahl ist eine leere Liste, kein weggelassener Key.
		displayConfig.active_metrics = toStoredActiveMetrics(edits.activeMetricKeys);
	}

	if (edits.hourlyMetricKeys !== undefined) {
		// Bug #1299/C2 (Staging-Fund F005): Leere Auswahl EXPLIZIT als [] persistieren —
		// NICHT den Key loeschen. Der Server-Merge (mergeConfigMap, config_merge.go, #1159)
		// ueberschreibt Keys nur, loescht sie nie; ein weggelassener Key bliebe wirkungslos
		// (alter Wert bleibt). Der Renderer resolve_hourly_metrics behandelt [] identisch
		// zu absent -> alle 9 Spalten sichtbar. Analog active_metrics (#1191).
		displayConfig.hourly_metrics = edits.hourlyMetricKeys;
	}

	// Issue #1170: metric_alert_levels lebt in display_config (analog Trip).
	if (edits.metricAlertLevels !== undefined) {
		displayConfig.metric_alert_levels = edits.metricAlertLevels;
	}

	// Issue #1260 S5: telegram_style lebt in display_config. undefined → Feld nicht
	// editiert → Round-Trip via `...original.display_config` (RMW, kein Datenverlust).
	if (edits.telegramStyle !== undefined) {
		displayConfig.telegram_style = edits.telegramStyle;
	}

	const body: ComparePreset = {
		...original,
		name: edits.name,
		location_ids: edits.pickedIds,
		profil: edits.activityProfile ?? original.profil,
		display_config: displayConfig,
		// Issue #1268: forecast_hours/hour_from/hour_to werden nicht mehr aus dem
		// Editor gesetzt. Der `...original`-Spread oben traegt die gespeicherten
		// Bestandswerte unveraendert in den Body (Read-Modify-Write, kein Nullen).
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
			: {}),
		// Issue #1361/#1372 S1b: analoges Round-Trip-Prinzip für das Tagesfenster.
		...(edits.dayWindowStartHour !== undefined
			? { day_window_start_hour: edits.dayWindowStartHour }
			: {}),
		...(edits.dayWindowEndHour !== undefined ? { day_window_end_hour: edits.dayWindowEndHour } : {})
	};

	return { url, body };
}

// ─── Create-Pfad (POST /api/compare/presets) ──────────────────────────────
//
// Issue #1360 F002: Pure-Function-Gegenstueck zu buildComparePresetSavePayload
// fuer die Neuanlage (`CompareWizardState.saveNewPreset()`). Analoges Prinzip
// (keine Browser-/SvelteKit-Imports, plain Input-Objekt statt $state-Runen) —
// damit ist die Create-Payload ohne Svelte-Runtime testbar (kein nachgebautes
// Objekt im Test, keine Mock-Rückspiegelung).

export interface NewComparePresetFields {
	name: string;
	pickedIds: string[];
	activityProfile: ActivityProfile | null;
	schedule: 'daily_morning' | 'daily_evening' | 'weekly';
	officialAlertsEnabled: boolean;
	radarAlertEnabled: boolean;
	hourlyEnabled: boolean;
	officialAlertTriggersEnabled: boolean;
	sendTelegram: boolean;
	sendSms: boolean;
	officialWarningsEnabled: boolean;
	morningEnabled: boolean;
	morningTime: string;
	eveningEnabled: boolean;
	eveningTime: string;
	endDate: string | null;
	// Issue #1361/#1372 S1b: Tagesfenster — Anlegen folgt dem Trip-Muster
	// (#622), das Feld gehört von Anfang an zur Bedienfläche (Default 4/19).
	dayWindowStartHour: number;
	dayWindowEndHour: number;
	alertCooldownMinutes?: number;
	alertQuietFrom?: string;
	alertQuietTo?: string;
	corridors: Corridor[];
	region: string;
	idealRanges: Record<string, IdealRange>;
	activeMetricKeys: string[];
	hourlyMetricKeys: string[];
	metricAlertLevels: Record<string, string>;
	telegramStyle: 'rich' | 'kurzform';
}

/**
 * Baut den POST-Payload fuer `/api/compare/presets` (Neuanlage). Anders als
 * beim Edit-Pfad gibt es kein `original` zum Round-Trippen — alle Felder
 * kommen direkt aus dem Wizard-Zustand.
 */
export function buildNewComparePresetPayload(fields: NewComparePresetFields): Record<string, unknown> {
	return {
		name: fields.name,
		location_ids: fields.pickedIds,
		profil: fields.activityProfile ?? 'wandern',
		// fields.schedule ist 'daily_morning'|'daily_evening'|'weekly'; Preset-API erwartet 'daily'|'weekly'|'manual'
		schedule: fields.schedule.startsWith('daily')
			? 'daily'
			: fields.schedule === 'weekly'
				? 'weekly'
				: 'manual',
		// Issue #1268: hour_from/hour_to/forecast_hours werden beim Anlegen nicht
		// mehr gesendet — das Go-Backend setzt beim Create eigene Defaults.
		official_alerts_enabled: fields.officialAlertsEnabled, // Issue #1040
		radar_alert_enabled: fields.radarAlertEnabled, // Issue #1041 Slice 2
		hourly_enabled: fields.hourlyEnabled, // Issue #1107
		// Issue #1216 Slice 2b: Amtliche-Warnungen-Alarm-Trigger + Kanal-Opt-in.
		official_alert_triggers_enabled: fields.officialAlertTriggersEnabled,
		send_telegram: fields.sendTelegram,
		send_sms: fields.sendSms,
		// Issue #1258 S4 (AC-27/E3): unconditional wie die Geschwister-Booleans
		// oben — Neuanlagen tragen immer official_warnings.enabled (F1-Default
		// false), kein sources-Feld (FE schreibt sources nie).
		official_warnings: { enabled: fields.officialWarningsEnabled },
		// Issue #1232 Scheibe 2b: Zwei-Slot-Zeitplan (Neu-Preset-Defaults
		// identisch zur Go-Create-Default-Tabelle aus Scheibe 2a). end_date
		// wird nur gesendet, wenn gesetzt — kein Sentinel nötig beim Create.
		morning_enabled: fields.morningEnabled,
		morning_time: toHHMMSS(fields.morningTime),
		evening_enabled: fields.eveningEnabled,
		evening_time: toHHMMSS(fields.eveningTime),
		...(fields.endDate ? { end_date: fields.endDate } : {}),
		// Issue #1361/#1372 S1b: Tagesfenster — von Anfang an zur Bedienfläche,
		// analog morning_enabled/hourly_enabled oben immer gesendet.
		day_window_start_hour: fields.dayWindowStartHour,
		day_window_end_hour: fields.dayWindowEndHour,
		// Issue #1170: Alarm-Konfiguration — cooldown/quiet Top-Level (Trip-identisch).
		...(fields.alertCooldownMinutes !== undefined
			? { alert_cooldown_minutes: fields.alertCooldownMinutes }
			: {}),
		...(fields.alertQuietFrom !== undefined ? { alert_quiet_from: fields.alertQuietFrom } : {}),
		...(fields.alertQuietTo !== undefined ? { alert_quiet_to: fields.alertQuietTo } : {}),
		empfaenger: [],
		// Issue #1231 Slice 4: Top-Level-Feld (analog Go-Model ComparePreset.Corridors).
		corridors: fields.corridors,
		display_config: {
			region: fields.region,
			...(Object.keys(fields.idealRanges).length > 0 ? { ideal_ranges: fields.idealRanges } : {}),
			// Issue #1373 (S2 Scheibe B): Neuformat (Groesse + Auswertung). Die
			// Asymmetrie zum Edit-Pfad bleibt bewusst erhalten (#1191/F001): bei
			// leerer Auswahl laesst die Neuanlage den Key WEG, der Edit-Pfad
			// schreibt ihn explizit als [].
			...(fields.activeMetricKeys.length > 0
				? { active_metrics: toStoredActiveMetrics(fields.activeMetricKeys) }
				: {}),
			...(fields.hourlyMetricKeys.length > 0 ? { hourly_metrics: fields.hourlyMetricKeys } : {}),
			...(Object.keys(fields.metricAlertLevels).length > 0
				? { metric_alert_levels: fields.metricAlertLevels }
				: {}),
			// Issue #1260 S5: nur bei Abweichung vom Default persistieren.
			...(fields.telegramStyle !== 'rich' ? { telegram_style: fields.telegramStyle } : {})
		}
	};
}
