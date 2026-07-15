// State-Klasse fuer den Compare-Wizard (Orts-Vergleich).
// Issue #440. Spec: docs/specs/modules/issue_440_compare_wizard_shell_step1_step2.md
//
// Factory-Pattern: Instanziierung im +page.svelte mount (Safari-Reaktivitaets-Fix).
// Lazy imports von goto/api damit Unit-Tests die Klasse ohne Browser-APIs testen.

import type { ActivityProfile, ChannelLayouts, ComparePreset, Corridor } from '$lib/types';
import type { IdealRange } from './compareMetricDefs';
import { buildComparePresetSavePayload } from './compareEditorSave';
import { toHHMMSS } from '$lib/utils/time';

export type SaveStatus = 'idle' | 'saving' | 'ok' | 'error';

export class CompareWizardState {
	name = $state('');
	region = $state(''); // mapped: display_config.region
	activityProfile = $state<ActivityProfile | null>(null);
	pickedIds = $state<string[]>([]);
	isEditMode = $state(false);
	subscriptionId = $state<string | null>(null);
	subscriptionEnabled = $state(true);
	// round-trip Sicherheit fuer bestehende display_config-Felder
	existingDisplayConfig = $state<Record<string, unknown>>({});
	// Issue #441: Idealwerte pro Metrik (Step 3); leer = nicht in display_config.
	idealRanges = $state<Record<string, IdealRange>>({});
	// Issue #680: Slice 3 — aktive Metriken-Auswahl (aus display_config.active_metrics)
	activeMetricKeys = $state<string[]>([]);
	// Issue #1231 Slice 4 — Korridore (CorridorEditor context="vergleich"),
	// TOP-LEVEL Feld (Dual-Write spiegelt zusaetzlich in idealRanges/activeMetricKeys/
	// metricAlertLevels, s. corridorEditorState.ts::buildCompareCorridorSavePayload).
	corridors = $state<Corridor[]>([]);
	// Issue #1106: Slice C — Stundenverlauf-Metriken-Auswahl (aus display_config.hourly_metrics)
	hourlyMetricKeys = $state<string[]>([]);
	metricsManuallyEdited = $state(false);
	// Issue #442: Pro-Kanal-Layouts. null = Step 4 nicht besucht / nichts konfiguriert.
	channelLayouts = $state<ChannelLayouts | null>(null);
	// Issue #443 — Step 5 Versand-Felder
	sendEmail = $state(true);
	sendTelegram = $state(false);
	sendSms = $state(false);
	timeWindowStart = $state(9);
	timeWindowEnd = $state(16);
	forecastHours = $state(48);
	// Issue #1040: amtliche Warnungen ein/aus (Default true).
	officialAlertsEnabled = $state(true);
	// Issue #1041 Slice 2: Radar-Alarm ein/aus (Default AUS — opt-in).
	radarAlertEnabled = $state(false);
	// Issue #1107: Stundenverlauf-Sektion ein/aus (Default true).
	hourlyEnabled = $state(true);
	// Issue #1216 Slice 2b: Amtliche-Warnungen-Alarm-Trigger (Default AN —
	// sicherheitsrelevant, analog officialAlertsEnabled). Kanal-Opt-in nutzt die
	// bestehenden Runen sendTelegram/sendSms (Versand-Tab), keine neue Kanal-Rune.
	officialAlertTriggersEnabled = $state(true);
	// Issue #1258 S2: Persistenz-Verdrahtung folgt in S4 (toPresetPayload/Hydration).
	// Default false = F1-Neuanlage-Default (analog Trip official_warnings.enabled).
	officialWarningsEnabled = $state(false);
	// Issue #1170 — Alarm-Konfiguration (Epic #1095 Scheibe 3/3), Trip-identische Keys.
	metricAlertLevels = $state<Record<string, string>>({});
	alertCooldownMinutes = $state<number | undefined>(undefined);
	alertQuietFrom = $state<string | undefined>(undefined);
	alertQuietTo = $state<string | undefined>(undefined);
	schedule = $state<'daily_morning' | 'daily_evening' | 'weekly'>('daily_morning');
	weekday = $state(0);
	// Issue #1232 Scheibe 2b — Zwei-Slot-Zeitplan + editierbare Laufzeit
	// (VersandTab context="vergleich"). Defaults identisch zur Go-Create-Default-
	// Tabelle (Scheibe 2a): morning an/07:00, evening aus/18:00, kein Enddatum.
	morningEnabled = $state(true);
	morningTime = $state('07:00');
	eveningEnabled = $state(false);
	eveningTime = $state('18:00');
	endDate = $state<string | null>(null);
	includeHourly = $state(false);
	topN = $state(3);
	saveStatus = $state<SaveStatus>('idle');
	saveError = $state<string | null>(null);

	// --- API-Aktionen --------------------------------------------------------
	// Issue #1250 Scheibe 0: die beiden Legacy-Save-Methoden (enabled-Toggle +
	// Voll-Payload-Save) wurden entfernt — Totcode, schrieb in den stillgelegten
	// Legacy-Drittstack /api/subscriptions (#1131). Aktive Speicherpfade:
	// saveNewPreset() (Create) / saveComparePreset() (Edit), beide gegen
	// /api/compare/presets*.

	/**
	 * Issue #681: Create-Modus — legt neues Preset via POST /api/compare/presets an.
	 * Wird von "Briefing aktivieren" im Header aufgerufen.
	 */
	async saveNewPreset(): Promise<void> {
		this.saveStatus = 'saving';
		this.saveError = null;
		const payload = {
			name: this.name,
			location_ids: this.pickedIds,
			profil: this.activityProfile ?? 'wandern',
			// wiz.schedule ist 'daily_morning'|'daily_evening'|'weekly'; Preset-API erwartet 'daily'|'weekly'|'manual'
			schedule: this.schedule.startsWith('daily') ? 'daily' : this.schedule === 'weekly' ? 'weekly' : 'manual',
			hour_from: this.timeWindowStart,
			hour_to: this.timeWindowEnd,
			forecast_hours: this.forecastHours, // Issue #764: Horizont persistieren
			official_alerts_enabled: this.officialAlertsEnabled, // Issue #1040
			radar_alert_enabled: this.radarAlertEnabled, // Issue #1041 Slice 2
			hourly_enabled: this.hourlyEnabled, // Issue #1107
			// Issue #1216 Slice 2b: Amtliche-Warnungen-Alarm-Trigger + Kanal-Opt-in.
			official_alert_triggers_enabled: this.officialAlertTriggersEnabled,
			send_telegram: this.sendTelegram,
			send_sms: this.sendSms,
			// Issue #1232 Scheibe 2b: Zwei-Slot-Zeitplan (Neu-Preset-Defaults
			// identisch zur Go-Create-Default-Tabelle aus Scheibe 2a). end_date
			// wird nur gesendet, wenn gesetzt — kein Sentinel nötig beim Create.
			morning_enabled: this.morningEnabled,
			morning_time: toHHMMSS(this.morningTime),
			evening_enabled: this.eveningEnabled,
			evening_time: toHHMMSS(this.eveningTime),
			...(this.endDate ? { end_date: this.endDate } : {}),
			// Issue #1170: Alarm-Konfiguration — cooldown/quiet Top-Level (Trip-identisch).
			...(this.alertCooldownMinutes !== undefined
				? { alert_cooldown_minutes: this.alertCooldownMinutes }
				: {}),
			...(this.alertQuietFrom !== undefined ? { alert_quiet_from: this.alertQuietFrom } : {}),
			...(this.alertQuietTo !== undefined ? { alert_quiet_to: this.alertQuietTo } : {}),
			empfaenger: [],
			// Issue #1231 Slice 4: Top-Level-Feld (analog Go-Model ComparePreset.Corridors).
			corridors: this.corridors,
			display_config: {
				region: this.region,
				...(Object.keys(this.idealRanges).length > 0 ? { ideal_ranges: this.idealRanges } : {}),
				...(this.channelLayouts !== null ? { channel_layouts: this.channelLayouts } : {}),
				...(this.activeMetricKeys.length > 0 ? { active_metrics: this.activeMetricKeys } : {}),
				...(this.hourlyMetricKeys.length > 0 ? { hourly_metrics: this.hourlyMetricKeys } : {}),
				...(this.topN !== undefined ? { top_n: this.topN } : {}),
				...(Object.keys(this.metricAlertLevels).length > 0
					? { metric_alert_levels: this.metricAlertLevels }
					: {})
			}
		};
		try {
			const { api } = await import('$lib/api');
			const { goto } = await import('$app/navigation');
			const created = await api.post('/api/compare/presets', payload);
			this.saveStatus = 'ok';
			await goto('/compare/' + (created as { id: string }).id);
		} catch (e) {
			this.saveStatus = 'error';
			this.saveError = extractErrorMessage(e);
		}
	}

	/**
	 * Edit-Modus: speichert Preset via PUT /api/compare/presets/{id}.
	 * Round-Trip-Spread via buildComparePresetSavePayload — nicht editierte Felder
	 * (empfaenger, schedule, hour_from/to, weekday) bleiben erhalten.
	 * Issue #679.
	 */
	async saveComparePreset(original: ComparePreset): Promise<void> {
		this.saveStatus = 'saving';
		this.saveError = null;
		const { url, body } = buildComparePresetSavePayload(original, {
			name: this.name,
			activityProfile: this.activityProfile,
			pickedIds: this.pickedIds,
			region: this.region,
			idealRanges: this.idealRanges,
			channelLayouts: this.channelLayouts,
			activeMetricKeys: this.activeMetricKeys,
			hourlyMetricKeys: this.hourlyMetricKeys, // Issue #1106
			forecastHours: this.forecastHours, // Issue #764
			officialAlertsEnabled: this.officialAlertsEnabled, // Issue #1040
			radarAlertEnabled: this.radarAlertEnabled, // Issue #1041 Slice 2
			hourlyEnabled: this.hourlyEnabled, // Issue #1107
			topN: this.topN, // Issue #1104
			metricAlertLevels: this.metricAlertLevels, // Issue #1170
			alertCooldownMinutes: this.alertCooldownMinutes,
			alertQuietFrom: this.alertQuietFrom,
			alertQuietTo: this.alertQuietTo,
			corridors: this.corridors // Issue #1231 Slice 4
		});
		try {
			const { api } = await import('$lib/api');
			const { goto } = await import('$app/navigation');
			await api.put(url, body);
			this.saveStatus = 'ok';
			await goto('/compare/' + original.id);
		} catch (e) {
			this.saveStatus = 'error';
			this.saveError = extractErrorMessage(e);
		}
	}
}

function extractErrorMessage(e: unknown): string {
	if (e && typeof e === 'object') {
		const obj = e as Record<string, unknown>;
		if (typeof obj.detail === 'string' && obj.detail) return obj.detail;
		if (typeof obj.error === 'string' && obj.error) return obj.error;
		if (typeof obj.message === 'string' && obj.message) return obj.message;
	}
	return 'Fehler beim Speichern';
}
