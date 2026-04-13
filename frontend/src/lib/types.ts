export interface Location {
	id: string;
	name: string;
	lat: number;
	lon: number;
	elevation_m?: number;
	region?: string;
	bergfex_slug?: string;
	activity_profile?: 'wintersport' | 'wandern' | 'allgemein';
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

export interface HealthResponse {
	status: 'ok' | 'degraded';
	version: string;
	python_core: 'ok' | 'unavailable';
}

export interface ApiError {
	error: string;
	detail?: string;
}
