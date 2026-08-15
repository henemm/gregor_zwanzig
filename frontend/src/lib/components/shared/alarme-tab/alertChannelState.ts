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
	// Issue #1745 A — vierter Alarm-Kanal (Garmin inReach), im Backend seit
	// #1701 vollwertig (_effective_alert_channels, compare_alert_channels.py).
	premium_sms: boolean;
}

// Anzeige-Reihenfolge lt. Design (corridor-editor.jsx:487-489).
// Issue #1745 A (D5): premium_sms steht DIREKT unter sms und VOR email —
// identisch zur Anordnung im Versand-Reiter (ein SMS-Block).
export const ALERT_CHANNEL_ORDER = ['telegram', 'sms', 'premium_sms', 'email'] as const;
export type ChannelKind = (typeof ALERT_CHANNEL_ORDER)[number];

// Design-Default (corridor-editor.jsx:470) — gilt NUR ohne uebergebenen
// Bestands-State (Neuanlage, AC-11). Mit Bestand wird der Bestand
// uebernommen, fehlende Keys werden false (kein stiller Kanal-Wechsel).
// Issue #1745 A (D1): premium_sms ist beim Anlegen AUS — Kostenkanal
// (Satelliten-SMS), wird bewusst angehakt, nie automatisch.
const NEW_ENTITY_DEFAULT: AlertChannelState = {
	telegram: true,
	sms: true,
	email: false,
	premium_sms: false
};

// Adversary Fix-Loop 1, F001: ein leeres Objekt `{}` (oder eines ohne einen
// einzigen explizit gesetzten boolean-Wert, z.B. `{telegram: undefined}`)
// wurde bisher wie ein Bestand mit "alles aus" behandelt — Foot-Gun fuer die
// S3-Bestand-Rekonstruktion, die versehentlich ein leeres Objekt statt
// undefined uebergeben koennte. Fix: nur ein Objekt mit MINDESTENS einem
// explizit gesetzten boolean-Kanal gilt als Bestand; sonst greift der
// Neuanlage-Default. Aufrufer-Vertrag: Bestand nur mit mindestens einem
// explizit gesetzten Kanal uebergeben — sonst greift der Neuanlage-Default.
// Issue #1745 A (Landmine 2): premium_sms zaehlt hier MIT — ein Bestand, der
// nur beim vierten Kanal einen expliziten Wert traegt, galt sonst als "kein
// Bestand" und wuerde vom Neuanlage-Default ueberschrieben.
function hasAnyExplicitChannelValue(existing: Partial<AlertChannelState>): boolean {
	return (
		typeof existing.telegram === 'boolean' ||
		typeof existing.sms === 'boolean' ||
		typeof existing.email === 'boolean' ||
		typeof existing.premium_sms === 'boolean'
	);
}

export function resolveAlertChannels(
	existing?: Partial<AlertChannelState> | null
): AlertChannelState {
	if (!existing || !hasAnyExplicitChannelValue(existing)) return { ...NEW_ENTITY_DEFAULT };
	return {
		telegram: existing.telegram ?? false,
		sms: existing.sms ?? false,
		email: existing.email ?? false,
		premium_sms: existing.premium_sms ?? false
	};
}

export const NO_CHANNEL_WARNING = 'kein Kanal — Alerts gehen nirgends hin';

// Issue #1745 A (Landmine 4): premium_sms zaehlt hier MIT — ein Trip/Preset mit
// AUSSCHLIESSLICH Premium-SMS zeigte sonst faelschlich "kein Kanal", waehrend
// das Backend den Alarm sehr wohl zustellt (_effective_alert_channels, #1701).
export function channelWarningNeeded(state: AlertChannelState): boolean {
	return !state.telegram && !state.sms && !state.email && !state.premium_sms;
}

// ─────────────────────────────────────────────────────────────────────────
// Issue #1461 S3b-2a — Kanal-Schwelle (ab welcher Dringlichkeit ein Kanal
// eine Alarm-Meldung erreicht). Geschwister-Zustand zu AlertChannelState,
// NICHT darin (Backend-Geschwisterfeld trip.alert_channel_thresholds).
// Diese Scheibe bedient nur den Trip-Speicherweg (`route`).
// ─────────────────────────────────────────────────────────────────────────

export type ChannelThreshold = 'LOW' | 'MODERATE' | 'HIGH';

export interface AlertChannelThresholdState {
	telegram: ChannelThreshold;
	sms: ChannelThreshold;
	email: ChannelThreshold;
	// Issue #1745 A: der vierte Kanal hat dieselbe Dringlichkeits-Schwelle wie
	// die drei Bestandskanaele (ADR-0046 gilt fuer jeden Kanal).
	premium_sms: ChannelThreshold;
}

export const CHANNEL_THRESHOLD_LEVELS: ChannelThreshold[] = ['LOW', 'MODERATE', 'HIGH'];

export const CHANNEL_THRESHOLD_LABELS: Record<ChannelThreshold, string> = {
	LOW: 'gering',
	MODERATE: 'mittel',
	HIGH: 'hoch'
};

// PO-Entscheidung 2026-08-05: Startwert je Kanal ist 'LOW' — es wird
// nirgends stiller, bis der Nutzer selbst eine Schwelle hochsetzt (rote
// Linie #638).
const DEFAULT_CHANNEL_THRESHOLD: ChannelThreshold = 'LOW';

function coerceThreshold(value: unknown): ChannelThreshold {
	return value === 'MODERATE' || value === 'HIGH' ? value : DEFAULT_CHANNEL_THRESHOLD;
}

export function resolveAlertChannelThresholds(
	existing?: Partial<Record<ChannelKind, string | null>> | null
): AlertChannelThresholdState {
	return {
		telegram: coerceThreshold(existing?.telegram),
		sms: coerceThreshold(existing?.sms),
		email: coerceThreshold(existing?.email),
		premium_sms: coerceThreshold(existing?.premium_sms)
	};
}

// Adversary F003: die eigentliche Aenderungs-Logik hinter einem Klick auf
// eine Stufe (AlertChannelPicker.svelte -> AlarmeTab.svelte
// handleThresholdChange) liegt HIER als reine, direkt testbare Funktion,
// statt nur inline im Svelte-Handler zu stehen — node:test kann Svelte-
// Komponenten nicht mounten (ADR-0020), eine reine Funktion aber echt mit
// Ein-/Ausgabewerten pruefen ("kann diese Einstellung aendern", AC-10).
export function applyThresholdChange(
	state: AlertChannelThresholdState,
	kind: ChannelKind,
	level: ChannelThreshold
): AlertChannelThresholdState {
	return { ...state, [kind]: level };
}
