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
// Aufloesung seit Issue #2154 Scheibe A (Kandidaten nur Premium-Tier); loest
// die alte R3-Heuristik ab, deren Ein-Kandidaten-Fallback jede fremde Nummer
// ohne Geheimnis zur Rueckadresse machte:
//  1. Frischer Treffer auf gespeicherte PremiumSmsReplyTo (innerhalb
//     model.PremiumSmsReplyTTL) -> dieser Nutzer, Code wird ignoriert.
//  2. Sonst ohne Code -> kein Ziel (der eigentliche Bugfix, AC-1).
//  3. Sonst mit Code -> Budget der Ratebremse pruefen, dann bcrypt-Vergleich
//     gegen den gespeicherten Verknuepfungs-Code jedes Kandidaten; genau ein
//     Treffer -> Ziel, sonst Zaehler +1 und kein Ziel. NIE Fallback auf
//     "default".
//
// Der Dry-Run-Zweig (AC-10) ist ein eigener Rueckgabepfad VOR SaveUser, kein
// `if` drumherum — SaveUser ist im Dry-Run strukturell unerreichbar.
import (
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// Ablehnungsgruende, wie sie im Antwortkoerper erscheinen.
const (
	reasonLinkCodeRequired    = "link_code_required"
	reasonLinkCodeInvalid     = "link_code_invalid"
	reasonLinkCodeRateLimited = "link_code_rate_limited"
)

// PostPremiumSmsLearnHandler baut den Handler mit injiziertem Store und
// injizierter Ratebremse (prozessweit, s. premium_sms_ratelimit.go).
func PostPremiumSmsLearnHandler(s *store.Store, rl *PremiumSmsRateLimiter) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !requireLocalOnly(w, r) {
			return
		}

		var body struct {
			From   string `json:"from"`
			Code   string `json:"code"`
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

		w.Header().Set("Content-Type", "application/json")

		if body.DryRun {
			// Strukturell eigener Rueckgabepfad: weder SaveUser noch der
			// prozessweite Fehlversuchszaehler sind von hier aus erreichbar.
			// Der Trockenlauf rechnet gegen eine Wegwerf-Bremse, damit ein
			// falscher Code die echte Bremse nie beruehrt (AC-8).
			target, reason := resolvePremiumSmsTarget(s, candidates, storedMatch, body.Code, rl.scratch())
			if target == nil {
				json.NewEncoder(w).Encode(map[string]string{
					"status":  "dry_run",
					"outcome": "would_skip",
					"reason":  reason,
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

		target, reason := resolvePremiumSmsTarget(s, candidates, storedMatch, body.Code, rl)
		if reason == reasonLinkCodeRateLimited {
			w.WriteHeader(http.StatusTooManyRequests)
			json.NewEncoder(w).Encode(map[string]string{
				"status": "skipped",
				"reason": reason,
			})
			return
		}
		if target == nil {
			w.WriteHeader(http.StatusConflict)
			json.NewEncoder(w).Encode(map[string]string{
				"status": "skipped",
				"reason": reason,
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

// resolvePremiumSmsTarget setzt die Schritte 4-6 des Entscheidungsbaums um und
// liefert das Zielkonto oder nil samt Ablehnungsgrund (Issue #2154 Scheibe A).
//
// Die Reihenfolge ist die Zusicherung: das Budget der Ratebremse wird VOR jedem
// bcrypt-Vergleich gefragt (AC-7). Stuende die Pruefung dahinter, koennte ein
// Angreifer weiter raten und die Bremse waere Zierde.
func resolvePremiumSmsTarget(
	s *store.Store, candidates []*model.User, storedMatch *model.User,
	code string, rl *PremiumSmsRateLimiter,
) (*model.User, string) {
	// Schritt 4: nur ein FRISCHER gespeicherter Treffer bestaetigt ohne Code.
	// Dieselbe Frist-Semantik wie im Sendepfad und in der Oberflaeche — eine
	// zweite, eigene Vergleichsformel hier waere ein Drift-Risiko.
	if storedMatch != nil &&
		model.DerivePremiumSmsReplyState(storedMatch.PremiumSmsReplyTo, storedMatch.PremiumSmsReplyAt) == model.PremiumSmsStateFresh {
		return storedMatch, ""
	}

	// Schritt 5: ohne Code kein Ziel. Hier stand bis #2154 der
	// len(candidates)==1-Fallback — er entfaellt ersatzlos (AC-1).
	if code == "" {
		return nil, reasonLinkCodeRequired
	}

	// Schritt 6: Budget zuerst, Hash-Vergleich danach.
	if !rl.Allow() {
		return nil, reasonLinkCodeRateLimited
	}
	var matches []*model.User
	for _, c := range candidates {
		stored, err := s.LoadLinkCode(c.ID)
		if err != nil || stored == nil || stored.CodeHash == "" {
			continue
		}
		if bcrypt.CompareHashAndPassword([]byte(stored.CodeHash), []byte(code)) == nil {
			matches = append(matches, c)
		}
	}
	if len(matches) == 1 {
		return matches[0], ""
	}
	rl.RecordFailure()
	return nil, reasonLinkCodeInvalid
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
