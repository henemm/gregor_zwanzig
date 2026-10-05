// tripNewLogic.ts — Reine Logik fuer den progressiven Anlege-Flow.
// 1:1 gespiegelt aus TN_unlocked / TN_doneSet / TN_stageDate / TN_Progress
// (docs/design-requests/trip-anlegen-2026-06-06/screen-trip-new-v2.jsx).
// Keine Seiteneffekte, keine Svelte-Imports — testbar mit node:test.

import type { Trip, WeatherConfigMetric, ReportConfig, Waypoint, ActivityType, Corridor } from '$lib/types';
import {
	resolveAlertChannels,
	resolveAlertChannelThresholds,
	applyThresholdChange,
	type AlertChannelState,
	type AlertChannelThresholdState,
	type ChannelKind,
	type ChannelThreshold,
} from '../shared/alarme-tab/alertChannelState.ts';
import { tailUnlocked, tailDone, canFinish, progressCount as kernProgressCount, type TailIds } from '../shared/anlegeLockEngine.ts';
import { buildAlarmeDeliveryPayload } from '../shared/alarme-tab/alarmeDeliveryPayload.ts';

// ── TabId ────────────────────────────────────────────────────────────────────

export type TabId = 'route' | 'etappen' | 'wegpunkte' | 'wetter-metriken' | 'wertebereiche' | 'alarme' | 'versand';

// ── Freischalt-Logik (TN_unlocked) ──────────────────────────────────────────
// Issue #2277 S2a: neuer Parameter `wbVisited` (Wertebereiche besucht) an
// Position 5 — die Kette laeuft jetzt ueber Wetter-Metriken -> Wertebereiche
// -> Alarme -> Versand (geteilter Kern `shared/anlegeLockEngine.ts`, #2277 S4).

const TAIL: TailIds<TabId> = { metriken: 'wetter-metriken', wertebereiche: 'wertebereiche', alarme: 'alarme', versand: 'versand' };

export function unlockedTabs(
	name: string,
	startDate: string,
	etDone: boolean,
	wtVisited: boolean,
	wbVisited: boolean,
	alVisited: boolean,
	vsVisited: boolean
): Set<TabId> {
	const s = new Set<TabId>(['route']);
	if (name.trim() && startDate) s.add('etappen');
	if (etDone) s.add('wegpunkte');
	// Trip-Semantik (bit-gleich zu vorher): nur `metriken` haengt an etDone, die
	// uebrigen Schwanz-Reiter ausschliesslich an den Besuchs-Flags. Der Kern sperrt
	// bei fehlendem Vorderteil den ganzen Schwanz — daher mit metrikenFrei=true
	// aufrufen und `metriken` hier selbst an etDone binden.
	const tail = tailUnlocked(TAIL, {
		metrikenFrei: true, metrikenVisited: wtVisited, wertebereicheVisited: wbVisited,
		alarmeVisited: alVisited, versandVisited: vsVisited,
	});
	if (!etDone) tail.delete('wetter-metriken');
	for (const t of tail) s.add(t);
	return s;
}

// ── Done-Zustand (TN_doneSet) ────────────────────────────────────────────────

export function doneTabs(
	name: string,
	startDate: string,
	etDone: boolean,
	wtVisited: boolean,
	wbVisited: boolean,
	alVisited: boolean,
	vsVisited: boolean
): Set<TabId> {
	const s = new Set<TabId>();
	if (name.trim() && startDate) s.add('route');
	if (etDone) s.add('etappen');
	for (const t of tailDone(TAIL, {
		metrikenFrei: etDone, metrikenVisited: wtVisited, wertebereicheVisited: wbVisited,
		alarmeVisited: alVisited, versandVisited: vsVisited,
	})) s.add(t);
	return s;
}

// ── Etappen-Datum (TN_stageDate) ─────────────────────────────────────────────

export function stageDate(startDate: string, offset: number): string | null {
	if (!startDate) return null;
	try {
		// UTC, damit das Anzeige-Datum exakt zum ISO-Datum im POST-Payload passt
		// (addDaysISO nutzt ebenfalls UTC) — kein ±1-Tag-Drift in Extrem-Zeitzonen (Adversary F002).
		const d = new Date(startDate + 'T00:00:00Z');
		d.setUTCDate(d.getUTCDate() + offset);
		return `${String(d.getUTCDate()).padStart(2, '0')}.${String(d.getUTCMonth() + 1).padStart(2, '0')}.`;
	} catch (e) { return null; }
}

// ── Fortschrittsbalken (TN_Progress) ────────────────────────────────────────

export function progressCount(done: Set<TabId>): number {
	return kernProgressCount(done, ['route', 'etappen', 'wetter-metriken', 'versand']);
}

// ── Speichern-Gate ────────────────────────────────────────────────────────────

export function canSave(done: Set<TabId>): boolean {
	return canFinish(done, 'versand');
}

// ── State + Payload-Builder ──────────────────────────────────────────────────

export interface CreateTripStage {
	id: number;
	name: string;
	// Issue #658 — aus GPX berechnete (ggf. editierte) Wegpunkte je Etappe.
	// Optional, damit Slice-1-Aufrufer ohne Wegpunkte typkompatibel bleiben.
	waypoints?: Waypoint[];
	// Issue #675 — Startzeit je Etappe (HH:MM), nur setzen wenn vorhanden.
	start_time?: string;
}

export interface CreateTripChannels {
	email: boolean;
	telegram: boolean;
	sms: boolean;
}

export interface CreateTripState {
	name: string;
	region?: string;
	startDate: string;
	stages: CreateTripStage[];
	weatherMetrics?: WeatherConfigMetric[];
	channels: CreateTripChannels;
	reportConfig?: ReportConfig;
	// Issue #2277 S1 — Alarm-Schatten-State des geteilten AlarmeTab (createMode).
	alarm?: CreateTripAlarmState;
	// Issue #674 — Aktivitätstyp (Fahrrad/Wanderer) für Naismith-Berechnung.
	activity?: ActivityType;
	// Issue #2277 S2a — Wertebereiche-Schatten-State des geteilten CorridorEditor
	// (createMode, context="route"). `undefined` solange der Reiter nie eine
	// gültige Zeile gemeldet hat; buildCreateTripPayload() setzt trotzdem immer
	// `trip.corridors = state.corridors ?? []` (AC-6, kein `null` im POST-Body).
	corridors?: Corridor[];
}

// ── Alarm-Schatten-State (Issue #2277 S1) ────────────────────────────────────
// Gleicher Default + gleiche Deltalogik wie AlarmeTab.svelte intern (route-Zweig).

export interface CreateTripAlarmState {
	officialWarningsEnabled: boolean;
	cooldownMinutes?: number;
	quietFrom?: string;
	quietTo?: string;
	channels: AlertChannelState;
	channelThresholds: AlertChannelThresholdState;
	metricLevels: Record<string, string>;
}

export function initialCreateTripAlarmState(): CreateTripAlarmState {
	return {
		officialWarningsEnabled: false,
		cooldownMinutes: undefined,
		quietFrom: undefined,
		quietTo: undefined,
		channels: resolveAlertChannels(undefined),
		channelThresholds: resolveAlertChannelThresholds(undefined),
		metricLevels: {},
	};
}

export function applyAlarmChannelToggle(state: CreateTripAlarmState, kind: ChannelKind): CreateTripAlarmState {
	return { ...state, channels: { ...state.channels, [kind]: !state.channels[kind] } };
}

export function applyAlarmThresholdChange(
	state: CreateTripAlarmState,
	kind: ChannelKind,
	level: ChannelThreshold
): CreateTripAlarmState {
	return { ...state, channelThresholds: applyThresholdChange(state.channelThresholds, kind, level) };
}

export function applyAlarmMetricLevelChange(
	state: CreateTripAlarmState,
	metric: string,
	level: string
): CreateTripAlarmState {
	return { ...state, metricLevels: { ...state.metricLevels, [metric]: level } };
}

function newId(): string {
	return crypto.randomUUID().slice(0, 8);
}

function addDaysISO(iso: string, days: number): string {
	const [y, m, d] = iso.split('-').map(Number);
	const dt = new Date(Date.UTC(y, m - 1, d));
	dt.setUTCDate(dt.getUTCDate() + days);
	const yy = dt.getUTCFullYear();
	const mm = String(dt.getUTCMonth() + 1).padStart(2, '0');
	const dd = String(dt.getUTCDate()).padStart(2, '0');
	return `${yy}-${mm}-${dd}`;
}

export function buildCreateTripPayload(state: CreateTripState): Trip {
	const trip: Trip = {
		id: newId(),
		name: state.name,
		stages: state.stages.map((s, idx) => ({
			id: newId(),
			name: s.name,
			date: addDaysISO(state.startDate, idx),
			// Issue #658 — GPX-Wegpunkte (ggf. editiert) persistieren statt verwerfen.
			waypoints: s.waypoints ?? [],
			// Issue #675 — Startzeit nur wenn explizit gesetzt (kein leerer String).
			...(s.start_time ? { start_time: s.start_time } : {}),
		})),
	};

	if (state.region && state.region.trim().length > 0) {
		trip.region = state.region.trim();
	}

	// Issue #674 — Aktivitätstyp persistieren (Fahrrad/Wanderer).
	if (state.activity) {
		trip.activity = state.activity;
	}

	// display_config: metriken + kanäle (channels als extra-Feld, additiv)
	trip.display_config = {
		channels: state.channels,
		metrics: state.weatherMetrics ?? [],
	} as unknown as Trip['display_config'];

	if (state.reportConfig) {
		trip.report_config = state.reportConfig;
	}

	// Issue #2277 S2a (AC-6) — immer gesetzt, nie undefined im POST-Body: ein
	// frisch angelegter Trip ohne Wertebereiche-Interaktion liefert per GET
	// "corridors": [], nie null.
	trip.corridors = state.corridors ?? [];

	// Issue #2277 S1 — Alarm-Felder additiv mergen: Read-Modify-Write auf dem
	// bereits gebauten display_config (channels/metrics bleiben erhalten).
	const alarm = state.alarm ?? initialCreateTripAlarmState();
	const bisherigeDc = trip.display_config as Record<string, unknown> | undefined;
	const alarmPayload = buildAlarmeDeliveryPayload({
		officialWarningsEnabled: alarm.officialWarningsEnabled,
		cooldownMinutes: alarm.cooldownMinutes,
		quietFrom: alarm.quietFrom,
		quietTo: alarm.quietTo,
		channels: alarm.channels,
		channelThresholds: alarm.channelThresholds,
		metricLevels: alarm.metricLevels,
	}) as Record<string, unknown>;
	Object.assign(trip, alarmPayload);
	// Neuanlage (POST): der Alarm-Teilfeld-Rumpf traegt nur `metric_alert_levels`;
	// channels/metrics des frisch gebauten display_config bleiben erhalten.
	if (alarmPayload.display_config) {
		trip.display_config = { ...(bisherigeDc ?? {}), ...(alarmPayload.display_config as object) };
	}

	return trip;
}
