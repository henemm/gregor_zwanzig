// Issue #1258 Scheibe S2 — geteilter Alarme-Organism (ungewired).
// Konsolidierte PUT-Payload fuer die Alarm-Zustellungsfelder (amtliche
// Warnungen-Inhalt, amtliche-Warnungen-Trigger scharf via official_warnings,
// Cooldown, Stille Stunden) — EIN Objekt fuer den einen $effect in
// AlarmeTab.svelte (AC-12), analog versand-tab/alertDeliveryPayload.ts:34-42.
//
// official_warnings sendet bewusst NUR "enabled", KEIN "sources" — der
// Server-RMW-Handler behaelt ein vorhandenes sources[] sonst nicht (S1-F002,
// siehe docs/specs/modules/issue_1258_alarme_tab_official_warnings.md
// Changelog).
//
// Adversary Fix-Loop 1, F002: officialAlertsEnabled/officialWarningsEnabled
// waren optional mit stillem Default (enabled:false) bei fehlendem Wert —
// dieselbe Fehlerklasse wie S1-F002 fuer kuenftige Aufrufer. Beide Felder
// sind jetzt PFLICHT (kein stiller Default mehr moeglich); official_warnings
// wird IMMER mit explizitem enabled gesendet — der Aufrufer muss den Wert
// kennen, kein stilles false. Laufzeit-Guard faengt Aufrufer ab, die trotz
// strip-types (keine Typpruefung zur Laufzeit) einen Nicht-boolean uebergeben.
//
// F003-Nachzug (S2-Adversary, #1199, eingeloest S3): der Guard existierte
// bisher NUR fuer officialWarningsEnabled — officialAlertsEnabled konnte
// unbemerkt undefined/Nicht-boolean sein und wurde klaglos in die
// PUT-Payload durchgereicht. Guard jetzt symmetrisch fuer beide Felder.
//
// Adversary Fix-Loop 1, F001 (S3): AlarmeScheduleTab.svelte hatte zwei
// EIGENE saveController.schedule()-Aufrufer (Kanal-Toggle, Metrik-Level-
// Aenderung) neben dem EINEN $effect in AlarmeTab.svelte — alle drei teilen
// sich denselben Ein-Slot-Debounce (saveStatusStore.svelte.ts:67-72), zwei
// Aenderungen aus verschiedenen Quellen im 700ms-Fenster verwerfen die
// erste Payload still. Fix: Kanaele (`channels`) und Metrik-Level
// (`metricLevels`) sind jetzt Teil DIESER EINEN konsolidierten Payload —
// AlarmeScheduleTab.svelte hat KEINE eigene Schreibquelle mehr (s.
// AlarmeTab.svelte route-$effect).
//
// `channels` ist PFLICHT (kein stiller Default, Laufzeit-Guard analog
// officialAlertsEnabled/officialWarningsEnabled: alle drei Kanal-Werte
// muessen echte booleans sein). `metricLevels` ist optional — NUR wenn
// gesetzt, wird `display_config` als Read-Modify-Write-Spread ueber
// `currentDisplayConfig` geschrieben (BUG-DATALOSS-Klasse: andere
// display_config-Keys wie ideal_ranges/channel_layouts/region/top_n
// duerfen nicht verloren gehen, s. CLAUDE.md "Daten-Schema-Reworks").
//
// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md (AC-12, AC-26)

export interface AlarmeChannelsState {
	email: boolean;
	telegram: boolean;
	sms: boolean;
}

export interface AlarmeDeliveryState {
	officialAlertsEnabled: boolean;
	officialWarningsEnabled: boolean;
	cooldownMinutes?: number;
	quietFrom?: string;
	quietTo?: string;
	channels: AlarmeChannelsState;
	metricLevels?: Record<string, string> | undefined;
}

export function buildAlarmeDeliveryPayload(
	state: AlarmeDeliveryState,
	currentDisplayConfig?: Record<string, unknown>
): object {
	if (typeof state.officialAlertsEnabled !== 'boolean') {
		throw new Error(
			'buildAlarmeDeliveryPayload: officialAlertsEnabled fehlt oder ist kein boolean — ' +
				'official_alerts_enabled wird IMMER mit explizitem Wert gesendet, kein stiller Default.'
		);
	}
	if (typeof state.officialWarningsEnabled !== 'boolean') {
		throw new Error(
			'buildAlarmeDeliveryPayload: officialWarningsEnabled fehlt oder ist kein boolean — ' +
				'official_warnings wird IMMER mit explizitem enabled gesendet, kein stilles false.'
		);
	}
	if (
		typeof state.channels?.email !== 'boolean' ||
		typeof state.channels?.telegram !== 'boolean' ||
		typeof state.channels?.sms !== 'boolean'
	) {
		throw new Error(
			'buildAlarmeDeliveryPayload: channels fehlt oder enthaelt einen Nicht-boolean-Wert — ' +
				'alert_channels wird IMMER mit allen drei expliziten Werten gesendet, kein stiller Default (F001).'
		);
	}
	const payload: Record<string, unknown> = {
		official_alerts_enabled: state.officialAlertsEnabled,
		official_warnings: { enabled: state.officialWarningsEnabled },
		alert_cooldown_minutes: state.cooldownMinutes ?? null,
		alert_quiet_from: state.quietFrom || null,
		alert_quiet_to: state.quietTo || null,
		alert_channels: {
			email: state.channels.email,
			telegram: state.channels.telegram,
			sms: state.channels.sms
		}
	};
	if (state.metricLevels !== undefined) {
		payload.display_config = {
			...(currentDisplayConfig ?? {}),
			metric_alert_levels: state.metricLevels
		};
	}
	return payload;
}
