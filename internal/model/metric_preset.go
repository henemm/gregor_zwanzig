package model

import "time"

// Horizons drueckt aus, fuer welche Tage relativ zum Report-Datum
// (today / tomorrow / day_after) eine Metrik in der HTML-Tabelle angezeigt
// wird. Default beim Load fehlender Felder ist {true,true,true} (Issue #342).
type Horizons struct {
	Today    bool `json:"today"`
	Tomorrow bool `json:"tomorrow"`
	DayAfter bool `json:"day_after"`
}

// DisplayMetric ist die strukturierte Form einer aktivierten Metrik in einem
// MetricPreset (Issue #342). Sie ersetzt das alte Tuple aus Metrics []string +
// FriendlyIDs []string und ergaenzt das Pro-Metrik-Zeithorizont-Feld.
type DisplayMetric struct {
	MetricID          string   `json:"metric_id"`
	Enabled           bool     `json:"enabled"`
	UseFriendlyFormat bool     `json:"use_friendly_format"`
	Horizons          Horizons `json:"horizons"`
}

// MetricPreset speichert eine benutzer-definierte Auswahl an Wettermetriken
// fuer den Trip-Briefing-Editor (Epic #138 / Issue #177, erweitert in #342).
//
// Storage: data/users/{user_id}/metric_presets.json (JSON-Array, eine Datei
// pro User). Legacy-Schema (Metrics []string + FriendlyIDs []string) wird
// beim Load via store.LoadMetricPresets() in das neue Schema migriert.
type MetricPreset struct {
	ID          string          `json:"id"`
	Name        string          `json:"name"`
	Description string          `json:"description,omitempty"`
	IsDefault   bool            `json:"is_default"`
	Metrics     []DisplayMetric `json:"metrics"`
	CreatedAt   time.Time       `json:"created_at"`
}
