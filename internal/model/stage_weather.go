package model

// StageWeatherSummary — kompaktes Subset aus SegmentWeatherSummary für die
// API-Response GET /api/trips/{id}/stages/weather (Issue #203).
type StageWeatherSummary struct {
	TempMinC   *float64 `json:"temp_min_c"`
	TempMaxC   *float64 `json:"temp_max_c"`
	WindMaxKmh *float64 `json:"wind_max_kmh"`
	PrecipMm   *float64 `json:"precip_mm"`
	WmoCode    *int     `json:"wmo_code"`
	IsDay      *int     `json:"is_day"`
}

// StageWeatherResult — Weather + Risk für eine Stage.
type StageWeatherResult struct {
	WeatherSummary *StageWeatherSummary `json:"weather_summary"`
	// Risk: "green" | "yellow" | "red" — null wenn kein Forecast verfügbar.
	Risk *string `json:"risk"`
}

// StagesWeatherResponse — Response-DTO für GET /api/trips/{id}/stages/weather.
// Map-Key ist die Stage-ID.
type StagesWeatherResponse struct {
	Results map[string]*StageWeatherResult `json:"results"`
}
