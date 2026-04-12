package model

type Waypoint struct {
	ID         string  `json:"id"`
	Name       string  `json:"name"`
	Lat        float64 `json:"lat"`
	Lon        float64 `json:"lon"`
	ElevationM int     `json:"elevation_m"`
	TimeWindow *string `json:"time_window,omitempty"`
}

type Stage struct {
	ID        string     `json:"id"`
	Name      string     `json:"name"`
	Date      string     `json:"date"`
	Waypoints []Waypoint `json:"waypoints"`
	StartTime *string    `json:"start_time,omitempty"`
}

type Trip struct {
	ID               string                 `json:"id"`
	Name             string                 `json:"name"`
	Stages           []Stage                `json:"stages"`
	AvalancheRegions []string               `json:"avalanche_regions,omitempty"`
	Aggregation      map[string]interface{} `json:"aggregation,omitempty"`
	WeatherConfig    map[string]interface{} `json:"weather_config,omitempty"`
	DisplayConfig    map[string]interface{} `json:"display_config,omitempty"`
	ReportConfig     map[string]interface{} `json:"report_config,omitempty"`
}
