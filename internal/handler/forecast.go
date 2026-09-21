package handler

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/provider"
)

// Wartezeit auf die Kontingent-Auskunft des Python-Core. Kurz gehalten: der
// Core schreibt unter einer fcntl-Sperre, und diese Reservierung sitzt VOR dem
// eigentlichen Wetterabruf im Request-Pfad. Laeuft sie ab, gilt fail-open.
const forecastReserveTimeout = 5 * time.Second

// forecastReservePfad ist der Kontingent-Endpunkt des Python-Core (#2391).
const forecastReservePfad = "/api/_internal/forecast-budget/reserve"

// budgetUrteil ist die Antwort des Core auf eine Reservierung.
type budgetUrteil struct {
	Allowed     bool `json:"allowed"`
	RetryAfterS int  `json:"retry_after_s"`
}

// reserviereForecastBudget fragt beim Python-Core an, ob dieser Abruf noch ins
// Tageskontingent passt, und bucht ihn im Erfolgsfall dort (ADR-0076: die
// Entscheidung bleibt in ForecastBudgetGate, Go baut sie nicht nach).
//
// Die Query wird FRISCH gebaut -- eine vom Client mitgeschickte user_id darf
// nie durchgereicht werden (Muster internal/handler/proxy.go:appendUserID).
// Der Client bekommt bewusst KEINEN eigenen Transport: coreauth umhuellt
// http.DefaultTransport global, nur darueber traegt die Anfrage X-GZ-Core-Auth.
func reserviereForecastBudget(coreURL, userID string) (budgetUrteil, error) {
	frage := url.Values{}
	frage.Set("user_id", userID)
	frage.Set("priority", "polling")
	ziel := strings.TrimSuffix(coreURL, "/") + forecastReservePfad + "?" + frage.Encode()

	client := &http.Client{Timeout: forecastReserveTimeout}
	resp, err := client.Post(ziel, "application/json", nil)
	if err != nil {
		return budgetUrteil{}, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return budgetUrteil{}, fmt.Errorf("core antwortete mit Status %d", resp.StatusCode)
	}

	var urteil budgetUrteil
	if err := json.NewDecoder(resp.Body).Decode(&urteil); err != nil {
		return budgetUrteil{}, err
	}
	return urteil, nil
}

// klemmeRetryAfter haelt die Wartezeit im sinnvollen Band: der Zaehler wird an
// der UTC-Tagesgrenze zurueckgesetzt, mehr als ein voller Tag kann nie
// herauskommen -- und ein Header "Retry-After: 0" waere keine Auskunft.
func klemmeRetryAfter(sekunden int) int {
	const sekundenJeTag = 86400
	if sekunden < 1 {
		return 1
	}
	if sekunden > sekundenJeTag {
		return sekundenJeTag
	}
	return sekunden
}

func ForecastHandler(p provider.WeatherProvider, coreURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")

		// Auth ZUERST -- vor der Parametervalidierung und vor jeder
		// Reservierung: ohne echte Kennung buchte der Core auf ein leeres
		// oder fremdes Konto (ADR-0003, ADR-0075 Punkt 4).
		userID := middleware.UserIDFromContext(r.Context())
		if userID == "" {
			w.WriteHeader(http.StatusUnauthorized)
			json.NewEncoder(w).Encode(map[string]string{
				"error":  "unauthorized",
				"detail": "authentication required",
			})
			return
		}

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

		// Kontingent-Reservierung vor dem Abruf (#2391). Fail-open: ein
		// unerreichbarer oder fehlerhafter Zaehler darf nie einen Abruf
		// blockieren -- Verhalten wie vor dieser Aenderung.
		if urteil, err := reserviereForecastBudget(coreURL, userID); err != nil {
			log.Printf("[forecast] WARN: budget reserve fehlgeschlagen, fail-open: %v", err)
		} else if !urteil.Allowed {
			w.Header().Set("Retry-After", strconv.Itoa(klemmeRetryAfter(urteil.RetryAfterS)))
			w.WriteHeader(http.StatusTooManyRequests)
			json.NewEncoder(w).Encode(map[string]string{
				"error":  "budget_exceeded",
				"detail": "daily forecast budget exhausted for this user",
			})
			return
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
