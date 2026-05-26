package compare

import (
	"context"
	"math"
	"sort"
	"sync"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/provider"
	"github.com/henemm/gregor-api/internal/store"
)

// Engine runs a full compare flow: parallel fetch, profile-weighted scoring,
// ranking, winner-tag computation, and hourly-data projection for the top-N
// locations.
type Engine struct {
	store    *store.Store
	provider provider.WeatherProvider
	cache    *resultCache
}

// New wires a compare Engine. provider may be nil — in that case the engine
// returns empty summaries for every existing location, which is useful for
// integration tests that hit the store but not external APIs.
func New(s *store.Store, p provider.WeatherProvider) *Engine {
	return &Engine{store: s, provider: p, cache: newResultCache()}
}

// fetchedRow is the intermediate result for a single location after the
// provider/cache stage but before population-wide scoring.
type fetchedRow struct {
	locationID string
	summary    model.SegmentWeatherSummary
	hourly     []model.ForecastDataPoint
	location   *model.Location
}

// Run executes a compare round-trip. It is safe to call concurrently.
//
// Behaviour summary:
//   - Locations that don't exist are silently dropped (partial result, no error).
//   - A nil provider yields an empty SegmentWeatherSummary for every existing
//     location — scoring then degenerates to zeros, but the request still
//     succeeds with a populated rows array. This lets the HTTP handler stay
//     observable in tests that don't wire a real provider.
//   - Cache hits skip both the store lookup and the provider call.
func (e *Engine) Run(ctx context.Context, userID string, req CompareRequest) (CompareResult, error) {
	us := e.store.WithUser(userID)

	var mu sync.Mutex
	var wg sync.WaitGroup
	fetched := make([]fetchedRow, 0, len(req.LocationIDs))

	for _, id := range req.LocationIDs {
		locID := id
		wg.Add(1)
		go func() {
			defer wg.Done()

			key := cacheKey{LocationID: locID, Date: req.Date, Profile: req.Profile}
			if entry, ok := e.cache.get(key); ok {
				loc, err := us.LoadLocation(locID)
				if err != nil || loc == nil {
					return
				}
				mu.Lock()
				fetched = append(fetched, fetchedRow{locationID: locID, summary: entry.summary, hourly: entry.hourly, location: loc})
				mu.Unlock()
				return
			}

			loc, err := us.LoadLocation(locID)
			if err != nil || loc == nil {
				return // partial result — drop silently
			}

			var summary model.SegmentWeatherSummary
			var hourly []model.ForecastDataPoint

			if e.provider != nil {
				ts, err := e.provider.FetchForecast(loc.Lat, loc.Lon, 72)
				if err != nil {
					return // provider failed → drop location (partial result)
				}
				if ts != nil {
					if agg := aggregateByDate(ts.Data, req.Date); agg != nil {
						summary = *agg
					}
					hourly = filterByDate(ts.Data, req.Date)
				}
			}

			e.cache.set(key, summary, hourly)

			mu.Lock()
			fetched = append(fetched, fetchedRow{locationID: locID, summary: summary, hourly: hourly, location: loc})
			mu.Unlock()
		}()
	}
	wg.Wait()

	if len(fetched) == 0 {
		return CompareResult{Rows: []CompareRow{}, Hourly: map[string][]model.ForecastDataPoint{}}, nil
	}

	locs := make([]*model.Location, 0, len(fetched))
	for _, fr := range fetched {
		if fr.location != nil {
			locs = append(locs, fr.location)
		}
	}
	enabledKeys := intersectScoreKeys(locs, req.Profile)

	allMetrics := make([]model.SegmentWeatherSummary, len(fetched))
	for i, fr := range fetched {
		allMetrics[i] = fr.summary
	}

	rows := make([]CompareRow, len(fetched))
	for i, fr := range fetched {
		rows[i] = CompareRow{
			LocationID: fr.locationID,
			Score:      ScoreRow(fr.summary, req.Profile, allMetrics, enabledKeys),
			Metrics:    fr.summary,
		}
	}

	sort.SliceStable(rows, func(i, j int) bool {
		if rows[i].Score != rows[j].Score {
			return rows[i].Score > rows[j].Score
		}
		return rows[i].LocationID < rows[j].LocationID
	})
	for i := range rows {
		rows[i].Rank = i + 1
	}

	hourly := make(map[string][]model.ForecastDataPoint)
	topN := 3
	if len(rows) < topN {
		topN = len(rows)
	}
	hourlyByLoc := make(map[string][]model.ForecastDataPoint, len(fetched))
	for _, fr := range fetched {
		hourlyByLoc[fr.locationID] = fr.hourly
	}
	for i := 0; i < topN; i++ {
		hourly[rows[i].LocationID] = hourlyByLoc[rows[i].LocationID]
	}

	var winner *CompareWinner
	if len(rows) > 0 {
		w := rows[0]
		winner = &CompareWinner{
			LocationID: w.LocationID,
			Tags:       WinnerTags(w.Metrics, req.Profile),
		}
	}

	return CompareResult{Rows: rows, Winner: winner, Hourly: hourly}, nil
}

// filterByDate keeps only forecast points whose UTC date matches dateStr
// (YYYY-MM-DD). An empty or unparseable dateStr is treated as "no filter".
func filterByDate(points []model.ForecastDataPoint, dateStr string) []model.ForecastDataPoint {
	if dateStr == "" {
		out := make([]model.ForecastDataPoint, len(points))
		copy(out, points)
		return out
	}
	out := make([]model.ForecastDataPoint, 0, len(points))
	for _, pt := range points {
		if pt.Time.UTC().Format("2006-01-02") == dateStr {
			out = append(out, pt)
		}
	}
	return out
}

// aggregateByDate aggregates forecast points into a SegmentWeatherSummary
// for a single UTC day. Empty/invalid dateStr → aggregate over all points.
// Returns nil if no points qualify.
func aggregateByDate(points []model.ForecastDataPoint, dateStr string) *model.SegmentWeatherSummary {
	filtered := points
	if dateStr != "" {
		filtered = make([]model.ForecastDataPoint, 0, len(points))
		for _, pt := range points {
			if pt.Time.UTC().Format("2006-01-02") == dateStr {
				filtered = append(filtered, pt)
			}
		}
	}
	if len(filtered) == 0 {
		return nil
	}

	out := &model.SegmentWeatherSummary{ThunderLevelMax: model.ThunderNone}

	const dniMin, dniMax = 60.0, 180.0
	var precipSum float64
	precipAny := false
	var sunnyFractionSum float64
	sunnyAny := false
	var cloudSum int
	cloudCount := 0
	var snowDepthMax *float64
	var snowNewSum float64
	snowNewAny := false

	for _, pt := range filtered {
		updateMinFloat(&out.TempMinC, pt.T2mC)
		updateMaxFloat(&out.TempMaxC, pt.T2mC)
		updateMaxFloat(&out.WindMaxKmh, pt.Wind10mKmh)
		updateMaxFloat(&out.GustMaxKmh, pt.GustKmh)
		updateMinFloat(&out.VisibilityMinM, pt.VisibilityM)
		updateMinFloat(&out.WindChillMinC, pt.WindChillC)
		updateMaxFloat(&out.CapeMaxJkg, pt.CapeJkg)
		updateMaxFloat(&out.UvIndexMax, pt.UvIndex)
		updateMaxInt(&out.PopMaxPct, pt.PopPct)

		if pt.Precip1hMm != nil {
			precipSum += *pt.Precip1hMm
			precipAny = true
		}
		if pt.DniWm2 != nil {
			v := *pt.DniWm2
			switch {
			case v >= dniMax:
				sunnyFractionSum += 1.0
			case v > dniMin:
				sunnyFractionSum += (v - dniMin) / (dniMax - dniMin)
			}
			sunnyAny = true
		}
		if pt.CloudTotalPct != nil {
			cloudSum += *pt.CloudTotalPct
			cloudCount++
		}
		if pt.SnowDepthCm != nil {
			if snowDepthMax == nil || *pt.SnowDepthCm > *snowDepthMax {
				v := *pt.SnowDepthCm
				snowDepthMax = &v
			}
		}
		if pt.SnowNew24hCm != nil {
			snowNewSum += *pt.SnowNew24hCm
			snowNewAny = true
		}
		if thunderOrder(pt.ThunderLevel) > thunderOrder(out.ThunderLevelMax) {
			out.ThunderLevelMax = pt.ThunderLevel
		}
	}

	if precipAny {
		s := precipSum
		out.PrecipSumMm = &s
	}
	if sunnyAny {
		rounded := math.Round(sunnyFractionSum*10) / 10
		out.SunnyHoursH = &rounded
	}
	if cloudCount > 0 {
		avg := cloudSum / cloudCount
		out.CloudAvgPct = &avg
	}
	if snowDepthMax != nil {
		out.SnowDepthCm = snowDepthMax
	}
	if snowNewAny {
		s := snowNewSum
		out.SnowNewSumCm = &s
	}

	return out
}

func updateMinFloat(dst **float64, v *float64) {
	if v == nil {
		return
	}
	if *dst == nil || *v < **dst {
		val := *v
		*dst = &val
	}
}

func updateMaxFloat(dst **float64, v *float64) {
	if v == nil {
		return
	}
	if *dst == nil || *v > **dst {
		val := *v
		*dst = &val
	}
}

func updateMaxInt(dst **int, v *int) {
	if v == nil {
		return
	}
	if *dst == nil || *v > **dst {
		val := *v
		*dst = &val
	}
}

func thunderOrder(l model.ThunderLevel) int {
	switch l {
	case model.ThunderHigh:
		return 2
	case model.ThunderMed:
		return 1
	default:
		return 0
	}
}

// frontendIDToMetricKey maps the string metric IDs stored in DisplayConfig
// to the internal metricKey constants used by the scoring engine.
var frontendIDToMetricKey = map[string]metricKey{
	"precipitation": metricPrecipSum,
	"wind":          metricWindMax,
	"gust":          metricWindMax,
	"temperature":   metricTempMax,
	"snow_depth":    metricSnowDepth,
	"fresh_snow":    metricSnowNew,
	"sunshine":      metricSunnyHours,
	"cloud_total":   metricCloudAvg,
	"thunder":       metricThunderProxy,
	"visibility":    metricVisibilityMin,
	"uv_index":      metricUvIndexMax,
}

// extractScoreMap reads score_member fields from a location's DisplayConfig.
// Returns nil if no score_member fields are present (all default to true).
func extractScoreMap(loc *model.Location) map[metricKey]bool {
	if loc == nil || loc.DisplayConfig == nil {
		return nil
	}
	raw, ok := loc.DisplayConfig["metrics"]
	if !ok {
		return nil
	}
	metricsSlice, ok := raw.([]interface{})
	if !ok {
		return nil
	}
	result := make(map[metricKey]bool)
	for _, item := range metricsSlice {
		entry, ok := item.(map[string]interface{})
		if !ok {
			continue
		}
		idRaw, ok := entry["metric_id"]
		if !ok {
			continue
		}
		id, ok := idRaw.(string)
		if !ok {
			continue
		}
		smRaw, ok := entry["score_member"]
		if !ok {
			continue // absent = default true, skip
		}
		sm, ok := smRaw.(bool)
		if !ok {
			continue
		}
		mk, ok := frontendIDToMetricKey[id]
		if !ok {
			continue
		}
		result[mk] = sm
	}
	if len(result) == 0 {
		return nil
	}
	return result
}

// intersectScoreKeys returns metric keys enabled (score_member=true or absent)
// across ALL locations. Returns nil when no filtering is needed:
//   - no location has any score_member field set
//   - the resulting intersection would be empty (fallback to full scoring)
func intersectScoreKeys(locs []*model.Location, _ ActivityProfile) map[metricKey]bool {
	scoreMaps := make([]map[metricKey]bool, 0, len(locs))
	for _, loc := range locs {
		if sm := extractScoreMap(loc); sm != nil {
			scoreMaps = append(scoreMaps, sm)
		}
	}
	if len(scoreMaps) == 0 {
		return nil
	}

	// Collect all mentioned keys.
	allKeys := make(map[metricKey]struct{})
	for _, sm := range scoreMaps {
		for k := range sm {
			allKeys[k] = struct{}{}
		}
	}

	// A key is included only if it is NOT explicitly false in any location.
	result := make(map[metricKey]bool)
	for k := range allKeys {
		excluded := false
		for _, sm := range scoreMaps {
			if v, exists := sm[k]; exists && !v {
				excluded = true
				break
			}
		}
		if !excluded {
			result[k] = true
		}
	}

	if len(result) == 0 {
		return nil // empty intersection → fallback
	}
	return result
}
