// Issue #2276 Scheibe S6f (Epic #2345) — Hydrations-Haelfte der aufgeloesten
// Compare-Hub-Klebeschicht (Issue #1256 Scheibe 6, AC-16, AC-33, AC-34, Edge
// Case Z.1020; Issue #1258 Scheibe 5, AC-19/AC-29). Alles, was einen
// Hub-Zustand aus einem `ComparePreset` befuellt: die 6 Idealwerte-Felder
// fuer `CorridorEditor.svelte` im vergleich-Kontext sowie die Erst-Oeffnungs-
// Hydration fuer den Hub-Alarme-Tab.
//
// Spec: docs/specs/modules/rework_2276_s6f_bridge_umzug.md — AC-1
//
// Funktionskoerper/JSDoc byte-identisch aus der aufgeloesten Bridge
// uebernommen (nur die zwei Umbenennungen HubWizardFields->HubFields,
// hydrateWizardStateFromPreset->hydrateHubFieldsFromPreset) — reiner Umzug,
// kein Verhalten geaendert.
//
// Kein Browser-/SvelteKit-Import — lauffaehig unter node --experimental-strip-types.
//
// gz-eigenstaendig: Compare-Hub-Orchestrierung (ComparePreset-Hydration fuer CompareTabs.svelte), reiner Umzug der aufgeloesten Compare-Klebeschicht; kein Trip-Pendant (Spec rework_2276_s6f_bridge_umzug.md)

import type { ActivityProfile, ComparePreset, Corridor } from '../../types.ts';
import type { IdealRange } from '../shared/corridor-editor/corridorEditorState.ts';
import { rehydrateActiveMetrics } from './compareEditorLoad.ts';
// Issue #1373 (S2 Scheibe B, AC-12): dieselbe Lesenormalisierung wie im
// Lade-Pfad — Alt- UND Neuformat der gespeicherten Metrik-Auswahl.
import {
	registeredCompareMetricCatalog,
	type CompareSelectionEntry
} from '../shared/weather-metrics-tab/compareMetricSelection.ts';
import { hydrateWeatherMetricsFromPreset } from '../shared/weather-metrics-tab/weatherMetricsCompareSave.ts';
import type { AlarmHydrationTarget } from '../shared/alarmeVergleichSpeicherung.ts';

/** Plain-Objekt mit GENAU den 6 Feldern, die CorridorEditor.svelte im
 * vergleich-Kontext aus dem Wizard-State liest. Die Bridge-Komponente
 * (CompareTabs.svelte) uebertraegt dies auf eine echte CompareWizardState-
 * Instanz und ruft setContext(...). */
export interface HubFields {
	isEditMode: true;
	corridors: Corridor[];
	activityProfile: ActivityProfile | null;
	idealRanges: Record<string, IdealRange>;
	// #1191-Semantik (rehydrateActiveMetrics): null = "Feld fehlte im Preset"
	// (Signal fuer Profil-Default-Pfad), NIEMALS still als [] getarnt.
	activeMetricKeys: string[] | null;
	metricAlertLevels: Record<string, string>;
}

/**
 * Teil-Hydration der 6 CorridorEditor-Felder aus einem ComparePreset.
 * isEditMode ist immer true — der Hub mountet den Organism wie den Editor.
 */
export function hydrateHubFieldsFromPreset(
	preset: ComparePreset,
	// Issue #1373 (S2 Scheibe B, Fix-Runde 1): geladene Katalogantwort — ohne sie
	// bliebe eine im Format Größe + Auswertung gespeicherte Auswahl unaufgelöst,
	// und das ✕-Entfernen einer Metrik-Zeile im Idealwerte-Reiter träfe sie nicht
	// mehr (`activeSet.delete(key)` in buildCompareCorridorSavePayload).
	catalog: CompareSelectionEntry[] = registeredCompareMetricCatalog()
): HubFields {
	const displayConfig = (preset.display_config as Record<string, unknown>) ?? {};
	const rehydrated = rehydrateActiveMetrics(displayConfig.active_metrics, catalog);
	return {
		isEditMode: true,
		corridors: preset.corridors ?? [],
		activityProfile: (preset.profil as ActivityProfile) ?? null,
		idealRanges: (displayConfig.ideal_ranges as Record<string, IdealRange>) ?? {},
		activeMetricKeys: rehydrated ? rehydrated.activeMetricKeys : null,
		metricAlertLevels: (displayConfig.metric_alert_levels as Record<string, string>) ?? {}
	};
}

/**
 * Issue #1258 Scheibe 5 (AC-19, AC-29): Erst-Oeffnungs-Hydration fuer den
 * Hub-Alarme-Tab — mutiert `state` DIREKT (analog dem lazy `alarme`-Effekt in
 * CompareTabs.svelte, H3), OHNE eine vorherige `hydrateWizardStateFromPreset`-
 * oder `hydrateVersandFieldsFromPreset`-Hydration vorauszusetzen. Der Alarme-
 * Tab kann als ERSTER Tab geoeffnet werden (Deep-Link `?tab=alarme`) — deshalb
 * hydriert diese Funktion ALLE alarm-relevanten Felder eigenstaendig, inkl.
 * `corridors` (H4: der Idealwerte-Tab braucht bereits geladene Korridore,
 * falls er NACH Alarme als zweiter Tab geoeffnet wird).
 *
 * Fallbacks 1:1 analog `AlarmeTab.svelte:80-90` bzw. Trip-Pipeline
 * (trip_alert.py): `officialWarningsEnabled` faellt auf
 * `official_alert_triggers_enabled !== false` zurueck, wenn `official_warnings`
 * fehlt (Legacy-Kompatibilitaet).
 */
export function hydrateAlarmFieldsFromPreset(
	state: AlarmHydrationTarget,
	preset: ComparePreset,
	// Issue #1373 (S2 Scheibe B, Fix-Runde 1): geladene Katalogantwort, nötig zum
	// Auflösen des Speicherformats der Metrik-Auswahl (Größe + Auswertung) in
	// der Zeile unten. Default = bereits registrierter Katalog.
	catalog: CompareSelectionEntry[] = registeredCompareMetricCatalog()
): void {
	const displayConfig = (preset.display_config as Record<string, unknown>) ?? {};
	state.officialAlertsEnabled = preset.official_alerts_enabled ?? true;
	state.officialWarningsEnabled =
		preset.official_warnings?.enabled ?? preset.official_alert_triggers_enabled !== false;
	state.radarAlertEnabled = preset.radar_alert_enabled ?? false;
	state.metricAlertLevels = (displayConfig.metric_alert_levels as Record<string, string>) ?? {};
	// Issue #1461 S3b-2b (Speicher-Bugfix): sendTelegram/sendSms UND die
	// Kanal-Schwelle mit-hydrieren, damit eine Aenderung im Alarme-Reiter als
	// Snapshot-Differenz erkennbar wird (s. AlarmHydrationTarget-Kommentar).
	state.sendTelegram = preset.send_telegram ?? false;
	state.sendSms = preset.send_sms ?? false;
	// Issue #1745 A (D1): fehlt das Feld im Preset, ist der Kostenkanal AUS.
	state.sendPremiumSms = preset.send_premium_sms ?? false;
	state.channelThresholds = (preset.alert_channel_thresholds as Record<string, string>) ?? {};
	state.alertCooldownMinutes = preset.alert_cooldown_minutes;
	state.alertQuietFrom = preset.alert_quiet_from;
	state.alertQuietTo = preset.alert_quiet_to;
	state.corridors = preset.corridors ?? [];
	// Issue #1320: Alarme kann als ERSTER Tab geoeffnet werden — dann hat
	// activeMetricKeys noch keinen Hydrations-Durchlauf vom Wetter-Metriken-/
	// Idealwerte-Tab gesehen. Ohne diese Zeile zeigt die Empfindlichkeits-
	// Tabelle faelschlich "keine Metriken", obwohl das Preset aktive Metriken hat.
	state.activeMetricKeys = hydrateWeatherMetricsFromPreset(preset, catalog);
	// Issue #1260: Kurzstil-Toggle aus display_config.telegram_style hydrieren,
	// Default "rich" (analog CompareEditor). Ohne diese Zeile bliebe der Toggle
	// im Hub-Alarme-Tab dauerhaft auf dem Klasse-Default stehen und ein
	// gespeicherter "kurzform"-Wert waere unsichtbar.
	state.telegramStyle = (displayConfig.telegram_style as 'rich' | 'kurzform') ?? 'rich';
}
