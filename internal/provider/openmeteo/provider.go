package openmeteo

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"math"
	"net/http"
	"net/url"
	"path/filepath"
	"strings"
	"time"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/provider"
)

type ProviderConfig struct {
	BaseURL    string
	AQURL      string
	TimeoutSec int
	Retries    int
	CacheDir   string
}

type OpenMeteoProvider struct {
	cfg    ProviderConfig
	client *http.Client
}

func NewProvider(cfg ProviderConfig) *OpenMeteoProvider {
	return &OpenMeteoProvider{
		cfg: cfg,
		client: &http.Client{
			Timeout: time.Duration(cfg.TimeoutSec) * time.Second,
		},
	}
}

// SelectModel returns the highest-resolution model covering lat/lon.
func SelectModel(lat, lon float64) (RegionalModel, error) {
	for _, m := range RegionalModels {
		if lat >= m.MinLat && lat <= m.MaxLat && lon >= m.MinLon && lon <= m.MaxLon {
			return m, nil
		}
	}
	return RegionalModel{}, &provider.ProviderError{Msg: "no model found for coordinates"}
}

// doRequest executes an HTTP GET with retry logic.
func (p *OpenMeteoProvider) doRequest(ctx context.Context, reqURL string) ([]byte, error) {
	var lastErr error
	for attempt := 0; attempt < p.cfg.Retries; attempt++ {
		if attempt > 0 {
			wait := math.Min(math.Pow(2, float64(attempt))*2, 60)
			select {
			case <-ctx.Done():
				return nil, ctx.Err()
			case <-time.After(time.Duration(wait) * time.Second):
			}
		}

		req, err := http.NewRequestWithContext(ctx, "GET", reqURL, nil)
		if err != nil {
			return nil, err
		}

		resp, err := p.client.Do(req)
		if err != nil {
			lastErr = err
			log.Printf("WARN: OpenMeteo request attempt %d failed: %v", attempt+1, err)
			continue
		}

		body, readErr := io.ReadAll(resp.Body)
		resp.Body.Close()
		if readErr != nil {
			lastErr = readErr
			continue
		}

		if resp.StatusCode == 502 || resp.StatusCode == 503 || resp.StatusCode == 504 {
			lastErr = &provider.ProviderRequestError{
				StatusCode: resp.StatusCode,
				Msg:        string(body),
			}
			log.Printf("WARN: OpenMeteo HTTP %d, retrying (%d/%d)", resp.StatusCode, attempt+1, p.cfg.Retries)
			continue
		}

		if resp.StatusCode != 200 {
			return nil, &provider.ProviderRequestError{
				StatusCode: resp.StatusCode,
				Msg:        string(body),
			}
		}

		return body, nil
	}
	return nil, fmt.Errorf("all %d retries exhausted: %w", p.cfg.Retries, lastErr)
}

// buildForecastURL constructs the API URL for a model.
func (p *OpenMeteoProvider) buildForecastURL(m RegionalModel, lat, lon float64, start, end time.Time) string {
	params := url.Values{}
	params.Set("latitude", fmt.Sprintf("%.4f", lat))
	params.Set("longitude", fmt.Sprintf("%.4f", lon))
	params.Set("hourly", strings.Join(HourlyParams, ","))
	params.Set("timezone", "UTC")
	params.Set("start_date", start.Format("2006-01-02"))
	params.Set("end_date", end.Format("2006-01-02"))
	return fmt.Sprintf("%s%s?%s", p.cfg.BaseURL, m.Endpoint, params.Encode())
}

// openMeteoResponse represents the raw API JSON structure.
type openMeteoResponse struct {
	Hourly map[string]json.RawMessage `json:"hourly"`
}

// parseResponse converts raw API JSON into ForecastDataPoints.
func parseResponse(raw []byte, m RegionalModel, uvData map[string]*float64) ([]model.ForecastDataPoint, error) {
	var resp openMeteoResponse
	if err := json.Unmarshal(raw, &resp); err != nil {
		return nil, fmt.Errorf("parse error: %w", err)
	}

	var times []string
	if err := json.Unmarshal(resp.Hourly["time"], &times); err != nil {
		return nil, fmt.Errorf("parse times: %w", err)
	}

	getFloats := func(key string) []*float64 {
		raw, ok := resp.Hourly[key]
		if !ok {
			return make([]*float64, len(times))
		}
		var vals []interface{}
		json.Unmarshal(raw, &vals)
		result := make([]*float64, len(vals))
		for i, v := range vals {
			if v != nil {
				if f, ok := v.(float64); ok {
					result[i] = &f
				}
			}
		}
		return result
	}

	getInts := func(key string) []*int {
		raw, ok := resp.Hourly[key]
		if !ok {
			return make([]*int, len(times))
		}
		var vals []interface{}
		json.Unmarshal(raw, &vals)
		result := make([]*int, len(vals))
		for i, v := range vals {
			if v != nil {
				if f, ok := v.(float64); ok {
					n := int(f)
					result[i] = &n
				}
			}
		}
		return result
	}

	temp := getFloats("temperature_2m")
	windSpeed := getFloats("wind_speed_10m")
	windDir := getFloats("wind_direction_10m")
	gusts := getFloats("wind_gusts_10m")
	precip := getFloats("precipitation")
	cloudTotal := getInts("cloud_cover")
	cloudLow := getInts("cloud_cover_low")
	cloudMid := getInts("cloud_cover_mid")
	cloudHigh := getInts("cloud_cover_high")
	wmoCode := getInts("weather_code")
	visibility := getFloats("visibility")
	freezing := getFloats("freezing_level_height")
	windChill := getFloats("apparent_temperature")
	pressure := getFloats("pressure_msl")
	humidity := getInts("relative_humidity_2m")
	dewpoint := getFloats("dewpoint_2m")
	pop := getInts("precipitation_probability")
	cape := getFloats("cape")
	isDay := getInts("is_day")
	dni := getFloats("direct_normal_irradiance")

	points := make([]model.ForecastDataPoint, len(times))
	for i, ts := range times {
		t, err := time.Parse("2006-01-02T15:04", ts)
		if err != nil {
			t, _ = time.Parse(time.RFC3339, ts)
		}

		var thunder model.ThunderLevel
		if i < len(wmoCode) && wmoCode[i] != nil {
			thunder = parseThunderLevel(*wmoCode[i])
		}

		dp := model.ForecastDataPoint{
			Time:         model.UTCTime{Time: t.UTC()},
			ThunderLevel: thunder,
		}

		if i < len(temp) {
			dp.T2mC = temp[i]
		}
		if i < len(windSpeed) {
			dp.Wind10mKmh = windSpeed[i]
		}
		if i < len(windDir) {
			dp.WindDirectionDeg = windDir[i]
		}
		if i < len(gusts) {
			dp.GustKmh = gusts[i]
		}
		if i < len(precip) {
			dp.Precip1hMm = precip[i]
		}
		if i < len(cloudTotal) {
			dp.CloudTotalPct = cloudTotal[i]
		}
		if i < len(cloudLow) {
			dp.CloudLowPct = cloudLow[i]
		}
		if i < len(cloudMid) {
			dp.CloudMidPct = cloudMid[i]
		}
		if i < len(cloudHigh) {
			dp.CloudHighPct = cloudHigh[i]
		}
		if i < len(wmoCode) {
			dp.WmoCode = wmoCode[i]
		}
		if i < len(visibility) {
			dp.VisibilityM = visibility[i]
		}
		if i < len(freezing) {
			dp.FreezingLevelM = freezing[i]
		}
		if i < len(windChill) {
			dp.WindChillC = windChill[i]
		}
		if i < len(pressure) {
			dp.PressureMslHpa = pressure[i]
		}
		if i < len(humidity) {
			dp.HumidityPct = humidity[i]
		}
		if i < len(dewpoint) {
			dp.DewpointC = dewpoint[i]
		}
		if i < len(pop) {
			dp.PopPct = pop[i]
		}
		if i < len(cape) {
			dp.CapeJkg = cape[i]
		}
		if i < len(isDay) {
			dp.IsDay = isDay[i]
		}
		if i < len(dni) {
			dp.DniWm2 = dni[i]
		}

		// UV from Air Quality API
		if uvData != nil {
			if uv, ok := uvData[ts]; ok {
				dp.UvIndex = uv
			}
		}

		points[i] = dp
	}

	return points, nil
}

// fetchUVData fetches UV index from the Air Quality API.
func (p *OpenMeteoProvider) fetchUVData(ctx context.Context, lat, lon float64, start, end time.Time) map[string]*float64 {
	params := url.Values{}
	params.Set("latitude", fmt.Sprintf("%.4f", lat))
	params.Set("longitude", fmt.Sprintf("%.4f", lon))
	params.Set("hourly", "uv_index")
	params.Set("timezone", "UTC")
	params.Set("start_date", start.Format("2006-01-02"))
	params.Set("end_date", end.Format("2006-01-02"))

	reqURL := fmt.Sprintf("%s/v1/air-quality?%s", p.cfg.AQURL, params.Encode())
	body, err := p.doRequest(ctx, reqURL)
	if err != nil {
		log.Printf("WARN: UV data fetch failed: %v", err)
		return nil
	}

	var resp openMeteoResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		log.Printf("WARN: UV data parse failed: %v", err)
		return nil
	}

	var times []string
	json.Unmarshal(resp.Hourly["time"], &times)

	var uvVals []interface{}
	json.Unmarshal(resp.Hourly["uv_index"], &uvVals)

	result := make(map[string]*float64, len(times))
	for i, ts := range times {
		if i < len(uvVals) && uvVals[i] != nil {
			if f, ok := uvVals[i].(float64); ok {
				result[ts] = &f
			}
		}
	}
	return result
}

// FetchForecast implements WeatherProvider.
func (p *OpenMeteoProvider) FetchForecast(lat, lon float64, hours int) (*model.Timeseries, error) {
	ctx := context.Background()

	m, err := SelectModel(lat, lon)
	if err != nil {
		return nil, err
	}
	log.Printf("DEBUG: Selected model %s (%.1fkm) for %.4f, %.4f", m.ID, m.GridResKm, lat, lon)

	now := time.Now().UTC()
	end := now.Add(time.Duration(hours) * time.Hour)

	reqURL := p.buildForecastURL(m, lat, lon, now, end)
	body, err := p.doRequest(ctx, reqURL)
	if err != nil {
		return nil, err
	}

	uvData := p.fetchUVData(ctx, lat, lon, now, end)

	points, err := parseResponse(body, m, uvData)
	if err != nil {
		return nil, err
	}

	// Truncate to requested hours (API returns full days)
	if len(points) > hours {
		points = points[:hours]
	}

	// Fallback: check for missing metrics and try secondary model
	points, fallbackModel, fallbackMetrics := p.tryFallback(ctx, lat, lon, m, points, now, end)

	tz := TimezoneForCoords(lat, lon)

	meta := model.ForecastMeta{
		Provider:  "OPENMETEO",
		Model:     m.ID,
		GridResKm: m.GridResKm,
	}
	if fallbackModel != "" {
		meta.FallbackModel = fallbackModel
		meta.FallbackMetrics = fallbackMetrics
	}

	return &model.Timeseries{
		Timezone: tz,
		Meta:     meta,
		Data:     points,
	}, nil
}

// tryFallback checks for nil fields in primary and merges from fallback model.
func (p *OpenMeteoProvider) tryFallback(
	ctx context.Context,
	lat, lon float64,
	primary RegionalModel,
	points []model.ForecastDataPoint,
	start, end time.Time,
) ([]model.ForecastDataPoint, string, []string) {
	if len(points) == 0 {
		return points, "", nil
	}

	// Check if any important fields are nil in first data point
	sample := points[0]
	missing := []string{}
	if sample.T2mC == nil {
		missing = append(missing, "temperature_2m")
	}
	if sample.Wind10mKmh == nil {
		missing = append(missing, "wind_speed_10m")
	}
	if sample.PressureMslHpa == nil {
		missing = append(missing, "pressure_msl")
	}

	if len(missing) == 0 {
		return points, "", nil
	}

	// Find fallback model
	fallback, found := findFallbackModel(lat, lon, primary)
	if !found {
		return points, "", nil
	}

	log.Printf("DEBUG: Trying fallback model %s for missing metrics: %v", fallback.ID, missing)

	reqURL := p.buildForecastURL(fallback, lat, lon, start, end)
	body, err := p.doRequest(ctx, reqURL)
	if err != nil {
		log.Printf("WARN: Fallback request failed: %v", err)
		return points, "", nil
	}

	fbPoints, err := parseResponse(body, fallback, nil)
	if err != nil {
		return points, "", nil
	}

	merged := mergeFallback(points, fbPoints)
	return merged, fallback.ID, missing
}

// findFallbackModel returns the next-priority model covering lat/lon.
func findFallbackModel(lat, lon float64, primary RegionalModel) (RegionalModel, bool) {
	for _, m := range RegionalModels {
		if m.Priority <= primary.Priority {
			continue
		}
		if lat >= m.MinLat && lat <= m.MaxLat && lon >= m.MinLon && lon <= m.MaxLon {
			return m, true
		}
	}
	return RegionalModel{}, false
}

// mergeFallback fills nil fields in primary from fallback by matching timestamps.
func mergeFallback(primary, fallback []model.ForecastDataPoint) []model.ForecastDataPoint {
	fbMap := make(map[string]model.ForecastDataPoint, len(fallback))
	for _, dp := range fallback {
		key := dp.Time.Time.Format(time.RFC3339)
		fbMap[key] = dp
	}

	for i := range primary {
		key := primary[i].Time.Time.Format(time.RFC3339)
		fb, ok := fbMap[key]
		if !ok {
			continue
		}
		if primary[i].T2mC == nil && fb.T2mC != nil {
			primary[i].T2mC = fb.T2mC
		}
		if primary[i].Wind10mKmh == nil && fb.Wind10mKmh != nil {
			primary[i].Wind10mKmh = fb.Wind10mKmh
		}
		if primary[i].PressureMslHpa == nil && fb.PressureMslHpa != nil {
			primary[i].PressureMslHpa = fb.PressureMslHpa
		}
		if primary[i].HumidityPct == nil && fb.HumidityPct != nil {
			primary[i].HumidityPct = fb.HumidityPct
		}
		if primary[i].CloudTotalPct == nil && fb.CloudTotalPct != nil {
			primary[i].CloudTotalPct = fb.CloudTotalPct
		}
		if primary[i].VisibilityM == nil && fb.VisibilityM != nil {
			primary[i].VisibilityM = fb.VisibilityM
		}
		if primary[i].FreezingLevelM == nil && fb.FreezingLevelM != nil {
			primary[i].FreezingLevelM = fb.FreezingLevelM
		}
	}

	return primary
}

// cachePath returns the full path to the availability cache file.
func (p *OpenMeteoProvider) cachePath() string {
	return filepath.Join(p.cfg.CacheDir, "model_availability.json")
}
