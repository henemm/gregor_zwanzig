package model

// SegmentWeatherSummary holds aggregated weather metrics for a trip segment.
type SegmentWeatherSummary struct {
	TempMinC        *float64     `json:"temp_min_c,omitempty"`
	TempMaxC        *float64     `json:"temp_max_c,omitempty"`
	TempAvgC        *float64     `json:"temp_avg_c,omitempty"`
	WindMaxKmh      *float64     `json:"wind_max_kmh,omitempty"`
	GustMaxKmh      *float64     `json:"gust_max_kmh,omitempty"`
	PrecipSumMm     *float64     `json:"precip_sum_mm,omitempty"`
	CloudAvgPct     *int         `json:"cloud_avg_pct,omitempty"`
	HumidityAvgPct  *int         `json:"humidity_avg_pct,omitempty"`
	ThunderLevelMax ThunderLevel `json:"thunder_level_max,omitempty"`
	VisibilityMinM  *float64     `json:"visibility_min_m,omitempty"`
	WindChillMinC   *float64     `json:"wind_chill_min_c,omitempty"`
	PopMaxPct       *int         `json:"pop_max_pct,omitempty"`
	CapeMaxJkg      *float64     `json:"cape_max_jkg,omitempty"`
	PressureAvgHpa  *float64     `json:"pressure_avg_hpa,omitempty"`
	DewpointAvgC    *float64     `json:"dewpoint_avg_c,omitempty"`
	UvIndexMax      *float64     `json:"uv_index_max,omitempty"`
	SnowNewSumCm    *float64     `json:"snow_new_sum_cm,omitempty"`
}
