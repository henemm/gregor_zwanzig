// Issue #2276 Scheibe S6c (Epic #2345) — EINE Stelle, die aus dem
// Compare-Wizard-Zustand das Prop-Bündel für den geteilten Alarme-Organismus
// (`shared/AlarmeTab.svelte`) baut. Alle DREI Vergleichs-Mounts (Hub
// `CompareTabs.svelte`, Anlege-Seite Desktop + Mobil `CompareNewEditor.svelte`)
// speisen dasselbe Bündel ein — bei drei Mounts × 13 Feldern wären
// Inline-Adapter dreifache Gelegenheit zur Drift (Spec, Design-Entscheidung 4).
//
// gz-eigenstaendig: Diese Uebersetzung vom Compare-Wizard-Zustand in Wertprops
// gehört nach compare/ und hat bewusst kein Trip-Pendant — läge sie in shared/,
// importierte der geteilte Bereich die Compare-Klebeschicht (genau das, was
// AC-4 von #2276 abbaut und alarme_tab_laedt_keine_compare_klebeschicht.test.ts
// bewacht), und der Trip-Mount braucht sie nicht, weil er seine Werte ohne
// Zwischenschicht direkt an AlarmeTab übergibt.
//
// 🔴 Aufrufform (prüfbar, kein Prosa-Wunsch): `{...alarmePropsAus(wiz)}` steht
// IM MARKUP-AUSDRUCK jedes Mounts, NIEMALS in einer Skript-Variablen. Ein einmal
// berechnetes, dort eingefrorenes Objekt bestünde SSR-Prüfstand und AST-Wächter
// anstandslos und fiele erst im Browser auf — die `$state`-Lesezugriffe würden
// dann außerhalb des reaktiven Renderns registriert.
//
// 🔴 Diskriminator-Regel des Organismus (deshalb hier KEIN `undefined`):
// `AlarmeTab` unterscheidet Vergleich und Tour an etwas, das dieses Bündel
// IMMER liefert und der Trip-Mount NIE übergibt. Für `officialWarningsEnabled`,
// `metricAlertLevels`, `sendTelegram`/`sendSms`/`sendPremiumSms`,
// `channelThresholds`, `radarAlertEnabled` und `activeMetricKeys` ist das der
// WERT — er darf deshalb nie `undefined` sein. Bei `cooldownMinutes`,
// `quietFrom` und `quietTo` ist `undefined` ein gültiger Wert („nicht
// gesetzt"), dort entscheidet die Anwesenheit des RÜCKRUFS.
//
// Kein Browser-/SvelteKit-Import — lauffähig unter node --experimental-strip-types.

import {
	applyThresholdChange,
	resolveAlertChannelThresholds,
	type AlertChannelThresholdState,
	type ChannelKind,
	type ChannelThreshold
} from '../shared/alarme-tab/alertChannelState.ts';

/** Strukturelle Sicht auf die Alarmfelder des Compare-Wizard-Zustands —
 *  absichtlich nicht `CompareWizardState` selbst, damit diese Funktion auch
 *  gegen einen hydrierten Plain-Zustand (Hub-Bridge) arbeitet. */
export interface AlarmeZustandsQuelle {
	officialAlertsEnabled?: boolean;
	officialWarningsEnabled?: boolean;
	radarAlertEnabled?: boolean;
	metricAlertLevels?: Record<string, string>;
	channelThresholds?: Record<string, string>;
	telegramStyle?: 'rich' | 'kurzform';
	alertCooldownMinutes?: number;
	alertQuietFrom?: string;
	alertQuietTo?: string;
	sendTelegram?: boolean;
	sendSms?: boolean;
	sendPremiumSms?: boolean;
	activeMetricKeys?: string[] | null;
}

/** Vollständige Kanal-Schwellen OHNE stillen Wertverlust: die Vorgabe „gering"
 *  füllt nur die Kanäle, für die noch nichts gespeichert ist — ein bereits
 *  gehaltener Wert überlebt unverändert (`resolveAlertChannelThresholds`
 *  allein würde jeden ihm unbekannten Wert auf „gering" zurückdrehen). */
function vollstaendigeSchwellen(bestand: Record<string, string>): AlertChannelThresholdState {
	return { ...resolveAlertChannelThresholds(bestand), ...bestand } as AlertChannelThresholdState;
}

/**
 * Das Prop-Bündel für `AlarmeTab context="vergleich"`: 13 Werte, 8
 * Gesten-Rückrufe, der Zonen-Bezug der Stillen Stunden (#1378 AC-4) und die
 * Rollback-Senke des unveränderten Vergleichs-Speicherwegs.
 */
export function alarmePropsAus(wiz: AlarmeZustandsQuelle) {
	return {
		amtlicheWarnungenImBericht: wiz.officialAlertsEnabled ?? true,
		officialWarningsEnabled: wiz.officialWarningsEnabled ?? false,
		radarAlertEnabled: wiz.radarAlertEnabled ?? false,
		metricAlertLevels: wiz.metricAlertLevels ?? {},
		channelThresholds: wiz.channelThresholds ?? {},
		telegramStyle: wiz.telegramStyle ?? 'rich',
		sendTelegram: wiz.sendTelegram ?? false,
		sendSms: wiz.sendSms ?? false,
		sendPremiumSms: wiz.sendPremiumSms ?? false,
		activeMetricKeys: wiz.activeMetricKeys ?? null,
		// `undefined` ist hier ein gültiger Wert — siehe Diskriminator-Regel oben.
		cooldownMinutes: wiz.alertCooldownMinutes,
		quietFrom: wiz.alertQuietFrom,
		quietTo: wiz.alertQuietTo,
		zonenBezug: 'des ersten Orts',
		onOfficialWarningsChange: (an: boolean) => {
			wiz.officialWarningsEnabled = an;
		},
		onMetricLevelChange: (metrik: string, stufe: string) => {
			wiz.metricAlertLevels = { ...(wiz.metricAlertLevels ?? {}), [metrik]: stufe };
		},
		onChannelToggle: (kanal: ChannelKind) => {
			// E-Mail bleibt implizit (compare_official_alert.py:161-169) — dafür
			// gibt es im Vergleich keinen Schalter.
			if (kanal === 'telegram') wiz.sendTelegram = !wiz.sendTelegram;
			else if (kanal === 'sms') wiz.sendSms = !wiz.sendSms;
			else if (kanal === 'premium_sms') wiz.sendPremiumSms = !wiz.sendPremiumSms;
		},
		onThresholdChange: (kanal: ChannelKind, stufe: ChannelThreshold) => {
			// Issue #1745 A (Landmine 1): die VOLLE Struktur durchreichen statt
			// Feld-für-Feld zu picken — ein explizites Dreifeld-Objekt würde
			// premium_sms still verwerfen.
			wiz.channelThresholds = applyThresholdChange(
				vollstaendigeSchwellen(wiz.channelThresholds ?? {}),
				kanal,
				stufe
			) as unknown as Record<string, string>;
		},
		onTelegramStyleChange: (stil: 'rich' | 'kurzform') => {
			wiz.telegramStyle = stil;
		},
		onCooldownChange: (minuten: number | undefined) => {
			wiz.alertCooldownMinutes = minuten;
		},
		onQuietHoursChange: (von: string | undefined, bis: string | undefined) => {
			wiz.alertQuietFrom = von;
			wiz.alertQuietTo = bis;
		},
		onRadarAlertChange: (an: boolean) => {
			wiz.radarAlertEnabled = an;
		},
		/** Rollback-Senke: `rollbackAlarmSnapshot` (alarmeVergleichSpeicherung.ts)
		 *  setzt nach einem gescheiterten PUT feldweise zurück. KEIN Bedienelement
		 *  schreibt hierüber — die acht Gesten-Rückrufe oben sind die einzigen
		 *  Schreibwege der Oberfläche. */
		onAlarmFeldSetzen: (feld: string, wert: unknown) => {
			(wiz as unknown as Record<string, unknown>)[feld] = wert;
		}
	};
}
