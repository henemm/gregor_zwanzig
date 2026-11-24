// Issue #679 — Pure-Function: Compare-Preset-Save-Payload
// Spec: docs/specs/modules/issue_679_compare_editor_edit.md § AC-3
//
// Round-Trip-Spread: nicht editierte Felder (empfaenger, schedule, hour_from/to,
// weekday, previous_schedule) kommen unveraendert aus `original`. Nur explizit
// geaenderte Felder werden ueberschrieben. Verhindert Datenverlust beim Speichern.
//
// Kein Browser-/SvelteKit-Import — lauffaehig unter node --experimental-strip-types.

import type { ComparePreset, ActivityProfile, Corridor } from '../../types.ts';
import type { IdealRange } from '../shared/wetter-tab/corridorEditorState.ts';
import { toHHMMSS } from '../../utils/time.ts';
import { pickEigenfelder } from '../shared/pickEigenfelder.ts';
import {
	newEntityAlertChannelDefault,
	type AlertChannelState
} from '../shared/alarme-tab/alertChannelState.ts';
// Issue #1373 (S2 Scheibe B): Speicherformat der Metrik-Auswahl ist Größe +
// Auswertung. Die Übersetzung kommt aus der bereits geladenen Antwort von
// GET /api/compare/metrics (Scheibe A liefert metric_id/aggregation je Eintrag) —
// keine zweite Tabelle im Frontend, keine zusätzliche Anfrage.
import { toStoredActiveMetrics } from '../shared/weather-metrics-tab/compareMetricSelection.ts';
// Issue #1703 Scheibe 8: Typ der Kanal-Ebene des Feldsatzes (Hub-Hydration);
// geschrieben wird `channel_active_metrics` seit #3276 nicht mehr.
import type { CompareChannelActiveMetrics } from '../shared/weather-metrics-tab/compareChannelMetricLayouts.ts';
import { baueDiff, type KanalMap } from '../shared/alarme-tab/alertMetricChannels.ts';
import { STANDARD_VORLAGE } from '../shared/wetter-tab/ampelModell.ts';
import { felderNutzlast, type KarteAnlegeStand } from '../shared/wetter-tab/wasStehtWoSpeicherung.ts';

/** Issue #1895 S3b1: `{alert_metric_channels: Diff}` oder `{}` (kein Diff ⇒ Feld fehlt). */
function kanalDiffFeld(basis: KanalMap | undefined, aktuell: KanalMap | undefined): { alert_metric_channels?: KanalMap } {
	const diff = baueDiff(basis, aktuell);
	return Object.keys(diff).length > 0 ? { alert_metric_channels: diff } : {};
}

export interface CompareEditorEdits {
	name: string;
	activityProfile: ActivityProfile | null;
	pickedIds: string[];
	region: string;
	idealRanges: Record<string, IdealRange>;
	// Issue #680: Slice 3 — aktive Metriken (AC-10). Optional → rückwärtskompatibel.
	activeMetricKeys?: string[];
	// Issue #3276 (Spec-AC-38, Epic #3122): `channelActiveMetricKeys`,
	// `hourlyMetricKeys`, `outlookMetricKeys`, `outlookMetricFormats`,
	// `hourlyMetricFormats` sind entfallen. Der Ortsvergleich schreibt die
	// Altschluessel nicht mehr; die Tabelle „Was steht wo" (`placements`) ist
	// die einzige Quelle (ADR-0124).
	// Issue #1361/#1368: 3-Tages-Ausblick-Sektion ein/aus (Top-Level, analog
	// hourlyEnabled). Optional → rückwärtskompatibel.
	outlookEnabled?: boolean;
	// Issue #1040: amtliche Warnungen ein/aus. Optional → rückwärtskompatibel.
	officialAlertsEnabled?: boolean;
	// Issue #1041 Slice 2: Radar-Alarm ein/aus (Default AUS). Optional → rückwärtskompatibel.
	radarAlertEnabled?: boolean;
	// Issue #1107: Stundenverlauf-Sektion ein/aus. Optional → rückwärtskompatibel.
	hourlyEnabled?: boolean;
	// Issue #1170: Alarm-Konfiguration (Epic #1095 Scheibe 3/3). Optional → rückwärtskompatibel.
	metricAlertLevels?: Record<string, string>;
	// Issue #1461 S3b-2b: Kanal-Schwelle (analog metricAlertLevels), TOP-LEVEL
	// Feld (Go-Model ComparePreset.AlertChannelThresholds, NICHT in
	// display_config). Optional → rückwärtskompatibel (undefined = Feld nicht
	// editiert → Round-Trip via `...original`).
	channelThresholds?: Record<string, string>;
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
	// Issue #1745 A / #2293 S2: Premium-SMS-BRIEFING-Opt-in (Versand-Reiter).
	// Optional → rückwärtskompatibel (undefined = Feld nicht editiert → Round-Trip).
	sendPremiumSms?: boolean;
	// Issue #2293 Scheibe S2 (Epic #1374/#2345): ALARM-Kanal-Objekt (Alarme-
	// Reiter), unabhängig von sendTelegram/sendSms/sendPremiumSms oben. Optional
	// → rückwärtskompatibel (undefined = Feld nicht editiert → Round-Trip).
	alertChannels?: { email: boolean; telegram: boolean; sms: boolean; premium_sms: boolean };
	// Issue #1895 S3b1: Kanäle je Wettergröße; gesendet wird nur der Diff gegen `original`.
	alertMetricChannels?: KanalMap;
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

	// Issue #3039 (ADR-0119, loest #1351 AC-6 ab): channel_layouts ist wieder
	// Nutzerstand (Karte „Inhalt je Kanal“) und bleibt wie alle anderen Felder
	// beim Speichern aus einem anderen Reiter erhalten (Read-Modify-Write).
	const baseDisplayConfig: Record<string, unknown> =
		(original.display_config as Record<string, unknown>) ?? {};
	const displayConfig: Record<string, unknown> = {
		...baseDisplayConfig,
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

	// Issue #3276: die sechs Altschluessel (`channel_layouts`, `outlook_metrics`,
	// `outlook_metric_formats`, `channel_active_metrics`, `hourly_metrics`,
	// `hourly_metric_formats`) werden hier nie gesetzt. Bestandswerte reisen nur
	// ueber den `...baseDisplayConfig`-Spread oben unveraendert mit (Read-Modify-
	// Write); die Teilfeld-Speicherer schneiden sie ohnehin heraus.

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
		// Issue #1361/#1368: analoges Round-Trip-Prinzip für outlook_enabled.
		...(edits.outlookEnabled !== undefined ? { outlook_enabled: edits.outlookEnabled } : {}),
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
		// Issue #1745 A / #2293 S2: analoges Round-Trip-Prinzip für das Premium-SMS-
		// Briefing-Opt-in.
		...(edits.sendPremiumSms !== undefined ? { send_premium_sms: edits.sendPremiumSms } : {}),
		// Issue #2293 Scheibe S2: analoges Round-Trip-Prinzip für den Alarm-
		// Kanal-Bestand (Alarme-Reiter) — unabhängig von den drei Feldern oben.
		...(edits.alertChannels !== undefined ? { alert_channels: edits.alertChannels } : {}),
		// Issue #1895 S3b1: Diff statt Vollmap (Server ersetzt je Schlüssel); kein Diff ⇒ `undefined`
		// überdeckt den `...original`-Bestand, das Feld wird nicht gesendet.
		...(edits.alertMetricChannels !== undefined
			? { alert_metric_channels: kanalDiffFeld(original.alert_metric_channels, edits.alertMetricChannels).alert_metric_channels }
			: {}),
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
		...(edits.dayWindowEndHour !== undefined ? { day_window_end_hour: edits.dayWindowEndHour } : {}),
		// Issue #1461 S3b-2b: analoges Round-Trip-Prinzip für die Kanal-Schwelle —
		// TOP-LEVEL Feld (Go-Model ComparePreset.AlertChannelThresholds), NICHT in
		// display_config verschachtelt (anders als metric_alert_levels oben).
		...(edits.channelThresholds !== undefined
			? { alert_channel_thresholds: edits.channelThresholds }
			: {})
	};

	return { url, body };
}

// ─── Teilfeld-Pfad (PUT, Issue #2375) ───────────────────────────────────────
//
// Jeder Schreibweg des Ortsvergleichs (Reiter, Kopf, Orte, Status) sendet NUR
// seine Eigenfelder. Der Go-Handler mergt fehlende Felder als „unverändert"
// (mergeBriefingPatch/mergeConfigMap) — ein Voll-Spread der lokalen, womöglich
// veralteten Basis schriebe dagegen Fremdwerte zurück (#2375, #2381).
// `buildComparePresetSavePayload` bleibt für die Neuanlage unverändert.

/**
 * PUT-Nutzlast mit ausschließlich den übergebenen Feldern. `felder` sind
 * Top-Level-Schlüssel des Datensatzes (snake_case, bereits übersetzt);
 * `displayConfigFelder` landen unter `display_config` — nur diese Schlüssel.
 * `undefined`-Werte werden nicht gesendet; `[]`, `{}` und `""` schon (Lösch-Semantik).
 */
export function buildComparePresetPartialPayload(
	id: string,
	felder: Record<string, unknown>,
	displayConfigFelder?: Record<string, unknown>
): { url: string; body: ComparePreset } {
	const body: Record<string, unknown> = {};
	for (const [k, v] of Object.entries(felder)) {
		if (v !== undefined) body[k] = v;
	}
	if (displayConfigFelder) {
		const dc: Record<string, unknown> = {};
		for (const [k, v] of Object.entries(displayConfigFelder)) {
			if (v !== undefined) dc[k] = v;
		}
		if (Object.keys(dc).length > 0) body.display_config = dc;
	}
	return { url: '/api/compare/presets/' + id, body: body as unknown as ComparePreset };
}

/**
 * Schneidet aus einer vollständig gebauten Nutzlast (die Leseübersetzungen wie
 * `toStoredActiveMetrics`, `toHHMMSS`, `end_date: null → ""` schon angewendet
 * hat) die Eigenfelder eines Reiters heraus.
 */
export function waehleEigenfelder(
	voll: { url: string; body: ComparePreset },
	topKeys: readonly string[],
	displayKeys: readonly string[] = [],
	displayConfigExtra: Record<string, unknown> = {}
): { url: string; body: ComparePreset } {
	const b = voll.body as unknown as Record<string, unknown>;
	// Adapter auf die geteilte Auswahl (#1433): gleiche Regeln wie im Trip.
	const body = pickEigenfelder(b, { top: topKeys });
	const dc = {
		...((pickEigenfelder(b, { display: displayKeys }).display_config as object | undefined) ?? {}),
		...Object.fromEntries(Object.entries(displayConfigExtra).filter(([, v]) => v !== undefined))
	};
	if (Object.keys(dc).length > 0) body.display_config = dc;
	return { url: voll.url, body: body as unknown as ComparePreset };
}

// ─── Create-Pfad (POST /api/compare/presets) ──────────────────────────────
//
// Issue #1360 F002: Pure-Function-Gegenstueck zu buildComparePresetSavePayload
// fuer die Neuanlage (Speichern in `CompareNewEditor.svelte`). Analoges Prinzip
// (keine Browser-/SvelteKit-Imports, plain Input-Objekt statt $state-Runen) —
// damit ist die Create-Payload ohne Svelte-Runtime testbar (kein nachgebautes
// Objekt im Test, keine Mock-Rückspiegelung).

export interface NewComparePresetFields {
	name: string;
	pickedIds: string[];
	// Issue #3198 (S4b-3): wird beim Anlegen nicht mehr gelesen — `profil` ist
	// konstant „allgemein“, maßgeblich ist die Vorlage (`vorlageId`, ADR-0108).
	activityProfile?: ActivityProfile | null;
	// Issue #3198: angezeigte Vorlage; reist als `display_config.ampel.template`.
	vorlageId?: string;
	schedule: 'daily_morning' | 'daily_evening' | 'weekly';
	officialAlertsEnabled: boolean;
	radarAlertEnabled: boolean;
	hourlyEnabled: boolean;
	// Issue #1361/#1368: 3-Tages-Ausblick-Schalter, analog hourlyEnabled.
	// Optional, damit bestehende Aufrufer/Tests ohne das Feld unveraendert
	// funktionieren (der Wizard setzt es immer).
	outlookEnabled?: boolean;
	officialAlertTriggersEnabled: boolean;
	sendTelegram: boolean;
	sendSms: boolean;
	// Issue #1745 A (AC-11) / #2293 S2: Premium-SMS-BRIEFING-Opt-in. Pflichtfeld
	// wie seine beiden Geschwister-Booleans — ein weggelassener Schlüssel
	// überliesse den Default dem Server.
	sendPremiumSms: boolean;
	// Issue #2293 Scheibe S2 (Implementation Details Abschnitt 1/7, AC-6):
	// ALARM-Kanal-Bestand des Alarme-Reiters bei der Neuanlage. Optional — ohne
	// Wert gilt der geteilte Neuanlage-Default (Issue #2518: `{email:true,
	// telegram:true, sms:false, premium_sms:false}`), damit `AlertChannels` beim
	// Create nie `nil` ist.
	alertChannels?: { email: boolean; telegram: boolean; sms: boolean; premium_sms: boolean };
	alertMetricChannels?: KanalMap; // Issue #1895 S3b1
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
	// Issue #1366 F002 (symmetrisch zu F001/hourlyMetricKeys): `null` = „nie
	// eingestellt" -- der Schluessel `active_metrics` wird dann gar nicht
	// gesendet (Default bleibt „alle").
	activeMetricKeys: string[] | null;
	// Issue #3276: `channelActiveMetricKeys`, `hourlyMetricKeys`,
	// `outlookMetricKeys`, `outlookMetricFormats`, `hourlyMetricFormats` sind
	// entfallen -- die Neuanlage traegt keinen Altschluessel mehr, die Tabelle
	// „Was steht wo" ergaenzt der Server aus der Grundauswahl (#3237).
	metricAlertLevels: Record<string, string>;
	// Issue #1461 S3b-2b: Kanal-Schwelle beim Anlegen (PO-Entscheid 2026-08-06,
	// Spec v1.3) — nur nicht-leere Werte werden gesendet (analog
	// metricAlertLevels unten), Startwert "gering" bleibt implizit. Optional →
	// rückwärtskompatibel (bestehende Aufrufer/Tests ohne das Feld funktionieren
	// unverändert, der Wizard setzt es immer).
	channelThresholds?: Record<string, string>;
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
		// Issue #3198 (S4b-3): Go verlangt ein gueltiges `profil`; „allgemein“ ist neutral,
		// die Bewertung folgt der Vorlage (display_config.ampel.template unten).
		profil: 'allgemein',
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
		// Issue #1361/#1368: nur senden, wenn die Bedienflaeche einen Wert
		// geliefert hat (undefined = Aufrufer kennt das Feld nicht).
		...(fields.outlookEnabled !== undefined ? { outlook_enabled: fields.outlookEnabled } : {}),
		// Issue #1216 Slice 2b: Amtliche-Warnungen-Alarm-Trigger + Kanal-Opt-in.
		official_alert_triggers_enabled: fields.officialAlertTriggersEnabled,
		send_telegram: fields.sendTelegram,
		send_sms: fields.sendSms,
		// Issue #1745 A (AC-11) / #2293 S2: unconditional wie die beiden Geschwister oben.
		send_premium_sms: fields.sendPremiumSms,
		// Issue #2293 Scheibe S2 (AC-1/Abschnitt 1): IMMER gesendet (nie
		// weggelassen), damit `AlertChannels` beim Create nie `nil` ist.
		// Issue #2518: Rueckfall ist der geteilte Neuanlage-Default (dieselbe Quelle
		// wie der Alarme-Reiter), NICHT mehr aus den Briefing-Schaltern abgeleitet.
		alert_channels: fields.alertChannels ?? newEntityAlertChannelDefault(),
		...kanalDiffFeld({}, fields.alertMetricChannels),
		// Issue #1258 S4 (AC-27/E3): unconditional wie die Geschwister-Booleans
		// oben — Neuanlagen tragen immer official_warnings.enabled (Vorgabe true,
		// #3047 Runde 7), kein sources-Feld (FE schreibt sources nie).
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
		// Issue #1461 S3b-2b: Kanal-Schwelle beim Anlegen — TOP-LEVEL Feld (Go-Model
		// ComparePreset.AlertChannelThresholds), nur gesendet wenn mindestens ein
		// Kanal vom Startwert "gering" abweicht (analog metric_alert_levels unten).
		...(Object.keys(fields.channelThresholds ?? {}).length > 0
			? { alert_channel_thresholds: fields.channelThresholds }
			: {}),
		// Issue #1231 Slice 4: Top-Level-Feld (analog Go-Model ComparePreset.Corridors).
		corridors: fields.corridors,
		display_config: {
			region: fields.region,
			// Issue #3198: immer die angezeigte Vorlage — ohne Besuch des Reiters Wetter
			// fuellt der Server die Metriken daraus (vorher Rueckfall auf das Profil).
			ampel: { template: fields.vorlageId ?? STANDARD_VORLAGE },
			...(Object.keys(fields.idealRanges).length > 0 ? { ideal_ranges: fields.idealRanges } : {}),
			// Issue #1366 F002 (Fix-Runde 2, loest die S3B-Fassung dieses Kommentars
			// ab): `null` ("Wetter-Metriken-Bereich nie geoeffnet/beruehrt") laesst
			// den Schluessel ganz weg -- der Resolver erkennt "Feld fehlt" (= alle
			// Groessen), statt einer faelschlich gesendeten Leerauswahl (Adversary
			// F002). Eine ECHTE bewusste Leerauswahl (`[]`, Bereich geoeffnet und
			// alles abgewaehlt) wird weiterhin unbedingt gesendet -- AC-7 bleibt gueltig.
			...(fields.activeMetricKeys !== null
				? { active_metrics: toStoredActiveMetrics(fields.activeMetricKeys) }
				: {}),
			// Issue #3276: keiner der sechs Altschluessel (`channel_layouts`,
			// `outlook_metrics`, `outlook_metric_formats`, `channel_active_metrics`,
			// `hourly_metrics`, `hourly_metric_formats`) -- auch nicht leer.
			...(Object.keys(fields.metricAlertLevels).length > 0
				? { metric_alert_levels: fields.metricAlertLevels }
				: {}),
			// Issue #1260 S5: nur bei Abweichung vom Default persistieren.
			...(fields.telegramStyle !== 'rich' ? { telegram_style: fields.telegramStyle } : {})
		}
	};
}

// ─── Feldsatz des Ortsvergleichs (Issue #2727, Epic #2345 DoD-1) ──────────
//
// Ersetzt das geloeschte geteilte Zustandsmodul: reine Daten-Factory mit den
// Startwerten der frueheren Klassenfelder (ohne die toten Felder saveStatus,
// saveError, metricsManuallyEdited, weekday). Hub (CompareTabs.svelte) und
// Anlege-Editor (CompareNewEditor.svelte) halten daraus jeweils komponentenlokal
// ihren reaktiven Feldsatz. Jeder Aufruf liefert ein frisches Objekt samt
// frischen Unterobjekten — keine modulglobale Instanz (AC-17).
// Spec: docs/specs/modules/feat_2727_compare_wizardstate_abloesen.md

export interface CompareFeldsatz {
	name: string;
	region: string; // mapped: display_config.region
	activityProfile: ActivityProfile | null;
	// Issue #3198 (S4b-3): Vorlage der Neuanlage (Quelle der Abo-Sicht des Reiters Wetter).
	vorlageId: string;
	pickedIds: string[];
	isEditMode: boolean;
	// Issue #441: Idealwerte pro Metrik; leer = nicht in display_config.
	idealRanges: Record<string, IdealRange>;
	// Issue #680/#1366 F002: `null` = „nie eingestellt" (Default-Menge aktiv),
	// `[]` = bewusste Leerauswahl.
	activeMetricKeys: string[] | null;
	// Issue #1703 Scheibe 8: kanal-eigene Auswahl der Uebersichtstabelle; `null`
	// je Kanal = nie editiert (folgt der Grundauswahl).
	channelActiveMetricKeys: CompareChannelActiveMetrics;
	// Issue #1231 Slice 4: Korridore (CorridorEditor context="vergleich").
	corridors: Corridor[];
	// Issue #1106/#1366 F001: `null` = „nie eingestellt", `[]` = bewusst leer.
	hourlyMetricKeys: string[] | null;
	// Issue #1361/#1368: Spaltenauswahl des 3-Tages-Ausblicks, Semantik wie oben.
	outlookMetricKeys: string[] | null;
	// Issue #2049: Roh/Einfach je Ausblick-Groesse; `null` = „nie eingestellt".
	outlookMetricFormats: Record<string, boolean> | null;
	// Issue #3097: Roh/Einfach je Stundenverlauf-Groesse; `null` = „nie eingestellt".
	hourlyMetricFormats: Record<string, boolean> | null;
	// Issue #443: Versand-Felder.
	sendEmail: boolean;
	sendTelegram: boolean;
	sendSms: boolean;
	// Issue #1745 A / #2293 S2: Premium-SMS-Briefing-Opt-in (Default AUS).
	sendPremiumSms: boolean;
	// Issue #2293 S2: Alarm-Kanal-Bestand; `undefined` = nie umgeschaltet
	// (alarmePropsAus faellt dann auf den Neuanlage-Default zurueck).
	channels: AlertChannelState | undefined;
	officialAlertsEnabled: boolean; // Issue #1040
	radarAlertEnabled: boolean; // Issue #1041 Slice 2
	hourlyEnabled: boolean; // Issue #1107
	outlookEnabled: boolean; // Issue #1361/#1368
	officialAlertTriggersEnabled: boolean; // Issue #1216 Slice 2b
	officialWarningsEnabled: boolean; // Issue #1258
	metricAlertLevels: Record<string, string>; // Issue #1170
	channelThresholds: Record<string, string>; // Issue #1461 S3b-2b
	alertMetricChannels: KanalMap; // Issue #1895 S3b1
	telegramStyle: 'rich' | 'kurzform'; // Issue #1260 S5
	alertCooldownMinutes: number | undefined;
	alertQuietFrom: string | undefined;
	alertQuietTo: string | undefined;
	schedule: 'daily_morning' | 'daily_evening' | 'weekly';
	// Issue #1232 Scheibe 2b: Zwei-Slot-Zeitplan + Laufzeit.
	morningEnabled: boolean;
	morningTime: string;
	eveningEnabled: boolean;
	eveningTime: string;
	endDate: string | null;
	// Issue #1361/#1372 S1b: Tagesfenster (Default 4/19 wie der Renderer).
	dayWindowStartHour: number;
	dayWindowEndHour: number;
}

/** Frischer Standard-Feldsatz des Ortsvergleichs (reine Daten, keine Runen). */
export function compareFeldsatzStandard(): CompareFeldsatz {
	return {
		name: '',
		region: '',
		activityProfile: null,
		vorlageId: STANDARD_VORLAGE,
		pickedIds: [],
		isEditMode: false,
		idealRanges: {},
		activeMetricKeys: null,
		channelActiveMetricKeys: { email: null, telegram: null, sms: null },
		corridors: [],
		hourlyMetricKeys: null,
		outlookMetricKeys: null,
		outlookMetricFormats: null,
		hourlyMetricFormats: null,
		sendEmail: true,
		sendTelegram: false,
		sendSms: false,
		sendPremiumSms: false,
		channels: undefined,
		officialAlertsEnabled: true,
		radarAlertEnabled: false,
		hourlyEnabled: true,
		outlookEnabled: true,
		officialAlertTriggersEnabled: true,
		// #3047 Runde 7 (PO 2026-11-16, loest #1258 AC-4 ab): Briefing UND Alarm an.
		officialWarningsEnabled: true,
		metricAlertLevels: {},
		channelThresholds: {},
		alertMetricChannels: {},
		telegramStyle: 'rich',
		alertCooldownMinutes: undefined,
		alertQuietFrom: undefined,
		alertQuietTo: undefined,
		schedule: 'daily_morning',
		morningEnabled: true,
		morningTime: '07:00',
		eveningEnabled: false,
		eveningTime: '18:00',
		endDate: null,
		dayWindowStartHour: 4,
		dayWindowEndHour: 19
	};
}

/**
 * Issue #3276 (Fix-Loop F002): POST-Rumpf des Anlege-Editors (CompareNewEditor.svelte) aus
 * dem Feldsatz und dem Stand des Reiters Wetter. Keine Altschluessel (Kanal-Overrides,
 * Stundenverlauf, Ausblick) -- die Tabelle „Was steht wo" ergaenzt der Server (#3237).
 */
export function baueVergleichAnlegeRumpf(
	wiz: CompareFeldsatz,
	wetter: { ampel?: object; auswahl?: unknown; karte?: KarteAnlegeStand } = {}
): Record<string, unknown> {
	const payload = buildNewComparePresetPayload({
		name: wiz.name,
		pickedIds: wiz.pickedIds,
		vorlageId: wiz.vorlageId, // Issue #3198: angezeigte Vorlage (profil ist konstant)
		schedule: wiz.schedule,
		officialAlertsEnabled: wiz.officialAlertsEnabled, // Issue #1040
		radarAlertEnabled: wiz.radarAlertEnabled, // Issue #1041 Slice 2
		hourlyEnabled: wiz.hourlyEnabled, // Issue #1107
		outlookEnabled: wiz.outlookEnabled, // Issue #1361/#1368
		officialAlertTriggersEnabled: wiz.officialAlertTriggersEnabled, // Issue #1216 Slice 2b
		sendTelegram: wiz.sendTelegram,
		sendSms: wiz.sendSms,
		sendPremiumSms: wiz.sendPremiumSms, // Issue #1745 A (AC-11) / #2293 S2
		alertChannels: wiz.channels, // Issue #2293 Scheibe S2 (Abschnitt 1/7)
		officialWarningsEnabled: wiz.officialWarningsEnabled, // Issue #1258 S4
		morningEnabled: wiz.morningEnabled, // Issue #1232 Scheibe 2b
		morningTime: wiz.morningTime,
		eveningEnabled: wiz.eveningEnabled,
		eveningTime: wiz.eveningTime,
		endDate: wiz.endDate,
		// Issue #1361/#1372 S1b: Tagesfenster gehört von Anfang an zur Bedienfläche.
		dayWindowStartHour: wiz.dayWindowStartHour,
		dayWindowEndHour: wiz.dayWindowEndHour,
		alertCooldownMinutes: wiz.alertCooldownMinutes, // Issue #1170
		alertQuietFrom: wiz.alertQuietFrom,
		alertQuietTo: wiz.alertQuietTo,
		corridors: wiz.corridors, // Issue #1231 Slice 4
		region: wiz.region,
		idealRanges: wiz.idealRanges,
		activeMetricKeys: wiz.activeMetricKeys,
		metricAlertLevels: wiz.metricAlertLevels, // Issue #1170
		channelThresholds: wiz.channelThresholds, // Issue #1461 S3b-2b
		alertMetricChannels: wiz.alertMetricChannels, // Issue #1895 S3b1
		telegramStyle: wiz.telegramStyle // Issue #1260 S5
	});
	// #2794 S3a Teil-PR 3: Abo-Ampel und Auswahl aus dem Reiter Wetter in display_config
	// (additiv; AC-37: active_metrics im Speicherformat, konsistent mit der Ampel).
	if (wetter.ampel)
		payload.display_config = {
			...((payload.display_config as object) ?? {}),
			ampel: wetter.ampel,
			...(wetter.auswahl ? { active_metrics: wetter.auswahl } : {})
		};
	if (wetter.karte) mitKarte(payload, wetter.karte);
	return payload;
}

/** #3306 (AC-2, AC-3): Tabelle der Karte und die gegenüber ihrem Start geänderten Schalter in den POST
 *  (hourly_enabled top-level, display_config.telegram_style); alles andere bleibt. Read-Modify-Write. */
function mitKarte(payload: Record<string, unknown>, karte: KarteAnlegeStand): void {
	const { display_config: dcDiff, ...rest } = felderNutzlast('vergleich', karte.felder, karte.felderStart) as { display_config?: object };
	Object.assign(payload, rest);
	payload.display_config = { ...((payload.display_config as object) ?? {}), ...(dcDiff ?? {}), placements: karte.placements };
}

/**
 * Issue #3276 (Fix-Loop 2, F-ADV1): der gesamte Anlege-Schritt -- Rumpf bauen und
 * POST /api/compare/presets absenden -- in einer Funktion, damit zwischen Rumpf-Bau und
 * Versand kein Altschluessel mehr unbemerkt eingebaut werden kann. Liefert die neue id.
 */
export async function legeVergleichAn(
	api: { post<T>(url: string, body: unknown): Promise<T> },
	wiz: CompareFeldsatz,
	wetter: { ampel?: object; auswahl?: unknown; karte?: KarteAnlegeStand } = {}
): Promise<{ id: string }> {
	return api.post<{ id: string }>('/api/compare/presets', baueVergleichAnlegeRumpf(wiz, wetter));
}
