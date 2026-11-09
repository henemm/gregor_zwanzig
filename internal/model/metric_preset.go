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
//
// Issue #2794 S3a (W5b, AC-22/AC-26): Zeithorizonte entfallen. Horizons wird
// weder gespeichert noch ausgeliefert (fehlend = „alle Tage"); Altwerte
// entfernt scripts/migrate_2794_preset_horizons.py.
type DisplayMetric struct {
	MetricID          string   `json:"metric_id"`
	Enabled           bool     `json:"enabled"`
	UseFriendlyFormat bool     `json:"use_friendly_format"`
	Horizons          Horizons `json:"-"`
}

// Arten eigener Vorlagen (Issue #2794 S3a, AC-24): Trip bzw. Orts-Vergleich.
// Bestand ohne kind gilt als Trip.
const (
	PresetKindRoute     = "route"
	PresetKindVergleich = "vergleich"
)

// ValidPresetKind meldet, ob k eine gueltige Vorlagen-Art ist.
func ValidPresetKind(k string) bool {
	return k == PresetKindRoute || k == PresetKindVergleich
}

// MetricPreset speichert eine benutzer-definierte Auswahl an Wettermetriken
// fuer den Trip-Briefing-Editor (Epic #138 / Issue #177, erweitert in #342).
//
// Storage: data/users/{user_id}/metric_presets.json (JSON-Array, eine Datei
// pro User). Legacy-Schema (Metrics []string + FriendlyIDs []string) wird
// beim Load via store.LoadMetricPresets() in das neue Schema migriert.
type MetricPreset struct {
	ID          string `json:"id"`
	Name        string `json:"name"`
	Description string `json:"description,omitempty"`
	// Issue #2794 S3a: Art der Vorlage (route|vergleich); is_default und
	// Namens-Eindeutigkeit gelten je Art.
	Kind      string          `json:"kind"`
	IsDefault bool            `json:"is_default"`
	Metrics   []DisplayMetric `json:"metrics"`
	CreatedAt time.Time       `json:"created_at"`
	// Issue #2792 S1a / ADR-0106: Profil-Ampel der eigenen Vorlage
	// ({template, metrics{id:{enabled, lower, upper, alarm_ab}}, thunder}),
	// beim Anwenden ins Abo kopiert. nil = Vorlage "allgemein" (Bestand).
	// Keine Zustellungsfelder (Empfaenger, Kanaele, Etappen).
	Ampel map[string]interface{} `json:"ampel,omitempty"`
}
