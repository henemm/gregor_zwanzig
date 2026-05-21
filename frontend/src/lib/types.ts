export interface Location {
	id: string;
	name: string;
	lat: number;
	lon: number;
	elevation_m?: number;
	region?: string;
	bergfex_slug?: string;
	activity_profile?: ActivityProfile;
	group?: string;
	display_config?: Record<string, unknown>;
	timezone?: string;
	data_source?: string;
	created_at?: string;
}

export type ActivityType = 'trekking' | 'skitour' | 'hochtour' | 'klettersteig' | 'mtb';

export interface Waypoint {
	id: string;
	name: string;
	lat: number;
	lon: number;
	elevation_m: number;
	time_window?: string;
	suggested?: boolean;
}

export interface Stage {
	id: string;
	name: string;
	date: string;
	waypoints: Waypoint[];
	start_time?: string;
	/**
	 * Transientes Wizard-Flag (Step 2 / Sub-Spec #162):
	 * `true` wenn der User das Datum manuell ueberschrieben hat — Auto-Datierung
	 * (recomputeStageDates) laesst dieses Stage in Ruhe. Wird beim Save (Step 4)
	 * via `toTripPayload()` gestrippt — analog `Waypoint.suggested`.
	 */
	dateOverridden?: boolean;
}

// Alert Rules (Issue #205) — typisierte Alarm-Regeln pro Trip
export type AlertRuleKind = 'absolute' | 'delta';
export type AlertSeverity = 'info' | 'warning' | 'critical';
export type AlertMetric =
	| 'wind_gust'
	| 'precipitation_sum'
	| 'temperature_min'
	| 'temperature_max'
	| 'thunder_level'
	| 'snow_line'
	| 'temperature_change'
	| 'wind_change'
	| 'precipitation_change';

export interface AlertRule {
	id: string;
	kind: AlertRuleKind;
	metric: AlertMetric;
	threshold: number;
	unit?: string;
	severity: AlertSeverity;
	enabled: boolean;
	// Issue #297 — Paar-Markierung für mode='both' (gemeinsame UUID).
	pair_id?: string;
	// Issue #297 — Zeitfenster für delta-Rules ('1h' | '3h' | '6h' | '12h' | '24h').
	delta_window?: string;
}

// Issue #207 — Strukturiertes Typing fuer drei Trip-Konfigurationsfelder.
// Spec: docs/specs/modules/issue_207_strukturiertes_typing.md
// Nur Felder, die im Code aktuell gelesen/geschrieben werden — keine Toten-Felder.
export type ActivityProfile = 'wintersport' | 'wandern' | 'allgemein' | 'summer_trekking';

export const ACTIVITY_PROFILE_OPTIONS = [
	{ value: 'allgemein',       label: 'Allgemein' },
	{ value: 'wintersport',     label: 'Wintersport' },
	{ value: 'wandern',         label: 'Wandern' },
	{ value: 'summer_trekking', label: 'Sommer-Trekking' },
] as const satisfies ReadonlyArray<{ value: ActivityProfile; label: string }>;

// Exhaustiveness-Check: wenn jemand ActivityProfile erweitert ohne
// ACTIVITY_PROFILE_OPTIONS zu pflegen, bricht hier der Compiler.
type _ActivityProfileOptionsCoverage =
	ActivityProfile extends (typeof ACTIVITY_PROFILE_OPTIONS)[number]['value'] ? true : never;
const _activityProfileCoverageCheck: _ActivityProfileOptionsCoverage = true;
void _activityProfileCoverageCheck;

export interface Aggregation {
	profile?: ActivityProfile;
}

export interface WeatherConfigMetric {
	metric_id: string;
	enabled: boolean;
	use_friendly_format?: boolean;
}

export interface WeatherConfig {
	metrics?: WeatherConfigMetric[];
}

export interface ReportConfig {
	enabled?: boolean;
	morning_enabled?: boolean;
	evening_enabled?: boolean;
	morning_time?: string;
	evening_time?: string;
	send_email?: boolean;
	send_signal?: boolean;
	send_telegram?: boolean;
	send_sms?: boolean;
	alert_on_changes?: boolean;
	change_threshold_temp_c?: number;
	change_threshold_wind_kmh?: number;
	change_threshold_precip_mm?: number;
	show_compact_summary?: boolean;
	show_daylight?: boolean;
	wind_exposition_min_elevation_m?: number | null;
	multi_day_trend_morning?: boolean;
	multi_day_trend_evening?: boolean;
	multi_day_trend_reports?: string[];
}

export interface DisplayConfig {
	preset_name?: string;
	metrics?: WeatherConfigMetric[];
}

// Epic #138 Issue #177 — User-definierte Metric-Presets (Server-seitig persistiert).
export interface MetricPreset {
	id: string;
	name: string;
	description?: string;
	is_default: boolean;
	metrics: string[];
	friendly_ids: string[];
	created_at: string;
}

export interface Trip {
	id: string;
	name: string;
	shortcode?: string;
	activity?: ActivityType;
	region?: string;
	stages: Stage[];
	avalanche_regions?: string[];
	aggregation?: Aggregation;
	weather_config?: WeatherConfig;
	display_config?: DisplayConfig;
	report_config?: ReportConfig;
	alert_rules?: AlertRule[];
	alert_cooldown_minutes?: number;
	alert_quiet_from?: string;
	alert_quiet_to?: string;
	paused_at?: string;
	archived_at?: string;
}

export interface Subscription {
	id: string;
	name: string;
	enabled: boolean;
	locations: string[];
	forecast_hours: number;
	time_window_start: number;
	time_window_end: number;
	schedule: 'daily_morning' | 'daily_evening' | 'weekly';
	weekday: number;
	include_hourly: boolean;
	top_n: number;
	send_email: boolean;
	send_signal: boolean;
	send_telegram: boolean;
	display_config?: Record<string, unknown>;
	activity_profile?: ActivityProfile;
	// Issue #252 — per-Subscription Empfaenger + Lauf-Status (additiv)
	recipients?: string[];
	last_run?: string;     // ISO-8601
	last_status?: string;  // "ok" | "error"
}

export interface HealthResponse {
	status: 'ok' | 'degraded';
	version: string;
	python_core: 'ok' | 'unavailable';
}

export interface ApiError {
	error: string;
	detail?: string;
}

export type ThunderLevel = 'NONE' | 'MED' | 'HIGH';

export interface ForecastDataPoint {
	ts: string;
	t2m_c?: number | null;
	wind10m_kmh?: number | null;
	wind_direction_deg?: number | null;
	gust_kmh?: number | null;
	precip_1h_mm?: number | null;
	cloud_total_pct?: number | null;
	wmo_code?: number | null;
	thunder_level?: ThunderLevel | null;
	visibility_m?: number | null;
	wind_chill_c?: number | null;
	humidity_pct?: number | null;
	pop_pct?: number | null;
	is_day?: number | null;
	dni_wm2?: number | null;
	uv_index?: number | null;
	snow_depth_cm?: number | null;
	snow_new_24h_cm?: number | null;
	freezing_level_m?: number | null;
}

// Issue #251 — Compare-Engine (POST /api/compare/run) DTOs.
// Spec: docs/specs/modules/issue_251_compare_main_stage.md
export interface CompareMetrics {
	temp_min_c?: number | null;
	temp_max_c?: number | null;
	wind_max_kmh?: number | null;
	gust_max_kmh?: number | null;
	precip_sum_mm?: number | null;
	cloud_avg_pct?: number | null;
	visibility_min_m?: number | null;
	wind_chill_min_c?: number | null;
	uv_index_max?: number | null;
	dni_avg_wm2?: number | null;
	snow_depth_cm?: number | null;
	snow_new_sum_cm?: number | null;
	thunder_level_max?: string | null; // 'NONE' | 'MED' | 'HIGH'
}

export interface CompareRow {
	location_id: string;
	score: number; // 0–100
	rank: number;  // 1 = bester
	metrics: CompareMetrics;
}

export interface CompareWinner {
	location_id: string;
	tags: string[];
}

export interface CompareResult {
	rows: CompareRow[];
	winner?: CompareWinner;
	hourly: Record<string, ForecastDataPoint[]>;
}

// Adapter: System-Namespace ActivityProfile → Go-Engine-Namespace.
// Ausschliesslich an der API-Call-Site (+page.svelte::runComparison) zu verwenden.
export function toCompareProfile(profile: ActivityProfile): string {
	switch (profile) {
		case 'wintersport':     return 'WINTERSPORT';
		case 'wandern':         return 'ALPINE_TOURING';
		case 'summer_trekking': return 'SUMMER_TREKKING';
		case 'allgemein':       return 'ALLGEMEIN';
	}
}

export interface ForecastMeta {
	provider: string;
	model: string;
	grid_res_km: number;
}

export interface ForecastResponse {
	timezone: string;
	meta: ForecastMeta;
	data: ForecastDataPoint[];
}

export interface SchedulerJob {
	id: string;
	name: string;
	next_run: string | null;
	last_run: { time: string; status: 'ok' | 'error'; error?: string } | null;
}

export interface SchedulerStatus {
	running: boolean;
	timezone: string;
	jobs: SchedulerJob[];
}

// Issue #203 — Stage-Weather + Risk DTOs für GET /api/trips/{id}/stages/weather.
export interface StageWeatherSummary {
	temp_min_c?: number | null;
	temp_max_c?: number | null;
	wind_max_kmh?: number | null;
	precip_mm?: number | null;
	wmo_code?: number | null;
	is_day?: number | null;
}

export interface StageWeatherResult {
	weather_summary: StageWeatherSummary | null;
	risk: 'green' | 'yellow' | 'red' | null;
}

export interface StagesWeatherResponse {
	results: Record<string, StageWeatherResult | null>;
}
