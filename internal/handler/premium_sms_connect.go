package handler

// PostPremiumSmsLearnHandler — POST /api/internal/premium-sms-learn
//
// Issue #1676 Scheibe S1: lernt die von Garmin je Gespraech neu vergebene
// Rueckadresse fuer den Premium-SMS-Rueckkanal. Wird ausschliesslich vom
// Python-Core (InboundSmsReader, localhost) aufgerufen — Vorbild
// telegram_connect.go::PostTelegramConnectHandler (localhost-only-Sperre).
//
// Spec: docs/specs/modules/feat_1676_s1_premium_sms_rueckkanal.md v1.1,
// Implementation Details "Go: neuer Endpoint POST /api/internal/premium-sms-learn".
//
// R3-Aufloesung (Kandidaten nur Premium-Tier):
//  1. Treffer auf gespeicherte PremiumSmsReplyTo -> dieser Nutzer.
//  2. Sonst genau EIN Premium-Kandidat -> dieser Nutzer.
//  3. Sonst (0 oder >1 ohne Treffer) -> kein Treffer, NIE Fallback auf "default".
//
// Der Dry-Run-Zweig (AC-10) ist ein eigener Rueckgabepfad VOR SaveUser, kein
// `if` drumherum — SaveUser ist im Dry-Run strukturell unerreichbar.
import (
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// PostPremiumSmsLearnHandler baut den Handler mit injiziertem Store.
func PostPremiumSmsLearnHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !requireLocalOnly(w, r) {
			return
		}

		var body struct {
			From   string `json:"from"`
			DryRun bool   `json:"dry_run"`
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil || body.From == "" {
			http.Error(w, "bad request", http.StatusBadRequest)
			return
		}

		userIDs, err := s.ListUserIDs()
		if err != nil {
			http.Error(w, "list users failed", http.StatusInternalServerError)
			return
		}

		var candidates []*model.User
		var storedMatch *model.User
		for _, id := range userIDs {
			user, err := s.LoadUser(id)
			if err != nil || user == nil {
				continue
			}
			if model.EffectiveTier(user.Tier) != "premium" {
				continue
			}
			candidates = append(candidates, user)
			if user.PremiumSmsReplyTo == body.From {
				storedMatch = user
			}
		}

		var target *model.User
		if storedMatch != nil {
			target = storedMatch
		} else if len(candidates) == 1 {
			target = candidates[0]
		}

		w.Header().Set("Content-Type", "application/json")

		if body.DryRun {
			// Strukturell eigener Rueckgabepfad: SaveUser wird von hier aus
			// nie erreicht, unabhaengig vom Ergebnis der R3-Aufloesung.
			if target == nil {
				json.NewEncoder(w).Encode(map[string]string{
					"status":  "dry_run",
					"outcome": "would_skip",
					"reason":  "no_unique_premium_candidate",
				})
				return
			}
			maskedFrom := maskPhoneNumber(body.From)
			json.NewEncoder(w).Encode(map[string]string{
				"status":      "dry_run",
				"outcome":     "would_learn",
				"user_id":     target.ID,
				"masked_from": maskedFrom,
			})
			return
		}

		if target == nil {
			w.WriteHeader(http.StatusConflict)
			json.NewEncoder(w).Encode(map[string]string{
				"status": "skipped",
				"reason": "no_unique_premium_candidate",
			})
			return
		}

		now := time.Now().UTC()
		target.PremiumSmsReplyTo = body.From
		target.PremiumSmsReplyAt = &now
		if err := s.SaveUser(*target); err != nil {
			http.Error(w, "save failed", http.StatusInternalServerError)
			return
		}

		json.NewEncoder(w).Encode(map[string]string{"status": "ok", "user_id": target.ID})
	}
}

// maskPhoneNumber loggt/meldet Rufnummern nur maskiert (Spec: "Protokolliere
// Rufnummern nur maskiert") — alle bis auf die letzten drei Stellen werden
// verdeckt.
func maskPhoneNumber(number string) string {
	if len(number) <= 3 {
		return strings.Repeat("*", len(number))
	}
	return strings.Repeat("*", len(number)-3) + number[len(number)-3:]
}
