// Issue #386 — Startseite-Cockpit: page-lokale Pure-Function-Helfer.
// Spec: docs/specs/modules/screen_home_migration.md
//
// Reine Funktionen (seiteneffektfrei) für die Hero-/Briefing-/Archiv-Ableitung.
// Keine Mocks, kein Render — gegen echte Trip/Stage/ReportConfig-DTO-Form.

import type { Trip, Stage, ReportConfig, StageWeatherResult, BriefingLogEntry } from '$lib/types';
// Relative Wert-Importe (statt $lib-Alias), damit die reinen Helfer auch unter
// dem Node-Test-Runner (`node --test --experimental-strip-types`) auflösbar
// bleiben. Vite löst $lib-Alias und relativen Pfad zur Laufzeit identisch auf.
import { computeHeaderStats } from '../../lib/components/email-preview/headerStats.ts';
import { tripStatus } from '../../lib/utils/tripStatus.ts';

/** Höhen-Array (number[]) einer Etappe für ElevSparkline. Leer wenn keine Wegpunkte. */
export function stageProfile(stage: Stage | null | undefined): number[] {
	return (stage?.waypoints ?? [])
		.map((w) => w.elevation_m)
		.filter((e): e is number => Number.isFinite(e));
}

/** Zeitfenster "HH:MM – HH:MM" aus erstem/letztem Wegpunkt; leer wenn unbekannt. */
export function stageWindow(stage: Stage | null | undefined): string {
	const wps = stage?.waypoints ?? [];
	const first = wps[0]?.time_window ?? wps[0]?.arrival_calculated ?? stage?.start_time ?? '';
	const last = wps.length > 1 ? (wps[wps.length - 1]?.arrival_calculated ?? '') : '';
	if (first && last) return `${first} – ${last}`;
	return first || '';
}

export interface StageStatLine {
	km: number;
	ascent: number;
	descent: number;
	maxElev: number;
}

/** km/↑/↓/max einer Etappe (gerundet via headerStats). */
export function stageStats(stage: Stage | null | undefined): StageStatLine {
	const s = computeHeaderStats(stage);
	return {
		km: Math.round(s.distanceKm * 10) / 10,
		ascent: s.ascentM,
		descent: s.descentM,
		maxElev: s.maxElevationM
	};
}

export type StageStripState = 'done' | 'active' | 'future';

/**
 * Zustand einer Etappe im Hero-Etappen-Streifen (strikt datumsbasiert, AC-4).
 *   - `todayIdx < 0` (Hero ist "Nächste Tour", keine Etappe ist heute) →
 *     ALLE Etappen liegen in der Zukunft → immer 'future'.
 *   - sonst: i < todayIdx → 'done', i === todayIdx → 'active', i > todayIdx → 'future'.
 *
 * 'active' bedeutet ausschließlich "läuft heute" — bei geplanten Touren darf
 * daher keine Etappe 'active' sein (Fix Adversary-Finding F001, Issue #386).
 */
export function stageStripState(todayIdx: number, i: number): StageStripState {
	if (todayIdx < 0) return 'future';
	if (i < todayIdx) return 'done';
	if (i === todayIdx) return 'active';
	return 'future';
}

export type RiskPillTone = 'good' | 'warn' | 'bad';

/** Risk-Stufe (green/yellow/red) → Pill-Tone; null wenn kein Wetter. */
export function riskTone(weather: StageWeatherResult | null | undefined): RiskPillTone | null {
	if (weather?.risk === 'green') return 'good';
	if (weather?.risk === 'yellow') return 'warn';
	if (weather?.risk === 'red') return 'bad';
	return null;
}

/** Kompakter Wetter-Summary-Text aus weather_summary; leer wenn nichts da. */
export function weatherSummary(weather: StageWeatherResult | null | undefined): string {
	const ws = weather?.weather_summary;
	if (!ws) return '';
	const parts: string[] = [];
	if (ws.temp_min_c != null && ws.temp_max_c != null) {
		parts.push(`${Math.round(ws.temp_min_c)}–${Math.round(ws.temp_max_c)} °C`);
	}
	if (ws.wind_max_kmh != null) parts.push(`Wind ${Math.round(ws.wind_max_kmh)} km/h`);
	if (ws.precip_mm != null && ws.precip_mm > 0) parts.push(`${ws.precip_mm.toFixed(1)} mm`);
	return parts.join(' · ');
}

export interface BriefingReport {
	when: string;
	kind: string;
	channels: string[];
	status: 'planned' | 'sent';
	etappe?: string;
}

/** Aktive Kanäle aus report_config (email/signal/telegram/sms). */
export function reportChannels(rc: ReportConfig | undefined): string[] {
	const out: string[] = [];
	if (rc?.send_email) out.push('email');
	if (rc?.send_signal) out.push('signal');
	if (rc?.send_telegram) out.push('telegram');
	if (rc?.send_sms) out.push('sms');
	return out;
}

/**
 * Geplante Briefings aus report_config → BriefingTimelineRow-Eingabe.
 *
 * Issue #393: optionaler `sentLog` (heutige Briefing-Versand-Einträge) markiert
 * Rows als 'sent', wenn ein passender Eintrag (gleicher tripId + kind + heutiges
 * Datum) existiert; sonst 'planned'. Ohne sentLog/tripId bleibt alles 'planned'
 * (backward-compatible).
 */
export function plannedBriefings(
	rc: ReportConfig | undefined,
	sentLog?: BriefingLogEntry[],
	tripId?: string
): BriefingReport[] {
	if (!rc) return [];
	const channels = reportChannels(rc);
	const todayPrefix = new Date().toISOString().slice(0, 10);

	const isSent = (kind: string): boolean => {
		if (!sentLog || !tripId) return false;
		return sentLog.some(
			(e) => e.trip_id === tripId && e.kind === kind && e.sent_at.startsWith(todayPrefix)
		);
	};

	const rows: BriefingReport[] = [];
	if (rc.morning_enabled) {
		rows.push({
			when: (rc.morning_time || '07:00').slice(0, 5),
			kind: 'morgen',
			channels,
			status: isSent('morning') ? 'sent' : 'planned'
		});
	}
	if (rc.evening_enabled) {
		rows.push({
			when: (rc.evening_time || '18:00').slice(0, 5),
			kind: 'abend',
			channels,
			status: isSent('evening') ? 'sent' : 'planned'
		});
	}
	return rows;
}

export interface ArchiveCard {
	id: string;
	name: string;
	dates: string;
	stages: number;
}

const MONTHS_DE = ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez'];

function shortRange(trip: Trip): string {
	const dates = (trip.stages ?? [])
		.map((s) => s.date)
		.filter((d): d is string => !!d)
		.map((d) => d.slice(0, 10))
		.sort();
	if (dates.length === 0) return '';
	const fmt = (iso: string) => {
		const [y, m] = iso.split('-').map(Number);
		return `${MONTHS_DE[(m ?? 1) - 1]} ${y}`;
	};
	return dates.length === 1 || fmt(dates[0]) === fmt(dates[dates.length - 1])
		? fmt(dates[0])
		: `${fmt(dates[0])} – ${fmt(dates[dates.length - 1])}`;
}

/**
 * Abgeschlossene/archivierte Touren (Status 'fertig'), bis zu `limit`.
 * Hero-Tour ist per Definition nie 'fertig', daher keine Sonderbehandlung nötig.
 */
export function archivedTrips(trips: Trip[], now: Date = new Date(), limit = 4): ArchiveCard[] {
	return (trips ?? [])
		.filter((t) => tripStatus(t, now) === 'fertig')
		.slice(0, limit)
		.map((t) => ({
			id: t.id,
			name: t.name,
			dates: shortRange(t),
			stages: t.stages?.length ?? 0
		}));
}
