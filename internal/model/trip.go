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
	ID                   string                 `json:"id"`
	Name                 string                 `json:"name"`
	Stages               []Stage                `json:"stages"`
	AvalancheRegions     []string               `json:"avalanche_regions,omitempty"`
	Aggregation          map[string]interface{} `json:"aggregation,omitempty"`
	WeatherConfig        map[string]interface{} `json:"weather_config,omitempty"`
	DisplayConfig        map[string]interface{} `json:"display_config,omitempty"`
	ReportConfig         map[string]interface{} `json:"report_config,omitempty"`
	AlertRules           []AlertRule            `json:"alert_rules"`
	AlertCooldownMinutes *int                   `json:"alert_cooldown_minutes,omitempty"`
	AlertQuietFrom       *string                `json:"alert_quiet_from,omitempty"`
	AlertQuietTo         *string                `json:"alert_quiet_to,omitempty"`
	Shortcode            string                 `json:"shortcode,omitempty"`
	Activity             string                 `json:"activity,omitempty"`
	Region               string                 `json:"region,omitempty"`
	PausedAt             *time.Time             `json:"paused_at,omitempty"`
	ArchivedAt           *time.Time             `json:"archived_at,omitempty"`
	// OfficialAlertsEnabled — Issue #1087, Pointer-Muster analog #1040:
	// nil = Feld fehlte (Altdaten/Default aktiv), false = strukturell kein
	// Fetch amtlicher Warnungen fuer diesen Trip.
	OfficialAlertsEnabled *bool `json:"official_alerts_enabled,omitempty"`
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

// ActiveAlertableMetricIDs reads display_config["metrics"] and returns the IDs
// of all enabled=true metrics that are contained in AlertableMetrics.
// This allows store.SaveTrip and store.LoadTrip to call SyncAlertRules centrally
// without importing the handler package (which would create an import cycle).
// Issue #809.
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
	seen := map[string]bool{}
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
		id, _ := mm["metric_id"].(string)
		if id == "" {
			continue
		}
		if seen[id] {
			continue
		}
		if _, alertable := AlertableMetrics[AlertMetric(id)]; alertable {
			seen[id] = true
			ids = append(ids, id)
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
