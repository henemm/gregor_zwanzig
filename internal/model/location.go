package model

type Location struct {
	ID              string                 `json:"id"`
	Name            string                 `json:"name"`
	Lat             float64                `json:"lat"`
	Lon             float64                `json:"lon"`
	ElevationM      *int                   `json:"elevation_m,omitempty"`
	Region          *string                `json:"region,omitempty"`
	BergfexSlug     *string                `json:"bergfex_slug,omitempty"`
	ActivityProfile *string                `json:"activity_profile,omitempty"`
	DisplayConfig   map[string]interface{} `json:"display_config,omitempty"`
}
