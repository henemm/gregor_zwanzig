// Issue #1232 Scheibe 1 — Adversary-Fund F002: EIN konsolidierter PUT-Payload
// für die gesamte Alert-Zustellung (amtliche Warnungen + Trigger + Cooldown +
// Stille Stunden), statt drei unabhängiger Save-Aufrufe.
//
// Grund: `saveStatusStore.svelte.ts` kennt nur EINEN Debounce-Slot
// (`schedule()` überschreibt `_pendingFn` vollständig). Lösen mehrere dieser
// Felder unabhängig voneinander je einen eigenen `schedule()`-Aufruf aus,
// verwirft der zweite Aufruf innerhalb des 700ms-Fensters die erste Payload
// unwiderruflich — sie wird nie gesendet (Datenverlust).
//
// Fix: VersandTab.svelte ruft `buildAlertDeliveryPayload()` mit dem
// VOLLSTÄNDIGEN aktuellen Zustand aller 5 Felder auf und plant GENAU EINEN
// gemeinsamen Save — jede Änderung ersetzt den pending Save durch einen
// neuen, der wieder alle 5 aktuellen Werte enthält (kein Feld geht verloren).
//
// Spec: docs/specs/modules/versand_tab_route.md (AC-6)

export interface AlertDeliveryState {
	officialAlertsEnabled: boolean;
	officialAlertTriggersEnabled: boolean;
	cooldownMinutes?: number;
	quietFrom?: string;
	quietTo?: string;
}

export interface AlertDeliveryPayload {
	official_alerts_enabled: boolean;
	official_alert_triggers_enabled: boolean;
	alert_cooldown_minutes: number | null;
	alert_quiet_from: string | null;
	alert_quiet_to: string | null;
}

export function buildAlertDeliveryPayload(state: AlertDeliveryState): AlertDeliveryPayload {
	return {
		official_alerts_enabled: state.officialAlertsEnabled,
		official_alert_triggers_enabled: state.officialAlertTriggersEnabled,
		alert_cooldown_minutes: state.cooldownMinutes ?? null,
		alert_quiet_from: state.quietFrom || null,
		alert_quiet_to: state.quietTo || null
	};
}
