package model

import "time"

type CompareSubscription struct {
	ID              string                 `json:"id"`
	Name            string                 `json:"name"`
	Enabled         bool                   `json:"enabled"`
	Locations       []string               `json:"locations"`
	ForecastHours   int                    `json:"forecast_hours"`
	TimeWindowStart int                    `json:"time_window_start"`
	TimeWindowEnd   int                    `json:"time_window_end"`
	Schedule        string                 `json:"schedule"`
	Weekday         int                    `json:"weekday"`
	IncludeHourly   bool                   `json:"include_hourly"`
	TopN            int                    `json:"top_n"`
	SendEmail       bool                   `json:"send_email"`
	SendTelegram    bool                   `json:"send_telegram"`
	DisplayConfig   map[string]interface{} `json:"display_config,omitempty"`
	ActivityProfile *string                `json:"activity_profile,omitempty"`
	// Issue #252 — per-Subscription Empfaenger & Lauf-Status (additiv, omitempty)
	Recipients           []string   `json:"recipients,omitempty"`
	LastRun              *time.Time `json:"last_run,omitempty"`
	LastStatus           string     `json:"last_status,omitempty"`
	TopOrtLetzterVersand string     `json:"top_ort_letzter_versand,omitempty"`
}
