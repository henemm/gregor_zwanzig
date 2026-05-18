package model

import "time"

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
type AlertRule struct {
	ID        string        `json:"id"`
	Kind      AlertRuleKind `json:"kind"`
	Metric    AlertMetric   `json:"metric"`
	Threshold float64       `json:"threshold"`
	Unit      string        `json:"unit,omitempty"`
	Severity  AlertSeverity `json:"severity"`
	Enabled   bool          `json:"enabled"`
}

type Waypoint struct {
	ID         string  `json:"id"`
	Name       string  `json:"name"`
	Lat        float64 `json:"lat"`
	Lon        float64 `json:"lon"`
	ElevationM int     `json:"elevation_m"`
	TimeWindow *string `json:"time_window,omitempty"`
	Suggested  bool    `json:"suggested,omitempty"`
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
