// State-Klasse fuer den Compare-Wizard (Orts-Vergleich).
// Issue #440. Spec: docs/specs/modules/issue_440_compare_wizard_shell_step1_step2.md
//
// Factory-Pattern: Instanziierung im +page.svelte mount (Safari-Reaktivitaets-Fix).
// Lazy imports von goto/api damit Unit-Tests die Klasse ohne Browser-APIs testen.

import type { ActivityProfile, ComparePreset, Corridor } from '$lib/types';
import type { IdealRange } from '../shared/corridor-editor/corridorEditorState';
import type { CompareChannelActiveMetrics } from '../shared/weather-metrics-tab/compareChannelMetricLayouts';
import { buildComparePresetSavePayload, buildNewComparePresetPayload } from './compareEditorSave';

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
	// Issue #1366 F002 (symmetrisch zu F001/hourlyMetricKeys): `null` = „nie
	// eingestellt" (Default-Menge aktiv), `[]` = bewusste Leerauswahl. Init auf
	// `null`, NICHT `[]` -- sonst startet ein neuer Vergleich, dessen
	// Wetter-Metriken-Bereich nie geoeffnet wurde, bereits als „bewusst leer"
	// (materializeActiveMetricKeys, compareMetricOrder.ts).
	activeMetricKeys = $state<string[] | null>(null);
	// Issue #1703 Scheibe 8 — kanal-eigene Auswahl DERSELBEN Uebersichtstabelle
	// (display_config.channel_active_metrics). `null` je Kanal = nie editiert,
	// der Kanal folgt der Grundauswahl `activeMetricKeys` (ADR-0050 Regel 1/2:
	// die Grundauswahl ist das MAXIMUM, ein Kanal darf nur abwaehlen). `[]` =
	// bewusste Leerauswahl fuer diesen Kanal — dieselbe „fehlend != leer"-
	// Unterscheidung wie oben (#1191/#1366).
	channelActiveMetricKeys = $state<CompareChannelActiveMetrics>({
		email: null,
		telegram: null,
		sms: null
	});
	// Issue #1231 Slice 4 — Korridore (CorridorEditor context="vergleich"),
	// TOP-LEVEL Feld (Dual-Write spiegelt zusaetzlich in idealRanges/activeMetricKeys/
	// metricAlertLevels, s. corridorEditorState.ts::buildCompareCorridorSavePayload).
	corridors = $state<Corridor[]>([]);
	// Issue #1106: Slice C — Stundenverlauf-Metriken-Auswahl (aus display_config.hourly_metrics)
	// Issue #1366 F001: `null` = „nie eingestellt" (Default-Menge aktiv),
	// `[]` = bewusste Leerauswahl. Init auf `null`, NICHT `[]` -- sonst startet
	// ein neuer Vergleich bereits als „bewusst leer" (materializeHourlyMetricKeys).
	hourlyMetricKeys = $state<string[] | null>(null);
	// Issue #1361 Befund 2/#1368: Spaltenauswahl des 3-Tages-Ausblicks (aus
	// display_config.outlook_metrics, Neuformat). `null` = „nie eingestellt"
	// (die heutigen sieben Spalten), `[]` = bewusste Leerauswahl (Block
	// entfaellt) — dieselbe Semantik wie hourlyMetricKeys/activeMetricKeys.
	outlookMetricKeys = $state<string[] | null>(null);
	metricsManuallyEdited = $state(false);
	// Issue #443 — Step 5 Versand-Felder
	sendEmail = $state(true);
	sendTelegram = $state(false);
	sendSms = $state(false);
	// Issue #1745 A (D1): vierter ALARM-Kanal des Ortsvergleichs (Premium-SMS,
	// Go-Pendant ComparePreset.SendPremiumSms). Default AUS — Kostenkanal.
	sendPremiumSms = $state(false);
	// Issue #1268: timeWindowStart/timeWindowEnd/forecastHours entfallen — die
	// Felder sind aus dem Editor entfernt; der Dispatch nutzt fest 0–23 Uhr / 48 h.
	// Issue #1040: amtliche Warnungen ein/aus (Default true).
	officialAlertsEnabled = $state(true);
	// Issue #1041 Slice 2: Radar-Alarm ein/aus (Default AUS — opt-in).
	radarAlertEnabled = $state(false);
	// Issue #1107: Stundenverlauf-Sektion ein/aus (Default true).
	hourlyEnabled = $state(true);
	// Issue #1361/#1368: 3-Tages-Ausblick-Sektion ein/aus (Default true,
	// identisch zum Python-Default in report_config_resolver.py).
	outlookEnabled = $state(true);
	// Issue #1216 Slice 2b: Amtliche-Warnungen-Alarm-Trigger (Default AN —
	// sicherheitsrelevant, analog officialAlertsEnabled). Kanal-Opt-in nutzt die
	// bestehenden Runen sendTelegram/sendSms (Versand-Tab), keine neue Kanal-Rune.
	officialAlertTriggersEnabled = $state(true);
	// Issue #1258 S2: Persistenz-Verdrahtung folgt in S4 (toPresetPayload/Hydration).
	// Default false = F1-Neuanlage-Default (analog Trip official_warnings.enabled).
	officialWarningsEnabled = $state(false);
	// Issue #1170 — Alarm-Konfiguration (Epic #1095 Scheibe 3/3), Trip-identische Keys.
	metricAlertLevels = $state<Record<string, string>>({});
	// Issue #1461 S3b-2b — Kanal-Schwelle (analog metricAlertLevels): je Kanal
	// (telegram/sms/email) die Dringlichkeits-Schwelle, fehlende Keys = Startwert
	// "gering" (Aufloesung ueber resolveAlertChannelThresholds, AlarmeTab.svelte).
	channelThresholds = $state<Record<string, string>>({});
	// Issue #1260 S5 — Telegram-Kurzstil fuer amtliche Compare-Warnungen
	// (display_config.telegram_style). Default "rich".
	telegramStyle = $state<'rich' | 'kurzform'>('rich');
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
	// Issue #1361/#1372 S1b — gemeinsames Tagesfenster mit dem Trip (Reiter
	// Wetter-Metriken). Default 4/19 identisch zum Renderer-Default
	// (day_window.py DAY_WINDOW_START_HOUR/_END_HOUR).
	dayWindowStartHour = $state(4);
	dayWindowEndHour = $state(19);
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
		const payload = buildNewComparePresetPayload({
			name: this.name,
			pickedIds: this.pickedIds,
			activityProfile: this.activityProfile,
			schedule: this.schedule,
			officialAlertsEnabled: this.officialAlertsEnabled, // Issue #1040
			radarAlertEnabled: this.radarAlertEnabled, // Issue #1041 Slice 2
			hourlyEnabled: this.hourlyEnabled, // Issue #1107
			outlookEnabled: this.outlookEnabled, // Issue #1361/#1368
			officialAlertTriggersEnabled: this.officialAlertTriggersEnabled, // Issue #1216 Slice 2b
			sendTelegram: this.sendTelegram,
			sendSms: this.sendSms,
			sendPremiumSms: this.sendPremiumSms, // Issue #1745 A (AC-11)
			officialWarningsEnabled: this.officialWarningsEnabled, // Issue #1258 S4
			morningEnabled: this.morningEnabled, // Issue #1232 Scheibe 2b
			morningTime: this.morningTime,
			eveningEnabled: this.eveningEnabled,
			eveningTime: this.eveningTime,
			endDate: this.endDate,
			// Issue #1361/#1372 S1b: Tagesfenster — Anlegen folgt dem Trip-Muster
			// (#622), das Feld gehört von Anfang an zur Bedienfläche.
			dayWindowStartHour: this.dayWindowStartHour,
			dayWindowEndHour: this.dayWindowEndHour,
			alertCooldownMinutes: this.alertCooldownMinutes, // Issue #1170
			alertQuietFrom: this.alertQuietFrom,
			alertQuietTo: this.alertQuietTo,
			corridors: this.corridors, // Issue #1231 Slice 4
			region: this.region,
			idealRanges: this.idealRanges,
			activeMetricKeys: this.activeMetricKeys,
			// Issue #1703 Scheibe 8: Kanal-Overrides der Uebersichtstabelle — der
			// Anlege-Editor mountet denselben WeatherMetricsTab, ohne diese Zeile
			// bliebe die Bedienflaeche dort eine Attrappe. Kopie, damit der
			// gesendete Stand nicht spaeter noch mitmutiert.
			channelActiveMetricKeys: { ...this.channelActiveMetricKeys },
			hourlyMetricKeys: this.hourlyMetricKeys,
			outlookMetricKeys: this.outlookMetricKeys, // Issue #1361/#1368
			metricAlertLevels: this.metricAlertLevels, // Issue #1170
			channelThresholds: this.channelThresholds, // Issue #1461 S3b-2b
			telegramStyle: this.telegramStyle // Issue #1260 S5
		});
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
			// Issue #1366 F002: `CompareEditorEdits.activeMetricKeys` erwartet weiterhin
			// `string[] | undefined` (unveraendert, Edit-Pfad nicht betroffen) --
			// `null` ("nie eingestellt") wird hier zu `undefined` ("nicht editiert,
			// Round-Trip"), NICHT zu `[]` (das waere "bewusst leer").
			activeMetricKeys: this.activeMetricKeys ?? undefined,
			hourlyMetricKeys: this.hourlyMetricKeys, // Issue #1106
			officialAlertsEnabled: this.officialAlertsEnabled, // Issue #1040
			radarAlertEnabled: this.radarAlertEnabled, // Issue #1041 Slice 2
			hourlyEnabled: this.hourlyEnabled, // Issue #1107
			outlookMetricKeys: this.outlookMetricKeys, // Issue #1361/#1368
			outlookEnabled: this.outlookEnabled,
			metricAlertLevels: this.metricAlertLevels, // Issue #1170
			channelThresholds: this.channelThresholds, // Issue #1461 S3b-2b
			alertCooldownMinutes: this.alertCooldownMinutes,
			alertQuietFrom: this.alertQuietFrom,
			alertQuietTo: this.alertQuietTo,
			corridors: this.corridors, // Issue #1231 Slice 4
			telegramStyle: this.telegramStyle, // Issue #1260 S5
			dayWindowStartHour: this.dayWindowStartHour, // Issue #1361/#1372 S1b
			dayWindowEndHour: this.dayWindowEndHour
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
