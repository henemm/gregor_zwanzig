// Issue #2276 Scheibe S2 (Epic #2345) — Speicherweg des Alarme-Reiters im
// Ortsvergleich-Hub. Der Reiter speichert SELBST über den Speicher-Controller
// der Seite (schedule/flush/retryConflict), wie bei der Trip — nicht mehr über
// Wrapper + `handleAlarmeCommit` in CompareTabs.svelte.
//
// Spec: docs/specs/modules/rework_2276_s2_alarme.md
//
// AC-9: dieses Modul lädt zur Laufzeit NICHT die Compare-Hub-Klebeschicht
// (aufgelöst in Issue #2276 S6f) — AlarmHydrationTarget ist seither lokal
// definiert (s. u.), kein Typ-Import mehr aus compare/. Nutzlast-Baustein
// ist `buildComparePresetSavePayload` (Spec, Design Punkt 2: Voll-Spread).
//
// Kein Browser-/SvelteKit-Import — lauffähig unter node --experimental-strip-types.

import type { ActivityProfile, ComparePreset, Corridor } from '../../types.ts';
import type { IdealRange } from './corridor-editor/corridorEditorState.ts';
import type { SaveFn, SaveStatus } from '../../stores/saveStatusStore.svelte.ts';
import { merkeNutzlast } from '../../stores/nutzlastStand.ts';
import type { PutClient } from './tripSpeicherung.ts';
import type { AlertChannelState } from './alarme-tab/alertChannelState.ts';
import { buildComparePresetSavePayload, waehleEigenfelder } from '../compare/compareEditorSave.ts';
import {
	normalizeStoredActiveMetrics,
	normalizeStoredOutlookMetrics
} from './weather-metrics-tab/compareMetricSelection.ts';

/** Plain-Snapshot der persistenzrelevanten Alarme-Reiter-Felder.
 * `corridors` ist bewusst NICHT Teil des Snapshots — die Korridor-Persistenz
 * bleibt exklusiv beim Idealwerte-Reiter. Optionale Felder: `undefined`
 * bedeutet „nicht editiert" (Round-Trip aus dem Preset). */
export interface AlarmSnapshot {
	officialAlertsEnabled: boolean;
	officialWarningsEnabled: boolean;
	radarAlertEnabled: boolean;
	metricAlertLevels: Record<string, string>;
	alertCooldownMinutes?: number;
	alertQuietFrom?: string;
	alertQuietTo?: string;
	// Issue #1260: ein reiner Kurzstil-Klick muss als Differenz erkannt werden.
	telegramStyle?: 'rich' | 'kurzform';
	// Issue #1461 S3b-2b: Kanal-Schwellen.
	// Issue #2293 S2 (Entkopplung, AC-9): sendTelegram/sendSms/sendPremiumSms sind
	// NICHT mehr die Alarm-Kanal-Quelle -- das uebernimmt `channels` (s.u.). Die
	// drei Felder bleiben nur optional stehen, weil aeltere Testliterale sie noch
	// setzen (kein Schreiber/Leser mehr in diesem Modul).
	sendTelegram?: boolean;
	sendSms?: boolean;
	sendPremiumSms?: boolean;
	channelThresholds?: Record<string, string>;
	// Issue #2293 Scheibe S2 (Implementation Details Abschnitt 3): alle vier
	// Alarm-Kanaele als EIN Objekt statt der drei Flach-Felder oben -- Vorbild
	// `buildAlarmeDeliveryPayload` (Trip).
	channels?: AlertChannelState;
}

/** Ziel-Objekt fuer `hydrateAlarmFieldsFromPreset`: ALLE Felder optional, damit
 * sowohl ein frischer Plain-Objekt-Stub (Kern-Test) als auch die reale
 * `CompareWizardState`-Instanz (CompareTabs.svelte) strukturell passen —
 * eine `Record<string, unknown>`-Signatur waere fuer die Klasseninstanz NICHT
 * zuweisbar (kein Index-Signature), waehrend optionale benannte Felder in
 * beide Richtungen kompatibel sind. */
export interface AlarmHydrationTarget {
	officialAlertsEnabled?: boolean;
	officialWarningsEnabled?: boolean;
	radarAlertEnabled?: boolean;
	metricAlertLevels?: Record<string, string>;
	alertCooldownMinutes?: number;
	alertQuietFrom?: string;
	alertQuietTo?: string;
	corridors?: Corridor[];
	// Issue #1260: Telegram-Kurzstil-Toggle im Hub-Alarme-Tab
	// (display_config.telegram_style). Default "rich".
	telegramStyle?: 'rich' | 'kurzform';
	// Issue #2293 S2 (AC-9): sendTelegram/sendSms/sendPremiumSms sind seit dieser
	// Scheibe reine Briefing-Felder (versandVergleichSpeicherung.ts) -- kein
	// Schreiber/Leser mehr hier. `channels` (s.u.) uebernimmt die Alarm-Seite.
	sendTelegram?: boolean;
	sendSms?: boolean;
	sendPremiumSms?: boolean;
	channelThresholds?: Record<string, string>;
	// Issue #2293 Scheibe S2: Alarm-Kanal-Bestand (vier Booleans) statt der drei
	// Flach-Felder oben -- Quelle der Hydration ist reconstructCompareAlertChannels.
	channels?: AlertChannelState;
	// Issue #1320: activeMetricKeys wird sonst nur von den Hydrations-Effekten
	// der Tabs "wetter-metriken"/"idealwerte" befuellt — fehlt Alarme als
	// Erst-Tab (Deep-Link), zeigt AlarmeTab.svelte faelschlich "keine Metriken".
	// Issue #1366 F002: `string[] | null`, damit `wizardState` (jetzt nullable)
	// strukturell zuweisbar bleibt -- hydrateAlarmFieldsFromPreset schreibt hier
	// ohnehin immer einen konkreten Wert (Zeile unten), nie `null`.
	activeMetricKeys?: string[] | null;
}

/** Aktueller Alarmstand von `wiz` als entkoppelte Kopie (JSON-Rundreise löst
 *  Svelte-$state-Proxies zuverlässig auf). */
export function alarmSnapshotAus(wiz: AlarmHydrationTarget): AlarmSnapshot {
	return JSON.parse(
		JSON.stringify({
			officialAlertsEnabled: wiz.officialAlertsEnabled,
			officialWarningsEnabled: wiz.officialWarningsEnabled,
			radarAlertEnabled: wiz.radarAlertEnabled,
			metricAlertLevels: wiz.metricAlertLevels,
			alertCooldownMinutes: wiz.alertCooldownMinutes,
			alertQuietFrom: wiz.alertQuietFrom,
			alertQuietTo: wiz.alertQuietTo,
			telegramStyle: wiz.telegramStyle,
			channelThresholds: wiz.channelThresholds,
			channels: wiz.channels
		})
	) as AlarmSnapshot;
}

// Issue #2375: Feld-Besitz des Alarme-Reiters (Spec compare_konfliktschutz_teilfelder.md
// §2). `official_alerts_enabled` gehört NICHT dazu (Wetter-Metriken), ebenso keine
// `send_*`-Felder (Versand).
const ALARM_TOP = [
	'alert_channels',
	'alert_channel_thresholds',
	'alert_cooldown_minutes',
	'alert_quiet_from',
	'alert_quiet_to',
	'official_warnings',
	'radar_alert_enabled'
] as const;
const ALARM_DISPLAY = ['metric_alert_levels', 'telegram_style'] as const;

/**
 * EINZIGE Erzeugerin der Alarm-Nutzlast (Issue #2375: Teilfeld-Nutzlast). Die
 * Alarmfelder kommen aus `current` (Live-Zustand, nie aus der Basis); die
 * Übersetzungen laufen weiter über `buildComparePresetSavePayload`, gesendet
 * werden aber nur die Eigenfelder — der Server mergt fehlende Felder als
 * „unverändert". `officialWarnings` trägt NIEMALS `sources` (F001, S4).
 *
 * Issue #2293 S2 (AC-9/AC-10): der Alarm-Kanal-Bestand läuft als
 * `alert_channels` (`current.channels`); `send_telegram`/`send_sms`/
 * `send_premium_sms` sind Briefing-Felder des Versand-Reiters und stehen nie im
 * Alarm-Body.
 */
export function baueAlarmNutzlast(
	preset: ComparePreset,
	current: AlarmSnapshot
): { url: string; body: ComparePreset } {
	const displayConfig = (preset.display_config as Record<string, unknown>) ?? {};
	const voll = buildComparePresetSavePayload(preset, {
		name: preset.name,
		activityProfile: (preset.profil as ActivityProfile) ?? null,
		pickedIds: preset.location_ids ?? [],
		region: (displayConfig.region as string) ?? '',
		idealRanges: (displayConfig.ideal_ranges as Record<string, IdealRange>) ?? {},
		activeMetricKeys: normalizeStoredActiveMetrics(displayConfig.active_metrics) ?? undefined,
		channelActiveMetricKeys: undefined,
		metricAlertLevels:
			current.metricAlertLevels ?? (displayConfig.metric_alert_levels as Record<string, string> | undefined),
		channelThresholds:
			current.channelThresholds ?? (preset.alert_channel_thresholds as Record<string, string> | undefined),
		corridors: preset.corridors,
		alertChannels: current.channels,
		alertCooldownMinutes: current.alertCooldownMinutes,
		alertQuietFrom: current.alertQuietFrom,
		alertQuietTo: current.alertQuietTo,
		officialAlertsEnabled: current.officialAlertsEnabled,
		officialWarnings: { enabled: current.officialWarningsEnabled },
		radarAlertEnabled: current.radarAlertEnabled,
		telegramStyle: current.telegramStyle,
		hourlyMetricKeys: displayConfig.hourly_metrics as string[] | null | undefined,
		hourlyEnabled: preset.hourly_enabled,
		outlookMetricKeys: normalizeStoredOutlookMetrics(displayConfig.outlook_metrics) ?? undefined,
		outlookMetricFormats:
			(displayConfig.outlook_metric_formats as Record<string, boolean> | undefined) ?? undefined,
		outlookEnabled: preset.outlook_enabled,
		dayWindowStartHour: preset.day_window_start_hour ?? undefined,
		dayWindowEndHour: preset.day_window_end_hour ?? undefined
	});
	// Issue #2375: NUR die Alarm-Eigenfelder senden (Feld-Besitz-Tabelle) — kein
	// official_alerts_enabled (Wetter-Metriken), keine send_* (Versand).
	return waehleEigenfelder(voll, ALARM_TOP, ALARM_DISPLAY);
}

/**
 * Liefert `null`, wenn sich der Alarm-Snapshot seit dem letzten gespeicherten
 * Stand NICHT verändert hat (kein unnötiger PUT), sonst die fertige Nutzlast.
 */
export function flushPendingAlarmSave(
	preset: ComparePreset,
	current: AlarmSnapshot,
	before: AlarmSnapshot | null
): { url: string; body: ComparePreset } | null {
	const baseline = before ?? current;
	if (JSON.stringify(current) === JSON.stringify(baseline)) return null;
	return baueAlarmNutzlast(preset, current);
}

/**
 * Diff-basierter Rollback (Issue #1258 S5, F001): ein Feld wird nur
 * zurückgesetzt, wenn `state` noch exakt den Wert trägt, den DIESER
 * gescheiterte Vorgang gesendet hat — ein zwischenzeitlicher Edit eines
 * Nachbar-Reiters an einem geteilten Feld (Cooldown, Stille Stunden,
 * Metrik-Stufen) überlebt.
 */
export function rollbackAlarmSnapshot(
	state: AlarmHydrationTarget,
	before: AlarmSnapshot,
	attempted: AlarmSnapshot
): void {
	const fields: (keyof AlarmSnapshot)[] = [
		'officialAlertsEnabled',
		'officialWarningsEnabled',
		'radarAlertEnabled',
		'metricAlertLevels',
		'alertCooldownMinutes',
		'alertQuietFrom',
		'alertQuietTo',
		'telegramStyle',
		'channelThresholds',
		// Issue #2293 S2: channels ersetzt die drei Flach-Felder in der
		// Rollback-Feldliste (Alarm-Kanal-Quelle, s. AlarmSnapshot).
		'channels'
	];
	const target = state as Record<string, unknown>;
	for (const field of fields) {
		if (JSON.stringify(target[field]) === JSON.stringify(attempted[field])) {
			target[field] = before[field];
		}
	}
}

/**
 * Issue #2276 S6c: Bruecke zwischen den WERTPROPS des Alarme-Organismus und
 * diesem (unveraenderten) Speicherweg. Seit S6c haelt `AlarmeTab` keine
 * Wizard-Referenz mehr — es reicht seine Props herein, und HIER, an genau
 * einer Stelle, treffen die beiden Namensraeume aufeinander.
 *
 * Gelesen wird IMMER frisch (`werte()` je Zugriff): ein einmal gebautes Objekt
 * saehe nach der ersten Aenderung veraltete Werte, und der Diff-Gate-Vergleich
 * fiele dann stumm aus. Geschrieben wird ausschliesslich vom diff-basierten
 * Rollback (`rollbackAlarmSnapshot`) — `setzen` meldet das an den Halter des
 * Zustands weiter; kein Bedienelement schreibt hierueber.
 */
const PROP_JE_FELD: Record<string, string> = {
	// Persistenzwert OHNE Bedienelement im Alarme-Reiter: der Schalter dafuer
	// steht im Inhalt-Bereich (#1301 D2). Er muss trotzdem durch den Snapshot
	// laufen, sonst faellt er beim naechsten Alarm-PUT aus der Nutzlast.
	officialAlertsEnabled: 'amtlicheWarnungenImBericht',
	alertCooldownMinutes: 'cooldownMinutes',
	alertQuietFrom: 'quietFrom',
	alertQuietTo: 'quietTo'
};

export function alarmZustandsBruecke(
	werte: () => Record<string, unknown>,
	setzen?: (feld: string, wert: unknown) => void
): AlarmHydrationTarget {
	return new Proxy({} as AlarmHydrationTarget, {
		get: (_ziel, feld) => werte()[PROP_JE_FELD[feld as string] ?? (feld as string)],
		set: (_ziel, feld, wert) => {
			setzen?.(feld as string, wert);
			return true;
		}
	});
}

export interface AlarmeVergleichSpeicherungOptionen {
	client: PutClient;
	/** Issue #2276 S6c: der gehaltene Alarmstand. Frueher `wiz` — der
	 *  Alarme-Organismus reicht seit S6c eine Bruecke ueber seine Wertprops
	 *  herein, kein Wizard-Objekt mehr. */
	zustand: AlarmHydrationTarget;
	/** Basis — als Getter, damit sie ERST bei Ausführung in der Queue gelesen wird (AC-3). */
	preset: () => ComparePreset;
	/** Hub-Queue (`hubPutQueue.enqueue`) — Serialisierung mit den Nachbar-Reitern. */
	enqueueHubWrite: <T>(fn: () => Promise<T>) => Promise<T>;
	/** Basis-Rückmeldung nach Erfolg (`currentPreset` im Hub, AC-2). */
	onCompareUpdate: (antwort: ComparePreset) => void;
	saveController: SaveStatus;
}

/**
 * Orchestrierung des Alarm-Speicherns im Ortsvergleich. Anfangs-Baseline =
 * Alarmstand von `zustand` beim Erzeugen (nach der Hydration).
 *
 * `aenderungMelden()`: ohne Unterschied zur Baseline wird ein eigener, noch
 * ausstehender Vorgang verworfen (`cancel` + `markPristine`, AC-5) — sonst
 * `schedule(SaveFn)`. Die SaveFn liest Basis und Alarmstand erst bei
 * Ausführung in der Queue, reicht `init` (keepalive) an den PUT durch (AC-10),
 * rollt nur bei Nicht-412 zurück (AC-4) und wirft den Fehler weiter, damit der
 * Controller `conflict`/`error` anzeigt.
 */
export function erstelleAlarmeVergleichSpeicherung(opt: AlarmeVergleichSpeicherungOptionen): {
	aenderungMelden(): void;
} {
	const { client, zustand, enqueueHubWrite, saveController } = opt;
	let zuletztGespeichert: AlarmSnapshot = alarmSnapshotAus(zustand);
	// Nur einen EIGENEN, noch nicht gestarteten Vorgang verwerfen — ein
	// ausstehender Speichervorgang eines anderen Reiters bleibt unangetastet.
	let eigenerVorgangAussteht = false;

	const saveFn: SaveFn = async (init) => {
		eigenerVorgangAussteht = false;
		await enqueueHubWrite(async () => {
			// F005: nach jedem erfolgreichen PUT den DANN aktuellen Alarmstand gegen
			// den soeben persistierten diffen — eine während des Flugs gemeldete
			// Rücknahme fand gegen die alte Baseline keinen Unterschied. Nachschieben
			// im selben Vorgang, damit „Gespeichert" erst bei Server == UI erscheint.
			for (;;) {
				const current = alarmSnapshotAus(zustand);
				const before = zuletztGespeichert;
				const payload = flushPendingAlarmSave(opt.preset(), current, before);
				if (!payload) return;
				try {
					// Fix-Loop 3 (F201): die GESENDETE Nutzlast bleibt am Funktionsobjekt (Seitenstand-Fortschreibung bei 412).
					merkeNutzlast(saveFn, payload.body);
					const antwort = await client.put<ComparePreset>(payload.url, payload.body, init);
					zuletztGespeichert = current;
					opt.onCompareUpdate(antwort);
				} catch (e) {
					if ((e as { status?: number })?.status !== 412 && !saveController.imWiederholen) {
						rollbackAlarmSnapshot(zustand, before, current);
					}
					throw e;
				}
			}
		});
	};

	return {
		aenderungMelden(): void {
			const current = alarmSnapshotAus(zustand);
			if (JSON.stringify(current) === JSON.stringify(zuletztGespeichert)) {
				if (eigenerVorgangAussteht) {
					eigenerVorgangAussteht = false;
					saveController.cancel();
					saveController.markPristine();
				}
				return;
			}
			eigenerVorgangAussteht = true;
			saveController.schedule(saveFn);
		}
	};
}
