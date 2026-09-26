package handler

// Staging-only Seed fuer Tarif und SMS-Tageszaehler — Issue #2423.
// Spec: docs/specs/modules/staging_seed_endpoint.md
//
// Registriert nur bei GZ_ENV=staging (router.go), anmeldepflichtig. Die
// Nutzerkennung stammt ausschliesslich aus dem Auth-Kontext; Nutzerfelder im
// Rumpf werden ignoriert. Reihenfolge: validieren, Zaehler (Python-Core),
// Tarif — bei Core-Fehler wird der Tarif nicht angefasst.

import (
	"bytes"
	"encoding/json"
	"io"
	"math"
	"net/http"
	"net/url"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/store"
)

const seedMaxCounter = 1000

// seedCounter liest einen Zaehlerwert (0..1000, Ganzzahl) aus dem Rumpf.
// present=false: Feld fehlt; ok=false: Feld vorhanden aber ungueltig.
func seedCounter(raw map[string]json.RawMessage, key string) (val int, present, ok bool) {
	rm, has := raw[key]
	if !has {
		return 0, false, true
	}
	if string(bytes.TrimSpace(rm)) == "null" {
		return 0, true, false
	}
	var f float64
	if err := json.Unmarshal(rm, &f); err != nil || f != math.Trunc(f) || f < 0 || f > seedMaxCounter {
		return 0, true, false
	}
	return int(f), true, true
}

func StagingSeedHandler(s *store.Store, cfg config.Config) http.HandlerFunc {
	client := &http.Client{Timeout: 3 * time.Second}
	return func(w http.ResponseWriter, r *http.Request) {
		userID := middleware.UserIDFromContext(r.Context())
		var raw map[string]json.RawMessage
		if err := json.NewDecoder(io.LimitReader(r.Body, 4096)).Decode(&raw); err != nil {
			writeJSONError(w, http.StatusBadRequest, "validation_error")
			return
		}
		tier := ""
		_, hasTier := raw["tier"]
		if hasTier {
			if err := json.Unmarshal(raw["tier"], &tier); err != nil || (tier != "free" && tier != "standard" && tier != "premium") {
				writeJSONError(w, http.StatusBadRequest, "validation_error")
				return
			}
		}
		sms, hasSms, okSms := seedCounter(raw, "sms")
		prem, hasPrem, okPrem := seedCounter(raw, "premium_sms")
		if !okSms || !okPrem {
			writeJSONError(w, http.StatusBadRequest, "validation_error")
			return
		}
		if !hasTier && !hasSms && !hasPrem {
			writeJSONError(w, http.StatusBadRequest, "nothing_to_set")
			return
		}
		user, err := s.LoadUser(userID)
		if err != nil || user == nil {
			writeJSONError(w, http.StatusNotFound, "not_found")
			return
		}

		resp := map[string]any{}
		if hasSms || hasPrem {
			body := map[string]any{"user_id": userID}
			if hasSms {
				body["sms"] = sms
			}
			if hasPrem {
				body["premium_sms"] = prem
			}
			payload, _ := json.Marshal(body)
			cr, err := client.Post(cfg.PythonCoreURL+"/api/_internal/sms/seed-daily-usage", "application/json", bytes.NewReader(payload))
			if err != nil {
				writeJSONError(w, http.StatusBadGateway, "core_unavailable")
				return
			}
			defer cr.Body.Close()
			var stand map[string]int
			if cr.StatusCode/100 != 2 || json.NewDecoder(cr.Body).Decode(&stand) != nil {
				writeJSONError(w, http.StatusBadGateway, "core_unavailable")
				return
			}
			resp["sms"], resp["premium_sms"] = stand["sms"], stand["premium_sms"]
		}
		if hasTier {
			if err := s.SetUserTier(userID, tier); err != nil {
				writeJSONError(w, http.StatusInternalServerError, "internal error")
				return
			}
			user.Tier = tier
		}
		resp["tier"] = user.Tier
		if _, ok := resp["sms"]; !ok {
			// Reiner Tarif-Aufruf: Stand ueber den Leseweg, Ausfall ist kein Fehler.
			if ur, err := client.Get(cfg.PythonCoreURL + "/api/_internal/sms/daily-usage?user_id=" + url.QueryEscape(userID)); err == nil {
				defer ur.Body.Close()
				var u struct {
					SMS        struct{ Used int } `json:"sms"`
					PremiumSMS struct{ Used int } `json:"premium_sms"`
				}
				if ur.StatusCode == http.StatusOK && json.NewDecoder(ur.Body).Decode(&u) == nil {
					resp["sms"], resp["premium_sms"] = u.SMS.Used, u.PremiumSMS.Used
				}
			}
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}
}
