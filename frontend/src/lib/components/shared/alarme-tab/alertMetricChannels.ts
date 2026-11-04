// Issue #1895 S3b1 — Kanäle je Wettergröße (Spec alert_metric_channels.md, AC-41..AC-51).
// Reine Regeln für AlertMetricChannelsBlock.svelte und beide Speicherwege. Der Server ersetzt
// je Speicherschlüssel den ganzen Eintrag ⇒ immer vier Flags oder `null`, nur der Diff wird gesendet.
import type { ConnectionProfile } from '../versand-tab/channelConnectionStatus.ts';
import type { AlertChannelThresholdState, ChannelThreshold } from './alertChannelState.ts';

export const KANAELE = ['email', 'telegram', 'sms', 'premium_sms'] as const;
export type Kanal = (typeof KANAELE)[number];
export type KanalEintrag = Record<Kanal, boolean> | null;
export type KanalMap = Record<string, KanalEintrag>;
export interface KanalSchluessel {
	keys: Record<string, string[]>;
	accepted: string[];
}
/** Eigennamen (wie AlertChannelPicker). */
export const KANAL_NAMEN: Record<Kanal, string> = {
	email: 'Email',
	telegram: 'Telegram',
	sms: 'SMS',
	premium_sms: 'Premium-SMS (Garmin inReach)'
};

// Nutzerunabhängige Antwort ⇒ Modul-Cache mandantensicher; ein Fehler wird nie gecacht (AC-50).
let cache: Promise<KanalSchluessel | null> | null = null;
export function ladeKanalSchluessel(fetchFn: typeof fetch = fetch): Promise<KanalSchluessel | null> {
	if (cache) return cache;
	const laufend = fetchFn('/api/alert-metric-channel-keys', { credentials: 'same-origin' })
		.then((r) => (r.ok ? (r.json() as Promise<KanalSchluessel>) : null))
		.catch(() => null)
		.then((a) => {
			if (!a && cache === laufend) cache = null;
			return a;
		});
	cache = laufend;
	return laufend;
}
export function _resetKanalSchluesselCache(): void {
	cache = null;
}

/** Eine Zeile je Speicherschlüssel: Vereinigung keys[m] der aktiven Zeilen, nur accepted (F4). */
export function kanalZeilen(aktiveMetriken: string[], keys: Record<string, string[]>, accepted: string[]): string[] {
	const erlaubt = new Set(accepted);
	const zeilen = new Set(aktiveMetriken.flatMap((m) => keys[m] ?? []).filter((k) => erlaubt.has(k)));
	return [...zeilen].sort();
}

/** Immer alle vier Flags; kein Kanal gewählt ⇒ `null` (erbt, E5). */
export function normalisiereEintrag(flags: Partial<Record<Kanal, boolean>> | null | undefined): KanalEintrag {
	const e = Object.fromEntries(KANAELE.map((k) => [k, flags?.[k] === true])) as Record<Kanal, boolean>;
	return KANAELE.some((k) => e[k]) ? e : null;
}

const gleich = (a: KanalEintrag | undefined, b: KanalEintrag | undefined): boolean =>
	KANAELE.every((k) => (a?.[k] ?? false) === (b?.[k] ?? false)) && !a === !b;

/** Nur Schlüssel aus `aktuell`, die vom hydrierten Stand abweichen; fehlend = null (erbt). */
export function baueDiff(hydriert: KanalMap | null | undefined, aktuell: KanalMap | null | undefined): KanalMap {
	const diff: KanalMap = {};
	for (const [k, e] of Object.entries(aktuell ?? {})) {
		if (!gleich(hydriert?.[k] ?? null, e ?? null)) diff[k] = e ? normalisiereEintrag(e) : null;
	}
	return diff;
}

/** Gewählte Kanäle, die im Abo-Satz aus sind (AC-51). */
export function hinweise(eintrag: KanalEintrag | undefined, aboSatz: Partial<Record<Kanal, boolean>>): Kanal[] {
	return eintrag ? KANAELE.filter((k) => eintrag[k] && !aboSatz[k]) : [];
}

/** S3b2 (AC-63..AC-67): gewählte Kanäle ohne Empfänger. Telegram/SMS deckungsgleich mit
 * channelConnectionStatus („sendebereit"); E-Mail nie; Profil unbekannt ⇒ nichts raten. */
export function kanaeleOhneEmpfaenger(eintrag: KanalEintrag | undefined, profil: ConnectionProfile | null | undefined): Kanal[] {
	if (!eintrag || !profil) return [];
	const p = profil;
	const rueck = p.premium_sms_reply_state ?? 'none'; // fehlend = keine Rückadresse
	const ohne: Record<Kanal, boolean> = {
		email: false,
		telegram: !p.telegram_chat_id,
		sms: !p.sms_to || p.sms_allowed === false || !p.sms_verified,
		premium_sms: rueck === 'none' || rueck === 'stale'
	};
	return KANAELE.filter((k) => eintrag[k] && ohne[k]);
}

/** S3b2 (AC-69/AC-70): gewählte Kanäle mit Schwelle MODERATE/HIGH, stufenunabhängig. */
export function kanaeleMitSchwelle(
	eintrag: KanalEintrag | undefined,
	schwellen: Partial<AlertChannelThresholdState> | null | undefined
): Array<{ kanal: Kanal; schwelle: ChannelThreshold }> {
	if (!eintrag) return [];
	return KANAELE.flatMap((kanal) => {
		const schwelle = schwellen?.[kanal];
		return eintrag[kanal] && (schwelle === 'MODERATE' || schwelle === 'HIGH') ? [{ kanal, schwelle }] : [];
	});
}
