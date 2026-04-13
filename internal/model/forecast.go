package model

import (
	"fmt"
	"time"
)

// ThunderLevel serialisiert als String "NONE" / "MED" / "HIGH"
type ThunderLevel string

const (
	ThunderNone ThunderLevel = "NONE"
	ThunderMed  ThunderLevel = "MED"
	ThunderHigh ThunderLevel = "HIGH"
)

// UTCTime wraps time.Time to serialize with +00:00 suffix instead of Z
type UTCTime struct {
	time.Time
}

func (t UTCTime) MarshalJSON() ([]byte, error) {
	s := t.Time.UTC().Format("2006-01-02T15:04:05+00:00")
	return []byte(fmt.Sprintf("%q", s)), nil
}

func (t *UTCTime) UnmarshalJSON(data []byte) error {
	var s string
	if len(data) < 2 {
		return fmt.Errorf("invalid time: %s", string(data))
	}
	s = string(data[1 : len(data)-1])
	parsed, err := time.Parse("2006-01-02T15:04:05+00:00", s)
	if err != nil {
		parsed, err = time.Parse(time.RFC3339, s)
	}
	if err != nil {
		return err
	}
	t.Time = parsed.UTC()
	return nil
}

type ForecastDataPoint struct {
	Time             UTCTime      `json:"ts"`
	T2mC             *float64     `json:"t2m_c,omitempty"`
	Wind10mKmh       *float64     `json:"wind10m_kmh,omitempty"`
	WindDirectionDeg *float64     `json:"wind_direction_deg,omitempty"`
	GustKmh          *float64     `json:"gust_kmh,omitempty"`
	Precip1hMm       *float64     `json:"precip_1h_mm,omitempty"`
	CloudTotalPct    *int         `json:"cloud_total_pct,omitempty"`
	CloudLowPct      *int         `json:"cloud_low_pct,omitempty"`
	CloudMidPct      *int         `json:"cloud_mid_pct,omitempty"`
	CloudHighPct     *int         `json:"cloud_high_pct,omitempty"`
	WmoCode          *int         `json:"wmo_code,omitempty"`
	ThunderLevel     ThunderLevel `json:"thunder_level,omitempty"`
	VisibilityM      *float64     `json:"visibility_m,omitempty"`
	FreezingLevelM   *float64     `json:"freezing_level_m,omitempty"`
	WindChillC       *float64     `json:"wind_chill_c,omitempty"`
	PressureMslHpa   *float64     `json:"pressure_msl_hpa,omitempty"`
	HumidityPct      *int         `json:"humidity_pct,omitempty"`
	DewpointC        *float64     `json:"dewpoint_c,omitempty"`
	PopPct           *int         `json:"pop_pct,omitempty"`
	CapeJkg          *float64     `json:"cape_jkg,omitempty"`
	IsDay            *int         `json:"is_day,omitempty"`
	DniWm2           *float64     `json:"dni_wm2,omitempty"`
	UvIndex          *float64     `json:"uv_index,omitempty"`
}

type ForecastMeta struct {
	Provider        string   `json:"provider"`
	Model           string   `json:"model"`
	GridResKm       float64  `json:"grid_res_km"`
	FallbackModel   string   `json:"fallback_model,omitempty"`
	FallbackMetrics []string `json:"fallback_metrics,omitempty"`
}

type Timeseries struct {
	Timezone string              `json:"timezone"`
	Meta     ForecastMeta        `json:"meta"`
	Data     []ForecastDataPoint `json:"data"`
}
