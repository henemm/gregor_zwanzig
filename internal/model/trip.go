package model

import (
	"crypto/rand"
	"encoding/hex"
	"time"
)

// shortID generates a random 8-character hex string for new alert rule IDs.
func shortID() string {
	b := make([]byte, 4)
	if _, err := rand.Read(b); err != nil {
		panic("crypto/rand unavailable: " + err.Error())
	}
	return hex.EncodeToString(b)
}

// AlertRuleKind classifies an alert rule as absolute threshold or delta change.
type AlertRuleKind string

const (
	AlertRuleKindAbsolute AlertRuleKind = "absolute"
	AlertRuleKindDelta    AlertRuleKind = "delta"
)

// AlertSeverity classifies the severity of an alert rule.
type AlertSeverity string

const (
	AlertSeverityInfo     AlertSeverity = "info"
	AlertSeverityWarning  AlertSeverity = "warning"
	AlertSeverityCritical AlertSeverity = "critical"
)

// AlertMetric identifies which weather metric an alert observes.
type AlertMetric string

const (
	AlertMetricWindGust            AlertMetric = "wind_gust"
	AlertMetricPrecipitationSum    AlertMetric = "precipitation_sum"
	AlertMetricTemperatureMin      AlertMetric = "temperature_min"
	AlertMetricTemperatureMax      AlertMetric = "temperature_max"
	AlertMetricThunderLevel        AlertMetric = "thunder_level"
	AlertMetricSnowLine            AlertMetric = "snow_line"
	AlertMetricTemperatureChange   AlertMetric = "temperature_change"
	AlertMetricWindChange          AlertMetric = "wind_change"
	AlertMetricPrecipitationChange AlertMetric = "precipitation_change"
)

// AlertRule is a single configurable alert rule on a Trip (Issue #205).
// Issue #297 — PairID + DeltaWindow als optionale Felder (omitempty) ergänzt.
// Issue #638 — Channels: per-alert channel override (empty = inherit from report_config).
type AlertRule struct {
	ID          string        `json:"id"`
	Kind        AlertRuleKind `json:"kind"`
	Metric      AlertMetric   `json:"metric"`
	Threshold   float64       `json:"threshold"`
	Unit        string        `json:"unit,omitempty"`
	Severity    AlertSeverity `json:"severity"`
	Enabled     bool          `json:"enabled"`
	PairID      *string       `json:"pair_id,omitempty"`
	DeltaWindow *string       `json:"delta_window,omitempty"`
	Channels    []string      `json:"channels,omitempty"`
}

// Corridor is a value range for a metric that unifies Trip alert thresholds
// (Notify) and Compare ideal ranges (Mark) into one structure (Issue #1231).
// Additiv neben AlertRules/DisplayConfig["ideal_ranges"], die bis zu einem
// spaeteren Cutover die technische Wahrheit fuer den Delta-Waechter bleiben.
// Range ist ein 2er-Array [min, max]; jede Seite kann nil sein (offen, C2).
type Corridor struct {
	Metric string      `json:"metric"`
	Range  [2]*float64 `json:"range"`
	Notify bool        `json:"notify"`
	Mark   bool        `json:"mark"`
	Prio   string      `json:"prio,omitempty"` // "hoch"|"mittel"|"niedrig" — nur Anzeige-Reihenfolge (C1)
}

type Waypoint struct {
	ID                string  `json:"id"`
	Name              string  `json:"name"`
	Lat               float64 `json:"lat"`
	Lon               float64 `json:"lon"`
	ElevationM        int     `json:"elevation_m"`
	TimeWindow        *string `json:"time_window,omitempty"`
	ArrivalCalculated *string `json:"arrival_calculated,omitempty"` // Issue #296 — "HH:MM", vom Backend berechnet (Naismith)
	// Issue #303 — algorithmische Wegpunktvorschläge + Override.
	Origin          string  `json:"origin,omitempty"`           // "manual" | "algorithmic"; leer = "manual"
	Confirmed       *bool   `json:"confirmed,omitempty"`        // *bool: false bleibt serialisierbar, nur nil wird ausgelassen
	ArrivalOverride *string `json:"arrival_override,omitempty"` // User-Override "HH:MM"
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
	AlertRules       []AlertRule            `json:"alert_rules"`
	// Corridors — Issue #1231, Slice 1: additiv, kein omitempty (analog
	// AlertRules), damit Go konsistent zum Python-Verhalten (app.loader
	// emittiert corridors immer, auch leer) bleibt.
	Corridors            []Corridor `json:"corridors"`
	AlertCooldownMinutes *int       `json:"alert_cooldown_minutes,omitempty"`
	AlertQuietFrom       *string    `json:"alert_quiet_from,omitempty"`
	AlertQuietTo         *string    `json:"alert_quiet_to,omitempty"`
	Shortcode            string     `json:"shortcode,omitempty"`
	Activity             string     `json:"activity,omitempty"`
	Region               string     `json:"region,omitempty"`
	PausedAt             *time.Time `json:"paused_at,omitempty"`
	ArchivedAt           *time.Time `json:"archived_at,omitempty"`
	// OfficialAlertsEnabled — Issue #1087, Pointer-Muster analog #1040:
	// nil = Feld fehlte (Altdaten/Default aktiv), false = strukturell kein
	// Fetch amtlicher Warnungen fuer diesen Trip.
	OfficialAlertsEnabled *bool `json:"official_alerts_enabled,omitempty"`
	// OfficialAlertTriggersEnabled — Issue #1088, gleiches Pointer-Muster wie
	// OfficialAlertsEnabled: nil/true = eigenstaendiger Sofort-Alert-Trigger
	// bei amtlichen Warnungen aktiv, false = kein Sofort-Alert-Trigger.
	OfficialAlertTriggersEnabled *bool `json:"official_alert_triggers_enabled,omitempty"`
	// OfficialWarnings — Issue #1258, loest OfficialAlertTriggersEnabled
	// funktional ab (Legacy-Feld bleibt fuer Rollback-Sicherheit unveraendert
	// bestehen). nil = Feld fehlte (Altdaten, noch nicht migriert, s.
	// internal/store/migrate_1258.go), gesetzt = massgeblich fuer die
	// Sofort-Alarm-Pipeline.
	OfficialWarnings *OfficialWarningsConfig `json:"official_warnings,omitempty"`
}

// OfficialWarningsConfig — Issue #1258, geteilt zwischen Trip und
// ComparePreset (Pointer-Feld-Pattern analog OfficialAlertsEnabled/#1040/
// #1087). Sources unset/leer = alle registrierten Quellen beruecksichtigt.
type OfficialWarningsConfig struct {
	Enabled bool     `json:"enabled"`
	Sources []string `json:"sources,omitempty"`
}

// AlertableMetrics are metrics that can receive an alert rule (delta-based since #817).
// Issue #817: thunder_level added — no meaningful absolute threshold, but
// delta threshold (Δ≥1 level) is meaningful.
// Excluded: *_change metrics (conceptually redundant after #817, Folge-Issue pending).
var AlertableMetrics = map[AlertMetric]struct{}{
	AlertMetricWindGust:         {},
	AlertMetricPrecipitationSum: {},
	AlertMetricTemperatureMin:   {},
	AlertMetricTemperatureMax:   {},
	AlertMetricSnowLine:         {},
	AlertMetricThunderLevel:     {},
}

// DefaultDeltaThreshold spiegelt Python metric_catalog.default_change_threshold
// (Cross-Lang-Wertekontrakt — Präzedenz: #802 naismith, Issue #817).
// Einheit entspricht der jeweiligen AlertRule.Unit.
var DefaultDeltaThreshold = map[AlertMetric]struct {
	Threshold float64
	Unit      string
	Severity  AlertSeverity
}{
	AlertMetricWindGust:         {20, "km/h", AlertSeverityWarning},
	AlertMetricPrecipitationSum: {10, "mm", AlertSeverityWarning},
	AlertMetricTemperatureMin:   {5, "°C", AlertSeverityWarning},
	AlertMetricTemperatureMax:   {5, "°C", AlertSeverityInfo},
	AlertMetricThunderLevel:     {1, "", AlertSeverityWarning},
	AlertMetricSnowLine:         {200, "m", AlertSeverityInfo},
}

// DefaultAlertThreshold contains default values for new absolute alert rules.
var DefaultAlertThreshold = map[AlertMetric]struct {
	Threshold float64
	Unit      string
	Severity  AlertSeverity
}{
	AlertMetricWindGust:         {50, "km/h", AlertSeverityWarning},
	AlertMetricPrecipitationSum: {20, "mm", AlertSeverityWarning},
	AlertMetricTemperatureMin:   {-5, "°C", AlertSeverityWarning},
	AlertMetricTemperatureMax:   {35, "°C", AlertSeverityInfo},
	AlertMetricSnowLine:         {1500, "m", AlertSeverityInfo},
}

// catalogIDToAlertMetrics is the forward mapping from metric-catalog IDs
// (src/app/metric_catalog.py, e.g. "gust", "temperature") to the AlertMetric
// value(s) they activate. Issue #1257: exact inverse of the Python bridge
// _ALERT_METRIC_TO_CATALOG_ID (src/services/weather_change_detection.py),
// filtered to AlertableMetrics — kept in sync via
// tests/tdd/test_alert_metric_mapping_parity.py.
var catalogIDToAlertMetrics = map[string][]AlertMetric{
	"gust":             {AlertMetricWindGust},
	"precipitation":    {AlertMetricPrecipitationSum},
	"thunder":          {AlertMetricThunderLevel},
	"temperature":      {AlertMetricTemperatureMin, AlertMetricTemperatureMax},
	"temperature_cold": {AlertMetricTemperatureMin},
	"snowfall_limit":   {AlertMetricSnowLine},
	"freezing_level":   {AlertMetricSnowLine},
}

// ActiveAlertableMetricIDs reads display_config["metrics"], translates each
// enabled=true catalog metric_id via catalogIDToAlertMetrics into the
// AlertMetric vocabulary, and returns the deduplicated AlertMetric values
// that are also contained in AlertableMetrics (safety net).
// This allows store.SaveTrip and store.LoadTrip to call SyncAlertRules centrally
// without importing the handler package (which would create an import cycle).
// Issue #809, forward-mapping fix Issue #1257.
func ActiveAlertableMetricIDs(displayConfig map[string]interface{}) []string {
	if displayConfig == nil {
		return nil
	}
	raw, ok := displayConfig["metrics"]
	if !ok {
		return nil
	}
	metrics, ok := raw.([]interface{})
	if !ok {
		return nil
	}
	seen := map[AlertMetric]bool{}
	var ids []string
	for _, m := range metrics {
		mm, ok := m.(map[string]interface{})
		if !ok {
			continue
		}
		enabled, _ := mm["enabled"].(bool)
		if !enabled {
			continue
		}
		catalogID, _ := mm["metric_id"].(string)
		if catalogID == "" {
			continue
		}
		for _, alertMetric := range catalogIDToAlertMetrics[catalogID] {
			if _, alertable := AlertableMetrics[alertMetric]; !alertable {
				continue
			}
			if seen[alertMetric] {
				continue
			}
			seen[alertMetric] = true
			ids = append(ids, string(alertMetric))
		}
	}
	return ids
}

// SyncAlertRules synchronizes alert_rules with the active weather metrics.
// Issue #817 — Invariant: exactly one kind="delta" rule per active alertable metric.
//
// Migration logic:
//   - Existing delta rule → preserved as-is (incl. user-configured threshold, idempotent).
//   - Existing absolute rule → migrated to kind="delta" with DefaultDeltaThreshold value;
//     enabled/severity/channels/pair_id are preserved (read-modify-write, no replace).
//   - No existing rule for a metric → new kind="delta" rule with DefaultDeltaThreshold.
//   - Rules for inactive metrics → removed.
func SyncAlertRules(existing []AlertRule, activeMetricIDs []string) []AlertRule {
	// Index existing rules per metric.
	// Issue #817 F003: wenn fuer dieselbe Metrik sowohl eine absolute ALS AUCH
	// eine delta-Regel vorliegt (z.B. stale client state), gewinnt die delta-Regel
	// — damit geht der nutzerkonfigurierte Δ-Threshold nicht verloren.
	existingByMetric := map[AlertMetric]AlertRule{}
	for _, r := range existing {
		cur, seen := existingByMetric[r.Metric]
		if !seen {
			existingByMetric[r.Metric] = r
		} else if cur.Kind == AlertRuleKindAbsolute && r.Kind == AlertRuleKindDelta {
			existingByMetric[r.Metric] = r // delta mit Custom-Threshold gewinnt
		}
	}

	result := []AlertRule{}
	for _, id := range activeMetricIDs {
		m := AlertMetric(id)
		if _, alertable := AlertableMetrics[m]; !alertable {
			continue
		}
		if ex, ok := existingByMetric[m]; ok {
			// Read-modify-write: migrate kind to delta, reset threshold only if was absolute.
			rule := ex
			rule.Kind = AlertRuleKindDelta
			if ex.Kind == AlertRuleKindAbsolute {
				def := DefaultDeltaThreshold[m]
				rule.Threshold = def.Threshold
				rule.Unit = def.Unit
			}
			result = append(result, rule)
		} else {
			def := DefaultDeltaThreshold[m]
			result = append(result, AlertRule{
				ID:        shortID(),
				Kind:      AlertRuleKindDelta,
				Metric:    m,
				Threshold: def.Threshold,
				Unit:      def.Unit,
				Severity:  def.Severity,
				Enabled:   true,
			})
		}
	}
	return result
}
