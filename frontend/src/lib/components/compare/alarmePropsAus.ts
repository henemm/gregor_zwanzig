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
// `AlarmeTab` unterscheidet Vergleich und Trip an etwas, das dieses Bündel
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
	newEntityAlertChannelDefault,
	resolveAlertChannelThresholds,
	type AlertChannelState,
	type AlertChannelThresholdState,
	type ChannelKind,
	type ChannelThreshold
} from '../shared/alarme-tab/alertChannelState.ts';

/** Strukturelle Sicht auf die Alarmfelder des Compare-Wizard-Zustands —
 *  absichtlich nicht `CompareWizardState` selbst, damit diese Funktion auch
 *  gegen einen hydrierten Plain-Zustand (Hub-Bridge) arbeitet.
 *
 *  Issue #2293 Scheibe S2 (AC-9 Entkopplung): `sendTelegram`/`sendSms`/
 *  `sendPremiumSms` sind hier ENTFALLEN — sie sind seit dieser Scheibe reine
 *  Briefing-Felder (`versandPropsAus.ts`) und duerfen die Alarm-Kanal-Quelle
 *  nicht mehr beeinflussen. `channels` uebernimmt die Alarm-Seite komplett. */
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
	channels?: AlertChannelState;
	activeMetricKeys?: string[] | null;
}

/**
 * Issue #2293 Scheibe S2 (Implementation Details Abschnitt 3) — Vorbild
 * `shared/alarme-tab/tripChannelReconstruction.ts::reconstructTripAlertChannels`.
 * Vorrang `preset.alert_channels` (seit der Go-Materialisierung bei JEDEM
 * geladenen Preset gesetzt) — 1:1 uebernommen, KEIN hartes `email:true`.
 * Defense-in-Depth-Rueckfall auf die flachen `send_telegram`/`send_sms`/
 * `send_premium_sms`-Felder (E-Mail dabei immer `true`) fuer den nur noch
 * theoretischen Fall eines Rohobjekts ohne `alert_channels`.
 */
export function reconstructCompareAlertChannels(preset: {
	alert_channels?: { email?: boolean; telegram?: boolean; sms?: boolean; premium_sms?: boolean } | null;
	send_telegram?: boolean;
	send_sms?: boolean;
	send_premium_sms?: boolean;
}): AlertChannelState {
	const ac = preset.alert_channels;
	if (ac) {
		return {
			email: ac.email ?? false,
			telegram: ac.telegram ?? false,
			sms: ac.sms ?? false,
			premium_sms: ac.premium_sms ?? false
		};
	}
	return {
		email: true,
		telegram: preset.send_telegram ?? false,
		sms: preset.send_sms ?? false,
		premium_sms: preset.send_premium_sms ?? false
	};
}

/** Vollständige Kanal-Schwellen OHNE stillen Wertverlust: die Vorgabe „gering"
 *  füllt nur die Kanäle, für die noch nichts gespeichert ist — ein bereits
 *  gehaltener Wert überlebt unverändert (`resolveAlertChannelThresholds`
 *  allein würde jeden ihm unbekannten Wert auf „gering" zurückdrehen). */
function vollstaendigeSchwellen(bestand: Record<string, string>): AlertChannelThresholdState {
	return { ...resolveAlertChannelThresholds(bestand), ...bestand } as AlertChannelThresholdState;
}

/**
 * Das Prop-Bündel für `AlarmeTab context="vergleich"`: 12 Werte, 8
 * Gesten-Rückrufe, der Zonen-Bezug der Stillen Stunden (#1378 AC-4) und die
 * Rollback-Senke des unveränderten Vergleichs-Speicherwegs.
 *
 * Issue #2293 Scheibe S2: `existingChannels` (Wert) + `onChannelToggle`
 * (Rückruf, alle vier Kanäle inkl. E-Mail) ersetzen die frühere Sonderableitung
 * mit hartem `email:true` und den drei Flach-Feldern — dieselbe `existingChannels`-
 * Prop wie beim Trip (AlarmeTab.svelte bindet sie kontextunabhängig).
 */
export function alarmePropsAus(wiz: AlarmeZustandsQuelle) {
	// Solange der Alarme-Reiter noch nie einen Kanal umgeschaltet hat
	// (`wiz.channels` unbesetzt = frische Neuanlage), gilt der geteilte
	// Neuanlage-Default (Issue #2518) — identisch zum Create-Body-Rueckfall.
	// Bestand wird vorher in `wiz.channels` hydriert (compareHubHydration.ts).
	const aktuelleKanaele = wiz.channels ?? newEntityAlertChannelDefault();
	return {
		amtlicheWarnungenImBericht: wiz.officialAlertsEnabled ?? true,
		officialWarningsEnabled: wiz.officialWarningsEnabled ?? false,
		radarAlertEnabled: wiz.radarAlertEnabled ?? false,
		metricAlertLevels: wiz.metricAlertLevels ?? {},
		channelThresholds: wiz.channelThresholds ?? {},
		telegramStyle: wiz.telegramStyle ?? 'rich',
		existingChannels: aktuelleKanaele,
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
			// Issue #2293 S2 (AC-1/AC-9): schreibt EIN Alarm-Kanal-Objekt (alle
			// vier Kanäle inkl. E-Mail) auf `wiz.channels` — NIE auf
			// sendTelegram/sendSms/sendPremiumSms (Briefing-Felder, Entkopplung).
			const basis = wiz.channels ?? aktuelleKanaele;
			wiz.channels = { ...basis, [kanal]: !basis[kanal] };
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
