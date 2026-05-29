package compare

import (
	"context"
	"fmt"
	"math"
	"sort"
	"sync"
	"time"

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
//     succeeds with a populated ranking array. This lets the HTTP handler stay
//     observable in tests that don't wire a real provider.
//   - Cache hits skip both the store lookup and the provider call.
//   - Issue #454: Multi-day aggregation across [date_from..date_to] with an
//     hour-window filter [hour_from..hour_to] (UTC).
func (e *Engine) Run(ctx context.Context, userID string, req CompareRequest) (CompareResult, error) {
	us := e.store.WithUser(userID)

	hours := forecastHours(req.DateTo)

	var mu sync.Mutex
	var wg sync.WaitGroup
	fetched := make([]fetchedRow, 0, len(req.LocationIDs))

	for _, id := range req.LocationIDs {
		locID := id
		wg.Add(1)
		go func() {
			defer wg.Done()
			fr, ok := e.fetchOne(us, locID, req, hours)
			if !ok {
				return
			}
			mu.Lock()
			fetched = append(fetched, fr)
			mu.Unlock()
		}()
	}
	wg.Wait()

	return buildResult(fetched, req), nil
}

// forecastHours returns the number of forecast hours to request from the
// provider, sized to span until date_to + 48h buffer, capped to OpenMeteo's
// 240h limit and floored at 72h to keep backwards compatibility with the
// previous single-day behaviour.
func forecastHours(dateTo string) int {
	const (
		defaultHours = 72
		maxHours     = 240
	)
	if dateTo == "" {
		return defaultHours
	}
	t, err := time.Parse("2006-01-02", dateTo)
	if err != nil {
		return defaultHours
	}
	delta := int(t.Sub(time.Now()).Hours()) + 48
	if delta < defaultHours {
		return defaultHours
	}
	if delta > maxHours {
		return maxHours
	}
	return delta
}

// fetchOne resolves a single location (cache-first, then provider). Returns
// (row, true) on success, (_, false) when the location should be dropped.
func (e *Engine) fetchOne(us *store.Store, locID string, req CompareRequest, hours int) (fetchedRow, bool) {
	key := cacheKey{
		LocationID: locID,
		DateFrom:   req.DateFrom,
		DateTo:     req.DateTo,
		HourFrom:   req.HourFrom,
		HourTo:     req.HourTo,
		Profile:    req.Profile,
	}
	if entry, ok := e.cache.get(key); ok {
		loc, err := us.LoadLocation(locID)
		if err != nil || loc == nil {
			return fetchedRow{}, false
		}
		return fetchedRow{locationID: locID, summary: entry.summary, hourly: entry.hourly, location: loc}, true
	}

	loc, err := us.LoadLocation(locID)
	if err != nil || loc == nil {
		return fetchedRow{}, false
	}

	var summary model.SegmentWeatherSummary
	var hourly []model.ForecastDataPoint
	if e.provider != nil {
		ts, err := e.provider.FetchForecast(loc.Lat, loc.Lon, hours)
		if err != nil {
			return fetchedRow{}, false
		}
		if ts != nil {
			if agg := aggregateByDateRange(ts.Data, req.DateFrom, req.DateTo, req.HourFrom, req.HourTo); agg != nil {
				summary = *agg
			}
			hourly = filterByDateRange(ts.Data, req.DateFrom, req.DateTo, req.HourFrom, req.HourTo)
		}
	}

	e.cache.set(key, summary, hourly)
	return fetchedRow{locationID: locID, summary: summary, hourly: hourly, location: loc}, true
}

// buildResult turns the fetched rows into the Issue #454 response shape.
func buildResult(fetched []fetchedRow, req CompareRequest) CompareResult {
	empty := CompareResult{
		Ranking:        []RankingEntry{},
		Matrix:         []MatrixEntry{},
		StundenVerlauf: []StundenVerlaufEntry{},
	}
	if len(fetched) == 0 {
		return empty
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

	// Stable sort: highest score first, ties broken by location_id asc.
	type scoredRow struct {
		fr    fetchedRow
		score int
	}
	scored := make([]scoredRow, len(fetched))
	for i, fr := range fetched {
		scored[i] = scoredRow{fr: fr, score: ScoreRow(fr.summary, req.Profile, allMetrics, enabledKeys)}
	}
	sort.SliceStable(scored, func(i, j int) bool {
		if scored[i].score != scored[j].score {
			return scored[i].score > scored[j].score
		}
		return scored[i].fr.locationID < scored[j].fr.locationID
	})

	ranking := make([]RankingEntry, len(scored))
	matrix := make([]MatrixEntry, len(scored))
	stundenVerlauf := make([]StundenVerlaufEntry, len(scored))
	for i, s := range scored {
		var name string
		if s.fr.location != nil {
			name = s.fr.location.Name
		}
		tags := []CompareTag{}
		if i == 0 {
			tags = WinnerTagsTyped(s.fr.summary, req.Profile)
		}
		ranking[i] = RankingEntry{
			LocationID: s.fr.locationID,
			Name:       name,
			Score:      s.score,
			Tags:       tags,
		}
		matrix[i] = MatrixEntry{LocationID: s.fr.locationID, Metrics: metricsMap(s.fr.summary)}
		stundenVerlauf[i] = StundenVerlaufEntry{
			LocationID: s.fr.locationID,
			Hours:      hourlyMap(s.fr.hourly),
		}
	}

	return CompareResult{Ranking: ranking, Matrix: matrix, StundenVerlauf: stundenVerlauf}
}

// metricsMap serialises a SegmentWeatherSummary into a flat snake_case map,
// only including non-nil / non-zero values.
func metricsMap(s model.SegmentWeatherSummary) map[string]any {
	out := map[string]any{}
	if s.TempMinC != nil {
		out["temp_min_c"] = *s.TempMinC
	}
	if s.TempMaxC != nil {
		out["temp_max_c"] = *s.TempMaxC
	}
	if s.WindMaxKmh != nil {
		out["wind_max_kmh"] = *s.WindMaxKmh
	}
	if s.GustMaxKmh != nil {
		out["gust_max_kmh"] = *s.GustMaxKmh
	}
	if s.PrecipSumMm != nil {
		out["precip_sum_mm"] = *s.PrecipSumMm
	}
	if s.SunnyHoursH != nil {
		out["sunny_hours_h"] = *s.SunnyHoursH
	}
	if s.CloudAvgPct != nil {
		out["cloud_avg_pct"] = *s.CloudAvgPct
	}
	if s.VisibilityMinM != nil {
		out["visibility_min_m"] = *s.VisibilityMinM
	}
	if s.SnowDepthCm != nil {
		out["snow_depth_cm"] = *s.SnowDepthCm
	}
	if s.SnowNewSumCm != nil {
		out["snow_new_sum_cm"] = *s.SnowNewSumCm
	}
	if s.UvIndexMax != nil {
		out["uv_index_max"] = *s.UvIndexMax
	}
	if s.PopMaxPct != nil {
		out["pop_max_pct"] = *s.PopMaxPct
	}
	if s.CapeMaxJkg != nil {
		out["cape_max_jkg"] = *s.CapeMaxJkg
	}
	if s.ThunderLevelMax != "" {
		out["thunder_level_max"] = string(s.ThunderLevelMax)
	}
	return out
}

// hourlyMap projects forecast points to the stunden_verlauf shape: two-digit
// UTC hour and a flat values map of the 7 surface fields per the spec.
func hourlyMap(points []model.ForecastDataPoint) []StundenVerlaufHour {
	hours := make([]StundenVerlaufHour, 0, len(points))
	for _, pt := range points {
		values := map[string]any{}
		if pt.T2mC != nil {
			values["t2m_c"] = *pt.T2mC
		}
		if pt.Wind10mKmh != nil {
			values["wind10m_kmh"] = *pt.Wind10mKmh
		}
		if pt.GustKmh != nil {
			values["gust_kmh"] = *pt.GustKmh
		}
		if pt.Precip1hMm != nil {
			values["precip_1h_mm"] = *pt.Precip1hMm
		}
		if pt.CloudTotalPct != nil {
			values["cloud_total_pct"] = *pt.CloudTotalPct
		}
		if pt.ThunderLevel != "" {
			values["thunder_level"] = string(pt.ThunderLevel)
		}
		if pt.VisibilityM != nil {
			values["visibility_m"] = *pt.VisibilityM
		}
		hours = append(hours, StundenVerlaufHour{
			Hour:   fmt.Sprintf("%02d", pt.Time.UTC().Hour()),
			Values: values,
		})
	}
	return hours
}

// filterByDateRange keeps only forecast points whose UTC date is within
// [dateFrom..dateTo] AND whose UTC hour is within [hourFrom..hourTo].
// Empty / unparseable date strings degrade to "no date filter" (hour filter
// still applies).
func filterByDateRange(points []model.ForecastDataPoint, dateFrom, dateTo string, hourFrom, hourTo int) []model.ForecastDataPoint {
	from, fromOK := parseDate(dateFrom)
	to, toOK := parseDate(dateTo)
	out := make([]model.ForecastDataPoint, 0, len(points))
	for _, pt := range points {
		utc := pt.Time.UTC()
		hour := utc.Hour()
		if hour < hourFrom || hour > hourTo {
			continue
		}
		if fromOK && toOK {
			d := time.Date(utc.Year(), utc.Month(), utc.Day(), 0, 0, 0, 0, time.UTC)
			if d.Before(from) || d.After(to) {
				continue
			}
		}
		out = append(out, pt)
	}
	return out
}

// dayAggregate holds a per-day summary plus the point count that produced it
// (for the cloud-cover weighted average over the full window).
type dayAggregate struct {
	summary *model.SegmentWeatherSummary
	count   int
}

// aggregateByDateRange splits points into calendar days, aggregates each day
// via aggregateByDate, and merges the per-day summaries into one.
func aggregateByDateRange(points []model.ForecastDataPoint, dateFrom, dateTo string, hourFrom, hourTo int) *model.SegmentWeatherSummary {
	from, fromOK := parseDate(dateFrom)
	to, toOK := parseDate(dateTo)
	if !fromOK || !toOK || to.Before(from) {
		return nil
	}

	days := make([]dayAggregate, 0)
	for d := from; !d.After(to); d = d.AddDate(0, 0, 1) {
		dateStr := d.Format("2006-01-02")
		filtered := make([]model.ForecastDataPoint, 0)
		for _, pt := range points {
			utc := pt.Time.UTC()
			if utc.Format("2006-01-02") != dateStr {
				continue
			}
			if utc.Hour() < hourFrom || utc.Hour() > hourTo {
				continue
			}
			filtered = append(filtered, pt)
		}
		if agg := aggregateByDate(filtered, ""); agg != nil {
			days = append(days, dayAggregate{summary: agg, count: len(filtered)})
		}
	}
	if len(days) == 0 {
		return nil
	}
	return mergeDays(days)
}

// mergeDays combines per-day SegmentWeatherSummary aggregates into a single
// summary. min/max/sum/weighted-avg per the spec §3.
func mergeDays(days []dayAggregate) *model.SegmentWeatherSummary {
	out := &model.SegmentWeatherSummary{ThunderLevelMax: model.ThunderNone}
	var precipSum, sunnySum, snowNewSum float64
	precipAny, sunnyAny, snowNewAny := false, false, false
	var cloudWeighted float64
	var cloudWeights int
	var lastSnowDepth *float64

	for _, d := range days {
		s := d.summary
		updateMinFloat(&out.TempMinC, s.TempMinC)
		updateMaxFloat(&out.TempMaxC, s.TempMaxC)
		updateMaxFloat(&out.WindMaxKmh, s.WindMaxKmh)
		updateMaxFloat(&out.GustMaxKmh, s.GustMaxKmh)
		updateMinFloat(&out.VisibilityMinM, s.VisibilityMinM)
		updateMaxFloat(&out.UvIndexMax, s.UvIndexMax)
		updateMaxFloat(&out.CapeMaxJkg, s.CapeMaxJkg)
		updateMaxInt(&out.PopMaxPct, s.PopMaxPct)

		if s.PrecipSumMm != nil {
			precipSum += *s.PrecipSumMm
			precipAny = true
		}
		if s.SunnyHoursH != nil {
			sunnySum += *s.SunnyHoursH
			sunnyAny = true
		}
		if s.SnowNewSumCm != nil {
			snowNewSum += *s.SnowNewSumCm
			snowNewAny = true
		}
		if s.CloudAvgPct != nil && d.count > 0 {
			cloudWeighted += float64(*s.CloudAvgPct) * float64(d.count)
			cloudWeights += d.count
		}
		if s.SnowDepthCm != nil {
			v := *s.SnowDepthCm
			lastSnowDepth = &v
		}
		if thunderOrder(s.ThunderLevelMax) > thunderOrder(out.ThunderLevelMax) {
			out.ThunderLevelMax = s.ThunderLevelMax
		}
	}

	if precipAny {
		v := precipSum
		out.PrecipSumMm = &v
	}
	if sunnyAny {
		v := math.Round(sunnySum*10) / 10
		out.SunnyHoursH = &v
	}
	if snowNewAny {
		v := snowNewSum
		out.SnowNewSumCm = &v
	}
	if cloudWeights > 0 {
		v := int(math.Round(cloudWeighted / float64(cloudWeights)))
		out.CloudAvgPct = &v
	}
	if lastSnowDepth != nil {
		out.SnowDepthCm = lastSnowDepth
	}
	return out
}

// parseDate is a permissive YYYY-MM-DD parser. Returns (zero, false) on error.
func parseDate(s string) (time.Time, bool) {
	if s == "" {
		return time.Time{}, false
	}
	t, err := time.Parse("2006-01-02", s)
	if err != nil {
		return time.Time{}, false
	}
	return t, true
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
