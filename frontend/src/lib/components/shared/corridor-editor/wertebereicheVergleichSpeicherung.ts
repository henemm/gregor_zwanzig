// Issue #2276 Scheibe S3 (Epic #2345) — Speicherweg des Wertebereiche-Reiters
// im Ortsvergleich-Hub. Der Reiter speichert SELBST über den Speicher-Controller
// der Seite (schedule/flush/retryConflict), wie Alarme (S2) und die Tour — der
// zweite Weg (Wrapper `.hub-corridor-wrap` + `<svelte:window onpointerup>` →
// alte Hub-Commit-Funktion) ist entfallen.
//
// Spec: docs/specs/modules/rework_2276_s3_wertebereiche.md
//
// AC-7: dieses Modul lädt zur Laufzeit NICHT die Compare-Klebeschicht
// (`compare/compareHubWizardBridge.ts`) — aus `compare/` kommen nur Typen.
// Nutzlast-Baustein ist `buildComparePresetSavePayload` (Design Punkt 2 + 9).
//
// Kein Browser-/SvelteKit-Import — lauffähig unter node --experimental-strip-types.

import type { ActivityProfile, ComparePreset, Corridor } from '../../../types.ts';
import type { IdealRange } from './corridorEditorState.ts';
import type { SaveFn, SaveStatus } from '../../../stores/saveStatusStore.svelte.ts';
import type { PutClient } from '../tripSpeicherung.ts';
import { buildComparePresetSavePayload } from '../../compare/compareEditorSave.ts';
import { normalizeStoredOutlookMetrics } from '../weather-metrics-tab/compareMetricSelection.ts';
import { materializeActiveMetricKeys } from '../weather-metrics-tab/compareMetricOrder.ts';

/** Plain-Snapshot der 4 persistenzrelevanten Wertebereiche-Felder. */
export interface CorridorSnapshot {
	corridors: Corridor[];
	idealRanges: Record<string, IdealRange>;
	activeMetricKeys: string[];
	metricAlertLevels: Record<string, string>;
}

/** Wizard-Zustand, den der Wertebereiche-Reiter liest/schreibt (Teilmenge von
 *  CompareWizardState — bewusst locker typisiert, kein Laufzeit-Import). */
export type WertebereicheZustand = object;

function felder(ws: WertebereicheZustand): Record<string, unknown> {
	return ws as Record<string, unknown>;
}

/** Aktueller Wertebereiche-Stand von `ws` als entkoppelte Kopie (JSON-Rundreise
 *  löst Svelte-$state-Proxies auf). `activeMetricKeys` materialisiert (#1366). */
export function corridorSnapshotAus(ws: WertebereicheZustand): CorridorSnapshot {
	const f = felder(ws);
	return JSON.parse(
		JSON.stringify({
			corridors: f.corridors ?? [],
			idealRanges: f.idealRanges ?? {},
			activeMetricKeys: materializeActiveMetricKeys((f.activeMetricKeys as string[] | null | undefined) ?? null),
			metricAlertLevels: f.metricAlertLevels ?? {}
		})
	) as CorridorSnapshot;
}

/**
 * EINZIGE Erzeugerin der Wertebereiche-Nutzlast: Voll-Spread über `preset`
 * (Go-Merge mergt `display_config` nur auf Ebene 1), die vier Korridor-Felder
 * aus `current` — `metricAlertLevels` LIVE aus dem Zustand (AC-3), nie aus
 * einer eingefrorenen Preset-Kopie. Alle übrigen Felder laufen durch dieselben
 * Rückfälle wie `buildHubPutPayload` (Lesenormalisierung #1373).
 */
export function baueWertebereichNutzlast(
	preset: ComparePreset,
	current: CorridorSnapshot
): { url: string; body: ComparePreset } {
	const displayConfig = (preset.display_config as Record<string, unknown>) ?? {};
	return buildComparePresetSavePayload(preset, {
		name: preset.name,
		activityProfile: (preset.profil as ActivityProfile) ?? null,
		pickedIds: preset.location_ids ?? [],
		region: (displayConfig.region as string) ?? '',
		idealRanges: current.idealRanges,
		activeMetricKeys: current.activeMetricKeys,
		channelActiveMetricKeys: undefined,
		metricAlertLevels: current.metricAlertLevels,
		channelThresholds: preset.alert_channel_thresholds as Record<string, string> | undefined,
		corridors: current.corridors,
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
 * Liefert `null`, wenn sich der Wertebereiche-Snapshot seit dem letzten
 * gespeicherten Stand NICHT verändert hat (kein unnötiger PUT), sonst die
 * fertige Nutzlast. `before === null` ⇒ der aktuelle Stand ist die Baseline.
 */
export function flushPendingCorridorSave(
	preset: ComparePreset,
	current: CorridorSnapshot,
	before: CorridorSnapshot | null
): { url: string; body: ComparePreset } | null {
	const baseline = before ?? current;
	if (JSON.stringify(current) === JSON.stringify(baseline)) return null;
	return baueWertebereichNutzlast(preset, current);
}

/**
 * Diff-basierter Rollback (Design Punkt 5): ein Feld wird nur zurückgesetzt,
 * wenn `ws` noch exakt den Wert trägt, den DIESER gescheiterte Vorgang
 * gesendet hat — ein zwischenzeitlicher Alarme-Edit an `metricAlertLevels`
 * überlebt.
 */
export function rollbackCorridorSnapshot(
	ws: WertebereicheZustand,
	before: CorridorSnapshot,
	attempted: CorridorSnapshot
): void {
	const target = felder(ws);
	const aktuell = corridorSnapshotAus(ws);
	for (const field of ['corridors', 'idealRanges', 'activeMetricKeys', 'metricAlertLevels'] as const) {
		if (JSON.stringify(aktuell[field]) === JSON.stringify(attempted[field])) {
			target[field] = before[field];
		}
	}
}

export interface WertebereicheVergleichSpeicherungOptionen {
	client: PutClient;
	ws: WertebereicheZustand;
	/** Basis — als Getter, damit sie ERST bei Ausführung in der Queue gelesen wird. */
	preset: () => ComparePreset;
	/** Hub-Queue (`hubPutQueue.enqueue`) — Serialisierung mit den Nachbar-Reitern. */
	enqueueHubWrite: <T>(fn: () => Promise<T>) => Promise<T>;
	/** Basis-Rückmeldung nach Erfolg (`currentPreset` im Hub). */
	onCompareUpdate: (antwort: ComparePreset) => void;
	saveController: SaveStatus;
}

/**
 * Orchestrierung des Wertebereiche-Speicherns im Ortsvergleich (Muster
 * `erstelleAlarmeVergleichSpeicherung`, S2). Anfangs-Baseline = Stand von `ws`
 * beim Erzeugen (nach der Hydration, Design Punkt 6).
 *
 * `aenderungMelden()`: ohne Unterschied zur Baseline wird ein eigener, noch
 * ausstehender Vorgang verworfen — sonst `schedule(SaveFn)`. Die SaveFn liest
 * Basis und Stand erst bei Ausführung in der Queue, reicht `init` (keepalive)
 * an den PUT durch (AC-10), rollt nur bei Nicht-412 zurück (AC-5) und wirft den
 * Fehler weiter, damit der Controller `conflict`/`error` anzeigt.
 */
export function erstelleWertebereicheVergleichSpeicherung(opt: WertebereicheVergleichSpeicherungOptionen): {
	aenderungMelden(): void;
} {
	const { client, ws, enqueueHubWrite, saveController } = opt;
	let zuletztGespeichert: CorridorSnapshot = corridorSnapshotAus(ws);
	let eigenerVorgangAussteht = false;

	const saveFn: SaveFn = async (init) => {
		eigenerVorgangAussteht = false;
		await enqueueHubWrite(async () => {
			// Nachschieben im selben Vorgang (S2 F005): „Gespeichert" erst bei Server == UI.
			for (;;) {
				const current = corridorSnapshotAus(ws);
				const before = zuletztGespeichert;
				const payload = flushPendingCorridorSave(opt.preset(), current, before);
				if (!payload) return;
				try {
					const antwort = await client.put<ComparePreset>(payload.url, payload.body, init);
					zuletztGespeichert = current;
					opt.onCompareUpdate(antwort);
				} catch (e) {
					if ((e as { status?: number })?.status !== 412) {
						rollbackCorridorSnapshot(ws, before, current);
					}
					throw e;
				}
			}
		});
	};

	return {
		aenderungMelden(): void {
			const current = corridorSnapshotAus(ws);
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

/** Erzeugungs-Bedingung der Vergleichs-Speicherung im Editor (AC-9, AC-12):
 *  nur im Ortsvergleich-Hub (vergleich + Zustand + Basis + Controller). */
export function wertebereicheVergleichSpeicherungAktiv(p: {
	context: string;
	ws: unknown;
	preset: unknown;
	saveController: unknown;
}): boolean {
	return p.context === 'vergleich' && !!p.ws && !!p.preset && !!p.saveController;
}

/** Reiter des Ortsvergleich-Hubs, die SELBST über den einen Speicher-Platz des
 *  Controllers speichern (Design Punkt 4). Issue #2276 S4: 'wetter-metriken'
 *  ergaenzt (kombinierte Wetter-Metriken/Layout-Orchestrierung). */
export const SELBST_SPEICHERNDE_VERGLEICH_REITER: readonly string[] = [
	'alarme',
	'idealwerte',
	'wetter-metriken'
];

/**
 * Generischer Flush-Guard vor dem Reiterwechsel (TripTabs-Muster): verlässt
 * der Nutzer einen selbst speichernden Reiter, wird dessen ausstehende
 * Änderung gesendet, BEVOR der Wechsel freigegeben wird (AC-4, S2 AC-6).
 */
export async function sichereSelbstSpeichererVorReiterwechsel(
	aktiverReiter: string,
	zielReiter: string,
	saveController?: SaveStatus
): Promise<void> {
	if (!SELBST_SPEICHERNDE_VERGLEICH_REITER.includes(aktiverReiter)) return;
	if (zielReiter === aktiverReiter || !saveController) return;
	await saveController.flush();
}
