// tripNewLogic.ts — Reine Logik fuer den progressiven Anlege-Flow.
// 1:1 gespiegelt aus TN_unlocked / TN_doneSet / TN_stageDate / TN_Progress
// (docs/design-requests/trip-anlegen-2026-06-06/screen-trip-new-v2.jsx).
// Keine Seiteneffekte, keine Svelte-Imports — testbar mit node:test.

import type { Trip, WeatherConfigMetric, ReportConfig, AlertRule } from '$lib/types';

// ── TabId ────────────────────────────────────────────────────────────────────

export type TabId = 'route' | 'etappen' | 'wegpunkte' | 'metriken' | 'zeitplan' | 'alerts';

// ── Freischalt-Logik (TN_unlocked) ──────────────────────────────────────────

export function unlockedTabs(
	name: string,
	startDate: string,
	etDone: boolean,
	wtVisited: boolean,
	ztVisited: boolean
): Set<TabId> {
	const s = new Set<TabId>(['route']);
	if (name.trim() && startDate) s.add('etappen');
	if (etDone) { s.add('wegpunkte'); s.add('metriken'); }
	if (wtVisited) s.add('zeitplan');
	if (ztVisited) s.add('alerts');
	return s;
}

// ── Done-Zustand (TN_doneSet) ────────────────────────────────────────────────

export function doneTabs(
	name: string,
	startDate: string,
	etDone: boolean,
	wtVisited: boolean,
	ztVisited: boolean
): Set<TabId> {
	const s = new Set<TabId>();
	if (name.trim() && startDate) s.add('route');
	if (etDone) s.add('etappen');
	if (wtVisited) s.add('metriken');
	if (ztVisited) s.add('zeitplan');
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
	const steps: TabId[] = ['route', 'etappen', 'metriken', 'zeitplan'];
	return steps.filter(s => done.has(s)).length;
}

// ── Speichern-Gate ────────────────────────────────────────────────────────────

export function canSave(done: Set<TabId>): boolean {
	return done.has('zeitplan');
}

// ── State + Payload-Builder ──────────────────────────────────────────────────

export interface CreateTripStage {
	id: number;
	name: string;
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
	alertRules?: AlertRule[];
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
			waypoints: [],
		})),
	};

	if (state.region && state.region.trim().length > 0) {
		trip.region = state.region.trim();
	}

	// display_config: metriken + kanäle (channels als extra-Feld, additiv)
	trip.display_config = {
		channels: state.channels,
		metrics: state.weatherMetrics ?? [],
	} as unknown as Trip['display_config'];

	if (state.reportConfig) {
		trip.report_config = state.reportConfig;
	}

	if (state.alertRules && state.alertRules.length > 0) {
		trip.alert_rules = state.alertRules;
	}

	return trip;
}
