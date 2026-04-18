export interface Location {
	id: string;
	name: string;
	lat: number;
	lon: number;
	elevation_m?: number;
	region?: string;
	bergfex_slug?: string;
	activity_profile?: 'wintersport' | 'wandern' | 'allgemein';
	group?: string;
	display_config?: Record<string, unknown>;
}

export interface Waypoint {
	id: string;
	name: string;
	lat: number;
	lon: number;
	elevation_m: number;
	time_window?: string;
}

export interface Stage {
	id: string;
	name: string;
	date: string;
	waypoints: Waypoint[];
	start_time?: string;
}

export interface Trip {
	id: string;
	name: string;
	stages: Stage[];
	avalanche_regions?: string[];
	aggregation?: Record<string, unknown>;
	weather_config?: Record<string, unknown>;
	display_config?: Record<string, unknown>;
	report_config?: Record<string, unknown>;
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
	activity_profile?: 'wintersport' | 'wandern' | 'allgemein';
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
