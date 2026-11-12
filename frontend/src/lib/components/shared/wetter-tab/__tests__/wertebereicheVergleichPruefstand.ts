// Gemeinsamer Prüfstand der Wertebereiche-Speichertests im Ortsvergleich
// (Issue #2276 Scheibe S3, Epic #2345). KEINE Testdatei (kein `.test.ts`) —
// nur Aufbauhilfen. Bewusst OHNE Import des neuen Moduls
// `wertebereicheVergleichSpeicherung.ts`: der Prüfstand muss auch heute
// laden, damit das Rot der Tests am fehlenden Modul liegt, nicht hier.
//
// Alles ECHT außer dem Transport: echte Hub-Hydration (compareHubHydration),
// echte Editor-Logik (corridorEditorState: buildComparePool/patchRow/removeRow/
// buildCompareCorridorSavePayload — exakt die Schritte von `syncToWizard()` in
// CorridorEditor.svelte), echte SaveStatus-Instanz. Transport: `api` gegen
// `fakeTripServer.ts` (Compare-Preset-Pfad mit ETag/412).

import { SaveStatus } from '../../../../stores/saveStatusStore.svelte.ts';
import type { ComparePreset, SensLevel } from '../../../../types.ts';
import {
	hydrateAlarmFieldsFromPreset,
	hydrateHubFieldsFromPreset
} from '../../../compare/compareHubHydration.ts';
import {
	buildComparePool,
	buildCompareCorridorSavePayload,
	patchRow,
	removeRow,
	type CompareMetricDef,
	type CorridorRowState
} from '../corridorEditorState.ts';
import { materializeActiveMetricKeys } from '../../weather-metrics-tab/compareMetricOrder.ts';

export function makePreset(id: string, overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id,
		name: 'Ortsvergleich Wertebereiche',
		location_ids: ['loc-a', 'loc-b', 'loc-c'],
		schedule: 'daily',
		previous_schedule: 'daily',
		profil: 'wandern',
		hour_from: 6,
		hour_to: 9,
		forecast_hours: 48,
		empfaenger: ['a@example.com'],
		created_at: '2026-01-01T00:00:00Z',
		official_alerts_enabled: true,
		official_warnings: { enabled: true },
		radar_alert_enabled: false,
		send_telegram: true,
		send_sms: false,
		send_premium_sms: false,
		alert_cooldown_minutes: 30,
		alert_quiet_from: '22:00',
		alert_quiet_to: '07:00',
		corridors: [
			{ metric: 'wind_max_kmh', range: [0, 40], notify: true, mark: true },
			{ metric: 'snow_depth_cm', range: [30, 200], notify: false, mark: true }
		],
		display_config: {
			metric_alert_levels: { wind_max_kmh: 'standard', snow_depth_cm: 'sensibel' },
			ideal_ranges: { wind_max_kmh: { min: 0, max: 40 }, snow_depth_cm: { min: 30, max: 200 } },
			active_metrics: ['wind_max_kmh', 'snow_depth_cm', 'temp_max_c'],
			telegram_style: 'rich'
		},
		...overrides
	} as ComparePreset;
}

/** Echte SaveStatus-Instanz ohne Konstruktor (Runen-Felder, s. saveStatus.test.ts),
 *  MIT Kennung {typ:'vergleich', id} — sonst läuft `retryConflict()` leer. */
export function createController(id: string): SaveStatus {
	const inst = Object.create(SaveStatus.prototype) as SaveStatus;
	const f = inst as unknown as Record<string, unknown>;
	f.state = 'idle';
	f.savedAt = null;
	f.error = null;
	f._timer = null;
	f._pendingFn = null;
	f._inflight = null;
	f._lastFailed = null;
	f._unresolvedError = null;
	f._tripId = id;
	f._resourceKind = 'vergleich';
	return inst;
}

/** EIN Wizard-Zustand für den ganzen Hub (wie `wizardState` in CompareTabs):
 *  Alarme-Hydration UND Idealwerte-Hydration auf demselben Objekt. */
export function hydrierterWs(preset: ComparePreset): Record<string, unknown> {
	const ws: Record<string, unknown> = {};
	hydrateAlarmFieldsFromPreset(ws, preset, []);
	const h = hydrateHubFieldsFromPreset(preset, []);
	ws.isEditMode = h.isEditMode;
	ws.corridors = h.corridors;
	ws.activityProfile = h.activityProfile;
	ws.idealRanges = h.idealRanges;
	if (h.activeMetricKeys !== null) ws.activeMetricKeys = h.activeMetricKeys;
	ws.metricAlertLevels = h.metricAlertLevels;
	return ws;
}

const DEF_BASIS = { kind: 'range' as const, defaultMin: null, defaultMax: null, alarmCapable: true };
export const DEFS: CompareMetricDef[] = [
	{ ...DEF_BASIS, metric: 'wind_max_kmh', label: 'Wind', unit: 'km/h', scale: [0, 120], step: 1 },
	{ ...DEF_BASIS, metric: 'snow_depth_cm', label: 'Schneehöhe', unit: 'cm', scale: [0, 400], step: 5 },
	{ ...DEF_BASIS, metric: 'temp_max_c', label: 'Temperatur max', unit: '°C', scale: [-20, 40], step: 1 }
];

/**
 * Nachbau der Bedienlogik von CorridorEditor.svelte im `vergleich`-Kontext
 * OHNE Svelte: `patch()`/`remove()` ändern die Zeilen und spiegeln sie mit
 * derselben Funktion wie `syncToWizard()` in den Wizard-Zustand. Das Melden an
 * die Speicherung (`aenderungMelden()`) macht der Test selbst — genau diese
 * Delegation ist die Aufgabe von `maybeSchedule()` nach S3.
 */
export function wertebereicheBedienung(ws: Record<string, unknown>) {
	const pool = buildComparePool((ws.corridors as never) ?? [], DEFS);
	let rows: CorridorRowState[] = pool.rows;
	const unknownCorridors = pool.unknownCorridors;
	let removedMetrics: string[] = [];
	function syncToWizard(): void {
		const payload = buildCompareCorridorSavePayload(
			rows,
			removedMetrics,
			{
				idealRanges: ws.idealRanges as never,
				activeMetricKeys: materializeActiveMetricKeys((ws.activeMetricKeys as string[] | null) ?? null),
				metricAlertLevels: ws.metricAlertLevels as Record<string, SensLevel | undefined>
			},
			unknownCorridors
		);
		ws.corridors = payload.corridors;
		ws.idealRanges = payload.idealRanges;
		ws.activeMetricKeys = payload.activeMetricKeys;
		ws.metricAlertLevels = payload.metricAlertLevels;
	}
	return {
		patch(metric: string, p: Partial<Pick<CorridorRowState, 'min' | 'max' | 'notify' | 'mark'>>): void {
			rows = patchRow(rows, metric, p);
			syncToWizard();
		},
		remove(metric: string): void {
			rows = removeRow(rows, metric);
			removedMetrics = [...removedMetrics, metric];
			syncToWizard();
		}
	};
}

/** Korridor einer Metrik aus einem gespeicherten Rumpf. */
export function korridor(body: unknown, metric: string): { range: [number | null, number | null] } | undefined {
	const cs = ((body as Record<string, unknown>).corridors as Array<{ metric: string; range: [number | null, number | null] }>) ?? [];
	return cs.find((c) => c.metric === metric);
}
