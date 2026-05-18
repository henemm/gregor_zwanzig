package handler

import (
	"encoding/json"
	"net/http"
	"sync"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/provider"
	"github.com/henemm/gregor-api/internal/risk"
	"github.com/henemm/gregor-api/internal/store"
)

// StagesWeatherHandler liefert pro Stage eines Trips eine kompakte Wetter-
// Summary plus Risiko-Level. Stage ohne Datum oder Waypoints liefert null
// (Fail-soft, kein 5xx). Issue #203 / Spec issue_203_stage_weather_risk.md.
func StagesWeatherHandler(s *store.Store, p provider.WeatherProvider) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")

		us := s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")

		trip, err := us.LoadTrip(id)
		if err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}
		if trip == nil {
			w.WriteHeader(http.StatusNotFound)
			w.Write([]byte(`{"error":"not_found"}`))
			return
		}

		results := make(map[string]*model.StageWeatherResult, len(trip.Stages))
		var mu sync.Mutex
		var wg sync.WaitGroup

		for i := range trip.Stages {
			stage := trip.Stages[i]
			if stage.ID == "" {
				continue
			}
			wg.Add(1)
			go func(st model.Stage) {
				defer wg.Done()
				res := computeStageWeather(st, p)
				mu.Lock()
				results[st.ID] = res
				mu.Unlock()
			}(stage)
		}
		wg.Wait()

		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(model.StagesWeatherResponse{Results: results})
	}
}

// computeStageWeather verarbeitet eine einzelne Stage und liefert ein
// Result oder nil (bei fehlenden Daten / API-Fehler).
func computeStageWeather(stage model.Stage, p provider.WeatherProvider) *model.StageWeatherResult {
	if stage.Date == "" || len(stage.Waypoints) == 0 || p == nil {
		return nil
	}

	// Mittelpunkt aller Waypoints als repräsentative Koordinate.
	var sumLat, sumLon float64
	for _, wp := range stage.Waypoints {
		sumLat += wp.Lat
		sumLon += wp.Lon
	}
	n := float64(len(stage.Waypoints))
	avgLat := sumLat / n
	avgLon := sumLon / n

	ts, err := p.FetchForecast(avgLat, avgLon, 168)
	if err != nil || ts == nil {
		return nil
	}

	summary := aggregateForecasts(ts.Data, stage.Date)
	if summary == nil {
		return nil
	}

	// IsDay: 1 wenn an dem Tag mindestens ein Punkt IsDay=1 hat.
	isDay := computeIsDay(ts.Data, stage.Date)

	assessment := risk.Assess(*summary)
	level := risk.GetMaxRiskLevel(assessment)
	riskStr := mapRiskLevel(level)

	ws := &model.StageWeatherSummary{
		TempMinC:   summary.TempMinC,
		TempMaxC:   summary.TempMaxC,
		WindMaxKmh: summary.WindMaxKmh,
		PrecipMm:   summary.PrecipSumMm,
		WmoCode:    summary.DominantWmoCode,
		IsDay:      isDay,
	}
	return &model.StageWeatherResult{
		WeatherSummary: ws,
		Risk:           &riskStr,
	}
}

func mapRiskLevel(l model.RiskLevel) string {
	switch l {
	case model.RiskHigh:
		return "red"
	case model.RiskModerate:
		return "yellow"
	default:
		return "green"
	}
}

func computeIsDay(points []model.ForecastDataPoint, stageDate string) *int {
	any := false
	hasDay := false
	for _, pt := range points {
		if pt.Time.UTC().Format("2006-01-02") != stageDate {
			continue
		}
		if pt.IsDay != nil {
			any = true
			if *pt.IsDay == 1 {
				hasDay = true
				break
			}
		}
	}
	if !any {
		return nil
	}
	v := 0
	if hasDay {
		v = 1
	}
	return &v
}

// aggregateForecasts aggregiert Forecast-Punkte auf einen UTC-Tag.
// Liefert nil wenn nach Filter keine Punkte übrig bleiben.
func aggregateForecasts(points []model.ForecastDataPoint, stageDate string) *model.SegmentWeatherSummary {
	filtered := make([]model.ForecastDataPoint, 0, len(points))
	for _, pt := range points {
		if pt.Time.UTC().Format("2006-01-02") == stageDate {
			filtered = append(filtered, pt)
		}
	}
	if len(filtered) == 0 {
		return nil
	}

	out := &model.SegmentWeatherSummary{ThunderLevelMax: model.ThunderNone}

	var precipSum float64
	precipAny := false
	wmoCounts := map[int]int{}

	for _, pt := range filtered {
		updateMinFloat(&out.TempMinC, pt.T2mC)
		updateMaxFloat(&out.TempMaxC, pt.T2mC)
		updateMaxFloat(&out.WindMaxKmh, pt.Wind10mKmh)
		updateMaxFloat(&out.GustMaxKmh, pt.GustKmh)
		updateMinFloat(&out.VisibilityMinM, pt.VisibilityM)
		updateMinFloat(&out.WindChillMinC, pt.WindChillC)
		updateMaxFloat(&out.CapeMaxJkg, pt.CapeJkg)
		updateMaxInt(&out.PopMaxPct, pt.PopPct)

		if pt.Precip1hMm != nil {
			precipSum += *pt.Precip1hMm
			precipAny = true
		}
		if thunderOrder(pt.ThunderLevel) > thunderOrder(out.ThunderLevelMax) {
			out.ThunderLevelMax = pt.ThunderLevel
		}
		if pt.WmoCode != nil {
			wmoCounts[*pt.WmoCode]++
		}
	}

	if precipAny {
		s := precipSum
		out.PrecipSumMm = &s
	}
	out.DominantWmoCode = selectDominantWmoCode(wmoCounts)

	return out
}

func selectDominantWmoCode(wmoCounts map[int]int) *int {
	if len(wmoCounts) == 0 {
		return nil
	}
	best := -1
	bestTier := -1
	for code := range wmoCounts {
		tier := wmoSeverityTier(code)
		// Höchster Schweregrad gewinnt; bei Gleichstand höchster Code.
		if tier > bestTier || (tier == bestTier && code > best) {
			best = code
			bestTier = tier
		}
	}
	return &best
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

// wmoSeverityTier liefert den Schweregrad eines WMO-Codes für die Auswahl
// des dominanten Codes auf einem Aggregations-Fenster. Höhere Tier =
// kritischer für Weitwanderer. Spec issue_203_stage_weather_risk.md §2.
func wmoSeverityTier(code int) int {
	switch {
	case code >= 95:
		return 5 // Gewitter (95-99)
	case code >= 80 && code <= 82:
		return 4 // Regen-Schauer (80-82)
	case code >= 71 && code <= 77:
		return 3 // Schnee (71-77)
	case code >= 51 && code <= 67:
		return 4 // Nieselregen/Regen (51-67) — gleiche Schwere wie Schauer
	case code >= 45 && code <= 48:
		return 2 // Nebel (45-48)
	case code >= 2 && code <= 3:
		return 1 // Bewölkt (2-3)
	default:
		return 0 // Klar (0-1) / unbekannt
	}
}
