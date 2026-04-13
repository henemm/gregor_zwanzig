package handler

import (
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/henemm/gregor-api/internal/provider"
)

func ForecastHandler(p provider.WeatherProvider) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")

		latStr := r.URL.Query().Get("lat")
		lonStr := r.URL.Query().Get("lon")
		hoursStr := r.URL.Query().Get("hours")

		if latStr == "" || lonStr == "" {
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]string{
				"error":  "invalid_params",
				"detail": "lat and lon are required",
			})
			return
		}

		lat, err := strconv.ParseFloat(latStr, 64)
		if err != nil || lat < -90 || lat > 90 {
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]string{
				"error":  "invalid_params",
				"detail": "lat must be between -90 and 90",
			})
			return
		}

		lon, err := strconv.ParseFloat(lonStr, 64)
		if err != nil || lon < -180 || lon > 180 {
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]string{
				"error":  "invalid_params",
				"detail": "lon must be between -180 and 180",
			})
			return
		}

		hours := 48
		if hoursStr != "" {
			h, err := strconv.Atoi(hoursStr)
			if err != nil || h < 1 || h > 240 {
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]string{
					"error":  "invalid_params",
					"detail": "hours must be between 1 and 240",
				})
				return
			}
			hours = h
		}

		ts, err := p.FetchForecast(lat, lon, hours)
		if err != nil {
			w.WriteHeader(http.StatusBadGateway)
			json.NewEncoder(w).Encode(map[string]string{
				"error":  "provider_error",
				"detail": err.Error(),
			})
			return
		}

		json.NewEncoder(w).Encode(ts)
	}
}
