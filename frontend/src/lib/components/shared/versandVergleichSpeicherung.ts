// Hydrations-Helfer des Versand-Abschnitts im Ortsvergleich (Issue #1256 S7,
// #2276 S5). Gespeichert wird seit #2794/#3020 über den Zustellungs-Speicherer
// (`zustellung-tab/zustellungSpeicherung.ts`); der frühere Versand-Speicherweg
// samt Snapshot-, Nutzlast- und Rollback-Funktionen ist mit #3389 entfernt.
//
// Kein Browser-/SvelteKit-Import — lauffähig unter node --experimental-strip-types.

import type { ComparePreset } from '../../types.ts';

/** Die persistenzrelevanten Versand-Felder (OHNE sendEmail — `ComparePreset`
 * kennt kein `send_email`-Feld, s. `hydrateVersandFieldsFromPreset`).
 *
 * `alertCooldownMinutes`/`alertQuietFrom`/`alertQuietTo` sind Legacy-Restfelder
 * (Besitzer: Alarme-Teil der Zustellung); sie bleiben optional im Typ, weil
 * Hydration und Wertprops sie weiter führen. */
interface VersandSnapshot {
	sendTelegram: boolean;
	sendSms: boolean;
	// Issue #2293 Scheibe S2 (#2448): eigener Premium-SMS-Briefing-Schalter,
	// unabhängig vom Alarm-Kanal (alert_channels.premium_sms).
	sendPremiumSms?: boolean;
	morningEnabled: boolean;
	morningTime: string;
	eveningEnabled: boolean;
	eveningTime: string;
	endDate: string | null;
	alertCooldownMinutes?: number;
	alertQuietFrom?: string;
	alertQuietTo?: string;
}

/**
 * Issue #1256 Scheibe 7 (AC-35/36): Hydration der Versand-Felder, die der
 * eingebettete Versand-Abschnitt im Hub aus `wizardState.*` liest. Defaults
 * identisch zur Edit-Routen-Hydration. `sendEmail` ist IMMER true —
 * ComparePreset hat kein `send_email`-Feld (vorbestehende Luecke, Known
 * Limitation der S7-Freigabe).
 */
export function hydrateVersandFieldsFromPreset(
	preset: ComparePreset
): VersandSnapshot & { sendEmail: true } {
	return {
		sendEmail: true,
		sendTelegram: preset.send_telegram ?? false,
		sendSms: preset.send_sms ?? false,
		sendPremiumSms: preset.send_premium_sms ?? false,
		morningEnabled: preset.morning_enabled ?? true,
		morningTime: (preset.morning_time ?? '06:00').slice(0, 5),
		eveningEnabled: preset.evening_enabled ?? false,
		eveningTime: (preset.evening_time ?? '18:00').slice(0, 5),
		endDate: preset.end_date ?? null,
		alertCooldownMinutes: preset.alert_cooldown_minutes ?? undefined,
		alertQuietFrom: preset.alert_quiet_from ?? undefined,
		alertQuietTo: preset.alert_quiet_to ?? undefined
	};
}
