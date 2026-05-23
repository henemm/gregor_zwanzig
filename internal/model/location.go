package model

import "time"

type Location struct {
	ID              string                 `json:"id"`
	Name            string                 `json:"name"`
	Lat             float64                `json:"lat"`
	Lon             float64                `json:"lon"`
	ElevationM      *int                   `json:"elevation_m,omitempty"`
	Region          *string                `json:"region,omitempty"`
	BergfexSlug     *string                `json:"bergfex_slug,omitempty"`
	ActivityProfile *string                `json:"activity_profile,omitempty"`
	Group           *string                `json:"group,omitempty"`
	GroupID         *string                `json:"group_id,omitempty"`
	DisplayConfig   map[string]interface{} `json:"display_config,omitempty"`
	Timezone        string                 `json:"timezone,omitempty"`
	DataSource      string                 `json:"data_source,omitempty"`
	CreatedAt       *time.Time             `json:"created_at,omitempty"`
}
