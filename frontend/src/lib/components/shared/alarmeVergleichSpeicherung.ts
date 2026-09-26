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
import type { PutClient } from './tripSpeicherung.ts';
import { buildComparePresetSavePayload } from '../compare/compareEditorSave.ts';
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
	// Issue #1461 S3b-2b / #1745 A: Kanal-Schalter + Kanal-Schwellen.
	sendTelegram?: boolean;
	sendSms?: boolean;
	sendPremiumSms?: boolean;
	channelThresholds?: Record<string, string>;
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
	// Issue #1461 S3b-2b (bestaetigter Speicher-Fehler, s. Spec „Implementation
	// Details"): sendTelegram/sendSms fehlten hier bisher komplett -- eine
	// Kanal-Umschaltung im Alarme-Reiter war deshalb weder als Snapshot-Differenz
	// erkennbar noch im PUT-Body enthalten (der Server-Bestand wurde beim
	// naechsten Alarme-Save aktiv zurueckgeschrieben). Analog channelThresholds.
	sendTelegram?: boolean;
	sendSms?: boolean;
	// Issue #1745 A: der vierte Kanal muss aus demselben Grund mit-hydriert
	// werden — sonst ist eine Aenderung im Alarme-Reiter weder als
	// Snapshot-Differenz erkennbar noch im PUT-Body enthalten.
	sendPremiumSms?: boolean;
	channelThresholds?: Record<string, string>;
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
			sendTelegram: wiz.sendTelegram,
			sendSms: wiz.sendSms,
			sendPremiumSms: wiz.sendPremiumSms,
			channelThresholds: wiz.channelThresholds
		})
	) as AlarmSnapshot;
}

/**
 * EINZIGE Erzeugerin der Alarm-Nutzlast (Nahtstelle für #2293 `alert_channels`):
 * Voll-Spread über `preset` via `buildComparePresetSavePayload`, die Alarmfelder
 * aus `current`. Die Nicht-Alarmfelder laufen durch DIESELBEN Rückfälle wie
 * der abgeschaffte Hub-PUT-Pfad (Lesenormalisierung #1373, sonst Datenverlust an der
 * Metrik-Auswahl). `officialWarnings` trägt NIEMALS `sources` (F001, S4).
 */
export function baueAlarmNutzlast(
	preset: ComparePreset,
	current: AlarmSnapshot
): { url: string; body: ComparePreset } {
	const displayConfig = (preset.display_config as Record<string, unknown>) ?? {};
	return buildComparePresetSavePayload(preset, {
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
		sendTelegram: current.sendTelegram,
		sendSms: current.sendSms,
		sendPremiumSms: current.sendPremiumSms,
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
		'sendTelegram',
		'sendSms',
		'sendPremiumSms',
		'channelThresholds'
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
					const antwort = await client.put<ComparePreset>(payload.url, payload.body, init);
					zuletztGespeichert = current;
					opt.onCompareUpdate(antwort);
				} catch (e) {
					if ((e as { status?: number })?.status !== 412) {
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
