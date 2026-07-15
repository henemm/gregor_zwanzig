// Issue #1258 Scheibe S2 — geteilter Alarme-Organism (ungewired).
// Pure-Function-Kern fuer AlertChannelPicker.svelte: Design-Default
// (Telegram/SMS an, E-Mail aus, NUR bei Neuanlage), Anzeige-Reihenfolge und
// Warnhinweis bei null aktiven Kanaelen (AC-11).
//
// Design: claude-code-handoff/current/jsx/corridor-editor.jsx:469-489
// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md (AC-11)

export interface AlertChannelState {
	telegram: boolean;
	sms: boolean;
	email: boolean;
}

// Anzeige-Reihenfolge lt. Design (corridor-editor.jsx:487-489).
export const ALERT_CHANNEL_ORDER = ['telegram', 'sms', 'email'] as const;

// Design-Default (corridor-editor.jsx:470) — gilt NUR ohne uebergebenen
// Bestands-State (Neuanlage, AC-11). Mit Bestand wird der Bestand
// uebernommen, fehlende Keys werden false (kein stiller Kanal-Wechsel).
const NEW_ENTITY_DEFAULT: AlertChannelState = { telegram: true, sms: true, email: false };

// Adversary Fix-Loop 1, F001: ein leeres Objekt `{}` (oder eines ohne einen
// einzigen explizit gesetzten boolean-Wert, z.B. `{telegram: undefined}`)
// wurde bisher wie ein Bestand mit "alles aus" behandelt — Foot-Gun fuer die
// S3-Bestand-Rekonstruktion, die versehentlich ein leeres Objekt statt
// undefined uebergeben koennte. Fix: nur ein Objekt mit MINDESTENS einem
// explizit gesetzten boolean-Kanal gilt als Bestand; sonst greift der
// Neuanlage-Default. Aufrufer-Vertrag: Bestand nur mit mindestens einem
// explizit gesetzten Kanal uebergeben — sonst greift der Neuanlage-Default.
function hasAnyExplicitChannelValue(existing: Partial<AlertChannelState>): boolean {
	return (
		typeof existing.telegram === 'boolean' ||
		typeof existing.sms === 'boolean' ||
		typeof existing.email === 'boolean'
	);
}

export function resolveAlertChannels(
	existing?: Partial<AlertChannelState> | null
): AlertChannelState {
	if (!existing || !hasAnyExplicitChannelValue(existing)) return { ...NEW_ENTITY_DEFAULT };
	return {
		telegram: existing.telegram ?? false,
		sms: existing.sms ?? false,
		email: existing.email ?? false
	};
}

export const NO_CHANNEL_WARNING = 'kein Kanal — Alerts gehen nirgends hin';

export function channelWarningNeeded(state: AlertChannelState): boolean {
	return !state.telegram && !state.sms && !state.email;
}
