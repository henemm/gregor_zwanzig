export interface Location {
	id: string;
	name: string;
	lat: number;
	lon: number;
	elevation_m?: number;
	region?: string;
	bergfex_slug?: string;
	activity_profile?: ActivityProfile;
	group?: string;      // Legacy-Freitext — bleibt erhalten, wird nicht mehr gelesen
	group_id?: string;   // Issue #301 — Source of Truth (FK auf Group-Entity)
	display_config?: Record<string, unknown>;
	timezone?: string;
	data_source?: string;
	created_at?: string;
}

// Issue #301 — Group-Entity (Spiegel von internal/model/group.go).
// Source of Truth fuer Gruppen kommt aus GET /api/groups (sortiert nach order).
export interface Group {
	id: string;
	name: string;
	default_profile?: ActivityProfile; // kanonisch (Unterstrich): 'wintersport' | 'wandern' | 'summer_trekking' | 'allgemein'
	order: number;
}

export type ActivityType = 'trekking' | 'skitour' | 'hochtour' | 'klettersteig' | 'mtb';

export interface Waypoint {
	id: string;
	name: string;
	lat: number;
	lon: number;
	elevation_m: number;
	time_window?: string;
	// Issue #296 — vom Backend (Naismith) persistierte Ankunftszeit "HH:MM".
	// Editor zeigt clientseitig live (computeArrivalTimes), BE ist authoritative.
	arrival_calculated?: string;
	// Issue #303 — algorithmische Wegpunktvorschläge + User-Override.
	origin?: string;              // 'manual' | 'algorithmic'
	confirmed?: boolean;          // true = vom User bestätigt
	arrival_override?: string;    // User-Override "HH:MM"
	// Issue #585 — Wegpunkt-Typ (Gipfel, Pass, Hütte, etc.)
	type?: string;                // 'start' | 'end' | 'summit' | 'pass' | 'valley' | 'hut'
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
	 * via `toTripPayload()` gestrippt.
	 */
	dateOverridden?: boolean;
	// Issue #585 — Etappen-Code (z.B. "GR20-N01") und Standort für Pausentage
	code?: string;
	location?: string;
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

// Issue #343 — Pro-Metrik-Zeithorizont (Backend live aus #342).
// Default beim Load fehlender Felder ist {true,true,true}.
export type Horizons = {
	today: boolean;
	tomorrow: boolean;
	day_after: boolean;
};

export const HORIZONS_ALL: Horizons = {
	today: true,
	tomorrow: true,
	day_after: true,
};

// Issue #435 — kanonische Frontend-Repräsentation eines Metrik-Eintrags
// aus GET /api/catalog/metrics. Single Source of Truth (Adversary F002).
// Frühere lokale Duplikate in metricsEditor.ts und WeatherConfigDialog.svelte
// wurden durch Import dieses Typs ersetzt.
export interface MetricEntry {
	id: string;
	label: string;
	unit: string;
	category: string;
	default_enabled: boolean;
	has_friendly_format: boolean;
	/** Issue #435: erlaubte Format-Modi pro Metrik (raw/scale/simplified/symbol). */
	format_modes?: string[];
	/** Issue #435: Default-Format-Modus dieser Metrik. */
	default_format_mode?: string;
}

export interface WeatherConfigMetric {
	metric_id: string;
	enabled: boolean;
	/** @deprecated Issue #435 — bleibt als Backward-Compat; siehe `format_mode`. */
	use_friendly_format?: boolean;
	/** Issue #435: explicit format mode. Werte: 'raw' | 'scale' | 'simplified' | 'symbol'. */
	format_mode?: string;
	horizons?: Horizons; // Issue #343 — optional; defaultet HORIZONS_ALL beim Load
	// Issue #364 — Bucket-Editor: Spalten/Detail-Zuordnung + Reihenfolge.
	// Reisen additiv durch die Go-API (DisplayConfig = map[string]interface{})
	// und werden vom Python-Loader (#360) gelesen.
	bucket?: 'primary' | 'secondary';
	order?: number;
	score_member?: boolean;
	/** Issue #624: Konfigurierter Schwellwert für SMS-/Telegram-Kurzform (erste-Überschreitung). */
	sms_threshold?: number;
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
	// Issue #619 — E-Mail-Elemente abschaltbar (Backend seit #621 live)
	show_stage_stats?: boolean;
	show_quick_take_tags?: boolean;
	show_stability?: boolean;
	show_highlights?: boolean;
	daily_summary_metrics?: string[];
	// Issue #664 — Metriken-Überblick (ersetzt Quick-Take + Tages-Summe)
	show_metrics_summary?: boolean;
}

// Issue #429 — kanal-spezifische Layout-Listen (snake_case auf der Wire).
// Backend persistiert pro Kanal eine eigene WeatherConfigMetric[]; bei
// fehlendem Kanal-Eintrag fällt das Rendering auf DisplayConfig.metrics zurück.
export interface ChannelLayouts {
	email?: WeatherConfigMetric[];
	telegram?: WeatherConfigMetric[];
	sms?: WeatherConfigMetric[];
}

// Issue #434 — per-report-Overrides (Abend ≠ Morgen, snake_case auf der Wire).
export interface ChannelLayoutsPerReport {
	morning?: ChannelLayouts;
	evening?: ChannelLayouts;
}

export interface DisplayConfig {
	preset_name?: string;
	metrics?: WeatherConfigMetric[];
	channel_layouts?: ChannelLayouts; // Issue #429
	channel_layouts_per_report?: ChannelLayoutsPerReport; // Issue #434
	telegram_kurzform?: boolean; // Issue #614: SMS-Kurzform als Tages-Max-Anhang
}

// Epic #138 Issue #177 — User-definierte Metric-Presets (Server-seitig persistiert).
// Issue #342 / #343 — Schema-Migration: `metrics` ist jetzt eine Liste von
// DisplayMetric-Objekten ({metric_id, enabled, use_friendly_format, horizons?})
// statt zweier paralleler String-Arrays (metrics + friendly_ids).
// Backend hat Compat-Layer (siehe internal/store/store.go::LoadMetricPresets).
export interface MetricPresetMetric {
	metric_id: string;
	enabled: boolean;
	use_friendly_format: boolean;
	horizons?: Horizons;
}

export interface MetricPreset {
	id: string;
	name: string;
	description?: string;
	is_default: boolean;
	metrics: MetricPresetMetric[];
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
	send_telegram: boolean;
	display_config?: Record<string, unknown>;
	activity_profile?: ActivityProfile;
	// Issue #252 — per-Subscription Empfaenger + Lauf-Status (additiv)
	recipients?: string[];
	last_run?: string;     // ISO-8601
	last_status?: string;  // "ok" | "error"
	// Issue #456 — Top-Ort des letzten Versands (additiv)
	top_ort_letzter_versand?: string;
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

// Issue #251/#454/455 — Compare-Engine (POST /api/compare/run) DTOs.
// Issue #454 änderte Response-Schema: ranking/matrix/stunden_verlauf.
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
	sunny_hours_h?: number | null;
	snow_depth_cm?: number | null;
	snow_new_sum_cm?: number | null;
	thunder_level_max?: string | null;
}

export interface CompareRow {
	location_id: string;
	score: number;
	rank: number;
	metrics: CompareMetrics;
}

export interface CompareTag {
	type: string;
	label: string;
}

export interface RankingEntry {
	location_id: string;
	name: string;
	score: number;
	tags: CompareTag[];
}

export interface MatrixEntry {
	location_id: string;
	metrics: Record<string, unknown>;
}

export interface StundenVerlaufHour {
	hour: string;
	values: Record<string, unknown>;
}

export interface StundenVerlaufEntry {
	location_id: string;
	hours: StundenVerlaufHour[];
}

export interface CompareResult {
	ranking: RankingEntry[];
	matrix: MatrixEntry[];
	stunden_verlauf: StundenVerlaufEntry[];
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

// Issue #393 — Cockpit-Kacheln: Versandstatus + Alarm-Historie.
export interface BriefingLogEntry {
	trip_id: string;
	kind: 'morning' | 'evening';
	sent_at: string;
	channels: string[];
}

export interface AlertLogEntry {
	trip_id: string;
	sent_at: string;
	changes_count: number;
	severity: 'LOW' | 'MODERATE' | 'HIGH';
}

export interface CockpitStatus {
	briefings: BriefingLogEntry[];
	alerts: AlertLogEntry[];
}

// Issue #459 — Auto-Briefings Sidepanel.
// Spec: docs/specs/modules/issue_459_auto_briefings_sidepanel.md
// Spiegelt das von #458 bereitgestellte ComparePreset (GET /api/compare/presets).
export interface ComparePreset {
	id: string;
	name: string;
	location_ids: string[];
	schedule: 'daily' | 'weekly' | 'manual';
	previous_schedule?: string;         // #631: konserviert Rhythmus über Pause hinweg
	weekday?: number;  // 0=Montag … 6=Sonntag; nur relevant wenn schedule='weekly'
	profil: ActivityProfile;
	hour_from: number;
	hour_to: number;
	empfaenger: string[];
	letzter_versand?: string;           // ISO-8601
	top_ort_letzter_versand?: string | null;
	created_at: string;
	archived_at?: string;               // Issue #611 — gesetzt = archiviert
	display_config?: Record<string, unknown>;  // ideal_ranges, channel_layouts, region
}
