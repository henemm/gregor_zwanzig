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
	ID               string                 `json:"id"`
	Name             string                 `json:"name"`
	Stages           []Stage                `json:"stages"`
	AvalancheRegions []string               `json:"avalanche_regions,omitempty"`
	Aggregation      map[string]interface{} `json:"aggregation,omitempty"`
	WeatherConfig    map[string]interface{} `json:"weather_config,omitempty"`
	DisplayConfig    map[string]interface{} `json:"display_config,omitempty"`
	ReportConfig     map[string]interface{} `json:"report_config,omitempty"`
	AlertRules              []AlertRule            `json:"alert_rules"`
	AlertCooldownMinutes    *int                   `json:"alert_cooldown_minutes,omitempty"`
	AlertQuietFrom          *string                `json:"alert_quiet_from,omitempty"`
	AlertQuietTo            *string                `json:"alert_quiet_to,omitempty"`
	Shortcode               string                 `json:"shortcode,omitempty"`
	Activity         string                 `json:"activity,omitempty"`
	Region           string                 `json:"region,omitempty"`
	PausedAt         *time.Time             `json:"paused_at,omitempty"`
	ArchivedAt       *time.Time             `json:"archived_at,omitempty"`
}

// AlertableMetrics are metrics that can receive an absolute alert rule.
// Excluded: *_change metrics (delta-only), thunder_level (no meaningful absolute threshold).
var AlertableMetrics = map[AlertMetric]struct{}{
	AlertMetricWindGust:         {},
	AlertMetricPrecipitationSum: {},
	AlertMetricTemperatureMin:   {},
	AlertMetricTemperatureMax:   {},
	AlertMetricSnowLine:         {},
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

// SyncAlertRules synchronizes alert_rules with the active weather metrics.
// Invariant: exactly one absolute rule per active alertable metric.
// Existing absolute rules are preserved with their threshold (no default override).
// Delta rules and rules for inactive metrics are removed.
func SyncAlertRules(existing []AlertRule, activeMetricIDs []string) []AlertRule {
	// Index existing absolute rules per metric (first match wins)
	existingByMetric := map[AlertMetric]AlertRule{}
	for _, r := range existing {
		if r.Kind == AlertRuleKindAbsolute {
			if _, seen := existingByMetric[r.Metric]; !seen {
				existingByMetric[r.Metric] = r
			}
		}
	}

	result := []AlertRule{}
	for _, id := range activeMetricIDs {
		m := AlertMetric(id)
		if _, alertable := AlertableMetrics[m]; !alertable {
			continue
		}
		if ex, ok := existingByMetric[m]; ok {
			result = append(result, ex)
		} else {
			def := DefaultAlertThreshold[m]
			result = append(result, AlertRule{
				ID:        shortID(),
				Kind:      AlertRuleKindAbsolute,
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
