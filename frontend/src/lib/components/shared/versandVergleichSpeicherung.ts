// Issue #2276 Scheibe S5 (Epic #2345) — Speicherweg des Versand-Reiters im
// Ortsvergleich-Hub. Der Reiter speichert SELBST über den Speicher-Controller
// der Seite (schedule/flush/retryConflict), wie bei der Tour — nicht mehr über
// den Wrapper-Div `.hub-versand-wrap` + `handleVersandCommit` in
// CompareTabs.svelte.
//
// Spec: docs/specs/modules/rework_2276_s5_versand.md
//
// AC-8: dieses Modul lädt zur Laufzeit NICHT die Compare-Klebeschicht
// (`compare/compareHubWizardBridge.ts`). Nutzlast-Baustein ist
// `buildComparePresetSavePayload` (Spec, Design Punkt 5: Voll-Spread).
//
// Kein Browser-/SvelteKit-Import — lauffähig unter node --experimental-strip-types.

import type { ActivityProfile, ComparePreset } from '../../types.ts';
import type { IdealRange } from './corridor-editor/corridorEditorState.ts';
import type { SaveFn, SaveStatus } from '../../stores/saveStatusStore.svelte.ts';
import type { PutClient } from './tripSpeicherung.ts';
import { buildComparePresetSavePayload } from '../compare/compareEditorSave.ts';
import {
	normalizeStoredActiveMetrics,
	normalizeStoredOutlookMetrics
} from './weather-metrics-tab/compareMetricSelection.ts';

/** Plain-Snapshot der 10 persistenzrelevanten Versand-Felder (OHNE sendEmail —
 * `ComparePreset` kennt kein `send_email`-Feld, s. `hydrateVersandFieldsFromPreset`).
 *
 * `alertCooldownMinutes`/`alertQuietFrom`/`alertQuietTo` sind die drei toten
 * Legacy-Restfelder: kein Kontrollelement des Versand-Reiters mutiert sie
 * (die Alert-Zustellungs-Sektion zog in #1258 S4 nach AlarmeTab.svelte ab).
 * Sie bleiben BEWUSST Teil von Snapshot und Nutzlast (Spec, Implementation
 * Details Punkt 6) — der Go-Handler dekodiert ein PUT ins volle Modell, ein
 * Weglassen würde sie bei einem Bestands-Preset nullen. Entfernung gehört an
 * S6/#2285, sobald ein Patch-DTO existiert. */
export interface VersandSnapshot {
	sendTelegram: boolean;
	sendSms: boolean;
	morningEnabled: boolean;
	morningTime: string;
	eveningEnabled: boolean;
	eveningTime: string;
	endDate: string | null;
	alertCooldownMinutes?: number;
	alertQuietFrom?: string;
	alertQuietTo?: string;
}

/** Ziel-Objekt der Versand-Felder: ALLE Felder optional, damit sowohl ein
 * Plain-Objekt-Stub (Kern-Test) als auch die reale `CompareWizardState`-
 * Instanz (CompareTabs.svelte) strukturell passen — Begründung 1:1 wie bei
 * `AlarmHydrationTarget`. */
export interface VersandHydrationTarget {
	sendTelegram?: boolean;
	sendSms?: boolean;
	morningEnabled?: boolean;
	morningTime?: string;
	eveningEnabled?: boolean;
	eveningTime?: string;
	endDate?: string | null;
	alertCooldownMinutes?: number;
	alertQuietFrom?: string;
	alertQuietTo?: string;
}

/**
 * Issue #1256 Scheibe 7 (AC-35/36): Hydration der Versand-Felder, die der
 * eingebettete `VersandTab context="vergleich"` im Hub aus `wizardState.*`
 * liest. Defaults identisch zur Edit-Routen-Hydration
 * (routes/compare/[id]/edit/+page.svelte:44-61). `sendEmail` ist IMMER true —
 * ComparePreset hat kein `send_email`-Feld (vorbestehende Luecke, Known
 * Limitation der S7-Freigabe).
 *
 * Issue #2276 S5: reiner Read-Helfer, mit dem Speicherweg aus der
 * Klebeschicht hierher umgezogen (AC-8).
 */
export function hydrateVersandFieldsFromPreset(
	preset: ComparePreset
): VersandSnapshot & { sendEmail: true } {
	return {
		sendEmail: true,
		sendTelegram: preset.send_telegram ?? false,
		sendSms: preset.send_sms ?? false,
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

/** Aktueller Versandstand von `wiz` als entkoppelte Kopie (JSON-Rundreise löst
 *  Svelte-$state-Proxies zuverlässig auf). `endDate` ist Teil des Snapshots —
 *  „Bis auf Weiteres" ist ein reiner Button-Klick ohne change-/focusout-
 *  Ereignis und wäre sonst unsichtbar (AC-5). */
export function versandSnapshotAus(wiz: VersandHydrationTarget): VersandSnapshot {
	return JSON.parse(
		JSON.stringify({
			sendTelegram: wiz.sendTelegram,
			sendSms: wiz.sendSms,
			morningEnabled: wiz.morningEnabled,
			morningTime: wiz.morningTime,
			eveningEnabled: wiz.eveningEnabled,
			eveningTime: wiz.eveningTime,
			endDate: wiz.endDate,
			alertCooldownMinutes: wiz.alertCooldownMinutes,
			alertQuietFrom: wiz.alertQuietFrom,
			alertQuietTo: wiz.alertQuietTo
		})
	) as VersandSnapshot;
}

/**
 * EINZIGE Erzeugerin der Versand-Nutzlast: Voll-Spread über `preset` via
 * `buildComparePresetSavePayload`, die Versandfelder aus `current`. Die
 * Nicht-Versandfelder laufen durch DIESELBEN Rückfälle wie der abgeschaffte Hub-PUT-Pfad
 * (Lesenormalisierung #1373, sonst Datenverlust an der Metrik-Auswahl).
 * `officialWarnings` bleibt undefined — der Bestand round-trippt über
 * `...original`, ein Echo würde `sources` clobbern (F001, S4).
 * `sendPremiumSms` ist KEIN Versand-Feld im Ortsvergleich (ADR-0049) und
 * round-trippt ebenfalls.
 */
export function baueVersandNutzlast(
	preset: ComparePreset,
	current: VersandSnapshot
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
		metricAlertLevels: displayConfig.metric_alert_levels as Record<string, string> | undefined,
		channelThresholds: preset.alert_channel_thresholds as Record<string, string> | undefined,
		corridors: preset.corridors,
		sendTelegram: current.sendTelegram,
		sendSms: current.sendSms,
		morningEnabled: current.morningEnabled,
		morningTime: current.morningTime,
		eveningEnabled: current.eveningEnabled,
		eveningTime: current.eveningTime,
		endDate: current.endDate,
		// Spec Punkt 6: die drei toten Legacy-Restfelder MÜSSEN mitgesendet
		// werden, sonst nullt der Versand-PUT Alarm-Zustellungsfelder (AC-11).
		alertCooldownMinutes: current.alertCooldownMinutes,
		alertQuietFrom: current.alertQuietFrom,
		alertQuietTo: current.alertQuietTo,
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
 * Liefert `null`, wenn sich der Versand-Snapshot seit dem letzten gespeicherten
 * Stand NICHT verändert hat (kein unnötiger PUT, #1234), sonst die fertige
 * Nutzlast.
 */
export function flushPendingVersandSave(
	preset: ComparePreset,
	current: VersandSnapshot,
	before: VersandSnapshot | null
): { url: string; body: ComparePreset } | null {
	const baseline = before ?? current;
	if (JSON.stringify(current) === JSON.stringify(baseline)) return null;
	return baueVersandNutzlast(preset, current);
}

/**
 * Diff-basierter Rollback (Issue #2276 S5, AC-3): ein Feld wird nur
 * zurückgesetzt, wenn `state` noch exakt den Wert trägt, den DIESER
 * gescheiterte Vorgang gesendet hat — eine zwischenzeitliche Änderung des
 * Alarme-Reiters an einem geteilten Feld (`sendTelegram`/`sendSms`) oder an
 * den drei Legacy-Restfeldern überlebt. Ersetzt den bisherigen unbedingten
 * Full-Overwrite-Rollback aus `handleVersandCommit` (Datenverlust-Klasse
 * BUG-DATALOSS-GR221).
 */
export function rollbackVersandSnapshot(
	state: VersandHydrationTarget,
	before: VersandSnapshot,
	attempted: VersandSnapshot
): void {
	const fields: (keyof VersandSnapshot)[] = [
		'sendTelegram',
		'sendSms',
		'morningEnabled',
		'morningTime',
		'eveningEnabled',
		'eveningTime',
		'endDate',
		'alertCooldownMinutes',
		'alertQuietFrom',
		'alertQuietTo'
	];
	const target = state as Record<string, unknown>;
	for (const field of fields) {
		if (JSON.stringify(target[field]) === JSON.stringify(attempted[field])) {
			target[field] = before[field];
		}
	}
}

/** Erzeugungs-Bedingung der Versand-Speicherung im Editor (AC-9, AC-12):
 *  nur im Ortsvergleich-Hub (vergleich + Zustand + Basis + Controller). */
export function versandVergleichSpeicherungAktiv(p: {
	context: string;
	wiz: unknown;
	preset: unknown;
	saveController: unknown;
}): boolean {
	return p.context === 'vergleich' && !!p.wiz && !!p.preset && !!p.saveController;
}

export interface VersandVergleichSpeicherungOptionen {
	client: PutClient;
	wiz: VersandHydrationTarget;
	/** Basis — als Getter, damit sie ERST bei Ausführung in der Queue gelesen wird. */
	preset: () => ComparePreset;
	/** Hub-Queue (`hubPutQueue.enqueue`) — Serialisierung mit den Nachbar-Reitern. */
	enqueueHubWrite: <T>(fn: () => Promise<T>) => Promise<T>;
	/** Basis-Rückmeldung nach Erfolg (`currentPreset` im Hub). */
	onCompareUpdate: (antwort: ComparePreset) => void;
	saveController: SaveStatus;
}

/**
 * Orchestrierung des Versand-Speicherns im Ortsvergleich (S2-Muster, EINE
 * Domäne). Anfangs-Baseline = Versandstand von `wiz` beim Erzeugen (nach der
 * Hydration).
 *
 * `aenderungMelden()`: ohne Unterschied zur Baseline wird ein eigener, noch
 * ausstehender Vorgang verworfen (`cancel` + `markPristine`) — sonst
 * `schedule(SaveFn)`. Die SaveFn liest Basis und Versandstand erst bei
 * Ausführung in der Queue (AC-2: `sendTelegram`/`sendSms` live aus `wiz`,
 * nie aus einer eingefrorenen Kopie), reicht `init` (keepalive) an den PUT
 * durch (AC-10), rollt nur bei Nicht-412 zurück (AC-6) und wirft den Fehler
 * weiter, damit der Controller `conflict`/`error` anzeigt.
 */
export function erstelleVersandVergleichSpeicherung(
	opt: VersandVergleichSpeicherungOptionen
): { aenderungMelden(): void } {
	const { client, wiz, enqueueHubWrite, saveController } = opt;
	let zuletztGespeichert: VersandSnapshot = versandSnapshotAus(wiz);
	// Nur einen EIGENEN, noch nicht gestarteten Vorgang verwerfen — ein
	// ausstehender Speichervorgang eines anderen Reiters bleibt unangetastet.
	let eigenerVorgangAussteht = false;

	const saveFn: SaveFn = async (init) => {
		eigenerVorgangAussteht = false;
		await enqueueHubWrite(async () => {
			// F005-Muster: nach jedem erfolgreichen PUT den DANN aktuellen Stand
			// gegen den soeben persistierten diffen — eine während des Flugs
			// gemeldete Änderung fand gegen die alte Baseline keinen Unterschied.
			// Nachschieben im selben Vorgang, damit „Gespeichert" erst bei
			// Server == UI erscheint.
			for (;;) {
				const current = versandSnapshotAus(wiz);
				const before = zuletztGespeichert;
				const payload = flushPendingVersandSave(opt.preset(), current, before);
				if (!payload) return;
				try {
					const antwort = await client.put<ComparePreset>(payload.url, payload.body, init);
					zuletztGespeichert = current;
					opt.onCompareUpdate(antwort);
				} catch (e) {
					if ((e as { status?: number })?.status !== 412) {
						rollbackVersandSnapshot(wiz, before, current);
					}
					throw e;
				}
			}
		});
	};

	return {
		aenderungMelden(): void {
			const current = versandSnapshotAus(wiz);
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
