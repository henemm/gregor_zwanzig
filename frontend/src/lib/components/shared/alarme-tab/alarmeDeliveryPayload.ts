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
// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md (AC-12)

export interface AlarmeDeliveryState {
	officialAlertsEnabled: boolean;
	officialWarningsEnabled: boolean;
	cooldownMinutes?: number;
	quietFrom?: string;
	quietTo?: string;
}

export function buildAlarmeDeliveryPayload(state: AlarmeDeliveryState): object {
	if (typeof state.officialWarningsEnabled !== 'boolean') {
		throw new Error(
			'buildAlarmeDeliveryPayload: officialWarningsEnabled fehlt oder ist kein boolean — ' +
				'official_warnings wird IMMER mit explizitem enabled gesendet, kein stilles false.'
		);
	}
	return {
		official_alerts_enabled: state.officialAlertsEnabled,
		official_warnings: { enabled: state.officialWarningsEnabled },
		alert_cooldown_minutes: state.cooldownMinutes ?? null,
		alert_quiet_from: state.quietFrom || null,
		alert_quiet_to: state.quietTo || null
	};
}
