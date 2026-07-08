package store

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

// PresetsFile gibt den Pfad zur Preset-Datei des aktuellen Users zurück.
func (s *Store) PresetsFile() string {
	return filepath.Join(s.DataDir, "users", s.UserID, "metric_presets.json")
}

// LoadMetricPresets lädt alle User-Presets. Gibt leeren Slice (nicht nil)
// zurück wenn die Datei nicht existiert (Erst-Aufruf).
//
// Issue #342: Zwei-Phasen-Decode mit Legacy-Migration. Bestehende Presets im
// alten Schema ({metrics:[]string, friendly_ids:[]string}) werden lazy in
// das neue Schema ([]DisplayMetric mit horizons-Defaults) ueberfuehrt; das
// JSON auf der Platte bleibt unveraendert bis zum naechsten Save.
func (s *Store) LoadMetricPresets() ([]model.MetricPreset, error) {
	data, err := os.ReadFile(s.PresetsFile())
	if err != nil {
		if os.IsNotExist(err) {
			return []model.MetricPreset{}, nil
		}
		return nil, err
	}
	var rawPresets []map[string]interface{}
	if err := json.Unmarshal(data, &rawPresets); err != nil {
		return nil, fmt.Errorf("metric_presets.json korrupt: %w", err)
	}
	presets := make([]model.MetricPreset, 0, len(rawPresets))
	for _, rp := range rawPresets {
		presets = append(presets, migrateMetricPreset(rp))
	}
	return presets, nil
}

// migrateMetricPreset fuehrt die Schema-Migration eines einzelnen Preset-
// Datensatzes durch. Erkennt drei Layouts:
//   - Legacy: metrics ist []string + paralleler friendly_ids
//   - Neu:    metrics ist []map mit metric_id/enabled/use_friendly_format/horizons
//   - Mischform: Neu-Schema ohne horizons-Feld -> Default {true,true,true}.
//
// Fehlende horizons-Felder werden auf {Today:true, Tomorrow:true,
// DayAfter:true} defaultet (= altes Verhalten, alle Tage sichtbar).
func migrateMetricPreset(rp map[string]interface{}) model.MetricPreset {
	allTrue := model.Horizons{Today: true, Tomorrow: true, DayAfter: true}

	p := model.MetricPreset{Metrics: []model.DisplayMetric{}}
	if v, ok := rp["id"].(string); ok {
		p.ID = v
	}
	if v, ok := rp["name"].(string); ok {
		p.Name = v
	}
	if v, ok := rp["description"].(string); ok {
		p.Description = v
	}
	if v, ok := rp["is_default"].(bool); ok {
		p.IsDefault = v
	}
	if v, ok := rp["created_at"].(string); ok {
		if ts, err := time.Parse(time.RFC3339, v); err == nil {
			p.CreatedAt = ts
		}
	}

	// Friendly-IDs aus Legacy-Layout extrahieren (Set fuer O(1) Lookup).
	friendlySet := map[string]bool{}
	if rawFIDs, ok := rp["friendly_ids"].([]interface{}); ok {
		for _, fid := range rawFIDs {
			if s, ok := fid.(string); ok {
				friendlySet[s] = true
			}
		}
	}

	rawMetrics, _ := rp["metrics"].([]interface{})
	for _, rm := range rawMetrics {
		// Legacy-Pfad: metric_id als String.
		if id, ok := rm.(string); ok {
			p.Metrics = append(p.Metrics, model.DisplayMetric{
				MetricID:          id,
				Enabled:           true,
				UseFriendlyFormat: friendlySet[id],
				Horizons:          allTrue,
			})
			continue
		}
		// Neu/Mischform-Pfad: metric_id als Map.
		m, ok := rm.(map[string]interface{})
		if !ok {
			continue
		}
		dm := model.DisplayMetric{Horizons: allTrue}
		if v, ok := m["metric_id"].(string); ok {
			dm.MetricID = v
		}
		if v, ok := m["enabled"].(bool); ok {
			dm.Enabled = v
		} else {
			dm.Enabled = true
		}
		if v, ok := m["use_friendly_format"].(bool); ok {
			dm.UseFriendlyFormat = v
		}
		if h, ok := m["horizons"].(map[string]interface{}); ok {
			if v, ok := h["today"].(bool); ok {
				dm.Horizons.Today = v
			}
			if v, ok := h["tomorrow"].(bool); ok {
				dm.Horizons.Tomorrow = v
			}
			if v, ok := h["day_after"].(bool); ok {
				dm.Horizons.DayAfter = v
			}
		}
		p.Metrics = append(p.Metrics, dm)
	}
	return p
}

// SaveMetricPresets schreibt alle Presets atomar.
func (s *Store) SaveMetricPresets(presets []model.MetricPreset) error {
	dir := filepath.Join(s.DataDir, "users", s.UserID)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}
	if presets == nil {
		presets = []model.MetricPreset{}
	}
	data, err := json.MarshalIndent(presets, "", "  ")
	if err != nil {
		return err
	}
	return writeFileLogged(s.PresetsFile(), data)
}
