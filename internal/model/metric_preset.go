package model

import "time"

// MetricPreset speichert eine benutzer-definierte Auswahl an Wettermetriken
// für den Trip-Briefing-Editor (Epic #138 / Issue #177).
//
// Storage: data/users/{user_id}/metric_presets.json (JSON-Array, eine Datei pro User).
type MetricPreset struct {
	ID          string    `json:"id"`
	Name        string    `json:"name"`
	Description string    `json:"description,omitempty"`
	IsDefault   bool      `json:"is_default"`
	Metrics     []string  `json:"metrics"`      // aktivierte Metric-IDs
	FriendlyIDs []string  `json:"friendly_ids"` // IDs mit use_friendly_format=true
	CreatedAt   time.Time `json:"created_at"`
}
